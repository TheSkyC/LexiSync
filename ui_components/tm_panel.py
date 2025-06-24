# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget, QListWidgetItem, QSizePolicy
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from difflib import SequenceMatcher
from utils.localization import _

class TMPanel(QWidget):
    apply_tm_suggestion_signal = Signal(str)
    update_tm_signal = Signal()
    clear_tm_signal = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        self.tm_label = QLabel(_("Translation Memory Matches:"))
        self.tm_label.setObjectName("tm_label")
        layout.addWidget(self.tm_label)

        self.tm_suggestions_listbox = QListWidget()
        self.tm_suggestions_listbox.setFixedHeight(100)
        self.tm_suggestions_listbox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.tm_suggestions_listbox.itemDoubleClicked.connect(self._on_tm_suggestion_double_click)
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

        layout.addStretch(1)

    def _on_tm_suggestion_double_click(self, item):
        full_text = item.text()
        try:
            translation_text_ui = full_text.split("): ", 1)[1].strip()
        except IndexError:
            translation_text_ui = full_text.strip()
        self.apply_tm_suggestion_signal.emit(translation_text_ui)

    def update_tm_suggestions_for_text(self, original_semantic_text, translation_memory):
        self.tm_suggestions_listbox.clear()
        if not original_semantic_text: return
        if original_semantic_text in translation_memory:
            suggestion_from_tm = translation_memory[original_semantic_text]
            suggestion_for_ui = suggestion_from_tm.replace("\\n", "\n")
            item = QListWidgetItem(f"(100% Exact Match): {suggestion_for_ui}")
            item.setForeground(QColor("darkgreen"))
            self.tm_suggestions_listbox.addItem(item)

        original_lower = original_semantic_text.lower()
        case_insensitive_match = None
        for tm_orig, tm_trans in translation_memory.items():
            if tm_orig.lower() == original_lower and tm_orig != original_semantic_text:
                case_insensitive_match = tm_trans
                break

        if case_insensitive_match:
            suggestion_for_ui = case_insensitive_match.replace("\\n", "\n")
            item = QListWidgetItem(f"(Case Mismatch): {suggestion_for_ui}")
            item.setForeground(QColor("orange red"))
            self.tm_suggestions_listbox.addItem(item)

        fuzzy_matches = []
        for tm_orig, tm_trans_with_slash_n in translation_memory.items():
            if tm_orig == original_semantic_text or tm_orig.lower() == original_lower:
                continue

            ratio = SequenceMatcher(None, original_semantic_text, tm_orig).ratio()
            if ratio > 0.65:
                fuzzy_matches.append((ratio, tm_orig, tm_trans_with_slash_n))

        fuzzy_matches.sort(key=lambda x: x[0], reverse=True)

        for ratio, orig_match_text, trans_match_text in fuzzy_matches[:3]:
            suggestion_for_ui = trans_match_text.replace("\\n", "\n")
            display_orig_match = orig_match_text[:40].replace("\n", "↵") + ("..." if len(orig_match_text) > 40 else "")
            item = QListWidgetItem(f"({ratio * 100:.0f}% ~ {display_orig_match}): {suggestion_for_ui}")
            item.setForeground(QColor("purple"))
            self.tm_suggestions_listbox.addItem(item)

    def update_ui_texts(self):
        self.findChild(QLabel, "tm_label").setText(_("Translation Memory Matches:"))
        self.findChild(QPushButton, "update_selected_tm_btn").setText(_("Update TM for Selected"))
        self.findChild(QPushButton, "clear_selected_tm_btn").setText(_("Clear TM for Selected"))