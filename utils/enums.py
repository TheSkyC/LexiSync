# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from enum import Enum, auto


class WarningType(Enum):
    # --- 占位符相关 ---
    # 包含通用的占位符错误以及特定的代码格式化变量错误
    PLACEHOLDER_MISSING = auto()  # 译文中缺少原文中的占位符
    PLACEHOLDER_EXTRA = auto()  # 译文中出现原文没有的占位符
    PLACEHOLDER_NAME_MISMATCH = auto()  # 占位符名称不一致
    PRINTF_MISMATCH = auto()  # %s, %d 等 Printf 风格格式符不匹配
    PYTHON_BRACE_MISMATCH = auto()  # {}, {name} 等 Python 风格格式符不匹配

    # --- 格式与结构 ---
    # 包含大小写、空格、换行、标点符号及括号的成对情况
    CAPITALIZATION_MISMATCH = auto()  # 首字母大小写不匹配
    REPEATED_WORD = auto() # 有重复文本
    LEADING_WHITESPACE_MISMATCH = auto()  # 前导空格不匹配
    TRAILING_WHITESPACE_MISMATCH = auto()  # 后导空格不匹配
    DOUBLE_SPACE = auto()  # 意外的双空格
    NEWLINE_COUNT_MISMATCH = auto() # 换行符数量不匹配
    PUNCTUATION_MISMATCH_START = auto()  # 开头标点不匹配
    PUNCTUATION_MISMATCH_END = auto()  # 结尾标点不匹配
    BRACKET_MISMATCH = auto()  # 括号不成对
    QUOTE_MISMATCH = auto() # 引号不成对
    ACCELERATOR_MISMATCH = auto() #加速键不匹配

    # --- 长度相关 ---
    LENGTH_DEVIATION_MINOR = auto()  # 译文长度与原文差异略大
    LENGTH_DEVIATION_MAJOR = auto()  # 译文长度与原文差异较大
    TRANSLATION_EMPTY_BUT_ORIGINAL_NOT = auto()  # 译文为空但原文不为空
    ORIGINAL_EMPTY_BUT_TRANSLATION_NOT = auto()  # 原文为空但译文不为空

    # --- 其他 ---
    # 包含术语、实体保护（URL/Email）、数字准确性及模糊匹配状态
    GLOSSARY_MISMATCH = auto()  # 术语不匹配
    URL_MISMATCH = auto()  # URL 被错误翻译或丢失
    EMAIL_MISMATCH = auto()  # Email 被错误翻译或丢失
    NUMBER_MISMATCH = auto()  # 数字内容不一致
    FUZZY_TRANSLATION = auto()
    UNUSUAL_EXPANSION_RATIO = auto()

    def get_display_text(self):
        from utils.localization import _
        if self == WarningType.PLACEHOLDER_MISSING:
            return _("Placeholder Missing")
        if self == WarningType.PLACEHOLDER_EXTRA:
            return _("Extra Placeholder")
        if self == WarningType.CAPITALIZATION_MISMATCH:
            return _("Capitalization Mismatch")
        if self == WarningType.LEADING_WHITESPACE_MISMATCH:
            return _("Leading Whitespace Mismatch")
        if self == WarningType.TRAILING_WHITESPACE_MISMATCH:
            return _("Trailing Whitespace Mismatch")
        if self == WarningType.NEWLINE_COUNT_MISMATCH:
            return _("Line Count Mismatch")
        if self == WarningType.PUNCTUATION_MISMATCH_START:
            return _("Starting Punctuation Mismatch")
        if self == WarningType.PUNCTUATION_MISMATCH_END:
            return _("Ending Punctuation Mismatch")
        if self == WarningType.LENGTH_DEVIATION_MINOR:
            return _("Length Deviation (Minor)")
        if self == WarningType.LENGTH_DEVIATION_MAJOR:
            return _("Length Deviation (Major)")
        if self == WarningType.GLOSSARY_MISMATCH:
            return _("Glossary Mismatch")
        if self == WarningType.TRANSLATION_EMPTY_BUT_ORIGINAL_NOT:
            return _("Translation Empty")
        if self == WarningType.ORIGINAL_EMPTY_BUT_TRANSLATION_NOT:
            return _("Translated an Empty Original")
        if self == WarningType.FUZZY_TRANSLATION:
            return _("Fuzzy Translation")
        return self.name.replace('_', ' ').title()

class AIOperationType(Enum):
    TRANSLATION = auto()
    BATCH_TRANSLATION = auto()
    FIX = auto()
    BATCH_FIX = auto()