# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QWidget, QTableView
from PySide6.QtCore import Qt, Signal, QEvent, QTimer
from PySide6.QtGui import QPainter, QColor, QMouseEvent
from .tooltip import Tooltip
import bisect
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
        self._selection_model = None
        self._update_timer = QTimer(self)
        self._update_timer.setSingleShot(True)
        self._update_timer.setInterval(50)
        self._update_timer.timeout.connect(self._update_selection_ranges_from_model)
        self._point_markers = defaultdict(list)
        self._range_markers = defaultdict(list)

        self._marker_configs = {
            # Point Markers (drawn on the left track)
            'error': {'color': QColor(237, 28, 36, 200), 'priority': 10, 'label': _("Error")},
            'warning': {'color': QColor(255, 193, 7, 200), 'priority': 9, 'label': _("Warning")},
            'info': {'color': QColor(33, 150, 243, 200), 'priority': 8, 'label': _("Info")},
            'search': {'color': QColor(147, 112, 219, 180), 'priority': 7, 'label': _("Search Match")},

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

    def add_marker(self, marker_type: str, source_row: int):
        """Adds a single point marker efficiently."""
        if marker_type not in self._marker_configs:
            return

        marker_list = self._point_markers[marker_type]
        insertion_point = bisect.bisect_left(marker_list, source_row)
        if insertion_point == len(marker_list) or marker_list[insertion_point] != source_row:
            marker_list.insert(insertion_point, source_row)
            self._invalidate_cache()

    def remove_marker(self, marker_type: str, source_row: int):
        """Removes a single point marker efficiently."""
        if marker_type not in self._point_markers:
            return

        marker_list = self._point_markers[marker_type]
        index = bisect.bisect_left(marker_list, source_row)
        if index != len(marker_list) and marker_list[index] == source_row:
            marker_list.pop(index)
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

    def set_selection_model(self, selection_model):
        if hasattr(self, '_selection_model') and self._selection_model:
            try:
                self._selection_model.selectionChanged.disconnect(self._on_selection_changed_internal)
            except RuntimeError:
                pass

        self._selection_model = selection_model
        if self._selection_model:
            self._selection_model.selectionChanged.connect(self._on_selection_changed_internal)

    def _on_selection_changed_internal(self, selected, deselected):
        if not self._selection_model or not self.proxy_model:
            self.clear_ranges('selection')
            return

        selection = self._selection_model.selection()
        if selection.isEmpty():
            self.clear_ranges('selection')
            return

        total_selected_rows = sum(r.height() for r in selection)
        SELECTION_THRESHOLD = 1000

        if total_selected_rows > SELECTION_THRESHOLD and total_selected_rows :
            self.clear_ranges('selection')
            if self._update_timer.isActive():
                self._update_timer.stop()
        else:
            self._update_timer.start()

    def _update_selection_ranges_from_model(self):
        if not self._selection_model or not self.proxy_model:
            self.clear_ranges('selection')
            return

        selection = self._selection_model.selection()
        if selection.isEmpty():
            self.clear_ranges('selection')
            return

        total_selected_rows = sum(r.height() for r in selection)
        SELECTION_THRESHOLD = 1000

        if total_selected_rows > SELECTION_THRESHOLD:
            self.clear_ranges('selection')
            return

        # 选中过多
        if total_selected_rows > SELECTION_THRESHOLD:
            self.clear_ranges('selection')
            return

        # 正常选择
        ranges = []
        source_rows = []

        for selection_range in selection:
            if not selection_range.isValid():
                continue

            top = selection_range.top()
            bottom = selection_range.bottom()

            for r in range(top, bottom + 1):
                src_idx = self.proxy_model.mapToSource(self.proxy_model.index(r, 0))
                if src_idx.isValid():
                    source_rows.append(src_idx.row())

        if source_rows:
            source_rows.sort()
            ranges = self._merge_selection_ranges(source_rows)
            self.set_ranges('selection', ranges)
        else:
            self.clear_ranges('selection')

    def _merge_selection_ranges(self, sorted_source_rows: list) -> list:
        if not sorted_source_rows:
            return []

        # 如果两个标记在屏幕上的距离小于3像素，则合并显示
        Y_THRESHOLD = 3
        ranges = []
        current_range_start = sorted_source_rows[0]
        current_range_end = sorted_source_rows[0]

        for i in range(1, len(sorted_source_rows)):
            prev_row = sorted_source_rows[i - 1]
            current_row = sorted_source_rows[i]

            # 计算视觉距离
            y_prev = self._row_to_y(prev_row)
            y_current = self._row_to_y(current_row)

            if (current_row == prev_row + 1) or ((y_current - y_prev) <= Y_THRESHOLD):
                current_range_end = current_row
            else:
                ranges.append((current_range_start, current_range_end))
                current_range_start = current_row
                current_range_end = current_row

        ranges.append((current_range_start, current_range_end))
        return ranges

    def _invalidate_cache(self):
        self._cache_valid = False
        self.update()

    def _get_total_rows(self):
        if not self.proxy_model or not self.proxy_model.sourceModel(): return 0
        return self.proxy_model.sourceModel().rowCount()

    def _get_row_height(self):
        total_rows = self._get_total_rows()
        if total_rows == 0: return 0
        return self.height() / total_rows

    def _row_to_y(self, source_row: int) -> int:
        total_rows = self._get_total_rows()
        if total_rows == 0: return 0
        return int((source_row / total_rows) * self.height())

    def _y_to_row(self, y: int) -> int:
        total_rows = self._get_total_rows()
        if total_rows == 0: return 0
        return int((y / self.height()) * total_rows)

    def _build_cache(self):
        if self._cache_valid:
            return
        height = self.height()
        if height == 0:
            self._cached_points = []
            self._cache_valid = True
            return
        pixel_map = {}
        # [CRITICAL RENDERING LOGIC]
        # We sort by priority in DESCENDING order (Higher number = Higher priority).
        # We iterate from highest to lowest priority.
        # The check `if y not in pixel_map` ensures that the HIGHEST priority marker
        # claims the pixel first. Lower priority markers at the same pixel are ignored.
        # DO NOT CHANGE SORT ORDER without understanding this "first-come-first-served" logic.
        # ---------------------------------------------------------------------------
        sorted_marker_types = sorted(
            [mt for mt in self._marker_configs if mt in self._point_markers],
            key=lambda k: self._marker_configs[k]['priority'],
            reverse=True
        )
        for marker_type in sorted_marker_types:
            config = self._marker_configs[marker_type]
            for row in self._point_markers[marker_type]:
                y = self._row_to_y(row)
                if y not in pixel_map:
                    pixel_map[y] = {
                        'source_row': row,
                        'color': config['color'],
                        'type': marker_type,
                        'label': config.get('label', marker_type.capitalize())
                    }
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

        visual_row_height = self.height() / total_rows
        effective_row_height = max(1.0, visual_row_height)

        # 1. Draw Range Markers on the right track
        sorted_range_types = sorted(self._range_markers.keys(), key=lambda k: self._marker_configs[k]['priority'],
                                    reverse=True)
        painter.setPen(Qt.NoPen)
        for range_type in sorted_range_types:
            config = self._marker_configs[range_type]
            for start_row, end_row in self._range_markers[range_type]:
                y_start = self._row_to_y(start_row)
                # y_end = y_start of end_row + height of end_row
                y_end = int(((end_row + 1) / total_rows) * self.height())

                height = max(1, y_end - y_start)

                painter.fillRect(self.range_track_x, y_start, self.range_track_width, height, config['color'])

        # 2. Draw Point Markers on the left track
        self._build_cache()

        marker_height = max(2, int(visual_row_height))

        for marker in self._cached_points:
            row_top = marker['y']
            draw_y = row_top + (int(visual_row_height) - marker_height) // 2

            painter.fillRect(0, draw_y, self.point_track_width, marker_height, marker['color'])

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
                    tooltip_parts = []
                    main_label = found_marker['label']
                    main_color = found_marker['color'].name()
                    tooltip_parts.append(f"<b style='color:{main_color}; font-size:13px;'>{main_label}</b>")
                    if found_marker.get('is_range'):
                        tooltip_parts.append(
                            f" <span style='color:#FFFFFF;'>({_('Range')}: {found_marker['start'] + 1} - {found_marker['end'] + 1})</span>")
                    else:
                        tooltip_parts.append(f" <span style='color:#FFFFFF;'>({_('Row')} {target_row + 1})</span>")

                    tooltip_parts.append("<hr style='border-color: #555; margin: 6px 0;'>")

                    if not ts_obj.is_warning_ignored:
                        groups = [
                            (_("Error"), ts_obj.warnings, "#D32F2F"),
                            (_("Warning"), ts_obj.minor_warnings, "#F57C00"),
                            (_("Info"), ts_obj.infos, "#1976D2")
                        ]

                        has_content = False
                        for title, msg_list, color in groups:
                            if msg_list:
                                has_content = True
                                tooltip_parts.append(
                                    f"<div style='color:{color}; font-weight:bold; margin-top:4px;'>{title}</div>")
                                for __, msg in msg_list:
                                    tooltip_parts.append(
                                        f"<div style='margin-left:8px;'>"
                                        f"<span style='color:{color};'>●</span> {msg}"
                                        f"</div>"
                                    )

                        if not has_content:
                            summary = ts_obj.original_semantic.replace("\n", " ")
                            if len(summary) > 50: summary = summary[:47] + "..."
                            tooltip_parts.append(f"<div style='color:#CCC;'>{summary}</div>")

                    else:
                        tooltip_parts.append(
                            f"<div style='color:#999; font-style:italic;'>{_('Warnings ignored')}</div>")

                    self.tooltip.show_tooltip(event.globalPos(), "".join(tooltip_parts), delay=1)
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