# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import hashlib
from PySide6.QtGui import QColor, QFont
from utils.constants import APP_NAMESPACE_UUID, MAX_UNDO_HISTORY
from utils.localization import _
from utils.enums import WarningType
import logging
logger = logging.getLogger(__name__)


class TranslatableString:
    def __init__(self, original_raw, original_semantic, line_num, char_pos_start_in_file, char_pos_end_in_file,
                 full_code_lines, string_type="Custom String", source_file_path="", occurrences=None, occurrence_index=0):
        name_string_for_uuid = f"{source_file_path}::{original_semantic}::{string_type}::{str(occurrence_index)}"
        self.id = hashlib.md5(name_string_for_uuid.encode('utf-8')).hexdigest()
        self.context = ""
        self.original_raw = original_raw
        self.original_semantic = original_semantic
        self.translation = ""
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

        self.ui_style_cache = {}
        context_radius = 5
        start_line_idx = max(0, line_num - 1 - context_radius)
        current_line_content_idx = line_num - 1
        if full_code_lines:
            self.context_lines = full_code_lines[
                                 start_line_idx: min(len(full_code_lines),
                                                     current_line_content_idx + context_radius + 1)]
            self.current_line_in_context_idx = current_line_content_idx - start_line_idx
        else:
            self.context_lines = []
            self.current_line_in_context_idx = -1
        self._translation_edit_history = [self.translation]
        self._translation_history_pointer = 0

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

    def set_translation_internal(self, text_with_newlines):
        if text_with_newlines == self.translation:
            return
        self.translation = text_with_newlines
        if self._translation_history_pointer < len(self._translation_edit_history) - 1:
            self._translation_edit_history = self._translation_edit_history[:self._translation_history_pointer + 1]
        self._translation_edit_history.append(self.translation)
        if len(self._translation_edit_history) > MAX_UNDO_HISTORY * 2:
            self._translation_edit_history.pop(0)
        self._translation_history_pointer = len(self._translation_edit_history) - 1

    def get_translation_for_ui(self):
        return self.translation

    def get_translation_for_storage_and_tm(self):
        return self.translation.replace("\n", "\\n")

    def get_raw_translated_for_code(self):
        return self.translation.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')

    def to_dict(self):
        serializable_warnings = [(wt.name, msg) for wt, msg in self.warnings]
        serializable_minor_warnings = [(wt.name, msg) for wt, msg in self.minor_warnings]
        serializable_infos = [(wt.name, msg) for wt, msg in self.infos]

        return {
            'id': self.id,
            'original_raw': self.original_raw,
            'original_semantic': self.original_semantic,
            'translation': self.translation,
            'is_ignored': self.is_ignored,
            'was_auto_ignored': self.was_auto_ignored,
            'line_num_in_file': self.line_num_in_file, # Backward compatible
            'source_file_path': self.source_file_path, # Backward compatible
            'occurrences': self.occurrences,
            'char_pos_start_in_file': self.char_pos_start_in_file,
            'char_pos_end_in_file': self.char_pos_end_in_file,
            'string_type': self.string_type,
            'context': self.context,
            'comment': self.comment,
            'is_reviewed': self.is_reviewed,
            'is_fuzzy': self.is_fuzzy,
            'po_comment': self.po_comment,
            'is_warning_ignored': self.is_warning_ignored,
            'warnings': serializable_warnings,
            'minor_warnings': serializable_minor_warnings,
            'infos': serializable_infos,
        }

    @classmethod
    def from_dict(cls, data, full_code_lines_ref):
        ts = cls(
            original_raw=data['original_raw'],
            original_semantic=data['original_semantic'],
            line_num=data['line_num_in_file'],
            char_pos_start_in_file=data['char_pos_start_in_file'],
            char_pos_end_in_file=data['char_pos_end_in_file'],
            full_code_lines=full_code_lines_ref,
            string_type=data.get('string_type', "Custom String"),
            occurrences=data.get('occurrences')
        )
        if not ts.occurrences and 'line_num_in_file' in data: # Backward compatible
            ts.occurrences = [(data.get('source_file_path', ''), str(data['line_num_in_file']))]
        ts.id = data['id']
        ts.translation = data.get('translation', "")
        ts.is_ignored = data.get('is_ignored', False)
        ts.was_auto_ignored = data.get('was_auto_ignored', False)
        ts.context = data.get('context', "")
        ts.comment = data.get('comment', "")
        ts.is_reviewed = data.get('is_reviewed', False)
        ts.is_fuzzy = data.get('is_fuzzy', False)
        ts.po_comment = data.get('po_comment', "")
        ts.is_warning_ignored = data.get('is_warning_ignored', False)
        if 'warnings' in data:
            for wt_name, msg in data['warnings']:
                try:
                    ts.warnings.append((WarningType[wt_name], msg))
                except KeyError:
                    logger.warning(
                        f"Warning: Unknown warning type name '{wt_name}' found in project file for ID {ts.id}. Original message: {msg}")
        if 'minor_warnings' in data:
            for wt_name, msg in data['minor_warnings']:
                try:
                    ts.minor_warnings.append((WarningType[wt_name], msg))
                except KeyError:
                    logger.warning(
                        f"Warning: Unknown minor warning type name '{wt_name}' found in project file for ID {ts.id}. Original message: {msg}")
        if 'infos' in data:
            for wt_name, msg in data['infos']:
                try:
                    ts.infos.append((WarningType[wt_name], msg))
                except KeyError:
                    pass
        return ts

    def update_style_cache(self, all_strings_map=None):
        fuzzy_warning_tuple = (WarningType.FUZZY_TRANSLATION, _("Translation is marked as fuzzy and needs review."))

        has_fuzzy_in_minor_warnings = any(wt == WarningType.FUZZY_TRANSLATION for wt, _ in self.minor_warnings)

        should_have_fuzzy_warning = self.is_fuzzy and self.translation.strip()

        if should_have_fuzzy_warning and not has_fuzzy_in_minor_warnings:
            self.minor_warnings.append(fuzzy_warning_tuple)
        elif not should_have_fuzzy_warning and has_fuzzy_in_minor_warnings:
            self.minor_warnings = [(wt, msg) for wt, msg in self.minor_warnings if wt != WarningType.FUZZY_TRANSLATION]

        self.ui_style_cache = {}

        # 1. 最高优先级：已忽略
        if self.is_ignored:
            # 被忽略，但仍有警告，则特殊显示
            if self.warnings and not self.is_warning_ignored:
                self.ui_style_cache['background'] = QColor(220, 220, 220, 200)
                self.ui_style_cache['foreground'] = QColor(255, 0, 0, 150)
                font = QFont()
                font.setItalic(True)
                self.ui_style_cache['font'] = font
            else:
                # 普通的忽略样式
                self.ui_style_cache['background'] = QColor(220, 220, 220, 200)
                self.ui_style_cache['foreground'] = QColor("#707070")
                font = QFont()
                font.setItalic(True)
                self.ui_style_cache['font'] = font

        # 2. 次高优先级：已审阅
        elif self.is_reviewed:
            self.ui_style_cache['foreground'] = QColor("darkgreen")

        # 3. 严重警告
        elif self.warnings and not self.is_warning_ignored:
                self.ui_style_cache['background'] = QColor("#FFDDDD")  # 浅红色背景
                self.ui_style_cache['foreground'] = QColor("red")  # 红色文字

        # 4. 次级警告
        elif self.minor_warnings and not self.is_warning_ignored:
            self.ui_style_cache['background'] = QColor("#FFFACD")  # 浅黄色背景

        # 5. 普通翻译状态
        elif self.translation.strip():
            self.ui_style_cache['foreground'] = QColor("darkblue")  # 已翻译 - 深蓝色
        else:  # 未翻译
            self.ui_style_cache['foreground'] = QColor("darkred")  # 未翻译 - 暗红色

        original_has_newline = '\n' in self.original_semantic
        translation_has_newline = '\n' in self.translation

        # 换行符
        self.ui_style_cache.pop('original_newline_color', None)
        self.ui_style_cache.pop('translation_newline_color', None)

        if original_has_newline and translation_has_newline:
            # 两者都有，都是绿色
            green_color = QColor(34, 177, 76, 180)
            self.ui_style_cache['original_newline_color'] = green_color
            self.ui_style_cache['translation_newline_color'] = green_color
        elif original_has_newline or translation_has_newline:
            # 只有一个有，哪个有，哪个就是红色
            red_color = QColor(237, 28, 36, 180)
            if original_has_newline:
                self.ui_style_cache['original_newline_color'] = red_color
            if translation_has_newline:
                self.ui_style_cache['translation_newline_color'] = red_color