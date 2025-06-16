import json
import os
from . import constants


class ConfigManager:
    def __init__(self, config_file=constants.CONFIG_FILE):
        self.config_file = config_file
        self.config = self.load_config()

    def load_config(self):
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            config_data = {}

        # General settings
        config_data.setdefault("language", "zh_cn")
        config_data.setdefault("last_dir", "")
        config_data.setdefault("recent_files", [])
        config_data.setdefault("auto_backup_tm_on_save", True)
        config_data.setdefault("hotkeys", constants.DEFAULT_HOTKEYS)

        # AI settings
        config_data.setdefault("ai_api_key", "")
        config_data.setdefault("ai_api_base_url", constants.DEFAULT_API_URL)
        config_data.setdefault("ai_target_language", "中文")
        config_data.setdefault("ai_model_name", "deepseek-chat")
        config_data.setdefault("ai_api_interval", 200)
        config_data.setdefault("ai_max_concurrent_requests", 1)
        config_data.setdefault("ai_use_translation_context", True)
        config_data.setdefault("ai_context_neighbors", 3)
        config_data.setdefault("ai_use_original_context", True)
        config_data.setdefault("ai_original_context_neighbors", 3)

        current_prompt = config_data.get("ai_prompt_template")
        if not current_prompt or "[Termbase Mappings]" not in current_prompt:
            config_data["ai_prompt_template"] = constants.DEFAULT_AI_PROMPT_TEMPLATE

        return config_data

    def save_config(self):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving config file: {e}")

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self.save_config()

    def add_to_recent_files(self, filepath):
        if not filepath: return
        recent_files = self.get("recent_files", [])
        if filepath in recent_files:
            recent_files.remove(filepath)
        recent_files.insert(0, filepath)
        self.set("recent_files", recent_files[:10])