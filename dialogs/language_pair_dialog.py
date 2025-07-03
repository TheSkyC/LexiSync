# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QDialogButtonBox
)
from utils.constants import SUPPORTED_LANGUAGES
from utils.localization import _


class LanguagePairDialog(QDialog):
    def __init__(self, parent, current_source_lang, current_target_lang):
        super().__init__(parent)
        self.setWindowTitle(_("Language Pair Settings"))
        self.setModal(True)
        self.resize(400, 150)

        self.source_lang = current_source_lang
        self.target_lang = current_target_lang

        self.lang_map = SUPPORTED_LANGUAGES
        self.lang_name_list = list(self.lang_map.keys())
        self.lang_code_list = list(self.lang_map.values())

        main_layout = QVBoxLayout(self)
        form_layout = QHBoxLayout()

        # 源语言
        source_layout = QVBoxLayout()
        source_layout.addWidget(QLabel(_("Source Language:")))
        self.source_combo = QComboBox()
        self.source_combo.addItems(self.lang_name_list)
        source_layout.addWidget(self.source_combo)
        form_layout.addLayout(source_layout)

        # 目标语言
        target_layout = QVBoxLayout()
        target_layout.addWidget(QLabel(_("Target Language:")))
        self.target_combo = QComboBox()
        self.target_combo.addItems(self.lang_name_list)
        target_layout.addWidget(self.target_combo)
        form_layout.addLayout(target_layout)

        main_layout.addLayout(form_layout)
        try:
            source_index = self.lang_code_list.index(current_source_lang)
            self.source_combo.setCurrentIndex(source_index)
        except ValueError:
            pass

        try:
            target_index = self.lang_code_list.index(current_target_lang)
            self.target_combo.setCurrentIndex(target_index)
        except ValueError:
            pass
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

    def accept(self):
        selected_source_name = self.source_combo.currentText()
        self.source_lang = self.lang_map.get(selected_source_name, 'en')

        selected_target_name = self.target_combo.currentText()
        self.target_lang = self.lang_map.get(selected_target_name, 'en')

        super().accept()