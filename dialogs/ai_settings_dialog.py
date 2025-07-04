# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QCheckBox, QSpinBox, QMessageBox, QWidget, QGroupBox, QApplication
)
from PySide6.QtCore import Qt, Signal, QObject, QTimer, QThread
import threading
from services.ai_translator import AITranslator
from utils.constants import DEFAULT_API_URL, DEFAULT_PROMPT_STRUCTURE, SUPPORTED_LANGUAGES
from utils.localization import _
from services.prompt_service import generate_prompt_from_structure
from dialogs.prompt_manager_dialog import PromptManagerDialog

class TestConnectionWorker(QObject):
    finished = Signal(bool, str)

    def __init__(self, api_key, model_name, api_url, system_prompt):
        super().__init__()
        self.api_key = api_key
        self.model_name = model_name
        self.api_url = api_url
        self.system_prompt = system_prompt

    def run(self):
        try:
            translator = AITranslator(self.api_key, self.model_name, self.api_url)
            success, message = translator.test_connection(system_prompt=self.system_prompt)
            self.finished.emit(success, message)
        except Exception as e:
            self.finished.emit(False, str(e))

class AISettingsDialog(QDialog):
    def __init__(self, parent, title, app_config_ref, save_config_callback, ai_translator_ref, app_instance, current_target_lang_name):
        super().__init__(parent)
        self.app_config = app_config_ref
        self.save_config_callback = save_config_callback
        self.ai_translator_instance = ai_translator_ref
        self.app = app_instance
        self.current_target_lang_name = current_target_lang_name

        self.setWindowTitle(title)
        self.setModal(True)
        self.test_thread = None
        self.worker = None

        self.initial_api_key = self.app_config.get("ai_api_key", "")
        self.initial_api_base_url = self.app_config.get("ai_api_base_url", DEFAULT_API_URL)
        self.initial_api_interval = self.app_config.get("ai_api_interval", 200)
        self.initial_model_name = self.app_config.get("ai_model_name", "deepseek-chat")
        self.initial_max_concurrent_requests = self.app_config.get("ai_max_concurrent_requests", 1)
        self.initial_use_context = self.app_config.get("ai_use_translation_context", False)
        self.initial_context_neighbors = self.app_config.get("ai_context_neighbors", 0)
        self.initial_use_original_context = self.app_config.get("ai_use_original_context", True)
        self.initial_original_context_neighbors = self.app_config.get("ai_original_context_neighbors", 3)

        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        # API Connection & Model Settings
        api_frame = QGroupBox(_("API Connection & Model Settings"))
        api_layout = QVBoxLayout(api_frame)

        api_key_layout = QHBoxLayout()
        api_key_layout.addWidget(QLabel(_("API Key:")))
        self.api_key_entry = QLineEdit(self.initial_api_key)
        self.api_key_entry.setEchoMode(QLineEdit.Password)
        api_key_layout.addWidget(self.api_key_entry)
        api_layout.addLayout(api_key_layout)

        api_base_url_layout = QHBoxLayout()
        api_base_url_layout.addWidget(QLabel(_("API Base URL:")))
        self.api_base_url_entry = QLineEdit(self.initial_api_base_url)
        api_base_url_layout.addWidget(self.api_base_url_entry)
        api_layout.addLayout(api_base_url_layout)

        model_name_layout = QHBoxLayout()
        model_name_layout.addWidget(QLabel(_("Model Name:")))
        self.model_name_entry = QLineEdit(self.initial_model_name)
        model_name_layout.addWidget(self.model_name_entry)
        api_layout.addLayout(model_name_layout)

        main_layout.addWidget(api_frame)

        trans_frame = QGroupBox(_("Translation & Context Settings"))
        trans_layout = QVBoxLayout(trans_frame)

        target_language_layout = QHBoxLayout()
        target_language_layout.addWidget(QLabel(_("Target Language:")))
        self.target_language_entry = QLineEdit(self.current_target_lang_name)
        self.target_language_entry.setReadOnly(True)
        self.target_language_entry.setToolTip(_("Target language is set in 'Settings > Language Pair Settings...'"))
        target_language_layout.addWidget(self.target_language_entry)
        trans_layout.addLayout(target_language_layout)

        api_interval_layout = QHBoxLayout()
        api_interval_layout.addWidget(QLabel(_("API Call Interval (ms):")))
        self.api_interval_spinbox = QSpinBox()
        self.api_interval_spinbox.setRange(0, 10000)
        self.api_interval_spinbox.setSingleStep(50)
        self.api_interval_spinbox.setValue(self.initial_api_interval)
        api_interval_layout.addWidget(self.api_interval_spinbox)
        api_interval_layout.addStretch(1)
        trans_layout.addLayout(api_interval_layout)

        max_concurrent_requests_layout = QHBoxLayout()
        max_concurrent_requests_layout.addWidget(QLabel(_("Max Concurrent Requests:")))
        self.max_concurrent_requests_spinbox = QSpinBox()
        self.max_concurrent_requests_spinbox.setRange(1, 10)
        self.max_concurrent_requests_spinbox.setSingleStep(1)
        self.max_concurrent_requests_spinbox.setValue(self.initial_max_concurrent_requests)
        max_concurrent_requests_layout.addWidget(self.max_concurrent_requests_spinbox)
        max_concurrent_requests_layout.addStretch(1)
        trans_layout.addLayout(max_concurrent_requests_layout)

        self.use_original_context_check = QCheckBox(_("Use nearby original text as context"))
        self.use_original_context_check.setChecked(self.initial_use_original_context)
        self.use_original_context_check.stateChanged.connect(self.toggle_context_neighbors_state)
        trans_layout.addWidget(self.use_original_context_check)

        original_context_neighbor_layout = QHBoxLayout()
        original_context_neighbor_layout.addSpacing(20)
        original_context_neighbor_layout.addWidget(QLabel(_("Use nearby")))
        self.original_context_neighbors_spinbox = QSpinBox()
        self.original_context_neighbors_spinbox.setRange(0, 10)
        self.original_context_neighbors_spinbox.setSingleStep(1)
        self.original_context_neighbors_spinbox.setValue(self.initial_original_context_neighbors)
        original_context_neighbor_layout.addWidget(self.original_context_neighbors_spinbox)
        original_context_neighbor_layout.addWidget(QLabel(_("original strings (0 for all)")))
        original_context_neighbor_layout.addStretch(1)
        trans_layout.addLayout(original_context_neighbor_layout)

        self.use_context_check = QCheckBox(_("Use nearby translated text as context"))
        self.use_context_check.setChecked(self.initial_use_context)
        self.use_context_check.stateChanged.connect(self.toggle_context_neighbors_state)
        trans_layout.addWidget(self.use_context_check)

        context_neighbor_layout = QHBoxLayout()
        context_neighbor_layout.addSpacing(20)
        context_neighbor_layout.addWidget(QLabel(_("Use nearby")))
        self.context_neighbors_spinbox = QSpinBox()
        self.context_neighbors_spinbox.setRange(0, 10)
        self.context_neighbors_spinbox.setSingleStep(1)
        self.context_neighbors_spinbox.setValue(self.initial_context_neighbors)
        context_neighbor_layout.addWidget(self.context_neighbors_spinbox)
        context_neighbor_layout.addWidget(QLabel(_("translations (0 for all)")))
        context_neighbor_layout.addStretch(1)
        trans_layout.addLayout(context_neighbor_layout)

        main_layout.addWidget(trans_frame)

        self.test_status_label = QLabel("")
        self.test_status_label.setWordWrap(True)
        main_layout.addWidget(self.test_status_label)

        self.toggle_context_neighbors_state()

        # Buttons
        button_box = QHBoxLayout()
        self.prompt_btn = QPushButton(_("Prompt Manager..."))
        self.prompt_btn.clicked.connect(self.show_prompt_manager)
        button_box.addWidget(self.prompt_btn)
        button_box.addStretch(1)

        self.test_btn = QPushButton(_("Test Connection"))
        self.test_btn.clicked.connect(self.start_test_connection)
        button_box.addWidget(self.test_btn)

        self.ok_btn = QPushButton(_("OK"))
        self.ok_btn.clicked.connect(self.accept)
        button_box.addWidget(self.ok_btn)

        self.cancel_btn = QPushButton(_("Cancel"))
        self.cancel_btn.clicked.connect(self.reject)
        button_box.addWidget(self.cancel_btn)

        main_layout.addLayout(button_box)

    def toggle_context_neighbors_state(self):
        self.context_neighbors_spinbox.setEnabled(self.use_context_check.isChecked())
        self.original_context_neighbors_spinbox.setEnabled(self.use_original_context_check.isChecked())

    def show_prompt_manager(self):
        dialog = PromptManagerDialog(self, _("AI Prompt Manager"), self.app)
        dialog.exec()

    def start_test_connection(self):
        self.test_btn.setEnabled(False)
        self.test_status_label.setText(_("Testing..."))
        QApplication.processEvents()

        api_key = self.api_key_entry.text()
        api_url = self.api_base_url_entry.text().strip() or DEFAULT_API_URL
        model_name = self.model_name_entry.text().strip()

        if not api_key:
            QMessageBox.critical(self, _("Test Failed"), _("API Key is not filled."))
            self.test_status_label.setText(_("Test failed: API Key is not filled."))
            self.test_btn.setEnabled(True)
            return
        target_lang_code = self.app.target_language
        target_lang_name = next((name for name, code in SUPPORTED_LANGUAGES.items() if code == target_lang_code),
                                target_lang_code)

        placeholders = {
            '[Target Language]': target_lang_name,
            '[Custom Translate]': '',
            '[Untranslated Context]': '',
            '[Translated Context]': ''
        }
        system_prompt = generate_prompt_from_structure(
            self.app_config.get("ai_prompt_structure", DEFAULT_PROMPT_STRUCTURE), placeholders
        )
        self.test_thread = QThread()
        self.worker = TestConnectionWorker(api_key, model_name, api_url, system_prompt)
        self.worker.moveToThread(self.test_thread)

        self.test_thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_test_finished)

        self.worker.finished.connect(self.test_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.test_thread.finished.connect(self.test_thread.deleteLater)

        self.test_thread.start()

    def on_test_finished(self, success, message):
        self.test_status_label.setText(message)
        if success:
            QMessageBox.information(self, _("Test Connection"), message)
        else:
            QMessageBox.critical(self, _("Test Connection"), message)

        self.test_btn.setEnabled(True)

    def accept(self):
        api_key = self.api_key_entry.text()
        api_base_url = self.api_base_url_entry.text().strip()
        model_name = self.model_name_entry.text().strip()
        api_interval = self.api_interval_spinbox.value()
        use_context = self.use_context_check.isChecked()
        context_neighbors = self.context_neighbors_spinbox.value()
        use_original_context = self.use_original_context_check.isChecked()
        original_context_neighbors = self.original_context_neighbors_spinbox.value()
        max_concurrent_requests = self.max_concurrent_requests_spinbox.value()

        if not model_name:
            QMessageBox.critical(self, _("Error"), _("Model name cannot be empty."))
            self.model_name_entry.setFocus()
            return
        if api_interval < 0:
            QMessageBox.critical(self, _("Error"), _("API call interval cannot be negative."))
            self.api_interval_spinbox.setFocus()
            return
        if not (1 <= max_concurrent_requests <= 10):
            QMessageBox.critical(self, _("Error"), _("Max concurrent requests must be between 1 and 10."))
            self.max_concurrent_requests_spinbox.setFocus()
            return

        self.app_config["ai_api_key"] = api_key
        self.app_config["ai_api_base_url"] = api_base_url if api_base_url else DEFAULT_API_URL
        self.app_config["ai_model_name"] = model_name
        self.app_config["ai_api_interval"] = api_interval
        self.app_config["ai_use_translation_context"] = use_context
        self.app_config["ai_context_neighbors"] = context_neighbors
        self.app_config["ai_use_original_context"] = use_original_context
        self.app_config["ai_original_context_neighbors"] = original_context_neighbors
        self.app_config["ai_max_concurrent_requests"] = max_concurrent_requests

        self.ai_translator_instance.api_key = api_key
        self.ai_translator_instance.model_name = model_name
        self.ai_translator_instance.api_url = api_base_url if api_base_url else DEFAULT_API_URL

        changed = (api_key != self.initial_api_key or
                   api_base_url != self.initial_api_base_url or
                   model_name != self.initial_model_name or
                   api_interval != self.initial_api_interval or
                   use_context != self.initial_use_context or
                   context_neighbors != self.initial_context_neighbors or
                   use_original_context != self.initial_use_original_context or
                   original_context_neighbors != self.initial_original_context_neighbors or
                   max_concurrent_requests != self.initial_max_concurrent_requests)

        if changed:
            self.save_config_callback()

        super().accept()

    def reject(self):
        super().reject()