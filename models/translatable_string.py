# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import logging

from PySide6.QtGui import QColor, QFont
import xxhash

from utils.constants import MAX_UNDO_HISTORY
from utils.enums import WarningType
from utils.localization import _

logger = logging.getLogger(__name__)


class TranslatableString:
    __slots__ = [
        "_display_original",
        "_display_translation",
        "_search_cache",
        "_translation_edit_history",
        "_translation_history_pointer",
        "char_pos_end_in_file",
        "char_pos_start_in_file",
        "comment",
        "context",
        "context_lines",
        "current_line_in_context_idx",
        "id",
        "infos",
        "is_fuzzy",
        "is_ignored",
        "is_plural",
        "is_reviewed",
        "is_warning_ignored",
        "minor_warnings",
        "occurrences",
        "original_plural",
        "original_raw",
        "original_semantic",
        "plural_expr",
        "plural_translations",
        "po_comment",
        "sort_weight",
        "string_type",
        "translation",
        "ui_style_cache",
        "warnings",
        "was_auto_ignored",
    ]

    def __init__(
        self,
        original_raw,
        original_semantic,
        line_num,
        char_pos_start_in_file,
        char_pos_end_in_file,
        full_code_lines,
        string_type="Custom String",
        source_file_path="",
        occurrences=None,
        occurrence_index=0,
        id=None,
    ):
        if id:
            self.id = id
        else:
            name_string_for_uuid = f"{source_file_path}::{original_semantic}::{string_type}::{occurrence_index!s}"
            self.id = xxhash.xxh128(name_string_for_uuid.encode("utf-8")).hexdigest()
        self._search_cache = (original_semantic + " " + string_type).lower()
        self.context = ""
        self.original_raw = original_raw
        self.original_semantic = original_semantic
        self.translation = ""
        self._display_original = self.original_semantic.replace("\n", "↵")
        self._display_translation = ""
        self.is_ignored = False
        self.was_auto_ignored = False
        if occurrences is not None:
            self.occurrences = occurrences
        elif line_num > 0:
            self.occurrences = [(source_file_path, str(line_num))]
        else:
            self.occurrences = []
        self.char_pos_start_in_file = char_pos_start_in_file
        self.char_pos_end_in_file = char_pos_end_in_file
        self.warnings = []
        self.minor_warnings = []
        self.infos = []

        self.is_warning_ignored = False
        self.string_type = string_type
        self.comment = ""
        self.is_reviewed = False
        self.is_fuzzy = False
        self.po_comment = ""

        self.is_plural = False
        self.original_plural = ""
        self.plural_translations = {0: ""}  # Dict[int, str] 存储所有复数形式
        self.plural_expr = None

        self.ui_style_cache = {}
        context_radius = 5
        start_line_idx = max(0, line_num - 1 - context_radius)
        current_line_content_idx = line_num - 1
        if full_code_lines:
            self.context_lines = full_code_lines[
                start_line_idx : min(len(full_code_lines), current_line_content_idx + context_radius + 1)
            ]
            self.current_line_in_context_idx = current_line_content_idx - start_line_idx
        else:
            self.context_lines = []
            self.current_line_in_context_idx = -1
        self._translation_edit_history = [self.translation]
        self._translation_history_pointer = 0

    def update_sort_weight(self):
        """
        Pre-calculates the sort weight based on status.
        Lower number = appears higher in the list when sorting by status.
        Priority:
        0: Error (Warnings present)
        1: Warning (Minor warnings present)
        2: Info
        3: Untranslated
        4: Translated
        5: Reviewed
        6: Ignored
        """
        if self.is_ignored:
            self.sort_weight = 6
            return

        if self.is_reviewed:
            self.sort_weight = 5
            return

        if not self.is_warning_ignored:
            if self.warnings:
                self.sort_weight = 0  # Error
                return
            if self.minor_warnings:
                self.sort_weight = 1  # Warning
                return
            if self.infos:
                self.sort_weight = 2  # Info
                return

        if not self.translation.strip():
            self.sort_weight = 3  # Untranslated
            return

        self.sort_weight = 4  # Translated

    def update_search_cache(self):
        plural_trans_text = ""
        if self.is_plural:
            plural_trans_text = " ".join(self.plural_translations.values())

        orig_plural = self.original_plural if self.is_plural else ""

        search_content = [
            self.original_semantic,
            orig_plural,
            self.translation or "",
            plural_trans_text,
            self.comment or "",
            self.string_type or "",
        ]

        self._search_cache = " ".join(search_content).lower()

    @property
    def line_num_in_file(self):
        try:
            return int(self.occurrences[0][1])
        except (IndexError, ValueError, TypeError):
            return 0

    @property
    def source_file_path(self):
        try:
            return self.occurrences[0][0]
        except IndexError:
            return ""

    @property
    def singular_index(self) -> int:
        from utils.plural_utils import get_singular_index_from_expr

        return get_singular_index_from_expr(self.plural_expr)

    def set_translation_internal(self, text_with_newlines, is_initial=False, plural_index=0):
        """
        设置译文并同步缓存。
        is_initial: 如果为 True，则重置撤销栈，将其设为初始状态。
        """
        if self.is_plural:
            self.plural_translations[plural_index] = text_with_newlines
            # 默认 translation 始终保持与 index 0 同步，用于列表展示
            if plural_index == 0:
                self.translation = text_with_newlines
                self._display_translation = self.translation.replace("\n", "↵")
        else:
            self.translation = text_with_newlines
            self._display_translation = self.translation.replace("\n", "↵")

        if is_initial:
            self._translation_edit_history = [self.translation]
            self._translation_history_pointer = 0
        else:
            if self._translation_history_pointer < len(self._translation_edit_history) - 1:
                self._translation_edit_history = self._translation_edit_history[: self._translation_history_pointer + 1]
            self._translation_edit_history.append(self.translation)
            if len(self._translation_edit_history) > MAX_UNDO_HISTORY * 2:
                self._translation_edit_history.pop(0)
            self._translation_history_pointer = len(self._translation_edit_history) - 1
        self.update_search_cache()

    def get_translation_for_ui(self):
        return self.translation

    def get_translation_for_storage_and_tm(self):
        return self.translation.replace("\n", "\\n")

    def get_raw_translated_for_code(self):
        return self.translation.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

    def to_dict(self):
        serializable_warnings = [(wt.name, msg) for wt, msg in self.warnings]
        serializable_minor_warnings = [(wt.name, msg) for wt, msg in self.minor_warnings]
        serializable_infos = [(wt.name, msg) for wt, msg in self.infos]

        return {
            "id": self.id,
            "original_raw": self.original_raw,
            "original_semantic": self.original_semantic,
            "translation": self.translation,
            "is_ignored": self.is_ignored,
            "was_auto_ignored": self.was_auto_ignored,
            "line_num_in_file": self.line_num_in_file,  # Backward compatible
            "source_file_path": self.source_file_path,  # Backward compatible
            "occurrences": self.occurrences,
            "char_pos_start_in_file": self.char_pos_start_in_file,
            "char_pos_end_in_file": self.char_pos_end_in_file,
            "string_type": self.string_type,
            "context": self.context,
            "comment": self.comment,
            "is_reviewed": self.is_reviewed,
            "is_fuzzy": self.is_fuzzy,
            "po_comment": self.po_comment,
            "is_warning_ignored": self.is_warning_ignored,
            "warnings": serializable_warnings,
            "minor_warnings": serializable_minor_warnings,
            "infos": serializable_infos,
            "is_plural": self.is_plural,
            "original_plural": self.original_plural,
            "plural_translations": self.plural_translations,
        }

    @classmethod
    def from_dict(cls, data, full_code_lines_ref):
        ts = cls(
            original_raw=data["original_raw"],
            original_semantic=data["original_semantic"],
            line_num=data["line_num_in_file"],
            char_pos_start_in_file=data["char_pos_start_in_file"],
            char_pos_end_in_file=data["char_pos_end_in_file"],
            full_code_lines=full_code_lines_ref,
            string_type=data.get("string_type", "Custom String"),
            occurrences=data.get("occurrences"),
        )
        if not ts.occurrences and "line_num_in_file" in data:  # Backward compatible
            ts.occurrences = [(data.get("source_file_path", ""), str(data["line_num_in_file"]))]
        ts.id = data["id"]
        ts.set_translation_internal(data.get("translation", ""), is_initial=True)
        ts.is_ignored = data.get("is_ignored", False)
        ts.was_auto_ignored = data.get("was_auto_ignored", False)
        ts.context = data.get("context", "")
        ts.comment = data.get("comment", "")
        ts.is_reviewed = data.get("is_reviewed", False)
        ts.is_fuzzy = data.get("is_fuzzy", False)
        ts.po_comment = data.get("po_comment", "")
        ts.is_warning_ignored = data.get("is_warning_ignored", False)

        ts.is_plural = data.get("is_plural", False)
        ts.original_plural = data.get("original_plural", "")
        saved_plurals = data.get("plural_translations", {0: data.get("translation", "")})
        ts.plural_translations = {int(k): v for k, v in saved_plurals.items()}

        if "warnings" in data:
            for wt_name, msg in data["warnings"]:
                try:
                    ts.warnings.append((WarningType[wt_name], msg))
                except KeyError:
                    logger.warning(
                        f"Warning: Unknown warning type name '{wt_name}' found in project file for ID {ts.id}. Original message: {msg}"
                    )
        if "minor_warnings" in data:
            for wt_name, msg in data["minor_warnings"]:
                try:
                    ts.minor_warnings.append((WarningType[wt_name], msg))
                except KeyError:
                    logger.warning(
                        f"Warning: Unknown minor warning type name '{wt_name}' found in project file for ID {ts.id}. Original message: {msg}"
                    )
        if "infos" in data:
            for wt_name, msg in data["infos"]:
                try:
                    ts.infos.append((WarningType[wt_name], msg))
                except KeyError:
                    pass
        ts.update_search_cache()
        return ts

    def update_style_cache(self, all_strings_map=None):
        self.update_sort_weight()

        fuzzy_warning_tuple = (WarningType.FUZZY_TRANSLATION, _("Translation is marked as fuzzy and needs review."))

        has_fuzzy_in_minor_warnings = any(wt == WarningType.FUZZY_TRANSLATION for wt, _ in self.minor_warnings)

        should_have_fuzzy_warning = self.is_fuzzy and self.translation.strip() and not self.is_ignored

        if should_have_fuzzy_warning and not has_fuzzy_in_minor_warnings:
            self.minor_warnings.append(fuzzy_warning_tuple)
        elif not should_have_fuzzy_warning and has_fuzzy_in_minor_warnings:
            self.minor_warnings = [(wt, msg) for wt, msg in self.minor_warnings if wt != WarningType.FUZZY_TRANSLATION]

        self.ui_style_cache = {}

        # 1. 已忽略
        if self.is_ignored:
            self.ui_style_cache["background"] = QColor(220, 220, 220, 200)
            self.ui_style_cache["foreground"] = QColor("#707070")
            font = QFont()
            font.setItalic(True)
            self.ui_style_cache["font"] = font

        # 2. 已审阅 (绿色背景，黑色字)
        elif self.is_reviewed:
            self.ui_style_cache["background"] = QColor("#E8F5E9")
            self.ui_style_cache["foreground"] = QColor("#000000")

        # 3. 严重错误 (红色背景，红色字)
        elif self.warnings and not self.is_warning_ignored:
            self.ui_style_cache["background"] = QColor("#FFDDDD")
            self.ui_style_cache["foreground"] = QColor("#D32F2F")

        # 4. 次级警告 (黄色背景，黑色字)
        elif self.minor_warnings and not self.is_warning_ignored:
            self.ui_style_cache["background"] = QColor("#FFFACD")
            self.ui_style_cache["foreground"] = QColor("#000000")

        # 5. 未翻译 (透明背景，暗红色字)
        elif not self.translation.strip():
            self.ui_style_cache["foreground"] = QColor("darkred")

        # 6. 普通已翻译 (透明背景，黑色字)
        else:
            self.ui_style_cache["foreground"] = QColor("#000000")

        # 换行符
        orig_nl_count = self.original_semantic.count("\n")
        trans_nl_count = self.translation.count("\n")

        self.ui_style_cache.pop("original_newline_color", None)
        self.ui_style_cache.pop("translation_newline_color", None)

        if orig_nl_count > 0 or trans_nl_count > 0:
            if orig_nl_count == trans_nl_count:
                # 数量严致 -> 绿色
                green_color = QColor(34, 177, 76, 180)
                if orig_nl_count > 0:
                    self.ui_style_cache["original_newline_color"] = green_color
                if trans_nl_count > 0:
                    self.ui_style_cache["translation_newline_color"] = green_color
            else:
                # 数量不一致 -> 红色
                red_color = QColor(237, 28, 36, 180)
                if orig_nl_count > 0:
                    self.ui_style_cache["original_newline_color"] = red_color
                if trans_nl_count > 0:
                    self.ui_style_cache["translation_newline_color"] = red_color
