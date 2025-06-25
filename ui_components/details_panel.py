# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox,
    QFrame, QSizePolicy, QTextEdit, QToolButton
)
from PySide6.QtCore import Qt, Signal, QPropertyAnimation
from PySide6.QtGui import QTextCharFormat, QColor, QFont, QTextCursor
import re
from .newline_text_edit import NewlineTextEdit
from utils.localization import _
from services.validation_service import placeholder_regex
from .po_comment_highlighter import PoCommentHighlighter

class DetailsPanel(QWidget):
    apply_translation_signal = Signal()
    apply_comment_signal = Signal()
    ai_translate_signal = Signal()
    translation_text_changed_signal = Signal()
    translation_focus_out_signal = Signal()
    apply_po_comment_signal = Signal()
    comment_focus_out_signal = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.app_instance = parent
        self._ui_initialized = False
        self.animation = None
        self._collapsible_content_height = 0
        self.setup_ui()

    def setup_ui(self):
        if self._ui_initialized:
            return
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        self.original_label = QLabel(_("Original:"))
        self.original_label.setObjectName("original_label")
        layout.addWidget(self.original_label)
        self.original_text_display = NewlineTextEdit()
        self.original_text_display.setReadOnly(True)
        self.original_text_display.setLineWrapMode(NewlineTextEdit.WidgetWidth)
        self.original_text_display.setFixedHeight(70)
        self.original_text_display.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(self.original_text_display)

        self.translation_label = QLabel(_("Translation:"))
        self.translation_label.setObjectName("translation_label")
        layout.addWidget(self.translation_label)
        self.translation_edit_text = NewlineTextEdit()
        self.translation_edit_text.setLineWrapMode(NewlineTextEdit.WidgetWidth)
        self.translation_edit_text.setFixedHeight(100)
        self.translation_edit_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.translation_edit_text.textChanged.connect(self.translation_text_changed_signal.emit)
        self.translation_edit_text.focusOutEvent = self._translation_focus_out_event
        layout.addWidget(self.translation_edit_text)

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
        layout.addWidget(trans_actions_frame)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)

        self.toggle_button = QToolButton()
        self.toggle_button.setObjectName("toggle_button")
        self.toggle_button.setText(_("Comments && Status"))
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(True)
        self.toggle_button.setStyleSheet("QToolButton { border: none; font-weight: bold; }")
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle_button.setArrowType(Qt.DownArrow)
        self.toggle_button.toggled.connect(self.on_toggle_collapse)
        layout.addWidget(self.toggle_button)

        self.collapsible_widget = QWidget()
        self.collapsible_layout = QVBoxLayout(self.collapsible_widget)
        self.collapsible_layout.setContentsMargins(10, 0, 0, 0)
        self.collapsible_layout.setSpacing(5)
        layout.addWidget(self.collapsible_widget)

        self.comment_label = QLabel(_("Comment:"))
        self.comment_label.setObjectName("comment_label")
        self.collapsible_layout.addWidget(self.comment_label)

        self.comment_edit_text = NewlineTextEdit()
        self.comment_edit_text.setObjectName("comment_edit_text")
        self.comment_edit_text.setLineWrapMode(NewlineTextEdit.WidgetWidth)
        self.comment_edit_text.setFixedHeight(70)
        self.comment_edit_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.comment_edit_text.focusOutEvent = self._comment_focus_out_event
        self.collapsible_layout.addWidget(self.comment_edit_text)
        self.highlighter = PoCommentHighlighter(self.comment_edit_text.document())

        comment_actions_frame = QFrame()
        comment_actions_layout = QHBoxLayout(comment_actions_frame)
        comment_actions_layout.setContentsMargins(0, 0, 0, 0)
        self.apply_comment_btn = QPushButton(_("Apply Comment"))
        self.apply_comment_btn.setObjectName("apply_comment_btn")
        self.apply_comment_btn.clicked.connect(self.apply_comment_signal.emit)
        self.apply_comment_btn.setEnabled(False)
        comment_actions_layout.addWidget(self.apply_comment_btn)
        comment_actions_layout.addStretch(1)
        self.collapsible_layout.addWidget(comment_actions_frame)

        status_frame = QFrame()
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(0, 0, 0, 0)
        self.ignore_checkbox = QCheckBox(_("Ignore this string"))
        self.ignore_checkbox.setObjectName("ignore_checkbox")
        self.ignore_checkbox.setEnabled(False)
        status_layout.addWidget(self.ignore_checkbox)
        self.reviewed_checkbox = QCheckBox(_("Reviewed"))
        self.reviewed_checkbox.setObjectName("reviewed_checkbox")
        self.reviewed_checkbox.setEnabled(False)
        status_layout.addWidget(self.reviewed_checkbox)
        status_layout.addStretch(1)
        self.collapsible_layout.addWidget(status_frame)

        #layout.addStretch(1)

        self.setup_text_formats()
        self._ui_initialized = True
        self.collapsible_widget.setVisible(True)
        self.collapsible_widget.layout().activate()
        self._collapsible_content_height = self.collapsible_widget.sizeHint().height()
        if not self.toggle_button.isChecked():
            self.collapsible_widget.setMaximumHeight(0)
            self.collapsible_widget.setVisible(False)

    def on_toggle_collapse(self, checked):
        self.toggle_button.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)

        if hasattr(self, 'animation') and self.animation and self.animation.state() == QPropertyAnimation.State.Running:
            self.animation.stop()

        self.animation = QPropertyAnimation(self.collapsible_widget, b"maximumHeight")
        self.animation.setDuration(250)

        if checked:
            self.collapsible_widget.setVisible(True)
            self.animation.setStartValue(0)
            self.animation.setEndValue(self._collapsible_content_height)
            self.animation.finished.connect(self._on_expand_animation_finished)
        else:
            self.animation.setStartValue(self.collapsible_widget.height())
            self.animation.setEndValue(0)
            self.animation.finished.connect(self._on_collapse_animation_finished)

        self.animation.start()

    def _on_expand_animation_finished(self):
        if self.toggle_button.isChecked():
            self.collapsible_widget.setMaximumHeight(16777215)
        if hasattr(self, 'animation'):
            self.animation = None

    def _on_collapse_animation_finished(self):
        if not self.toggle_button.isChecked():
            self.collapsible_widget.setVisible(False)
        if hasattr(self, 'animation'):
            self.animation = None

    def setup_text_formats(self):
        self.placeholder_format = QTextCharFormat()
        self.placeholder_format.setForeground(QColor("orange red"))

        self.placeholder_error_format = QTextCharFormat()
        self.placeholder_error_format.setBackground(QColor("#FFDDDD"))
        self.placeholder_error_format.setForeground(QColor("red"))

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
        self.findChild(QLabel, "original_label").setText(_("Original:"))
        self.findChild(QLabel, "translation_label").setText(_("Translation:"))
        self.findChild(QPushButton, "apply_btn").setText(_("Apply Translation"))
        self.findChild(QPushButton, "ai_translate_current_btn").setText(_("AI Translate Selected"))
        self.findChild(QToolButton, "toggle_button").setText(_("Comments & Status"))
        self.findChild(QLabel, "comment_label").setText(_("Comment:"))
        self.findChild(QPushButton, "apply_comment_btn").setText(_("Apply Comment"))

        ignore_label_text = _("Ignore this string")
        if self.ignore_checkbox.isChecked() and self.app_instance.current_selected_ts_id:
            ts_obj = self.app_instance._find_ts_obj_by_id(self.app_instance.current_selected_ts_id)
            if ts_obj and ts_obj.was_auto_ignored:
                ignore_label_text += _(" (Auto)")
        self.findChild(QCheckBox, "ignore_checkbox").setText(ignore_label_text)

        self.findChild(QCheckBox, "reviewed_checkbox").setText(_("Reviewed"))