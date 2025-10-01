# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QWidget, QTableView
from PySide6.QtCore import Qt, Signal, QEvent
from PySide6.QtGui import QPainter, QColor, QMouseEvent
from .tooltip import Tooltip
from collections import defaultdict
from utils.localization import _
import logging

logger = logging.getLogger(__name__)


class MarkerBar(QWidget):
    marker_clicked = Signal(int)

    def __init__(self, table_view: QTableView, parent=None):
        super().__init__(parent)
        self.table_view = table_view
        self.proxy_model = None

        self._point_markers = defaultdict(list)
        self._range_markers = defaultdict(list)

        self._marker_configs = {
            # Point Markers (drawn on the left track)
            'error': {'color': QColor(237, 28, 36, 200), 'priority': 10, 'label': _("Error")},
            'warning': {'color': QColor(255, 193, 7, 200), 'priority': 9, 'label': _("Warning")},
            'search': {'color': QColor(147, 112, 219, 180), 'priority': 8, 'label': _("Search Match")},

            # Range Markers (drawn on the right track)
            'selection': {'color': QColor(0, 120, 215, 180), 'priority': 20, 'label': _("Selection")},
            'git_modified': {'color': QColor(255, 193, 7, 150), 'priority': 5, 'label': _("Git Modified")},
            'git_added': {'color': QColor(76, 175, 80, 150), 'priority': 4, 'label': _("Git Added")},
        }

        self._cached_points = []
        self._cache_valid = False

        self.setFixedWidth(14)
        self.setMouseTracking(True)

        self.tooltip = Tooltip(self)
        self._last_hovered_row = -1

        if self.table_view and self.table_view.verticalScrollBar():
            self.table_view.verticalScrollBar().valueChanged.connect(self.update)
            self.table_view.verticalScrollBar().rangeChanged.connect(self._invalidate_cache)

    def set_proxy_model(self, proxy_model):
        self.proxy_model = proxy_model
        if proxy_model and proxy_model.sourceModel():
            proxy_model.sourceModel().modelReset.connect(self._invalidate_cache)
            proxy_model.layoutChanged.connect(self._invalidate_cache)

    def add_markers(self, marker_type: str, source_rows: list):
        if marker_type not in self._marker_configs: return
        unique_rows = sorted(list(set(source_rows)))
        if self._point_markers.get(marker_type) != unique_rows:
            self._point_markers[marker_type] = unique_rows
            self._invalidate_cache()

    def set_ranges(self, range_type: str, ranges: list):
        if range_type not in self._marker_configs: return
        if self._range_markers.get(range_type) != ranges:
            self._range_markers[range_type] = ranges
            self._invalidate_cache()

    def clear_markers(self, marker_type: str = None):
        if marker_type:
            self._point_markers.pop(marker_type, None)
        else:
            self._point_markers.clear()
        self._invalidate_cache()

    def clear_ranges(self, range_type: str = None):
        if range_type:
            self._range_markers.pop(range_type, None)
        else:
            self._range_markers.clear()
        self._invalidate_cache()

    def _invalidate_cache(self):
        self._cache_valid = False
        self.update()

    def _get_total_rows(self):
        if not self.proxy_model or not self.proxy_model.sourceModel(): return 0
        return self.proxy_model.sourceModel().rowCount()

    def _row_to_y(self, source_row: int) -> int:
        total_rows = self._get_total_rows()
        if total_rows == 0: return 0
        return int((source_row / total_rows) * self.height())

    def _y_to_row(self, y: int) -> int:
        total_rows = self._get_total_rows()
        if total_rows == 0: return 0
        return int((y / self.height()) * total_rows)

    def _build_cache(self):
        if self._cache_valid: return

        height = self.height()
        if height == 0:
            self._cached_points = []
            self._cache_valid = True
            return

        pixel_map = {}
        sorted_marker_types = sorted(self._marker_configs.keys(), key=lambda k: self._marker_configs[k]['priority'])

        for marker_type in sorted_marker_types:
            if marker_type in self._point_markers:
                config = self._marker_configs[marker_type]
                for row in self._point_markers[marker_type]:
                    y = self._row_to_y(row)
                    if y not in pixel_map:
                        pixel_map[y] = {'source_row': row, 'color': config['color'], 'type': marker_type,
                                        'label': config['label']}

        self._cached_points = [{'y': y, **data} for y, data in pixel_map.items()]
        self._cache_valid = True

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().window())

        total_rows = self._get_total_rows()
        if total_rows == 0:
            return

        self.point_track_width = int(self.width() * 0.6)
        self.range_track_width = self.width() - self.point_track_width
        self.range_track_x = self.point_track_width

        # 1. Draw Range Markers on the right track
        sorted_range_types = sorted(self._range_markers.keys(), key=lambda k: self._marker_configs[k]['priority'],
                                    reverse=True)
        painter.setPen(Qt.NoPen)
        for range_type in sorted_range_types:
            config = self._marker_configs[range_type]
            for start_row, end_row in self._range_markers[range_type]:
                y_start = self._row_to_y(start_row)
                y_end = self._row_to_y(end_row)
                height = max(1, y_end - y_start)
                painter.fillRect(self.range_track_x, y_start, self.range_track_width, height, config['color'])

        # 2. Draw Point Markers on the left track
        self._build_cache()
        marker_height = 2
        for marker in self._cached_points:
            painter.fillRect(0, marker['y'] - marker_height // 2, self.point_track_width, marker_height,
                             marker['color'])

        # 3. Draw Viewport Indicator over everything
        self._draw_viewport_indicator(painter)

    def _find_point_marker_at_y(self, y_pos: int, tolerance: int = 5):
        """Finds the closest point marker to a given Y position."""
        if not self._cached_points: return None

        closest_marker = None
        min_distance = float('inf')

        for marker in self._cached_points:
            distance = abs(marker['y'] - y_pos)
            if distance < min_distance:
                min_distance = distance
                closest_marker = marker

        if min_distance <= tolerance:
            return closest_marker
        return None

    def _find_range_marker_at_y(self, y_pos: int):
        """Finds if a y-coordinate falls within any of the drawn ranges."""
        target_row = self._y_to_row(y_pos)
        sorted_range_types = sorted(self._range_markers.keys(), key=lambda k: self._marker_configs[k]['priority'])
        for range_type in sorted_range_types:
            for start_row, end_row in self._range_markers[range_type]:
                if start_row <= target_row <= end_row:
                    config = self._marker_configs[range_type]
                    return {'type': range_type, 'label': config['label'], 'color': config['color'],
                            'source_row': target_row, 'is_range': True, 'start': start_row, 'end': end_row}
        return None

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

    def _find_marker_at_y(self, y_pos: int, tolerance: int = 5):
        """Finds the closest point marker OR a range marker at a given Y position."""
        # First, check for point markers (higher priority for interaction)
        closest_point = None
        min_distance = float('inf')
        for marker in self._cached_points:
            distance = abs(marker['y'] - y_pos)
            if distance < min_distance:
                min_distance = distance
                closest_point = marker
        if min_distance <= tolerance:
            return closest_point

        # If no point marker, check for range markers
        target_row = self._y_to_row(y_pos)
        sorted_range_types = sorted(self._range_markers.keys(), key=lambda k: self._marker_configs[k]['priority'])
        for range_type in sorted_range_types:
            for start_row, end_row in self._range_markers[range_type]:
                if start_row <= target_row <= end_row:
                    config = self._marker_configs[range_type]
                    return {'type': range_type, 'label': config['label'], 'color': config['color'],
                            'source_row': target_row, 'is_range': True, 'start': start_row, 'end': end_row}
        return None

    def mouseMoveEvent(self, event: QMouseEvent):
        pos = event.pos()
        found_marker = None

        # Determine which track the mouse is on based on X coordinate
        if pos.x() < self.point_track_width:
            # Mouse is on the left (point) track
            found_marker = self._find_point_marker_at_y(pos.y())
        else:
            # Mouse is on the right (range) track
            found_marker = self._find_range_marker_at_y(pos.y())

        if found_marker:
            self.setCursor(Qt.PointingHandCursor)
            target_row = found_marker['source_row']
            if target_row != self._last_hovered_row:
                self._last_hovered_row = target_row
                if not self.proxy_model or not self.proxy_model.sourceModel():
                    return

                source_index = self.proxy_model.sourceModel().index(target_row, 0)
                ts_obj = self.proxy_model.sourceModel().data(source_index, Qt.UserRole)

                if ts_obj:
                    label = found_marker['label']
                    color = found_marker['color']
                    tooltip_text = f"<b style='color:{color.name()};'>{label}</b> ({_('Row')} {target_row + 1})"

                    if found_marker.get('is_range'):
                        tooltip_text += f"<br>{_('Range')}: {found_marker['start'] + 1} - {found_marker['end'] + 1}"
                    else:
                        warnings_html = ""
                        if found_marker.get('type') == 'error' and ts_obj.warnings:
                            warnings_html = "<br>".join([f"• {msg}" for _, msg in ts_obj.warnings])
                        elif found_marker.get('type') == 'warning' and ts_obj.minor_warnings:
                            warnings_html = "<br>".join([f"• {msg}" for _, msg in ts_obj.minor_warnings])
                        if warnings_html:
                            tooltip_text += f"<hr style='border-color: #555; margin: 4px 0;'>{warnings_html}"

                    self.tooltip.show_tooltip(event.globalPos(), tooltip_text)
                else:
                    self.tooltip.hide()
        else:
            self.unsetCursor()
            self.tooltip.hide()
            self._last_hovered_row = -1

        super().mouseMoveEvent(event)

    def leaveEvent(self, event: QEvent):
        self.unsetCursor()
        self.tooltip.hide()
        self._last_hovered_row = -1
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            pos = event.pos()
            found_marker = None
            if pos.x() < self.point_track_width:
                found_marker = self._find_point_marker_at_y(pos.y())
            else:
                found_marker = self._find_range_marker_at_y(pos.y())
            if found_marker:
                self.marker_clicked.emit(found_marker['source_row'])
        super().mousePressEvent(event)