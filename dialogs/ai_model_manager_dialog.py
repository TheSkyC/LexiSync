# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QLineEdit, QPushButton, QGroupBox, QFormLayout, QComboBox,
    QSpinBox, QSplitter, QMessageBox, QApplication, QDialogButtonBox
)
from PySide6.QtCore import Qt
import uuid
import copy
from services.ai_translator import AITranslator
from ui_components.help_button import HelpButton
from ui_components.styled_button import StyledButton
from utils.path_utils import get_resource_path
from utils.constants import AI_PROVIDER_PRESETS
from utils.localization import _


class AIModelManagerDialog(QDialog):
    def __init__(self, parent, app_instance):
        super().__init__(parent)
        self.app = app_instance
        self.setWindowTitle(_("AI Model Manager"))
        self.resize(800, 600)

        icon_down = get_resource_path("icons/chevron-down.svg").replace("\\", "/")
        icon_up = get_resource_path("icons/chevron-up.svg").replace("\\", "/")

        self.setStyleSheet(f"""
            QDialog {{
                background-color: #F5F7FA;
            }}
            QListWidget {{
                border: 1px solid #DCDFE6;
                border-radius: 4px;
                background-color: #FFFFFF;
                outline: 0;
            }}
            QListWidget::item {{
                padding: 8px 12px;
                border-radius: 4px;
                margin: 2px;
                color: #606266;
            }}
            QListWidget::item:selected {{
                background-color: #E6F7FF;
                color: #409EFF;
                border: 1px solid #BAE7FF;
            }}
            QListWidget::item:hover:!selected {{
                background-color: #F5F7FA;
            }}

            QLineEdit, QComboBox, QSpinBox {{
                padding: 6px 8px;
                border: 1px solid #DCDFE6;
                border-radius: 4px;
                background-color: #FFFFFF;
                min-height: 20px;
                color: #606266;
                selection-background-color: #409EFF;
            }}
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
                border-color: #409EFF;
            }}

            /* QComboBox 美化 */
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 24px;
                border-left: 1px solid #DCDFE6; /* 左侧分割线 */
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
                /* [CHANGED] Use UP arrow when expanded */
                image: url("{icon_up}");
            }}

            /* QSpinBox 美化 */
            QSpinBox {{
                padding-right: 24px;
            }}
            QSpinBox::up-button {{
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 24px;
                border-left: 1px solid #DCDFE6;   /* 左边框 */
                border-bottom: 1px solid #DCDFE6; /* 底部边框*/
                border-top-right-radius: 4px;
                background-color: #FAFAFA;
                margin-bottom: 0px;
            }}
            QSpinBox::down-button {{
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 24px;
                border-left: 1px solid #DCDFE6;   /* 左边框 */
                border-bottom-right-radius: 4px;
                background-color: #FAFAFA;
                margin-top: 0px;
            }}
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
                background-color: #F0F2F5;
            }}
            QSpinBox::up-button:pressed, QSpinBox::down-button:pressed {{
                background-color: #E6F1FC;
            }}
            QSpinBox::up-arrow {{
                image: url("{icon_up}");
                width: 10px;
                height: 10px;
            }}
            QSpinBox::down-arrow {{
                image: url("{icon_down}");
                width: 10px;
                height: 10px;
            }}

            /* GroupBox 样式 */
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
                color: #606266;
            }}
        """)

        self.models_buffer = copy.deepcopy(self.app.config.get("ai_models", []))
        self.active_model_id = self.app.config.get("active_ai_model_id", "")

        # UI State
        self.current_editing_item = None
        self.is_loading_ui = False

        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # Main Content Splitter
        splitter = QSplitter(Qt.Horizontal)

        # --- Left Panel: Model List ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 5, 0)

        self.model_list_widget = QListWidget()
        self.model_list_widget.currentRowChanged.connect(self.on_model_selected)
        left_layout.addWidget(self.model_list_widget)

        # List Buttons
        btn_layout = QHBoxLayout()
        self.btn_add = StyledButton("+", on_click=self.add_model, size="small")
        self.btn_del = StyledButton("-", on_click=self.delete_model, btn_type="danger", size="small")
        self.btn_copy = StyledButton("Copy", on_click=self.duplicate_model, size="small")

        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_del)
        btn_layout.addWidget(self.btn_copy)
        left_layout.addLayout(btn_layout)

        # --- Right Panel: Configuration Form ---
        self.right_widget = QWidget()
        self.right_widget.setEnabled(False)
        right_layout = QVBoxLayout(self.right_widget)
        right_layout.setContentsMargins(10, 0, 0, 0)

        # 1. Header (Name & Active Status)
        header_layout = QHBoxLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText(_("Profile Name (e.g. My DeepSeek)"))
        self.name_edit.textChanged.connect(self.on_name_changed)

        self.btn_set_active = QPushButton(_("Set as Active"))
        self.btn_set_active.setCheckable(True)
        self.btn_set_active.clicked.connect(self.set_current_as_active)
        self.btn_set_active.setStyleSheet("""
            QPushButton:checked { background-color: #4CAF50; color: white; border: none; }
        """)

        header_layout.addWidget(QLabel(_("Name:")))
        header_layout.addWidget(self.name_edit)
        header_layout.addWidget(self.btn_set_active)
        right_layout.addLayout(header_layout)

        # 2. Quick Fill
        preset_group = QGroupBox(_("Quick Setup"))
        preset_layout = QHBoxLayout(preset_group)
        self.preset_combo = QComboBox()
        self.preset_combo.addItem(_("Select a provider template..."), "")
        for provider in AI_PROVIDER_PRESETS.keys():
            self.preset_combo.addItem(provider, provider)
        self.preset_combo.currentIndexChanged.connect(self.apply_preset)

        preset_layout.addWidget(QLabel(_("Template:")))
        preset_layout.addWidget(self.preset_combo)
        right_layout.addWidget(preset_group)

        # 3. Connection Details
        conn_group = QGroupBox(_("Connection Details"))
        conn_layout = QFormLayout(conn_group)

        # -- API Base URL Row with Help Icon --
        self.base_url_edit = QLineEdit()
        self.base_url_edit.setPlaceholderText("https://api.example.com/v1")
        self.base_url_edit.textChanged.connect(self.save_current_form_to_buffer)
        self.base_url_edit.textChanged.connect(self.update_url_tooltip)

        # Container for Label + Help
        url_label_container = QWidget()
        url_label_layout = QHBoxLayout(url_label_container)
        url_label_layout.setContentsMargins(0, 0, 0, 0)
        url_label_layout.setSpacing(4)

        lbl_url = QLabel(_("API Base URL:"))

        # Base help text template
        self.base_help_text = _(
            "<b>Smart URL Handling:</b><br>"
            "• <b>Default:</b> Automatically appends <code>/chat/completions</code>.<br>"
            "• <b>Raw Mode:</b> End with <code>#</code> to disable auto-append.<br>"
            "<hr>"
        )
        self.btn_help = HelpButton(self.base_help_text)

        url_label_layout.addWidget(lbl_url)
        url_label_layout.addWidget(self.btn_help)
        url_label_layout.addStretch()

        conn_layout.addRow(url_label_container, self.base_url_edit)

        # -- API Key --
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setPlaceholderText("sk-...")
        self.api_key_edit.textChanged.connect(self.save_current_form_to_buffer)
        conn_layout.addRow(_("API Key:"), self.api_key_edit)

        # -- Model Name --
        self.model_name_edit = QLineEdit()
        self.model_name_edit.setPlaceholderText("gpt-4o, deepseek-chat...")
        self.model_name_edit.textChanged.connect(self.save_current_form_to_buffer)
        conn_layout.addRow(_("Model Name:"), self.model_name_edit)

        right_layout.addWidget(conn_group)

        # 4. Performance
        perf_group = QGroupBox(_("Performance"))
        perf_layout = QHBoxLayout(perf_group)

        self.concurrency_spin = QSpinBox()
        self.concurrency_spin.setRange(1, 50)
        self.concurrency_spin.setSuffix(_(" threads"))
        self.concurrency_spin.valueChanged.connect(self.save_current_form_to_buffer)

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(5, 300)
        self.timeout_spin.setSuffix(" s")
        self.timeout_spin.valueChanged.connect(self.save_current_form_to_buffer)

        perf_layout.addWidget(QLabel(_("Concurrency:")))
        perf_layout.addWidget(self.concurrency_spin)
        perf_layout.addSpacing(20)
        perf_layout.addWidget(QLabel(_("Timeout:")))
        perf_layout.addWidget(self.timeout_spin)
        right_layout.addWidget(perf_group)

        # 5. Test Button
        self.btn_test = QPushButton(_("Test Connection"))
        self.btn_test.clicked.connect(self.test_connection)
        right_layout.addWidget(self.btn_test)

        right_layout.addStretch()

        splitter.addWidget(left_widget)
        splitter.addWidget(self.right_widget)
        splitter.setSizes([250, 550])

        main_layout.addWidget(splitter)

        # Bottom Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

        self.refresh_model_list()

    def refresh_model_list(self):
        self.is_loading_ui = True
        current_row = self.model_list_widget.currentRow()
        self.model_list_widget.clear()

        for model in self.models_buffer:
            name = model.get("name", "Unnamed")
            if model["id"] == self.active_model_id:
                name += f" ({_('Active')})"
                item = QListWidgetItem(name)
                font = item.font()
                font.setBold(True)
                item.setFont(font)
                item.setForeground(Qt.darkGreen)
            else:
                item = QListWidgetItem(name)

            item.setData(Qt.UserRole, model["id"])
            self.model_list_widget.addItem(item)

        if current_row >= 0 and current_row < self.model_list_widget.count():
            self.model_list_widget.setCurrentRow(current_row)
        elif self.model_list_widget.count() > 0:
            self.model_list_widget.setCurrentRow(0)

        self.is_loading_ui = False

    def on_model_selected(self, row):
        if row < 0:
            self.right_widget.setEnabled(False)
            self.current_editing_item = None
            return

        self.is_loading_ui = True
        self.right_widget.setEnabled(True)

        item = self.model_list_widget.item(row)
        model_id = item.data(Qt.UserRole)
        model_data = next((m for m in self.models_buffer if m["id"] == model_id), None)

        if model_data:
            self.current_editing_item = model_data
            self.name_edit.setText(model_data.get("name", ""))
            self.base_url_edit.setText(model_data.get("api_base_url", ""))
            self.update_url_tooltip(self.base_url_edit.text())
            self.api_key_edit.setText(model_data.get("api_key", ""))
            self.model_name_edit.setText(model_data.get("model_name", ""))
            self.concurrency_spin.setValue(model_data.get("concurrency", 1))
            self.timeout_spin.setValue(model_data.get("timeout", 60))

            is_active = (model_id == self.active_model_id)
            self.btn_set_active.setChecked(is_active)
            self.btn_set_active.setText(_("Active") if is_active else _("Set as Active"))
            self.btn_set_active.setEnabled(not is_active)

            self.preset_combo.blockSignals(True)
            self.preset_combo.setCurrentIndex(0)
            self.preset_combo.blockSignals(False)

        self.is_loading_ui = False

    def save_current_form_to_buffer(self):
        if self.is_loading_ui or not self.current_editing_item:
            return
        self.current_editing_item["name"] = self.name_edit.text()
        self.current_editing_item["api_base_url"] = self.base_url_edit.text()
        self.current_editing_item["api_key"] = self.api_key_edit.text()
        self.current_editing_item["model_name"] = self.model_name_edit.text()
        self.current_editing_item["concurrency"] = self.concurrency_spin.value()
        self.current_editing_item["timeout"] = self.timeout_spin.value()

    def on_name_changed(self, text):
        self.save_current_form_to_buffer()
        current_item = self.model_list_widget.currentItem()
        if current_item and self.current_editing_item:
            display_name = text
            if self.current_editing_item["id"] == self.active_model_id:
                display_name += f" ({_('Active')})"
            current_item.setText(display_name)

    def update_url_tooltip(self, text):
        final_url = AITranslator._normalize_url(text) if text else ""

        if text.strip().endswith('#'):
            mode_text = f"<span style='color:#E6A23C'>[{_('Raw Mode')}]</span>"
        else:
            mode_text = f"<span style='color:#67C23A'>[{_('Auto')}]</span>"

        preview_html = f"<b>{_('Preview')}:</b><br>{mode_text} {final_url}"

        # Combine base help with dynamic preview
        full_tooltip = self.base_help_text + preview_html
        self.btn_help.set_tooltip_text(full_tooltip)

    def apply_preset(self, index):
        if self.is_loading_ui or index <= 0: return
        provider_name = self.preset_combo.currentText()
        preset = AI_PROVIDER_PRESETS.get(provider_name)
        if preset:
            self.base_url_edit.setText(preset["api_base_url"])
            self.model_name_edit.setText(preset["model_name"])
            self.concurrency_spin.setValue(preset["concurrency"])
            current_name = self.name_edit.text()
            if not current_name or current_name.startswith("New Model"):
                self.name_edit.setText(provider_name)

    def add_model(self):
        new_id = str(uuid.uuid4())
        new_model = {
            "id": new_id,
            "name": "New Model",
            "provider": "Custom",
            "api_base_url": "",
            "api_key": "",
            "model_name": "",
            "concurrency": 1,
            "timeout": 60
        }
        self.models_buffer.append(new_model)
        self.refresh_model_list()
        self.model_list_widget.setCurrentRow(self.model_list_widget.count() - 1)
        self.name_edit.setFocus()
        self.name_edit.selectAll()

    def delete_model(self):
        row = self.model_list_widget.currentRow()
        if row < 0: return
        item = self.model_list_widget.item(row)
        model_id = item.data(Qt.UserRole)
        if model_id == self.active_model_id:
            QMessageBox.warning(self, _("Warning"),
                                _("Cannot delete the active model. Please activate another model first."))
            return
        reply = QMessageBox.question(self, _("Confirm Delete"),
                                     _("Are you sure you want to delete this model configuration?"))
        if reply == QMessageBox.Yes:
            self.models_buffer = [m for m in self.models_buffer if m["id"] != model_id]
            self.refresh_model_list()

    def duplicate_model(self):
        if not self.current_editing_item: return
        new_model = self.current_editing_item.copy()
        new_model["id"] = str(uuid.uuid4())
        new_model["name"] = new_model["name"] + " (Copy)"
        self.models_buffer.append(new_model)
        self.refresh_model_list()
        self.model_list_widget.setCurrentRow(self.model_list_widget.count() - 1)

    def set_current_as_active(self):
        if not self.current_editing_item: return
        self.active_model_id = self.current_editing_item["id"]
        self.refresh_model_list()
        self.on_model_selected(self.model_list_widget.currentRow())

    def test_connection(self):
        api_key = self.api_key_edit.text().strip()
        url = self.base_url_edit.text().strip()
        model = self.model_name_edit.text().strip()
        if not url:
            QMessageBox.warning(self, _("Warning"), _("API Base URL is required."))
            return
        self.btn_test.setEnabled(False)
        self.btn_test.setText(_("Testing..."))
        QApplication.processEvents()
        from services.ai_translator import AITranslator
        temp_translator = AITranslator(api_key, model, url)
        try:
            success, message = temp_translator.test_connection()
            if success:
                QMessageBox.information(self, _("Success"), message)
            else:
                QMessageBox.warning(self, _("Failed"), message)
        except Exception as e:
            QMessageBox.critical(self, _("Error"), str(e))
        finally:
            self.btn_test.setEnabled(True)
            self.btn_test.setText(_("Test Connection"))

    def accept(self):
        # Validation
        ids = [m["id"] for m in self.models_buffer]
        if self.active_model_id not in ids and ids:
            self.active_model_id = ids[0]
        elif not ids:
            self.active_model_id = ""

        # Save to App Config
        self.app.config["ai_models"] = self.models_buffer
        self.app.config["active_ai_model_id"] = self.active_model_id

        # Update live translator
        active_model = next((m for m in self.models_buffer if m["id"] == self.active_model_id), None)
        if active_model:
            self.app.config["ai_api_key"] = active_model["api_key"]
            self.app.config["ai_api_base_url"] = active_model["api_base_url"]
            self.app.config["ai_model_name"] = active_model["model_name"]
            self.app.config["ai_max_concurrent_requests"] = active_model["concurrency"]

            self.app.ai_translator.api_key = active_model["api_key"]
            self.app.ai_translator.api_url = active_model["api_base_url"]
            self.app.ai_translator.model_name = active_model["model_name"]

        self.app.save_config()
        self.app.update_statusbar(_("AI models updated."))
        super().accept()