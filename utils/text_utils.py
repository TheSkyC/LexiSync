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