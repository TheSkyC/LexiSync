# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import uuid
from PySide6.QtGui import QColor, QFont
from utils.constants import APP_NAMESPACE_UUID, MAX_UNDO_HISTORY
from utils.localization import _

class TranslatableString:
    def __init__(self, original_raw, original_semantic, line_num, char_pos_start_in_file, char_pos_end_in_file,
                 full_code_lines, string_type="Custom String"):
        name_string_for_uuid = f"{original_semantic}::{string_type}::L{line_num}::C{char_pos_start_in_file}"
        self.id = str(uuid.uuid5(APP_NAMESPACE_UUID, name_string_for_uuid))
        self.original_raw = original_raw
        self.original_semantic = original_semantic
        self.translation = ""
        self.is_ignored = False
        self.was_auto_ignored = False
        self.line_num_in_file = line_num
        self.char_pos_start_in_file = char_pos_start_in_file
        self.char_pos_end_in_file = char_pos_end_in_file
        self.warnings = []
        self.minor_warnings = []
        self.is_warning_ignored = False

        self.string_type = string_type
        self.source_comment = ""
        self.comment = ""
        self.is_reviewed = False
        self.is_fuzzy = False
        self.po_comment = ""
        self.ui_style_cache = {}

        context_radius = 2
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
        return {
            'id': self.id,
            'original_raw': self.original_raw,
            'original_semantic': self.original_semantic,
            'translation': self.translation,
            'is_ignored': self.is_ignored,
            'was_auto_ignored': self.was_auto_ignored,
            'line_num_in_file': self.line_num_in_file,
            'char_pos_start_in_file': self.char_pos_start_in_file,
            'char_pos_end_in_file': self.char_pos_end_in_file,
            'string_type': self.string_type,
            'comment': self.comment,
            'is_reviewed': self.is_reviewed,
            'is_fuzzy': self.is_fuzzy,
            'po_comment': self.po_comment,
            '_translation_edit_history': self._translation_edit_history,
            '_translation_history_pointer': self._translation_history_pointer,
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
            string_type=data.get('string_type', "Custom String")
        )
        ts.id = data['id']
        ts.translation = data.get('translation', "")
        ts.is_ignored = data.get('is_ignored', False)
        ts.was_auto_ignored = data.get('was_auto_ignored', False)
        ts.comment = data.get('comment', "")
        ts.is_reviewed = data.get('is_reviewed', False)
        ts.is_fuzzy = data.get('is_fuzzy', False)
        ts.po_comment = data.get('po_comment', "")
        ts._translation_edit_history = data.get('_translation_edit_history', [ts.translation])
        ts._translation_history_pointer = data.get('_translation_history_pointer',
                                                   len(ts._translation_edit_history) - 1 if ts._translation_edit_history else 0)
        return ts


    def update_style_cache(self, all_strings_map=None):
        self.ui_style_cache = {}
        if self.is_fuzzy:
            if _("Translation is marked as fuzzy and needs review.") not in self.minor_warnings:
                 self.minor_warnings.append(_("Translation is marked as fuzzy and needs review."))
        else:
            try:
                self.minor_warnings.remove(_("Translation is marked as fuzzy and needs review."))
            except ValueError:
                pass # 如果警告不存在，就什么都不做
        if self.warnings and not self.is_warning_ignored:
            self.ui_style_cache['background'] = QColor("#FFDDDD")
            self.ui_style_cache['foreground'] = QColor("red")
        elif self.minor_warnings and not self.is_warning_ignored:
            self.ui_style_cache['background'] = QColor("#FFFACD")
        elif self.is_ignored:
            self.ui_style_cache['background'] = QColor("#F0F0F0")
            self.ui_style_cache['foreground'] = QColor("#707070")
            font = QFont()
            font.setItalic(True)
            self.ui_style_cache['font'] = font
        elif self.translation.strip():
            if self.is_reviewed:
                self.ui_style_cache['foreground'] = QColor("darkgreen")
            else:
                self.ui_style_cache['foreground'] = QColor("darkblue")
        else:
            self.ui_style_cache['foreground'] = QColor("darkred")

        original_has_newline = '\n' in self.original_semantic
        translation_has_newline = '\n' in self.translation

        if original_has_newline or translation_has_newline:
            if original_has_newline and translation_has_newline:
                self.ui_style_cache['newline_color'] = QColor(34, 177, 76, 180)  # Green
            else:
                self.ui_style_cache['newline_color'] = QColor(237, 28, 36, 180)  # Red