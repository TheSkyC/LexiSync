from PySide6.QtWidgets import QWidget, QTableView
from PySide6.QtCore import Qt, Signal, QEvent
from PySide6.QtGui import QPainter, QColor, QMouseEvent

from .tooltip import Tooltip

from collections import defaultdict
from utils.localization import _


class RangeMarkerBar(QWidget):
    range_clicked = Signal(int)

    """A narrow bar to display range-based markers like selection or git status."""
    def __init__(self, table_view: QTableView, parent=None):
        super().__init__(parent)
        self.table_view = table_view
        self.proxy_model = None

        self._ranges = defaultdict(list)

        self._range_configs = {
            'selection': {'color': QColor(0, 120, 215, 180), 'priority': 10, 'label': _("Selection")},

            'find_results': {'color': QColor(156, 39, 176, 100), 'priority': 8, 'label': _("Find Results")},

            'fuzzy': {'color': QColor(255, 87, 34, 120), 'priority': 6, 'label': _("Fuzzy Match")},

            'git_modified': {'color': QColor(255, 193, 7, 150), 'priority': 5, 'label': _("Git Modified")},
            'git_added': {'color': QColor(76, 175, 80, 150), 'priority': 4, 'label': _("Git Added")},

            'untranslated': {'color': QColor(244, 67, 54, 100), 'priority': 3, 'label': _("Untranslated")},
            'comment': {'color': QColor(0, 150, 136, 120), 'priority': 2, 'label': _("Comment")},
        }

        self.setFixedWidth(6)

        self.setMouseTracking(True)
        self.tooltip = Tooltip(self)
        self._last_hovered_row = -1

        if self.table_view and self.table_view.verticalScrollBar():
            self.table_view.verticalScrollBar().valueChanged.connect(self.update)
            self.table_view.verticalScrollBar().rangeChanged.connect(self.update)

    def set_proxy_model(self, proxy_model):
        self.proxy_model = proxy_model
        if proxy_model:
            if proxy_model.sourceModel():
                proxy_model.sourceModel().modelReset.connect(self.update)
            proxy_model.layoutChanged.connect(self.update)

    def set_ranges(self, range_type: str, ranges: list):
        """Sets or updates a list of ranges for a given type."""
        if range_type not in self._range_configs:
            return
        self._ranges[range_type] = ranges
        self.update()

    def clear_ranges(self, range_type: str = None):
        if range_type:
            self._ranges.pop(range_type, None)
        else:
            self._ranges.clear()
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

    def _find_range_at_y(self, y_pos: int):
        """Finds if a y-coordinate falls within any of the drawn ranges."""
        target_row = self._y_to_row(y_pos)

        # Iterate from highest priority to lowest
        sorted_types = sorted(self._ranges.keys(), key=lambda k: self._range_configs[k]['priority'])

        for range_type in sorted_types:
            for start_row, end_row in self._ranges[range_type]:
                if start_row <= target_row <= end_row:
                    return {
                        'type': range_type,
                        'label': self._range_configs[range_type]['label'],
                        'color': self._range_configs[range_type]['color'],
                        'start_row': start_row,
                        'end_row': end_row,
                        'target_row': target_row
                    }
        return None

    def mouseMoveEvent(self, event: QMouseEvent):
        found_range = self._find_range_at_y(event.pos().y())

        if found_range:
            self.setCursor(Qt.PointingHandCursor)

            target_row = found_range['target_row']
            if target_row != self._last_hovered_row:
                self._last_hovered_row = target_row

                tooltip_text = (
                    f"<b style='color:{found_range['color'].name()};'>{found_range['label']}</b><br>"
                    f"<hr style='border-color: #555; margin: 4px 0;'>"
                    f"{_('Range')}: {found_range['start_row'] + 1} - {found_range['end_row'] + 1}<br>"
                    f"{_('Current')}: {target_row + 1}"
                )
                self.tooltip.show_tooltip(event.globalPos(), tooltip_text)
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
            found_range = self._find_range_at_y(event.pos().y())
            if found_range:
                self.range_clicked.emit(found_range['target_row'])
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().window())
        total_rows = self._get_total_rows()
        if total_rows == 0:
            return
        sorted_types = sorted(self._ranges.keys(), key=lambda k: self._range_configs[k]['priority'], reverse=True)
        painter.setPen(Qt.NoPen)
        for range_type in sorted_types:
            config = self._range_configs[range_type]
            painter.setBrush(config['color'])
            for start_row, end_row in self._ranges[range_type]:
                y_start = self._row_to_y(start_row)
                y_end = self._row_to_y(end_row)

                height = max(1, y_end - y_start)

                painter.drawRect(0, y_start, self.width(), height)