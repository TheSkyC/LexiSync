# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import re
import os
from utils.localization import _
from utils.enums import WarningType

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
    # 清空旧的警告
    ts_obj.warnings = []
    ts_obj.minor_warnings = [(wt, msg) for wt, msg in ts_obj.minor_warnings if wt == WarningType.FUZZY_TRANSLATION]

    if not ts_obj.translation or ts_obj.is_ignored:
        return

    original = ts_obj.original_semantic
    translation = ts_obj.translation

    # 占位符检查
    original_placeholders = set(placeholder_regex.findall(original))
    translated_placeholders = set(placeholder_regex.findall(translation))
    missing_placeholders = original_placeholders - translated_placeholders
    extra_placeholders = translated_placeholders - original_placeholders

    if missing_placeholders:
        ts_obj.warnings.append((WarningType.PLACEHOLDER_MISSING,
                                _("Missing placeholders: {placeholders}").format(
                                    placeholders=", ".join(missing_placeholders))))
    if extra_placeholders:
        ts_obj.warnings.append((WarningType.PLACEHOLDER_EXTRA,
                                _("Extra placeholders: {placeholders}").format(
                                    placeholders=", ".join(extra_placeholders))))

    # 换行符数量
    if original.count('\n') != translation.count('\n'):
        ts_obj.warnings.append((WarningType.LINE_COUNT_MISMATCH, _("Line count differs from original.")))

    # 首尾空格
    if original.startswith(' ') and not translation.startswith(' '):
        ts_obj.warnings.append(
            (WarningType.LEADING_WHITESPACE_MISMATCH, _("Original starts with space, translation does not.")))
    elif not original.startswith(' ') and translation.startswith(' '):
        ts_obj.warnings.append(
            (WarningType.LEADING_WHITESPACE_MISMATCH, _("Translation starts with space, original does not.")))

    if original.endswith(' ') and not translation.endswith(' '):
        ts_obj.warnings.append(
            (WarningType.TRAILING_WHITESPACE_MISMATCH, _("Original ends with space, translation does not.")))
    elif not original.endswith(' ') and translation.endswith(' '):
        ts_obj.warnings.append(
            (WarningType.TRAILING_WHITESPACE_MISMATCH, _("Translation ends with space, original does not.")))

    # 首尾标点
    punctuation_map = {'.': '。', ',': '，', '?': '？', '!': '！', ':': '：', ';': '；', '(': '（', ')': '）'}
    all_punc_keys = list(punctuation_map.keys())
    all_punc_values = list(punctuation_map.values())

    original_stripped = original.strip()
    translation_stripped = translation.strip()

    if original_stripped and translation_stripped:
        orig_start_char, trans_start_char = original_stripped[0], translation_stripped[0]
        orig_is_punc_start = orig_start_char in all_punc_keys or orig_start_char in all_punc_values
        trans_is_punc_start = trans_start_char in all_punc_keys or trans_start_char in all_punc_values
        if orig_is_punc_start != trans_is_punc_start:
            ts_obj.warnings.append(
                (WarningType.PUNCTUATION_MISMATCH_START, _("Starting punctuation presence differs.")))
        elif orig_is_punc_start and (
                punctuation_map.get(orig_start_char) != trans_start_char and orig_start_char != trans_start_char):
            ts_obj.warnings.append((WarningType.PUNCTUATION_MISMATCH_START,
                                    _("Starting punctuation differs: '{c1}' vs '{c2}'.").format(c1=orig_start_char,
                                                                                                c2=trans_start_char)))

        orig_end_char, trans_end_char = original_stripped[-1], translation_stripped[-1]
        orig_is_punc_end = orig_end_char in all_punc_keys or orig_end_char in all_punc_values
        trans_is_punc_end = trans_end_char in all_punc_keys or trans_end_char in all_punc_values
        if orig_is_punc_end != trans_is_punc_end:
            ts_obj.warnings.append((WarningType.PUNCTUATION_MISMATCH_END, _("Ending punctuation presence differs.")))
        elif orig_is_punc_end and (
                punctuation_map.get(orig_end_char) != trans_end_char and orig_end_char != trans_end_char):
            ts_obj.warnings.append((WarningType.PUNCTUATION_MISMATCH_END,
                                    _("Ending punctuation differs: '{c1}' vs '{c2}'.").format(c1=orig_end_char,
                                                                                              c2=trans_end_char)))

    # 首字母大小写
    first_char_original = get_starting_cased_char(original)
    first_char_translation = get_starting_cased_char(translation)
    if first_char_original and first_char_translation and (
            first_char_original.isupper() != first_char_translation.isupper()):
        ts_obj.warnings.append((WarningType.CAPITALIZATION_MISMATCH, _("Initial capitalization mismatch.")))
    len_orig = len(original)
    len_trans = len(translation)

    if len_orig == 0 and len_trans > 0:
        ts_obj.warnings.append(
            (WarningType.ORIGINAL_EMPTY_BUT_TRANSLATION_NOT, _("Original is empty but translation is not.")))
    elif len_trans == 0 and len_orig > 0:
        ts_obj.warnings.append(
            (WarningType.TRANSLATION_EMPTY_BUT_ORIGINAL_NOT, _("Translation is empty but original is not.")))
    elif len_orig > 0:
        short_text_threshold = 5
        absolute_diff_threshold = 5

        is_short_text = len_orig < short_text_threshold
        absolute_diff = abs(len_trans - len_orig)
        relative_deviation = absolute_diff / len_orig

        apply_length_warning = True
        if is_short_text and absolute_diff <= absolute_diff_threshold:
            apply_length_warning = False

        if apply_length_warning:
            if relative_deviation >= 0.8:
                ts_obj.warnings.append((WarningType.LENGTH_DEVIATION_MAJOR,
                                        _("Translation length differs by {percent:.0%} (Major).").format(
                                            percent=relative_deviation)))
            elif relative_deviation >= 0.5:
                ts_obj.minor_warnings.append((WarningType.LENGTH_DEVIATION_MINOR,
                                              _("Translation length differs by {percent:.0%} (Minor).").format(
                                                  percent=relative_deviation)))


def run_validation_on_all(translatable_objects):
    for ts_obj in translatable_objects:
        validate_string(ts_obj)