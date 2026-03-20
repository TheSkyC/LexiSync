# Copyright (c) 2025-2026, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from functools import lru_cache
import gettext
import logging

from babel import Locale

from lexisync.utils.localization import _

logger = logging.getLogger(__name__)

_PLURAL_TEST_NUMBERS = [*list(range(101)), 111, 121, 200, 201, 500, 1000, 10000, 100000, 1000000]

_TAG_ORDER = ["zero", "one", "two", "few", "many", "other"]


def _get_tag_names() -> list[str]:
    """动态获取复数标签名"""
    return [_("Zero"), _("One"), _("Two"), _("Few"), _("Many"), _("Other")]


def _get_tag_map() -> dict[str, str]:
    """动态获取 CLDR tag → 本地化名称映射"""
    return {
        "zero": _("Zero"),
        "one": _("One"),
        "two": _("Two"),
        "few": _("Few"),
        "many": _("Many"),
        "other": _("Other"),
    }


def _collect_examples(buckets: dict, key_func) -> dict:
    """
    通用采样函数。
    遍历 _PLURAL_TEST_NUMBERS，用 key_func(n) 确定分组键，
    每组最多收集 5 个不重复的样本字符串。
    """
    for n in _PLURAL_TEST_NUMBERS:
        key = key_func(n)
        bucket = buckets.get(key)
        if bucket is not None and len(bucket) < 5:
            s = str(n)
            if s not in bucket:
                bucket.append(s)
    return buckets


def _format_examples(bucket: list) -> str:
    """将样本列表格式化为可读字符串。"""
    if not bucket:
        return _("No typical examples found")
    s = ", ".join(bucket)
    return s + "..." if len(bucket) == 5 else s


def _fill_missing_forms(results: list, target_count: int, has_file_info: bool) -> list:
    tag_names = _get_tag_names()
    placeholder = _("Unknown") if has_file_info else _("N/A")
    while len(results) < target_count:
        i = len(results)
        cat_name = tag_names[i] if i < len(tag_names) else f"Form {i}"
        results.append({"index": i, "category": cat_name, "examples": placeholder})
    return results


@lru_cache(maxsize=256)
def get_plural_info(
    lang_code: str,
    num_plurals_from_file: int | None = None,
    plural_expr_from_file: str | None = None,
) -> list[dict]:
    """
    获取目标语言的复数规则信息。

    :param lang_code: 语言代码，如 'ar'
    :param num_plurals_from_file: po 文件头中的 nplurals 值
    :param plural_expr_from_file: po 文件头中的 plural 表达式
    :returns: 形如 [{"index": int, "category": str, "examples": str}, ...] 的列表
    """
    results = []
    tag_names = _get_tag_names()

    # 1. 优先使用 PO 文件自带的公式动态计算
    if num_plurals_from_file and plural_expr_from_file:
        try:
            plural_func = gettext.c2py(plural_expr_from_file)
            buckets = {i: [] for i in range(num_plurals_from_file)}
            _collect_examples(buckets, plural_func)

            index_to_cldr: dict[int, str] = {}
            try:
                parsed_locale = Locale.parse(lang_code, sep="_")
                babel_plural = parsed_locale.plural_form
                for idx, examples in buckets.items():
                    if examples:
                        index_to_cldr[idx] = babel_plural(int(examples[0]))
            except Exception:
                pass

            tag_map = _get_tag_map()
            for i in range(num_plurals_from_file):
                cldr_tag = index_to_cldr.get(i)
                if cldr_tag and cldr_tag in tag_map:
                    cat_name = tag_map[cldr_tag]
                else:
                    cat_name = tag_names[i] if i < len(tag_names) else f"Form {i}"
                results.append(
                    {
                        "index": i,
                        "category": cat_name,
                        "examples": _format_examples(buckets[i]),
                    }
                )
            return results
        except Exception as e:
            logger.warning(f"Failed to parse plural expr '{plural_expr_from_file}': {e}")
            results = []

    # 2. 降级使用 Babel
    if not results:
        try:
            parsed_locale = Locale.parse(lang_code, sep="_")
            plural_form = parsed_locale.plural_form

            buckets = {tag: [] for tag in plural_form.tags}
            _collect_examples(buckets, plural_form)

            tag_map = _get_tag_map()
            sorted_tags = sorted(
                plural_form.tags,
                key=lambda x: _TAG_ORDER.index(x) if x in _TAG_ORDER else 99,
            )

            for i, tag in enumerate(sorted_tags):
                category_name = tag_map.get(tag, tag.capitalize())
                results.append(
                    {
                        "index": i,
                        "category": category_name,
                        "examples": _format_examples(buckets[tag]),
                    }
                )
        except Exception as e:
            logger.warning(f"Babel failed to parse plural rules for '{lang_code}': {e}")

    # 3. 统一兜底：补全不足的复数形态
    target = num_plurals_from_file or 1
    _fill_missing_forms(results, target, has_file_info=bool(num_plurals_from_file))

    return results


def get_plural_form_description(
    lang_code: str,
    index: int,
    num_plurals: int | None = None,
    plural_expr: str | None = None,
) -> str:
    """
    获取指定语言和索引的复数形式描述。
    支持传入文件特定的 nplurals 和 expression 以提高准确性。
    """
    all_forms = get_plural_info(lang_code, num_plurals, plural_expr)
    form_info = next((f for f in all_forms if f["index"] == index), None)

    if form_info:
        category = form_info["category"]
        examples = form_info["examples"] or _("N/A")
        return f"Category: **{category}**\nApplicable to numbers like: {examples}"

    return f"Category: Form {index} (Specific rule not found for {lang_code})"


@lru_cache(maxsize=128)
def get_singular_index_from_expr(plural_expr: str) -> int:
    if not plural_expr:
        return 0
    try:
        plural_func = gettext.c2py(plural_expr)
        return plural_func(1)
    except Exception:
        return 0
