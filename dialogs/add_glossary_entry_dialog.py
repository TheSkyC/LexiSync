# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit,
                               QPushButton, QDialogButtonBox, QComboBox, QTextEdit,
                               QMessageBox)
from PySide6.QtCore import Qt
from utils.localization import _
from utils.constants import SUPPORTED_LANGUAGES


class AddGlossaryEntryDialog(QDialog):
    def __init__(self, parent=None, default_source_lang=None, default_target_lang=None):
        super().__init__(parent)
        self.setWindowTitle(_("Add Glossary Entry"))
        self.setModal(False)

        self.setAttribute(Qt.WA_DeleteOnClose)

        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.source_term_edit = QLineEdit()
        self.target_term_edit = QLineEdit()
        self.source_lang_combo = QComboBox()
        self.target_lang_combo = QComboBox()
        self.comment_edit = QTextEdit()
        self.comment_edit.setFixedHeight(80)

        self._populate_lang_combos()

        if default_source_lang:
            index = self.source_lang_combo.findData(default_source_lang)
            if index != -1: self.source_lang_combo.setCurrentIndex(index)

        if default_target_lang:
            index = self.target_lang_combo.findData(default_target_lang)
            if index != -1: self.target_lang_combo.setCurrentIndex(index)

        form_layout.addRow(_("Source Term:"), self.source_term_edit)
        form_layout.addRow(_("Source Language:"), self.source_lang_combo)
        form_layout.addRow(_("Target Term:"), self.target_term_edit)
        form_layout.addRow(_("Target Language:"), self.target_lang_combo)
        form_layout.addRow(_("Comment:"), self.comment_edit)

        layout.addLayout(form_layout)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _populate_lang_combos(self):
        for name, code in sorted(SUPPORTED_LANGUAGES.items()):
            self.source_lang_combo.addItem(name, code)
            self.target_lang_combo.addItem(name, code)

    def get_data(self):
        return {
            "source_term": self.source_term_edit.text().strip(),
            "target_term": self.target_term_edit.text().strip(),
            "source_lang": self.source_lang_combo.currentData(),
            "target_lang": self.target_lang_combo.currentData(),
            "comment": self.comment_edit.toPlainText().strip()
        }

    def accept(self):
        data = self.get_data()
        if not data['source_term'] or not data['target_term']:
            QMessageBox.warning(self, _("Missing Information"), _("Source term and target term cannot be empty."))
            return
        if data['source_lang'] == data['target_lang']:
            QMessageBox.warning(self, _("Invalid Languages"), _("Source and target languages cannot be the same."))
            return
        super().accept()