# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit, QSizePolicy
from PySide6.QtGui import QTextCharFormat, QColor, QTextCursor, QFont
from PySide6.QtCore import Qt
from utils.localization import _


class ContextPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.app_instance = parent
        self.setup_ui()
        self.line_highlight_format = QTextCharFormat()
        self.line_highlight_format.setBackground(QColor("#E3F2FD"))
        self.keyword_highlight_format = QTextCharFormat()
        self.keyword_highlight_format.setBackground(QColor("#E3F2FD"))
        self.keyword_highlight_format.setFontUnderline(True)
        self.keyword_highlight_format.setUnderlineColor(QColor("#007BFF"))
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

    def set_context(self, ts_obj):
        cursor = self.context_text_display.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.setCharFormat(self.default_format)
        self.context_text_display.clear()

        if not  ts_obj or not ts_obj.context_lines:
            self.context_text_display.setPlainText("")
            return

        context_lines = ts_obj.context_lines
        current_line_in_context_idx = ts_obj.current_line_in_context_idx
        keyword_to_highlight = ts_obj.original_raw
        full_text = "\n".join(context_lines)
        self.context_text_display.setPlainText(full_text)

        if 0 <= current_line_in_context_idx < len(context_lines):
            doc = self.context_text_display.document()
            current_block = doc.findBlockByNumber(current_line_in_context_idx)

            if not current_block.isValid():
                return

            cursor = QTextCursor(current_block)
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            cursor.setCharFormat(self.line_highlight_format)
            if self.app_instance.is_project_mode:
                file_content_for_context = self.app_instance.current_active_source_file_content
            else:
                file_content_for_context = self.app_instance.original_raw_code_content

            keyword_cursor = None
            if file_content_for_context:
                line_start_char_pos_in_file = file_content_for_context.rfind(
                    '\n', 0, ts_obj.char_pos_start_in_file
                ) + 1
                keyword_start_in_line = ts_obj.char_pos_start_in_file - line_start_char_pos_in_file

                if keyword_start_in_line >= 0:
                    keyword_cursor = QTextCursor(current_block)
                    keyword_cursor.setPosition(current_block.position() + keyword_start_in_line)
                    keyword_cursor.setPosition(
                        current_block.position() + keyword_start_in_line + len(keyword_to_highlight),
                        QTextCursor.KeepAnchor
                    )
                    if keyword_cursor.selectedText() == keyword_to_highlight:
                        keyword_cursor.setCharFormat(self.keyword_highlight_format)
                    else:
                        keyword_cursor = None

            # 定位到关键词
            scroll_target_cursor = keyword_cursor if keyword_cursor else QTextCursor(current_block)
            self.context_text_display.setTextCursor(scroll_target_cursor)
            cursor_rect = self.context_text_display.cursorRect()

            viewport_height = self.context_text_display.viewport().height()
            target_y = self.context_text_display.verticalScrollBar().value() + cursor_rect.top() - (
                        viewport_height / 2) + (cursor_rect.height() / 2)
            self.context_text_display.verticalScrollBar().setValue(int(target_y))

            viewport_width = self.context_text_display.viewport().width()
            target_x = self.context_text_display.horizontalScrollBar().value() + cursor_rect.left() - (
                        viewport_width / 2) + (cursor_rect.width() / 2)
            self.context_text_display.horizontalScrollBar().setValue(int(target_x))
            final_cursor = self.context_text_display.textCursor()
            start_position = final_cursor.selectionStart()
            final_cursor.clearSelection()
            final_cursor.setPosition(start_position)
            self.context_text_display.setTextCursor(final_cursor)

    def update_ui_texts(self):
        label = self.findChild(QLabel, "context_label")