# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List, Dict
from models.translatable_string import TranslatableString
import json
import os
import logging
logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from main_window import LexiSyncApp
    from plugins.plugin_manager import PluginManager
    from PySide6.QtGui import QPainter
    from PySide6.QtWidgets import QStyleOptionViewItem, QHBoxLayout
    from PySide6.QtCore import QModelIndex


class PluginBase(ABC):
    """
    The base class for all LexiSync plugins.
    """
    def __init__(self):
        self.main_window: 'LexiSyncApp' = None
        self.plugin_manager: 'PluginManager' = None
        self._ = lambda s: s
        self.config = {}
        self.config_path = ""

    def setup(self, main_window: 'LexiSyncApp', plugin_manager: 'PluginManager'):
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

    def load_on_prewarm(self) -> bool:
        """
        Return True if this plugin is safe to be loaded during the application's
        pre-warming phase (when the main window is created but still hidden).

        Plugins that perform complex UI operations or depend on the window being
        visible in their setup() method should return False.

        Defaults to True for backward compatibility.
        """
        return True

    def on_app_ready(self):
        """
        Called after the main window is initialized and shown.
        Ideal for post-startup tasks like update checks.
        """
        pass

    def on_app_shutdown(self):
        """
        Called just before the main application window closes.
        Ideal for saving plugin state.
        """
        pass

    def add_menu_items(self) -> list:
        """
        Return a list of menu items to be added to the Plugins menu.
        The format can be:
        - ('Menu Item Name', callback_function) for a simple action.
        - ('Submenu Name', [('Action 1', callback1), ('Action 2', callback2)]) for a submenu.
        """
        return []

    def on_main_toolbar_setup(self, toolbar_layout: 'QHBoxLayout') -> None:
        """
        (Notification Hook) Called when the main toolbar (filter bar) is being set up.
        Plugins can add their own widgets (buttons, labels, etc.) to the toolbar layout.

        :param toolbar_layout: The QHBoxLayout of the main toolbar.
        """
        pass

    def add_statusbar_widgets(self) -> list:
        """
        (Collecting Hook) Called when the status bar is being set up.
        Plugins can return a list of QWidgets to be permanently added to the status bar.

        :return: A list of QWidget instances to add to the status bar.
        """
        return []

    def on_table_context_menu(self, selected_ts_objects: list['TranslatableString']) -> list:
        """
        (Collecting Hook) Called when the context menu for the main strings table is about to be shown.
        Plugins can return a list of menu items to be added to the menu.

        :param selected_ts_objects: A list of the currently selected TranslatableString objects.
        :return: A list defining menu structure, e.g., [('My Action', callback), '---', ('Submenu', [...])]
        """
        return []

    def on_file_tree_context_menu(self, selected_paths: list) -> list:
        """
        (Collecting Hook) Called when the context menu for the file explorer is about to be shown.
        Plugins can return a list of menu items to be added to the menu.

        :param selected_paths: A list of selected file/directory paths.
        :return: A list defining menu structure.
        """
        return []

    def on_selection_changed(self, selected_ts_objects: list['TranslatableString']):
        """
        (Notification Hook) Called when the selection in the main strings table changes.

        :param selected_ts_objects: A list of the currently selected TranslatableString objects.
                                    The list will be empty if the selection is cleared.
        """
        pass

    def register_settings_pages(self) -> dict:
        """
        (Collecting Hook) Called by the main settings dialog to gather custom settings pages from plugins.
        Each page should be a QWidget subclass and should implement a `save_settings()` method.

        :return: A dictionary where keys are the page titles (str) and values are the QWidget classes
                 (not instances) for the settings pages. e.g., {'My Plugin Settings': MySettingsPage}
        """
        return {}

    def show_settings_dialog(self, parent_widget) -> bool:
        """
        If the plugin has a settings dialog, this method should create and show it.
        The method should return True if settings were changed, False otherwise.
        If the plugin has no settings, this method should not be implemented.

        :param parent_widget: The parent widget for the dialog (usually the main window).
        :return: True if settings were changed, False otherwise.
        """
        return False

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

    def on_after_project_save(self, filepath: str, file_format: str):
        """
        (Notification Hook) Called after a project or file has been successfully saved to disk.

        :param filepath: The absolute path of the saved file.
        :param file_format: A string indicating the format, e.g., 'owproj', 'po', 'ow'.
        """
        pass

    def process_raw_content_before_extraction(self, raw_content: str, filepath: str) -> str:
        """
        (Processing Hook) Called after loading a file but before extracting strings.
        Allows for preprocessing of the raw file content.
        Note: The order of arguments is (data_to_process, *other_args).
        :param raw_content: The raw string content of the file.
        :param filepath: The absolute path of the file being processed.
        :return: The processed (or original) string content.
        """
        return raw_content

    def process_extraction_patterns(self, patterns: list, filepath: str, raw_content: str) -> list:
        """
        (Processing Hook) Called before extracting strings from a code file.
        Allows plugins to dynamically modify the list of extraction patterns.

        :param patterns: The current list of extraction pattern dictionaries from the config.
        :param filepath: The path of the file being processed.
        :param raw_content: The raw string content of the file.
        :return: The modified (or original) list of extraction patterns.
        """
        return patterns

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

    def on_string_saved(self, ts_object: 'TranslatableString', column: str, new_value: str, old_value: str):
        """
        (Notification Hook) Called after a string's property (e.g., translation, comment)
        has been successfully updated in the data model.

        :param ts_object: The TranslatableString object that was modified.
        :param column: The name of the property that was changed (e.g., 'translation', 'comment').
        :param new_value: The new value of the property.
        :param old_value: The value of the property before the change.
        """
        pass

    def on_before_undo_redo(self, action_type: str, is_undo: bool, action_data: dict) -> bool:
        """
        (Intercepting Hook) Called before an undo or redo action is performed.
        A plugin can return True to prevent the default undo/redo logic from executing.

        :param action_type: The type of action being undone/redone (e.g., 'single_change', 'bulk_change').
        :param is_undo: True if it's an undo action, False if it's a redo action.
        :param action_data: The dictionary containing the data for the action.
        :return: True to block the default operation, False to allow it.
        """
        return False

    def register_ai_placeholders(self) -> list[dict]:
        """
        Return a list of AI prompt placeholders provided by this plugin.
        Each item in the list should be a dictionary with 'placeholder' and 'description' keys.
        Example: [{'placeholder': '[MyPlaceholder]', 'description': 'Inserts custom data.'}]
        The 'provider' key will be added automatically by the PluginManager.
        """
        return []

    def on_ui_setup_complete(self):
        """
        Hook called after the main window's UI has been completely set up.
        Use this to add custom menu items, toolbars, etc.
        """
        pass

    def process_ai_translate_list(self, ts_objects_to_translate: list['TranslatableString']) -> list['TranslatableString']:
        """
        (Processing Hook) Called before sending a list of strings to the AI for translation.
        Allows plugins to filter or modify the list of TranslatableString objects.

        :param ts_objects_to_translate: The list of TranslatableString objects about to be translated.
        :return: The modified (or original) list of objects to be sent to the AI.
        """
        return ts_objects_to_translate

    def process_ai_translated_text(self, translated_text: str, ts_object: 'TranslatableString') -> str:
        """
        (Processing Hook) Called after receiving a translation from the AI, but before applying it.
        Allows plugins to perform post-processing on the translated text.

        :param translated_text: The raw text returned by the AI. This is the value that is chained between plugins.
        :param ts_object: The original TranslatableString object that was translated (for context).
        :return: The post-processed translated text to be applied to the data model.
        """
        return translated_text

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

    def register_importers(self) -> dict:
        """
        (Collecting Hook) Registers custom file importers to be added to the 'File > Import' menu.

        :return: A dictionary where keys are the menu item text (including file filter,
                 e.g., "Custom Format (*.myformat)") and values are the callback functions
                 to be executed when the menu item is clicked. The callback will receive no arguments.
        """
        return {}

    def register_exporters(self) -> dict:
        """
        (Collecting Hook) Registers custom file exporters to be added to the 'File > Export' menu.

        :return: A dictionary where keys are the menu item text (e.g., "Export as Custom Format")
                 and values are the callback functions. The callback will receive no arguments.
        """
        return {}

    def register_validation_rules(self) -> list:
        """
        (Collecting Hook) Called by the ValidationService to gather custom validation rules.
        :return: A list of callable functions. Each function should accept a
                 TranslatableString object and return a ValidationWarning object or None.
        """
        return []

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
            logger.error(f"Error saving config for plugin {self.plugin_id()}: {e}")

