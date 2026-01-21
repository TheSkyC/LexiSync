# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem
from PySide6.QtGui import QPainter, QColor, QPen, QFont
from PySide6.QtCore import Qt, QModelIndex


class CustomCellDelegate(QStyledItemDelegate):
    def __init__(self, parent=None, app_instance=None):
        super().__init__(parent)
        self.app = app_instance

        self.selection_border_pen = QPen(QColor(51, 153, 255, 145), 1)
        self.focus_border_pen = QPen(QColor(20, 100, 255, 255), 1)
        search_pen = QPen(QColor(255, 165, 0), 1)
        search_pen.setStyle(Qt.PenStyle.DotLine)
        self.search_highlight_pen = search_pen

        self.newline_symbol = "↵"

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        display_option = QStyleOptionViewItem(option)
        original_text = index.data(Qt.DisplayRole)
        text_to_draw = str(original_text) if original_text is not None else ""
        if index.column() in [2, 3] and '\n' in text_to_draw:
            text_to_draw = text_to_draw.replace('\n', '↵')
        display_option.text = text_to_draw
        if index.column() == 1:
            display_option.displayAlignment = Qt.AlignCenter
        background_color = index.data(Qt.BackgroundRole)
        if background_color and isinstance(background_color, QColor):
            painter.save()
            painter.fillRect(display_option.rect, background_color)
            painter.restore()
        super().paint(painter, display_option, index)
        painter.save()
        current_proxy_index_tuple = (index.row(), index.column())

        is_find_match = False
        is_current_find_focus = False

        if hasattr(self.app, 'search_service'):
            is_find_match = current_proxy_index_tuple in self.app.search_service.highlight_indices
            is_current_find_focus = current_proxy_index_tuple == self.app.search_service.current_focus_index

        if is_current_find_focus:
            painter.fillRect(display_option.rect, QColor(144, 238, 144, 150))
        elif is_find_match:
            painter.fillRect(display_option.rect, QColor(147, 112, 219, 110))
        painter.restore()

        painter.save()
        ts_obj = index.data(Qt.UserRole)
        if ts_obj:
            is_selected = display_option.state & self.parent().style().StateFlag.State_Selected
            is_focused = (self.app and ts_obj.id == self.app.current_focused_ts_id)

            pen_to_use = None
            if is_focused:
                pen_to_use = self.focus_border_pen
            elif is_selected:
                pen_to_use = self.selection_border_pen
            elif is_find_match:
                pen_to_use = self.search_highlight_pen

            if pen_to_use:
                painter.setPen(pen_to_use)
                rect = display_option.rect
                painter.drawLine(rect.topLeft(), rect.topRight())
                painter.drawLine(rect.bottomLeft().x(), rect.bottomLeft().y() - 1, rect.bottomRight().x(),
                                 rect.bottomRight().y() - 1)
                if index.column() == 0:
                    painter.drawLine(rect.topLeft().x(), rect.topLeft().y(), rect.bottomLeft().x(),
                                     rect.bottomLeft().y() - 1)
                if index.column() == index.model().columnCount() - 1:
                    painter.drawLine(rect.topRight().x(), rect.topRight().y(), rect.bottomRight().x(),
                                     rect.bottomRight().y() - 1)
        if index.column() in [2, 3]:
            symbol_color = None
            if index.column() == 2:  # 原文列
                symbol_color = ts_obj.ui_style_cache.get('original_newline_color')
            elif index.column() == 3:  # 译文列
                symbol_color = ts_obj.ui_style_cache.get('translation_newline_color')
            if symbol_color and isinstance(symbol_color, QColor):
                symbol_font = QFont(display_option.font)
                symbol_font.setPointSize(int(display_option.font.pointSize() * 0.9))
                painter.setFont(symbol_font)
                painter.setPen(symbol_color)
                font_metrics = painter.fontMetrics()
                symbol_width = font_metrics.horizontalAdvance(self.newline_symbol)
                x = display_option.rect.right() - symbol_width - 3
                y = display_option.rect.bottom() - font_metrics.descent() - 2
                painter.drawText(x, y, self.newline_symbol)

        painter.restore()