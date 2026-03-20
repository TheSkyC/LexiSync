# Copyright (c) 2025-2026, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QFormLayout, QMessageBox, QVBoxLayout

from lexisync.utils.constants import SUPPORTED_LANGUAGES
from lexisync.utils.localization import _


class TMImportDialog(QDialog):
    def __init__(self, parent, filename):
        super().__init__(parent)
        self.setWindowTitle(_("Configure TM Import"))
        self.setModal(True)

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.source_lang_combo = QComboBox()
        self.target_lang_combo = QComboBox()
        self._populate_lang_combos()

        form_layout.addRow(_("Source Language:"), self.source_lang_combo)
        form_layout.addRow(_("Target Language:"), self.target_lang_combo)

        layout.addLayout(form_layout)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(button_box)

        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

    def _populate_lang_combos(self):
        for name, code in sorted(SUPPORTED_LANGUAGES.items()):
            self.source_lang_combo.addItem(name, code)
            self.target_lang_combo.addItem(name, code)
        self.source_lang_combo.setCurrentText("English")
        self.target_lang_combo.setCurrentText("简体中文")

    def get_data(self):
        return {
            "source_lang": self.source_lang_combo.currentData(),
            "target_lang": self.target_lang_combo.currentData(),
        }

    def accept(self):
        data = self.get_data()
        if data["source_lang"] == data["target_lang"]:
            QMessageBox.warning(self, _("Invalid Languages"), _("Source and target languages cannot be the same."))
            return
        super().accept()
