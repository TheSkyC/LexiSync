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

def format_file_size(size_bytes: int) -> str:
    if size_bytes == 0:
        return "0 B"
    size_names = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    import math
    i = math.floor(math.log(size_bytes, 1024))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_names[i]}"