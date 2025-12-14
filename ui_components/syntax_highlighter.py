# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
from PySide6.QtCore import QRegularExpression
import re
from logging import getLogger
logger = getLogger(__name__)


class TranslationHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.valid_placeholders = set()
        self.missing_placeholders = set()
        self.glossary_matches = []

        self.fmt_placeholder_ok = QTextCharFormat()
        self.fmt_placeholder_ok.setForeground(QColor("orange red"))

        self.fmt_placeholder_error = QTextCharFormat()
        self.fmt_placeholder_error.setBackground(QColor("#FFDDDD"))
        self.fmt_placeholder_error.setForeground(QColor("red"))

        self.fmt_whitespace = QTextCharFormat()
        self.fmt_whitespace.setBackground(QColor("#DDEEFF"))

        self.fmt_multi_space = QTextCharFormat()
        self.fmt_multi_space.setBackground(QColor("#FFCCFF"))

        self.fmt_glossary = QTextCharFormat()
        self.fmt_glossary.setUnderlineColor(QColor("teal"))
        self.fmt_glossary.setUnderlineStyle(QTextCharFormat.WaveUnderline)

    def update_data(self, valid_placeholders, missing_placeholders=None):
        missing = missing_placeholders or set()
        if self.valid_placeholders == valid_placeholders and self.missing_placeholders == missing:
            return

        self.valid_placeholders = valid_placeholders
        self.missing_placeholders = missing
        self.rehighlight()

    def update_glossary(self, matches):
        self.glossary_matches = matches
        self.rehighlight()

    def highlightBlock(self, text):
        if self.glossary_matches:
            for match in self.glossary_matches:
                term = match['source']
                try:
                    pattern = re.compile(re.escape(term), re.IGNORECASE)
                    for m in pattern.finditer(text):
                        self.setFormat(m.start(), m.end() - m.start(), self.fmt_glossary)
                except Exception:
                    pass

        # 1. 高亮多重空格 (中间)
        expression = QRegularExpression(r'\s{2,}')
        it = expression.globalMatch(text)
        while it.hasNext():
            match = it.next()
            self.setFormat(match.capturedStart(), match.capturedLength(), self.fmt_multi_space)

        # 2. 高亮首尾空格
        leading_match = re.match(r'^\s+', text)
        if leading_match:
            self.setFormat(0, leading_match.end(), self.fmt_whitespace)

        trailing_match = re.search(r'\s+$', text)
        if trailing_match:
            self.setFormat(trailing_match.start(), len(text) - trailing_match.start(), self.fmt_whitespace)

        # 3. 高亮占位符 {x}
        expression = QRegularExpression(r'\{([^{}]+)\}')
        it = expression.globalMatch(text)
        while it.hasNext():
            match = it.next()
            content = match.captured(1)

            if content in self.missing_placeholders:
                self.setFormat(match.capturedStart(), match.capturedLength(), self.fmt_placeholder_error)
            elif content in self.valid_placeholders:
                self.setFormat(match.capturedStart(), match.capturedLength(), self.fmt_placeholder_ok)
            else:
                self.setFormat(match.capturedStart(), match.capturedLength(), self.fmt_placeholder_error)