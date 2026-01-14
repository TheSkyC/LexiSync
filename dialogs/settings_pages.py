# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QComboBox, QCheckBox, QSpinBox,
    QPushButton, QGroupBox, QHBoxLayout, QLineEdit, QMessageBox, QLabel,
    QApplication, QScrollArea, QFrame, QDoubleSpinBox, QGridLayout,
    QButtonGroup, QRadioButton, QAbstractSpinBox
)
from PySide6.QtGui import QColor, QPixmap, QPainter
from PySide6.QtCore import Qt, QEvent
from utils.path_utils import get_resource_path
from utils.constants import DEFAULT_API_URL, DEFAULT_VALIDATION_RULES
from utils.localization import _, lang_manager


class BaseSettingsPage(QWidget):
    def __init__(self):
        super().__init__()

        icon_down = get_resource_path("icons/chevron-down.svg").replace("\\", "/")
        icon_up = get_resource_path("icons/chevron-up.svg").replace("\\", "/")

        self.setStyleSheet(f"""
            QGroupBox {{
                border: 1px solid #E4E7ED;
                border-radius: 4px;
                margin-top: 10px;
                padding: 15px;
                font-weight: bold;
                background-color: #FFFFFF;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                left: 10px;
                color: #303133;
            }}
            QLabel {{
                font-size: 14px;
                color: #606266;
            }}
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
                padding: 5px 8px;
                border: 1px solid #DCDFE6;
                border-radius: 4px;
                min-height: 22px;
                background-color: #FFFFFF;
                color: #606266;
            }}
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
                border-color: #409EFF;
            }}

            /* QComboBox 美化 */
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 24px;
                border-left: 1px solid #DCDFE6;
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
                background-color: #FAFAFA;
            }}
            QComboBox::drop-down:hover {{
                background-color: #F0F2F5;
            }}
            QComboBox::drop-down:on {{
                background-color: #E6F1FC;
            }}
            QComboBox::down-arrow {{
                image: url("{icon_down}");
                width: 12px;
                height: 12px;
            }}
            QComboBox::down-arrow:on {{
                image: url("{icon_up}");
            }}

            /* QSpinBox & QDoubleSpinBox 美化 */
            QSpinBox, QDoubleSpinBox {{
                padding-right: 24px;
            }}
            QSpinBox::up-button, QDoubleSpinBox::up-button {{
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 24px;
                border-left: 1px solid #DCDFE6;
                border-bottom: 1px solid #DCDFE6;
                border-top-right-radius: 4px;
                background-color: #FAFAFA;
                margin-bottom: 0px;
            }}
            QSpinBox::down-button, QDoubleSpinBox::down-button {{
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 24px;
                border-left: 1px solid #DCDFE6;
                border-bottom-right-radius: 4px;
                background-color: #FAFAFA;
                margin-top: 0px;
            }}
            QSpinBox::up-button:hover, QSpinBox::down-button:hover,
            QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{
                background-color: #F0F2F5;
            }}
            QSpinBox::up-button:pressed, QSpinBox::down-button:pressed,
            QDoubleSpinBox::up-button:pressed, QDoubleSpinBox::down-button:pressed {{
                background-color: #E6F1FC;
            }}
            QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
                image: url("{icon_up}");
                width: 10px;
                height: 10px;
            }}
            QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
                image: url("{icon_down}");
                width: 10px;
                height: 10px;
            }}
        """)

        self.page_layout = QVBoxLayout(self)
        self.page_layout.setContentsMargins(20, 20, 20, 20)
        self.page_layout.setSpacing(15)
        self.page_layout.setAlignment(Qt.AlignTop)

    def apply_widget_policies(self):
        """
        Applies standard policies to widgets on the page.
        Disable mouse wheel on inputs UNLESS they have focus.
        """
        combos = self.findChildren(QComboBox)
        spinboxes = self.findChildren(QAbstractSpinBox)

        for widget in combos + spinboxes:
            original_wheel_event = widget.wheelEvent

            def smart_wheel_event(event, w=widget, original=original_wheel_event):
                if w.hasFocus():
                    original(event)
                else:
                    event.ignore()
            widget.wheelEvent = smart_wheel_event
            widget.setFocusPolicy(Qt.StrongFocus)


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
            'untranslated': _("Next Untranslated"),
            'any': _("Next Item"),
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
        self.apply_widget_policies()


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

        self.accelerator_marker_edit = QLineEdit(self.app.config.get('accelerator_marker', '&'))
        self.accelerator_marker_edit.setMaxLength(20)
        self.accelerator_marker_edit.setToolTip(_("Enter characters used for menu accelerators, separated by comma (e.g., '&, _')."))
        form_layout.addRow(_("Accelerator Marker(s):"), self.accelerator_marker_edit)

        self.font_button = QPushButton(_("Font Settings..."))
        self.font_button.clicked.connect(self.app.show_font_settings_dialog)
        form_layout.addRow(_("Fonts:"), self.font_button)

        self.keybinding_button = QPushButton(_("Keybinding Settings..."))
        self.keybinding_button.clicked.connect(self.app.show_keybinding_dialog)
        form_layout.addRow(_("Keybindings:"), self.keybinding_button)

        self.page_layout.addLayout(form_layout)
        self.apply_widget_policies()

    def save_settings(self):
        self.app.config['accelerator_marker'] = self.accelerator_marker_edit.text()


class AISettingsPage(BaseSettingsPage):
    def __init__(self, app_instance):
        super().__init__()
        self.app = app_instance

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        content_widget = QWidget()
        content_widget.setObjectName("aiContent")
        content_widget.setStyleSheet("#aiContent { background-color: #FFFFFF; }")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(15)

        # Model Management Section
        model_group = QGroupBox(_("AI Models"))
        model_layout = QVBoxLayout(model_group)

        # Show currently active model
        self.lbl_active_model_name = QLabel()
        self.lbl_active_model_name.setStyleSheet("font-size: 14px; margin-bottom: 2px;")

        from ui_components.elided_label import ElidedLabel
        self.lbl_active_model_detail = ElidedLabel()
        self.lbl_active_model_detail.setStyleSheet("color: gray; font-size: 12px;")

        self.update_active_model_label()

        model_layout.addWidget(self.lbl_active_model_name)
        model_layout.addWidget(self.lbl_active_model_detail)

        self.btn_manage_models = QPushButton(_("Manage AI Models..."))
        self.btn_manage_models.setMinimumHeight(36)
        self.btn_manage_models.clicked.connect(self.open_model_manager)
        model_layout.addWidget(self.btn_manage_models)

        content_layout.addWidget(model_group)

        # Performance
        perf_group = QGroupBox(_("Global Settings"))
        perf_layout = QFormLayout(perf_group)
        self.interval_spinbox = QSpinBox()
        self.interval_spinbox.setRange(0, 10000)
        self.interval_spinbox.setSuffix(" ms")
        self.interval_spinbox.setValue(self.app.config.get("ai_api_interval", 100))
        perf_layout.addRow(_("API Call Interval:"), self.interval_spinbox)
        content_layout.addWidget(perf_group)

        # Context & Prompts
        context_group = QGroupBox(_("Context & Prompts"))
        context_layout = QVBoxLayout(context_group)
        prompt_select_layout = QFormLayout()

        self.trans_prompt_combo = QComboBox()
        self.fix_prompt_combo = QComboBox()
        self._populate_prompt_combos()

        prompt_select_layout.addRow(_("Translation Prompt:"), self.trans_prompt_combo)
        prompt_select_layout.addRow(_("Correction Prompt:"), self.fix_prompt_combo)

        context_layout.addLayout(prompt_select_layout)
        context_layout.addSpacing(10)

        # Context Strategy Group
        context_group = QGroupBox(_("Context Strategy"))
        context_layout = QGridLayout(context_group)
        context_layout.setVerticalSpacing(10)
        context_layout.setColumnStretch(1, 1)

        # 1. Neighboring Text
        self.chk_neighbors = QCheckBox(_("Neighboring Text"))
        self.chk_neighbors.setToolTip(_("Include nearby original and translated text."))
        self.chk_neighbors.setChecked(self.app.config.get("ai_use_neighbors", True))

        self.spin_neighbors = QSpinBox()
        self.spin_neighbors.setRange(1, 20)
        self.spin_neighbors.setValue(self.app.config.get("ai_context_neighbors", 3))
        self.spin_neighbors.setSuffix(_(" lines"))
        self.chk_neighbors.stateChanged.connect(self.spin_neighbors.setEnabled)
        self.spin_neighbors.setEnabled(self.chk_neighbors.isChecked())

        context_layout.addWidget(self.chk_neighbors, 0, 0)
        context_layout.addWidget(self.spin_neighbors, 0, 1)

        # 2. Semantic Retrieval (RAG)
        self.chk_retrieval = QCheckBox(_("Semantic Retrieval"))
        self.chk_retrieval.setToolTip(_("Search for semantically similar texts (Requires Index)."))
        self.chk_retrieval.setChecked(self.app.config.get("ai_use_retrieval", False))

        rag_opts_layout = QHBoxLayout()
        self.spin_retrieval = QSpinBox()
        self.spin_retrieval.setRange(1, 10)
        self.spin_retrieval.setValue(self.app.config.get("ai_retrieval_limit", 3))
        self.spin_retrieval.setSuffix(_(" items"))

        self.combo_retrieval_mode = QComboBox()
        self.combo_retrieval_mode.addItem(_("Auto"), "auto")
        self.combo_retrieval_mode.addItem("TF-IDF", "tfidf")
        self.combo_retrieval_mode.addItem("Local LLM", "onnx")
        current_rag_mode = self.app.config.get("ai_retrieval_mode", "auto")
        idx = self.combo_retrieval_mode.findData(current_rag_mode)
        if idx != -1: self.combo_retrieval_mode.setCurrentIndex(idx)

        # Check plugin availability
        if hasattr(self.app, 'plugin_manager'):
            plugin = self.app.plugin_manager.get_plugin("com_theskyc_retrieval_enhancer")
            if not plugin:
                self.chk_retrieval.setEnabled(False)
                self.chk_retrieval.setToolTip(_("Retrieval Enhancer plugin not found."))

        self.chk_retrieval.stateChanged.connect(self.spin_retrieval.setEnabled)
        self.chk_retrieval.stateChanged.connect(self.combo_retrieval_mode.setEnabled)
        self.spin_retrieval.setEnabled(self.chk_retrieval.isChecked())
        self.combo_retrieval_mode.setEnabled(self.chk_retrieval.isChecked())

        rag_opts_layout.addWidget(self.spin_retrieval)
        rag_opts_layout.addWidget(self.combo_retrieval_mode)
        rag_opts_layout.addStretch()

        context_layout.addWidget(self.chk_retrieval, 1, 0)
        context_layout.addLayout(rag_opts_layout, 1, 1)

        # 3. Translation Memory (TM)
        self.chk_tm = QCheckBox(_("Translation Memory"))
        self.chk_tm.setChecked(self.app.config.get("ai_use_tm", True))

        tm_opts_layout = QHBoxLayout()
        self.tm_mode_group = QButtonGroup(self)
        self.rb_tm_exact = QRadioButton(_("Exact"))
        self.rb_tm_fuzzy = QRadioButton(_("Fuzzy"))
        self.tm_mode_group.addButton(self.rb_tm_exact)
        self.tm_mode_group.addButton(self.rb_tm_fuzzy)

        if self.app.config.get("ai_tm_mode", "fuzzy") == "exact":
            self.rb_tm_exact.setChecked(True)
        else:
            self.rb_tm_fuzzy.setChecked(True)

        self.spin_tm_threshold = QDoubleSpinBox()
        self.spin_tm_threshold.setRange(0.1, 1.0)
        self.spin_tm_threshold.setSingleStep(0.05)
        self.spin_tm_threshold.setValue(self.app.config.get("ai_tm_threshold", 0.75))
        self.spin_tm_threshold.setToolTip(_("Fuzzy Match Threshold"))

        self.chk_tm.toggled.connect(self.rb_tm_exact.setEnabled)
        self.chk_tm.toggled.connect(self.rb_tm_fuzzy.setEnabled)
        self.chk_tm.toggled.connect(self.spin_tm_threshold.setEnabled)

        # Initial state
        is_tm_on = self.chk_tm.isChecked()
        self.rb_tm_exact.setEnabled(is_tm_on)
        self.rb_tm_fuzzy.setEnabled(is_tm_on)
        self.spin_tm_threshold.setEnabled(is_tm_on)

        tm_opts_layout.addWidget(self.rb_tm_exact)
        tm_opts_layout.addWidget(self.rb_tm_fuzzy)
        tm_opts_layout.addWidget(QLabel(_("Threshold:")))
        tm_opts_layout.addWidget(self.spin_tm_threshold)
        tm_opts_layout.addStretch()

        context_layout.addWidget(self.chk_tm, 2, 0)
        context_layout.addLayout(tm_opts_layout, 2, 1)

        # 4. Glossary
        self.chk_glossary = QCheckBox(_("Glossary Database"))
        self.chk_glossary.setChecked(self.app.config.get("ai_use_glossary", True))
        context_layout.addWidget(self.chk_glossary, 3, 0, 1, 2)

        content_layout.addWidget(context_group)

        # Prompts Group
        prompt_group = QGroupBox(_("Prompts"))
        prompt_layout = QVBoxLayout(prompt_group)

        prompt_select_layout = QFormLayout()

        self.trans_prompt_combo = QComboBox()
        self.fix_prompt_combo = QComboBox()
        self._populate_prompt_combos()

        prompt_select_layout.addRow(_("Translation Prompt:"), self.trans_prompt_combo)
        prompt_select_layout.addRow(_("Correction Prompt:"), self.fix_prompt_combo)

        prompt_layout.addLayout(prompt_select_layout)
        prompt_layout.addSpacing(15)

        self.prompt_button = QPushButton(_("Prompt Manager..."))
        self.prompt_button.clicked.connect(self.open_prompt_manager)
        prompt_layout.addWidget(self.prompt_button)

        content_layout.addWidget(prompt_group)
        content_layout.addStretch(1)
        scroll_area.setWidget(content_widget)

        self.page_layout.addWidget(scroll_area)
        self.apply_widget_policies()

    def update_active_model_label(self):
        active_id = self.app.config.get("active_ai_model_id", "")
        models = self.app.config.get("ai_models", [])
        active_model = next((m for m in models if m["id"] == active_id), None)

        if active_model:
            # Line 1: Profile Name
            self.lbl_active_model_name.setText(
                f"<b>{_('Current Active Model')}:</b> {active_model.get('name', 'Unknown')}")

            # Line 2: Model ID @ URL
            detail_text = f"{active_model.get('model_name', '')} @ {active_model.get('api_base_url', '')}"
            self.lbl_active_model_detail.setText(detail_text)
            self.lbl_active_model_detail.setToolTip(detail_text)
        else:
            self.lbl_active_model_name.setText(f"<b>{_('Current Active Model')}:</b> {_('None Selected')}")
            self.lbl_active_model_detail.setText("")
            self.lbl_active_model_detail.setToolTip("")

    def open_model_manager(self):
        from dialogs.ai_model_manager_dialog import AIModelManagerDialog
        dialog = AIModelManagerDialog(self, self.app)
        if dialog.exec():
            self.update_active_model_label()

    def _populate_prompt_combos(self):
        self.trans_prompt_combo.clear()
        self.fix_prompt_combo.clear()

        prompts = self.app.config.get("ai_prompts", [])
        for p in prompts:
            if p.get("type") == "translation":
                self.trans_prompt_combo.addItem(p["name"], p["id"])
            elif p.get("type") == "correction":
                self.fix_prompt_combo.addItem(p["name"], p["id"])

        curr_trans = self.app.config.get("active_translation_prompt_id")
        curr_fix = self.app.config.get("active_correction_prompt_id")

        idx_t = self.trans_prompt_combo.findData(curr_trans)
        if idx_t != -1: self.trans_prompt_combo.setCurrentIndex(idx_t)

        idx_f = self.fix_prompt_combo.findData(curr_fix)
        if idx_f != -1: self.fix_prompt_combo.setCurrentIndex(idx_f)

    def open_prompt_manager(self):
        self.app.show_prompt_manager()
        try:
            if self.trans_prompt_combo.parent() is not None:
                self._populate_prompt_combos()
        except RuntimeError:
            pass

    def save_settings(self):
        self.app.config["ai_api_interval"] = self.interval_spinbox.value()
        # Content
        self.app.config["ai_use_neighbors"] = self.chk_neighbors.isChecked()
        self.app.config["ai_context_neighbors"] = self.spin_neighbors.value()

        self.app.config["ai_use_retrieval"] = self.chk_retrieval.isChecked()
        self.app.config["ai_retrieval_limit"] = self.spin_retrieval.value()
        self.app.config["ai_retrieval_mode"] = self.combo_retrieval_mode.currentData()

        self.app.config["ai_use_tm"] = self.chk_tm.isChecked()
        self.app.config["ai_tm_mode"] = "exact" if self.rb_tm_exact.isChecked() else "fuzzy"
        self.app.config["ai_tm_threshold"] = self.spin_tm_threshold.value()

        self.app.config["ai_use_glossary"] = self.chk_glossary.isChecked()

        # Other
        self.app.config["active_translation_prompt_id"] = self.trans_prompt_combo.currentData()
        self.app.config["active_correction_prompt_id"] = self.fix_prompt_combo.currentData()
        return False

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
        label_text = config_data.get("label", key)
        self.checkbox = QCheckBox(_(label_text))
        self.checkbox.setChecked(config_data.get("enabled", True))
        self.checkbox.stateChanged.connect(self.update_state)

        # Modes
        self.mode_combo = QComboBox()
        self.mode_combo.setFixedWidth(100)
        available_modes = self.config_data.get("modes")
        if available_modes and len(available_modes) > 1:
            tooltip_parts = [_("Available Modes:")]
            for mode_key, mode_info in available_modes.items():
                display_name = _(mode_info.get("name", mode_key))
                description = _(mode_info.get("description", ""))
                self.mode_combo.addItem(display_name, mode_key)
                tooltip_parts.append(f"<b>• {display_name}:</b> {description}")
            self.mode_combo.setToolTip("<br>".join(tooltip_parts))
            current_mode = self.config_data.get("mode", self.config_data.get("default_mode"))
            index = self.mode_combo.findData(current_mode)
            if index != -1:
                self.mode_combo.setCurrentIndex(index)
        else:
            self.mode_combo.setVisible(False)

        # Level
        self.level_combo = QComboBox()
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
        layout.addWidget(self.mode_combo)
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
        is_enabled = self.checkbox.isChecked()
        self.level_combo.setEnabled(is_enabled)
        self.mode_combo.setEnabled(is_enabled)

    def get_data(self):
        data = {
            "enabled": self.checkbox.isChecked(),
            "level": self.level_combo.currentData(),
            "label": self.config_data.get("label", self.key)
        }
        if self.mode_combo.isVisible():
            data["mode"] = self.mode_combo.currentData()
            data["modes"] = self.config_data.get("modes")
            data["default_mode"] = self.config_data.get("default_mode")
        return data

class ValidationSettingsPage(BaseSettingsPage):
    def __init__(self, app_instance):
        super().__init__()
        self.app = app_instance
        self.rule_widgets = {}

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        content_widget = QWidget()
        content_widget.setObjectName("validationContent")
        content_widget.setStyleSheet("#validationContent { background-color: #FFFFFF; }")

        self.main_layout = QVBoxLayout(content_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        # 获取当前配置
        current_rules = self.app.config.get("validation_rules", DEFAULT_VALIDATION_RULES)

        # 分组定义
        groups = {
            _("Code Safety"): ["printf", "python_brace", "html_tags", "url_email", "accelerator"],
            _("Content Consistency"): ["numbers", "glossary", "fuzzy", "repeated_word"],
            _("Formatting & Punctuation"): ["punctuation", "brackets", "whitespace", "double_space", "capitalization", "newline_count", "quotes", "pangu"]
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

        scroll_area.setWidget(content_widget)
        self.page_layout.addWidget(scroll_area)
        self._take_state_snapshot()

        self.apply_widget_policies()

    def _take_state_snapshot(self):
        self._initial_rules_state = {}
        for key, widget in self.rule_widgets.items():
            self._initial_rules_state[key] = widget.get_data()
        self._initial_length_state = {
            'check': self.check_length.isChecked(),
            'major': self.major_threshold.value(),
            'minor': self.minor_threshold.value()
        }

    def save_settings(self):
        new_rules = {}
        for key, widget in self.rule_widgets.items():
            new_rules[key] = widget.get_data()

        new_length_state = {
            'check': self.check_length.isChecked(),
            'major': self.major_threshold.value(),
            'minor': self.minor_threshold.value()
        }

        rules_changed = new_rules != self._initial_rules_state

        length_settings_changed = (
                new_length_state['check'] != self._initial_length_state['check'] or
                abs(new_length_state['major'] - self._initial_length_state['major']) > 0.001 or
                abs(new_length_state['minor'] - self._initial_length_state['minor']) > 0.001
        )

        if rules_changed or length_settings_changed:
            self.app.config["validation_rules"] = new_rules
            self.app.config['check_length'] = new_length_state['check']
            self.app.config['length_threshold_major'] = new_length_state['major']
            self.app.config['length_threshold_minor'] = new_length_state['minor']
            self._take_state_snapshot()
            self.app._run_and_refresh_with_validation()

        return False