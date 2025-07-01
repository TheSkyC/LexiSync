# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QCheckBox, QSpinBox, QMessageBox, QWidget, QGroupBox, QApplication
)
from PySide6.QtCore import Qt, Signal, QObject, QTimer
import threading
from services.ai_translator import AITranslator
from utils.constants import DEFAULT_API_URL, DEFAULT_PROMPT_STRUCTURE
from utils.localization import _
from services.prompt_service import generate_prompt_from_structure
from dialogs.prompt_manager_dialog import PromptManagerDialog

class AISettingsDialog(QDialog):
    def __init__(self, parent, title, app_config_ref, save_config_callback, ai_translator_ref, app_instance):
        super().__init__(parent)
        self.app_config = app_config_ref
        self.save_config_callback = save_config_callback
        self.ai_translator_instance = ai_translator_ref
        self.app = app_instance

        self.setWindowTitle(title)
        self.setModal(True)

        self.initial_api_key = self.app_config.get("ai_api_key", "")
        self.initial_api_base_url = self.app_config.get("ai_api_base_url", DEFAULT_API_URL)
        self.initial_target_language = self.app_config.get("ai_target_language", _("Target Language"))
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
        self.target_language_entry = QLineEdit(self.initial_target_language)
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
        self.test_btn.clicked.connect(self.test_api_connection_dialog)
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

    def test_api_connection_dialog(self):
        self.test_status_label.setText(_("Testing..."))
        QApplication.processEvents()

        api_key = self.api_key_entry.text()
        api_url = self.api_base_url_entry.text().strip() or DEFAULT_API_URL
        model_name = self.model_name_entry.text().strip()

        if not api_key:
            QMessageBox.critical(self, _("Test Failed"), _("API Key is not filled."))
            self.test_status_label.setText(_("Test failed: API Key is not filled."))
            return

        temp_translator = AITranslator(api_key, model_name, api_url)
        class TestWorker(QObject):
            finished = Signal(bool, str)

            def __init__(self, translator, system_prompt, test_text):
                super().__init__()
                self.translator = translator
                self.system_prompt = system_prompt
                self.test_text = test_text

            def run(self):
                success, message = self.translator.test_connection(system_prompt=self.system_prompt, test_text=self.test_text)
                self.finished.emit(success, message)

        self.test_thread = threading.Thread(target=self._test_in_thread_wrapper, args=(temp_translator, api_key, model_name, api_url))
        self.test_thread.daemon = True
        self.test_thread.start()

    def _test_in_thread_wrapper(self, temp_translator, api_key, model_name, api_url):
        placeholders = {'[Target Language]': _('Target Language'), '[Custom Translate]': '', '[Untranslated Context]': '',
                        '[Translated Context]': ''}
        test_prompt = generate_prompt_from_structure(
            self.app_config.get("ai_prompt_structure", DEFAULT_PROMPT_STRUCTURE), placeholders)

        success, message = temp_translator.test_connection(system_prompt=test_prompt)
        self.app.thread_signals.handle_ai_result.emit("", "", message, False)
        QTimer.singleShot(0, lambda: self._show_test_result(success, message))


    def _show_test_result(self, success, message):
        if self.isVisible():
            self.test_status_label.setText(message)
            if success:
                QMessageBox.information(self, _("Test Connection"), message)
            else:
                QMessageBox.critical(self, _("Test Connection"), message)

    def accept(self):
        api_key = self.api_key_entry.text()
        api_base_url = self.api_base_url_entry.text().strip()
        target_language = self.target_language_entry.text().strip()
        model_name = self.model_name_entry.text().strip()
        api_interval = self.api_interval_spinbox.value()
        use_context = self.use_context_check.isChecked()
        context_neighbors = self.context_neighbors_spinbox.value()
        use_original_context = self.use_original_context_check.isChecked()
        original_context_neighbors = self.original_context_neighbors_spinbox.value()
        max_concurrent_requests = self.max_concurrent_requests_spinbox.value()

        if not target_language:
            QMessageBox.critical(self, _("Error"), _("Target language cannot be empty."))
            self.target_language_entry.setFocus()
            return
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
        self.app_config["ai_target_language"] = target_language
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
                   target_language != self.initial_target_language or
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