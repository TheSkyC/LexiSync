# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import json
import os
from copy import deepcopy
from utils.constants import (
    CONFIG_FILE, DEFAULT_API_URL, DEFAULT_PROMPT_STRUCTURE, DEFAULT_KEYBINDINGS,
    DEFAULT_EXTRACTION_PATTERNS, DEFAULT_VALIDATION_RULES
)
import logging
logger = logging.getLogger(__name__)


def get_default_font_settings():
    return {
        "override_default_fonts": False,
        "scripts": {
            "latin": {"family": "Segoe UI", "size": 10, "style": "normal"},
            "cjk": {"family": "Microsoft YaHei UI", "size": 10, "style": "normal"},
            "cyrillic": {"family": "Segoe UI", "size": 10, "style": "normal"},
        },
        "code_context": {"family": "Consolas", "size": 9, "style": "normal"}
    }


def load_config():
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
    config_data.setdefault("ai_api_key", "")
    config_data.setdefault("ai_api_base_url", DEFAULT_API_URL)
    config_data.setdefault("ai_model_name", "deepseek-chat")
    config_data.setdefault("ai_api_interval", 200)
    config_data.setdefault("ai_max_concurrent_requests", 1)
    config_data.setdefault("ai_use_translation_context", False)
    config_data.setdefault("ai_context_neighbors", 0)
    config_data.setdefault("ai_use_original_context", True)
    config_data.setdefault("ai_original_context_neighbors", 3)

    # Prompt structure
    config_data.setdefault("ai_prompt_structure", deepcopy(DEFAULT_PROMPT_STRUCTURE))
    config_data.pop("ai_prompt_template", None) # Remove old key if exists

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
    if "font_settings" not in config_data:
        config_data["font_settings"] = default_fonts
    else:
        config_data["font_settings"].setdefault("override_default_fonts", default_fonts["override_default_fonts"])
        config_data["font_settings"].setdefault("scripts", default_fonts["scripts"])
        config_data["font_settings"].setdefault("code_context", default_fonts["code_context"])
        for script, settings in default_fonts["scripts"].items():
            config_data["font_settings"]["scripts"].setdefault(script, settings)
        for key, value in default_fonts["code_context"].items():
            config_data["font_settings"]["code_context"].setdefault(key, value)

    # Window state
    config_data.setdefault("window_state", "")
    config_data.setdefault("window_geometry", "")

    if "validation_rules" not in config_data:
        config_data["validation_rules"] = deepcopy(DEFAULT_VALIDATION_RULES)
    else:
        for key, default_val in DEFAULT_VALIDATION_RULES.items():
            if key not in config_data["validation_rules"]:
                config_data["validation_rules"][key] = default_val

    config_data.setdefault("check_length", True)
    config_data.setdefault("length_threshold_major", 2.5)
    config_data.setdefault("length_threshold_minor", 2.0)

    return config_data


def save_config(app_instance):
    config = app_instance.config
    config['extraction_patterns'] = app_instance.config.get("extraction_patterns", deepcopy(DEFAULT_EXTRACTION_PATTERNS))

    if app_instance.current_project_path:
        config["last_dir"] = os.path.dirname(app_instance.current_project_path)
    elif app_instance.current_code_file_path:
        config["last_dir"] = os.path.dirname(app_instance.current_code_file_path)
    elif app_instance.current_po_file_path:
        config["last_dir"] = os.path.dirname(app_instance.current_po_file_path)

    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving config file: {e}")