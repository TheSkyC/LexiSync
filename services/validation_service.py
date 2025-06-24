# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import re
import os
from utils.localization import _

placeholder_regex = re.compile(r'\{([^{}]+)\}')


def has_case(char):
    return char.lower() != char.upper()


def get_starting_cased_char(s):
    stripped_s = s.lstrip()
    if stripped_s:
        first_char = stripped_s[0]
        if has_case(first_char):
            return first_char
    return None


def validate_string(ts_obj):
    if not ts_obj.translation or ts_obj.is_ignored:
        ts_obj.warnings = []
        ts_obj.minor_warnings = []
        return

    warnings = []
    minor_warnings = []
    original = ts_obj.original_semantic
    translation = ts_obj.translation

    # 严重警告：占位符不匹配
    original_placeholders = set(placeholder_regex.findall(original))
    translated_placeholders = set(placeholder_regex.findall(translation))
    if original_placeholders != translated_placeholders:
        missing = original_placeholders - translated_placeholders
        extra = translated_placeholders - original_placeholders
        warning_msg = _("Placeholder mismatch.")
        if missing:
            warning_msg += f" " + _("Missing:") + f" {', '.join(missing)}."
        if extra:
            warning_msg += f" " + _("Extra:") + f" {', '.join(extra)}."
        warnings.append(warning_msg)

    # 严重警告：换行符数量不匹配
    if original.count('\n') != translation.count('\n'):
        warnings.append(_("Line count differs from original."))

    # 严重警告：首尾空格不匹配
    if (original.startswith(' ') and not translation.startswith(' ')) or \
            (not original.startswith(' ') and translation.startswith(' ')):
        warnings.append(_("Leading whitespace mismatch."))
    if (original.endswith(' ') and not translation.endswith(' ')) or \
            (not original.endswith(' ') and translation.endswith(' ')):
        warnings.append(_("Trailing whitespace mismatch."))

    # 严重警告：首尾标点不匹配
    punctuation_map = {'.': '。', '。': '.', ',': '，', '，': ',', '?': '？', '？': '?', '!': '！', '！': '!', ':': '：', '：': ':', ';': '；', '；': ';', '(': '（', '（': '(', ')': '）', '）': ')'}
    all_punc = set(punctuation_map.keys()).union(set(punctuation_map.values()))
    original_stripped = original.strip()
    translation_stripped = translation.strip()

    def is_punc(char):
        return char in all_punc

    def are_equivalent(char1, char2):
        return char1 == char2 or punctuation_map.get(char1) == char2 or punctuation_map.get(char2) == char1

    if original_stripped and translation_stripped:
        start_orig_char, start_trans_char = original_stripped[0], translation_stripped[0]
        if is_punc(start_orig_char) != is_punc(start_trans_char) or (
                is_punc(start_orig_char) and not are_equivalent(start_orig_char, start_trans_char)):
            warnings.append(_("Starting punctuation mismatch."))

        end_orig_char, end_trans_char = original_stripped[-1], translation_stripped[-1]
        if is_punc(end_orig_char) != is_punc(end_trans_char) or (
                is_punc(end_orig_char) and not are_equivalent(end_orig_char, end_trans_char)):
            warnings.append(_("Ending punctuation mismatch."))

    # 严重警告：首字母大小写不匹配
    common_prefix = os.path.commonprefix([original, translation])
    core_original = original[len(common_prefix):]
    core_translation = translation[len(common_prefix):]
    first_char_original = get_starting_cased_char(core_original)
    first_char_translation = get_starting_cased_char(core_translation)
    if first_char_original and first_char_translation and (
            first_char_original.isupper() != first_char_translation.isupper()):
        warnings.append(_("Initial capitalization mismatch."))

    # 次级警告：fuzzy 标记
    if ts_obj.is_fuzzy:
        minor_warnings.append(_("Translation is marked as fuzzy and needs review."))

    ts_obj.warnings = warnings
    ts_obj.minor_warnings = minor_warnings

    if original_stripped and translation_stripped:
        start_orig_char = original_stripped[0]
        start_trans_char = translation_stripped[0]
        orig_starts_with_punc = is_punc(start_orig_char)
        trans_starts_with_punc = is_punc(start_trans_char)
        if orig_starts_with_punc and not trans_starts_with_punc:
            minor_warnings.append(_("Original starts with '{char}', but translation does not start with punctuation.").format(
                char=start_orig_char))
        elif not orig_starts_with_punc and trans_starts_with_punc:
            minor_warnings.append(_("Translation starts with '{char}', but original does not start with punctuation.").format(
                char=start_trans_char))
        elif orig_starts_with_punc and trans_starts_with_punc and not are_equivalent(start_orig_char, start_trans_char):
            minor_warnings.append(_("Starting punctuation mismatch: '{char1}' vs '{char2}'.").format(char1=start_orig_char,
                                                                                               char2=start_trans_char))

    if original_stripped and translation_stripped:
        end_orig_char = original_stripped[-1]
        end_trans_char = translation_stripped[-1]
        orig_ends_with_punc = is_punc(end_orig_char)
        trans_ends_with_punc = is_punc(end_trans_char)
        if orig_ends_with_punc and not trans_ends_with_punc:
            minor_warnings.append(_("Original ends with '{char}', but translation does not end with punctuation.").format(
                char=end_orig_char))
        elif not orig_ends_with_punc and trans_ends_with_punc:
            minor_warnings.append(_("Translation ends with '{char}', but original does not end with punctuation.").format(
                char=end_trans_char))
        elif orig_ends_with_punc and trans_ends_with_punc and not are_equivalent(end_orig_char, end_trans_char):
            minor_warnings.append(_("Ending punctuation mismatch: '{char1}' vs '{char2}'.").format(char1=end_orig_char,
                                                                                             char2=end_trans_char))

    common_prefix = os.path.commonprefix([original, translation])
    core_original = original[len(common_prefix):]
    core_translation = translation[len(common_prefix):]
    first_char_original = get_starting_cased_char(core_original)
    first_char_translation = get_starting_cased_char(core_translation)

    if first_char_original and first_char_translation:
        if first_char_original.isupper() != first_char_translation.isupper():
            minor_warnings.append(_("Initial capitalization mismatch."))

    ts_obj.warnings = warnings
    ts_obj.minor_warnings = minor_warnings
    return warnings + minor_warnings

def run_validation_on_all(translatable_objects):
    for ts_obj in translatable_objects:
        validate_string(ts_obj)