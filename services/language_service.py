# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import langid


def detect_source_language(strings: list[str]) -> str:
    if not strings:
        return "en"

    meaningful_strings = [s for s in strings if s and len(s.strip()) > 10 and not s.strip().isnumeric()]

    sample_pool = meaningful_strings[:300] if meaningful_strings else strings[:50]

    text_block = "\n".join(sample_pool)
    if not text_block:
        return "en"

    try:
        lang_code, confidence = langid.classify(text_block)
        # 统一中文代码
        if lang_code == "zh":
            return "zh"
        return lang_code
    except Exception:
        return "en"
