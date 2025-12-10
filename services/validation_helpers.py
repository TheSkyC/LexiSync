# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import re
from collections import Counter

PUNCTUATION_MAP = {'.': '。', ',': '，', '?': '？', '!': '！', ':': '：', ';': '；', '(': '（', ')': '）'}
ALL_PUNC_KEYS = set(PUNCTUATION_MAP.keys())
ALL_PUNC_VALUES = set(PUNCTUATION_MAP.values())

# --- 正则表达式 ---
RE_PRINTF = re.compile(r'%(\d+\$)?[-+ 0#]*(\d+|\*)?(\.(\d+|\*))?[hlLzZjpt]*[diouxXeEfFgGcrs%]')
RE_PYTHON_BRACE = re.compile(r'\{([_a-zA-Z0-9\s\.\:\[\]]*)\}')
RE_URL = re.compile(r'https?://[^\s]+|www\.[^\s]+')
RE_EMAIL = re.compile(r'[\w\.-]+@[\w\.-]+')
RE_NUMBER = re.compile(r'\d+(?:\.\d+)?')

def _has_case(char):
    return char.lower() != char.upper()


def _get_starting_cased_char(s):
    stripped_s = s.lstrip()
    if stripped_s and _has_case(stripped_s[0]):
        return stripped_s[0]
    return None


def check_leading_whitespace(source, target):
    """检查开头空格"""
    src_has = source.lstrip() != source
    tgt_has = target.lstrip() != target

    if src_has and not tgt_has:
        return "Missing leading whitespace."
    if not src_has and tgt_has:
        return "Extra leading whitespace."
    return None


def check_trailing_whitespace(source, target):
    """检查结尾空格"""
    src_has = source.rstrip() != source
    tgt_has = target.rstrip() != target

    if src_has and not tgt_has:
        return "Missing trailing whitespace."
    if not src_has and tgt_has:
        return "Extra trailing whitespace."
    return None


def check_starting_punctuation(source, target):
    """检查开头标点"""
    s_strip = source.strip()
    t_strip = target.strip()
    if not s_strip or not t_strip:
        return None

    s_char = s_strip[0]
    t_char = t_strip[0]

    s_is_punc = s_char in ALL_PUNC_KEYS or s_char in ALL_PUNC_VALUES
    t_is_punc = t_char in ALL_PUNC_KEYS or t_char in ALL_PUNC_VALUES

    if s_is_punc != t_is_punc:
        return "Starting punctuation presence differs."

    if s_is_punc:
        expected_t = PUNCTUATION_MAP.get(s_char, s_char)
        if t_char != expected_t and t_char != s_char:
            return f"Starting punctuation differs: '{s_char}' vs '{t_char}'."

    return None


def check_ending_punctuation(source, target):
    """检查结尾标点"""
    s_strip = source.strip()
    t_strip = target.strip()
    if not s_strip or not t_strip:
        return None

    temp_s = s_strip
    if temp_s.lower().endswith('(s)'):
        temp_s = temp_s[:-3].rstrip()
    if not temp_s:
        temp_s = s_strip

    s_char = temp_s[-1]
    t_char = t_strip[-1]

    s_is_punc = s_char in ALL_PUNC_KEYS or s_char in ALL_PUNC_VALUES
    t_is_punc = t_char in ALL_PUNC_KEYS or t_char in ALL_PUNC_VALUES

    if s_is_punc != t_is_punc:
        return "Ending punctuation presence differs."

    if s_is_punc:
        expected_t = PUNCTUATION_MAP.get(s_char, s_char)
        if t_char != expected_t and t_char != s_char:
            return f"Ending punctuation differs: '{s_char}' vs '{t_char}'."
    return None


def check_capitalization(source, target):
    """检查首字母大小写"""
    s_char = _get_starting_cased_char(source)
    t_char = _get_starting_cased_char(target)

    if s_char and t_char:
        if s_char.isupper() != t_char.isupper():
            return "Initial capitalization mismatch."
    return None


def _compare_counts(src_list, tgt_list):
    src_counts = Counter(src_list)
    tgt_counts = Counter(tgt_list)
    missing = []
    extra = []
    all_keys = set(src_counts.keys()) | set(tgt_counts.keys())
    for key in all_keys:
        diff = src_counts[key] - tgt_counts[key]
        if diff > 0:
            missing.append(f"'{key}' (x{diff})")
        elif diff < 0:
            extra.append(f"'{key}' (x{abs(diff)})")
    return missing, extra


def check_printf(source, target):
    src_fmt = [m.group() for m in RE_PRINTF.finditer(source)]
    tgt_fmt = [m.group() for m in RE_PRINTF.finditer(target)]
    missing, extra = _compare_counts(src_fmt, tgt_fmt)
    if missing or extra:
        return f"Printf mismatch. Missing: {', '.join(missing)} | Extra: {', '.join(extra)}"
    return None


def check_python_brace(source, target):
    src_clean = source.replace('{{', '').replace('}}', '')
    tgt_clean = target.replace('{{', '').replace('}}', '')
    src_fmt = RE_PYTHON_BRACE.findall(src_clean)
    tgt_fmt = RE_PYTHON_BRACE.findall(tgt_clean)
    missing, extra = _compare_counts(src_fmt, tgt_fmt)
    if missing or extra:
        return f"Brace mismatch. Missing: {', '.join(missing)} | Extra: {', '.join(extra)}"
    return None


def check_urls_emails(source, target):
    # URL
    src_urls = RE_URL.findall(source)
    tgt_urls = RE_URL.findall(target)
    missing, _ = _compare_counts(src_urls, tgt_urls)
    if missing: return f"URL mismatch: {', '.join(missing)}"
    # Email
    src_emails = RE_EMAIL.findall(source)
    tgt_emails = RE_EMAIL.findall(target)
    missing_e, _ = _compare_counts(src_emails, tgt_emails)
    if missing_e: return f"Email mismatch: {', '.join(missing_e)}"
    return None


def check_numbers(source, target):
    src_clean = RE_PYTHON_BRACE.sub('', source)
    src_clean = RE_PRINTF.sub('', src_clean)
    tgt_clean = RE_PYTHON_BRACE.sub('', target)
    tgt_clean = RE_PRINTF.sub('', tgt_clean)

    src_nums = RE_NUMBER.findall(src_clean)
    tgt_nums = RE_NUMBER.findall(tgt_clean)
    missing, extra = _compare_counts(src_nums, tgt_nums)
    if missing or extra:
        return f"Numbers mismatch. Missing: {', '.join(missing)} | Extra: {', '.join(extra)}"
    return None


def check_brackets(source, target):
    """检查括号是否成对且数量一致"""
    brackets = [('(', ')'), ('[', ']'), ('{', '}'), ('（', '）'), ('【', '】')]
    errors = []
    for start, end in brackets:
        if target.count(start) != target.count(end):
            errors.append(f"Unbalanced '{start}' and '{end}'")
        # 检查数量是否与原文一致
        # if source.count(start) != target.count(start):
        #     errors.append(f"Count of '{start}' differs from original")
    return " | ".join(errors) if errors else None


def check_double_space(source, target):
    if "  " in target and "  " not in source:
        return "Translation contains double spaces"
    return None


def check_html_tags(source, target):
    # 匹配 <tag> 或 </tag> 或 <tag />
    tag_re = re.compile(r'</?[a-zA-Z0-9]+[^>]*>')
    src_tags = tag_re.findall(source)
    tgt_tags = tag_re.findall(target)
    missing, extra = _compare_counts(src_tags, tgt_tags)
    if missing or extra:
        return f"HTML Tag mismatch. Missing: {', '.join(missing)}"
    return None