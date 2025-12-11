# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QTextEdit, QMessageBox
from PySide6.QtGui import QPainter, QColor, QFont, QTextCursor
from PySide6.QtCore import Qt, QPoint, QMimeData
from utils.localization import _
import logging
logger = logging.getLogger(__name__)


class NewlineTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.newline_symbol = "↵"
        self.newline_symbol_color = QColor(0, 122, 204, 100)
        self.reference_length = 0
        self.paste_limit_threshold = 10000
        self.drawing_limit_threshold = 5000

    def canInsertFromMimeData(self, source: QMimeData) -> bool:
        return source.hasText()

    def insertFromMimeData(self, source: QMimeData):
        if source.hasText():
            text = source.text()
            text_len = len(text)

            if text_len > self.paste_limit_threshold:

                similarity_ratio = 0.0
                if self.reference_length > 0:
                    similarity_ratio = self.reference_length / text_len
                if similarity_ratio < 0.7:
                    logger.info(f"Large paste detected.")
                    msg = _(
                        "Large Text Detected ({len} chars).\n"
                        "It exceeds the safety limit.\n\n"
                        "Pasting this might freeze the application. Continue anyway?"
                    ).format(len=text_len)

                    reply = QMessageBox.question(
                        self,
                        _("Paste Protection"),
                        msg,
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No
                    )

                    if reply == QMessageBox.No:
                        logger.info("Paste cancelled by user.")
                        return
                    else:
                        logger.info("User forced paste.")

            self.insertPlainText(text)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.document().characterCount() > self.drawing_limit_threshold:
            return
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

            if end_of_block_rect.bottom() < event.rect().top() or end_of_block_rect.top() > event.rect().bottom():
                block = block.next()
                continue
            x = end_of_block_rect.left() + 3
            y = end_of_block_rect.bottom() - font_metrics.descent()
            painter.drawText(int(x), int(y), self.newline_symbol)
            block = block.next()