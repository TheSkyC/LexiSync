# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QDialogButtonBox, QLabel, QSplitter, QWidget
from PySide6.QtCore import Qt

class PreviewDialog(QDialog):
    def __init__(self, parent, original_text, preview_text, translator):
        super().__init__(parent)
        self._ = translator
        self.setWindowTitle(self._("Pseudo-Localization Preview"))
        self.setModal(True)
        self.resize(600, 400)

        layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Vertical)

        original_widget = QWidget()
        original_layout = QVBoxLayout(original_widget)
        original_layout.addWidget(QLabel(self._("Original Text:")))
        original_edit = QTextEdit(original_text)
        original_edit.setReadOnly(True)
        original_layout.addWidget(original_edit)

        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.addWidget(QLabel(self._("Preview:")))
        preview_edit = QTextEdit(preview_text)
        preview_edit.setReadOnly(True)
        preview_layout.addWidget(preview_edit)

        splitter.addWidget(original_widget)
        splitter.addWidget(preview_widget)
        layout.addWidget(splitter)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)