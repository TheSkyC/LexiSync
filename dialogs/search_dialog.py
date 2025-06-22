# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QCheckBox, QWidget, QMessageBox, QGroupBox
)
from PySide6.QtCore import Qt, QItemSelectionModel
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
        self._clear_all_highlights()
        super().closeEvent(event)

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
        current_options = self._get_current_search_options()
        if self.last_search_options == current_options and self.search_results:
            return True

        self._clear_all_highlights()
        self.search_results = []
        self.current_result_index = -1

        term = current_options["term"]
        if not term:
            self.results_label.setText(_("Please enter a search term."))
            return False

        flags = 0 if current_options["case"] else re.IGNORECASE
        try:
            pattern = re.compile(re.escape(term), flags)
        except re.error:
            self.results_label.setText(_("Invalid search term."))
            return False

        for row_idx in range(self.app.proxy_model.rowCount()):
            proxy_index = self.app.proxy_model.index(row_idx, 0)
            ts_obj = self.app.proxy_model.data(proxy_index, Qt.UserRole)
            if not ts_obj: continue

            if current_options["in_orig"] and pattern.search(ts_obj.original_semantic):
                self.search_results.append({"row": row_idx, "col": 2, "id": ts_obj.id})
            if current_options["in_trans"] and pattern.search(ts_obj.get_translation_for_ui()):
                self.search_results.append({"row": row_idx, "col": 3, "id": ts_obj.id})
            if current_options["in_comment"] and pattern.search(ts_obj.comment):
                self.search_results.append({"row": row_idx, "col": 4, "id": ts_obj.id})

        self.search_results.sort(key=lambda r: (r["row"], r["col"]))
        self.last_search_options = current_options
        self._highlight_all_matches()

        if self.search_results:
            self.results_label.setText(_("Found {count} matches.").format(count=len(self.search_results)))
        else:
            self.results_label.setText(_("No matches found."))

        return bool(self.search_results)

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
                self.app.table_view.scrollTo(proxy_index, self.app.table_view.PositionAtCenter)
                self.app.on_sheet_select(proxy_index, proxy_index)

    def _navigate_to_result(self):
        if not self.search_results:
            return

        self._update_current_selection_highlight()

        self.results_label.setText(
            _("Match {current}/{total}").format(current=self.current_result_index + 1,
                                                     total=len(self.search_results))
        )

    def _find_next(self):
        if not self._perform_search() or not self.search_results:
            return

        self.current_result_index = (self.current_result_index + 1) % len(self.search_results)
        self._navigate_to_result()

    def _find_prev(self):
        if not self._perform_search() or not self.search_results:
            return

        self.current_result_index = (self.current_result_index - 1 + len(self.search_results)) % len(
            self.search_results)
        self._navigate_to_result()

    def _replace_current(self):
        if self.current_result_index < 0 or self.current_result_index >= len(self.search_results):
            self._find_next()
            if self.current_result_index < 0:
                return

        res = self.search_results[self.current_result_index]
        ts_obj = self.app._find_ts_obj_by_id(res["id"])
        if not ts_obj: return

        term = self.search_term_entry.text()
        replace_with = self.replace_term_entry.text()
        if not term: return

        flags = 0 if self.case_sensitive_checkbox.isChecked() else re.IGNORECASE
        pattern = re.compile(re.escape(term), flags)

        target_column_index = res["col"]

        if target_column_index == 3:
            current_text = ts_obj.get_translation_for_ui()
            new_text, num_replacements = pattern.subn(replace_with, current_text, count=1)
            if num_replacements > 0:
                self.app._apply_translation_to_model(ts_obj, new_text, source="replace_current")

        elif target_column_index == 4:
            current_text = ts_obj.comment
            new_text, num_replacements = pattern.subn(replace_with, current_text, count=1)
            if num_replacements > 0:
                self.app._apply_comment_to_model(ts_obj, new_text)

        else:
            QMessageBox.information(self, _("Info"), _("Match is not in a replaceable column (Translation or Comment)."))
            self._find_next()
            return
        self.last_search_options = {}
        self._perform_search()
        self._find_next()

    def _replace_all(self):
        if not self._perform_search() or not self.search_results:
            QMessageBox.information(self, _("Replace All"), _("No matches found to replace."))
            return

        term = self.search_term_entry.text()
        replace_with = self.replace_term_entry.text()
        trans_results = [res for res in self.search_results if res["col"] == 3]
        comment_results = [res for res in self.search_results if res["col"] == 4]

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
        reply = QMessageBox.question(self, _("Confirm Replace All"), confirm_msg, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.No:
            return

        flags = 0 if self.case_sensitive_checkbox.isChecked() else re.IGNORECASE
        pattern = re.compile(re.escape(term), flags)

        bulk_changes = []
        processed_ids_trans = set()
        for res in trans_results:
            if res["id"] in processed_ids_trans: continue
            ts_obj = self.app._find_ts_obj_by_id(res["id"])
            if not ts_obj or ts_obj.is_ignored: continue

            old_text = ts_obj.get_translation_for_storage_and_tm()
            new_text = pattern.sub(replace_with, ts_obj.get_translation_for_ui())
            if new_text != ts_obj.get_translation_for_ui():
                ts_obj.set_translation_internal(new_text)
                bulk_changes.append({'string_id': ts_obj.id, 'field': 'translation', 'old_value': old_text,
                                     'new_value': ts_obj.get_translation_for_storage_and_tm()})
            processed_ids_trans.add(res["id"])

        processed_ids_comment = set()
        for res in comment_results:
            if res["id"] in processed_ids_comment: continue
            ts_obj = self.app._find_ts_obj_by_id(res["id"])
            if not ts_obj: continue

            old_text = ts_obj.comment
            new_text = pattern.sub(replace_with, old_text)
            if new_text != old_text:
                ts_obj.comment = new_text
                bulk_changes.append(
                    {'string_id': ts_obj.id, 'field': 'comment', 'old_value': old_text, 'new_value': new_text})
            processed_ids_comment.add(res["id"])

        if bulk_changes:
            self.app.add_to_undo_history('bulk_replace_all', {'changes': bulk_changes})
            self.app.mark_project_modified()
            self.app._run_and_refresh_with_validation()
            QMessageBox.information(self, _("Replace All Complete"),
                                _("Changes made to {count} field(s).").format(count=len(bulk_changes)))
        else:
            QMessageBox.information(self, _("Replace All"), _("No occurrences were replaced."))

        self.last_search_options = {}
        self.results_label.setText(_("Replacement complete."))
        self._clear_all_highlights()