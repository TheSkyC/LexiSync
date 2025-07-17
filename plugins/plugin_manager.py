# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import os
import importlib.util
import inspect
import gettext
import logging
from PySide6.QtWidgets import QMessageBox
from plugins.plugin_base import PluginBase
from plugins.plugin_dialog import PluginManagerDialog
from utils.localization import _


class PluginManager:
    def __init__(self, main_window):
        self.main_window = main_window
        self.plugins = []
        self.translators = {}
        self.plugin_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)))
        self.logger = logging.getLogger(__name__)

        self._enabled_plugins_cache = None
        self._cache_valid = False

        self.load_plugins()

    def load_plugins(self):
        self.plugins = []
        self._cache_valid = False
        if not os.path.isdir(self.plugin_dir):
            self.logger.warning(f"Plugin directory not found: {self.plugin_dir}")
            return

        plugin_specs = []
        for item_name in os.listdir(self.plugin_dir):
            if os.path.isdir(os.path.join(self.plugin_dir, item_name)):
                try:
                    spec = self._get_plugin_spec(item_name)
                    if spec:
                        plugin_specs.append(spec)
                except Exception as e:
                    self.logger.error(f"Failed to load plugin spec for '{item_name}': {e}", exc_info=True)

        try:
            sorted_instances = self._sort_and_instantiate_plugins(plugin_specs)
            self.plugins = sorted_instances
            for instance in self.plugins:
                self.setup_plugin_translation(instance.plugin_id())
                instance.setup(self.main_window, self)
                self.logger.info(
                    f"Successfully loaded and initialized plugin: {instance.name()} (ID: {instance.plugin_id()})")
        except Exception as e:
            self.logger.critical(f"Failed to sort or initialize plugins: {e}", exc_info=True)
            QMessageBox.critical(self.main_window, _("Plugin Loading Error"), str(e))

    def _get_plugin_spec(self, dir_name):
        plugin_file = os.path.join(self.plugin_dir, dir_name, '__init__.py')
        if not os.path.exists(plugin_file):
            return None

        spec = importlib.util.spec_from_file_location(f"plugins.{dir_name}", plugin_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        for name, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, PluginBase) and obj is not PluginBase:
                return {'class': obj, 'id': obj().plugin_id(), 'deps': obj().dependencies()}
        return None

    def _sort_and_instantiate_plugins(self, plugin_specs):
        # 拓扑排序
        from collections import defaultdict
        dep_graph = {spec['id']: set(spec['deps']) for spec in plugin_specs}
        in_degree = defaultdict(int)
        for u, neighbors in dep_graph.items():
            for v in neighbors:
                in_degree[u] += 1

        queue = [spec['id'] for spec in plugin_specs if in_degree[spec['id']] == 0]
        sorted_ids = []

        while queue:
            u_id = queue.pop(0)
            sorted_ids.append(u_id)
            for v_id, v_deps in dep_graph.items():
                if u_id in v_deps:
                    in_degree[v_id] -= 1
                    if in_degree[v_id] == 0:
                        queue.append(v_id)

        if len(sorted_ids) != len(plugin_specs):
            raise RuntimeError(_("Circular dependency detected in plugins. Cannot load."))

        id_to_spec = {spec['id']: spec for spec in plugin_specs}
        return [id_to_spec[id]['class']() for id in sorted_ids]

    def reload_plugins(self):
        self.logger.info("Reloading all plugins...")
        for plugin in self.plugins:
            try:
                plugin.teardown()
            except Exception as e:
                self.logger.error(f"Error during teardown of plugin {plugin.plugin_id()}: {e}", exc_info=True)

        self.plugins.clear()
        self.translators.clear()
        self.load_plugins()
        self.setup_plugin_ui()
        self.logger.info("Plugins reloaded.")

    def setup_plugin_translation(self, plugin_id):
        locale_dir = os.path.join(self.plugin_dir, plugin_id, 'locales')
        current_lang = self.main_window.config.get('language', 'en_US')
        try:
            lang = gettext.translation(domain=plugin_id, localedir=locale_dir, languages=[current_lang], fallback=True)
            self.translators[plugin_id] = lang.gettext
        except FileNotFoundError:
            self.translators[plugin_id] = lambda s: s

    def get_translator_for_plugin(self, plugin_id):
        return self.translators.get(plugin_id, lambda s: s)

    def get_plugin(self, plugin_id):
        return next((p for p in self.plugins if p.plugin_id() == plugin_id), None)

    def invalidate_cache(self):
        self._cache_valid = False

    def get_enabled_plugins(self):
        if not self._cache_valid or self._enabled_plugins_cache is None:
            enabled_ids = self.main_window.config.get('enabled_plugins', [])
            # 插件已按依赖顺序排序，此处直接过滤即可
            self._enabled_plugins_cache = [p for p in self.plugins if p.plugin_id() in enabled_ids]
            self._cache_valid = True
        return self._enabled_plugins_cache

    def check_dependencies(self, plugin_id_to_check):
        plugin = self.get_plugin(plugin_id_to_check)
        if not plugin: return False

        enabled_ids = self.main_window.config.get('enabled_plugins', [])
        missing_deps = [dep for dep in plugin.dependencies() if dep not in enabled_ids]

        if missing_deps:
            msg = _("Cannot enable '{plugin_name}'.\nIt requires the following disabled plugins:\n\n- {deps}").format(
                plugin_name=plugin.name(),
                deps="\n- ".join(missing_deps)
            )
            QMessageBox.warning(self.main_window, _("Dependency Error"), msg)
            return False
        return True

    def run_hook(self, hook_name, *args, **kwargs):
        if hook_name.startswith('process_'):
            return self._run_processing_hook(hook_name, *args, **kwargs)
        else:
            return self._run_notification_hook(hook_name, *args, **kwargs)

    def _run_processing_hook(self, hook_name, *args, **kwargs):
        processed_data = args[0]
        other_args = args[1:]
        for plugin in self.get_enabled_plugins():
            if hasattr(plugin, hook_name):
                try:
                    method = getattr(plugin, hook_name)
                    processed_data = method(processed_data, *other_args, **kwargs)
                except Exception as e:
                    self.logger.error(f"Error in plugin '{plugin.plugin_id()}' hook '{hook_name}': {e}", exc_info=True)
        return processed_data

    def _run_notification_hook(self, hook_name, *args, **kwargs):
        for plugin in self.get_enabled_plugins():
            if hasattr(plugin, hook_name):
                try:
                    method = getattr(plugin, hook_name)
                    method(*args, **kwargs)
                except Exception as e:
                    self.logger.error(f"Error in plugin '{plugin.plugin_id()}' hook '{hook_name}': {e}", exc_info=True)

    def on_main_app_language_changed(self):
        for plugin in self.plugins:
            self.setup_plugin_translation(plugin.plugin_id())
        self.setup_plugin_ui()

    def setup_plugin_ui(self):
        if not hasattr(self.main_window, 'plugin_menu'):
            self.main_window.plugin_menu = self.main_window.menuBar().addMenu(_("&Plugins"))
        self.main_window.plugin_menu.clear()

        manage_action = self.main_window.plugin_menu.addAction(_("Manage Plugins..."))
        manage_action.triggered.connect(self.show_plugin_manager_dialog)
        self.main_window.plugin_menu.addSeparator()

        for plugin in self.get_enabled_plugins():
            if hasattr(plugin, 'add_menu_items'):
                items = plugin.add_menu_items()
                if items:
                    for name, callback in items:
                        action = self.main_window.plugin_menu.addAction(name)
                        action.triggered.connect(callback)

    def show_plugin_manager_dialog(self):
        dialog = PluginManagerDialog(self.main_window, self)
        dialog.exec()
        self.setup_plugin_ui()