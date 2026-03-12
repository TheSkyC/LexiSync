# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from bisect import bisect_left
import datetime
import logging
import os
import re
import shutil

from lexisync.models.translatable_string import TranslatableString
from lexisync.utils.file_utils import atomic_open
from lexisync.utils.localization import _

logger = logging.getLogger(__name__)

_REGEX_ALL_DIGITS = re.compile(r"^\d+$")
_REGEX_OW_PLACEHOLDER = re.compile(r"^\{\d+}$")
_ALLOWED_SYMBOLS_CHARS = r".,?!|:;\-_+=*/%&#@$^~`<>(){}\[\]\s"
_REGEX_ONLY_SYMBOLS_AND_WHITESPACE = re.compile(f"^[{re.escape(_ALLOWED_SYMBOLS_CHARS)}]+$")
_REGEX_PLACEHOLDER_LIKE = re.compile(r"\{\d+}")
_REGEX_REPEATING_CHAR = re.compile(r"^(.)\1+$")
_REGEX_PROGRESS_BAR_LIKE = re.compile(r"^[\[(|\-=<>#\s]*[]\s]*$")
_REGEX_NEWLINES = re.compile(r"\n")

_SYMBOL_REMOVAL_TABLE = str.maketrans("", "", _ALLOWED_SYMBOLS_CHARS)

_KNOWN_UNTRANSLATABLE_SHORT_WORDS = frozenset(
    {"ID", "HP", "MP", "XP", "LV", "CD", "UI", "OK", "X", "Y", "Z", "A", "B", "C", "N/A"}
)

_ESCAPE_DICT = {"n": "\n", "r": "\n", "t": "\t", '"': '"', "\\": "\\"}
_REGEX_ESCAPE = re.compile(r"\\(.)")


def unescape_overwatch_string(s):
    if "\\" not in s:
        return s

    return _REGEX_ESCAPE.sub(lambda m: _ESCAPE_DICT.get(m.group(1), f"\\{m.group(1)}"), s)


def _is_auto_ignorable(s_semantic_stripped: str, semantic_content: str) -> bool:
    """判断字符串是否应被自动忽略。按计算成本从低到高排列短路条件。"""
    s_len_stripped = len(s_semantic_stripped)

    if not s_semantic_stripped:
        return True
    # 纯英文字母
    if s_len_stripped == 1 and s_semantic_stripped.isascii() and s_semantic_stripped.isalpha():
        return True
    if s_len_stripped <= 3 and s_semantic_stripped.upper() in _KNOWN_UNTRANSLATABLE_SHORT_WORDS:
        return True

    # 正则全匹配
    if _REGEX_ALL_DIGITS.fullmatch(s_semantic_stripped):
        return True
    if _REGEX_OW_PLACEHOLDER.fullmatch(s_semantic_stripped):
        return True
    if _REGEX_ONLY_SYMBOLS_AND_WHITESPACE.fullmatch(semantic_content):
        return True
    if s_len_stripped >= 2 and _REGEX_REPEATING_CHAR.fullmatch(s_semantic_stripped):
        return True
    if s_len_stripped > 2 and _REGEX_PROGRESS_BAR_LIKE.fullmatch(s_semantic_stripped):
        return True

    # 占位符检查及替换
    if _REGEX_PLACEHOLDER_LIKE.search(s_semantic_stripped):
        content_no_placeholders = _REGEX_PLACEHOLDER_LIKE.sub("", s_semantic_stripped)
        content_text_only = content_no_placeholders.translate(_SYMBOL_REMOVAL_TABLE).strip()
        if len(content_text_only) < 2:
            return True

    return False


def extract_translatable_strings(code_content, extraction_patterns, source_file_rel_path="", app_instance=None):
    newline_indices = [m.start() for m in _REGEX_NEWLINES.finditer(code_content)]

    occupied_mask = bytearray(len(code_content))
    mv_occupied = memoryview(occupied_mask)

    strings = []
    full_code_lines = code_content.splitlines()
    occurrence_counters = {}

    fill_enabled = bool(
        app_instance
        and hasattr(app_instance, "config")
        and app_instance.config.get("fill_translation_with_source", False)
    )

    for pattern_config in extraction_patterns:
        if not pattern_config.get("enabled", True):
            continue

        pattern_name = pattern_config.get("name", "Unknown Pattern")
        left_delimiter_str = pattern_config.get("left_delimiter")
        right_delimiter_str = pattern_config.get("right_delimiter")
        string_type = pattern_config.get("string_type", "Custom String")
        is_multiline = pattern_config.get("multiline", True)
        desc_from_pattern = pattern_config.get("description", "")

        if not left_delimiter_str or not right_delimiter_str:
            continue

        try:
            full_regex_str = f"({left_delimiter_str})(.*?)({right_delimiter_str})"
            flags = re.DOTALL if is_multiline else 0
            compiled_pattern = re.compile(full_regex_str, flags)
        except re.error as e:
            logger.warning(f"Warning: Invalid regex for pattern '{pattern_name}': {e}. Skipping.")
            continue

        for match in compiled_pattern.finditer(code_content):
            content_start_pos = match.start(2)
            content_end_pos = match.end(2)

            if b"\x01" in mv_occupied[content_start_pos:content_end_pos]:
                continue

            # 标记区间已占用
            occupied_mask[content_start_pos:content_end_pos] = b"\x01" * (content_end_pos - content_start_pos)

            raw_content = match.group(2)
            line_num = bisect_left(newline_indices, content_start_pos) + 1
            semantic_content = unescape_overwatch_string(raw_content)

            counter_key = (semantic_content, string_type)
            current_index = occurrence_counters.get(counter_key, 0)
            occurrence_counters[counter_key] = current_index + 1

            ts = TranslatableString(
                original_raw=raw_content,
                original_semantic=semantic_content,
                line_num=line_num,
                char_pos_start_in_file=content_start_pos,
                char_pos_end_in_file=content_end_pos,
                full_code_lines=full_code_lines,
                string_type=string_type,
                source_file_path=source_file_rel_path,
                occurrences=[(source_file_rel_path, str(line_num))],
                occurrence_index=current_index,
            )

            if fill_enabled:
                ts.set_translation_internal(semantic_content, is_initial=True)

            if desc_from_pattern:
                ts.comment = desc_from_pattern

            s_semantic_stripped = semantic_content.strip()
            if _is_auto_ignorable(s_semantic_stripped, semantic_content):
                ts.was_auto_ignored = True
                ts.is_ignored = True

            ts.update_sort_weight()
            strings.append(ts)

    # 按文件位置排序
    strings.sort(key=lambda s: s.char_pos_start_in_file)
    return strings


def save_translated_code(filepath_to_save, original_raw_code_content, translatable_objects, app_instance):
    sorted_ts_objects = sorted(
        translatable_objects,
        key=lambda ts: ts.char_pos_start_in_file,
    )

    # 过滤出需要替换的对象（有翻译且未忽略）
    to_replace = [ts for ts in sorted_ts_objects if ts.translation and not ts.is_ignored]

    if not to_replace:
        final_content = original_raw_code_content
    else:
        parts = []
        prev_end = 0
        for ts_obj in to_replace:
            start_idx = ts_obj.char_pos_start_in_file
            end_idx = ts_obj.char_pos_end_in_file
            if start_idx < prev_end:
                # 理论上不应发生区间重叠，发生则跳过
                continue
            parts.append(original_raw_code_content[prev_end:start_idx])
            parts.append(ts_obj.get_raw_translated_for_code())
            prev_end = end_idx

        parts.append(original_raw_code_content[prev_end:])
        final_content = "".join(parts)

    if os.path.exists(filepath_to_save):
        backup_path = filepath_to_save + ".bak." + datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        try:
            shutil.copy2(filepath_to_save, backup_path)
            app_instance.update_statusbar(
                _("Backup created: {filename}").format(filename=os.path.basename(backup_path))
            )
        except Exception as e_backup:
            from PySide6.QtWidgets import QMessageBox

            if app_instance and app_instance.isVisible():
                QMessageBox.warning(
                    app_instance,
                    _("Backup Failed"),
                    _("Could not create code file backup '{filename}': {error}").format(
                        filename=os.path.basename(backup_path), error=e_backup
                    ),
                )
            else:
                logger.warning(f"Backup Failed: {e_backup}")

    with atomic_open(filepath_to_save, "w", encoding="utf-8") as f:
        f.write(final_content)
