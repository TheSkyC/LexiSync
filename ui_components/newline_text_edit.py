# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QTextEdit
from PySide6.QtGui import QPainter, QColor, QFont, QTextCursor
from PySide6.QtCore import Qt, QPoint

class NewlineTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.newline_symbol = "↵"
        self.newline_symbol_color = QColor(0, 122, 204, 100)  # Semi-transparent blue

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self.viewport())
        symbol_font = QFont(self.font())
        symbol_font.setPointSize(int(self.font().pointSize() * 0.9))
        painter.setFont(symbol_font)
        painter.setPen(self.newline_symbol_color)
        font_metrics = painter.fontMetrics()
        first_visible_cursor = self.cursorForPosition(event.rect().topLeft())
        last_visible_cursor = self.cursorForPosition(event.rect().bottomRight())
        block = first_visible_cursor.block()
        while block.isValid() and block.blockNumber() <= last_visible_cursor.blockNumber():
            if not block.next().isValid():
                break
            cursor = QTextCursor(block)
            cursor.movePosition(QTextCursor.EndOfBlock)
            end_of_block_rect = self.cursorRect(cursor)
            if end_of_block_rect.bottom() < event.rect().top():
                block = block.next()
                continue
            x = end_of_block_rect.left() + 3  # 3px padding
            y = end_of_block_rect.bottom() - font_metrics.descent()  # Align baseline
            painter.drawText(int(x), int(y), self.newline_symbol)
            block = block.next()