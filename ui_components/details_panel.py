# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QSizePolicy, QSplitter
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QTextCharFormat, QColor, QFont, QTextCursor
import re
from .newline_text_edit import NewlineTextEdit
from utils.localization import _
from services.validation_service import placeholder_regex


class DetailsPanel(QWidget):
    apply_translation_signal = Signal()
    ai_translate_signal = Signal()
    translation_text_changed_signal = Signal()
    translation_focus_out_signal = Signal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self.app_instance = parent
        self._ui_initialized = False
        self.setup_ui()

    def setup_ui(self):
        if self._ui_initialized:
            return
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        splitter = QSplitter(Qt.Vertical)

        # --- 原文 ---
        original_container = QWidget()
        original_layout = QVBoxLayout(original_container)
        original_layout.setContentsMargins(0, 0, 0, 0)
        original_layout.setSpacing(5)
        original_header_layout = QHBoxLayout()
        self.original_label = QLabel(_("Original:"))
        self.original_label.setObjectName("original_label")
        self.original_label.setMinimumHeight(18)

        # Context Badge
        self.context_badge = QLabel(self)
        self.context_badge.setVisible(False)
        self.context_badge.setFixedHeight(18)
        self.context_badge.setAlignment(Qt.AlignCenter)
        self.context_badge.setStyleSheet("""
            QLabel {
                background-color: #E1F5FE;
                color: #0277BD;
                border-radius: 3px;
                padding: 0px 6px;
                font-size: 10px;
                font-weight: bold;
                margin-left: 6px;
                border: 1px solid #B3E5FC;
            }
       """)

        # Format Badge
        self.format_badge = QLabel(self)
        self.format_badge.setVisible(False)
        self.format_badge.setFixedHeight(18)
        self.format_badge.setAlignment(Qt.AlignCenter)
        self.format_badge.setStyleSheet("""
            QLabel {
                background-color: #E0E0E0;
                color: #444444;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 11px;
                font-weight: bold;
                margin-left: 5px;
            }
        """)

        self.char_count_label = QLabel("")
        self.char_count_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        original_header_layout.addWidget(self.original_label)
        original_header_layout.addWidget(self.context_badge)
        original_header_layout.addWidget(self.format_badge)
        original_header_layout.addStretch()
        original_header_layout.addWidget(self.char_count_label)

        original_layout.addLayout(original_header_layout)

        self.original_text_display = NewlineTextEdit()
        self.original_text_display.setReadOnly(True)
        self.original_text_display.setLineWrapMode(NewlineTextEdit.WidgetWidth)
        self.original_text_display.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        original_layout.addWidget(self.original_text_display)

        # --- 译文 ---
        translation_container = QWidget()
        translation_layout = QVBoxLayout(translation_container)
        translation_layout.setContentsMargins(0, 0, 0, 0)
        translation_layout.setSpacing(5)
        translation_header_layout = QHBoxLayout()
        self.translation_label = QLabel(_("Translation:"))
        self.translation_label.setObjectName("translation_label")
        self.ratio_label = QLabel("")
        self.ratio_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        translation_header_layout.addWidget(self.translation_label)
        translation_header_layout.addStretch()
        translation_header_layout.addWidget(self.ratio_label)
        translation_layout.addLayout(translation_header_layout)
        self.translation_edit_text = NewlineTextEdit()
        self.translation_edit_text.setLineWrapMode(NewlineTextEdit.WidgetWidth)
        self.translation_edit_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.translation_edit_text.textChanged.connect(self.translation_text_changed_signal.emit)
        self.translation_edit_text.focusOutEvent = self._translation_focus_out_event
        translation_layout.addWidget(self.translation_edit_text)

        splitter.addWidget(original_container)
        splitter.addWidget(translation_container)
        splitter.setSizes([100, 100])
        main_layout.addWidget(splitter)
        trans_actions_frame = QFrame()
        trans_actions_layout = QHBoxLayout(trans_actions_frame)
        trans_actions_layout.setContentsMargins(0, 0, 0, 0)
        self.apply_btn = QPushButton(_("Apply Translation"))
        self.apply_btn.setObjectName("apply_btn")
        self.apply_btn.clicked.connect(self.apply_translation_signal.emit)
        self.apply_btn.setEnabled(False)
        trans_actions_layout.addWidget(self.apply_btn)
        trans_actions_layout.addStretch(1)
        self.ai_translate_current_btn = QPushButton(_("AI Translate Selected"))
        self.ai_translate_current_btn.setObjectName("ai_translate_current_btn")
        self.ai_translate_current_btn.clicked.connect(self.ai_translate_signal.emit)
        self.ai_translate_current_btn.setEnabled(False)
        trans_actions_layout.addWidget(self.ai_translate_current_btn)
        main_layout.addWidget(trans_actions_frame)

        self.setup_text_formats()
        self._ui_initialized = True

    def _translation_focus_out_event(self, event):
        self.translation_focus_out_signal.emit()
        super(NewlineTextEdit, self.translation_edit_text).focusOutEvent(event)

    def setup_text_formats(self):
        self.placeholder_format = QTextCharFormat()
        self.placeholder_format.setForeground(QColor("orange red"))

        self.placeholder_error_format = QTextCharFormat()
        self.placeholder_error_format.setBackground(QColor("#FFDDDD"))
        self.placeholder_error_format.setForeground(QColor("red"))

        self.whitespace_format = QTextCharFormat()
        self.whitespace_format.setBackground(QColor("#DDEEFF"))

        self.multi_space_format = QTextCharFormat()
        self.multi_space_format.setBackground(QColor("#FFCCFF"))

        self.newline_format = QTextCharFormat()
        self.newline_format.setForeground(QColor("#007ACC"))
        self.newline_format.setFontItalic(True)

    def apply_placeholder_highlights(self, original_text_widget, translation_text_widget, original_placeholders,
                                     translated_placeholders):
        cursor = QTextCursor(original_text_widget.document())
        cursor.select(QTextCursor.Document)
        cursor.setCharFormat(QTextCharFormat())
        cursor = QTextCursor(translation_text_widget.document())
        cursor.select(QTextCursor.Document)
        cursor.setCharFormat(QTextCharFormat())

        original_doc = original_text_widget.document()
        for p_text in original_placeholders:
            tag_format = self.placeholder_error_format if p_text not in translated_placeholders else self.placeholder_format
            self._apply_format_to_all_occurrences(original_doc, f"{{{p_text}}}", tag_format)
        self._apply_whitespace_highlights(original_doc)

        translation_doc = translation_text_widget.document()
        all_placeholders = original_placeholders.union(translated_placeholders)
        for p_text in all_placeholders:
            if p_text in original_placeholders and p_text in translated_placeholders:
                tag_format = self.placeholder_format
            elif p_text in translated_placeholders:
                tag_format = self.placeholder_error_format
            else:
                continue
            self._apply_format_to_all_occurrences(translation_doc, f"{{{p_text}}}", tag_format)
        self._apply_whitespace_highlights(translation_doc)

    def _apply_format_to_all_occurrences(self, document, pattern, text_format):
        cursor = QTextCursor(document)
        start_pos = 0
        while True:
            inner_pattern = pattern[1:-1]
            full_regex_pattern = r"\{" + re.escape(inner_pattern) + r"\}"
            match = re.search(full_regex_pattern, document.toPlainText()[start_pos:])
            if match:
                actual_start = start_pos + match.start()
                actual_end = start_pos + match.end()

                cursor.setPosition(actual_start)
                cursor.setPosition(actual_end, QTextCursor.KeepAnchor)
                cursor.mergeCharFormat(text_format)
                start_pos = actual_end
            else:
                break

    def _apply_whitespace_highlights(self, document):
        cursor = QTextCursor(document)
        multi_space_regex = re.compile(r'\s{2,}')

        for i in range(document.blockCount()):
            block = document.findBlockByNumber(i)
            text = block.text()

            # Highlight multiple spaces in the middle of the text
            for match in multi_space_regex.finditer(text):
                start, end = match.span()
                cursor.setPosition(block.position() + start)
                cursor.setPosition(block.position() + end, QTextCursor.KeepAnchor)
                cursor.mergeCharFormat(self.multi_space_format)

            # Highlight leading whitespace
            leading_ws_match = re.match(r'^\s+', text)
            if leading_ws_match:
                cursor.setPosition(block.position())
                cursor.setPosition(block.position() + leading_ws_match.end(), QTextCursor.KeepAnchor)
                cursor.mergeCharFormat(self.whitespace_format)

            # Highlight trailing whitespace
            trailing_ws_match = re.search(r'\s+$', text)
            if trailing_ws_match:
                cursor.setPosition(block.position() + trailing_ws_match.start())
                cursor.setPosition(block.position() + trailing_ws_match.end(), QTextCursor.KeepAnchor)
                cursor.mergeCharFormat(self.whitespace_format)

    def update_stats_labels(self, char_counts: tuple | None, ratios: tuple | None):
        if char_counts:
            self.char_count_label.setText(f"{char_counts[0]} | {char_counts[1]}")
        else:
            self.char_count_label.setText("")

        if ratios:
            actual_str = f"{ratios[0]:.2f}" if ratios[0] is not None else "-"
            expected_str = f"{ratios[1]:.2f}" if ratios[1] is not None else "-"
            self.ratio_label.setText(f"{actual_str} | {expected_str}")
        else:
            self.ratio_label.setText("")

    def update_ui_texts(self):
        self.findChild(QLabel, "original_label").setText(_("Original:"))
        self.findChild(QLabel, "translation_label").setText(_("Translation:"))
        self.findChild(QPushButton, "apply_btn").setText(_("Apply Translation"))
        self.findChild(QPushButton, "ai_translate_current_btn").setText(_("AI Translate Selected"))

    def update_context_badge(self, ts_obj):
        """
        Updates the context badge based on ts_obj.context (msgctxt).
        """
        if ts_obj and ts_obj.context:
            self.context_badge.setText(ts_obj.context)
            self.context_badge.setVisible(True)
        else:
            self.context_badge.setVisible(False)

    def update_format_badge(self, ts_obj):
        """
        Parses the po_comment to find format flags (e.g., python-format) and updates the badge.
        """
        if not ts_obj or not ts_obj.po_comment:
            self.format_badge.setVisible(False)
            return

        from itertools import chain

        flags = set(chain.from_iterable(
            (f.strip() for f in line.replace('#,', '').strip().split(','))
            for line in ts_obj.po_comment.splitlines()
            if line.strip().startswith('#,')
        ))

        format_map = {
            # Python
            'python-format': 'Python',
            'python-brace-format': 'Python Brace',

            # C
            'c-format': 'C',
            'c-sharp-format': 'C#',
            'objc-format': 'Objective-C',

            # Java
            'java-format': 'Java',
            'java-printf-format': 'Java Printf',

            # JavaScript/Web
            'javascript-format': 'JavaScript',
            'typescript-format': 'TypeScript',

            # Shell
            'sh-format': 'Shell',
            'bash-format': 'Bash',
            'perl-format': 'Perl',
            'perl-brace-format': 'Perl Brace',

            # PHP
            'php-format': 'PHP',

            # Qt
            'qt-format': 'Qt',
            'qt-plural-format': 'Qt Plural',

            # Ruby
            'ruby-format': 'Ruby',

            # Lisp
            'lisp-format': 'Lisp',
            'scheme-format': 'Scheme',

            # Others
            'elisp-format': 'Emacs Lisp',
            'librep-format': 'LibRep',
            'smalltalk-format': 'Smalltalk',
            'tcl-format': 'Tcl',
            'awk-format': 'AWK',
            'lua-format': 'Lua',
            'gcc-internal-format': 'GCC Internal',
            'gfc-internal-format': 'GFortran Internal',
            'boost-format': 'Boost',
        }

        found_format = next(
            (format_map[flag] for flag in flags if flag in format_map),
            next(
                (flag.replace('-format', '').capitalize()
                 for flag in flags if flag.endswith('-format')),
                None
            )
        )

        if found_format:
            self.format_badge.setText(f"{found_format} {_('Format')}")
            self.format_badge.setVisible(True)
        else:
            self.format_badge.setVisible(False)