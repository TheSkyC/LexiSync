# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QCheckBox, QWidget, QMessageBox, QGroupBox, QAbstractItemView, QApplication
)
from PySide6.QtCore import Qt, QItemSelectionModel, QModelIndex, QTimer, QEvent
import re
from utils.localization import _


class AdvancedSearchDialog(QDialog):
    def __init__(self, parent, title, app_instance):
        super().__init__(parent)
        self.app = app_instance
        self.setWindowTitle(title)
        self.setModal(False)

        self.search_results = []
        self.current_result_index = -1
        self.last_search_options = {}

        self.setup_ui()
        self.load_last_search_settings()
        self.paste_from_clipboard_if_needed()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # 查找内容
        find_layout = QHBoxLayout()
        find_layout.addWidget(QLabel(_("Find what:")))
        self.search_term_entry = QLineEdit()
        self.search_term_entry.textChanged.connect(self._on_search_term_changed)
        self.search_term_entry.returnPressed.connect(self._find_next)
        find_layout.addWidget(self.search_term_entry)
        main_layout.addLayout(find_layout)
        # 替换为
        replace_layout = QHBoxLayout()
        replace_layout.addWidget(QLabel(_("Replace with:")))
        self.replace_term_entry = QLineEdit()
        replace_layout.addWidget(self.replace_term_entry)
        main_layout.addLayout(replace_layout)

        # 选项
        options_group = QGroupBox(_("Options"))
        options_layout = QHBoxLayout(options_group)
        self.case_sensitive_checkbox = QCheckBox(_("Case sensitive"))
        options_layout.addWidget(self.case_sensitive_checkbox)

        search_in_group = QWidget()
        search_in_layout = QHBoxLayout(search_in_group)
        search_in_layout.setContentsMargins(0, 0, 0, 0)
        search_in_layout.addWidget(QLabel(_("Search in:")))
        self.search_in_original_checkbox = QCheckBox(_("Original"))
        self.search_in_translation_checkbox = QCheckBox(_("Translation"))
        self.search_in_comment_checkbox = QCheckBox(_("Comment"))
        search_in_layout.addWidget(self.search_in_original_checkbox)
        search_in_layout.addWidget(self.search_in_translation_checkbox)
        search_in_layout.addWidget(self.search_in_comment_checkbox)
        search_in_layout.addStretch(1)
        options_layout.addWidget(search_in_group)

        main_layout.addWidget(options_group)

        # 结果标签
        self.results_label = QLabel("")
        main_layout.addWidget(self.results_label)

        # 按钮
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
        self.search_term_entry.installEventFilter(self)

        # 初始化复选框状态
        self.search_in_original_checkbox.setChecked(True)
        self.search_in_translation_checkbox.setChecked(True)
        self.search_in_comment_checkbox.setChecked(True)

    def closeEvent(self, event):
        self.app.clear_search_markers()
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
        self.search_results.clear()
        self.current_result_index = -1
        self.app.find_highlight_indices.clear()
        self.app.current_find_highlight_index = None
        self.app.table_view.viewport().update()

    def _get_current_search_options(self):
        return {
            "term": self.search_term_entry.text(),
            "case": self.case_sensitive_checkbox.isChecked(),
            "in_orig": self.search_in_original_checkbox.isChecked(),
            "in_trans": self.search_in_translation_checkbox.isChecked(),
            "in_comment": self.search_in_comment_checkbox.isChecked()
        }

    def _perform_search(self):
        options = self._get_current_search_options()
        term = options["term"]
        if not term:
            self.results_label.setText(_("Please enter a search term."))
            return False

        if self.last_search_options == options:
            return bool(self.search_results)

        self.search_results.clear()
        self.search_results_source_rows.clear()
        self.current_result_index = -1
        self.app.find_highlight_indices.clear()
        self.app.current_find_highlight_index = None

        flags = 0 if options["case"] else re.IGNORECASE
        pattern = re.compile(re.escape(term), flags)

        proxy = self.app.proxy_model
        source_model = proxy.sourceModel()
        for row in range(proxy.rowCount()):
            proxy_index = proxy.index(row, 0)
            source_index = proxy.mapToSource(proxy_index)
            ts_obj = source_model.data(source_index, Qt.ItemDataRole.UserRole)
            found = False
            if options["in_orig"] and pattern.search(ts_obj.original_semantic):
                found = True
            if options["in_trans"] and pattern.search(ts_obj.get_translation_for_ui()):
                found = True
            if options["in_comment"] and pattern.search(ts_obj.comment):
                found = True

            if found:
                self.search_results.append({"proxy_row": row, "obj": ts_obj})
                self.search_results_source_rows.append(source_index.row())

        self.search_results_source_rows = sorted(list(set(self.search_results_source_rows)))

        self.last_search_options = options

        if self.search_results:
            self.results_label.setText(_("Found {count} matches.").format(count=len(self.search_results)))
            for res in self.search_results:
                self.app.find_highlight_indices.add((res["proxy_row"], res["col"]))
            self.app.table_view.viewport().update()
            self.app.update_search_markers(self.search_results_source_rows)
        else:
            self.results_label.setText(_("No matches found."))
            self.app.table_view.viewport().update()
            self.app.clear_search_markers()

        return bool(self.search_results)

    def _navigate_to_result(self):
        if not self.search_results:
            self.app.current_find_highlight_index = None
            self.app.table_view.viewport().update()
            return

        res = self.search_results[self.current_result_index]
        proxy_index = self.app.proxy_model.index(res["proxy_row"], res["col"])

        self.app.current_find_highlight_index = (res["proxy_row"], res["col"])

        if proxy_index.isValid():
            self.app.table_view.selectionModel().clearSelection()
            self.app.table_view.selectionModel().setCurrentIndex(proxy_index,
                                                                 QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
            self.app.table_view.scrollTo(proxy_index, QAbstractItemView.ScrollHint.PositionAtCenter)

        self.app.table_view.viewport().update()

        self.results_label.setText(
            _("Match {current}/{total}").format(current=self.current_result_index + 1, total=len(self.search_results))
        )

    def eventFilter(self, obj, event):
        if obj is self.search_term_entry and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
                self._find_next()
                return True
        return super().eventFilter(obj, event)

    def _find_next(self):
        is_new_search = self.last_search_options != self._get_current_search_options()
        if is_new_search:
            if not self._perform_search(): return
            self.current_result_index = -1

        if not self.search_results: return
        if self.current_result_index == -1:
            current_selection = self.app.table_view.selectionModel().currentIndex()
            start_row = current_selection.row() if current_selection.isValid() else -1
            for i, res in enumerate(self.search_results):
                if res["proxy_row"] >= start_row:
                    self.current_result_index = i - 1
                    break
            else:
                self.current_result_index = len(self.search_results) - 1
        self.current_result_index = (self.current_result_index + 1) % len(self.search_results)
        self._navigate_to_result()

    def _find_prev(self):
        is_new_search = self.last_search_options != self._get_current_search_options()
        if is_new_search:
            if not self._perform_search(): return
            self.current_result_index = -1

        if not self.search_results: return
        if self.current_result_index == -1:
            current_selection = self.app.table_view.selectionModel().currentIndex()
            start_row = current_selection.row() if current_selection.isValid() else -1
            for i in range(len(self.search_results) - 1, -1, -1):
                res = self.search_results[i]
                if res["proxy_row"] <= start_row:
                    self.current_result_index = i + 1
                    break
            else:
                self.current_result_index = 0
        self.current_result_index = (self.current_result_index - 1 + len(self.search_results)) % len(
            self.search_results)
        self._navigate_to_result()

    def _replace_current(self):
        if not self._perform_search() or not self.search_results:
            QMessageBox.information(self, _("Info"), _("No matches found to replace."))
            return

        if self.current_result_index == -1:
            self._find_next()
            if self.current_result_index == -1: return

        res = self.search_results[self.current_result_index]
        ts_obj = res["obj"]
        col = res["col"]

        term = self.search_term_entry.text()
        replace_with = self.replace_term_entry.text()
        flags = 0 if self.case_sensitive_checkbox.isChecked() else re.IGNORECASE
        pattern = re.compile(re.escape(term), flags)

        if col == 3:  # Translation
            current_text = ts_obj.get_translation_for_ui()
            new_text, num_replacements = pattern.subn(replace_with, current_text, count=1)
            if num_replacements > 0:
                self.app._apply_translation_to_model(ts_obj, new_text, source="replace_current")
        elif col == 4:  # Comment
            old_comment = ts_obj.comment
            new_comment, num_replacements = pattern.subn(replace_with, old_comment, count=1)
            if num_replacements > 0:
                self.app._apply_comment_to_model(ts_obj, new_comment)
        else:
            QMessageBox.information(self, _("Info"),
                                    _("Match is not in a replaceable column (Translation or Comment)."))
            self._find_next()
            return

        QTimer.singleShot(50, self._find_next)

    def _replace_all(self):
        if not self._perform_search() or not self.search_results:
            QMessageBox.information(self, _("Info"), _("No matches found to replace."))
            return

        term = self.search_term_entry.text()
        replace_with = self.replace_term_entry.text()
        flags = 0 if self.case_sensitive_checkbox.isChecked() else re.IGNORECASE
        pattern = re.compile(re.escape(term), flags)

        trans_results = [res for res in self.search_results if res["col"] == 3]
        comment_results = [res for res in self.search_results if res["col"] == 4]

        if not trans_results and not comment_results:
            QMessageBox.information(self, _("Info"), _("No matches found in Translation or Comment columns."))
            return

        bulk_changes = []
        modified_ts_ids = set()

        for res in trans_results:
            ts_obj = res["obj"]
            if ts_obj.id in modified_ts_ids: continue
            current_text = ts_obj.get_translation_for_ui()
            new_text = pattern.sub(replace_with, current_text)
            if new_text != current_text:
                old_val = ts_obj.get_translation_for_storage_and_tm()
                ts_obj.set_translation_internal(new_text)
                bulk_changes.append({'string_id': ts_obj.id, 'field': 'translation', 'old_value': old_val,
                                     'new_value': ts_obj.get_translation_for_storage_and_tm()})
                modified_ts_ids.add(ts_obj.id)

        for res in comment_results:
            ts_obj = res["obj"]
            if ts_obj.id in modified_ts_ids: continue
            current_text = ts_obj.comment
            new_text = pattern.sub(replace_with, current_text)
            if new_text != current_text:
                old_val = ts_obj.comment
                ts_obj.comment = new_text
                bulk_changes.append(
                    {'string_id': ts_obj.id, 'field': 'comment', 'old_value': old_val, 'new_value': new_text})
                modified_ts_ids.add(ts_obj.id)

        if bulk_changes:
            self.app.add_to_undo_history('bulk_replace_all', {'changes': bulk_changes})
            self.app.mark_project_modified()
            self.app.force_full_refresh(id_to_reselect=self.app.current_selected_ts_id)
            QMessageBox.information(self, _("Replace All Complete"),
                                    _("Replaced occurrences in {count} item(s).").format(count=len(modified_ts_ids)))

        self.close()