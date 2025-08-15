# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QComboBox,
                               QPushButton, QDialogButtonBox, QMessageBox, QTableWidget,
                               QTableWidgetItem, QHeaderView, QCheckBox, QGroupBox, QLabel)
from PySide6.QtCore import Qt
from utils.localization import _
from utils.constants import SUPPORTED_LANGUAGES
from services import language_service


class ImportConfigurationDialog(QDialog):
    def __init__(self, parent, filename: str, detected_languages: list, resource_type: str = "Glossary"):
        super().__init__(parent)
        self.filename = filename
        self.detected_languages = detected_languages
        self.resource_type = resource_type
        self.lexisync_langs = {name: code for name, code in sorted(SUPPORTED_LANGUAGES.items())}

        self.setWindowTitle(_("{resource_type} Import Configuration").format(resource_type=self.resource_type))
        self.setModal(True)
        self.setMinimumWidth(600)

        self.setup_ui()
        self.populate_mappings()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        intro_label = QLabel(
            _("LexiSync has analyzed <b>{filename}</b>. Please configure the import settings below.").format(
                filename=self.filename)
        )
        intro_label.setWordWrap(True)
        layout.addWidget(intro_label)

        # --- 1. Language Mapping Group ---
        mapping_group = QGroupBox(_("Language Mapping"))
        mapping_layout = QVBoxLayout(mapping_group)

        mapping_info = QLabel(_("Confirm the language mapping from the file to LexiSync's supported languages."))
        mapping_info.setWordWrap(True)
        mapping_layout.addWidget(mapping_info)

        self.mapping_table = QTableWidget()
        self.mapping_table.setColumnCount(2)
        self.mapping_table.setHorizontalHeaderLabels([_("Language in File"), _("Map to Language in LexiSync")])
        self.mapping_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.mapping_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        mapping_layout.addWidget(self.mapping_table)
        layout.addWidget(mapping_group)

        # --- 2. Import Settings Group ---
        settings_group = QGroupBox(_("Import Settings"))
        settings_layout = QFormLayout(settings_group)

        self.source_lang_combo = QComboBox()
        self.target_lang_combo = QComboBox()

        settings_layout.addRow(_("Source Language:"), self.source_lang_combo)
        settings_layout.addRow(_("Target Language:"), self.target_lang_combo)

        if self.resource_type == "Glossary":
            self.bidirectional_checkbox = QCheckBox(_("Import as bidirectional (e.g., en->fr and fr->en)"))
            self.bidirectional_checkbox.setChecked(True)
            settings_layout.addRow("", self.bidirectional_checkbox)

        layout.addWidget(settings_group)

        # --- Buttons ---
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.button(QDialogButtonBox.Ok).setText(_("Import"))
        layout.addWidget(button_box)

        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

    def populate_mappings(self):
        self.mapping_table.setRowCount(len(self.detected_languages))

        mapped_lexisync_langs = []

        for i, lang_in_file in enumerate(self.detected_languages):
            # Column 0: Language in File
            item = QTableWidgetItem(lang_in_file)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.mapping_table.setItem(i, 0, item)

            # Column 1: Mapped Language
            combo = QComboBox()
            best_guess_index = 0

            base_lang = lang_in_file.split('-')[0].split('_')[0].lower()
            for idx, (name, code) in enumerate(self.lexisync_langs.items()):
                combo.addItem(name, code)
                if code == base_lang:
                    best_guess_index = idx

            combo.setCurrentIndex(best_guess_index)
            self.mapping_table.setCellWidget(i, 1, combo)
            mapped_lexisync_langs.append((combo.currentText(), combo.currentData()))

        unique_langs = sorted(list(dict.fromkeys(mapped_lexisync_langs)))
        for name, code in unique_langs:
            self.source_lang_combo.addItem(name, code)
            self.target_lang_combo.addItem(name, code)

        if self.target_lang_combo.count() > 1:
            self.target_lang_combo.setCurrentIndex(1)

    def get_data(self):
        lang_mapping = {}
        for i in range(self.mapping_table.rowCount()):
            lang_in_file = self.mapping_table.item(i, 0).text()
            combo = self.mapping_table.cellWidget(i, 1)
            lexisync_lang = combo.currentData()
            lang_mapping[lang_in_file] = lexisync_lang

        return {
            "source_lang": self.source_lang_combo.currentData(),
            "target_langs": [self.target_lang_combo.currentData()],
            "is_bidirectional": self.bidirectional_checkbox.isChecked(),
            "lang_mapping": lang_mapping
        }

    def accept(self):
        data = self.get_data()
        if data['source_lang'] == data['target_langs']:
            QMessageBox.warning(self, _("Invalid Languages"), _("Source and target languages cannot be the same."))
            return
        super().accept()