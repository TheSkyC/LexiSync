# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from plugins.plugin_base import PluginBase
from PySide6.QtWidgets import QInputDialog, QMessageBox
import json
import os

GLOBAL_SETTINGS_KEY = "__GLOBAL__"

class PersonalizedTranslationPlugin(PluginBase):
    def __init__(self):
        super().__init__()
        self.settings_cache = {}
        self.settings_file_path = ""

    def plugin_id(self) -> str:
        return "com_theskyc_custom_instructions"

    def name(self) -> str:
        return self._("Custom Instructions")

    def description(self) -> str:
        return self._("Allows setting global and project-specific instructions for AI translation.")

    def author(self) -> str:
        return "TheSkyC"

    def version(self) -> str:
        return "1.0.0"

    def url(self) -> str:
        return "https://github.com/TheSkyC/overwatch-localizer/tree/master/plugins/com_theskyc_personalized_translation"

    def compatible_app_version(self) -> str:
        return "1.1"

    def has_settings_dialog(self) -> bool:
        return False

    def register_ai_placeholders(self) -> list[dict]:
        return [
            {
                'placeholder': '[Global Instructions]',
                'description': self._('Global instructions that apply to all projects.')
            },
            {
                'placeholder': '[Project Instructions]',
                'description': self._('Instructions specific to the current project.')
            }
        ]

    def setup(self, main_window, plugin_manager):
        super().setup(main_window, plugin_manager)
        self.settings_file_path = os.path.join(
            self.plugin_manager.plugin_dir, self.plugin_id(), "config.json"
        )
        self._load_settings()

    def _load_settings(self):
        try:
            with open(self.settings_file_path, 'r', encoding='utf-8') as f:
                self.settings_cache = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.settings_cache = {}

    def _save_settings(self):
        try:
            with open(self.settings_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.settings_cache, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving personalized settings: {e}")

    def get_current_project_key(self):
        if self.main_window.current_project_file_path:
            return self.main_window.current_project_file_path
        if self.main_window.current_po_file_path:
            return self.main_window.current_po_file_path
        if self.main_window.current_code_file_path:
            return self.main_window.current_code_file_path
        return None

    def add_menu_items(self) -> list:
        return [
            (self.name(), [
                (self._("Project-specific Instructions..."), self.show_project_settings_dialog),
                (self._("Global Instructions..."), self.show_global_settings_dialog)
            ])
        ]

    def show_project_settings_dialog(self):
        project_key = self.get_current_project_key()
        if not project_key:
            QMessageBox.warning(self.main_window, self._("No Project"), self._("Please open a file first."))
            return

        current_instructions = self.settings_cache.get(project_key, "")
        new_instructions, ok = QInputDialog.getMultiLineText(
            self.main_window,
            self._("Project-specific Instructions"),
            self._(
                "Enter instructions for this project. These will override global instructions.\n(e.g., 'Translate \"Hero\" as \"Agent\"', 'Use a formal tone')."),
            current_instructions
        )

        if ok and new_instructions != current_instructions:
            self.settings_cache[project_key] = new_instructions
            self._save_settings()
            self.main_window.update_statusbar(self._("Project-specific instructions updated."))

    def show_global_settings_dialog(self):
        current_instructions = self.settings_cache.get(GLOBAL_SETTINGS_KEY, "")

        new_instructions, ok = QInputDialog.getMultiLineText(
            self.main_window,
            self._("Global Instructions"),
            self._(
                "Enter global instructions that will apply to all projects unless overridden by project-specific settings.\n(e.g., 'Always use simplified Chinese characters', 'Maintain a neutral tone')."),
            current_instructions
        )

        if ok and new_instructions != current_instructions:
            self.settings_cache[GLOBAL_SETTINGS_KEY] = new_instructions
            self._save_settings()
            self.main_window.update_statusbar(self._("Global instructions updated."))

    def get_ai_translation_context(self) -> dict:
        global_instructions = self.settings_cache.get(GLOBAL_SETTINGS_KEY, "")
        project_instructions = ""
        project_key = self.get_current_project_key()
        if project_key:
            project_instructions = self.settings_cache.get(project_key, "")
        return {
            '[Global Instructions]': global_instructions,
            '[Project Instructions]': project_instructions
        }