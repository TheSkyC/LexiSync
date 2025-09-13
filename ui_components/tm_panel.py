# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget, QListWidgetItem, QSizePolicy
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from typing import List, Dict, Optional
from utils.localization import _

class TMPanel(QWidget):
    apply_tm_suggestion_signal = Signal(str)
    update_tm_signal = Signal()
    clear_tm_signal = Signal()

    def __init__(self, parent=None, app_instance=None):
        super().__init__(parent)
        self.app = app_instance
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        self.tm_suggestions_listbox = QListWidget()
        self.tm_suggestions_listbox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.tm_suggestions_listbox.itemDoubleClicked.connect(self._on_tm_suggestion_double_click)
        self.tm_suggestions_listbox.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.tm_suggestions_listbox)

        tm_actions_frame = QWidget()
        tm_actions_layout = QHBoxLayout(tm_actions_frame)
        tm_actions_layout.setContentsMargins(0, 0, 0, 0)
        self.update_selected_tm_btn = QPushButton(_("Update TM for Selected"))
        self.update_selected_tm_btn.setObjectName("update_selected_tm_btn")
        self.update_selected_tm_btn.clicked.connect(self.update_tm_signal.emit)
        self.update_selected_tm_btn.setEnabled(False)
        tm_actions_layout.addWidget(self.update_selected_tm_btn)

        self.clear_selected_tm_btn = QPushButton(_("Clear TM for Selected"))
        self.clear_selected_tm_btn.setObjectName("clear_selected_tm_btn")
        self.clear_selected_tm_btn.clicked.connect(self.clear_tm_signal.emit)
        self.clear_selected_tm_btn.setEnabled(False)
        tm_actions_layout.addWidget(self.clear_selected_tm_btn)
        tm_actions_layout.addStretch(1)
        layout.addWidget(tm_actions_frame)

    def _on_tm_suggestion_double_click(self, item):
        translation_text_ui = item.data(Qt.UserRole)
        if translation_text_ui is not None:
            self.apply_tm_suggestion_signal.emit(translation_text_ui)

    def update_tm_suggestions(self, exact_match: Optional[str], fuzzy_matches: List[Dict]):
        self.tm_suggestions_listbox.clear()

        has_results = False
        if exact_match:
            has_results = True
            suggestion_for_ui = exact_match.replace("\\n", "\n")
            item = QListWidgetItem(f"(100%): {suggestion_for_ui}")
            item.setForeground(QColor("darkgreen"))
            item.setData(Qt.UserRole, suggestion_for_ui)
            self.tm_suggestions_listbox.addItem(item)

        if fuzzy_matches:
            has_results = True
            for match in fuzzy_matches:
                score = match['score']
                orig_text = match['source_text']
                trans_text = match['target_text']

                suggestion_for_ui = trans_text.replace("\\n", "\n")
                display_orig = orig_text[:40].replace("\n", "↵") + ("..." if len(orig_text) > 40 else "")

                item = QListWidgetItem(f"({score:.0%}): {suggestion_for_ui}  ~{display_orig}")

                if score > 0.85:
                    item.setForeground(QColor("purple"))
                else:
                    item.setForeground(QColor("darkblue"))
                item.setData(Qt.UserRole, suggestion_for_ui)
                self.tm_suggestions_listbox.addItem(item)

        if not has_results:
            item = QListWidgetItem(_("No TM matches found."))
            item.setForeground(Qt.gray)
            self.tm_suggestions_listbox.addItem(item)

    def update_ui_texts(self):
        self.findChild(QPushButton, "update_selected_tm_btn").setText(_("Update TM for Selected"))
        self.findChild(QPushButton, "clear_selected_tm_btn").setText(_("Clear TM for Selected"))