# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QWidget, QVBoxLayout, QFormLayout, QComboBox, QCheckBox, QSpinBox, QPushButton, QGroupBox, \
    QHBoxLayout, QLineEdit, QMessageBox, QLabel
from PySide6.QtCore import Qt
from utils.localization import _
from utils.constants import DEFAULT_API_URL


class BaseSettingsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("""
            QGroupBox {
                border: 1px solid #E4E7ED;
                border-radius: 4px;
                margin-top: 10px;
                padding: 15px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                left: 10px;
            }
            QLabel {
                font-size: 14px;
            }
            QLineEdit, QComboBox, QSpinBox {
                padding: 5px 8px;
                border: 1px solid #DCDFE6;
                border-radius: 4px;
                min-height: 22px;
                background-color: #FFFFFF;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
                border-color: #409EFF;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 8px;
                border-left-width: 1px;
                border-left-color: #DCDFE6;
                border-left-style: solid;
                border-top-right-radius: 3px;
                border-bottom-right-radius: 3px;
            }
            QSpinBox {
                padding-right: 20px;
            }
            QSpinBox::up-button {
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 16px;
                border-left-width: 1px;
                border-left-color: #E4E7ED;
                border-left-style: solid;
                border-top-right-radius: 3px;
            }
            QSpinBox::down-button {
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 16px;
                border-top-width: 1px;
                border-top-color: #E4E7ED;
                border-top-style: solid;
                border-left-width: 1px;
                border-left-color: #E4E7ED;
                border-left-style: solid;
                border-bottom-right-radius: 3px;
            }
        """)

        self.page_layout = QVBoxLayout(self)
        self.page_layout.setContentsMargins(20, 20, 20, 20)
        self.page_layout.setSpacing(15)
        self.page_layout.setAlignment(Qt.AlignTop)


class GeneralSettingsPage(BaseSettingsPage):
    def __init__(self, app_instance):
        super().__init__()
        self.app = app_instance

        form_layout = QFormLayout()
        form_layout.setRowWrapPolicy(QFormLayout.WrapAllRows)
        form_layout.setLabelAlignment(Qt.AlignLeft)

        # UI Language
        self.lang_combo = QComboBox()
        available_langs = self.app.lang_manager.get_available_languages()
        for code in available_langs:
            name = self.app.lang_manager.get_language_name(code)
            self.lang_combo.addItem(f"{name} ({code})", code)
        self.current_lang_on_open = self.app.config.get('language', 'en_US')
        index = self.lang_combo.findData(self.current_lang_on_open)
        if index != -1:
            self.lang_combo.setCurrentIndex(index)
        form_layout.addRow(_("UI Language:"), self.lang_combo)

        # Auto-save
        auto_save_layout = QHBoxLayout()
        auto_save_layout.setContentsMargins(0, 0, 0, 0)
        self.auto_save_spinbox = QSpinBox()
        self.auto_save_spinbox.setRange(0, 3600)
        self.auto_save_spinbox.setSingleStep(30)
        self.auto_save_spinbox.setSuffix(_(" s"))
        self.auto_save_spinbox.setValue(self.app.config.get('auto_save_interval_sec', 60))
        self.auto_save_hint_label = QLabel(_("(0 to disable)"))
        self.auto_save_hint_label.setStyleSheet("color: gray;")
        auto_save_layout.addWidget(self.auto_save_spinbox)
        auto_save_layout.addWidget(self.auto_save_hint_label)
        auto_save_layout.addStretch()
        form_layout.addRow(_("Auto-save Interval:"), auto_save_layout)

        # Extraction Rules
        self.extraction_button = QPushButton(_("Manage Extraction Rules..."))
        self.extraction_button.clicked.connect(self.app.show_extraction_pattern_dialog)
        form_layout.addRow(_("Extraction Rules:"), self.extraction_button)

        self.page_layout.addLayout(form_layout)

        # On Save Options
        on_save_group = QGroupBox(_("On File Save"))
        on_save_layout = QVBoxLayout(on_save_group)
        self.backup_tm_checkbox = QCheckBox(_("Auto-backup Translation Memory"))
        self.backup_tm_checkbox.setChecked(self.app.config.get('auto_backup_tm_on_save', True))
        self.compile_mo_checkbox = QCheckBox(_("Auto-compile .mo file when save .po file"))
        self.compile_mo_checkbox.setChecked(self.app.config.get('auto_compile_mo_on_save', True))
        on_save_layout.addWidget(self.backup_tm_checkbox)
        on_save_layout.addWidget(self.compile_mo_checkbox)
        self.page_layout.addWidget(on_save_group)

    def save_settings(self):
        lang_changed = False
        new_lang_code = self.lang_combo.currentData()
        if new_lang_code and new_lang_code != self.current_lang_on_open:
            self.app.change_language(new_lang_code)
            self.current_lang_on_open = new_lang_code
            lang_changed = True

        self.app.auto_save_interval_sec = self.auto_save_spinbox.value()
        self.app.config['auto_save_interval_sec'] = self.app.auto_save_interval_sec
        self.app.setup_auto_save_timer()

        self.app.auto_backup_tm_on_save_var = self.backup_tm_checkbox.isChecked()
        self.app.config['auto_backup_tm_on_save'] = self.app.auto_backup_tm_on_save_var

        self.app.auto_compile_mo_var = self.compile_mo_checkbox.isChecked()
        self.app.config['auto_compile_mo_on_save'] = self.app.auto_compile_mo_var

        return lang_changed


class AppearanceSettingsPage(BaseSettingsPage):
    def __init__(self, app_instance):
        super().__init__()
        self.app = app_instance

        form_layout = QFormLayout()
        form_layout.setRowWrapPolicy(QFormLayout.WrapAllRows)
        form_layout.setLabelAlignment(Qt.AlignLeft)

        self.static_sort_checkbox = QCheckBox(_("Use static sorting (Press F5 to manual refresh)"))
        self.static_sort_checkbox.setChecked(self.app.config.get('use_static_sorting', False))
        form_layout.addRow(_("Sorting Mode:"), self.static_sort_checkbox)

        self.font_button = QPushButton(_("Font Settings..."))
        self.font_button.clicked.connect(self.app.show_font_settings_dialog)
        form_layout.addRow(_("Fonts:"), self.font_button)

        self.keybinding_button = QPushButton(_("Keybinding Settings..."))
        self.keybinding_button.clicked.connect(self.app.show_keybinding_dialog)
        form_layout.addRow(_("Keybindings:"), self.keybinding_button)

        self.page_layout.addLayout(form_layout)

    def save_settings(self):
        is_checked = self.static_sort_checkbox.isChecked()
        if is_checked != self.app.use_static_sorting_var:
            self.app._toggle_static_sorting_mode(is_checked)


class AISettingsPage(BaseSettingsPage):
    def __init__(self, app_instance):
        super().__init__()
        self.app = app_instance

        api_group = QGroupBox(_("API Settings"))
        api_layout = QFormLayout(api_group)
        self.api_key_entry = QLineEdit(self.app.config.get("ai_api_key", ""))
        self.api_key_entry.setEchoMode(QLineEdit.Password)
        self.api_base_url_entry = QLineEdit(self.app.config.get("ai_api_base_url", DEFAULT_API_URL))
        self.model_name_entry = QLineEdit(self.app.config.get("ai_model_name", "deepseek-chat"))
        api_layout.addRow(_("API Key:"), self.api_key_entry)
        api_layout.addRow(_("API Base URL:"), self.api_base_url_entry)
        api_layout.addRow(_("Model Name:"), self.model_name_entry)
        self.page_layout.addWidget(api_group)

        perf_group = QGroupBox(_("Performance"))
        perf_layout = QFormLayout(perf_group)
        self.interval_spinbox = QSpinBox()
        self.interval_spinbox.setRange(0, 10000)
        self.interval_spinbox.setSuffix(" ms")
        self.interval_spinbox.setValue(self.app.config.get("ai_api_interval", 500))
        self.concurrent_spinbox = QSpinBox()
        self.concurrent_spinbox.setRange(1, 16)
        self.concurrent_spinbox.setValue(self.app.config.get("ai_max_concurrent_requests", 8))
        perf_layout.addRow(_("API Call Interval:"), self.interval_spinbox)
        perf_layout.addRow(_("Max Concurrent Requests:"), self.concurrent_spinbox)
        self.page_layout.addWidget(perf_group)

        context_group = QGroupBox(_("Context & Prompts"))
        context_layout = QVBoxLayout(context_group)
        target_lang_layout = QHBoxLayout()
        target_lang_label = QLabel(_("Target Language:"))
        target_lang_code = self.app.target_language
        target_lang_name = self.app.lang_manager.get_language_name(target_lang_code)
        self.target_language_display = QLineEdit(f"{target_lang_name} ({target_lang_code})")
        self.target_language_display.setReadOnly(True)
        self.target_language_display.setToolTip(_("Target language is set in 'Settings > Language Pair Settings...'"))
        target_lang_layout.addWidget(target_lang_label)
        target_lang_layout.addWidget(self.target_language_display)
        context_layout.addLayout(target_lang_layout)
        context_layout.addSpacing(10)
        self.use_original_context_check = QCheckBox(_("Use nearby original text as context"))
        self.use_original_context_check.setChecked(self.app.config.get("ai_use_original_context", True))
        context_layout.addWidget(self.use_original_context_check)
        original_neighbor_layout = QHBoxLayout()
        original_neighbor_layout.addSpacing(20)
        original_neighbor_layout.addWidget(QLabel(_("Use nearby")))
        self.original_neighbors_spinbox = QSpinBox()
        self.original_neighbors_spinbox.setRange(0, 20)
        self.original_neighbors_spinbox.setValue(self.app.config.get("ai_original_context_neighbors", 8))
        self.original_neighbors_spinbox.setMinimumWidth(70)
        original_neighbor_layout.addWidget(self.original_neighbors_spinbox)
        original_neighbor_layout.addWidget(QLabel(_("original strings (0 for all)")))
        original_neighbor_layout.addStretch()
        context_layout.addLayout(original_neighbor_layout)
        self.use_translation_context_check = QCheckBox(_("Use nearby translated text as context"))
        self.use_translation_context_check.setChecked(self.app.config.get("ai_use_translation_context", True))
        context_layout.addWidget(self.use_translation_context_check)
        translation_neighbor_layout = QHBoxLayout()
        translation_neighbor_layout.addSpacing(20)
        translation_neighbor_layout.addWidget(QLabel(_("Use nearby")))
        self.translation_neighbors_spinbox = QSpinBox()
        self.translation_neighbors_spinbox.setRange(0, 20)
        self.translation_neighbors_spinbox.setValue(self.app.config.get("ai_context_neighbors", 8))
        self.translation_neighbors_spinbox.setMinimumWidth(70)
        translation_neighbor_layout.addWidget(self.translation_neighbors_spinbox)
        translation_neighbor_layout.addWidget(QLabel(_("translations (0 for all)")))
        translation_neighbor_layout.addStretch()
        context_layout.addLayout(translation_neighbor_layout)
        self.use_original_context_check.stateChanged.connect(self.original_neighbors_spinbox.setEnabled)
        self.use_translation_context_check.stateChanged.connect(self.translation_neighbors_spinbox.setEnabled)
        self.original_neighbors_spinbox.setEnabled(self.use_original_context_check.isChecked())
        self.translation_neighbors_spinbox.setEnabled(self.use_translation_context_check.isChecked())
        context_layout.addSpacing(15)
        self.prompt_button = QPushButton(_("Prompt Manager..."))
        self.prompt_button.clicked.connect(self.app.show_prompt_manager)
        self.project_instructions_button = QPushButton(_("Project-specific Instructions..."))
        self.project_instructions_button.clicked.connect(self.app.show_project_custom_instructions_dialog)
        self.project_instructions_button.setEnabled(self.app.current_project_file_path is not None)
        context_layout.addWidget(self.prompt_button)
        context_layout.addWidget(self.project_instructions_button)
        self.page_layout.addWidget(context_group)

    def save_settings(self):
        self.app.config["ai_api_key"] = self.api_key_entry.text()
        self.app.config["ai_api_base_url"] = self.api_base_url_entry.text()
        self.app.config["ai_model_name"] = self.model_name_entry.text()
        self.app.config["ai_api_interval"] = self.interval_spinbox.value()
        self.app.config["ai_max_concurrent_requests"] = self.concurrent_spinbox.value()
        self.app.config["ai_use_original_context"] = self.use_original_context_check.isChecked()
        self.app.config["ai_original_context_neighbors"] = self.original_neighbors_spinbox.value()
        self.app.config["ai_use_translation_context"] = self.use_translation_context_check.isChecked()
        self.app.config["ai_context_neighbors"] = self.translation_neighbors_spinbox.value()
        self.app.ai_translator.api_key = self.api_key_entry.text()
        self.app.ai_translator.api_url = self.api_base_url_entry.text()
        self.app.ai_translator.model_name = self.model_name_entry.text()


class ValidationSettingsPage(BaseSettingsPage):
    def __init__(self, app_instance):
        super().__init__()
        self.app = app_instance

        group = QGroupBox(_("Enabled Validation Checks"))
        layout = QVBoxLayout(group)

        self.check_placeholders = QCheckBox(_("Check for missing/extra placeholders"))
        self.check_placeholders.setChecked(self.app.config.get('check_placeholders', True))
        layout.addWidget(self.check_placeholders)

        self.check_formatting = QCheckBox(_("Check for formatting differences (whitespace, punctuation, etc.)"))
        self.check_formatting.setChecked(self.app.config.get('check_formatting', True))
        layout.addWidget(self.check_formatting)

        self.check_fuzzy = QCheckBox(_("Flag entries marked as 'Fuzzy'"))
        self.check_fuzzy.setChecked(self.app.config.get('check_fuzzy', True))
        layout.addWidget(self.check_fuzzy)

        self.check_length = QCheckBox(_("Check for unusual translation length/expansion ratio"))
        self.check_length.setChecked(self.app.config.get('check_length', True))
        layout.addWidget(self.check_length)

        self.page_layout.addWidget(group)

    def save_settings(self):
        self.app.config['check_placeholders'] = self.check_placeholders.isChecked()
        self.app.config['check_formatting'] = self.check_formatting.isChecked()
        self.app.config['check_fuzzy'] = self.check_fuzzy.isChecked()
        self.app.config['check_length'] = self.check_length.isChecked()