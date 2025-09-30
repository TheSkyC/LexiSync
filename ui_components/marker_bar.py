# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QWidget, QTableView
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QColor
from collections import defaultdict
from logging import getLogger
logger = getLogger(__name__)

class MarkerBar(QWidget):
    marker_clicked = Signal(int)

    def __init__(self, table_view: QTableView, parent=None):
        super().__init__(parent)
        self.table_view = table_view
        self.proxy_model = None

        self._markers = defaultdict(list)

        self._marker_configs = {
            'error': {'color': QColor(237, 28, 36, 200), 'priority': 1},
            'warning': {'color': QColor(255, 193, 7, 200), 'priority': 2},
            'search': {'color': QColor(33, 150, 243, 180), 'priority': 3},
        }

        self._cached_markers = []
        self._cache_valid = False

        self.setFixedWidth(14)
        self.setMouseTracking(True)

        if self.table_view and self.table_view.verticalScrollBar():
            self.table_view.verticalScrollBar().valueChanged.connect(self.update)
            self.table_view.verticalScrollBar().rangeChanged.connect(self._invalidate_cache)

    def set_proxy_model(self, proxy_model):
        self.proxy_model = proxy_model
        if proxy_model:
            if proxy_model.sourceModel():
                proxy_model.sourceModel().modelReset.connect(self._invalidate_cache)
            proxy_model.layoutChanged.connect(self._invalidate_cache)

    def add_markers(self, marker_type: str, source_rows: list):
        if marker_type not in self._marker_configs:
            return

        unique_rows = sorted(list(set(source_rows)))

        if self._markers.get(marker_type) != unique_rows:
            self._markers[marker_type] = unique_rows
            self._invalidate_cache()

    def clear_markers(self, marker_type: str = None):
        if marker_type:
            self._markers.pop(marker_type, None)
        else:
            self._markers.clear()
        self._invalidate_cache()

    def _find_closest_marker(self, y_pos: int, tolerance: int = 5):
        """Finds the closest marker to a given Y position within a tolerance."""
        if not self._cached_markers:
            return None

        closest_marker = None
        min_distance = float('inf')

        # Since _cached_markers is now sparse, linear search is very fast.
        for marker in self._cached_markers:
            distance = abs(marker['y'] - y_pos)
            if distance < min_distance:
                min_distance = distance
                closest_marker = marker

        if min_distance <= tolerance:
            return closest_marker
        return None

    def mouseMoveEvent(self, event):
        closest_marker = self._find_closest_marker(event.pos().y())
        if closest_marker:
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.unsetCursor()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            closest_marker = self._find_closest_marker(event.pos().y())

            if closest_marker:
                source_row = closest_marker['source_row']
                self.marker_clicked.emit(source_row)

        super().mousePressEvent(event)

    def _invalidate_cache(self):
        self._cache_valid = False
        self.update()

    def _get_total_rows(self):
        if not self.proxy_model or not self.proxy_model.sourceModel():
            return 0
        return self.proxy_model.sourceModel().rowCount()

    def _row_to_y(self, source_row: int) -> int:
        total_rows = self._get_total_rows()
        if total_rows == 0:
            return 0
        return int((source_row / total_rows) * self.height())

    def _y_to_row(self, y: int) -> int:
        total_rows = self._get_total_rows()
        if total_rows == 0:
            return 0
        return int((y / self.height()) * total_rows)

    def _build_cache(self):
        """
        Builds a cache mapping pixel rows to the highest-priority marker at that position.
        This is highly optimized for large datasets.
        """
        if self._cache_valid:
            return

        height = self.height()
        if height == 0:
            self._cached_markers = []
            self._cache_valid = True
            return

        # --- START OF NEW CACHING LOGIC ---
        # Create a map where each key is a Y-pixel coordinate.
        # The value will be the highest-priority marker at that pixel.
        pixel_map = {}

        # Iterate through markers, sorted by priority (most important first)
        sorted_marker_types = sorted(self._marker_configs.keys(), key=lambda k: self._marker_configs[k]['priority'])

        for marker_type in sorted_marker_types:
            if marker_type in self._markers:
                config = self._marker_configs[marker_type]
                for row in self._markers[marker_type]:
                    y = self._row_to_y(row)

                    # If this pixel is not yet taken, or the current marker is of higher priority
                    # (which it is, due to our sorted iteration), we set it.
                    if y not in pixel_map:
                        pixel_map[y] = {
                            'source_row': row,
                            'color': config['color']
                        }

        # Convert the map to a simple list for fast iteration during painting
        self._cached_markers = [{'y': y, **data} for y, data in pixel_map.items()]
        # --- END OF NEW CACHING LOGIC ---

        self._cache_valid = True

    def paintEvent(self, event):
        """Draws the markers."""
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().window())

        self._build_cache()

        marker_height = 2  # Use a thin line for markers
        marker_width = self.width() - 4

        # --- START OF NEW PAINTING LOGIC ---
        for marker in self._cached_markers:
            painter.fillRect(
                2,
                marker['y'],
                marker_width,
                marker_height,
                marker['color']
            )
        # --- END OF NEW PAINTING LOGIC ---

        self._draw_viewport_indicator(painter)

    def _draw_viewport_indicator(self, painter):
        scrollbar = self.table_view.verticalScrollBar()
        if not scrollbar or not self.proxy_model or not self.proxy_model.sourceModel():
            return

        total_rows = self._get_total_rows()
        if total_rows == 0:
            return

        first_visible_proxy_row = self.table_view.rowAt(0)
        last_visible_proxy_row = self.table_view.rowAt(self.table_view.viewport().height() - 1)

        if first_visible_proxy_row < 0:
            first_visible_proxy_row = 0
        if last_visible_proxy_row < 0:
            last_visible_proxy_row = first_visible_proxy_row

        first_source_index = self.proxy_model.mapToSource(self.proxy_model.index(first_visible_proxy_row, 0))
        last_source_index = self.proxy_model.mapToSource(self.proxy_model.index(last_visible_proxy_row, 0))

        if first_source_index.isValid() and last_source_index.isValid():
            y1 = self._row_to_y(first_source_index.row())
            y2 = self._row_to_y(last_source_index.row())

            painter.fillRect(0, y1, self.width(), max(3, y2 - y1 + 1), QColor(128, 128, 128, 70))
