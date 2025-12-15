# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QCheckBox, QWidget, QMessageBox, QGroupBox, QAbstractItemView, QApplication
)
from PySide6.QtCore import Qt, QItemSelectionModel, QEvent
import re
from utils.localization import _


class AdvancedSearchDialog(QDialog):
    def __init__(self, parent, title, app_instance):
        super().__init__(parent)
        self.app = app_instance
        self.service = app_instance.search_service

        self.setWindowTitle(title)
        self.setModal(False)

        self.setup_ui()

        self.search_term_entry.setText(self.service.last_term)
        self.replace_term_entry.setText(self.service.last_replace_term)

        opts = self.service.last_options
        self.case_sensitive_checkbox.setChecked(opts.get("case", False))
        self.search_in_original_checkbox.setChecked(opts.get("in_orig", True))
        self.search_in_translation_checkbox.setChecked(opts.get("in_trans", True))
        self.search_in_comment_checkbox.setChecked(opts.get("in_comment", True))

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

    def showEvent(self, event):
        super().showEvent(event)
        self.search_term_entry.setFocus()
        self.search_term_entry.selectAll()

    def reject(self):
        self.close()
        super().reject()

    def closeEvent(self, event):
        self.service.set_replace_term(self.replace_term_entry.text())

        self.service.clear()
        self.app.clear_search_markers()
        super().closeEvent(event)

    def paste_from_clipboard_if_needed(self):
        if not self.search_term_entry.text():
            clipboard = QApplication.clipboard()
            clipboard_text = clipboard.text()
            if clipboard_text and '\n' not in clipboard_text and 0 < len(clipboard_text) < 40:
                self.search_term_entry.setText(clipboard_text)
                self.search_term_entry.selectAll()

    def _on_search_term_changed(self, text):
        self.results_label.setText("")
        self.service.clear()
        self.app.clear_search_markers()

    def _get_current_search_options(self):
        return {
            "case": self.case_sensitive_checkbox.isChecked(),
            "in_orig": self.search_in_original_checkbox.isChecked(),
            "in_trans": self.search_in_translation_checkbox.isChecked(),
            "in_comment": self.search_in_comment_checkbox.isChecked()
        }


    def eventFilter(self, obj, event):
        if obj is self.search_term_entry and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
                self._find_next()
                return True
        return super().eventFilter(obj, event)

    def _find_next(self):
        term = self.search_term_entry.text()
        if not term: return

        opts = self._get_current_search_options()
        count = self.service.perform_search(term, opts)

        if count == 0:
            self.results_label.setText(_("No matches found."))
            return

        current, total = self.service.find_next()
        self.results_label.setText(_("Match {current}/{total}").format(current=current, total=total))

    def _find_prev(self):
        term = self.search_term_entry.text()
        if not term: return

        opts = self._get_current_search_options()
        count = self.service.perform_search(term, opts)

        if count == 0:
            self.results_label.setText(_("No matches found."))
            return

        current, total = self.service.find_prev()
        self.results_label.setText(_("Match {current}/{total}").format(current=current, total=total))

    def _replace_current(self):
        term = self.search_term_entry.text()
        replace_with = self.replace_term_entry.text()
        if not term: return

        opts = self._get_current_search_options()
        self.service.perform_search(term, opts)

        if self.service.current_result_index == -1:
            self._find_next()  # Highlight first match
            if self.service.current_result_index == -1: return

        success = self.service.replace_current(replace_with)

        if success:
            self._find_next()
        else:
            QMessageBox.information(self, _("Info"), _("Match is not in a replaceable column."))

    def _replace_all(self):
        term = self.search_term_entry.text()
        replace_with = self.replace_term_entry.text()
        if not term: return

        opts = self._get_current_search_options()
        self.service.perform_search(term, opts)

        count = self.service.replace_all(replace_with)

        if count > 0:
            QMessageBox.information(self, _("Replace All Complete"),
                                    _("Replaced occurrences in {count} item(s).").format(count=count))
        else:
            QMessageBox.information(self, _("Info"), _("No matches found to replace."))

        self.close()