# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit, QSizePolicy
from PySide6.QtGui import QTextCharFormat, QColor, QTextCursor
from PySide6.QtCore import Qt
from utils.localization import _

class ContextPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        self.context_label = QLabel(_("Context Preview:"))
        layout.addWidget(self.context_label)

        self.context_text_display = QTextEdit()
        self.context_text_display.setReadOnly(True)
        self.context_text_display.setLineWrapMode(QTextEdit.NoWrap) # Code context usually no wrap
        self.context_text_display.setFontFamily("Consolas") # Default code font
        self.context_text_display.setFontPointSize(9)
        self.context_text_display.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.context_text_display)

        self.highlight_format = QTextCharFormat()
        self.highlight_format.setBackground(QColor("yellow"))
        self.highlight_format.setForeground(QColor("black"))

    def set_context(self, context_lines, current_line_in_context_idx):
        self.context_text_display.clear()
        if not context_lines:
            return

        full_text = "\n".join(context_lines)
        self.context_text_display.setPlainText(full_text)

        if 0 <= current_line_in_context_idx < len(context_lines):
            cursor = QTextCursor(self.context_text_display.document())
            block = self.context_text_display.document().findBlockByNumber(current_line_in_context_idx)
            cursor.setPosition(block.position())
            cursor.setPosition(block.position() + block.length(), QTextCursor.KeepAnchor)
            cursor.mergeCharFormat(self.highlight_format)
            self.context_text_display.ensureCursorVisible()

    def update_ui_texts(self):
        self.context_label.setText(_("Context Preview:"))