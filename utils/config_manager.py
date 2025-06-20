# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import json
import os
from copy import deepcopy
from utils.constants import (
    CONFIG_FILE, DEFAULT_API_URL, DEFAULT_PROMPT_STRUCTURE, DEFAULT_KEYBINDINGS,
    DEFAULT_EXTRACTION_PATTERNS
)

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

    config_data.setdefault("deduplicate", False)
    config_data.setdefault("show_ignored", True)
    config_data.setdefault("show_untranslated", False)
    config_data.setdefault("show_translated", False)
    config_data.setdefault("show_unreviewed", False)
    config_data.setdefault("auto_save_tm", False)
    config_data.setdefault("auto_backup_tm_on_save", True)
    config_data.setdefault("last_dir", "")
    config_data.setdefault("recent_files", [])

    config_data.setdefault("ai_api_key", "")
    config_data.setdefault("ai_api_base_url", DEFAULT_API_URL)
    config_data.setdefault("ai_target_language", "中文")
    config_data.setdefault("ai_model_name", "deepseek-chat")
    config_data.setdefault("ai_api_interval", 200)
    config_data.setdefault("ai_max_concurrent_requests", 1)
    config_data.setdefault("ai_use_translation_context", False)
    config_data.setdefault("ai_context_neighbors", 0)
    config_data.setdefault("ai_use_original_context", True)
    config_data.setdefault("ai_original_context_neighbors", 3)

    config_data.setdefault("ai_prompt_structure", deepcopy(DEFAULT_PROMPT_STRUCTURE))
    config_data.pop("ai_prompt_template", None)

    config_data.setdefault("extraction_patterns", deepcopy(DEFAULT_EXTRACTION_PATTERNS))

    if 'keybindings' not in config_data:
        config_data['keybindings'] = DEFAULT_KEYBINDINGS.copy()
    else:
        for key, value in DEFAULT_KEYBINDINGS.items():
            config_data['keybindings'].setdefault(key, value)

    default_fonts = get_default_font_settings()
    if "font_settings" not in config_data:
        config_data["font_settings"] = default_fonts
    else:
        config_data["font_settings"].setdefault("override_default_fonts", default_fonts["override_default_fonts"])
        config_data["font_settings"].setdefault("scripts", default_fonts["scripts"])
        config_data["font_settings"].setdefault("code_context", default_fonts["code_context"])
        for script, settings in default_fonts["scripts"].items():
            config_data["font_settings"]["scripts"].setdefault(script, settings)
    return config_data


def save_config(app_instance):
    config = app_instance.config
    config["deduplicate"] = app_instance.deduplicate_strings_var.get()
    config["show_ignored"] = app_instance.show_ignored_var.get()
    config["show_untranslated"] = app_instance.show_untranslated_var.get()
    config["show_translated"] = app_instance.show_translated_var.get()
    config["show_unreviewed"] = app_instance.show_unreviewed_var.get()
    config["auto_save_tm"] = app_instance.auto_save_tm_var.get()
    config["auto_backup_tm_on_save"] = app_instance.auto_backup_tm_on_save_var.get()
    config['extraction_patterns'] = app_instance.config.get("extraction_patterns", deepcopy(DEFAULT_EXTRACTION_PATTERNS))

    if 'keybindings' in app_instance.config:
        config['keybindings'] = app_instance.config['keybindings']

    if app_instance.current_project_file_path:
        config["last_dir"] = os.path.dirname(app_instance.current_project_file_path)
    elif app_instance.current_code_file_path:
        config["last_dir"] = os.path.dirname(app_instance.current_code_file_path)

    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving config file: {e}")