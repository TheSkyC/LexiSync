# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from plugins.plugin_base import PluginBase
from PySide6.QtWidgets import QMessageBox, QFileDialog, QCheckBox
import os
import polib
import logging


class MODecompilerPlugin(PluginBase):
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)

    def plugin_id(self) -> str:
        return "com_theskyc_mo_decompiler"

    def name(self) -> str:
        return self._("MO Decompiler")

    def description(self) -> str:
        return self._(
            "Decompiles .mo files into .po files upon drag-and-drop or via menu.")

    def version(self) -> str:
        return "1.0.1"

    def author(self) -> str:
        return "TheSkyC"

    def compatible_app_version(self) -> str:
        return "1.1"

    def url(self) -> str:
        return "https://github.com/TheSkyC/overwatch-localizer/tree/master/plugins/com_theskyc_mo_decompiler"

    def add_menu_items(self) -> list:
        return [
            (self._("Decompile MO File..."), self.open_mo_file_dialog)
        ]

    def on_files_dropped(self, file_paths: list) -> bool:
        mo_files = [f for f in file_paths if f.lower().endswith('.mo')]
        if not mo_files:
            return False
        self.process_files(mo_files)
        return True

    def open_mo_file_dialog(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self.main_window,
            self._("Select MO files to decompile"),
            self.main_window.config.get("last_dir", ""),
            f"{self._('Compiled MO Files')} (*.mo);;{self._('All Files')} (*)"
        )
        if file_paths:
            self.process_files(file_paths)

    def process_files(self, mo_paths: list):
        if not mo_paths:
            return

        if not self.main_window.prompt_save_if_modified():
            return

        batch_save_choice = None
        batch_conflict_choice = None
        is_batch_mode = len(mo_paths) > 1

        if is_batch_mode:
            file_list = "\n - ".join(os.path.basename(p) for p in mo_paths[:10])
            if len(mo_paths) > 10:
                file_list += "\n - ..."

            reply = QMessageBox.question(
                self.main_window,
                self._("Batch Decompile"),
                self._("You are about to decompile {count} .mo files:\n\n - {files}\n\nDo you want to proceed?").format(
                    count=len(mo_paths), files=file_list
                )
            )
            if reply == QMessageBox.No:
                return

        decompiled_files = []
        for mo_path in mo_paths:
            po_path, batch_save_choice, batch_conflict_choice = self._handle_single_file(
                mo_path, batch_save_choice, batch_conflict_choice, is_batch_mode
            )
            if po_path:
                decompiled_files.append(po_path)
            elif batch_save_choice == 'cancel' or batch_conflict_choice == 'cancel':
                self.main_window.update_statusbar(self._("Batch operation cancelled by user."))
                break

        if decompiled_files:
            if not self.main_window.prompt_save_if_modified():
                return

            if len(decompiled_files) == 1:
                self.main_window.import_po_file_dialog_with_path(decompiled_files[0])
            else:
                QMessageBox.information(
                    self.main_window,
                    self._("Batch Decompile Complete"),
                    self._(
                        "{count} files were successfully decompiled. The application will now open the first file:\n\n{first_file}").format(
                        count=len(decompiled_files), first_file=os.path.basename(decompiled_files[0])
                    )
                )
                self.main_window.import_po_file_dialog_with_path(decompiled_files[0])

    def _handle_single_file(self, mo_path: str, batch_save_choice: str | None, batch_conflict_choice: str | None,
                            is_batch_mode: bool):
        try:
            po_path = None

            if batch_save_choice is None:
                msg_box = QMessageBox(self.main_window)
                msg_box.setWindowTitle(self._("Decompile MO File"))
                msg_box.setText(self._("Detected .mo file: {filename}").format(filename=os.path.basename(mo_path)))
                msg_box.setInformativeText(self._("How would you like to save the decompiled .po file?"))
                save_to_dir_btn = msg_box.addButton(self._("Save to Same Directory"), QMessageBox.ActionRole)
                save_as_btn = msg_box.addButton(self._("Save As..."), QMessageBox.ActionRole)
                msg_box.addButton(QMessageBox.Cancel)
                if is_batch_mode:
                    apply_all_checkbox = QCheckBox(self._("Apply to all subsequent files"))
                    apply_all_checkbox.setChecked(True)
                    msg_box.setCheckBox(apply_all_checkbox)
                msg_box.exec()
                clicked_button = msg_box.clickedButton()
                if clicked_button == save_to_dir_btn:
                    current_save_choice = 'same_dir'
                elif clicked_button == save_as_btn:
                    current_save_choice = 'save_as'
                else:
                    batch_save_choice = 'cancel'
                    return None, batch_save_choice, batch_conflict_choice

                if is_batch_mode and apply_all_checkbox.isChecked():
                    batch_save_choice = current_save_choice
            else:
                current_save_choice = batch_save_choice

            if current_save_choice == 'same_dir':
                target_dir = os.path.dirname(mo_path)
                base_name = os.path.splitext(os.path.basename(mo_path))[0]
                po_path = os.path.join(target_dir, f"{base_name}.po")
            elif current_save_choice == 'save_as':
                default_path = os.path.splitext(mo_path)[0] + ".po"
                po_path, _ = QFileDialog.getSaveFileName(
                    self.main_window, self._("Save Decompiled PO File"), default_path, f"{self._('PO Files')} (*.po)"
                )
                if not po_path:
                    return None, 'cancel', batch_conflict_choice

            while os.path.exists(po_path):
                current_conflict_choice = batch_conflict_choice
                if current_conflict_choice is None:
                    conflict_box = QMessageBox(self.main_window)
                    conflict_box.setWindowTitle(self._("File Conflict"))
                    conflict_box.setText(
                        self._("The file '{filename}' already exists.").format(filename=os.path.basename(po_path)))
                    conflict_box.setInformativeText(self._("What would you like to do?"))

                    overwrite_btn = conflict_box.addButton(self._("Overwrite"), QMessageBox.ActionRole)
                    rename_btn = conflict_box.addButton(self._("Rename"), QMessageBox.ActionRole)
                    conflict_box.addButton(QMessageBox.Cancel)

                    if is_batch_mode:
                        apply_all_checkbox_conflict = QCheckBox(self._("Apply to all subsequent conflicts"))
                        apply_all_checkbox_conflict.setChecked(True)
                        conflict_box.setCheckBox(apply_all_checkbox_conflict)

                    conflict_box.exec()

                    clicked_conflict_btn = conflict_box.clickedButton()

                    if clicked_conflict_btn == overwrite_btn:
                        current_conflict_choice = 'overwrite'
                    elif clicked_conflict_btn == rename_btn:
                        current_conflict_choice = 'rename'
                    else:
                        batch_conflict_choice = 'cancel'
                        return None, batch_save_choice, batch_conflict_choice

                    if is_batch_mode and apply_all_checkbox_conflict.isChecked():
                        batch_conflict_choice = current_conflict_choice

                if current_conflict_choice == 'overwrite':
                    break
                elif current_conflict_choice == 'rename':
                    base, ext = os.path.splitext(po_path)
                    i = 1
                    while os.path.exists(f"{base} ({i}){ext}"):
                        i += 1
                    po_path = f"{base} ({i}){ext}"
                    break
                else:
                    return None, batch_save_choice, 'cancel'

            mo_file = polib.mofile(mo_path)
            mo_file.save_as_pofile(po_path)

            self.main_window.update_statusbar(
                self._("Successfully decompiled '{mo}' to '{po}'.").format(
                    mo=os.path.basename(mo_path), po=os.path.basename(po_path)
                )
            )
            return po_path, batch_save_choice, batch_conflict_choice

        except Exception as e:
            self.logger.error(f"Failed to decompile {mo_path}: {e}", exc_info=True)
            QMessageBox.critical(
                self.main_window,
                self._("Decompile Error"),
                self._("An error occurred while decompiling '{filename}':\n\n{error}").format(
                    filename=os.path.basename(mo_path), error=str(e)
                )
            )
            return None, batch_save_choice, batch_conflict_choice