# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QStyledItemDelegate
from PySide6.QtGui import QPainter, QFont, QColor
from PySide6.QtCore import Qt, QRect
from .border_delegate import BorderDelegate


class NewlineDelegate(BorderDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.newline_symbol = "↵"
        self.match_color = QColor(34, 177, 76, 180)  # Green for match
        self.mismatch_color = QColor(237, 28, 36, 180)  # Red for mismatch
        self.default_color = QColor(0, 122, 204, 180)  # Blue for default (e.g., original column)

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        current_text = index.data(Qt.DisplayRole)
        if not current_text or '↵' not in current_text:
            return
        symbol_color = self.default_color
        current_col = index.column()
        if current_col == 3:
            original_index = index.siblingAtColumn(2)
            original_text = original_index.data(Qt.DisplayRole)

            original_has_newline = '↵' in (original_text or "")
            translation_has_newline = '↵' in (current_text or "")

            if original_has_newline and translation_has_newline:
                symbol_color = self.match_color
            else:
                symbol_color = self.mismatch_color
        elif current_col == 2:
            translation_index = index.siblingAtColumn(3)
            translation_text = translation_index.data(Qt.DisplayRole)

            original_has_newline = '↵' in (current_text or "")
            translation_has_newline = '↵' in (translation_text or "")

            if original_has_newline and not translation_has_newline:
                symbol_color = self.mismatch_color
            else:
                symbol_color = self.match_color if translation_has_newline else self.default_color
        painter.save()

        symbol_font = QFont(option.font)
        symbol_font.setPointSize(int(option.font.pointSize() * 0.9))
        painter.setFont(symbol_font)
        painter.setPen(symbol_color)
        font_metrics = painter.fontMetrics()
        symbol_width = font_metrics.horizontalAdvance(self.newline_symbol)

        x = option.rect.right() - symbol_width - 3
        y = option.rect.bottom() - font_metrics.descent() - 2

        painter.drawText(x, y, self.newline_symbol)

        painter.restore()