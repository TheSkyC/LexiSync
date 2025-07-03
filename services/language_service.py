# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import langid

def detect_source_language(strings: list[str]) -> str:
    if not strings:
        return 'en'
    meaningful_strings = [
        s for s in strings
        if s and len(s.strip()) > 10 and not s.strip().isnumeric()
    ]
    if not meaningful_strings:
        meaningful_strings = strings[:50]
    text_block = "\n".join(meaningful_strings)
    if not text_block:
        return 'en'

    try:
        lang_code, confidence = langid.classify(text_block)
        return lang_code
    except Exception:
        return 'en'