# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import os
import sys
import json
import uuid
from copy import deepcopy
from PySide6.QtWidgets import QMessageBox, QApplication
from utils.constants import (
    DEFAULT_PROMPT_STRUCTURE, DEFAULT_CORRECTION_PROMPT_STRUCTURE, DEFAULT_KEYBINDINGS,
    DEFAULT_EXTRACTION_PATTERNS, DEFAULT_VALIDATION_RULES
)
from utils.security_utils import encrypt_text, decrypt_text
from utils.path_utils import get_app_data_path
from utils.localization import _
import logging

logger = logging.getLogger(__name__)
CONFIG_FILE = os.path.join(get_app_data_path(), "config.json")

def get_default_font_settings():
    return {
        "enable_custom_fonts": False,
        "ui_font": {
            "family": "Segoe UI, Microsoft YaHei, sans-serif",
            "size": 9
        },
        "editor_font": {
            "family": "Consolas, Microsoft YaHei, monospace",
            "size": 10
        }
    }


def load_config():
    while True:
        try:
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                config_data = {}

            # General settings
            config_data.setdefault("deduplicate", False)
            config_data.setdefault("show_ignored", True)
            config_data.setdefault("show_untranslated", False)
            config_data.setdefault("show_translated", False)
            config_data.setdefault("show_unreviewed", False)
            config_data.setdefault("auto_save_tm", False)
            config_data.setdefault("auto_backup_tm_on_save", True)
            config_data.setdefault("apply_and_next_behavior", "untranslated")
            config_data.setdefault("accelerator_marker", "&")
            config_data.setdefault("translation_propagation_mode", "smart")

            # Smart Paste Group
            config_data.setdefault('smart_paste_enabled', True)
            config_data.setdefault('smart_paste_sync_whitespace', True)
            config_data.setdefault('smart_paste_normalize_newlines', True)

            config_data.setdefault('paste_protection_enabled', True)

            config_data.setdefault("last_dir", "")
            config_data.setdefault("recent_files", [])
            config_data.setdefault("ui_state", {})
            config_data.setdefault("favorite_language_pairs", [])

            # AI settings
            config_data.setdefault("ai_models", [])
            config_data.setdefault("active_ai_model_id", "")
            # Decrypt API Keys
            for model in config_data["ai_models"]:
                if "api_key" in model:
                    model["api_key"] = decrypt_text(model["api_key"])

            if not config_data["ai_models"]:
                default_id = str(uuid.uuid4())
                config_data["ai_models"].append({
                    "id": default_id,
                    "name": "DeepSeek V3",
                    "provider": "DeepSeek",
                    "api_base_url": "https://api.deepseek.com",
                    "api_key": "",
                    "model_name": "deepseek-chat",
                    "concurrency": 8,
                    "timeout": 60
                })
                config_data["active_ai_model_id"] = default_id

            config_data.setdefault("ai_api_interval", 100)
            # Global AI Context Settings
            config_data.setdefault("ai_use_neighbors", True)
            config_data.setdefault("ai_context_neighbors", 3)

            config_data.setdefault("ai_use_retrieval", False)
            config_data.setdefault("ai_retrieval_limit", 3)
            config_data.setdefault("ai_retrieval_mode", "auto")

            config_data.setdefault("ai_use_tm", True)
            config_data.setdefault("ai_tm_mode", "fuzzy")
            config_data.setdefault("ai_tm_threshold", 0.75)

            config_data.setdefault("ai_use_glossary", True)

            # Prompt structure
            if "ai_prompts" not in config_data:
                config_data["ai_prompts"] = []

            # Ensure default prompts exist
            has_default_trans = any(p["id"] == "default_translation" for p in config_data["ai_prompts"])
            if not has_default_trans:
                config_data["ai_prompts"].append({
                    "id": "default_translation",
                    "name": "Default Translation",
                    "type": "translation",
                    "structure": deepcopy(DEFAULT_PROMPT_STRUCTURE)
                })

            has_default_fix = any(p["id"] == "default_correction" for p in config_data["ai_prompts"])
            if not has_default_fix:
                config_data["ai_prompts"].append({
                    "id": "default_correction",
                    "name": "Default Correction",
                    "type": "correction",
                    "structure": deepcopy(DEFAULT_CORRECTION_PROMPT_STRUCTURE)
                })

            config_data.setdefault("active_translation_prompt_id", "default_translation")
            config_data.setdefault("active_correction_prompt_id", "default_correction")

            # Extraction patterns
            config_data.setdefault("extraction_patterns", deepcopy(DEFAULT_EXTRACTION_PATTERNS))

            # Keybindings
            if 'keybindings' not in config_data:
                config_data['keybindings'] = DEFAULT_KEYBINDINGS.copy()
            else:
                for key, value in DEFAULT_KEYBINDINGS.items():
                    config_data['keybindings'].setdefault(key, value)

            # Font settings
            default_fonts = get_default_font_settings()
            if "font_settings" not in config_data or "scripts" in config_data["font_settings"]:
                config_data["font_settings"] = default_fonts
            else:
                config_data["font_settings"].setdefault("enable_custom_fonts", default_fonts["enable_custom_fonts"])

                if "ui_font" not in config_data["font_settings"]:
                    config_data["font_settings"]["ui_font"] = default_fonts["ui_font"]
                else:
                    config_data["font_settings"]["ui_font"].setdefault("family", default_fonts["ui_font"]["family"])
                    config_data["font_settings"]["ui_font"].setdefault("size", default_fonts["ui_font"]["size"])

                if "editor_font" not in config_data["font_settings"]:
                    config_data["font_settings"]["editor_font"] = default_fonts["editor_font"]
                else:
                    config_data["font_settings"]["editor_font"].setdefault("family",
                                                                           default_fonts["editor_font"]["family"])
                    config_data["font_settings"]["editor_font"].setdefault("size", default_fonts["editor_font"]["size"])

            # Window state
            config_data.setdefault("window_state", "")
            config_data.setdefault("window_geometry", "")

            # Validation Rules
            if "validation_rules" not in config_data:
                config_data["validation_rules"] = deepcopy(DEFAULT_VALIDATION_RULES)
            else:
                for key, default_val in DEFAULT_VALIDATION_RULES.items():
                    if key not in config_data["validation_rules"]:
                        config_data["validation_rules"][key] = default_val
                    else:
                        user_rule = config_data["validation_rules"][key]
                        user_rule.setdefault("label", default_val.get("label", key))
                        user_rule.setdefault("level", default_val.get("level", "warning"))
                        user_rule.setdefault("enabled", default_val.get("enabled", True))

                        if 'modes' in default_val:
                            user_rule['modes'] = default_val['modes']
                            user_rule['default_mode'] = default_val['default_mode']
                            user_rule.setdefault("mode", default_val.get("default_mode"))

            config_data.setdefault("check_length", True)
            config_data.setdefault("length_threshold_major", 2.5)
            config_data.setdefault("length_threshold_minor", 2.0)

            return config_data
        except (IOError, PermissionError) as e:
            logger.critical(f"Fatal error during config load: {e}")

            app = QApplication.instance()
            if not app:
                print(f"FATAL ERROR: {e}")
                sys.exit(1)

            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setWindowTitle(_("Fatal Error - Encryption Key"))
            msg_box.setText(_("A critical error occurred while trying to access the encryption key."))
            msg_box.setInformativeText(str(e))

            retry_button = msg_box.addButton(_("Retry"), QMessageBox.AcceptRole)
            quit_button = msg_box.addButton(_("Quit"), QMessageBox.RejectRole)

            msg_box.exec()

            if msg_box.clickedButton() == quit_button:
                sys.exit(1)


def save_config(app_instance):
    while True:
        try:
            # Deep copy config to avoid modifying the runtime state
            config_to_save = deepcopy(app_instance.config)

            # Encrypt API Keys
            if "ai_models" in config_to_save:
                for model in config_to_save["ai_models"]:
                    if "api_key" in model:
                        model["api_key"] = encrypt_text(model["api_key"])

            config_to_save['extraction_patterns'] = app_instance.config.get("extraction_patterns",
                                                                            deepcopy(DEFAULT_EXTRACTION_PATTERNS))

            if app_instance.current_project_path:
                config_to_save["last_dir"] = os.path.dirname(app_instance.current_project_path)
            elif app_instance.current_code_file_path:
                config_to_save["last_dir"] = os.path.dirname(app_instance.current_code_file_path)
            elif app_instance.current_po_file_path:
                config_to_save["last_dir"] = os.path.dirname(app_instance.current_po_file_path)

            os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)

            # Perform the actual save
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config_to_save, f, indent=4, ensure_ascii=False)

            return True

        except (IOError, PermissionError) as e:
            logger.critical(f"Fatal error during config save: {e}")

            msg_box = QMessageBox(app_instance)
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setWindowTitle(_("Save Error - Encryption Key"))
            msg_box.setText(_("A critical error occurred while trying to access the encryption key for saving."))
            msg_box.setInformativeText(str(e))

            retry_button = msg_box.addButton(_("Retry"), QMessageBox.AcceptRole)
            plaintext_button = msg_box.addButton(_("Save as Plaintext (Insecure)"), QMessageBox.DestructiveRole)
            cancel_button = msg_box.addButton(_("Cancel Save"), QMessageBox.RejectRole)

            msg_box.exec()

            clicked_button = msg_box.clickedButton()

            if clicked_button == retry_button:
                continue
            elif clicked_button == plaintext_button:
                try:
                    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                        json.dump(app_instance.config, f, indent=4, ensure_ascii=False)

                    QMessageBox.warning(app_instance, _("Security Warning"),
                                        _("Configuration was saved with API keys in plaintext. "
                                          "Please resolve the file permission issue and save again to re-enable encryption."))
                    return True
                except Exception as plain_e:
                    QMessageBox.critical(app_instance, _("Save Failed"),
                                         _("Failed to save even in plaintext mode. Error: {error}").format(
                                             error=plain_e))
                    return False
            else:  # Cancel
                return False