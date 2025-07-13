# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt
from utils.localization import _

class POTDropDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.result = None

        self.setWindowTitle(_("POT File Detected"))
        self.setModal(True)

        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(QLabel(_("A POT file was dropped. What would you like to do?")))

        button_box = QHBoxLayout()

        update_btn = QPushButton(_("Update from POT"))
        update_btn.clicked.connect(lambda: self._set_result_and_accept("update"))
        button_box.addWidget(update_btn)

        import_btn = QPushButton(_("Import as New File"))
        import_btn.clicked.connect(lambda: self._set_result_and_accept("import"))
        button_box.addWidget(import_btn)

        cancel_btn = QPushButton(_("Cancel"))
        cancel_btn.clicked.connect(self.reject)
        button_box.addWidget(cancel_btn)

        main_layout.addLayout(button_box)

    def _set_result_and_accept(self, result):
        self.result = result
        self.accept()