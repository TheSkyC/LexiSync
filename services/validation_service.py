# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import re

placeholder_regex = re.compile(r'\{([^{}]+)\}')


def has_case(char):
    return char.lower() != char.upper()


def get_first_cased_char_from_first_cased_block(s):
    cased_blocks = re.findall(r'[\w\u00C0-\u017F]+', s)

    for block in cased_blocks:
        if block and has_case(block[0]):
            return block[0]

    return None


def validate_string(ts_obj):
    if not ts_obj.translation or ts_obj.is_ignored:
        return []

    warnings = []
    original = ts_obj.original_semantic
    translation = ts_obj.translation

    original_placeholders = set(placeholder_regex.findall(original))
    translated_placeholders = set(placeholder_regex.findall(translation))
    if original_placeholders != translated_placeholders:
        missing = original_placeholders - translated_placeholders
        extra = translated_placeholders - original_placeholders
        warning_msg = "Placeholder mismatch."
        if missing:
            warning_msg += f" Missing: {', '.join(missing)}."
        if extra:
            warning_msg += f" Extra: {', '.join(extra)}."
        warnings.append(warning_msg)

    if original.count('\n') != translation.count('\n'):
        warnings.append("Line count differs from original.")

    if (original.startswith(' ') and not translation.startswith(' ')) or \
            (not original.startswith(' ') and translation.startswith(' ')):
        warnings.append("Leading whitespace mismatch.")
    if (original.endswith(' ') and not translation.endswith(' ')) or \
            (not original.endswith(' ') and translation.endswith(' ')):
        warnings.append("Trailing whitespace mismatch.")

    punctuation_map = {
        '.': '。', '。': '.', ',': '，', '，': ',', '?': '？', '？': '?',
        '!': '！', '！': '!', ':': '：', '：': ':', ';': '；', '；': ';',
        '(': '（', '（': '(', ')': '）', '）': ')',
    }
    all_punc = set(punctuation_map.keys())

    original_stripped = original.strip()
    translation_stripped = translation.strip()

    def is_punc(char):
        return char in all_punc

    def are_equivalent(char1, char2):
        if char1 == char2:
            return True
        if punctuation_map.get(char1) == char2:
            return True
        return False

    if original_stripped and translation_stripped:
        start_orig_char = original_stripped[0]
        start_trans_char = translation_stripped[0]
        orig_starts_with_punc = is_punc(start_orig_char)
        trans_starts_with_punc = is_punc(start_trans_char)

        if orig_starts_with_punc and not trans_starts_with_punc:
            warnings.append(f"Original starts with '{start_orig_char}', but translation does not start with punctuation.")
        elif not orig_starts_with_punc and trans_starts_with_punc:
            warnings.append(f"Translation starts with '{start_trans_char}', but original does not start with punctuation.")
        elif orig_starts_with_punc and trans_starts_with_punc and not are_equivalent(start_orig_char, start_trans_char):
            warnings.append(f"Starting punctuation mismatch: '{start_orig_char}' vs '{start_trans_char}'.")

    if original_stripped and translation_stripped:
        end_orig_char = original_stripped[-1]
        end_trans_char = translation_stripped[-1]
        orig_ends_with_punc = is_punc(end_orig_char)
        trans_ends_with_punc = is_punc(end_trans_char)

        if orig_ends_with_punc and not trans_ends_with_punc:
            warnings.append(f"Original ends with '{end_orig_char}', but translation does not end with punctuation.")
        elif not orig_ends_with_punc and trans_ends_with_punc:
            warnings.append(f"Translation ends with '{end_trans_char}', but original does not end with punctuation.")
        elif orig_ends_with_punc and trans_ends_with_punc and not are_equivalent(end_orig_char, end_trans_char):
            warnings.append(f"Ending punctuation mismatch: '{end_orig_char}' vs '{end_trans_char}'.")

    first_char_original = get_first_cased_char_from_first_cased_block(original)
    first_char_translation = get_first_cased_char_from_first_cased_block(translation)

    if first_char_original and first_char_translation:
        if first_char_original.isupper() != first_char_translation.isupper():
            warnings.append("Initial capitalization mismatch.")

    return warnings


def run_validation_on_all(translatable_objects):
    for ts_obj in translatable_objects:
        ts_obj.warnings = validate_string(ts_obj)