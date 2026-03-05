# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QWidget, QTableView
from PySide6.QtCore import Qt, Signal, QTimer, QEvent
from PySide6.QtGui import QPainter, QColor, QMouseEvent, QCursor
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
        self.sheet_model = None
        self._selection_model = None

        self._update_timer = QTimer(self)
        self._update_timer.setSingleShot(True)
        self._update_timer.setInterval(50)
        self._update_timer.timeout.connect(self._update_selection_ranges_from_model)

        self._point_markers = defaultdict(list)
        self._range_markers = defaultdict(list)

        self._marker_configs = {
            'error': {'color': QColor(237, 28, 36, 200), 'priority': 10, 'label': _("Error")},
            'warning': {'color': QColor(255, 193, 7, 200), 'priority': 9, 'label': _("Warning")},
            'info': {'color': QColor(33, 150, 243, 200), 'priority': 8, 'label': _("Info")},
            'search': {'color': QColor(147, 112, 219, 180), 'priority': 7, 'label': _("Search Match")},
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

    def set_model(self, model):
        self.sheet_model = model
        if self.sheet_model:
            self.sheet_model.modelReset.connect(self._invalidate_cache)
            self.sheet_model.layoutChanged.connect(self._invalidate_cache)

    def _invalidate_cache(self):
        self._cache_valid = False
        self.update()

    def _get_total_rows(self):
        return self.sheet_model.rowCount() if self.sheet_model else 0

    def clear_markers(self, marker_type: str = None):
        if marker_type:
            self._point_markers.pop(marker_type, None)
        else:
            self._point_markers.clear()
        self._invalidate_cache()

    def remove_marker(self, marker_type: str, source_row: int):
        if marker_type in self._point_markers:
            try:
                self._point_markers[marker_type].remove(source_row)
                self._invalidate_cache()
            except ValueError:
                pass

    def set_ranges(self, range_type: str, ranges: list):
        self._range_markers[range_type] = ranges
        self.update()

    def clear_ranges(self, range_type: str = None):
        if range_type:
            self._range_markers.pop(range_type, None)
        else:
            self._range_markers.clear()
        self.update()

    def _row_to_y(self, source_row: int) -> int:
        total = self._get_total_rows()
        if total == 0: return 0
        return int((source_row / total) * self.height())

    def _y_to_row(self, y: int) -> int:
        total = self._get_total_rows()
        if total == 0 or self.height() == 0: return 0
        return int((y / self.height()) * total)

    def add_markers(self, marker_type: str, source_rows: list):
        if marker_type not in self._marker_configs: return
        self._point_markers[marker_type] = sorted(list(set(source_rows)))
        self._invalidate_cache()

    def _build_cache(self):
        if self._cache_valid: return
        height = self.height()
        total_visible = self._get_total_rows()
        if height <= 0 or total_visible <= 0 or not self.sheet_model:
            self._cached_points = []
            self._cache_valid = True
            return

        ratio = height / total_visible
        pixel_map = {}
        sorted_types = sorted(self._point_markers.keys(), key=lambda k: self._marker_configs[k]['priority'])

        for m_type in sorted_types:
            config = self._marker_configs[m_type]
            for raw_idx in self._point_markers[m_type]:
                visual_row = self.sheet_model.get_visual_row_by_raw_index(raw_idx)
                if visual_row != -1 and visual_row < total_visible:
                    y = int(visual_row * ratio)
                    pixel_map[y] = {
                        'visual_row': visual_row,
                        'color': config['color'],
                        'label': config['label'],
                        'type': m_type
                    }
        self._cached_points = [{'y': y, **data} for y, data in pixel_map.items()]
        self._cache_valid = True

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().window())
        total = self._get_total_rows()
        if total <= 0: return
        height, ratio = self.height(), self.height() / total

        for r_type, ranges in self._range_markers.items():
            color = self._marker_configs[r_type]['color']
            for start, end in ranges:
                y1, y2 = int(start * ratio), int((end + 1) * ratio)
                painter.fillRect(8, y1, 6, max(1, y2 - y1), color)

        self._build_cache()
        marker_h = max(2, int(height / total))
        for pt in self._cached_points:
            painter.fillRect(0, pt['y'], 8, marker_h, pt['color'])

        first_vis = self.table_view.rowAt(0)
        last_vis = self.table_view.rowAt(self.table_view.viewport().height() - 1)
        if first_vis != -1:
            y1 = int(first_vis * ratio)
            y2 = int((last_vis + 1) * ratio) if last_vis != -1 else height
            painter.fillRect(0, y1, self.width(), max(2, y2 - y1), QColor(128, 128, 128, 60))

    def _find_marker_at_y(self, y_pos: int):
        if not self._cached_points: return None
        total = self._get_total_rows()
        row_h = self.height() / total
        tolerance = max(5, row_h / 2)
        closest, min_dist = None, float('inf')
        for pt in self._cached_points:
            dist = abs(pt['y'] + row_h / 2 - y_pos)
            if dist < min_dist: min_dist, closest = dist, pt
        return closest if min_dist <= tolerance else None

    def mouseMoveEvent(self, event: QMouseEvent):
        pos = event.pos()
        found = self._find_marker_at_y(pos.y()) if pos.x() < 8 else None

        # 如果左侧没找到，尝试检测右侧范围标记
        if not found:
            target_row = self._y_to_row(pos.y())
            for r_type, ranges in self._range_markers.items():
                for s, e in ranges:
                    if s <= target_row <= e:
                        found = {'visual_row': target_row, 'type': r_type, 'is_range': True,
                                 'start': s, 'end': e, 'label': self._marker_configs[r_type]['label'],
                                 'color': self._marker_configs[r_type]['color']}
                        break

        if found:
            self.setCursor(Qt.PointingHandCursor)
            v_row = found['visual_row']
            if v_row != self._last_hovered_row:
                self._last_hovered_row = v_row
                ts_obj = self.sheet_model.get_ts_object_by_visual_row(v_row)
                if ts_obj:
                    tooltip_parts = []
                    color_hex = found['color'].name()
                    tooltip_parts.append(f"<b style='color:{color_hex}; font-size:13px;'>{found['label']}</b>")

                    if found.get('is_range'):
                        tooltip_parts.append(
                            f" <span style='color:#FFFFFF;'>({_('Range')}: {found['start'] + 1}-{found['end'] + 1})</span>")
                    else:
                        tooltip_parts.append(f" <span style='color:#FFFFFF;'>({_('Row')} {v_row + 1})</span>")

                    tooltip_parts.append("<hr style='border-color: #555; margin: 6px 0;'>")

                    if not ts_obj.is_warning_ignored:
                        groups = [(_("Error"), ts_obj.warnings, "#D32F2F"),
                                  (_("Warning"), ts_obj.minor_warnings, "#F57C00"),
                                  (_("Info"), ts_obj.infos, "#1976D2")]
                        has_msg = False
                        for title, msgs, color in groups:
                            if msgs:
                                has_msg = True
                                tooltip_parts.append(
                                    f"<div style='color:{color}; font-weight:bold; margin-top:4px;'>{title}</div>")
                                for __, m in msgs:
                                    tooltip_parts.append(
                                        f"<div style='margin-left:8px;'><span style='color:{color};'>●</span> {m}</div>")
                        if not has_msg:
                            summary = ts_obj.original_semantic[:80].replace('\n', ' ')
                            tooltip_parts.append(f"<div style='color:#CCC;'>{summary}</div>")
                    else:
                        tooltip_parts.append(
                            f"<div style='color:#999; font-style:italic;'>{_('Warnings ignored')}</div>")

                    self.tooltip.show_tooltip(event.globalPos(), "".join(tooltip_parts), delay=0)
        else:
            self.unsetCursor()
            self.tooltip.hide()
            self._last_hovered_row = -1

    def leaveEvent(self, event):
        self._last_hovered_row = -1
        self.unsetCursor()
        self.tooltip.hide()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            pt = self._find_marker_at_y(event.pos().y())
            if pt:
                self.marker_clicked.emit(pt['visual_row'])
            else:
                total = self._get_total_rows()
                if total > 0:
                    self.marker_clicked.emit(int((event.pos().y() / self.height()) * total))

    def set_selection_model(self, sm):
        self._selection_model = sm
        if sm: sm.selectionChanged.connect(lambda: self._update_timer.start())

    def _update_selection_ranges_from_model(self):
        if not self._selection_model: return
        rows = sorted([i.row() for i in self._selection_model.selectedRows()])
        ranges = []
        if rows:
            start = end = rows[0]
            for i in range(1, len(rows)):
                if rows[i] == end + 1:
                    end = rows[i]
                else:
                    ranges.append((start, end))
                    start = end = rows[i]
            ranges.append((start, end))
        self.set_ranges('selection', ranges)