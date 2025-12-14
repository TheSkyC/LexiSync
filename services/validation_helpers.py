# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import re
from collections import Counter
import html

PUNCTUATION_MAP = {'.': '。', ',': '，', '?': '？', '!': '！', ':': '：', ';': '；', '(': '（', ')': '）'}
ALL_PUNC_KEYS = set(PUNCTUATION_MAP.keys())
ALL_PUNC_VALUES = set(PUNCTUATION_MAP.values())

# --- 正则表达式 ---
RE_PRINTF = re.compile(r'%(\d+\$)?[-+ 0#]*(\d+|\*)?(\.(\d+|\*))?[hlLzZjpt]*[diouxXeEfFgGcrs%]')
RE_PYTHON_BRACE = re.compile(r'\{([_a-zA-Z0-9\s\.\:\[\]]*)\}')
RE_REPEATED_WORD = re.compile(r'\b(\w+)\s+\1\b', re.IGNORECASE)
RE_URL = re.compile(r'(?:ht|f)tps?://[^"<> \t\n\r]+|www\.[^"<> \t\n\r]+|(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}/[^"<> \t\n\r]*')
RE_EMAIL = re.compile(r'[\w\.-]+@[\w\.-]+')
RE_NUMBER = re.compile(r'\d+(?:\.\d+)?')
HTML_TAGS_WHITELIST = {
    'a', 'abbr', 'acronym', 'address', 'area', 'article', 'aside', 'audio', 'b', 'base', 'bdi', 'bdo',
    'blockquote', 'body', 'br', 'button', 'canvas', 'caption', 'cite', 'code', 'col', 'colgroup', 'data',
    'datalist', 'dd', 'del', 'details', 'dfn', 'dialog', 'div', 'dl', 'dt', 'em', 'embed', 'fieldset',
    'figcaption', 'figure', 'footer', 'form', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'head', 'header', 'hr',
    'html', 'i', 'iframe', 'img', 'input', 'ins', 'kbd', 'label', 'legend', 'li', 'link', 'main', 'map',
    'mark', 'meta', 'meter', 'nav', 'noscript', 'object', 'ol', 'optgroup', 'option', 'output', 'p', 'param',
    'picture', 'pre', 'progress', 'q', 'rp', 'rt', 'ruby', 's', 'samp', 'script', 'section', 'select', 'small',
    'source', 'span', 'strong', 'style', 'sub', 'summary', 'sup', 'svg', 'table', 'tbody', 'td', 'template',
    'textarea', 'tfoot', 'th', 'thead', 'time', 'title', 'tr', 'track', 'u', 'ul', 'var', 'video', 'wbr'
}
RE_HTML_TAG = re.compile(r'</?(' + '|'.join(HTML_TAGS_WHITELIST) + r')\b[^>]*>', re.IGNORECASE)
NUMBER_WORD_MAP = {
    '0': {
        'zero', 'null', 'cero', 'zéro', 'ноль', '零', '〇', 'rei', 'zero', '영', '공'},
    '1': {
        'one', 'first', '1st', 'eins', 'uno', 'un', 'une', 'um', 'один', '一', '壹', '①', '❶', 'ichi', 'hana', 'il'},
    '2': {
        'two', 'second', '2nd', 'zwei', 'dos', 'deux', 'dois', 'два', '二', '贰', '②', '❷', '两', 'ni', 'dul', 'i'},
    '3': {
        'three', 'third', '3rd', 'drei', 'tres', 'trois', 'três', 'три', '三', '叁', '③', '❸', 'san', 'set', 'sam'},
    '4': {
        'four', 'fourth', '4th', 'vier', 'cuatro', 'quatre', 'quatro', 'четыре', '四', '肆', '④', '❹', 'shi', 'yon', 'net', 'sa'},
    '5': {
        'five', 'fifth', '5th', 'fünf', 'cinco', 'cinq', 'пять', '五', '伍', '⑤', '❺', 'go', 'daseot', 'o'},
    '6': {
        'six', 'sixth', '6th', 'sechs', 'seis', 'six', 'шесть', '六', '陆', '⑥', '❻', 'roku', 'yeoseot', 'yuk'},
    '7': {
        'seven', 'seventh', '7th', 'sieben', 'siete', 'sept', 'sete', 'семь', '七', '柒', '⑦', '❼', 'shichi', 'nana', 'ilgop', 'chil'},
    '8': {
        'eight', 'eighth', '8th', 'acht', 'ocho', 'huit', 'oito', 'восемь', '八', '捌', '⑧', '❽', 'hachi', 'yeodeol', 'pal'},
    '9': {
        'nine', 'ninth', '9th', 'neun', 'nueve', 'neuf', 'nove', 'девять', '九', '玖', '⑨', '❾', 'kyu', 'ku', 'ahop', 'gu'},
    '10': {
        'ten', 'tenth', '10th', 'zehn', 'diez', 'dix', 'dez', 'десять', '十', '拾', '⑩', '❿', 'ju', 'yeol', 'sip'}
}

def _has_case(char):
    return char.lower() != char.upper()


def _get_starting_cased_char(s):
    stripped_s = s.lstrip()
    if stripped_s and _has_case(stripped_s[0]):
        return stripped_s[0]
    return None


def check_leading_whitespace(source, target):
    """检查开头空格"""
    whitespace_chars = ' \t'
    src_has = source.lstrip(whitespace_chars) != source
    tgt_has = target.lstrip(whitespace_chars) != target

    if src_has and not tgt_has:
        return "Missing leading whitespace."
    if not src_has and tgt_has:
        return "Extra leading whitespace."
    return None


def check_trailing_whitespace(source, target):
    """检查结尾空格"""
    whitespace_chars = ' \t'
    src_has = source.rstrip('\n\r').endswith(' ') or source.rstrip('\n\r').endswith('\t')
    tgt_has = target.rstrip('\n\r').endswith(' ') or target.rstrip('\n\r').endswith('\t')

    if src_has and not tgt_has:
        tgt_stripped = target.rstrip()
        if tgt_stripped:
            last_char = tgt_stripped[-1]
            full_width_puncts = {'：', '。', '？', '！', '，', '；'}
            if last_char in full_width_puncts:
                return None
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

    ellipses = ["...", "…", "……", "。。。"]
    src_has_ellipsis = any(temp_s.endswith(e) for e in ellipses)
    tgt_has_ellipsis = any(t_strip.endswith(e) for e in ellipses)

    if src_has_ellipsis and tgt_has_ellipsis:
        return None
    if src_has_ellipsis != tgt_has_ellipsis:
        return "Missing ending ellipsis." if src_has_ellipsis else "Extra ending ellipsis."

    s_char = temp_s[-1]
    t_char = t_strip[-1]

    s_is_punc = s_char in ALL_PUNC_KEYS or s_char in ALL_PUNC_VALUES
    t_is_punc = t_char in ALL_PUNC_KEYS or t_char in ALL_PUNC_VALUES

    if s_is_punc != t_is_punc:
        if not s_is_punc and t_is_punc:
            allowed_closing_brackets = {')', ']', '}', '）', '】', '>', '》'}
            if t_char in allowed_closing_brackets:
                opening_brackets = {
                    '(': ')', '[': ']', '{': '}',
                    '（': '）', '【': '】', '<': '>', '《': '》'
                }
                reverse_map = {v: k for k, v in opening_brackets.items()}
                expected_open = reverse_map.get(t_char)

                if expected_open:
                    open_count = t_strip.count(expected_open)
                    close_count = t_strip.count(t_char)
                    if open_count > 0 and open_count == close_count:
                        return None

            return "Extra ending punctuation."

        if s_is_punc and not t_is_punc:
            return "Missing ending punctuation."

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


def check_repeated_words(source, target):
    """检查译文中是否有重复的单词，如 'the the'"""
    if RE_REPEATED_WORD.search(target):
        match = RE_REPEATED_WORD.search(target)
        return f"Repeated word: '{match.group(1)}'"
    return None


def check_newline_count(source, target):
    """检查换行符数量是否一致"""
    src_count = source.count('\n')
    tgt_count = target.count('\n')
    if src_count != tgt_count:
        return f"Newline count mismatch (source: {src_count}, target: {tgt_count})."
    return None



def check_quotes(source, target, mode='flexible'):
    """检查单引号和双引号"""
    single_quote_variants = {"'", "‘", "’", "「", "」"}
    double_quote_variants = {'"', "“", "”", "『", "』", "«", "»", "„"}

    def get_quote_counts(text):
        apostrophe_pattern = re.compile(r"(?<!['’])\b\w+(?:['’]\w+|s['’])(?![\w'’])", re.IGNORECASE)
        text_without_apostrophes = apostrophe_pattern.sub('', text)
        single_count = sum(text_without_apostrophes.count(q) for q in single_quote_variants)
        double_count = sum(text_without_apostrophes.count(q) for q in double_quote_variants)
        return single_count, double_count

    src_single_count, src_double_count = get_quote_counts(source)
    tgt_single_count, tgt_double_count = get_quote_counts(target)

    if mode == 'strict':
        errors = []
        if src_single_count != tgt_single_count:
            errors.append(f"Single quotes mismatch (source: {src_single_count}, target: {tgt_single_count})")
        if src_double_count != tgt_double_count:
            errors.append(f"Double quotes mismatch (source: {src_double_count}, target: {tgt_double_count})")
        return " | ".join(errors) if errors else None

    elif mode == 'flexible':
        # 灵活模式：只比较引号总数
        src_total_quotes = src_single_count + src_double_count
        tgt_total_quotes = tgt_single_count + tgt_double_count

        if src_total_quotes != tgt_total_quotes:
            return f"Total quote count mismatch (source: {src_total_quotes}, target: {tgt_total_quotes})"

    return None


def strip_accelerators(text, marker):
    if not marker or marker not in text:
        return text
    pattern_in_parens = re.compile(r'\s*\(' + re.escape(marker) + r'.\)')
    cleaned_text = pattern_in_parens.sub('', text)
    pattern_prefix = re.compile(r'(?<!' + re.escape(marker) + r')' + re.escape(marker) + r'(\w)')
    cleaned_text = pattern_prefix.sub(r'\1', cleaned_text)
    return cleaned_text


def check_accelerators(source, target, marker):
    """检查加速键标记符的数量是否一致，并正确处理上下文。"""
    if not marker:
        return None

    pattern = re.compile(r'(?<!' + re.escape(marker) + r')' + re.escape(marker) + r'\w')
    src_count = len(pattern.findall(source))
    tgt_count = len(pattern.findall(target))
    if src_count != tgt_count:
        return f"Accelerator '{marker}' count mismatch (source: {src_count}, target: {tgt_count})."
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
    def get_valid_printf_matches(text):
        matches = []
        for m in RE_PRINTF.finditer(text):
            full_match = m.group(0)
            # 过滤掉像 "% abc" 这样的误判
            if re.fullmatch(r'%\s+[a-zA-Z]', full_match):
                # 安全检查边界
                if m.end() < len(text) and text[m.end()].isalpha():
                    continue
            matches.append(full_match)
        return matches

    src_fmt = get_valid_printf_matches(source)
    tgt_fmt = get_valid_printf_matches(target)

    missing, extra = _compare_counts(src_fmt, tgt_fmt)
    if missing or extra:
        error_parts = []
        if missing:
            error_parts.append(f"Missing: {', '.join(missing)}")
        if extra:
            error_parts.append(f"Extra: {', '.join(extra)}")
        return f"Printf mismatch ({' | '.join(error_parts)})"
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
    """检查 URL 和 Email 是否匹配"""
    errors = []

    # --- URL 检查 ---
    src_urls = set(RE_URL.findall(source))
    tgt_urls = set(RE_URL.findall(target))

    if src_urls != tgt_urls:
        missing_urls = src_urls - tgt_urls
        extra_urls = tgt_urls - src_urls

        error_parts = []
        if missing_urls:
            error_parts.append(f"Missing: {', '.join(missing_urls)}")
        if extra_urls:
            error_parts.append(f"Extra: {', '.join(extra_urls)}")

        errors.append(f"URL mismatch ({' | '.join(error_parts)})")

    # --- Email 检查 ---
    src_emails = set(RE_EMAIL.findall(source))
    tgt_emails = set(RE_EMAIL.findall(target))

    if src_emails != tgt_emails:
        missing_emails = src_emails - tgt_emails
        extra_emails = tgt_emails - src_emails

        error_parts = []
        if missing_emails:
            error_parts.append(f"Missing: {', '.join(missing_emails)}")
        if extra_emails:
            error_parts.append(f"Extra: {', '.join(extra_emails)}")

        errors.append(f"Email mismatch ({' | '.join(error_parts)})")

    return " | ".join(errors) if errors else None


def check_numbers(source, target, mode='loose'):
    # 1. 预处理：清理干扰项
    src_clean = RE_PYTHON_BRACE.sub('', source)
    src_clean = RE_PRINTF.sub('', src_clean)
    tgt_clean = RE_PYTHON_BRACE.sub('', target)
    tgt_clean = RE_PRINTF.sub('', tgt_clean)

    # 2. 提取阿拉伯数字
    # 即使在严格模式下，也先处理一下英文序数词后缀(1st->1)，防止误报
    ordinal_re = re.compile(r'(\d+)(st|nd|rd|th)\b', re.IGNORECASE)
    src_clean = ordinal_re.sub(r'\1', src_clean)
    tgt_clean = ordinal_re.sub(r'\1', tgt_clean)

    src_nums = RE_NUMBER.findall(src_clean)
    tgt_nums = RE_NUMBER.findall(tgt_clean)

    # 3. 计数比较
    src_counter = Counter(src_nums)
    tgt_counter = Counter(tgt_nums)

    # 如果完全匹配，直接通过
    if src_counter == tgt_counter:
        return None

    # 计算差异
    missing = []
    extra = []

    all_nums = set(src_counter.keys()) | set(tgt_counter.keys())
    for num in all_nums:
        diff = src_counter[num] - tgt_counter[num]
        if diff > 0:
            is_exempt = False
            if mode == 'loose' and num in NUMBER_WORD_MAP:
                possible_words = NUMBER_WORD_MAP[num]
                for word in possible_words:
                    if word.lower() in target.lower():
                        is_exempt = True
                        break

            if not is_exempt:
                missing.extend([num] * diff)

        elif diff < 0:
            extra.extend([num] * abs(diff))

    if missing or extra:
        error_parts = []
        if missing:
            error_parts.append(f"Missing: {', '.join(missing)}")
        if extra:
            error_parts.append(f"Extra: {', '.join(extra)}")
        return f"Numbers mismatch ({' | '.join(error_parts)})"

    return None


def check_brackets(source, target):
    """检查括号是否成对且数量一致"""
    bracket_groups = [
        ('(', ')', '（', '）', 'Parentheses ()'),
        ('[', ']', '【', '】', 'Square Brackets []'),
        ('{', '}', None, None, 'Curly Braces {}'),
    ]

    # 使用全局正则移除 HTML 标签
    s_plural_re = re.compile(r'\(s\)', re.IGNORECASE)
    source_clean = s_plural_re.sub('', source)
    target_clean = s_plural_re.sub('', target)

    errors = []

    for en_open, en_close, cn_open, cn_close, desc in bracket_groups:


        # 1. 计算原文中的括号总数
        src_open_count = source_clean.count(en_open) + (source_clean.count(cn_open) if cn_open else 0)

        # 2. 计算译文中的括号总数
        tgt_open_count = target_clean.count(en_open) + (target_clean.count(cn_open) if cn_open else 0)
        tgt_close_count = target_clean.count(en_close) + (target_clean.count(cn_close) if cn_close else 0)

        # 3. 检查译文自身是否配对
        if tgt_open_count != tgt_close_count:
            errors.append(f"Unbalanced {desc} in target")
            continue

        # 4. 检查数量是否与原文一致
        if src_open_count != tgt_open_count:
            if tgt_open_count > src_open_count:
                pass
            else:
                errors.append(f"Count of {desc} differs: source {src_open_count}, target {tgt_open_count}")

    return " | ".join(errors) if errors else None


def check_double_space(source, target):
    if "  " in target and "  " not in source:
        return "Translation contains double spaces"
    return None


def check_html_tags(source, target):
    def get_valid_tags(text):
        return [html.escape(m.group(0)) for m in RE_HTML_TAG.finditer(text)]

    src_tags = get_valid_tags(source)
    tgt_tags = get_valid_tags(target)

    missing, extra = _compare_counts(src_tags, tgt_tags)

    if missing or extra:
        error_parts = []
        if missing:
            error_parts.append(f"Missing: {', '.join(missing)}")
        if extra:
            error_parts.append(f"Extra: {', '.join(extra)}")
        return f"HTML Tag mismatch ({' | '.join(error_parts)})"
    return None