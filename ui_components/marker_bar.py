# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QWidget, QTableView
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QColor

from .tooltip import Tooltip
from utils.localization import _

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
            'error': {'color': QColor(237, 28, 36, 200), 'priority': 1, 'label': _("Error")},
            'warning': {'color': QColor(255, 193, 7, 200), 'priority': 2, 'label': _("Warning")},
            'search': {'color': QColor(33, 150, 243, 180), 'priority': 3, 'label': _("Search Match")},
        }

        self._cached_markers = []
        self._cache_valid = False

        self.setFixedWidth(14)
        self.setMouseTracking(True)

        self.tooltip = Tooltip()
        self._last_hovered_row = -1

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

        for marker in self._cached_markers:
            distance = abs(marker['y'] - y_pos)
            if distance < min_distance:
                min_distance = distance
                closest_marker = marker

        if min_distance <= tolerance:
            return closest_marker
        return None

    def mouseMoveEvent(self, event):
        """Dynamically change cursor and show tooltip based on proximity to a marker."""
        closest_marker = self._find_closest_marker(event.pos().y())

        if closest_marker:
            self.setCursor(Qt.PointingHandCursor)

            source_row = closest_marker['source_row']
            if source_row != self._last_hovered_row:
                self._last_hovered_row = source_row

                if not self.proxy_model or not self.proxy_model.sourceModel():
                    return

                source_index = self.proxy_model.sourceModel().index(source_row, 0)
                ts_obj = self.proxy_model.sourceModel().data(source_index, Qt.UserRole)

                if ts_obj:
                    marker_label = closest_marker.get('label', 'Info')

                    warnings_html = ""
                    if closest_marker.get('type') == 'error' and ts_obj.warnings:
                        warnings_html = "<br>".join([f"• {msg}" for __, msg in ts_obj.warnings])
                    elif closest_marker.get('type') == 'warning' and ts_obj.minor_warnings:
                        warnings_html = "<br>".join([f"• {msg}" for __, msg in ts_obj.minor_warnings])

                    tooltip_text = (
                        f"<b style='color:{closest_marker['color'].name()};'>{marker_label}</b> ({_('Row')} {source_row + 1})<br>"
                        f"<hr style='border-color: #555; margin: 4px 0;'>"
                        f"<b>{_('Original')}:</b> {ts_obj.original_semantic[:100].replace('<', '&lt;')}...<br>"
                        f"<b>{_('Translation')}:</b> {ts_obj.translation[:100].replace('<', '&lt;')}..."
                    )
                    if warnings_html:
                        tooltip_text += f"<hr style='border-color: #555; margin: 4px 0;'>{warnings_html}"

                    self.tooltip.show_tooltip(event.globalPosition().toPoint(), tooltip_text)
                else:
                    self.tooltip.hide()
        else:
            self.unsetCursor()
            self.tooltip.hide()
            self._last_hovered_row = -1

        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self.unsetCursor()
        self.tooltip.hide()
        self._last_hovered_row = -1
        super().leaveEvent(event)

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

        pixel_map = {}
        sorted_marker_types = sorted(self._marker_configs.keys(), key=lambda k: self._marker_configs[k]['priority'])

        for marker_type in sorted_marker_types:
            if marker_type in self._markers:
                config = self._marker_configs[marker_type]
                for row in self._markers[marker_type]:
                    y = self._row_to_y(row)
                    if y not in pixel_map:
                        pixel_map[y] = {
                            'source_row': row,
                            'color': config['color'],
                            'type': marker_type,
                            'label': config.get('label', marker_type.capitalize())
                        }
        self._cached_markers = [{'y': y, **data} for y, data in pixel_map.items()]

        self._cache_valid = True

    def paintEvent(self, event):
        """Draws the markers."""
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().window())

        self._build_cache()

        marker_height = 2
        marker_width = self.width() - 4

        for marker in self._cached_markers:
            painter.fillRect(
                2,
                marker['y'],
                marker_width,
                marker_height,
                marker['color']
            )

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
