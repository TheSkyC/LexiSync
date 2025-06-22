# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QStyledItemDelegate
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtCore import Qt


class BorderDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.app = parent.parent()  # 获取主窗口实例
        self.selection_border_pen = QPen(QColor(0, 100, 200), 1)
        self.focus_border_pen = QPen(QColor(0, 80, 180), 2)

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        ts_obj = index.data(Qt.UserRole)
        if not ts_obj:
            return
        is_selected = option.state & self.parent().style().StateFlag.State_Selected
        is_focused = (ts_obj.id == self.app.current_focused_ts_id)
        if not is_selected and not is_focused:
            return

        painter.save()
        if is_focused:
            painter.setPen(self.focus_border_pen)
        elif is_selected:
            painter.setPen(self.selection_border_pen)
        rect = option.rect
        if index.column() == 0:
            painter.drawLine(rect.topLeft(), rect.bottomLeft())
            painter.drawLine(rect.topLeft(), rect.topRight())
            painter.drawLine(rect.bottomLeft(), rect.bottomRight())
        elif index.column() == self.parent().model().columnCount() - 1:
            painter.drawLine(rect.topRight(), rect.bottomRight())
            painter.drawLine(rect.topLeft(), rect.topRight())
            painter.drawLine(rect.bottomLeft(), rect.bottomRight())
        else:
            painter.drawLine(rect.topLeft(), rect.topRight())
            painter.drawLine(rect.bottomLeft(), rect.bottomRight())
        painter.restore()