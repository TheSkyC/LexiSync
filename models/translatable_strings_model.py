# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor

from utils.localization import _

NewlineColorRole = Qt.UserRole + 1


class TranslatableStringsModel(QAbstractTableModel):
    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.app_instance = parent
        self.headers = ["#", "S", "Original", "Translation", "Comment", "✔", "Line"]

        self._all_data = data  # 所有数据 (List[TranslatableString])
        self._visible_indices = list(range(len(data)))  # 可见行的索引映射 [0, 1, 5, 8...]
        self._raw_to_visual_map = {i: i for i in range(len(data))}  # 反向映射表

        # ID 映射表
        self._id_to_raw_index_map = {obj.id: i for i, obj in enumerate(self._all_data)}
        self._default_flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        self._colors = {
            "transparent": QColor(Qt.transparent),
            "bg_ignored": QColor(220, 220, 220, 200),
            "fg_ignored": QColor("#707070"),
            "bg_error": QColor("#FFDDDD"),
            "fg_error": QColor("red"),
            "bg_warning": QColor("#FFFACD"),
            "fg_reviewed": QColor("darkgreen"),
            "fg_translated": QColor("darkblue"),
            "fg_untranslated": QColor("darkred"),
            "bg_read_only": QColor("#EFEFEF"),
        }

        self._colors = {
            "transparent": QColor(Qt.transparent),
            "bg_ignored": QColor(220, 220, 220, 200),
            "fg_ignored": QColor("#707070"),
            "bg_error": QColor("#FFDDDD"),
            "fg_error": QColor("#D32F2F"),  # 稍微深一点的红色，更易读
            "bg_warning": QColor("#FFFACD"),
            "bg_reviewed": QColor("#E8F5E9"),  # 浅绿色背景 (Material Green 50)
            "fg_reviewed": QColor("#000000"),  # 字体回归黑色
            "fg_translated": QColor("#000000"),  # 字体回归黑色
            "fg_untranslated": QColor("darkred"),
            "fg_default": QColor("#000000"),
            "bg_read_only": QColor("#EFEFEF"),
        }
        self._column_count = len(self.headers)
        self.current_search_term = ""

    def set_translatable_objects(self, new_data):
        """重置整个模型的数据"""
        self.beginResetModel()
        self._all_data = new_data
        self._id_to_index_map = {obj.id: i for i, obj in enumerate(self._all_data)}  # 兼容旧代码命名习惯
        self._id_to_raw_index_map = self._id_to_index_map
        # 默认显示所有数据
        self._visible_indices = list(range(len(new_data)))
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return len(self._visible_indices)

    def columnCount(self, parent=QModelIndex()):
        return self._column_count

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal and section < len(self.headers):
            try:
                return _(self.headers[section])
            except Exception:
                return self.headers[section]
        return None

    def flags(self, index):
        return self._default_flags

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        row = index.row()
        if row >= len(self._visible_indices):
            return None

        raw_index = self._visible_indices[row]
        ts_obj = self._all_data[raw_index]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 2:
                return ts_obj._display_original
            if col == 3:
                return ts_obj._display_translation
            if col == 4:
                return ts_obj.comment.replace("\n", " ")
            if col == 1:
                if ts_obj.is_ignored:
                    return "I"
                if ts_obj.is_reviewed:
                    return "R" if ts_obj.translation.strip() else "U"
                if ts_obj.warnings and not ts_obj.is_warning_ignored:
                    return "⚠️"
                if ts_obj.translation.strip():
                    return "*T" if (ts_obj.minor_warnings and not ts_obj.is_warning_ignored) else "T"
                return "U"
            if col == 0:
                return row + 1
            if col == 5:
                return "✔" if ts_obj.is_reviewed else ""
            if col == 6:
                return ts_obj.line_num_in_file

        elif role == Qt.BackgroundRole:
            # 1. 已忽略 (灰色)
            if ts_obj.is_ignored:
                if ts_obj.warnings and not ts_obj.is_warning_ignored:
                    return self._colors["bg_error"]
                return self._colors["bg_ignored"]
            # 2. 已审阅 (绿色)
            if ts_obj.is_reviewed:
                return self._colors["bg_reviewed"]
            # 3. 错误 (红色)
            if ts_obj.warnings and not ts_obj.is_warning_ignored:
                return self._colors["bg_error"]
            # 4. 警告 (黄色)
            if ts_obj.minor_warnings and not ts_obj.is_warning_ignored:
                return self._colors["bg_warning"]
            if col in [0, 3, 4, 6]:
                pass

            return self._colors["transparent"]

        elif role == Qt.ForegroundRole:
            # 1. 已忽略 (灰色)
            if ts_obj.is_ignored:
                return self._colors["fg_ignored"]
            # 2. 错误  (红色)
            if ts_obj.warnings and not ts_obj.is_warning_ignored and not ts_obj.is_reviewed:
                return self._colors["fg_error"]
            # 3. 未翻译 (暗红色)
            if not ts_obj.translation.strip():
                return self._colors["fg_untranslated"]
            # 4. 其他 （黑色）
            return self._colors["fg_default"]

        elif role == Qt.FontRole:
            return ts_obj.ui_style_cache.get("font")

        elif role == NewlineColorRole:
            if col in [2, 3]:
                if ts_obj.ui_style_cache.get("original_newline_color") or ts_obj.ui_style_cache.get(
                    "translation_newline_color"
                ):
                    return (
                        ts_obj.ui_style_cache.get("original_newline_color")
                        if col == 2
                        else ts_obj.ui_style_cache.get("translation_newline_color")
                    )
            return None

        elif role == Qt.UserRole:
            return ts_obj
        return None

    def apply_filter_and_sort(
        self,
        search_term,
        show_ignored,
        show_untranslated,
        show_translated,
        show_unreviewed,
        is_translation_mode,
        sort_col,
        sort_order,
    ):
        self.current_search_term = search_term.lower().strip()
        self.beginResetModel()

        search_term = search_term.lower().strip()
        new_entry_id = "##NEW_ENTRY##"
        data = self._all_data

        if not search_term and show_ignored and show_untranslated and show_translated and not show_unreviewed:
            self._visible_indices = list(range(len(data)))
        else:
            filtered_indices = []
            for i, ts in enumerate(data):
                if is_translation_mode and ts.id == new_entry_id:
                    filtered_indices.append(i)
                    continue

                if search_term and search_term not in ts._search_cache:
                    continue

                if ts.is_ignored:
                    if not show_ignored:
                        continue
                else:
                    has_trans = bool(ts.translation.strip())
                    if not has_trans and not show_untranslated:
                        continue
                    if has_trans and not show_translated:
                        continue

                if show_unreviewed and ts.is_reviewed:
                    continue

                filtered_indices.append(i)

            self._visible_indices = filtered_indices

        # 排序
        if sort_col != -1:
            reverse = sort_order == Qt.DescendingOrder

            key_func = None

            if sort_col in {1, 5}:  # Status / Reviewed
                # 优先按权重排序，次级按行号
                def key_func(i):
                    return (data[i].sort_weight, data[i].line_num_in_file)
            elif sort_col == 2:  # Original

                def key_func(i):
                    return data[i].original_semantic.lower()
            elif sort_col == 3:  # Translation

                def key_func(i):
                    return data[i].translation.lower()
            elif sort_col == 4:  # Comment

                def key_func(i):
                    return data[i].comment.lower()
            elif sort_col == 6:  # Line

                def key_func(i):
                    return data[i].line_num_in_file
            else:  # ID (0)

                def key_func(i):
                    return data[i].line_num_in_file

            if key_func:
                self._visible_indices.sort(key=key_func, reverse=reverse)

        self._raw_to_visual_map = {raw_idx: visual_idx for visual_idx, raw_idx in enumerate(self._visible_indices)}
        self.endResetModel()

    # --- 辅助方法 ---

    def get_ts_object_by_visual_row(self, row):
        """获取当前视图第 row 行对应的对象"""
        if 0 <= row < len(self._visible_indices):
            raw_index = self._visible_indices[row]
            return self._all_data[raw_index]
        return None

    def get_visual_row_by_id(self, ts_id):
        raw_index = self._id_to_raw_index_map.get(ts_id)
        if raw_index is None:
            return -1

        try:
            return self._visible_indices.index(raw_index)
        except ValueError:
            return -1

    def get_visual_row_by_raw_index(self, raw_index):
        return self._raw_to_visual_map.get(raw_index, -1)

    def get_raw_index_by_id(self, ts_id):
        return self._id_to_raw_index_map.get(ts_id)
