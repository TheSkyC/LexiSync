# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from enum import Enum, auto


class WarningType(Enum):
    # --- 占位符相关 ---
    PLACEHOLDER_MISSING = auto()  # 译文中缺少原文中的占位符
    PLACEHOLDER_EXTRA = auto()  # 译文中出现原文没有的占位符
    PLACEHOLDER_NAME_MISMATCH = auto()  # 占位符名称不一致

    # --- 格式与结构 ---
    CAPITALIZATION_MISMATCH = auto()  # 首字母大小写不匹配
    LEADING_WHITESPACE_MISMATCH = auto()  # 前导空格不匹配
    TRAILING_WHITESPACE_MISMATCH = auto()  # 后导空格不匹配
    LINE_COUNT_MISMATCH = auto()  # 换行符数量不匹配
    PUNCTUATION_MISMATCH_START = auto()  # 开头标点不匹配
    PUNCTUATION_MISMATCH_END = auto()  # 结尾标点不匹配

    # --- 长度相关 ---
    LENGTH_DEVIATION_MINOR = auto()  # 译文长度与原文差异 50%-79%
    LENGTH_DEVIATION_MAJOR = auto()  # 译文长度与原文差异 >= 80%
    TRANSLATION_EMPTY_BUT_ORIGINAL_NOT = auto()  # 译文为空但原文不为空
    ORIGINAL_EMPTY_BUT_TRANSLATION_NOT = auto()  # 原文为空但译文不为空

    # --- PO 文件相关 ---
    FUZZY_TRANSLATION = auto()  # PO文件导入的 fuzzy 标记

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
        if self == WarningType.LINE_COUNT_MISMATCH:
            return _("Line Count Mismatch")
        if self == WarningType.PUNCTUATION_MISMATCH_START:
            return _("Starting Punctuation Mismatch")
        if self == WarningType.PUNCTUATION_MISMATCH_END:
            return _("Ending Punctuation Mismatch")
        if self == WarningType.LENGTH_DEVIATION_MINOR:
            return _("Length Deviation (Minor)")
        if self == WarningType.LENGTH_DEVIATION_MAJOR:
            return _("Length Deviation (Major)")
        if self == WarningType.TRANSLATION_EMPTY_BUT_ORIGINAL_NOT:
            return _("Translation Empty")
        if self == WarningType.ORIGINAL_EMPTY_BUT_TRANSLATION_NOT:
            return _("Original Empty, Translation Not")
        if self == WarningType.FUZZY_TRANSLATION:
            return _("Fuzzy Translation")
        return self.name.replace('_', ' ').title()