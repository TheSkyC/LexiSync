# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget, QListWidgetItem, QSizePolicy
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from rapidfuzz import fuzz
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
        full_text = item.text()
        try:
            translation_text_ui = full_text.split("): ", 1)[1].strip()
        except IndexError:
            translation_text_ui = full_text.strip()
        self.apply_tm_suggestion_signal.emit(translation_text_ui)

    def update_tm_suggestions_for_text(self, original_semantic_text, translation_memory, source_map=None):
        self.tm_suggestions_listbox.clear()
        if not original_semantic_text: return

        source_map = source_map or {}

        plugin_suggestions = None
        if self.app and hasattr(self.app, 'plugin_manager'):
            plugin_suggestions = self.app.plugin_manager.run_hook(
                'query_tm_suggestions',
                original_text=original_semantic_text
            )

        if plugin_suggestions is not None:
            for score, tm_orig, tm_trans in plugin_suggestions:
                suggestion_for_ui = tm_trans.replace("\\n", "\n")
                display_orig_match = tm_orig[:40].replace("\n", "↵") + ("..." if len(tm_orig) > 40 else "")
                item_text = f"({score * 100:.0f}% ~ {display_orig_match}): {suggestion_for_ui}"
                item = QListWidgetItem(item_text)

                if score == 1.0:
                    item.setForeground(QColor("darkgreen"))
                elif score > 0.85:
                    item.setForeground(QColor("purple"))
                else:
                    item.setForeground(QColor("darkblue"))

                self.tm_suggestions_listbox.addItem(item)
            return

        if original_semantic_text in translation_memory:
            suggestion_from_tm = translation_memory[original_semantic_text]
            source_tag = source_map.get(original_semantic_text, "")
            suggestion_for_ui = suggestion_from_tm.replace("\\n", "\n")
            item = QListWidgetItem(f"{source_tag} (100%): {suggestion_for_ui}")
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
            if tm_orig == original_semantic_text:
                continue
            ratio = fuzz.ratio(original_semantic_text, tm_orig) / 100.0
            if ratio > 0.65:
                fuzzy_matches.append((ratio, tm_orig, tm_trans_with_slash_n))

        fuzzy_matches.sort(key=lambda x: x[0], reverse=True)

        for ratio, orig_match_text, trans_match_text in fuzzy_matches[:3]:
            source_tag = source_map.get(orig_match_text, "")
            suggestion_for_ui = trans_match_text.replace("\\n", "\n")
            display_orig_match = orig_match_text[:40].replace("\n", "↵") + ("..." if len(orig_match_text) > 40 else "")
            item = QListWidgetItem(f"{source_tag} ({ratio * 100:.0f}% ~ {display_orig_match}): {suggestion_for_ui}")
            item.setForeground(QColor("purple"))
            self.tm_suggestions_listbox.addItem(item)

    def update_ui_texts(self):
        self.findChild(QPushButton, "update_selected_tm_btn").setText(_("Update TM for Selected"))
        self.findChild(QPushButton, "clear_selected_tm_btn").setText(_("Clear TM for Selected"))