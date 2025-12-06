# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QListWidgetItem, QHBoxLayout, QLabel, QTextBrowser, QPushButton, QSplitter, QWidget, QMessageBox, QMenu, QFileDialog
from PySide6.QtCore import Qt, QUrl, Signal, QThread, QRectF
from PySide6.QtGui import QColor, QFont, QIcon, QPixmap, QPainter, QDesktopServices, QAction
from utils.localization import _
from services.dependency_service import DependencyManager
from plugins.plugin_base import PluginBase
import os
import shutil

def create_icon(color1, color2=None):
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)

    if color2:
        # 绘制双色半圆
        rect = QRectF(0, 0, 16, 16)
        # 左半圆
        painter.setBrush(QColor(color1))
        painter.drawPie(rect, 90 * 16, 180 * 16)
        # 右半圆
        painter.setBrush(QColor(color2))
        painter.drawPie(rect, -90 * 16, 180 * 16)
    else:
        painter.setBrush(QColor(color1))
        painter.drawEllipse(0, 0, 16, 16)

    painter.end()
    return QIcon(pixmap)

class InstallThread(QThread):
    progress = Signal(str)
    finished = Signal(bool)

    def __init__(self, dependencies_dict):
        super().__init__()
        self.dependencies = dependencies_dict

    def run(self):
        success = DependencyManager.get_instance().install_dependencies(self.dependencies, self.progress.emit)
        self.finished.emit(success)

class UninstallThread(QThread):
    progress = Signal(str)
    finished = Signal(bool)

    def __init__(self, package_name):
        super().__init__()
        self.package_name = package_name

    def run(self):
        success = DependencyManager.get_instance().uninstall_package(self.package_name, self.progress.emit)
        self.finished.emit(success)


class PluginManagerDialog(QDialog):
    ICON_GREEN = None
    ICON_RED = None
    ICON_GRAY = None
    ICON_YELLOW_WARNING = None
    ICON_GREEN_RED_WARNING = None

    def __init__(self, parent, manager):
        super().__init__(parent)
        self.manager = manager
        self.config = manager.main_window.config
        self.setWindowTitle(_("Plugin Manager"))
        self.setModal(True)
        self.resize(800, 600)
        self.setStyleSheet("""
            QDialog {
                background-color: #F5F7FA;
            }
            QTextBrowser {
                background-color: transparent;
                border: none;
            }
            QPushButton {
                padding: 6px 12px;
                border-radius: 4px;
                border: 1px solid #DCDFE6;
                background-color: #FFFFFF;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #ECF5FF;
                color: #409EFF;
                border-color: #C6E2FF;
            }
            QPushButton#deleteButton {
                color: #F56C6C;
                border-color: #FBC4C4;
            }
            QPushButton#deleteButton:hover {
                background-color: #FEF0F0;
                color: #F56C6C;
                border-color: #F56C6C;
            }
            QPushButton#reloadButton {
                background-color: #F0F9EB;
                color: #67C23A;
                border-color: #E1F3D8;
            }
            QPushButton#reloadButton:hover {
                background-color: #67C23A;
                color: white;
            }
        """)
        if PluginManagerDialog.ICON_GREEN is None:
            PluginManagerDialog.ICON_GREEN = create_icon("#2ECC71")
            PluginManagerDialog.ICON_RED = create_icon("#E74C3C")
            PluginManagerDialog.ICON_GRAY = create_icon("#BDC3C7")
            PluginManagerDialog.ICON_YELLOW_WARNING = create_icon("#2ECC71", "#FDB933")
            PluginManagerDialog.ICON_GREEN_RED_WARNING = create_icon("#2ECC71", "#E74C3C")
        main_layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        self.plugin_list = QListWidget()
        self.plugin_list.currentItemChanged.connect(self.update_details)
        self.plugin_list.itemChanged.connect(self.toggle_plugin_from_list)
        self.plugin_list.setStyleSheet("QListWidget::item { padding: 5px; }")
        self.plugin_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.plugin_list.customContextMenuRequested.connect(self.show_list_context_menu)
        splitter.addWidget(self.plugin_list)

        details_widget = QWidget()
        details_layout = QVBoxLayout(details_widget)
        details_layout.setContentsMargins(10, 5, 10, 5)

        self.name_label = QLabel()
        self.name_label.setStyleSheet("font-weight: bold; font-size: 18px;")

        self.version_author_label = QLabel()
        self.version_author_label.setStyleSheet("color: #555;")
        self.version_author_label.setOpenExternalLinks(False)
        self.version_author_label.linkActivated.connect(self.open_link)

        self.compat_label = QLabel()
        self.compat_label.setWordWrap(True)

        self.plugin_deps_label = QLabel()
        self.plugin_deps_label.setWordWrap(True)
        self.plugin_deps_label.linkActivated.connect(self.on_link_activated)

        self.external_deps_label = QLabel()
        self.external_deps_label.setWordWrap(True)
        self.external_deps_label.linkActivated.connect(self.on_link_activated)

        self.description_browser = QTextBrowser()
        self.description_browser.setOpenExternalLinks(True)

        self.actions_layout = QHBoxLayout()
        self.actions_layout.setContentsMargins(0, 10, 0, 0)

        self.open_dir_button = QPushButton(_("Open Plugin Directory"))
        self.open_dir_button.clicked.connect(self.open_plugin_directory)
        self.open_dir_button.setVisible(False)
        self.actions_layout.addWidget(self.open_dir_button)

        self.delete_button = QPushButton(_("Delete Plugin"))
        self.delete_button.setObjectName("deleteButton")
        self.delete_button.clicked.connect(self.delete_plugin)
        self.delete_button.setVisible(False)
        self.actions_layout.addWidget(self.delete_button)

        self.actions_layout.addStretch(1)

        self.settings_button = QPushButton(_("Settings..."))
        self.settings_button.clicked.connect(self.open_plugin_settings)
        self.settings_button.setVisible(False)

        details_layout.addWidget(self.name_label)
        details_layout.addWidget(self.version_author_label)
        details_layout.addWidget(self.compat_label)
        details_layout.addWidget(self.plugin_deps_label)
        details_layout.addWidget(self.external_deps_label)
        details_layout.addWidget(self.description_browser)
        details_layout.addLayout(self.actions_layout)
        details_layout.addWidget(self.settings_button)
        splitter.addWidget(details_widget)

        splitter.setSizes([280, 520])

        button_layout = QHBoxLayout()

        install_button = QPushButton(_("Install from File..."))
        install_button.clicked.connect(self.install_from_file)
        button_layout.addWidget(install_button)
        marketplace_button = QPushButton(_("Open Marketplace..."))
        marketplace_button.clicked.connect(self.open_marketplace)
        button_layout.addWidget(marketplace_button)
        reload_button = QPushButton(_("Reload All Plugins"))
        reload_button.setObjectName("reloadButton")
        reload_button.clicked.connect(self.reload_plugins)
        button_layout.addWidget(reload_button)
        button_layout.addStretch()
        close_button = QPushButton(_("Close"))
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)
        main_layout.addLayout(button_layout)

        self.populate_list()

    def populate_list(self):
        self.plugin_list.blockSignals(True)
        self.plugin_list.clear()
        enabled_plugins = self.config.get('enabled_plugins', [])

        for plugin in self.manager.plugins:
            plugin_id = plugin.plugin_id()
            item = QListWidgetItem(plugin.name())
            item.setData(Qt.UserRole, plugin_id)
            is_enabled = plugin_id in enabled_plugins

            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)

            if plugin_id in self.manager.incompatible_plugins:
                if is_enabled:
                    item.setCheckState(Qt.Checked)
                    item.setIcon(self.ICON_YELLOW_WARNING)
                    item.setToolTip(_("This plugin is force-enabled despite being incompatible."))
                else:
                    item.setCheckState(Qt.Unchecked)
                    item.setForeground(QColor("gray"))
                    item.setIcon(self.ICON_RED)
                    item.setToolTip(_("This plugin is incompatible. Check to force-enable."))
            elif plugin_id in self.manager.missing_deps_plugins:
                failed_deps_str = ", ".join([d['name'] for d in self.manager.missing_deps_plugins[plugin_id]['failed_deps']])
                if is_enabled:
                    item.setCheckState(Qt.Checked)
                    item.setIcon(self.ICON_GREEN_RED_WARNING)
                    item.setToolTip(_("Force-enabled with missing libraries: {libs}").format(libs=failed_deps_str))
                else:
                    item.setCheckState(Qt.Unchecked)
                    item.setForeground(QColor("gray"))
                    item.setIcon(self.ICON_RED)
                    item.setToolTip(_("Missing external libraries: {libs}. Check to force-enable.").format(libs=failed_deps_str))
            else:
                item.setCheckState(Qt.Checked if is_enabled else Qt.Unchecked)
                item.setIcon(self.ICON_GREEN if is_enabled else self.ICON_GRAY)

            self.plugin_list.addItem(item)

        for plugin_id, info in self.manager.invalid_plugins.items():
            try:
                plugin_name = info['spec']['class']().name()
            except:
                plugin_name = plugin_id

            item = QListWidgetItem(plugin_name)
            item.setData(Qt.UserRole, plugin_id)
            item.setFlags(item.flags() & ~Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            item.setForeground(QColor("darkred"))
            item.setIcon(self.ICON_RED)
            item.setToolTip(_("Failed to load: {reason}").format(reason=info['reason']))
            self.plugin_list.addItem(item)

        self.plugin_list.blockSignals(False)

        if self.plugin_list.count() > 0:
            self.plugin_list.setCurrentRow(0)

    def toggle_plugin_from_list(self, item):
        self.plugin_list.blockSignals(True)
        try:
            plugin_id = item.data(Qt.UserRole)
            plugin = self.manager.get_plugin(plugin_id)
            if not plugin:
                self.plugin_list.blockSignals(False)
                return

            is_checked = item.checkState() == Qt.Checked
            enabled_plugins = self.config.get('enabled_plugins', [])

            # 启用/禁用
            if is_checked and plugin_id in self.manager.incompatible_plugins:
                reply = QMessageBox.warning(
                    self,
                    _("Compatibility Warning"),
                    _("The plugin '{plugin_name}' is not marked as compatible with this application version.\n\n"
                      "Forcing it to enable may cause instability or crashes.\n\n"
                      "Are you sure you want to force enable it?").format(plugin_name=item.text()),
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    if plugin_id not in enabled_plugins: enabled_plugins.append(plugin_id)
                    item.setIcon(self.ICON_YELLOW_WARNING)
                    self.manager.main_window.update_statusbar(
                        _("Plugin '{plugin_name}' force-enabled.").format(plugin_name=plugin.name()), persistent=True)
                else:
                    item.setCheckState(Qt.Unchecked)
                    item.setIcon(self.ICON_RED)
                    self.plugin_list.blockSignals(False)
                    return
            elif is_checked and plugin_id in self.manager.missing_deps_plugins:
                failed_deps = self.manager.missing_deps_plugins[plugin_id]['failed_deps']
                failed_deps_str = "\n- ".join([f"{d['name']} ({d['status']})" for d in failed_deps])
                reply = QMessageBox.warning(
                    self,
                    _("Missing Dependencies"),
                    _("The plugin '{plugin_name}' is missing required external libraries:\n\n- {libs}\n\n"
                      "The plugin will likely fail to run correctly. You can try to install them from the details panel.\n\n"
                      "Are you sure you want to force enable it anyway?").format(plugin_name=item.text(), libs=failed_deps_str),
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    if plugin_id not in enabled_plugins: enabled_plugins.append(plugin_id)
                    item.setIcon(self.ICON_GREEN_RED_WARNING)
                    self.manager.main_window.update_statusbar(
                        _("Plugin '{plugin_name}' force-enabled with missing libraries.").format(plugin_name=plugin.name()), persistent=True)
                else:
                    item.setCheckState(Qt.Unchecked)
                    item.setIcon(self.ICON_RED)
                    self.plugin_list.blockSignals(False)
                    return
            elif is_checked:
                if not self.manager.check_dependencies(plugin_id):
                    item.setCheckState(Qt.Unchecked)
                    item.setIcon(self.ICON_GRAY)
                    self.plugin_list.blockSignals(False)
                    return
                if plugin_id not in enabled_plugins: enabled_plugins.append(plugin_id)
                item.setIcon(self.ICON_GREEN)
                self.manager.main_window.update_statusbar(
                    _("Plugin '{plugin_name}' enabled.").format(plugin_name=plugin.name()), persistent=True)
            else: # 禁用
                if self.manager.is_dependency_for_others(plugin_id):
                    item.setCheckState(Qt.Checked)
                    if plugin_id in self.manager.incompatible_plugins:
                        item.setIcon(self.ICON_YELLOW_WARNING)
                    elif plugin_id in self.manager.missing_deps_plugins:
                        item.setIcon(self.ICON_GREEN_RED_WARNING)
                    else:
                        item.setIcon(self.ICON_GREEN)
                    self.plugin_list.blockSignals(False)
                    return

                if plugin_id in enabled_plugins: enabled_plugins.remove(plugin_id)

                if plugin_id in self.manager.incompatible_plugins:
                    item.setIcon(self.ICON_RED)
                elif plugin_id in self.manager.missing_deps_plugins:
                    item.setIcon(self.ICON_RED)
                else:
                    item.setIcon(self.ICON_GRAY)
                self.manager.main_window.update_statusbar(
                    _("Plugin '{plugin_name}' disabled.").format(plugin_name=plugin.name()), persistent=True)

            self.config['enabled_plugins'] = enabled_plugins
            self.manager.main_window.save_config()
            self.manager.invalidate_cache()

        finally:
            self.plugin_list.blockSignals(False)

    def open_link(self, link_str):
        QDesktopServices.openUrl(QUrl(link_str))

    def open_plugin_settings(self):
        current_item = self.plugin_list.currentItem()
        if not current_item:
            return
        plugin_id = current_item.data(Qt.UserRole)
        plugin = self.manager.get_plugin(plugin_id)
        if plugin:
            plugin.show_settings_dialog(self)

    def update_details(self, current, previous):
        self.plugin_deps_label.hide()
        self.external_deps_label.hide()
        self.settings_button.hide()
        self.compat_label.hide()
        self.open_dir_button.hide()
        self.delete_button.hide()

        if not current:
            self.name_label.clear()
            self.version_author_label.clear()
            self.description_browser.clear()
            return

        plugin_id = current.data(Qt.UserRole)

        if plugin_id in self.manager.invalid_plugins:
            info = self.manager.invalid_plugins[plugin_id]
            metadata = info.get('spec', {}).get('metadata', {})
            self.name_label.setText(metadata.get('name', plugin_id))
            self.version_author_label.setText(
                f"{_('Version')}: {metadata.get('version', 'N/A')}  |  {_('Author')}: {metadata.get('author', 'N/A')}"
            )
            self.description_browser.setHtml(f"<p>{metadata.get('description', '')}</p>")
            self.compat_label.setText(
                f"<b style='color:red;'>{_('Loading Failed')}</b><br><small>{info['reason']}</small>")
            self.compat_label.setVisible(True)
            return
        plugin = self.manager.get_plugin(plugin_id)
        if not plugin:
            return

        self.open_dir_button.show()
        self.delete_button.show()
        # 显示基本信息
        self.name_label.setText(plugin.name())
        html_info = f"{_('Version')}: {plugin.version()}  |  {_('Author')}: {plugin.author()}"
        self.version_author_label.setText(html_info)
        url = plugin.url()
        if url:
            html_info += f"<br><a href='{url}'>{_('Visit Plugin Homepage')}</a>"

        self.version_author_label.setText(html_info)
        self.description_browser.setHtml(f"<p>{plugin.description()}</p>")

        # 版本兼容
        if plugin_id in self.manager.incompatible_plugins:
            info = self.manager.incompatible_plugins[plugin_id]
            self.compat_label.setText(
                f"<b style='color:#E74C3C;'>{_('Incompatible')}</b><br>"
                f"<small>{_('Requires App Version')}: <b>{info['required']}</b> | {_('Current')}: {info['current']}</small>"
            )
            self.compat_label.setVisible(True)
        elif plugin_id in self.manager.missing_deps_plugins:
            failed_deps = self.manager.missing_deps_plugins[plugin_id]['failed_deps']
            failed_deps_str = ", ".join([f"{d['name']} ({d['status']})" for d in failed_deps])
            self.compat_label.setText(
                f"<b style='color:#E74C3C;'>{_('Missing Libraries')}</b>"
            )
            self.compat_label.setVisible(True)
        else:
            required_version = plugin.compatible_app_version()
            if required_version:
                self.compat_label.setText(
                    f"<b style='color:#2ECC71;'>{_('Compatible')}</b><br>"
                    f"<small>{_('Requires App Version')}: <b>{required_version}</b></small>"
                )
                self.compat_label.setVisible(True)
            else:
                self.compat_label.setVisible(False)

        # 插件依赖
        plugin_deps = plugin.plugin_dependencies()
        if plugin_deps:
            html = f"<b>{_('Plugin Dependencies')}:</b> "
            links = []
            all_plugins = {p.plugin_id(): p for p in self.manager.plugins}
            for dep_id, spec in plugin_deps.items():
                res = DependencyManager.get_instance().check_plugin_dependency(dep_id, spec, all_plugins)
                color = {'ok': 'green', 'missing': 'red', 'outdated': 'orange'}[res['status']]
                title = f"{_('Required')}: {res['required'] or 'any'}\n{_('Installed')}: {res['installed'] or 'N/A'}"
                links.append(
                    f"<a href='plugin:{dep_id}' style='color:{color}; text-decoration:none;' title='{title}'>{res['name']}</a>")
            html += ", ".join(links)
            self.plugin_deps_label.setText(html)
            self.plugin_deps_label.show()

        # 外部库依赖
        ext_deps = plugin.external_dependencies()
        if ext_deps:
            html = f"<b>{_('External Libraries')}:</b> "
            links = []
            for lib_name, spec in ext_deps.items():
                res = DependencyManager.get_instance().check_external_dependency(lib_name, spec)
                color = {'ok': 'green', 'missing': 'red', 'outdated': 'orange'}[res['status']]
                title = f"{_('Required')}: {res['required'] or 'any'}\n{_('Installed')}: {res['installed'] or 'N/A'}"
                links.append(
                    f"<a href='lib:{lib_name}:{spec}' style='color:{color}; text-decoration:none;' title='{title}'>{res['name']}</a>")
            html += ", ".join(links)
            self.external_deps_label.setText(html)
            self.external_deps_label.show()
        method_on_instance_class = plugin.__class__.show_settings_dialog
        method_on_base_class = PluginBase.show_settings_dialog
        has_settings = method_on_instance_class is not method_on_base_class
        self.settings_button.setVisible(has_settings)

    def show_list_context_menu(self, pos):
        item = self.plugin_list.itemAt(pos)
        if not item:
            return
        plugin_id = item.data(Qt.UserRole)
        plugin = self.manager.get_plugin(plugin_id)
        if not plugin:
            return
        menu = QMenu()
        is_checked = item.checkState() == Qt.Checked
        toggle_action = QAction(_("Disable") if is_checked else _("Enable"), self)
        toggle_action.triggered.connect(lambda: item.setCheckState(Qt.Unchecked if is_checked else Qt.Checked))
        menu.addAction(toggle_action)
        menu.addSeparator()
        open_dir_action = QAction(_("Open Plugin Directory"), self)
        open_dir_action.triggered.connect(self.open_plugin_directory)
        menu.addAction(open_dir_action)
        delete_action = QAction(_("Delete Plugin"), self)
        delete_action.triggered.connect(self.delete_plugin)
        menu.addAction(delete_action)
        menu.exec(self.plugin_list.mapToGlobal(pos))

    def install_from_file(self):
        filepath, __ = QFileDialog.getOpenFileName(
            self,
            _("Select Plugin Archive"),
            self.manager.main_window.config.get("last_dir", ""),
            f"{_('Plugin Archives')} (*.zip)"
        )
        if not filepath:
            return
        try:
            installed_plugin_id, message = self.manager.install_plugin_from_zip(filepath)
            if installed_plugin_id:
                QMessageBox.information(
                    self,
                    _("Installation Successful"),
                    _("Plugin '{plugin_id}' has been installed.\n\nPlease restart the application to enable it.").format(
                        plugin_id=installed_plugin_id)
                )
                self.reload_plugins()
                for i in range(self.plugin_list.count()):
                    item = self.plugin_list.item(i)
                    if item.data(Qt.UserRole) == installed_plugin_id:
                        self.plugin_list.setCurrentItem(item)
                        break
            else:
                QMessageBox.critical(self, _("Installation Failed"), message)
        except Exception as e:
            QMessageBox.critical(self, _("Installation Error"), str(e))

    def open_marketplace(self):
        self.accept()
        self.manager.show_marketplace_dialog()

    def open_plugin_directory(self):
        current_item = self.plugin_list.currentItem()
        if not current_item: return
        plugin_id = current_item.data(Qt.UserRole)

        plugin_dir = os.path.join(self.manager.plugin_dir, plugin_id)
        if os.path.isdir(plugin_dir):
            QDesktopServices.openUrl(QUrl.fromLocalFile(plugin_dir))
        else:
            QMessageBox.warning(self, _("Error"), _("Plugin directory not found."))

    def delete_plugin(self):
        current_item = self.plugin_list.currentItem()
        if not current_item: return
        plugin_id = current_item.data(Qt.UserRole)
        plugin = self.manager.get_plugin(plugin_id)
        if not plugin: return

        reply = QMessageBox.warning(
            self,
            _("Confirm Deletion"),
            _("Are you sure you want to permanently delete the plugin '{plugin_name}'?\n\n"
              "The application will need to be restarted after deletion.").format(plugin_name=plugin.name()),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            success, message = self.manager.delete_plugin(plugin_id)
            if success:
                QMessageBox.information(
                    self,
                    _("Plugin Deleted"),
                    _("Plugin '{plugin_name}' has been deleted.\nPlease restart the application.").format(
                        plugin_name=plugin.name())
                )
                self.populate_list()
            else:
                QMessageBox.critical(self, _("Error"), message)

    def on_link_activated(self, link: str):
        parts = link.split(':', 2)
        link_type = parts[0]

        if link_type == 'plugin':
            plugin_id = parts[1]
            for i in range(self.plugin_list.count()):
                item = self.plugin_list.item(i)
                if item.data(Qt.UserRole) == plugin_id:
                    self.plugin_list.setCurrentItem(item)
                    return
        elif link_type == 'lib':
            lib_name, spec = parts[1], parts[2]
            self.install_dependency_dialog(lib_name, spec)

    def install_dependency_dialog(self, lib_name, spec):
        res = DependencyManager.get_instance().check_external_dependency(lib_name, spec)

        if res['status'] == 'ok':
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle(_("Dependency Check"))
            msg_box.setText(_("Library '{lib}' is already installed and compatible.").format(lib=lib_name))
            msg_box.setIcon(QMessageBox.Information)
            uninstall_btn = msg_box.addButton(_("Uninstall"), QMessageBox.ResetRole)
            ok_btn = msg_box.addButton(_("OK"), QMessageBox.AcceptRole)
            uninstall_btn.setStyleSheet("""
                QPushButton {
                    color: #F56C6C;
                    border: 1px solid #FBC4C4;
                    border-radius: 4px;
                    padding: 6px 12px;
                    background-color: #FFFFFF;
                }
                QPushButton:hover {
                    background-color: #FEF0F0;
                    color: #F56C6C;
                    border-color: #F56C6C;
                }
            """)

            msg_box.exec()

            if msg_box.clickedButton() == uninstall_btn:
                self.confirm_and_uninstall(lib_name)
            return

        action_text = _("Install") if res['status'] == 'missing' else _("Update")

        reply = QMessageBox.question(
            self, _("Install Dependency"),
            _("The plugin requires the library '{lib}' (version: {spec}).\n\nDo you want to try to {action} it now?").format(
                lib=lib_name, spec=spec or "any", action=action_text
            ),
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            log_dialog = QDialog(self)
            log_dialog.setWindowTitle(_("Installing {lib}...").format(lib=lib_name))
            log_dialog.setMinimumSize(600, 400)
            layout = QVBoxLayout(log_dialog)
            log_browser = QTextBrowser()
            layout.addWidget(log_browser)
            self.install_thread = InstallThread({lib_name: spec})  # 传递字典
            self.install_thread.progress.connect(log_browser.append)
            self.install_thread.finished.connect(
                lambda success: self.on_install_finished(success, lib_name, log_dialog)
            )
            self.install_thread.start()
            log_dialog.exec()

    def on_install_finished(self, success, lib_name, log_dialog):
        log_dialog.close()
        if success:
            QMessageBox.information(self, _("Success"), _(
                "Library '{lib}' installed successfully.\nPlease restart the application to use the plugin.").format(
                lib=lib_name))
            DependencyManager.get_instance()._cache.pop(lib_name, None)
            self.update_details(self.plugin_list.currentItem(), None)
        else:
            QMessageBox.critical(self, _("Failed"),
                                 _("Failed to install library '{lib}'.\nPlease check the log for details.").format(
                                     lib=lib_name))

    def confirm_and_uninstall(self, lib_name):
        reply = QMessageBox.question(
            self,
            _("Confirm Uninstall"),
            _("Are you sure you want to uninstall the library '{lib}'?\nThis may break plugins that depend on it.").format(
                lib=lib_name),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            log_dialog = QDialog(self)
            log_dialog.setWindowTitle(_("Uninstalling {lib}...").format(lib=lib_name))
            log_dialog.setMinimumSize(600, 400)
            layout = QVBoxLayout(log_dialog)
            log_browser = QTextBrowser()
            layout.addWidget(log_browser)

            self.uninstall_thread = UninstallThread(lib_name)
            self.uninstall_thread.progress.connect(log_browser.append)
            self.uninstall_thread.finished.connect(
                lambda success: self.on_uninstall_finished(success, lib_name, log_dialog)
            )
            self.uninstall_thread.start()
            log_dialog.exec()

    def on_uninstall_finished(self, success, lib_name, log_dialog):
        log_dialog.close()
        if success:
            QMessageBox.information(self, _("Success"), _(
                "Library '{lib}' uninstalled successfully.").format(lib=lib_name))
            self.update_details(self.plugin_list.currentItem(), None)
        else:
            QMessageBox.critical(self, _("Failed"),
                                 _("Failed to uninstall library '{lib}'.\nPlease check the log for details.").format(
                                     lib=lib_name))

    def reload_plugins(self):
        self.manager.reload_plugins()
        self.populate_list()
