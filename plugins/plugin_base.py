# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List, Dict
import json
import os

if TYPE_CHECKING:
    from main_window import OverwatchLocalizerApp
    from plugins.plugin_manager import PluginManager


class PluginBase(ABC):
    """
    The base class for all Overwatch Localizer plugins.
    """

    def __init__(self):
        self.main_window: 'OverwatchLocalizerApp' = None
        self.plugin_manager: 'PluginManager' = None
        self._ = lambda s: s
        self.config = {}
        self.config_path = ""

    def setup(self, main_window: 'OverwatchLocalizerApp', plugin_manager: 'PluginManager'):
        """
        Called when the plugin is loaded. Use this to initialize resources.
        The main window instance and plugin manager are provided.
        """
        self.main_window = main_window
        self.plugin_manager = plugin_manager
        self._ = self.plugin_manager.get_translator_for_plugin(self.plugin_id())
        self.config_path = os.path.join(
            plugin_manager.plugin_dir, self.plugin_id(), "config.json"
        )
        self.load_config()

    def teardown(self):
        """
        Called when the application is closing or the plugin is being unloaded.
        Use this to clean up any resources.
        """
        pass

    @abstractmethod
    def plugin_id(self) -> str:
        """
        Return a unique identifier for the plugin, e.g., 'com.author.plugin_name'.
        This should match the plugin's folder name.
        """
        pass

    @abstractmethod
    def name(self) -> str:
        """Return the display name of the plugin. This string is translatable."""
        pass

    def version(self) -> str:
        """Return the version of the plugin, e.g., '1.0.0'."""
        return "1.0.0"

    def author(self) -> str:
        """Return the author of the plugin."""
        return "Unknown"

    def description(self) -> str:
        """Return a short description of what the plugin does. This string is translatable."""
        return ""

    def url(self) -> str:
        """Return a URL for the plugin's homepage or source code."""
        return ""

    def compatible_app_version(self) -> str:
        """
        Return the compatible application version range for this plugin.
        Uses a simple prefix match. E.g., "1.1" matches "1.1.3", "1.1.4", etc.
        Return an empty string or None to indicate compatibility with all versions.
        """
        return "" # 确保有默认返回值

    def plugin_dependencies(self) -> Dict[str, str]:
        """
        Return a dictionary of plugin dependencies.
        Format: {'plugin_id': 'version_specifier', ...}
        e.g., {'com.theskyc.core': '>=1.2.0'}
        """
        return {}

    def external_dependencies(self) -> Dict[str, str]:
        """
        Return a dictionary of external Python library dependencies.
        Format: {'library_name': 'version_specifier', ...}
        e.g., {'scikit-learn': '>=1.0.0'}
        """
        return {}

    def register_ai_placeholders(self) -> list[dict]:
        """
        Return a list of AI prompt placeholders provided by this plugin.
        Each item in the list should be a dictionary with 'placeholder' and 'description' keys.
        Example: [{'placeholder': '[MyPlaceholder]', 'description': 'Inserts custom data.'}]
        The 'provider' key will be added automatically by the PluginManager.
        """
        return []

    # --- Hooks ---

    def on_ui_setup_complete(self):
        """
        Hook called after the main window's UI has been completely set up.
        Use this to add custom menu items, toolbars, etc.
        """
        pass

    def on_project_loaded(self, strings: list):
        """
        Hook called after a project or file has been loaded and strings have been extracted.
        :param strings: A list of TranslatableString objects.
        """
        pass

    def on_before_save(self, strings: list, file_path: str, file_format: str):
        """
        Hook called before a project or file is saved.
        :param strings: A list of TranslatableString objects to be saved.
        :param file_path: The path where the file will be saved.
        :param file_format: The format of the file, e.g., 'owproj', 'ow', 'po'.
        """
        pass

    def on_file_tree_context_menu(self, selected_paths: list) -> list:
        """
        Hook to add items to the file explorer's context menu.
        :param selected_paths: A list of selected file/directory paths.
        :return: A list defining menu structure, e.g., [('My Action', callback)]
        """
        return []

    def get_supported_file_patterns(self) -> List[str]:
        """
        Return a list of file patterns (e.g., ['*.mo', '*.custom']) that this
        plugin adds to the file explorer's default filter.
        """
        return []

    def on_file_dropped(self, file_path: str) -> bool:
        """
        Hook called when a file is dropped OR double-clicked in the file explorer
        and is not handled by the main application.

        :param file_path: The path of the file to handle.
        :return: True if the plugin handled the file open action, otherwise False.
        """
        return False

    def process_string_for_save(self, text: str, ts_object, column: str, source: str) -> str:
        """
        Hook to process a string right before it's saved into the data model or file.
        :param text: The string to be processed.
        :param ts_object: The full TranslatableString object for context.
        :param column: The column being processed, e.g., 'translation', 'comment'.
        :param source: A string indicating the origin of the action, e.g., 'manual_button', 'ai_translation'.
        :return: The processed string.
        """
        return text

    def process_string_for_display(self, text: str, ts_object, column: str) -> str:
        """
        Hook to process a string right before it's displayed in the main table.
        This is a chained hook.
        :param text: The string to be displayed.
        :param ts_object: The full TranslatableString object for context.
        :param column: The column being displayed, e.g., 'original', 'translation'.
        :return: The processed string for display.
        """
        return text

    def add_menu_items(self) -> list:
        """
        Return a list of menu items to be added to the Plugins menu.
        The format can be:
        - ('Menu Item Name', callback_function) for a simple action.
        - ('Submenu Name', [('Action 1', callback1), ('Action 2', callback2)]) for a submenu.
        """
        return []

    def on_tm_loaded(self, translation_memory: dict):
        """
        Hook called after the main Translation Memory has been loaded or updated.
        Plugins can use this to build/update their own indexes.
        :param translation_memory: The complete TM dictionary.
        """
        pass

    def query_tm_suggestions(self, original_text: str) -> list[tuple[float, str, str]] | None:
        """
        Hook for plugins to provide high-performance TM suggestions.
        This hook replaces the default fuzzy search logic if a plugin returns a valid list.

        :param original_text: The source text to find suggestions for.
        :return: A list of tuples: [(score, tm_original, tm_translation), ...],
                 or None if the plugin cannot handle the query.
                 Score should be a float between 0.0 and 1.0.
        """
        return None

    def get_default_config(self) -> dict:
        """
        Return a dictionary containing the default configuration for the plugin.
        This will be used if no config file is found.
        """
        return {}

    def load_config(self):
        """Loads the plugin's configuration from its config.json file."""
        defaults = self.get_default_config()
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
            defaults.update(user_config)
            self.config = defaults
        except (FileNotFoundError, json.JSONDecodeError):
            self.config = defaults

    def save_config(self):
        """Saves the plugin's current configuration to its config.json file."""
        if not self.config_path:
            return
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving config for plugin {self.plugin_id()}: {e}")

    def show_settings_dialog(self, parent_widget) -> bool:
        """
        If the plugin has a settings dialog, this method should create and show it.
        The method should return True if settings were changed, False otherwise.
        If the plugin has no settings, this method should not be implemented.

        :param parent_widget: The parent widget for the dialog (usually the main window).
        :return: True if settings were changed, False otherwise.
        """
        return False