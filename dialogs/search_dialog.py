# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QCheckBox, QWidget, QMessageBox, QGroupBox, QAbstractItemView, QApplication
)
from PySide6.QtCore import Qt, QItemSelectionModel, QModelIndex, QTimer
import re
from utils.localization import _


class AdvancedSearchDialog(QDialog):
    def __init__(self, parent, title, app_instance):
        super().__init__(parent)
        self.app = app_instance

        self.setWindowTitle(title)
        self.setModal(False)

        self.search_term_entry = QLineEdit()
        self.replace_term_entry = QLineEdit()
        self.case_sensitive_checkbox = QCheckBox(_("Case sensitive"))
        self.search_in_original_checkbox = QCheckBox(_("Original"))
        self.search_in_translation_checkbox = QCheckBox(_("Translation"))
        self.search_in_comment_checkbox = QCheckBox(_("Comment"))

        self.search_results = []
        self.current_result_index = -1
        self.last_search_options = {}

        self.setup_ui()

        self.load_last_search_settings()
        self.paste_from_clipboard_if_needed()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # Find what
        find_layout = QHBoxLayout()
        find_layout.addWidget(QLabel(_("Find what:")))
        find_layout.addWidget(self.search_term_entry)
        main_layout.addLayout(find_layout)
        self.search_term_entry.textChanged.connect(self._on_search_term_changed)
        self.search_term_entry.returnPressed.connect(self._find_next)

        # Replace with
        replace_layout = QHBoxLayout()
        replace_layout.addWidget(QLabel(_("Replace with:")))
        replace_layout.addWidget(self.replace_term_entry)
        main_layout.addLayout(replace_layout)

        # Options
        options_group = QGroupBox(_("Options"))
        options_layout = QHBoxLayout(options_group)
        options_layout.addWidget(self.case_sensitive_checkbox)

        search_in_group = QWidget()
        search_in_layout = QHBoxLayout(search_in_group)
        search_in_layout.setContentsMargins(0,0,0,0)
        search_in_layout.addWidget(QLabel(_("Search in:")))
        search_in_layout.addWidget(self.search_in_original_checkbox)
        search_in_layout.addWidget(self.search_in_translation_checkbox)
        search_in_layout.addWidget(self.search_in_comment_checkbox)
        search_in_layout.addStretch(1)
        options_layout.addWidget(search_in_group)
        options_layout.addStretch(1)
        main_layout.addWidget(options_group)

        self.results_label = QLabel("")
        main_layout.addWidget(self.results_label)

        # Buttons
        button_box = QHBoxLayout()
        find_next_btn = QPushButton(_("Find Next"))
        find_next_btn.clicked.connect(self._find_next)
        button_box.addWidget(find_next_btn)

        find_prev_btn = QPushButton(_("Find Previous"))
        find_prev_btn.clicked.connect(self._find_prev)
        button_box.addWidget(find_prev_btn)

        replace_btn = QPushButton(_("Replace"))
        replace_btn.clicked.connect(self._replace_current)
        button_box.addWidget(replace_btn)

        replace_all_btn = QPushButton(_("Replace All"))
        replace_all_btn.clicked.connect(self._replace_all)
        button_box.addWidget(replace_all_btn)

        button_box.addStretch(1)

        close_btn = QPushButton(_("Close"))
        close_btn.clicked.connect(self.close)
        button_box.addWidget(close_btn)
        main_layout.addLayout(button_box)

        # Set initial checkbox states
        self.search_in_original_checkbox.setChecked(True)
        self.search_in_translation_checkbox.setChecked(True)
        self.search_in_comment_checkbox.setChecked(True)

    def closeEvent(self, event):
        self.app.proxy_model.set_search_term("")
        self.save_current_search_settings()
        super().closeEvent(event)

    def load_last_search_settings(self):
        self.search_term_entry.setText(self.app.last_search_term)
        self.replace_term_entry.setText(self.app.last_replace_term)

        options = self.app.last_search_options
        self.case_sensitive_checkbox.setChecked(options.get("case_sensitive", False))
        self.search_in_original_checkbox.setChecked(options.get("in_original", True))
        self.search_in_translation_checkbox.setChecked(options.get("in_translation", True))
        self.search_in_comment_checkbox.setChecked(options.get("in_comment", True))

    def save_current_search_settings(self):
        self.app.last_search_term = self.search_term_entry.text()
        self.app.last_replace_term = self.replace_term_entry.text()

        self.app.last_search_options = {
            "case_sensitive": self.case_sensitive_checkbox.isChecked(),
            "in_original": self.search_in_original_checkbox.isChecked(),
            "in_translation": self.search_in_translation_checkbox.isChecked(),
            "in_comment": self.search_in_comment_checkbox.isChecked()
        }

    def paste_from_clipboard_if_needed(self):
        if not self.search_term_entry.text():
            clipboard = QApplication.clipboard()
            clipboard_text = clipboard.text()
            if clipboard_text and '\n' not in clipboard_text and 0 < len(clipboard_text) < 40:
                self.search_term_entry.setText(clipboard_text)
                self.search_term_entry.selectAll()

    def _on_search_term_changed(self, text):
        self.last_search_options = {}
        self.results_label.setText("")
        self._clear_all_highlights()

    def _get_current_search_options(self):
        return {
            "term": self.search_term_entry.text(),
            "case": self.case_sensitive_checkbox.isChecked(),
            "in_orig": self.search_in_original_checkbox.isChecked(),
            "in_trans": self.search_in_translation_checkbox.isChecked(),
            "in_comment": self.search_in_comment_checkbox.isChecked()
        }

    def _perform_search(self):
        term = self.search_term_entry.text()
        if not term:
            self.app.proxy_model.set_search_term("")
            self.results_label.setText(_("Please enter a search term."))
            return False

        self.app.proxy_model.set_search_term(
            term=term,
            case_sensitive=self.case_sensitive_checkbox.isChecked(),
            search_in_original=self.search_in_original_checkbox.isChecked(),
            search_in_translation=self.search_in_translation_checkbox.isChecked(),
            search_in_comment=self.search_in_comment_checkbox.isChecked()
        )

        count = len(self.app.proxy_model.search_results_indices)
        if count > 0:
            self.results_label.setText(_("Found {count} matches.").format(count=count))
        else:
            self.results_label.setText(_("No matches found."))

        return count > 0

    def _clear_all_highlights(self):
        self.app.table_view.clearSelection()
        self.app.sheet_model.dataChanged.emit(self.app.sheet_model.index(0,0), self.app.sheet_model.index(self.app.sheet_model.rowCount()-1, self.app.sheet_model.columnCount()-1), [Qt.BackgroundRole, Qt.ForegroundRole])
        self.app.table_view.viewport().update()

    def _highlight_all_matches(self):
        pass

    def _update_current_selection_highlight(self):
        if self.current_result_index != -1 and self.search_results:
            res = self.search_results[self.current_result_index]
            proxy_index = self.app.proxy_model.index(res["row"], res["col"])
            if proxy_index.isValid():
                self.app.table_view.selectionModel().clearSelection()
                self.app.table_view.selectionModel().setCurrentIndex(proxy_index, QItemSelectionModel.ClearAndSelect)
                self.app.table_view.scrollTo(proxy_index, QAbstractItemView.ScrollHint.PositionAtCenter)
                self.app.on_sheet_select(proxy_index, QModelIndex())

    def _get_sorted_search_results(self):
        if not self.app.proxy_model.search_results_indices:
            return []
        return sorted(list(self.app.proxy_model.search_results_indices), key=lambda item: (item[0], item[1]))

    def _navigate_to_result(self):
        sorted_results = self._get_sorted_search_results()
        if not sorted_results or self.current_result_index < 0 or self.current_result_index >= len(sorted_results):
            return
        source_row, source_col = sorted_results[self.current_result_index]
        source_index = self.app.sheet_model.index(source_row, source_col)
        proxy_index = self.app.proxy_model.mapFromSource(source_index)

        if proxy_index.isValid():
            self.app.table_view.selectionModel().clearSelection()
            self.app.table_view.selectionModel().setCurrentIndex(proxy_index, QItemSelectionModel.ClearAndSelect)
            self.app.table_view.scrollTo(proxy_index, QAbstractItemView.ScrollHint.PositionAtCenter)

        self.results_label.setText(
            _("Match {current}/{total}").format(current=self.current_result_index + 1,
                                                total=len(sorted_results))
        )

    def _find_next(self):
        if self.search_term_entry.text().lower() != self.app.proxy_model.search_term:
            self.current_result_index = -1
            if not self._perform_search():
                return

        sorted_results = self._get_sorted_search_results()
        if not sorted_results:
            return
        self.current_result_index = (self.current_result_index + 1) % len(sorted_results)
        self._navigate_to_result()

    def _find_prev(self):
        if self.search_term_entry.text().lower() != self.app.proxy_model.search_term:
            self.current_result_index = -1
            if not self._perform_search():
                return

        sorted_results = self._get_sorted_search_results()
        if not sorted_results:
            return
        self.current_result_index = (self.current_result_index - 1 + len(sorted_results)) % len(sorted_results)
        self._navigate_to_result()

    def _replace_current(self):
        if self.search_term_entry.text().lower() != self.app.proxy_model.search_term:
            self.current_result_index = -1
            if not self._perform_search(): return

        sorted_results = self._get_sorted_search_results()

        if not sorted_results:
            self._find_next()
            sorted_results = self._get_sorted_search_results()
            if not sorted_results: return
        if self.current_result_index < 0 or self.current_result_index >= len(sorted_results):
            self.current_result_index = 0
        source_row, source_col = sorted_results[self.current_result_index]
        ts_obj = self.app.sheet_model.data(self.app.sheet_model.index(source_row, 0), Qt.UserRole)
        if not ts_obj: return

        term = self.search_term_entry.text()
        replace_with = self.replace_term_entry.text()
        if not term: return

        flags = 0 if self.case_sensitive_checkbox.isChecked() else re.IGNORECASE
        pattern = re.compile(re.escape(term), flags)
        if source_col == 3:  # Translation column
            current_text = ts_obj.get_translation_for_ui()
            new_text, num_replacements = pattern.subn(replace_with, current_text, count=1)
            if num_replacements > 0:
                self.app._apply_translation_to_model(ts_obj, new_text, source="replace_current")

        elif source_col == 4:  # Comment column
            old_po_comment = ts_obj.po_comment
            old_user_comment = ts_obj.comment
            full_comment_text = "\n".join(old_po_comment.splitlines() + old_user_comment.splitlines())

            new_full_comment, num_replacements = pattern.subn(replace_with, full_comment_text, count=1)

            if num_replacements > 0:
                lines = new_full_comment.splitlines()
                new_po_lines = []
                new_user_lines = []
                for line in lines:
                    if line.strip().startswith('#'):
                        new_po_lines.append(line)
                    else:
                        new_user_lines.append(line)

                new_po_comment = "\n".join(new_po_lines)
                new_user_comment = "\n".join(new_user_lines)
                self.app.add_to_undo_history('bulk_change', {
                    'changes': [
                        {'string_id': ts_obj.id, 'field': 'po_comment', 'old_value': old_po_comment,
                         'new_value': new_po_comment},
                        {'string_id': ts_obj.id, 'field': 'comment', 'old_value': old_user_comment,
                         'new_value': new_user_comment}
                    ]
                })
                ts_obj.po_comment = new_po_comment
                ts_obj.comment = new_user_comment
                self.app.mark_project_modified()
                self.app.force_full_refresh(id_to_reselect=ts_obj.id)
        else:
            QMessageBox.information(self, _("Info"),
                                    _("Match is not in a replaceable column (Translation or Comment)."))
            self._find_next()
            return
        QTimer.singleShot(100, self._find_next)

    def _replace_all(self):
        if not self._perform_search():
            QMessageBox.information(self, _("Replace All"), _("No matches found to replace."))
            return

        term = self.search_term_entry.text()
        replace_with = self.replace_term_entry.text()

        sorted_results = self._get_sorted_search_results()
        trans_results = [res for res in sorted_results if res[1] == 3]  # Translation column
        comment_results = [res for res in sorted_results if res[1] == 4]  # Comment column

        if not trans_results and not comment_results:
            QMessageBox.information(self, _("Replace All"), _("No matches found in Translation or Comment columns."))
            return

        msg_parts = []
        if trans_results:
            msg_parts.append(_("{count} in Translation").format(count=len(trans_results)))
        if comment_results:
            msg_parts.append(_("{count} in Comment").format(count=len(comment_results)))
        confirm_msg = _("Are you sure you want to replace all occurrences?\nFound: {details}.").format(
            details=", ".join(msg_parts))
        reply = QMessageBox.question(self, _("Confirm Replace All"), confirm_msg, QMessageBox.Yes | QMessageBox.No,
                                     QMessageBox.No)
        if reply == QMessageBox.No:
            return
        flags = 0 if self.case_sensitive_checkbox.isChecked() else re.IGNORECASE
        pattern = re.compile(re.escape(term), flags)
        bulk_changes = []
        modified_ts_ids = set()
        trans_changes = {}
        for row, col in trans_results:
            ts_obj = self.app.sheet_model.data(self.app.sheet_model.index(row, 0), Qt.UserRole)
            if not ts_obj or ts_obj.is_ignored: continue
            current_text = trans_changes.get(ts_obj.id, ts_obj.get_translation_for_ui())
            trans_changes[ts_obj.id] = pattern.sub(replace_with, current_text)

        for ts_id, new_text in trans_changes.items():
            ts_obj = self.app._find_ts_obj_by_id(ts_id)
            if ts_obj and new_text != ts_obj.get_translation_for_ui():
                old_val = ts_obj.get_translation_for_storage_and_tm()
                ts_obj.set_translation_internal(new_text)
                bulk_changes.append({'string_id': ts_id, 'field': 'translation', 'old_value': old_val,
                                     'new_value': ts_obj.get_translation_for_storage_and_tm()})
                modified_ts_ids.add(ts_id)
        comment_changes = {}
        for row, col in comment_results:
            ts_obj = self.app.sheet_model.data(self.app.sheet_model.index(row, 0), Qt.UserRole)
            if not ts_obj: continue

            current_text = comment_changes.get(ts_obj.id, ts_obj.comment)
            comment_changes[ts_obj.id] = pattern.sub(replace_with, current_text)

        for ts_id, new_text in comment_changes.items():
            ts_obj = self.app._find_ts_obj_by_id(ts_id)
            if ts_obj and new_text != ts_obj.comment:
                old_val = ts_obj.comment
                ts_obj.comment = new_text
                bulk_changes.append(
                    {'string_id': ts_id, 'field': 'comment', 'old_value': old_val, 'new_value': new_text})
                modified_ts_ids.add(ts_id)
        if bulk_changes:
            for ts_id in modified_ts_ids:
                ts_obj = self.app._find_ts_obj_by_id(ts_id)
                if ts_obj:
                    ts_obj.update_style_cache()

            self.app.add_to_undo_history('bulk_replace_all', {'changes': bulk_changes})
            self.app.mark_project_modified()
            self.app.force_full_refresh(id_to_reselect=self.app.current_selected_ts_id)

            QMessageBox.information(self, _("Replace All Complete"),
                                    _("Replaced occurrences in {count} item(s).").format(count=len(modified_ts_ids)))
        else:
            QMessageBox.information(self, _("Replace All"), _("No occurrences were replaced."))
        self.app.proxy_model.set_search_term("")
        self.results_label.setText(_("Replacement complete."))
        self.close()