# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox,
    QFrame, QSizePolicy, QTextEdit
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QTextCharFormat, QColor, QFont, QTextCursor
import re
from .newline_text_edit import NewlineTextEdit
from utils.localization import _
from services.validation_service import placeholder_regex

class DetailsPanel(QWidget):
    apply_translation_signal = Signal()
    apply_comment_signal = Signal()
    toggle_ignore_signal = Signal(bool)
    toggle_reviewed_signal = Signal(bool)
    ai_translate_signal = Signal()
    translation_text_changed_signal = Signal()
    translation_focus_out_signal = Signal()
    comment_focus_out_signal = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.app_instance = parent
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Original Text Display
        layout.addWidget(QLabel(_("Original (Ctrl+Shift+C to copy):")))
        self.original_text_display = NewlineTextEdit() # 在这里创建
        self.original_text_display.setReadOnly(True)
        self.original_text_display.setLineWrapMode(NewlineTextEdit.WidgetWidth)
        self.original_text_display.setFixedHeight(70)
        self.original_text_display.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(self.original_text_display)

        # Translation Edit Text
        layout.addWidget(QLabel(_("Translation (Ctrl+Shift+V to paste):")))
        self.translation_edit_text = NewlineTextEdit()
        self.translation_edit_text.setLineWrapMode(NewlineTextEdit.WidgetWidth)
        self.translation_edit_text.setFixedHeight(100)
        self.translation_edit_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.translation_edit_text.textChanged.connect(self.translation_text_changed_signal.emit)
        self.translation_edit_text.focusOutEvent = self._translation_focus_out_event
        layout.addWidget(self.translation_edit_text)

        # Translation Actions
        trans_actions_frame = QFrame()
        trans_actions_layout = QHBoxLayout(trans_actions_frame)
        trans_actions_layout.setContentsMargins(0, 0, 0, 0)
        self.apply_btn = QPushButton(_("Apply Translation"))
        self.apply_btn.clicked.connect(self.apply_translation_signal.emit)
        self.apply_btn.setEnabled(False)
        trans_actions_layout.addWidget(self.apply_btn)
        trans_actions_layout.addStretch(1)
        self.ai_translate_current_btn = QPushButton(_("AI Translate Selected"))
        self.ai_translate_current_btn.clicked.connect(self.ai_translate_signal.emit)
        self.ai_translate_current_btn.setEnabled(False)
        trans_actions_layout.addWidget(self.ai_translate_current_btn)
        layout.addWidget(trans_actions_frame)

        # Comment Edit Text
        layout.addWidget(QLabel(_("Comment:")))
        self.comment_edit_text = NewlineTextEdit()
        self.comment_edit_text.setLineWrapMode(NewlineTextEdit.WidgetWidth)
        self.comment_edit_text.setFixedHeight(70)
        self.comment_edit_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.comment_edit_text.focusOutEvent = self._comment_focus_out_event
        layout.addWidget(self.comment_edit_text)

        # Comment Actions
        comment_actions_frame = QFrame()
        comment_actions_layout = QHBoxLayout(comment_actions_frame)
        comment_actions_layout.setContentsMargins(0, 0, 0, 0)
        self.apply_comment_btn = QPushButton(_("Apply Comment"))
        self.apply_comment_btn.clicked.connect(self.apply_comment_signal.emit)
        self.apply_comment_btn.setEnabled(False)
        comment_actions_layout.addWidget(self.apply_comment_btn)
        comment_actions_layout.addStretch(1)
        layout.addWidget(comment_actions_frame)

        # Status Checkboxes
        status_frame = QFrame()
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(0, 0, 0, 0)
        self.ignore_checkbox = QCheckBox(_("Ignore this string"))
        self.ignore_checkbox.stateChanged.connect(lambda state: self.toggle_ignore_signal.emit(bool(state)))
        self.ignore_checkbox.setEnabled(False)
        status_layout.addWidget(self.ignore_checkbox)
        self.reviewed_checkbox = QCheckBox(_("Reviewed"))
        self.reviewed_checkbox.stateChanged.connect(lambda state: self.toggle_reviewed_signal.emit(bool(state)))
        self.reviewed_checkbox.setEnabled(False)
        status_layout.addWidget(self.reviewed_checkbox)
        status_layout.addStretch(1)
        layout.addWidget(status_frame)

        layout.addStretch(1)

        self.setup_text_formats()

    def setup_text_formats(self):
        # Placeholder format
        self.placeholder_format = QTextCharFormat()
        self.placeholder_format.setForeground(QColor("orange red"))

        # Placeholder missing/extra format
        self.placeholder_error_format = QTextCharFormat()
        self.placeholder_error_format.setBackground(QColor("#FFDDDD"))
        self.placeholder_error_format.setForeground(QColor("red"))

        # Whitespace format
        self.whitespace_format = QTextCharFormat()
        self.whitespace_format.setBackground(QColor("#DDEEFF"))
        self.newline_format = QTextCharFormat()
        self.newline_format.setForeground(QColor("#007ACC"))
        self.newline_format.setFontItalic(True)

    def apply_placeholder_highlights(self, original_text_widget, translation_text_widget, original_placeholders, translated_placeholders):
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
        regex = placeholder_regex
        start_pos = 0
        while True:
            match = regex.search(document.toPlainText(), start_pos)
            if match and match.group(0) == pattern:
                cursor.setPosition(match.start())
                cursor.setPosition(match.end(), QTextCursor.KeepAnchor)
                cursor.mergeCharFormat(text_format)
                start_pos = match.end()
            elif match:
                start_pos = match.end()
            else:
                break

    def _apply_whitespace_highlights(self, document):
        for i in range(document.blockCount()):
            block = document.findBlockByNumber(i)
            text = block.text()
            cursor = QTextCursor(block)
            leading_ws_match = re.match(r'^\s+', text)
            if leading_ws_match:
                cursor.setPosition(block.position())
                cursor.setPosition(block.position() + leading_ws_match.end(), QTextCursor.KeepAnchor)
                cursor.mergeCharFormat(self.whitespace_format)
            trailing_ws_match = re.search(r'\s+$', text)
            if trailing_ws_match:
                cursor.setPosition(block.position() + trailing_ws_match.start())
                cursor.setPosition(block.position() + trailing_ws_match.end(), QTextCursor.KeepAnchor)
                cursor.mergeCharFormat(self.whitespace_format)

    def _translation_focus_out_event(self, event):
        self.translation_focus_out_signal.emit()
        QTextEdit.focusOutEvent(self.translation_edit_text, event)

    def _comment_focus_out_event(self, event):
        self.comment_focus_out_signal.emit()
        QTextEdit.focusOutEvent(self.comment_edit_text, event)

    def update_ui_texts(self):
        self.findChild(QLabel, _("Original (Ctrl+Shift+C to copy):")).setText(_("Original (Ctrl+Shift+C to copy):"))
        self.findChild(QLabel, _("Translation (Ctrl+Shift+V to paste):")).setText(_("Translation (Ctrl+Shift+V to paste):"))
        self.findChild(QLabel, _("Comment:")).setText(_("Comment:"))
        self.apply_btn.setText(_("Apply Translation"))
        self.ai_translate_current_btn.setText(_("AI Translate Selected"))
        self.apply_comment_btn.setText(_("Apply Comment"))
        self.ignore_checkbox.setText(_("Ignore this string"))
        self.reviewed_checkbox.setText(_("Reviewed"))
