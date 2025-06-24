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

        background_color = index.data(Qt.BackgroundRole)
        if background_color and isinstance(background_color, QColor):
            painter.fillRect(option.rect, background_color)

        super().paint(painter, display_option, index)

        source_index = index.model().mapToSource(index)
        is_search_result = (source_index.row(), source_index.column()) in index.model().search_results_indices

        if is_search_result:
            painter.fillRect(option.rect, QColor(147, 112, 219, 70))  # 半透明紫色

        ts_obj = index.data(Qt.UserRole)
        if not ts_obj: return

        is_selected = option.state & self.parent().style().StateFlag.State_Selected
        is_focused = (self.app and ts_obj.id == self.app.current_focused_ts_id)
        if is_selected or is_focused or is_search_result:
            painter.save()

            if is_focused:
                pen = self.focus_border_pen
            elif is_selected:
                pen = self.selection_border_pen
            else:
                search_pen = QPen(QColor(255, 165, 0), 1)
                search_pen.setStyle(Qt.PenStyle.DotLine)
                pen = search_pen


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