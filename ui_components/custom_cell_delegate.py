# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QStyledItemDelegate
from PySide6.QtGui import QPainter, QColor, QPen, QFont
from PySide6.QtCore import Qt
from models.translatable_strings_model import NewlineColorRole


class CustomCellDelegate(QStyledItemDelegate):
    def __init__(self, parent=None, app_instance=None):
        super().__init__(parent)
        self.app = app_instance

        self.selection_border_pen = QPen(QColor(51, 153, 255, 145), 1)
        self.focus_border_pen = QPen(QColor(255, 0, 0, 200), 1)

        self.newline_symbol = "↵"

    def paint(self, painter, option, index):
        original_text = index.data(Qt.DisplayRole)
        display_option = option
        if index.column() == 1:
            display_option.displayAlignment = Qt.AlignCenter
        if index.column() in [2, 3] and original_text and '\n' in original_text:
            display_option.text = original_text.replace('\n', '↵')

        super().paint(painter, display_option, index)

        ts_obj = index.data(Qt.UserRole)
        if not ts_obj: return
        is_focused = (self.app and ts_obj.id == self.app.current_focused_ts_id)
        is_selected = option.state & self.parent().style().StateFlag.State_Selected

        if is_selected:
            painter.save()
            pen = self.focus_border_pen if is_focused else self.selection_border_pen
            painter.setPen(pen)
            rect = option.rect
            painter.drawLine(rect.topLeft(), rect.topRight())
            painter.drawLine(rect.bottomLeft().x(), rect.bottomLeft().y() - 1, rect.bottomRight().x(),
                             rect.bottomRight().y() - 1)

            if index.column() == 0:
                painter.drawLine(rect.topLeft().x(), rect.topLeft().y(), rect.bottomLeft().x(),
                                 rect.bottomLeft().y() - 1)

            if index.column() == index.model().columnCount() - 1:
                painter.drawLine(rect.topRight().x(), rect.topRight().y(), rect.bottomRight().x(),
                                 rect.bottomRight().y() - 1)

            painter.restore()

        current_col = index.column()
        if current_col in [2, 3]:
            symbol_color = index.data(NewlineColorRole)
            if symbol_color and isinstance(symbol_color, QColor):
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