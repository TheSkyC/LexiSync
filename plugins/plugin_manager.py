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
from utils.constants import APP_VERSION
from utils.localization import _


class PluginManager:
    def __init__(self, main_window):
        self.main_window = main_window
        self.plugins = []
        self.translators = {}
        self.plugin_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)))
        self.logger = logging.getLogger(__name__)
        self.incompatible_plugins = {}

        self._enabled_plugins_cache = None
        self._cache_valid = False

        self.load_plugins()

    def _is_version_compatible(self, app_version, required_prefix):
        if not required_prefix:
            return True
        app_parts = app_version.split('.')
        req_parts = required_prefix.split('.')

        if len(req_parts) > len(app_parts):
            return False

        for i in range(len(req_parts)):
            if app_parts[i] != req_parts[i]:
                return False
        return True

    def load_plugins(self):
        self.plugins = []
        self.incompatible_plugins = {}
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
                required_version = instance.compatible_app_version()
                if not self._is_version_compatible(APP_VERSION, required_version):
                    self.logger.warning(
                        f"Plugin '{instance.name()}' (ID: {instance.plugin_id()}) is not compatible with app version {APP_VERSION}. "
                        f"Requires: {required_version}. It will be disabled by default."
                    )
                    self.incompatible_plugins[instance.plugin_id()] = {
                        "name": instance.name(),
                        "required": required_version,
                        "current": APP_VERSION
                    }

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
                return {'class': obj, 'id': obj().plugin_id(), 'deps': list(obj().plugin_dependencies().keys())}
        return None

    def _sort_and_instantiate_plugins(self, plugin_specs):
        from collections import defaultdict

        id_to_spec = {spec['id']: spec for spec in plugin_specs}
        all_plugin_ids = set(id_to_spec.keys())
        for spec in plugin_specs:
            missing_deps = set(spec['deps']) - all_plugin_ids
            if missing_deps:
                raise RuntimeError(
                    _("Plugin '{plugin_id}' has missing dependencies: {deps}").format(
                        plugin_id=spec['id'],
                        deps=", ".join(missing_deps)
                    )
                )
        dep_graph = {spec['id']: set(spec['deps']) for spec in plugin_specs}
        in_degree = {uid: 0 for uid in all_plugin_ids}
        for uid, deps in dep_graph.items():
            for dep in deps:
                in_degree[uid] += 1
        in_degree = {uid: 0 for uid in all_plugin_ids}
        graph = {uid: [] for uid in all_plugin_ids}
        for uid, spec in id_to_spec.items():
            for dep in spec['deps']:
                graph[dep].append(uid)
                in_degree[uid] += 1
        queue = [uid for uid in all_plugin_ids if in_degree[uid] == 0]
        sorted_ids = []
        while queue:
            u_id = queue.pop(0)
            sorted_ids.append(u_id)
            for v_id in graph.get(u_id, []):
                in_degree[v_id] -= 1
                if in_degree[v_id] == 0:
                    queue.append(v_id)
        if len(sorted_ids) != len(plugin_specs):
            cycle_nodes = set(all_plugin_ids) - set(sorted_ids)
            raise RuntimeError(
                _("Circular dependency detected in plugins: {nodes}. Cannot load.").format(
                    nodes=", ".join(cycle_nodes)
                )
            )
        return [id_to_spec[id]['class']() for id in sorted_ids]

    def get_all_supported_file_patterns(self) -> list[str]:
        all_patterns = []
        for plugin in self.get_enabled_plugins():
            if hasattr(plugin, 'get_supported_file_patterns'):
                try:
                    patterns = plugin.get_supported_file_patterns()
                    if patterns:
                        all_patterns.extend(patterns)
                except Exception as e:
                    self.logger.error(f"Error getting file patterns from plugin '{plugin.plugin_id()}': {e}", exc_info=True)
        return list(set(all_patterns))

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
            self._enabled_plugins_cache = [p for p in self.plugins if p.plugin_id() in enabled_ids]
            self._cache_valid = True
        return self._enabled_plugins_cache

    def check_dependencies(self, plugin_id_to_check: str) -> bool:
        plugin = self.get_plugin(plugin_id_to_check)
        if not plugin: return False
        enabled_ids = self.main_window.config.get('enabled_plugins', [])
        missing_deps = [dep_id for dep_id in plugin.plugin_dependencies().keys() if dep_id not in enabled_ids]
        if missing_deps:
            dep_names = [self.get_plugin(pid).name() for pid in missing_deps if self.get_plugin(pid)]
            msg = _("Cannot enable '{plugin_name}'.\nIt requires the following disabled plugins:\n\n- {deps}").format(
                plugin_name=plugin.name(),
                deps="\n- ".join(dep_names)
            )
            QMessageBox.warning(self.main_window, _("Dependency Error"), msg)
            return False
        return True

    def run_hook(self, hook_name, *args, **kwargs):
        """
        Runs a specific hook across all enabled plugins.
        - 'process_*' hooks are chained.
        - Intercepting hooks (e.g., on_file_dropped) stop and return True if any plugin handles it.
        - Collecting hooks (e.g., on_file_tree_context_menu) gather results from all plugins.
        - Notification hooks (other on_*) are called without returning a value.
        """
        # 1. 拦截型钩子 (Intercepting Hooks)
        INTERCEPTING_HOOKS = ['on_file_dropped', 'on_files_dropped']
        if hook_name in INTERCEPTING_HOOKS:
            for plugin in self.get_enabled_plugins():
                if hasattr(plugin, hook_name):
                    try:
                        method = getattr(plugin, hook_name)
                        if method(*args, **kwargs) is True:
                            self.logger.info(f"Hook '{hook_name}' was handled by plugin '{plugin.plugin_id()}'.")
                            return True
                    except Exception as e:
                        self.logger.error(
                            f"Error in plugin '{plugin.plugin_id()}' intercepting hook '{hook_name}': {e}",
                            exc_info=True)
            return False  # 循环结束，没有任何插件处理

        # 2. 处理型钩子 (Processing Hooks)
        elif hook_name.startswith('process_'):
            processed_data = args[0]
            other_args = args[1:]
            for plugin in self.get_enabled_plugins():
                if hasattr(plugin, hook_name):
                    try:
                        method = getattr(plugin, hook_name)
                        processed_data = method(processed_data, *other_args, **kwargs)
                    except Exception as e:
                        self.logger.error(f"Error in plugin '{plugin.plugin_id()}' processing hook '{hook_name}': {e}",
                                          exc_info=True)
            return processed_data

        # TM
        if hook_name == 'query_tm_suggestions':
            for plugin in self.get_enabled_plugins():
                if hasattr(plugin, hook_name):
                    try:
                        method = getattr(plugin, hook_name)
                        result = method(*args, **kwargs)
                        if result is not None:
                            self.logger.info(f"TM query handled by plugin '{plugin.plugin_id()}'.")
                            return result
                    except Exception as e:
                        self.logger.error(f"Error in plugin '{plugin.plugin_id()}' TM query hook: {e}", exc_info=True)
            return None

        # 3. 收集型和通知型钩子 (Collecting & Notification Hooks)
        else:
            all_results = []
            for plugin in self.get_enabled_plugins():
                if hasattr(plugin, hook_name):
                    try:
                        method = getattr(plugin, hook_name)
                        result = method(*args, **kwargs)
                        if result is not None:
                            all_results.append(result)
                    except Exception as e:
                        self.logger.error(
                            f"Error in plugin '{plugin.plugin_id()}' notification/collecting hook '{hook_name}': {e}",
                            exc_info=True)
            if hook_name == 'on_file_tree_context_menu':
                flat_list = [item for sublist in all_results for item in sublist]
                return flat_list
            return None

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
        self.logger.info(f"Main app language changed. Reloading all plugins to apply new language...")
        for plugin in self.plugins:
            try:
                plugin.teardown()
            except Exception as e:
                self.logger.error(f"Error during teardown of plugin {plugin.plugin_id()}: {e}", exc_info=True)
        self.plugins.clear()
        self.translators.clear()
        self.load_plugins()

    def setup_plugin_ui(self):
        if not hasattr(self.main_window, 'plugin_menu') or self.main_window.plugin_menu is None:
            self.main_window.plugin_menu = self.main_window.menuBar().addMenu("Plugins")
        self.main_window.plugin_menu.clear()

        manage_action = self.main_window.plugin_menu.addAction(_("Manage Plugins..."))
        manage_action.triggered.connect(self.show_plugin_manager_dialog)
        if self.get_enabled_plugins():
            self.main_window.plugin_menu.addSeparator()
        for plugin in self.get_enabled_plugins():
            if hasattr(plugin, 'add_menu_items'):
                items = plugin.add_menu_items()
                if items:
                    self._create_menu_from_structure(self.main_window.plugin_menu, items)

    def _create_menu_from_structure(self, parent_menu, structure):
        for item in structure:
            if isinstance(item, str) and item == '---':
                parent_menu.addSeparator()
                continue
            if not isinstance(item, tuple) or len(item) != 2:
                continue
            name, action = item
            if isinstance(action, list):
                submenu = parent_menu.addMenu(name)
                self._create_menu_from_structure(submenu, action)
            elif callable(action):
                menu_action = parent_menu.addAction(name)
                menu_action.triggered.connect(action)

    def show_plugin_manager_dialog(self):
        dialog = PluginManagerDialog(self.main_window, self)
        dialog.exec()
        self.setup_plugin_ui()

    def is_dependency_for_others(self, plugin_id_to_check: str) -> bool:
        dependent_plugins = []
        for p in self.get_enabled_plugins():
            if plugin_id_to_check in p.dependencies():
                dependent_plugins.append(p.name())

        if dependent_plugins:
            plugin_to_disable = self.get_plugin(plugin_id_to_check)
            msg = _("Cannot disable '{plugin_name}'.\nThe following enabled plugins depend on it:\n\n- {deps}").format(
                plugin_name=plugin_to_disable.name(),
                deps="\n- ".join(dependent_plugins)
            )
            QMessageBox.warning(self.main_window, _("Dependency Error"), msg)
            return True
        return False