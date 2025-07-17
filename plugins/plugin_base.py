# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List
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

    def dependencies(self) -> List[str]:
        """
        Return a list of plugin_id strings that this plugin depends on.
        The plugin manager will ensure these dependencies are loaded first.
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

    def process_string_for_save(self, text: str, ts_object, column: str) -> str:
        """
        Hook to process a string right before it's saved into the data model or file.
        This is a chained hook; the output of one plugin becomes the input for the next.
        :param text: The string to be processed.
        :param ts_object: The full TranslatableString object for context.
        :param column: The column being processed, e.g., 'translation', 'comment'.
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