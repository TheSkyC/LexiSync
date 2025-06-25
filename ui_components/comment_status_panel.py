# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox,
    QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from .newline_text_edit import NewlineTextEdit
from .po_comment_highlighter import PoCommentHighlighter
from utils.localization import _


class CommentStatusPanel(QWidget):
    apply_comment_signal = Signal()
    comment_focus_out_signal = Signal()
    toggle_ignore_signal = Signal(bool)
    toggle_reviewed_signal = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.app_instance = parent
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        self.comment_label = QLabel(_("Comment:"))
        self.comment_label.setObjectName("comment_label")
        layout.addWidget(self.comment_label)

        self.comment_edit_text = NewlineTextEdit()
        self.comment_edit_text.setObjectName("comment_edit_text")
        self.comment_edit_text.setLineWrapMode(NewlineTextEdit.WidgetWidth)
        self.comment_edit_text.setFixedHeight(70)
        self.comment_edit_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.comment_edit_text.focusOutEvent = self._comment_focus_out_event
        layout.addWidget(self.comment_edit_text)
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
        layout.addWidget(comment_actions_frame)

        status_frame = QFrame()
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(0, 0, 0, 0)
        self.ignore_checkbox = QCheckBox(_("Ignore this string"))
        self.ignore_checkbox.setObjectName("ignore_checkbox")
        self.ignore_checkbox.stateChanged.connect(lambda state: self.toggle_ignore_signal.emit(bool(state)))
        self.ignore_checkbox.setEnabled(False)
        status_layout.addWidget(self.ignore_checkbox)
        self.reviewed_checkbox = QCheckBox(_("Reviewed"))
        self.reviewed_checkbox.setObjectName("reviewed_checkbox")
        self.reviewed_checkbox.stateChanged.connect(lambda state: self.toggle_reviewed_signal.emit(bool(state)))
        self.reviewed_checkbox.setEnabled(False)
        status_layout.addWidget(self.reviewed_checkbox)
        status_layout.addStretch(1)
        layout.addWidget(status_frame)

        layout.addStretch(1)

    def _comment_focus_out_event(self, event):
        self.comment_focus_out_signal.emit()
        super(NewlineTextEdit, self.comment_edit_text).focusOutEvent(event)

    def update_ui_texts(self):
        self.findChild(QLabel, "comment_label").setText(_("Comment:"))
        self.findChild(QPushButton, "apply_comment_btn").setText(_("Apply Comment"))
        if hasattr(self, 'ignore_checkbox'):
            current_ignore_text_key = "Ignore this string (Auto)" if (
                self.ignore_checkbox.text().endswith(_(" (Auto)"))) else "Ignore this string"
            self.ignore_checkbox.setText(_(current_ignore_text_key))
        if hasattr(self, 'reviewed_checkbox'):
            self.reviewed_checkbox.setText(_("Reviewed"))