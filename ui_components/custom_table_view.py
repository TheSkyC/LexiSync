# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QTableView
from PySide6.QtCore import Qt, QPoint


class CustomTableView(QTableView):
    def __init__(self, parent=None, app_instance=None):
        super().__init__(parent)
        self.app = app_instance
        self.is_dragging = False
        self.press_pos = QPoint()

    def mousePressEvent(self, event):
        self.is_dragging = False
        self.press_pos = event.pos()

        index = self.indexAt(event.pos())
        if index.isValid():
            ts_obj = self.model().data(index, Qt.UserRole)
            if ts_obj and self.app and self.app.current_focused_ts_id != ts_obj.id:
                self.app.current_focused_ts_id = ts_obj.id
                self.viewport().update()

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not self.is_dragging and (event.pos() - self.press_pos).manhattanLength() > 5:
            self.is_dragging = True

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.is_dragging = False
        super().mouseReleaseEvent(event)