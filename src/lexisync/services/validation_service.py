# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import regex as re

from lexisync.services import validation_helpers
from lexisync.services.expansion_ratio_service import ExpansionRatioService
from lexisync.utils.constants import DEFAULT_VALIDATION_RULES
from lexisync.utils.enums import WarningType
from lexisync.utils.localization import _
from lexisync.utils.text_utils import generate_ngrams, get_linguistic_length

placeholder_regex = re.compile(r"\{([^{}]+)\}")


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


def validate_string(ts_obj, config, app_instance=None, term_cache=None):
    ts_obj.warnings = []
    ts_obj.minor_warnings = []
    ts_obj.infos = []

    if ts_obj.is_ignored:
        return

    rules = config.get("validation_rules", {})
    accelerator_markers_str = config.get("accelerator_marker", "&")
    markers = [m.strip() for m in accelerator_markers_str.split(",") if m.strip()] or ["&"]

    # 复数遍历验证
    forms_to_check = []
    if ts_obj.is_plural:
        s_idx = ts_obj.singular_index
        for idx, trans in ts_obj.plural_translations.items():
            if not trans:
                continue
            orig = ts_obj.original_semantic if idx == s_idx else ts_obj.original_plural
            forms_to_check.append((idx, orig, trans))

    if not forms_to_check:
        return

    for idx, original, translation in forms_to_check:

        def format_msg(msg, current_idx=idx):
            return f"[Form {current_idx}] {msg}" if current_idx is not None else msg

        original_clean = validation_helpers.strip_accelerators(original, markers)
        translation_clean = validation_helpers.strip_accelerators(translation, markers)

        # --- 1. 代码安全检查 ---
        printf_mode = rules.get("printf", {}).get("mode", "loose")
        if err := validation_helpers.check_printf(original, translation, mode=printf_mode):
            _report(ts_obj, config, "printf", WarningType.PRINTF_MISMATCH, format_msg(err))

        if err := validation_helpers.check_python_brace(original, translation):
            _report(ts_obj, config, "python_brace", WarningType.PYTHON_BRACE_MISMATCH, format_msg(err))

        if err := validation_helpers.check_icu_placeholders(original, translation):
            _report(ts_obj, config, "icu_placeholder", WarningType.ICU_PLACEHOLDER_MISMATCH, format_msg(err))

        if err := validation_helpers.check_html_tags(original, translation):
            _report(ts_obj, config, "html_tags", WarningType.PLACEHOLDER_MISSING, format_msg(err))

        if err := validation_helpers.check_urls_emails(original, translation):
            _report(ts_obj, config, "url_email", WarningType.URL_MISMATCH, format_msg(err))

        # --- 2. 内容一致性 ---
        numbers_mode = rules.get("numbers", {}).get("mode", "loose")
        if err := validation_helpers.check_numbers(original, translation, mode=numbers_mode):
            _report(ts_obj, config, "numbers", WarningType.NUMBER_MISMATCH, format_msg(err))

        if ts_obj.is_fuzzy:
            _report(ts_obj, config, "fuzzy", WarningType.FUZZY_TRANSLATION, _("Translation is marked as fuzzy."))

        # 术语库检查
        if term_cache:
            original_lower = original.lower()
            translation_lower = translation.lower()

            candidates = generate_ngrams(original_lower, min_n=1, max_n=5)
            candidates.sort(key=len, reverse=True)

            matched_substrings = []

            for word in candidates:
                if word in term_cache:
                    is_covered = False
                    for matched in matched_substrings:
                        if word in matched:
                            is_covered = True
                            break

                    if is_covered:
                        continue
                    if word in original_lower:
                        term_info = term_cache[word]
                        required_targets = [t["target"].lower() for t in term_info["translations"]]
                        if not any(target in translation_lower for target in required_targets):
                            msg = _(
                                "Glossary Mismatch: Term '{term}' should be translated as one of '{targets}'."
                            ).format(term=word, targets=" / ".join(required_targets))
                            _report(ts_obj, config, "glossary", WarningType.GLOSSARY_MISMATCH, msg)
                        matched_substrings.append(word)

        # --- 3. 格式与标点 ---
        if err := validation_helpers.check_pangu_spacing(translation):
            _report(ts_obj, config, "pangu", WarningType.PANGU_SPACING, format_msg(err))
        if err := validation_helpers.check_brackets(original_clean, translation_clean):
            _report(ts_obj, config, "brackets", WarningType.BRACKET_MISMATCH, format_msg(err))

        if err := validation_helpers.check_double_space(original, translation):
            _report(ts_obj, config, "double_space", WarningType.DOUBLE_SPACE, format_msg(_(err)))

        # 空格检查
        if err := validation_helpers.check_leading_whitespace(original_clean, translation_clean):
            _report(ts_obj, config, "whitespace", WarningType.LEADING_WHITESPACE_MISMATCH, format_msg(_(err)))

        if err := validation_helpers.check_trailing_whitespace(original_clean, translation_clean):
            _report(ts_obj, config, "whitespace", WarningType.TRAILING_WHITESPACE_MISMATCH, format_msg(_(err)))

        # 标点检查
        if err := validation_helpers.check_starting_punctuation(original_clean, translation_clean):
            _report(ts_obj, config, "punctuation", WarningType.PUNCTUATION_MISMATCH_START, format_msg(_(err)))

        if err := validation_helpers.check_ending_punctuation(original_clean, translation_clean):
            _report(ts_obj, config, "punctuation", WarningType.PUNCTUATION_MISMATCH_END, format_msg(_(err)))

        # 大小写检查
        if err := validation_helpers.check_capitalization(original_clean, translation_clean):
            _report(ts_obj, config, "capitalization", WarningType.CAPITALIZATION_MISMATCH, format_msg(_(err)))

        if err := validation_helpers.check_repeated_words(original_clean, translation_clean):
            _report(ts_obj, config, "repeated_word", WarningType.REPEATED_WORD, format_msg(_(err)))

        if err := validation_helpers.check_newline_count(original_clean, translation_clean):
            _report(ts_obj, config, "newline_count", WarningType.NEWLINE_COUNT_MISMATCH, format_msg(_(err)))

        if err := validation_helpers.check_quotes(original_clean, translation_clean):
            _report(ts_obj, config, "quotes", WarningType.QUOTE_MISMATCH, format_msg(_(err)))

        # --- 4. 长度检查 ---
        if config.get("check_length", True):
            # 逻辑条件：长度大于4 且 内容不同
            if len(original) > 4 and original != translation:
                len_orig = get_linguistic_length(original)
                len_trans = get_linguistic_length(translation)

                if len_orig > 0:
                    actual_ratio = len_trans / len_orig
                    service = ExpansionRatioService.get_instance()
                    expected_ratio = service.get_expected_ratio(
                        app_instance.source_language, app_instance.current_target_language, original, "none"
                    )

                    # 优先从 config 读取，如果没有则使用硬编码默认值 (2.5, 0.4, 2.0, 0.5)
                    major_upper_threshold_factor = config.get("length_threshold_major", 2.5)
                    major_lower_threshold_factor = 1 / major_upper_threshold_factor
                    minor_upper_threshold_factor = config.get("length_threshold_minor", 2.0)
                    minor_lower_threshold_factor = 1 / minor_upper_threshold_factor

                    if expected_ratio is not None and expected_ratio > 0:
                        if (
                            actual_ratio > expected_ratio * major_upper_threshold_factor
                            or actual_ratio < expected_ratio * major_lower_threshold_factor
                        ):
                            warning_msg = _(
                                "Length warning: Unusual expansion ratio ({actual:.1f}x), expected around {expected:.1f}x."
                            ).format(actual=actual_ratio, expected=expected_ratio)
                            ts_obj.warnings.append((WarningType.LENGTH_DEVIATION_MAJOR, warning_msg))

                        # 轻微警告逻辑
                        elif (
                            actual_ratio > expected_ratio * minor_upper_threshold_factor
                            or actual_ratio < expected_ratio * minor_lower_threshold_factor
                        ):
                            warning_msg = _(
                                "Length warning: Unusual expansion ratio ({actual:.1f}x), expected around {expected:.1f}x."
                            ).format(actual=actual_ratio, expected=expected_ratio)
                            ts_obj.minor_warnings.append((WarningType.LENGTH_DEVIATION_MINOR, warning_msg))


def run_validation_on_all(translatable_objects, config, app_instance=None):
    term_cache = {}
    if config.get("check_glossary", True) and app_instance:
        all_words = set()
        for ts_obj in translatable_objects:
            if not ts_obj.is_ignored:
                ngrams = generate_ngrams(ts_obj.original_semantic.lower(), min_n=1, max_n=5)
                all_words.update(ngrams)

        if all_words:
            source_lang = app_instance.source_language
            target_lang = app_instance.current_target_language
            # 批量查询所有 N-gram
            term_cache = app_instance.glossary_service.get_translations_batch(
                words=list(all_words), source_lang=source_lang, target_lang=target_lang, include_reverse=False
            )

    for ts_obj in translatable_objects:
        validate_string(ts_obj, config, app_instance, term_cache)
