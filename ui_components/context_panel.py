# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit, QSizePolicy
from PySide6.QtGui import QTextCharFormat, QColor, QTextCursor, QFont
from PySide6.QtCore import Qt
from utils.localization import _


class ContextPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.line_highlight_format = QTextCharFormat()
        self.line_highlight_format.setBackground(QColor("yellow"))
        self.keyword_highlight_format = QTextCharFormat()
        self.keyword_highlight_format.setBackground(QColor("yellow"))
        self.keyword_highlight_format.setFontUnderline(True)
        self.keyword_highlight_format.setUnderlineColor(QColor("#007BFF"))  # 设置下划线颜色
        self.default_format = QTextCharFormat()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        self.context_text_display = QTextEdit()
        self.context_text_display.setReadOnly(True)
        self.context_text_display.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.context_text_display.setFontFamily("Consolas")
        self.context_text_display.setFontPointSize(9)
        self.context_text_display.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.context_text_display)

    def set_context(self, context_lines, current_line_in_context_idx, keyword_to_highlight=""):
        cursor = self.context_text_display.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.setCharFormat(self.default_format)
        self.context_text_display.clear()

        if not context_lines:
            self.context_text_display.setPlainText("")
            return

        processed_lines = [line.replace('\t', '    ') for line in context_lines]
        full_text = "\n".join(processed_lines)
        self.context_text_display.setPlainText(full_text)

        if 0 <= current_line_in_context_idx < len(context_lines):
            doc = self.context_text_display.document()
            current_block = doc.findBlockByNumber(current_line_in_context_idx)

            if not current_block.isValid():
                return

            # 高亮当前行
            cursor = QTextCursor(current_block)
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            cursor.setCharFormat(self.line_highlight_format)

            # 在高亮行内查找并高亮关键词
            if keyword_to_highlight:
                block_text = current_block.text()
                start_pos = block_text.find(keyword_to_highlight)
                if start_pos != -1:
                    keyword_cursor = QTextCursor(current_block)
                    keyword_cursor.setPosition(current_block.position() + start_pos)
                    keyword_cursor.setPosition(
                        current_block.position() + start_pos + len(keyword_to_highlight),
                        QTextCursor.KeepAnchor
                    )
                    keyword_cursor.setCharFormat(self.keyword_highlight_format)

            # 滚动到视图中央
            scroll_target_cursor = QTextCursor(current_block)
            self.context_text_display.setTextCursor(scroll_target_cursor)
            cursor_rect = self.context_text_display.cursorRect()
            viewport_height = self.context_text_display.viewport().height()
            target_y = cursor_rect.top() - (viewport_height / 2) + (cursor_rect.height() / 2)
            self.context_text_display.verticalScrollBar().setValue(int(target_y))

    def update_ui_texts(self):
        label = self.findChild(QLabel, "context_label")