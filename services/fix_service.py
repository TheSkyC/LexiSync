# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from utils.enums import WarningType
import regex as re

# 标点映射表
PUNCTUATION_MAP = {
    'zh': {'.': '。', ',': '，', ':': '：', ';': '；', '?': '？', '!': '！', '(': '（', ')': '）'},
    'zh_CN': {'.': '。', ',': '，', ':': '：', ';': '；', '?': '？', '!': '！', '(': '（', ')': '）'},
    'zh_TW': {'.': '。', ',': '，', ':': '：', ';': '；', '?': '？', '!': '！', '(': '（', ')': '）'},
    'ja': {'.': '。', ',': '、', ':': '：', ';': '；', '?': '？', '!': '！', '(': '（', ')': '）'},
}

ALL_ENDING_PUNCTS = {
    '.', ',', ':', ';', '?', '!', ')', ']', '}', '>', '"', "'",
    '。', '，', '：', '；', '？', '！', '）', '】', '》', '”', '’', '、'
}


def get_fix_for_warning(ts_obj, warning_type, target_lang):
    """
    根据警告类型和目标语言，尝试生成修复后的译文。
    如果无法修复，返回 None。
    """
    original = ts_obj.original_semantic
    current_translation = ts_obj.translation

    if not current_translation:
        return None

    # 1. 前导空格修复
    whitespace_chars_to_fix = ' \t'
    if warning_type == WarningType.LEADING_WHITESPACE_MISMATCH:
        src_leading_match = re.match(f'^[{whitespace_chars_to_fix}]*', original)
        src_leading = src_leading_match.group(0) if src_leading_match else ''
        tgt_stripped = current_translation.lstrip(whitespace_chars_to_fix)
        return src_leading + tgt_stripped

    # 2. 尾随空格修复
    if warning_type == WarningType.TRAILING_WHITESPACE_MISMATCH:
        src_trailing_match = re.search(f'[{whitespace_chars_to_fix}]*$', original)
        src_trailing = src_trailing_match.group(0) if src_trailing_match else ''
        tgt_stripped = current_translation.rstrip(whitespace_chars_to_fix)
        return tgt_stripped + src_trailing

    # 3. 双空格修复 (替换为单空格)
    if warning_type == WarningType.DOUBLE_SPACE:
        return current_translation.replace("  ", " ")

    # 4. 首字母大小写修复
    if warning_type == WarningType.CAPITALIZATION_MISMATCH:
        if not target_lang.startswith(('zh', 'ja', 'ko')):
            src_first = original[0] if original else ''
            tgt_first = current_translation[0] if current_translation else ''
            if src_first.isupper() and tgt_first.islower():
                return tgt_first.upper() + current_translation[1:]
            elif src_first.islower() and tgt_first.isupper():
                return tgt_first.lower() + current_translation[1:]

    # 5. 结尾标点修复
    if warning_type == WarningType.PUNCTUATION_MISMATCH_END:
        src_strip = original.rstrip()
        tgt_strip = current_translation.rstrip()

        if not src_strip or not tgt_strip:
            return None

        ellipses = ["...", "…", "……", "。。。"]
        src_has_ellipsis = any(src_strip.endswith(e) for e in ellipses)
        tgt_has_ellipsis = any(tgt_strip.endswith(e) for e in ellipses)

        if src_has_ellipsis and not tgt_has_ellipsis:
            if target_lang.startswith('zh'):
                ellipsis_to_add = "……"
            else:
                ellipsis_to_add = "..."
            if tgt_strip[-1] in ALL_ENDING_PUNCTS:
                return tgt_strip[:-1] + ellipsis_to_add
            return tgt_strip + ellipsis_to_add

        elif not src_has_ellipsis and tgt_has_ellipsis:
            for e in ellipses:
                if tgt_strip.endswith(e):
                    return tgt_strip[:-len(e)]

        src_last = src_strip[-1]
        tgt_last = tgt_strip[-1]

        is_src_punct = src_last in ALL_ENDING_PUNCTS
        is_tgt_punct = tgt_last in ALL_ENDING_PUNCTS

        if not is_src_punct and is_tgt_punct:
            return current_translation.rstrip()[:-1]

        if is_src_punct:
            lang_map = PUNCTUATION_MAP.get(target_lang, {})
            expected_punct = lang_map.get(src_last, src_last)

            base_text = current_translation.rstrip()
            if is_tgt_punct:
                base_text = base_text[:-1]

            return base_text + expected_punct
    # 6. 盘古之白修复
    if warning_type == WarningType.PANGU_SPACING:
        from services.validation_helpers import RE_CJK, RE_LATIN
        new_text = re.sub(f'({RE_CJK})({RE_LATIN})', r'\1 \2', current_translation)
        new_text = re.sub(f'({RE_LATIN})({RE_CJK})', r'\1 \2', new_text)
        return new_text

    return None


def apply_all_fixes(ts_obj, target_lang):
    """尝试自动修复所有可修复的问题"""
    # 获取所有警告类型
    all_warnings = [w[0] for w in ts_obj.warnings + ts_obj.minor_warnings + ts_obj.infos]

    # 按照优先级顺序应用修复（避免冲突）
    # 顺序：空格 -> 标点 -> 大小写
    priority_order = [
        WarningType.LEADING_WHITESPACE_MISMATCH,
        WarningType.TRAILING_WHITESPACE_MISMATCH,
        WarningType.DOUBLE_SPACE,
        WarningType.PANGU_SPACING,
        WarningType.PUNCTUATION_MISMATCH_END,
        WarningType.CAPITALIZATION_MISMATCH
    ]

    new_text = ts_obj.translation

    # 创建一个临时的 ts_obj 用于链式修复
    from models.translatable_string import TranslatableString
    temp_ts = TranslatableString("", ts_obj.original_semantic, 0, 0, 0, [])
    temp_ts.translation = new_text

    fixed_something = False

    for wt in priority_order:
        if wt in all_warnings:
            suggestion = get_fix_for_warning(temp_ts, wt, target_lang)
            if suggestion and suggestion != temp_ts.translation:
                temp_ts.translation = suggestion
                fixed_something = True

    return temp_ts.translation if fixed_something else None