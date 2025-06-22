# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex, QSortFilterProxyModel, Signal, QObject
from PySide6.QtGui import QColor, QFont
from difflib import SequenceMatcher
import re
from utils.localization import _
from services.validation_service import placeholder_regex


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

        row = index.row()
        col = index.column()

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
                    return "T"
                else:
                    return "U"
            elif col == 2:
                return ts_obj.original_semantic.replace("\n", "↵")
            elif col == 3:
                return ts_obj.get_translation_for_ui().replace("\n", "↵")
            elif col == 4:
                return ts_obj.comment.replace("\n", "↵")[:50]
            elif col == 5:
                return "✔" if ts_obj.is_reviewed else ""
            elif col == 6:
                return ts_obj.line_num_in_file

        elif role == Qt.UserRole:
            return ts_obj


        elif role == Qt.BackgroundRole:
            if ts_obj.warnings and not ts_obj.is_warning_ignored:
                return QColor("#FFDDDD")  # 严重警告 - 浅红色背景
            elif ts_obj.minor_warnings and not ts_obj.is_warning_ignored:
                return QColor("#FFFACD")  # 次级警告 - 浅黄色背景
            elif ts_obj.is_ignored:
                return QColor("#F0F0F0")  # 已忽略 - 浅灰色背景
            return None

        elif role == Qt.ForegroundRole:
            if ts_obj.warnings and not ts_obj.is_warning_ignored:
                return QColor("red")  # 严重警告 - 红色文字
            elif ts_obj.is_ignored:
                return QColor("#707070")  # 已忽略 - 深灰色文字
            elif ts_obj.translation.strip():
                if ts_obj.is_reviewed:
                    return QColor("darkgreen")  # 已审阅 - 深绿色
                else:
                    return QColor("darkblue")  # 已翻译 - 深蓝色
            else:
                return QColor("darkred")  # 未翻译 - 暗红色

        elif role == Qt.FontRole:
            if ts_obj.is_ignored:
                font = QFont()
                font.setItalic(True)
                return font

        return None

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
        self.deduplicate = False
        self.show_ignored = True
        self.show_untranslated = False
        self.show_translated = False
        self.show_unreviewed = False
        self.search_term = ""
        self.is_po_mode = False
        self.processed_originals_for_dedup = set()
        self.new_entry_id = "##NEW_ENTRY##"

    def set_filters(self, deduplicate, show_ignored, show_untranslated, show_translated, show_unreviewed, search_term, is_po_mode):
        self.deduplicate = deduplicate
        self.show_ignored = show_ignored
        self.show_untranslated = show_untranslated
        self.show_translated = show_translated
        self.show_unreviewed = show_unreviewed
        self.search_term = search_term.lower()
        self.is_po_mode = is_po_mode

    def filterAcceptsRow(self, source_row, source_parent):
        ts_obj = self.sourceModel().data(self.sourceModel().index(source_row, 0, source_parent), Qt.UserRole)
        if not ts_obj:
            return False

        if self.is_po_mode and ts_obj.id == self.new_entry_id:
            return True

        if self.deduplicate:
            if ts_obj.original_semantic in self.processed_originals_for_dedup:
                return False
            self.processed_originals_for_dedup.add(ts_obj.original_semantic)

        has_translation = bool(ts_obj.translation.strip())

        if not self.show_ignored and ts_obj.is_ignored: return False
        if self.show_untranslated and has_translation and not ts_obj.is_ignored: return False
        if self.show_translated and not has_translation and not ts_obj.is_ignored: return False
        if self.show_unreviewed and ts_obj.is_reviewed: return False

        if self.search_term:
            if not (self.search_term in ts_obj.original_semantic.lower() or
                    self.search_term in ts_obj.get_translation_for_ui().lower() or
                    self.search_term in ts_obj.comment.lower()):
                return False

        return True

    def lessThan(self, left_index, right_index):

        left_obj = self.sourceModel().data(left_index, Qt.UserRole)
        right_obj = self.sourceModel().data(right_index, Qt.UserRole)

        if not left_obj or not right_obj:
            return False

        if self.is_po_mode:
            if left_obj.id == self.new_entry_id: return False
            if right_obj.id == self.new_entry_id: return True

        column = self.sortColumn()

        if column == 0:
            left_priority = 0 if (left_obj.warnings and not left_obj.is_warning_ignored) else 1
            right_priority = 0 if (right_obj.warnings and not right_obj.is_warning_ignored) else 1
            if left_priority != right_priority:
                return left_priority < right_priority
            return left_obj.line_num_in_file < right_obj.line_num_in_file
        elif column == 1:
            left_status_val = 0 if (left_obj.warnings and not left_obj.is_warning_ignored) else \
                1 if left_obj.is_ignored else \
                    2 if left_obj.translation.strip() else 3
            right_status_val = 0 if (right_obj.warnings and not right_obj.is_warning_ignored) else \
                1 if right_obj.is_ignored else \
                    2 if right_obj.translation.strip() else 3
            return left_status_val < right_status_val
        elif column == 2:
            return left_obj.original_semantic.lower() < right_obj.original_semantic.lower()
        elif column == 3:
            return left_obj.get_translation_for_ui().lower() < right_obj.get_translation_for_ui().lower()
        elif column == 4:
            return left_obj.comment.lower() < right_obj.comment.lower()
        elif column == 5:
            return left_obj.is_reviewed < right_obj.is_reviewed
        elif column == 6:
            return left_obj.line_num_in_file < right_obj.line_num_in_file

        return False

    def invalidateFilter(self):
        self.processed_originals_for_dedup.clear()
        super().invalidateFilter()

    def id_in_filtered_data(self, ts_id):
        source_index = self.sourceModel().index_from_id(ts_id)
        if source_index.isValid():
            proxy_index = self.mapFromSource(source_index)
            return proxy_index.isValid()
        return False