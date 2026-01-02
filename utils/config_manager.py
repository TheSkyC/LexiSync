# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import uuid
import json
import os
from copy import deepcopy
from utils.constants import (
    CONFIG_FILE, DEFAULT_API_URL, DEFAULT_PROMPT_STRUCTURE, DEFAULT_CORRECTION_PROMPT_STRUCTURE, DEFAULT_KEYBINDINGS,
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
    legacy_key = config_data.get("ai_api_key", "")
    if legacy_key and not config_data["ai_models"]:
        new_id = str(uuid.uuid4())
        legacy_model = {
            "id": new_id,
            "name": "Default (Legacy)",
            "provider": "Custom",
            "api_base_url": config_data.get("ai_api_base_url", DEFAULT_API_URL),
            "api_key": legacy_key,
            "model_name": config_data.get("ai_model_name", "deepseek-chat"),
            "concurrency": config_data.get("ai_max_concurrent_requests", 1),
            "timeout": 60
        }
        config_data["ai_models"].append(legacy_model)
        config_data["active_ai_model_id"] = new_id

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


    config_data.setdefault("ai_use_translation_context", False)
    config_data.setdefault("ai_context_neighbors", 0)
    config_data.setdefault("ai_use_original_context", True)
    config_data.setdefault("ai_original_context_neighbors", 3)

    # Prompt structure
    # 1. 确保 ai_prompts 列表存在
    if "ai_prompts" not in config_data:
        config_data["ai_prompts"] = []

    # 2. 迁移旧数据 (如果有)
    if "ai_prompt_structure" in config_data:
        has_default_trans = any(p["id"] == "default_translation" for p in config_data["ai_prompts"])
        if not has_default_trans:
            config_data["ai_prompts"].append({
                "id": "default_translation",
                "name": "Default Translation",
                "type": "translation", # 类型：translation 或 correction
                "structure": config_data["ai_prompt_structure"]
            })
        # 移除旧键，保持整洁 (可选，为了兼容性也可以保留)
        config_data.pop("ai_prompt_structure", None)

    # 3. 确保有默认的纠错预设
    has_default_fix = any(p["id"] == "default_correction" for p in config_data["ai_prompts"])
    if not has_default_fix:
        config_data["ai_prompts"].append({
            "id": "default_correction",
            "name": "Default Correction",
            "type": "correction",
            "structure": deepcopy(DEFAULT_CORRECTION_PROMPT_STRUCTURE)
        })

    # 4. 设置当前激活的预设 ID
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