# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import os
import importlib.util
import inspect
import gettext
from PySide6.QtWidgets import QMessageBox
from plugins.plugin_base import PluginBase
from plugins.plugin_dialog import PluginManagerDialog
from dialogs.marketplace_dialog import PluginMarketplaceDialog
from utils.constants import APP_VERSION
from utils.path_utils import get_app_data_path
from utils.plugin_context import plugin_libs_context
from utils.localization import _
from services.dependency_service import DependencyManager
import shutil
import zipfile
import tempfile
import logging
logger = logging.getLogger(__package__)


class PluginManager:
    def __init__(self, main_window):
        self.main_window = main_window
        self.plugins = []
        self.invalid_plugins = {}
        self.incompatible_plugins = {}
        self.missing_deps_plugins = {}
        self.translators = {}
        self.market_url = "https://raw.githubusercontent.com/TheSkyC/lexisync/refs/heads/master/market.json"
        self.plugin_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)))

        self._enabled_plugins_cache = None
        self._cache_valid = False

        self.load_plugins()

    def get_market_url(self) -> str:
        return self.market_url

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
        self.invalid_plugins = {}
        self.incompatible_plugins = {}
        self.missing_deps_plugins = {}
        self._cache_valid = False
        if not os.path.isdir(self.plugin_dir):
            logger.warning(f"Plugin directory not found: {self.plugin_dir}")
            return

        all_specs = {}
        for item_name in os.listdir(self.plugin_dir):
            if os.path.isdir(os.path.join(self.plugin_dir, item_name)):
                try:
                    spec = self._get_plugin_spec(item_name)
                    if spec:
                        all_specs[spec['id']] = spec
                except Exception as e:
                    logger.error(f"Failed to load plugin spec for '{item_name}': {e}", exc_info=True)
                    self.invalid_plugins[item_name] = {'spec': None, 'reason': str(e)}

        valid_specs = {}
        all_plugin_ids = set(all_specs.keys())
        for plugin_id, spec in all_specs.items():
            missing_deps = set(spec['deps']) - all_plugin_ids
            if missing_deps:
                reason = _("Missing dependencies: {deps}").format(deps=", ".join(missing_deps))
                try:
                    temp_instance = spec['class']()
                    self.setup_plugin_translation(plugin_id)
                    temp_instance._ = self.get_translator_for_plugin(plugin_id)

                    spec['metadata'] = {
                        'name': temp_instance.name(),
                        'version': temp_instance.version(),
                        'author': temp_instance.author(),
                        'description': temp_instance.description()
                    }
                except Exception:
                    spec['metadata'] = {'name': plugin_id}
                self.invalid_plugins[plugin_id] = {'spec': spec, 'reason': reason}
                logger.warning(f"Plugin '{plugin_id}' is invalid. {reason}")
            else:
                valid_specs[plugin_id] = spec

        try:
            sorted_instances = self._sort_and_instantiate_plugins(list(valid_specs.values()))
            self.plugins = sorted_instances

            for instance in self.plugins:
                plugin_id = instance.plugin_id()

                plugin_data_dir = os.path.join(get_app_data_path(), "plugins_data", plugin_id)
                os.makedirs(plugin_data_dir, exist_ok=True)
                config_path = os.path.join(plugin_data_dir, "config.json")
                instance.config_path = config_path

                self.setup_plugin_translation(plugin_id)
                instance.setup(self.main_window, self)

                # 检查版本兼容性
                required_version = instance.compatible_app_version()
                if not self._is_version_compatible(APP_VERSION, required_version):
                    reason = _("Incompatible with app version (requires {req}, current is {curr})").format(
                        req=required_version, curr=APP_VERSION)
                    self.incompatible_plugins[plugin_id] = {
                        'spec': {'class': instance.__class__},
                        'reason': reason,
                        'required': required_version,
                        'current': APP_VERSION
                    }
                    logger.warning(f"Plugin '{plugin_id}' is incompatible. {reason}")

                # 检查外部库依赖
                failed_deps = []
                ext_deps = instance.external_dependencies()
                if ext_deps:
                    for lib_name, spec in ext_deps.items():
                        res = DependencyManager.get_instance().check_external_dependency(lib_name, spec)
                        if res['status'] != 'ok':
                            failed_deps.append(res)

                if failed_deps:
                    self.missing_deps_plugins[instance.plugin_id()] = {
                        'failed_deps': failed_deps
                    }
                    reason_text = ", ".join([f"{d['name']} ({d['status']})" for d in failed_deps])
                    logger.warning(
                        f"Plugin '{instance.plugin_id()}' has missing/outdated external dependencies: {reason_text}")
                logger.info(f"Successfully loaded plugin: {instance.name()} (ID: {instance.plugin_id()})")

        except RuntimeError as e:
            logger.critical(f"Failed to sort plugins due to circular dependency: {e}", exc_info=True)
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
            logger.debug(f"Found potential plugin class '{obj.__name__}' in '{dir_name}'.")
        return None

    def _sort_and_instantiate_plugins(self, plugin_specs):
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
        logger.debug(f"Plugin dependency graph resolved. Load order: {sorted_ids}")
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
                    logger.error(f"Error getting file patterns from plugin '{plugin.plugin_id()}': {e}", exc_info=True)
        return list(set(all_patterns))

    def reload_plugins(self):
        logger.info("Reloading all plugins...")
        for plugin in self.plugins:
            try:
                plugin.teardown()
            except Exception as e:
                logger.error(f"Error during teardown of plugin {plugin.plugin_id()}: {e}", exc_info=True)

        self.plugins.clear()
        self.translators.clear()
        self.load_plugins()
        self.setup_plugin_ui()
        logger.info("Plugins reloaded.")

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
        with plugin_libs_context():
            # 1. 拦截型钩子 (Intercepting Hooks)
            INTERCEPTING_HOOKS = ['on_file_dropped', 'on_files_dropped']
            if hook_name in INTERCEPTING_HOOKS:
                for plugin in self.get_enabled_plugins():
                    if hasattr(plugin, hook_name):
                        try:
                            method = getattr(plugin, hook_name)
                            if method(*args, **kwargs) is True:
                                logger.info(f"Hook '{hook_name}' was handled by plugin '{plugin.plugin_id()}'.")
                                return True
                        except Exception as e:
                            logger.error(
                                f"Error in plugin '{plugin.plugin_id()}' intercepting hook '{hook_name}': {e}",
                                exc_info=True)
                return False  # 循环结束，没有任何插件处理

            # 2. 处理型钩子 (Processing Hooks)
            elif hook_name.startswith('process_'):
                processed_data = args[0]
                original_type = type(processed_data)
                other_args = args[1:]
                for plugin in self.get_enabled_plugins():
                    if hasattr(plugin, hook_name):
                        try:
                            method = getattr(plugin, hook_name)
                            result = method(processed_data, *other_args, **kwargs)
                            if isinstance(result, original_type):
                                processed_data = result
                            else:
                                logger.warning(
                                    f"Plugin '{plugin.plugin_id()}' hook '{hook_name}' returned wrong type "
                                    f"(expected {original_type.__name__}, got {type(result).__name__}). "
                                    f"Ignoring result."
                                )
                        except Exception as e:
                            logger.error(f"Error in plugin '{plugin.plugin_id()}' processing hook '{hook_name}': {e}",
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
                                logger.debug(f"TM query handled by plugin '{plugin.plugin_id()}'.")
                                return result
                        except Exception as e:
                            logger.error(f"Error in plugin '{plugin.plugin_id()}' TM query hook: {e}", exc_info=True)
                return None



            # 3. 收集型和通知型钩子 (Collecting & Notification Hooks)
            else:
                all_results = []
                for plugin in self.get_enabled_plugins():
                    if hasattr(plugin, hook_name):
                        try:
                            method = getattr(plugin, hook_name)
                            result = method(*args, **kwargs)
                            if hook_name == 'register_ai_placeholders' and isinstance(result, list):
                                for item in result:
                                    item['provider'] = plugin.name()
                                all_results.extend(result)
                            elif result is not None:
                                all_results.append(result)
                        except Exception as e:
                            logger.error(
                                f"Error in plugin '{plugin.plugin_id()}' notification/collecting hook '{hook_name}': {e}",
                                exc_info=True)
                if hook_name == 'retrieve_context':
                    flat_list = []
                    for res in all_results:
                        if isinstance(res, list):
                            flat_list.extend(res)
                    return flat_list
                if hook_name in ['on_file_tree_context_menu', 'on_table_context_menu', 'register_resource_viewers']:
                    flat_list = [item for sublist in all_results for item in sublist]
                    return flat_list
                if hook_name in ['add_statusbar_widgets', 'register_settings_pages', 'register_ai_placeholders', 'register_dock_widgets']:
                    return all_results
                if hook_name in ['register_importers', 'register_exporters', 'register_ai_providers']:
                    merged_dict = {}
                    for res_dict in all_results:
                        if isinstance(res_dict, dict):
                            merged_dict.update(res_dict)
                    return merged_dict
                if hook_name == 'get_ai_translation_context':
                    merged_context = {}
                    for res_dict in all_results:
                        if isinstance(res_dict, dict):
                            merged_context.update(res_dict)
                    return merged_context
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
                    logger.error(f"Error in plugin '{plugin.plugin_id()}' hook '{hook_name}': {e}", exc_info=True)
        return processed_data

    def _run_notification_hook(self, hook_name, *args, **kwargs):
        for plugin in self.get_enabled_plugins():
            if hasattr(plugin, hook_name):
                try:
                    method = getattr(plugin, hook_name)
                    method(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Error in plugin '{plugin.plugin_id()}' hook '{hook_name}': {e}", exc_info=True)

    def on_main_app_language_changed(self):
        logger.info(f"Main app language changed. Reloading all plugins to apply new language...")
        for plugin in self.plugins:
            try:
                plugin.teardown()
            except Exception as e:
                logger.error(f"Error during teardown of plugin {plugin.plugin_id()}: {e}", exc_info=True)
        self.plugins.clear()
        self.translators.clear()
        self.load_plugins()

    def install_plugin_from_zip(self, zip_filepath: str) -> tuple[str | None, str]:
        """
        Installs a plugin from a .zip file. Handles different archive structures.

        :param zip_filepath: Path to the .zip file.
        :return: A tuple (installed_plugin_id, message).
                 On success, plugin_id is the new plugin's ID and message is empty.
                 On failure, plugin_id is None and message contains the error.
        """
        if not zipfile.is_zipfile(zip_filepath):
            return None, _("The selected file is not a valid .zip archive.")

        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                with zipfile.ZipFile(zip_filepath, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
            except Exception as e:
                return None, _("Failed to extract the archive: {error}").format(error=str(e))
            content_list = os.listdir(temp_dir)
            if not content_list:
                return None, _("The archive is empty.")
            source_path = ""
            plugin_id_from_zip = ""
            if len(content_list) == 1 and os.path.isdir(os.path.join(temp_dir, content_list[0])):
                plugin_id_from_zip = content_list[0]
                source_path = os.path.join(temp_dir, plugin_id_from_zip)
                if not os.path.exists(os.path.join(source_path, '__init__.py')):
                    return None, _(
                        "The archive seems to contain a single folder, but it's not a valid plugin (missing __init__.py).")
            elif '__init__.py' in content_list:
                plugin_id_from_zip = os.path.splitext(os.path.basename(zip_filepath))[0]
                source_path = temp_dir
            else:
                return None, _(
                    "Invalid plugin archive structure. The archive must contain either a single plugin folder or the plugin's files (__init__.py, etc.) directly.")
            destination_path = os.path.join(self.plugin_dir, plugin_id_from_zip)
            if os.path.exists(destination_path):
                reply = QMessageBox.question(
                    self.main_window,
                    _("Plugin Exists"),
                    _("A plugin with the ID '{plugin_id}' already exists. Do you want to overwrite it?").format(
                        plugin_id=plugin_id_from_zip),
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if reply == QMessageBox.No:
                    return None, _("Installation cancelled by user.")
                try:
                    shutil.rmtree(destination_path)
                except Exception as e:
                    return None, _("Failed to remove the existing plugin directory: {error}").format(error=str(e))
            try:
                shutil.move(source_path, destination_path)
                logger.info(f"Plugin '{plugin_id_from_zip}' installed successfully to '{destination_path}'.")
                return plugin_id_from_zip, ""
            except Exception as e:
                return None, _("Failed to move plugin files to the destination: {error}").format(error=str(e))

    def delete_plugin(self, plugin_id: str) -> tuple[bool, str]:
        if self.is_dependency_for_others(plugin_id):
            return False, _("Cannot delete a plugin that is a dependency for other enabled plugins.")
        plugin_dir_to_delete = os.path.join(self.plugin_dir, plugin_id)
        if not os.path.isdir(plugin_dir_to_delete):
            return False, _("Plugin directory not found.")
        try:
            shutil.rmtree(plugin_dir_to_delete)
            logger.info(f"Plugin '{plugin_id}' directory deleted.")
            self.plugins = [p for p in self.plugins if p.plugin_id() != plugin_id]
            self.invalid_plugins.pop(plugin_id, None)
            self.incompatible_plugins.pop(plugin_id, None)
            self.missing_deps_plugins.pop(plugin_id, None)
            self.invalidate_cache()
            enabled_plugins = self.main_window.config.get('enabled_plugins', [])
            if plugin_id in enabled_plugins:
                enabled_plugins.remove(plugin_id)
                self.main_window.config['enabled_plugins'] = enabled_plugins
                self.main_window.save_config()
            return True, ""
        except Exception as e:
            logger.error(f"Failed to delete plugin '{plugin_id}': {e}", exc_info=True)
            return False, str(e)

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

    def show_marketplace_dialog(self):
        dialog = PluginMarketplaceDialog(self.main_window)
        dialog.exec()

    def is_dependency_for_others(self, plugin_id_to_check: str) -> bool:
        dependent_plugins = []
        for p in self.get_enabled_plugins():
            if plugin_id_to_check in p.plugin_dependencies():
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