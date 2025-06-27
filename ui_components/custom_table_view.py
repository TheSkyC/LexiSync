# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QTableView
from PySide6.QtCore import Qt, QPoint, QTimer


class CustomTableView(QTableView):
    def __init__(self, parent=None, app_instance=None):
        super().__init__(parent)
        self.app = app_instance
        self.is_dragging = False
        self.press_pos = QPoint()

        self._is_scrollbar_dragging = False
        self._dx_accumulator = 0
        self._dy_accumulator = 0

        self._scroll_throttle_timer = QTimer(self)
        self._scroll_throttle_timer.setInterval(20)
        self._scroll_throttle_timer.setSingleShot(True)
        self._scroll_throttle_timer.timeout.connect(self._perform_throttled_scroll)
        scrollbar = self.verticalScrollBar()
        scrollbar.sliderPressed.connect(self._on_slider_pressed)
        scrollbar.sliderReleased.connect(self._on_slider_released)

    def _perform_throttled_scroll(self):
        if self._dx_accumulator != 0 or self._dy_accumulator != 0:
            super().scrollContentsBy(self._dx_accumulator, self._dy_accumulator)
            self._dx_accumulator = 0
            self._dy_accumulator = 0

    def _on_slider_pressed(self):
        self._is_scrollbar_dragging = True
        self._dx_accumulator = 0
        self._dy_accumulator = 0

    def _on_slider_released(self):
        self._is_scrollbar_dragging = False
        if self._scroll_throttle_timer.isActive():
            self._scroll_throttle_timer.stop()
        self._perform_throttled_scroll()

    def scrollContentsBy(self, dx, dy):
        if self._is_scrollbar_dragging:
            self._dx_accumulator += dx
            self._dy_accumulator += dy
            if not self._scroll_throttle_timer.isActive():
                self._scroll_throttle_timer.start()
        else:
            super().scrollContentsBy(dx, dy)

    def mousePressEvent(self, event):
        self.is_dragging = False
        self.press_pos = event.pos()

        index = self.indexAt(event.pos())
        if index.isValid():
            ts_obj = self.model().data(index, Qt.ItemDataRole.UserRole)
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
