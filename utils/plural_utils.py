# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import logging
import gettext
from babel import Locale
from functools import lru_cache
from utils.localization import _

logger = logging.getLogger(__name__)


def get_plural_info(lang_code: str, num_plurals_from_file: int = None, plural_expr_from_file: str = None):
    """
    获取目标语言的复数规则信息。
    :param lang_code: 语言代码，如 'ar'
    :param num_plurals_from_file: po文件头中的 nplurals 值
    :param plural_expr_from_file: po文件头中的 plural 表达式
    """
    results = []

    tag_names = [_("Zero"), _("One"), _("Two"), _("Few"), _("Many"), _("Other")]

    # 1. 优先尝试使用 PO 文件自带的公式动态计算
    if num_plurals_from_file and plural_expr_from_file:
        try:
            plural_func = gettext.c2py(plural_expr_from_file)

            examples_map = {i: [] for i in range(num_plurals_from_file)}

            for n in range(201):
                idx = plural_func(n)
                if 0 <= idx < num_plurals_from_file:
                    if len(examples_map[idx]) < 5:
                        examples_map[idx].append(str(n))

            for i in range(num_plurals_from_file):
                examples_str = ", ".join(examples_map[i])
                if len(examples_map[i]) == 5:
                    examples_str += "..."
                elif not examples_map[i]:
                    examples_str = _("No typical examples found")

                cat_name = tag_names[i] if i < len(tag_names) else f"Form {i}"
                results.append({
                    'index': i,
                    'category': cat_name,
                    'examples': examples_str
                })

            return results

        except Exception as e:
            results = []

    # 2. 如果文件里没有公式，或者解析失败，降级使用 Babel
    if not results:
        try:
            parsed_locale = Locale.parse(lang_code, sep='_')
            plural_form = parsed_locale.plural_form

            examples_map = {tag: [] for tag in plural_form.tags}
            for i in range(201):
                tag = plural_form(i)
                if tag in examples_map and len(examples_map[tag]) < 5:
                    examples_map[tag].append(str(i))

            order = ['zero', 'one', 'two', 'few', 'many', 'other']
            sorted_tags = sorted(list(plural_form.tags), key=lambda x: order.index(x) if x in order else 99)

            tag_map = {
                'zero': _("Zero"), 'one': _("One"), 'two': _("Two"),
                'few': _("Few"), 'many': _("Many"), 'other': _("Other")
            }

            for i, tag in enumerate(sorted_tags):
                examples_str = ", ".join(examples_map[tag])
                if len(examples_map[tag]) == 5:
                    examples_str += "..."
                category_name = tag_map.get(tag, tag.capitalize())
                results.append({
                    'index': i,
                    'category': category_name,
                    'examples': examples_str
                })

        except Exception as e:
            logger.warning(f"Babel failed to parse plural rules for '{lang_code}': {e}")

    # 3. 检查并补充缺失的复数形态 (兜底逻辑)
    if num_plurals_from_file and len(results) < num_plurals_from_file:
        start_idx = len(results)
        for i in range(start_idx, num_plurals_from_file):
            cat_name = tag_names[i] if i < len(tag_names) else f"Form {i}"
            results.append({
                'index': i,
                'category': cat_name,
                'examples': _("Unknown")
            })

    # 4. 极致兜底
    if not results:
        num = num_plurals_from_file if num_plurals_from_file else 1
        for i in range(num):
            cat_name = tag_names[i] if i < len(tag_names) else f"Form {i}"
            results.append({
                'index': i,
                'category': cat_name,
                'examples': _("N/A")
            })

    return results


def get_plural_form_description(lang_code: str, index: int, num_plurals: int = None, plural_expr: str = None) -> str:
    """
    获取指定语言和索引的复数形式描述。
    支持传入文件特定的 nplurals 和 expression 以提高准确性。
    """
    all_forms = get_plural_info(lang_code, num_plurals, plural_expr)

    form_info = next((f for f in all_forms if f['index'] == index), None)

    if form_info:
        category = form_info['category']
        examples = form_info['examples']
        if not examples:
            examples = "N/A"
        return f"Category: **{category}**\nApplicable to numbers like: {examples}"

    # 兜底
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