# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import regex as re

non_linguistic_chars_regex = re.compile(r'[\p{P}\p{N}\p{S}\p{Z}]')
placeholder_regex = re.compile(r'\{([^{}]+)\}')

def get_linguistic_length(text: str) -> int:
    if not text:
        return 0
    text_no_placeholders = placeholder_regex.sub('', text)
    linguistic_text = non_linguistic_chars_regex.sub('', text_no_placeholders)
    return len(linguistic_text)


def generate_ngrams(text: str, min_n: int = 1, max_n: int = 5) -> list[str]:
    """
    生成文本的 N-gram 列表。
    """
    if not text:
        return []

    words = re.findall(r'\b\w+\b', text)
    if not words:
        return []

    ngrams = set()
    count = len(words)

    for n in range(min_n, max_n + 1):
        for i in range(count - n + 1):
            gram = " ".join(words[i:i + n])
            ngrams.add(gram)

    return list(ngrams)

def format_file_size(size_bytes: int) -> str:
    if size_bytes == 0:
        return "0 B"
    size_names = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    import math
    i = math.floor(math.log(size_bytes, 1024))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_names[i]}"