# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import re
import os
import shutil
import datetime
from models.translatable_string import TranslatableString


def unescape_overwatch_string(s):
    res = []
    i = 0
    while i < len(s):
        if s[i] == '\\':
            if i + 1 < len(s):
                char_after_backslash = s[i + 1]
                if char_after_backslash == 'n':
                    res.append('\n')
                elif char_after_backslash == 't':
                    res.append('\t')
                elif char_after_backslash == '"':
                    res.append('"')
                elif char_after_backslash == '\\':
                    res.append('\\')
                else:
                    res.append('\\');
                    res.append(char_after_backslash)
                i += 2
            else:
                res.append('\\');
                i += 1
        else:
            res.append(s[i]);
            i += 1
    return "".join(res)


def extract_translatable_strings(code_content, extraction_patterns):
    strings = []
    full_code_lines = code_content.splitlines()

    regex_all_digits = re.compile(r'^\d+$')
    regex_ow_placeholder = re.compile(r'^\{\d+\}$')
    allowed_symbols_and_whitespace_chars = r".,?!|:;\-_+=*/%&#@$^~`<>(){}\[\]\s"
    regex_only_symbols_and_whitespace = re.compile(f"^[{re.escape(allowed_symbols_and_whitespace_chars)}]+$")
    regex_placeholder_like = re.compile(r'\{\d+\}')
    regex_repeating_char = re.compile(r"^(.)\1{1,}$")
    regex_progress_bar_like = re.compile(r"^[\[\(\|\-=<>#\s]*[\]\s]*$")
    known_untranslatable_short_words = {
        "ID", "HP", "MP", "XP", "LV", "CD", "UI", "OK",
        "X", "Y", "Z", "A", "B", "C", "N/A"
    }

    for pattern_config in extraction_patterns:
        if not pattern_config.get("enabled", True):
            continue

        pattern_name = pattern_config.get("name", "Unknown Pattern")
        left_delimiter_str = pattern_config.get("left_delimiter")
        right_delimiter_str = pattern_config.get("right_delimiter")
        string_type_from_pattern = pattern_config.get("string_type", "Custom")

        if not left_delimiter_str or not right_delimiter_str:
            continue

        try:
            full_regex_str = f"({left_delimiter_str})(.*?)({right_delimiter_str})"
            compiled_pattern = re.compile(full_regex_str, re.DOTALL)
        except re.error as e:
            print(f"Warning: Invalid regex for pattern '{pattern_name}': {e}. Skipping.")
            continue

        for match in compiled_pattern.finditer(code_content):
            raw_content = match.group(2)

            semantic_content = unescape_overwatch_string(raw_content)

            content_start_pos = match.start(2)
            content_end_pos = match.end(2)

            line_num = code_content.count('\n', 0, content_start_pos) + 1

            ts = TranslatableString(
                original_raw=raw_content,
                original_semantic=semantic_content,
                line_num=line_num,
                char_pos_start_in_file=content_start_pos,
                char_pos_end_in_file=content_end_pos,
                full_code_lines=full_code_lines,
                string_type=string_type_from_pattern
            )

            if string_type_from_pattern and string_type_from_pattern not in ["Custom String", "Custom", ""]:
                ts.comment = string_type_from_pattern

            s_semantic_stripped = semantic_content.strip()
            s_len_stripped = len(s_semantic_stripped)

            if not s_semantic_stripped:
                ts.was_auto_ignored = True;
                ts.is_ignored = True
            elif regex_all_digits.fullmatch(s_semantic_stripped):
                ts.was_auto_ignored = True;
                ts.is_ignored = True
            elif regex_ow_placeholder.fullmatch(s_semantic_stripped):
                ts.was_auto_ignored = True;
                ts.is_ignored = True
            elif s_len_stripped == 1 and 'a' <= s_semantic_stripped.lower() <= 'z' and s_semantic_stripped.isascii():
                ts.was_auto_ignored = True;
                ts.is_ignored = True
            elif regex_only_symbols_and_whitespace.fullmatch(semantic_content):
                ts.was_auto_ignored = True;
                ts.is_ignored = True
            elif s_len_stripped >= 2 and regex_repeating_char.fullmatch(s_semantic_stripped):
                ts.was_auto_ignored = True;
                ts.is_ignored = True
            elif s_semantic_stripped.upper() in known_untranslatable_short_words:
                ts.was_auto_ignored = True;
                ts.is_ignored = True
            elif s_len_stripped > 2 and regex_progress_bar_like.fullmatch(s_semantic_stripped):
                ts.was_auto_ignored = True;
                ts.is_ignored = True
            else:
                if regex_placeholder_like.search(s_semantic_stripped):
                    content_no_placeholders = regex_placeholder_like.sub('', s_semantic_stripped)
                    content_text_only = re.sub(f"[{re.escape(allowed_symbols_and_whitespace_chars)}]", '',
                                               content_no_placeholders).strip()
                    if len(content_text_only) < 2:
                        ts.was_auto_ignored = True;
                        ts.is_ignored = True

            strings.append(ts)

    strings.sort(key=lambda s: s.char_pos_start_in_file)
    return strings


def save_translated_code(filepath_to_save, original_raw_code_content, translatable_objects, app_instance):
    content_chars = list(original_raw_code_content)
    sorted_ts_objects = sorted(translatable_objects, key=lambda ts: ts.char_pos_start_in_file, reverse=True)

    for ts_obj in sorted_ts_objects:
        if ts_obj.translation and not ts_obj.is_ignored:
            start_idx = ts_obj.char_pos_start_in_file
            end_idx_of_content_to_replace = ts_obj.char_pos_end_in_file
            raw_translated_str_for_code = ts_obj.get_raw_translated_for_code()
            content_chars[start_idx: end_idx_of_content_to_replace] = list(raw_translated_str_for_code)

    final_content = "".join(content_chars)

    if os.path.exists(filepath_to_save):
        backup_path = filepath_to_save + ".bak." + datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        try:
            shutil.copy2(filepath_to_save, backup_path)
            app_instance.update_statusbar(f"已创建备份: {os.path.basename(backup_path)}")
        except Exception as e_backup:
            from tkinter import messagebox
            if app_instance and app_instance.root:
                messagebox.showwarning("备份失败",
                                       f"无法创建代码文件备份 '{os.path.basename(backup_path)}': {e_backup}",
                                       parent=app_instance.root)
            else:
                print(f"备份失败: {e_backup}")

    with open(filepath_to_save, 'w', encoding='utf-8') as f:
        f.write(final_content)