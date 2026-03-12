import regex as re

from lexisync.services import validation_helpers
from lexisync.services.expansion_ratio_service import ExpansionRatioService
from lexisync.utils.constants import DEFAULT_VALIDATION_RULES
from lexisync.utils.enums import WarningType
from lexisync.utils.localization import _
from lexisync.utils.text_utils import generate_ngrams, get_linguistic_length

placeholder_regex = re.compile(r"\{([^{}]+)\}")
BRACKET_CHARS = set("()[]{}（）【】")


def has_case(char):
    return char.lower() != char.upper()


def get_starting_cased_char(s):
    stripped_s = s.lstrip()
    if stripped_s and has_case(stripped_s[0]):
        return stripped_s[0]
    return None


def _has_url_email(text):
    return "@" in text or "/" in text or "www" in text or "WWW" in text


def is_rule_enabled(config, rule_key):
    """判断规则是否开启"""
    rules = config.get("validation_rules", {})
    rule_cfg = rules.get(rule_key, DEFAULT_VALIDATION_RULES.get(rule_key, {"enabled": True}))
    return rule_cfg.get("enabled", True)


def get_rule_level(config, rule_key):
    """获取警告级别"""
    rules = config.get("validation_rules", {})
    rule_cfg = rules.get(rule_key, DEFAULT_VALIDATION_RULES.get(rule_key, {"level": "warning"}))
    return rule_cfg.get("level", "warning")


# --- 构建规则注册表 ---
VALIDATION_REGISTRY = [
    # --- 代码安全检查 ---
    {
        "key": "printf",
        "warning_type": WarningType.PRINTF_MISMATCH,
        "fast_path": lambda ctx: ctx["has_percent"],
        "check_func": validation_helpers.check_printf,
        "kwargs_gen": lambda ctx: {
            "mode": ctx["config"].get("validation_rules", {}).get("printf", {}).get("mode", "loose")
        },
        "use_clean_text": False,
    },
    {
        "key": "python_brace",
        "warning_type": WarningType.PYTHON_BRACE_MISMATCH,
        "fast_path": lambda ctx: ctx["has_brace"],
        "check_func": validation_helpers.check_python_brace,
        "kwargs_gen": lambda ctx: {},
        "use_clean_text": False,
    },
    {
        "key": "icu_placeholder",
        "warning_type": WarningType.ICU_PLACEHOLDER_MISMATCH,
        "fast_path": lambda ctx: ctx["has_brace"],
        "check_func": validation_helpers.check_icu_placeholders,
        "kwargs_gen": lambda ctx: {},
        "use_clean_text": False,
    },
    {
        "key": "html_tags",
        "warning_type": WarningType.PLACEHOLDER_MISSING,
        "fast_path": lambda ctx: ctx["has_html"],
        "check_func": validation_helpers.check_html_tags,
        "kwargs_gen": lambda ctx: {},
        "use_clean_text": False,
    },
    {
        "key": "url_email",
        "warning_type": WarningType.URL_MISMATCH,
        "fast_path": lambda ctx: ctx["has_url_email"],
        "check_func": validation_helpers.check_urls_emails,
        "kwargs_gen": lambda ctx: {},
        "use_clean_text": False,
    },
    # --- 内容一致性 ---
    {
        "key": "numbers",
        "warning_type": WarningType.NUMBER_MISMATCH,
        "fast_path": lambda ctx: True,  # 内部已优化 RE_HAS_DIGIT
        "check_func": validation_helpers.check_numbers,
        "kwargs_gen": lambda ctx: {
            "mode": ctx["config"].get("validation_rules", {}).get("numbers", {}).get("mode", "loose")
        },
        "use_clean_text": False,
    },
    # --- 格式与标点 ---
    {
        "key": "pangu",
        "warning_type": WarningType.PANGU_SPACING,
        "fast_path": lambda ctx: True,
        "check_func": validation_helpers.check_pangu_spacing,
        "kwargs_gen": lambda ctx: {},
        "use_clean_text": False,
    },
    {
        "key": "brackets",
        "warning_type": WarningType.BRACKET_MISMATCH,
        "fast_path": lambda ctx: ctx["has_brackets"],
        "check_func": validation_helpers.check_brackets,
        "kwargs_gen": lambda ctx: {},
        "use_clean_text": True,
    },
    {
        "key": "double_space",
        "warning_type": WarningType.DOUBLE_SPACE,
        "fast_path": lambda ctx: True,
        "check_func": validation_helpers.check_double_space,
        "kwargs_gen": lambda ctx: {},
        "use_clean_text": False,
    },
    {
        "key": "whitespace",
        "warning_type": WarningType.LEADING_WHITESPACE_MISMATCH,
        "fast_path": lambda ctx: True,
        "check_func": validation_helpers.check_leading_whitespace,
        "kwargs_gen": lambda ctx: {},
        "use_clean_text": True,
    },
    {
        "key": "whitespace",
        "warning_type": WarningType.TRAILING_WHITESPACE_MISMATCH,
        "fast_path": lambda ctx: True,
        "check_func": validation_helpers.check_trailing_whitespace,
        "kwargs_gen": lambda ctx: {},
        "use_clean_text": True,
    },
    {
        "key": "punctuation",
        "warning_type": WarningType.PUNCTUATION_MISMATCH_START,
        "fast_path": lambda ctx: True,
        "check_func": validation_helpers.check_starting_punctuation,
        "kwargs_gen": lambda ctx: {"target_lang": ctx["target_lang"]},
        "use_clean_text": True,
    },
    {
        "key": "punctuation",
        "warning_type": WarningType.PUNCTUATION_MISMATCH_END,
        "fast_path": lambda ctx: True,
        "check_func": validation_helpers.check_ending_punctuation,
        "kwargs_gen": lambda ctx: {"target_lang": ctx["target_lang"]},
        "use_clean_text": True,
    },
    {
        "key": "capitalization",
        "warning_type": WarningType.CAPITALIZATION_MISMATCH,
        "fast_path": lambda ctx: True,
        "check_func": validation_helpers.check_capitalization,
        "kwargs_gen": lambda ctx: {},
        "use_clean_text": True,
    },
    {
        "key": "repeated_word",
        "warning_type": WarningType.REPEATED_WORD,
        "fast_path": lambda ctx: True,
        "check_func": validation_helpers.check_repeated_words,
        "kwargs_gen": lambda ctx: {},
        "use_clean_text": True,
    },
    {
        "key": "newline_count",
        "warning_type": WarningType.NEWLINE_COUNT_MISMATCH,
        "fast_path": lambda ctx: "\n" in ctx["original"] or "\n" in ctx["translation"],
        "check_func": validation_helpers.check_newline_count,
        "kwargs_gen": lambda ctx: {},
        "use_clean_text": True,
    },
    {
        "key": "quotes",
        "warning_type": WarningType.QUOTE_MISMATCH,
        "fast_path": lambda ctx: True,  # 内部已优化 isdisjoint
        "check_func": validation_helpers.check_quotes,
        "kwargs_gen": lambda ctx: {},
        "use_clean_text": True,
    },
    {
        "key": "accelerator",
        "warning_type": WarningType.ACCELERATOR_MISMATCH,
        "fast_path": lambda ctx: ctx["has_marker_orig"] or ctx["has_marker_trans"],
        "check_func": validation_helpers.check_accelerators,
        "kwargs_gen": lambda ctx: {"markers": ctx["markers"]},
        "use_clean_text": False,
    },
]


def validate_string(ts_obj, ctx_env):
    ts_obj.warnings = []
    ts_obj.minor_warnings = []
    ts_obj.infos = []

    if ts_obj.is_ignored:
        return

    forms_to_check = []
    if ts_obj.is_plural:
        s_idx = ts_obj.singular_index
        for idx, trans in ts_obj.plural_translations.items():
            if trans:
                orig = ts_obj.original_semantic if idx == s_idx else ts_obj.original_plural
                forms_to_check.append((idx, orig, trans))
    else:
        forms_to_check.append((None, ts_obj.original_semantic, ts_obj.translation))

    if not forms_to_check:
        return

    markers = ctx_env["markers"]

    for idx, original, translation in forms_to_check:
        if not translation.strip():
            continue

        def format_msg(msg, current_idx=idx):
            return f"[Form {current_idx}] {msg}" if current_idx is not None else msg

        has_marker_orig = any(m in original for m in markers)
        has_marker_trans = any(m in translation for m in markers)

        original_clean = validation_helpers.strip_accelerators(original, markers) if has_marker_orig else original
        translation_clean = (
            validation_helpers.strip_accelerators(translation, markers) if has_marker_trans else translation
        )

        # 准备单次执行的上下文
        ctx = {
            "original": original,
            "translation": translation,
            "original_clean": original_clean,
            "translation_clean": translation_clean,
            "has_marker_orig": has_marker_orig,
            "has_marker_trans": has_marker_trans,
            "has_percent": "%" in original or "%" in translation,
            "has_brace": "{" in original or "{" in translation,
            "has_html": "<" in original or "<" in translation,
            "has_url_email": _has_url_email(original) or _has_url_email(translation),
            "has_brackets": not BRACKET_CHARS.isdisjoint(original_clean)
            or not BRACKET_CHARS.isdisjoint(translation_clean),
        }

        for rule_pack in ctx_env["active_rules"]:
            rule = rule_pack["rule"]
            if not rule["fast_path"](ctx):
                continue

            src_text = ctx["original_clean"] if rule["use_clean_text"] else ctx["original"]
            tgt_text = ctx["translation_clean"] if rule["use_clean_text"] else ctx["translation"]

            err_msg = rule["check_func"](src_text, tgt_text, **rule_pack["kwargs"])

            if err_msg:
                level = rule_pack["level"]
                formatted_msg = format_msg(err_msg)
                if level == "error":
                    ts_obj.warnings.append((rule["warning_type"], formatted_msg))
                elif level == "info":
                    ts_obj.infos.append((rule["warning_type"], formatted_msg))
                else:
                    ts_obj.minor_warnings.append((rule["warning_type"], formatted_msg))

        # --- 特殊逻辑 ---
        if ts_obj.is_fuzzy and ctx_env["fuzzy_enabled"]:
            msg = format_msg(_("Translation is marked as fuzzy."))
            target_list = (
                ts_obj.warnings
                if ctx_env["fuzzy_level"] == "error"
                else (ts_obj.infos if ctx_env["fuzzy_level"] == "info" else ts_obj.minor_warnings)
            )
            target_list.append((WarningType.FUZZY_TRANSLATION, msg))

        if ctx_env["term_cache"] is not None and ctx_env["glossary_enabled"]:
            matches = ctx_env["term_cache"].extract_keywords(original)
            if matches:
                translation_lower = translation.lower()
                for match in matches:
                    required_targets = [t["target"].lower() for t in match["data"]["translations"]]
                    if not any(target in translation_lower for target in required_targets):
                        msg = format_msg(
                            _("Glossary Mismatch: Term '{term}' should be translated as one of '{targets}'.").format(
                                term=match["term"], targets=" / ".join(required_targets)
                            )
                        )
                        target_list = (
                            ts_obj.warnings
                            if ctx_env["glossary_level"] == "error"
                            else (ts_obj.infos if ctx_env["glossary_level"] == "info" else ts_obj.minor_warnings)
                        )
                        target_list.append((WarningType.GLOSSARY_MISMATCH, msg))

        if ctx_env["check_length"]:
            if len(original) > 4 and original != translation:
                len_orig = get_linguistic_length(original)
                len_trans = get_linguistic_length(translation)

                if len_orig > 0:
                    actual_ratio = len_trans / len_orig
                    expected_ratio = ctx_env["ratio_service"].get_expected_ratio(
                        ctx_env["source_lang"], ctx_env["target_lang"], original, "none"
                    )
                    if expected_ratio is not None and expected_ratio > 0:
                        if (
                            actual_ratio > expected_ratio * ctx_env["len_major_up"]
                            or actual_ratio < expected_ratio * ctx_env["len_major_down"]
                        ):
                            msg = _(
                                "Length warning: Unusual expansion ratio ({actual:.1f}x), expected around {expected:.1f}x."
                            ).format(actual=actual_ratio, expected=expected_ratio)
                            ts_obj.warnings.append((WarningType.LENGTH_DEVIATION_MAJOR, msg))
                        elif (
                            actual_ratio > expected_ratio * ctx_env["len_minor_up"]
                            or actual_ratio < expected_ratio * ctx_env["len_minor_down"]
                        ):
                            msg = _(
                                "Length warning: Unusual expansion ratio ({actual:.1f}x), expected around {expected:.1f}x."
                            ).format(actual=actual_ratio, expected=expected_ratio)
                            ts_obj.minor_warnings.append((WarningType.LENGTH_DEVIATION_MINOR, msg))


def build_validation_context(config, app_instance=None):
    target_lang = app_instance.current_target_language if app_instance else "en"
    source_lang = app_instance.source_language if app_instance else "en"

    accelerator_markers_str = config.get("accelerator_marker", "&")
    markers = [m.strip() for m in accelerator_markers_str.split(",") if m.strip()] or ["&"]

    active_rules_pack = []
    init_ctx = {
        "config": config,
        "target_lang": target_lang,
        "markers": markers,
    }

    for rule in VALIDATION_REGISTRY:
        if is_rule_enabled(config, rule["key"]):
            active_rules_pack.append(
                {"rule": rule, "kwargs": rule["kwargs_gen"](init_ctx), "level": get_rule_level(config, rule["key"])}
            )

    check_length = config.get("check_length", True)
    len_major_up = config.get("length_threshold_major", 2.5)

    matcher = None
    if config.get("check_glossary", True) and app_instance:
        if (
            hasattr(app_instance, "_validation_glossary_matcher")
            and app_instance._validation_glossary_matcher is not None
        ):
            matcher = app_instance._validation_glossary_matcher
        else:
            all_words = set()
            source_pool = (
                app_instance.all_project_strings if app_instance.is_project_mode else app_instance.translatable_objects
            )

            for ts_obj in source_pool:
                if not ts_obj.is_ignored:
                    sem = ts_obj.original_semantic.lower()
                    if re.search(r"\w", sem):
                        all_words.update(generate_ngrams(sem, min_n=1, max_n=5))

            if all_words:
                term_cache_dict = app_instance.glossary_service.get_translations_batch(
                    words=list(all_words), source_lang=source_lang, target_lang=target_lang, include_reverse=False
                )
                if term_cache_dict:
                    from lexisync.utils.keyword_matcher import KeywordMatcher

                    matcher = KeywordMatcher(case_sensitive=False)
                    for term, info in term_cache_dict.items():
                        matcher.add_keyword(term, info)

                    app_instance._validation_glossary_matcher = matcher

    return {
        "active_rules": active_rules_pack,
        "markers": markers,
        "fuzzy_enabled": is_rule_enabled(config, "fuzzy"),
        "fuzzy_level": get_rule_level(config, "fuzzy"),
        "glossary_enabled": is_rule_enabled(config, "glossary"),
        "glossary_level": get_rule_level(config, "glossary"),
        "term_cache": matcher,
        "check_length": check_length,
        "ratio_service": ExpansionRatioService.get_instance() if check_length else None,
        "source_lang": source_lang,
        "target_lang": target_lang,
        "len_major_up": len_major_up,
        "len_major_down": 1 / len_major_up if len_major_up else 0,
        "len_minor_up": config.get("length_threshold_minor", 2.0),
        "len_minor_down": 1 / config.get("length_threshold_minor", 2.0)
        if config.get("length_threshold_minor", 2.0)
        else 0,
    }


def validate_single_string(ts_obj, config, app_instance=None):
    ctx_env = build_validation_context(config, app_instance)
    validate_string(ts_obj, ctx_env)


def run_validation_on_all(translatable_objects, config, app_instance=None):
    ctx_env = build_validation_context(config, app_instance)
    for ts_obj in translatable_objects:
        validate_string(ts_obj, ctx_env)
