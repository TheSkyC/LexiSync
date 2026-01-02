# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import regex as re
from utils.localization import _
from utils.enums import WarningType
from utils.text_utils import get_linguistic_length
from services import validation_helpers
from services.expansion_ratio_service import ExpansionRatioService
from utils.constants import DEFAULT_VALIDATION_RULES

placeholder_regex = re.compile(r'\{([^{}]+)\}')
def has_case(char):
    return char.lower() != char.upper()

def get_starting_cased_char(s):
    stripped_s = s.lstrip()
    if stripped_s and has_case(stripped_s[0]):
        return stripped_s[0]
    return None


def _report(ts_obj, config, rule_key, warning_type, message):
    rules = config.get("validation_rules", {})
    rule_cfg = rules.get(rule_key, DEFAULT_VALIDATION_RULES.get(rule_key, {"enabled": True, "level": "warning"}))

    if not rule_cfg.get("enabled", True):
        return

    level = rule_cfg.get("level", "warning")

    if level == "error":
        ts_obj.warnings.append((warning_type, message))
    elif level == "info":
        ts_obj.infos.append((warning_type, message))
    else:
        ts_obj.minor_warnings.append((warning_type, message))


"""
[Developer Guide] How to add a new validation rule?
【开发指南】如何增加一个新的验证规则？

1. Define Type (定义类型):
   - Modify `utils/enums.py`: Add a new member to `WarningType` (e.g., `QUOTE_MISMATCH`).

2. Define Default Config (定义默认配置):
   - Modify `utils/constants.py`: Add entry to `DEFAULT_VALIDATION_RULES`.
     Example: "quotes": {"enabled": True, "level": "warning", "label": "Check Quotes"}

3. Implement Logic (实现逻辑):
   - Modify `services/validation_helpers.py`: Write a pure function that returns an error string or None.
     Example: `def check_quotes(source, target): ...`

4. Integrate (集成):
   - Modify `services/validation_service.py`: In `validate_string`, call your helper and report it.
     Example:
     if err := validation_helpers.check_quotes(original, translation):
         _report(ts_obj, config, "quotes", WarningType.QUOTE_MISMATCH, err)

5. UI (UI显示):
   - Modify `dialogs/settings_pages.py`: Add the new key to the `groups` dictionary to show it in Settings.
"""

def validate_string(ts_obj, config, app_instance=None, term_cache=None):
    ts_obj.warnings = []
    ts_obj.minor_warnings = []
    ts_obj.infos = []

    if not ts_obj.translation or ts_obj.is_ignored:
        return

    original = ts_obj.original_semantic
    translation = ts_obj.translation
    rules = config.get("validation_rules", {})

    # 加速键检查
    accelerator_markers_str = config.get('accelerator_marker', '&')
    markers = [m.strip() for m in accelerator_markers_str.split(',') if m.strip()]
    if not markers:
        markers = ['&']
    if err := validation_helpers.check_accelerators(original, translation, markers):
        _report(ts_obj, config, "accelerator", WarningType.ACCELERATOR_MISMATCH, _(err))

    # 剥离加速键
    original_clean = validation_helpers.strip_accelerators(original, markers)
    translation_clean = validation_helpers.strip_accelerators(translation, markers)

    # --- 1. 代码安全检查 ---
    printf_mode = rules.get("printf", {}).get("mode", "loose")
    if err := validation_helpers.check_printf(original, translation, mode=printf_mode):
        _report(ts_obj, config, "printf", WarningType.PRINTF_MISMATCH, err)

    if err := validation_helpers.check_python_brace(original, translation):
        _report(ts_obj, config, "python_brace", WarningType.PYTHON_BRACE_MISMATCH, err)

    if err := validation_helpers.check_html_tags(original, translation):
        _report(ts_obj, config, "html_tags", WarningType.PLACEHOLDER_MISSING, err)

    if err := validation_helpers.check_urls_emails(original, translation):
        _report(ts_obj, config, "url_email", WarningType.URL_MISMATCH, err)

    # --- 2. 内容一致性 ---
    numbers_mode = rules.get("numbers", {}).get("mode", "loose")
    if err := validation_helpers.check_numbers(original, translation, mode=numbers_mode):
        _report(ts_obj, config, "numbers", WarningType.NUMBER_MISMATCH, err)

    if ts_obj.is_fuzzy:
        _report(ts_obj, config, "fuzzy", WarningType.FUZZY_TRANSLATION, _("Translation is marked as fuzzy."))

    # 术语库检查
    if term_cache:
        original_words = set(re.findall(r'\b\w+\b', original.lower()))
        translation_lower = translation.lower()
        for word in original_words:
            if word in term_cache:
                term_info = term_cache[word]
                required_targets = [t['target'].lower() for t in term_info['translations']]
                if not any(target in translation_lower for target in required_targets):
                    msg = _("Glossary Mismatch: Term '{term}' should be translated as one of '{targets}'.").format(
                        term=word, targets=" / ".join(required_targets))
                    _report(ts_obj, config, "glossary", WarningType.GLOSSARY_MISMATCH, msg)

    # --- 3. 格式与标点 ---
    if err := validation_helpers.check_brackets(original_clean, translation_clean):
        _report(ts_obj, config, "brackets", WarningType.BRACKET_MISMATCH, err)

    if err := validation_helpers.check_double_space(original, translation):
        _report(ts_obj, config, "double_space", WarningType.DOUBLE_SPACE, _(err))

    # 空格检查
    if err := validation_helpers.check_leading_whitespace(original_clean, translation_clean):
        _report(ts_obj, config, "whitespace", WarningType.LEADING_WHITESPACE_MISMATCH, _(err))

    if err := validation_helpers.check_trailing_whitespace(original_clean, translation_clean):
        _report(ts_obj, config, "whitespace", WarningType.TRAILING_WHITESPACE_MISMATCH, _(err))

    # 标点检查
    if err := validation_helpers.check_starting_punctuation(original_clean, translation_clean):
        _report(ts_obj, config, "punctuation", WarningType.PUNCTUATION_MISMATCH_START, _(err))

    if err := validation_helpers.check_ending_punctuation(original_clean, translation_clean):
        _report(ts_obj, config, "punctuation", WarningType.PUNCTUATION_MISMATCH_END, _(err))

    # 大小写检查
    if err := validation_helpers.check_capitalization(original_clean, translation_clean):
        _report(ts_obj, config, "capitalization", WarningType.CAPITALIZATION_MISMATCH, _(err))

    if err := validation_helpers.check_repeated_words(original_clean, translation_clean):
        _report(ts_obj, config, "repeated_word", WarningType.REPEATED_WORD, _(err))

    if err := validation_helpers.check_newline_count(original_clean, translation_clean):
        _report(ts_obj, config, "newline_count", WarningType.NEWLINE_COUNT_MISMATCH, _(err))

    if err := validation_helpers.check_quotes(original_clean, translation_clean):
        _report(ts_obj, config, "quotes", WarningType.QUOTE_MISMATCH, _(err))

    # --- 4. 长度检查 ---
    if config.get('check_length', True):
        # 逻辑条件：长度大于4 且 内容不同
        if len(original) > 4 and original != translation:
            len_orig = get_linguistic_length(original)
            len_trans = get_linguistic_length(translation)

            if len_orig > 0:
                actual_ratio = len_trans / len_orig
                service = ExpansionRatioService.get_instance()
                expected_ratio = service.get_expected_ratio(
                    app_instance.source_language,
                    app_instance.target_language,
                    original,
                    "none"
                )

                # 优先从 config 读取，如果没有则使用硬编码默认值 (2.5, 0.4, 2.0, 0.5)
                major_upper_threshold_factor = config.get("length_threshold_major", 2.5)
                major_lower_threshold_factor = 1 / major_upper_threshold_factor
                minor_upper_threshold_factor = config.get("length_threshold_minor", 2.0)
                minor_lower_threshold_factor = 1 / minor_upper_threshold_factor

                if expected_ratio is not None and expected_ratio > 0:
                    if actual_ratio > expected_ratio * major_upper_threshold_factor or \
                            actual_ratio < expected_ratio * major_lower_threshold_factor:

                        warning_msg = _(
                            "Length warning: Unusual expansion ratio ({actual:.1f}x), expected around {expected:.1f}x.").format(
                            actual=actual_ratio, expected=expected_ratio)
                        ts_obj.warnings.append((WarningType.LENGTH_DEVIATION_MAJOR, warning_msg))

                    # 轻微警告逻辑
                    elif actual_ratio > expected_ratio * minor_upper_threshold_factor or \
                            actual_ratio < expected_ratio * minor_lower_threshold_factor:

                        warning_msg = _(
                            "Length warning: Unusual expansion ratio ({actual:.1f}x), expected around {expected:.1f}x.").format(
                            actual=actual_ratio, expected=expected_ratio)
                        ts_obj.minor_warnings.append((WarningType.LENGTH_DEVIATION_MINOR, warning_msg))


def run_validation_on_all(translatable_objects, config, app_instance=None):
    term_cache = {}
    if config.get('check_glossary', True) and app_instance:
        all_words = set()
        for ts_obj in translatable_objects:
            if not ts_obj.is_ignored:
                all_words.update(re.findall(r'\b\w+\b', ts_obj.original_semantic.lower()))
        if all_words:
            source_lang = app_instance.source_language
            target_lang = app_instance.current_target_language if app_instance.is_project_mode else app_instance.target_language
            term_cache = app_instance.glossary_service.get_translations_batch(
                words=list(all_words),
                source_lang=source_lang,
                target_lang=target_lang,
                include_reverse=False
            )
    for ts_obj in translatable_objects:
        validate_string(ts_obj, config, app_instance, term_cache)