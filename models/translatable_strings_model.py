# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex, QSortFilterProxyModel, Signal, QObject
from utils.localization import _

NewlineColorRole = Qt.UserRole + 1

class TranslatableStringsModel(QAbstractTableModel):
    def __init__(self, data, parent=None):
        super().__init__(parent)
        self._data = data
        self._id_to_index_map = {obj.id: i for i, obj in enumerate(self._data)}
        self.headers = ["#", "S", "Original", "Translation", "Comment", "✔", "Line"]
        self.app_instance = parent

    def set_translatable_objects(self, new_data):
        self.beginResetModel()
        self._data = new_data
        self._id_to_index_map = {obj.id: i for i, obj in enumerate(self._data)}
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self.headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row, col = index.row(), index.column()
        if row >= len(self._data):
            return None
        ts_obj = self._data[row]

        if role == Qt.DisplayRole:
            if col == 0:
                return row + 1
            elif col == 1:
                if ts_obj.warnings and not ts_obj.is_warning_ignored:
                    return "⚠️"
                elif ts_obj.is_ignored:
                    return "I"
                elif ts_obj.translation.strip():
                    if ts_obj.minor_warnings and not ts_obj.is_warning_ignored:
                        return "*T"
                    return "T"
                else:
                    return "U"
            elif col == 2:
                return ts_obj.original_semantic
            elif col == 3:
                return ts_obj.get_translation_for_ui()
            elif col == 4:
                return ts_obj.comment
            elif col == 5:
                return "✔" if ts_obj.is_reviewed else ""
            elif col == 6:
                return ts_obj.line_num_in_file

        elif role == Qt.BackgroundRole:
            return ts_obj.ui_style_cache.get('background')

        elif role == Qt.ForegroundRole:
            return ts_obj.ui_style_cache.get('foreground')

        elif role == Qt.FontRole:
            return ts_obj.ui_style_cache.get('font')

        elif role == NewlineColorRole:
            if col in [2, 3]:
                if ts_obj.ui_style_cache.get('original_newline_color') or ts_obj.ui_style_cache.get('translation_newline_color'):
                     return ts_obj.ui_style_cache.get('original_newline_color') if col == 2 else ts_obj.ui_style_cache.get('translation_newline_color')
            return None

        elif role == Qt.UserRole:
            return ts_obj

        return None

    def sort_data(self, column, order):
        self.layoutAboutToBeChanged.emit()

        reverse = (order == Qt.DescendingOrder)

        if column == 1 or column == 5:  # Status / Reviewed
            # Primary: Weight, Secondary: Line Number
            key_func = lambda ts: (ts.sort_weight, ts.line_num_in_file)
        elif column == 2:  # Original
            key_func = lambda ts: ts.original_semantic.lower()
        elif column == 3:  # Translation
            key_func = lambda ts: ts.get_translation_for_ui().lower()
        elif column == 4:  # Comment
            key_func = lambda ts: ts.comment.lower()
        elif column == 6:  # Line
            key_func = lambda ts: ts.line_num_in_file
        else:  # ID (0) or Default
            key_func = lambda ts: ts.line_num_in_file

        self._data.sort(key=key_func, reverse=reverse)

        # Rebuild the ID map
        self._id_to_index_map = {obj.id: i for i, obj in enumerate(self._data)}

        self.layoutChanged.emit()

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            if section < len(self.headers):
                header_text = self.headers[section]
                try:
                    return _(header_text)
                except:
                    return header_text
        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def index_from_id(self, ts_id):
        if ts_id in self._id_to_index_map:
            row = self._id_to_index_map[ts_id]
            return self.index(row, 0)
        return QModelIndex()


class TranslatableStringsProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.show_ignored = True
        self.show_untranslated = False
        self.show_translated = False
        self.show_unreviewed = False
        self.search_term = ""
        self.search_results_indices = set()
        self.is_po_mode = False
        self._current_filter_seen_originals = set()
        self.new_entry_id = "##NEW_ENTRY##"
        super().setDynamicSortFilter(False)

    def setDynamicSortFilter(self, enable):
        super().setDynamicSortFilter(False)

    def setSourceModel(self, sourceModel):
        # Disconnect previous model if exists
        if self.sourceModel():
            try:
                self.sourceModel().dataChanged.disconnect(self._source_data_changed)
            except RuntimeError:
                pass

        super().setSourceModel(sourceModel)

        # Connect new model to custom handler
        if sourceModel:
            sourceModel.dataChanged.connect(self._source_data_changed)

    def _source_data_changed(self, topLeft, bottomRight, roles=None):
        if not topLeft.isValid() or not bottomRight.isValid():
            return

        start_proxy = self.mapFromSource(topLeft)
        end_proxy = self.mapFromSource(bottomRight)

        # Only emit dataChanged for visible rows
        if start_proxy.isValid() and end_proxy.isValid():
            self.dataChanged.emit(start_proxy, end_proxy, roles if roles is not None else [])

    def set_filters(self, show_ignored, show_untranslated, show_translated, show_unreviewed, search_term, is_po_mode,
                    sort_column, sort_order):
        self.show_ignored = show_ignored
        self.show_untranslated = show_untranslated
        self.show_translated = show_translated
        self.show_unreviewed = show_unreviewed
        self.search_term = search_term.lower()
        self.is_po_mode = is_po_mode

        self.invalidateFilter()
        self.sort(sort_column, sort_order)

    def filterAcceptsRow(self, source_row, source_parent):
        ts_obj = self.sourceModel()._data[source_row]
        if not ts_obj:
            return False
        if self.is_po_mode and ts_obj.id == self.new_entry_id:
            return True
        if self.search_term:
            if not (self.search_term in ts_obj.original_semantic.lower() or
                    self.search_term in ts_obj.get_translation_for_ui().lower() or
                    self.search_term in ts_obj.comment.lower()):
                return False
        has_translation = bool(ts_obj.translation.strip())
        if not self.show_ignored and ts_obj.is_ignored: return False
        if self.show_untranslated and has_translation and not ts_obj.is_ignored: return False
        if self.show_translated and not has_translation and not ts_obj.is_ignored: return False
        if self.show_unreviewed and ts_obj.is_reviewed: return False

        return True

    def sort(self, column, order=Qt.AscendingOrder):
        source = self.sourceModel()
        if source:
            source.sort_data(column, order)
            self.invalidate()

    def lessThan(self, left_index, right_index):
        source_model = self.sourceModel()
        left_obj = source_model._data[left_index.row()]
        right_obj = source_model._data[right_index.row()]

        if not left_obj or not right_obj:
            return False

        if self.is_po_mode:
            if left_obj.id == self.new_entry_id: return False
            if right_obj.id == self.new_entry_id: return True

        column = self.sortColumn()

        # Column 1 (Status Icon) or Column 5 (Reviewed Checkmark)
        if column == 1 or column == 5:
            # Use pre-calculated sort_weight
            if left_obj.sort_weight != right_obj.sort_weight:
                return left_obj.sort_weight < right_obj.sort_weight
            else:
                # Secondary sort by line number
                return left_obj.line_num_in_file < right_obj.line_num_in_file

        elif column == 0:  # ID / Row Num
            return left_index.row() < right_index.row()
        elif column == 2:  # Original
            return left_obj.original_semantic.lower() < right_obj.original_semantic.lower()
        elif column == 3:  # Translation
            return left_obj.get_translation_for_ui().lower() < right_obj.get_translation_for_ui().lower()
        elif column == 4:  # Comment
            return left_obj.comment.lower() < right_obj.comment.lower()
        elif column == 6:  # Line Num
            return left_obj.line_num_in_file < right_obj.line_num_in_file

        return False

    def invalidateFilter(self):
        self._current_filter_seen_originals.clear()
        super().invalidateFilter()

    def id_in_filtered_data(self, ts_id):
        source_index = self.sourceModel().index_from_id(ts_id)
        if source_index.isValid():
            proxy_index = self.mapFromSource(source_index)
            return proxy_index.isValid()
        return False