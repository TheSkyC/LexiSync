# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QComboBox, QCheckBox, QSpinBox,
    QPushButton, QGroupBox, QHBoxLayout, QLineEdit, QMessageBox, QLabel,
    QApplication, QScrollArea, QFrame, QDoubleSpinBox
)
from PySide6.QtGui import QColor, QPixmap, QPainter
from PySide6.QtCore import Qt
from utils.localization import _, lang_manager
from utils.constants import DEFAULT_API_URL, DEFAULT_VALIDATION_RULES


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

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        content_widget = QWidget()
        content_widget.setObjectName("generalContent")
        content_widget.setStyleSheet("#generalContent { background-color: #FFFFFF; }")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(15)


        main_form_layout = QFormLayout()
        main_form_layout.setRowWrapPolicy(QFormLayout.WrapAllRows)
        main_form_layout.setLabelAlignment(Qt.AlignLeft)

        # UI Language
        self.lang_combo = QComboBox()
        available_langs = lang_manager.get_available_languages()
        for code in available_langs:
            name = lang_manager.get_language_name(code)
            self.lang_combo.addItem(f"{name} ({code})", code)
        self.current_lang_on_open = self.app.config.get('language', 'en_US')
        index = self.lang_combo.findData(self.current_lang_on_open)
        if index != -1:
            self.lang_combo.setCurrentIndex(index)
        main_form_layout.addRow(_("UI Language:"), self.lang_combo)

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
        main_form_layout.addRow(_("Auto-save Interval:"), auto_save_layout)

        self.propagation_combo = QComboBox()
        self.propagation_map = {
            'smart': _("Smart (Update empty or identical translations)"),
            'fill_blanks': _("Fill Blanks Only (Update empty translations)"),
            'always': _("Always (Update all identical source strings)"),
            'single': _("Single (Update only the selected item)")
        }
        for key, text in self.propagation_map.items():
            self.propagation_combo.addItem(text, key)

        current_mode = self.app.config.get('translation_propagation_mode', 'smart')
        index = self.propagation_combo.findData(current_mode)
        if index != -1:
            self.propagation_combo.setCurrentIndex(index)

        main_form_layout.addRow(_("Translation Propagation:"), self.propagation_combo)

        content_layout.addLayout(main_form_layout)

        # Ctrl+Enter Behavior
        self.next_behavior_combo = QComboBox()
        self.next_behavior_map = {
            'untranslated': _("Next Untranslated (Default)"),
            'any': _("Next Item (Regardless of status)"),
            'unreviewed': _("Next Unreviewed"),
            'error': _("Next Error"),
            'warning': _("Next Warning"),
            'info': _("Next Info")
        }
        order = ['untranslated', 'any', 'unreviewed', 'error', 'warning', 'info']
        for key in order:
            self.next_behavior_combo.addItem(self.next_behavior_map[key], key)

        current_behavior = self.app.config.get('apply_and_next_behavior', 'untranslated')
        index = self.next_behavior_combo.findData(current_behavior)
        if index != -1:
            self.next_behavior_combo.setCurrentIndex(index)
        main_form_layout.addRow(_("Ctrl+Enter Jump To:"), self.next_behavior_combo)
        content_layout.addLayout(main_form_layout)

        # Project Settings Group
        project_group = QGroupBox(_("Project Settings"))
        project_layout = QFormLayout(project_group)
        self.load_all_files_checkbox = QCheckBox(_("Load all source files when opening a project"))
        self.load_all_files_checkbox.setToolTip(
            _("Improves performance for cross-file operations, but may increase initial loading time for large projects."))
        self.load_all_files_checkbox.setChecked(self.app.config.get('load_all_files_on_project_open', False))
        project_layout.addRow(self.load_all_files_checkbox)
        content_layout.addWidget(project_group)

        # On Save Options Group
        on_save_group = QGroupBox(_("On File Save"))
        on_save_layout = QVBoxLayout(on_save_group)
        self.backup_tm_checkbox = QCheckBox(_("Auto-backup Translation Memory"))
        self.backup_tm_checkbox.setChecked(self.app.config.get('auto_backup_tm_on_save', True))
        self.compile_mo_checkbox = QCheckBox(_("Auto-compile .mo file when save .po file"))
        self.compile_mo_checkbox.setChecked(self.app.config.get('auto_compile_mo_on_save', True))
        on_save_layout.addWidget(self.backup_tm_checkbox)
        on_save_layout.addWidget(self.compile_mo_checkbox)
        content_layout.addWidget(on_save_group)

        # Smart Paste Group
        paste_group = QGroupBox(_("Smart Paste"))
        paste_layout = QVBoxLayout(paste_group)
        self.smart_paste_checkbox = QCheckBox(_("Enable Smart Paste"))
        self.smart_paste_checkbox.setToolTip(_("Automatically format text when pasting into the translation editor."))
        self.smart_paste_checkbox.setChecked(self.app.config.get('smart_paste_enabled', True))
        self.sync_whitespace_checkbox = QCheckBox(_("Sync leading/trailing whitespace"))
        self.sync_whitespace_checkbox.setChecked(self.app.config.get('smart_paste_sync_whitespace', True))
        self.normalize_newlines_checkbox = QCheckBox(_("Normalize newlines"))
        self.normalize_newlines_checkbox.setChecked(self.app.config.get('smart_paste_normalize_newlines', True))
        self.smart_paste_checkbox.stateChanged.connect(self.sync_whitespace_checkbox.setEnabled)
        self.smart_paste_checkbox.stateChanged.connect(self.normalize_newlines_checkbox.setEnabled)
        self.sync_whitespace_checkbox.setEnabled(self.smart_paste_checkbox.isChecked())
        self.normalize_newlines_checkbox.setEnabled(self.smart_paste_checkbox.isChecked())
        paste_layout.addWidget(self.smart_paste_checkbox)
        sub_options_layout = QHBoxLayout()
        sub_options_layout.addSpacing(20)
        sub_options_widget = QWidget()
        sub_options_v_layout = QVBoxLayout(sub_options_widget)
        sub_options_v_layout.setContentsMargins(0, 0, 0, 0)
        sub_options_v_layout.addWidget(self.sync_whitespace_checkbox)
        sub_options_v_layout.addWidget(self.normalize_newlines_checkbox)
        sub_options_layout.addWidget(sub_options_widget)
        self.paste_protection_checkbox = QCheckBox(_("Enable Large Text Paste Protection"))
        self.paste_protection_checkbox.setToolTip(
            _("Warns when pasting large text that is significantly longer than the original."))
        self.paste_protection_checkbox.setChecked(self.app.config.get('paste_protection_enabled', True))

        paste_layout.addWidget(self.smart_paste_checkbox)
        paste_layout.addLayout(sub_options_layout)
        paste_layout.addSpacing(5)
        paste_layout.addWidget(self.paste_protection_checkbox)
        content_layout.addWidget(paste_group)

        # Extraction Rules
        extraction_group = QGroupBox(_("Extraction"))
        extraction_layout = QFormLayout(extraction_group)
        self.extraction_button = QPushButton(_("Manage Extraction Rules..."))
        self.extraction_button.clicked.connect(self.app.show_extraction_pattern_dialog)
        extraction_layout.addRow(self.extraction_button)
        content_layout.addWidget(extraction_group)

        content_layout.addStretch(1)
        scroll_area.setWidget(content_widget)
        self.page_layout.addWidget(scroll_area)


    def save_settings(self):
        lang_changed = False
        new_lang_code = self.lang_combo.currentData()
        if new_lang_code and new_lang_code != self.current_lang_on_open:
            self.app.change_language(new_lang_code)
            self.current_lang_on_open = new_lang_code
            lang_changed = True

        self.app.config['translation_propagation_mode'] = self.propagation_combo.currentData()
        self.app.auto_save_interval_sec = self.auto_save_spinbox.value()
        self.app.config['auto_save_interval_sec'] = self.app.auto_save_interval_sec
        self.app.setup_auto_save_timer()
        self.app.config['load_all_files_on_project_open'] = self.load_all_files_checkbox.isChecked()
        self.app.auto_backup_tm_on_save_var = self.backup_tm_checkbox.isChecked()
        self.app.config['auto_backup_tm_on_save'] = self.app.auto_backup_tm_on_save_var

        self.app.auto_compile_mo_var = self.compile_mo_checkbox.isChecked()
        self.app.config['auto_compile_mo_on_save'] = self.app.auto_compile_mo_var
        self.app.config['apply_and_next_behavior'] = self.next_behavior_combo.currentData()
        self.app.config['smart_paste_enabled'] = self.smart_paste_checkbox.isChecked()
        self.app.config['smart_paste_sync_whitespace'] = self.sync_whitespace_checkbox.isChecked()
        self.app.config['smart_paste_normalize_newlines'] = self.normalize_newlines_checkbox.isChecked()
        self.app.config['paste_protection_enabled'] = self.paste_protection_checkbox.isChecked()

        if hasattr(self.app, 'details_panel'):
            self.app.details_panel.translation_edit_text.paste_protection_enabled = self.paste_protection_checkbox.isChecked()
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

        self.accelerator_marker_edit = QLineEdit(self.app.config.get('accelerator_marker', '&'))
        self.accelerator_marker_edit.setMaxLength(1)
        self.accelerator_marker_edit.setToolTip(_("Enter a single character used for menu accelerators (e.g., &, _)."))
        form_layout.addRow(_("Accelerator Marker:"), self.accelerator_marker_edit)

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
        self.app.config['accelerator_marker'] = self.accelerator_marker_edit.text()


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
        self.test_btn = QPushButton(_("Test Connection"))
        self.test_btn.clicked.connect(self.on_test_connection)
        api_layout.addRow(_("API Key:"), self.api_key_entry)
        api_layout.addRow(_("API Base URL:"), self.api_base_url_entry)
        api_layout.addRow(_("Model Name:"), self.model_name_entry)
        api_layout.addRow("", self.test_btn)
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
        context_layout.addWidget(self.prompt_button)
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

    def on_test_connection(self):
        api_key = self.api_key_entry.text().strip()
        url = self.api_base_url_entry.text().strip()
        model = self.model_name_entry.text().strip()

        if not api_key:
            QMessageBox.warning(self, _("Warning"), _("Please enter an API Key."))
            return

        old_key = self.app.ai_translator.api_key
        old_url = self.app.ai_translator.api_url
        old_model = self.app.ai_translator.model_name

        self.app.ai_translator.api_key = api_key
        self.app.ai_translator.api_url = url
        self.app.ai_translator.model_name = model

        self.test_btn.setEnabled(False)
        self.test_btn.setText(_("Testing..."))
        QApplication.processEvents()

        try:
            success, message = self.app.ai_translator.test_connection()

            if success:
                QMessageBox.information(self, _("Success"), message)
            else:
                QMessageBox.warning(self, _("Failed"), message)
        except Exception as e:
            QMessageBox.critical(self, _("Error"), str(e))
        finally:
            self.test_btn.setEnabled(True)
            self.test_btn.setText(_("Test Connection"))

            self.app.ai_translator.api_key = old_key
            self.app.ai_translator.api_url = old_url
            self.app.ai_translator.model_name = old_model


class ValidationRuleWidget(QWidget):
    def __init__(self, key, config_data):
        super().__init__()
        self.key = key
        self.config_data = config_data

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)

        # Checkbox
        self.checkbox = QCheckBox(config_data.get("label", key))
        self.checkbox.setChecked(config_data.get("enabled", True))
        self.checkbox.stateChanged.connect(self.update_state)

        # Combobox
        self.level_combo = QComboBox()

        # [MODIFIED] 添加带颜色的条目

        # 1. Error
        self.level_combo.addItem(_("Error"), "error")
        self.level_combo.setItemData(0, QColor("#D32F2F"), Qt.ForegroundRole)
        self.level_combo.setItemData(0, self._create_color_icon("#D32F2F"), Qt.DecorationRole)

        # 2. Warning
        self.level_combo.addItem(_("Warning"), "warning")
        self.level_combo.setItemData(1, QColor("#F57C00"), Qt.ForegroundRole)
        self.level_combo.setItemData(1, self._create_color_icon("#FBC02D"), Qt.DecorationRole)

        # 3. Info
        self.level_combo.addItem(_("Info"), "info")
        self.level_combo.setItemData(2, QColor("#1976D2"), Qt.ForegroundRole)
        self.level_combo.setItemData(2, self._create_color_icon("#2196F3"), Qt.DecorationRole)

        current_level = config_data.get("level", "warning")
        index = self.level_combo.findData(current_level)
        if index != -1:
            self.level_combo.setCurrentIndex(index)

        self.level_combo.setFixedWidth(120)

        layout.addWidget(self.checkbox, 1)
        layout.addWidget(self.level_combo)

        self.update_state()

    def _create_color_icon(self, color_str):
        pixmap = QPixmap(12, 12)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        color = QColor(color_str)
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(0, 0, 12, 12, 3, 3)
        painter.end()
        return pixmap

    def update_state(self):
        self.level_combo.setEnabled(self.checkbox.isChecked())

    def get_data(self):
        return {
            "enabled": self.checkbox.isChecked(),
            "level": self.level_combo.currentData(),
            "label": self.config_data.get("label", self.key)  # 保持 Label 不变
        }

class ValidationSettingsPage(BaseSettingsPage):
    def __init__(self, app_instance):
        super().__init__()
        self.app = app_instance
        self.rule_widgets = {}

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        content_widget = QWidget()

        content_widget.setObjectName("validationContent")

        content_widget.setStyleSheet("""
                    #validationContent {
                        background-color: #FFFFFF;
                    }
                """)

        self.main_layout = QVBoxLayout(content_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        # 获取当前配置
        current_rules = self.app.config.get("validation_rules", DEFAULT_VALIDATION_RULES)

        # 分组定义
        groups = {
            _("Code Safety"): ["printf", "python_brace", "html_tags", "url_email", "accelerator"],
            _("Content Consistency"): ["numbers", "glossary", "fuzzy", "repeated_word"],
            _("Formatting & Punctuation"): ["punctuation", "brackets", "whitespace", "double_space", "capitalization", "newline_count", "quotes"]
        }

        for group_name, keys in groups.items():
            group_box = QGroupBox(group_name)
            group_layout = QVBoxLayout(group_box)

            for key in keys:
                if key in current_rules:
                    widget = ValidationRuleWidget(key, current_rules[key])
                    self.rule_widgets[key] = widget
                    group_layout.addWidget(widget)

            self.main_layout.addWidget(group_box)

        # 长度检查单独处理
        length_group = QGroupBox(_("Length Constraints"))
        length_layout = QFormLayout(length_group)

        self.check_length = QCheckBox(_("Enable Length Check"))
        self.check_length.setChecked(self.app.config.get('check_length', True))

        self.major_threshold = QDoubleSpinBox()
        self.major_threshold.setRange(1.1, 10.0)
        self.major_threshold.setSingleStep(0.1)
        self.major_threshold.setValue(self.app.config.get('length_threshold_major', 2.5))

        self.minor_threshold = QDoubleSpinBox()
        self.minor_threshold.setRange(1.1, 10.0)
        self.minor_threshold.setSingleStep(0.1)
        self.minor_threshold.setValue(self.app.config.get('length_threshold_minor', 2.0))

        length_layout.addRow(self.check_length)
        length_layout.addRow(_("Major Threshold (Error):"), self.major_threshold)
        length_layout.addRow(_("Minor Threshold (Warning):"), self.minor_threshold)

        self.main_layout.addWidget(length_group)
        self.main_layout.addStretch()

        scroll.setWidget(content_widget)
        self.page_layout.addWidget(scroll)

    def save_settings(self):
        new_rules = {}
        for key, widget in self.rule_widgets.items():
            new_rules[key] = widget.get_data()

        self.app.config["validation_rules"] = new_rules

        self.app.config['check_length'] = self.check_length.isChecked()
        self.app.config['length_threshold_major'] = self.major_threshold.value()
        self.app.config['length_threshold_minor'] = self.minor_threshold.value()

        self.app._run_and_refresh_with_validation()
        return False