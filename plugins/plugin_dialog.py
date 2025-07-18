# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QListWidgetItem, QHBoxLayout, QLabel, QTextBrowser, \
    QPushButton, QSplitter, QWidget, QMessageBox
from PySide6.QtCore import Qt, QUrl, QRectF
from PySide6.QtGui import QColor, QFont, QIcon, QPixmap, QPainter, QDesktopServices
from plugins.plugin_base import PluginBase
from utils.localization import _

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

class PluginManagerDialog(QDialog):
    ICON_GREEN = None
    ICON_RED = None
    ICON_GRAY = None
    ICON_YELLOW_WARNING = None

    def __init__(self, parent, manager):
        super().__init__(parent)
        self.manager = manager
        self.config = manager.main_window.config
        self.setWindowTitle(_("Plugin Manager"))
        self.setModal(True)
        self.resize(800, 600)
        if PluginManagerDialog.ICON_GREEN is None:
            PluginManagerDialog.ICON_GREEN = create_icon("#2ECC71")
            PluginManagerDialog.ICON_RED = create_icon("#E74C3C")
            PluginManagerDialog.ICON_GRAY = create_icon("#BDC3C7")
            PluginManagerDialog.ICON_YELLOW_WARNING = create_icon("#2ECC71", "#FDB933")
        main_layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        self.plugin_list = QListWidget()
        self.plugin_list.currentItemChanged.connect(self.update_details)
        self.plugin_list.itemChanged.connect(self.toggle_plugin_from_list)
        self.plugin_list.setStyleSheet("QListWidget::item { padding: 5px; }")
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

        self.dependencies_label = QLabel()
        self.dependencies_label.setWordWrap(True)

        self.description_browser = QTextBrowser()
        self.description_browser.setOpenExternalLinks(True)

        self.settings_button = QPushButton(_("Settings..."))
        self.settings_button.clicked.connect(self.open_plugin_settings)
        self.settings_button.setVisible(False)

        details_layout.addWidget(self.name_label)
        details_layout.addWidget(self.version_author_label)
        details_layout.addWidget(self.compat_label)
        details_layout.addWidget(self.dependencies_label)
        details_layout.addWidget(self.description_browser)
        details_layout.addWidget(self.settings_button)
        splitter.addWidget(details_widget)

        splitter.setSizes([280, 520])

        button_layout = QHBoxLayout()
        reload_button = QPushButton(_("Reload All Plugins"))
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
            else:
                item.setCheckState(Qt.Checked if is_enabled else Qt.Unchecked)
                item.setIcon(self.ICON_GREEN if is_enabled else self.ICON_GRAY)

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

            if is_checked and plugin_id in self.manager.incompatible_plugins:
                reply = QMessageBox.warning(
                    self,
                    _("Compatibility Warning"),
                    _("The plugin '{plugin_name}' is not marked as compatible with this version of the application.\n\n"
                      "Forcing it to enable may cause instability or crashes.\n\n"
                      "Are you sure you want to force enable it?").format(plugin_name=item.text()),
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )

                if reply == QMessageBox.Yes:
                    if plugin_id not in enabled_plugins:
                        enabled_plugins.append(plugin_id)
                    item.setIcon(self.ICON_YELLOW_WARNING)
                    self.manager.main_window.update_statusbar(
                        _("Plugin '{plugin_name}' force-enabled.").format(plugin_name=plugin.name()),
                        persistent=True
                    )
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

                if plugin_id not in enabled_plugins:
                    enabled_plugins.append(plugin_id)
                item.setIcon(self.ICON_GREEN)
                self.manager.main_window.update_statusbar(
                    _("Plugin '{plugin_name}' enabled.").format(plugin_name=plugin.name()),
                    persistent=True
                )
            else:
                if self.manager.is_dependency_for_others(plugin_id):
                    item.setCheckState(Qt.Checked)
                    if plugin_id in self.manager.incompatible_plugins:
                        item.setIcon(self.ICON_YELLOW_WARNING)
                    else:
                        item.setIcon(self.ICON_GREEN)
                    self.plugin_list.blockSignals(False)
                    return

                if plugin_id in enabled_plugins:
                    enabled_plugins.remove(plugin_id)

                if plugin_id in self.manager.incompatible_plugins:
                    item.setIcon(self.ICON_RED)
                else:
                    item.setIcon(self.ICON_GRAY)
                self.manager.main_window.update_statusbar(
                    _("Plugin '{plugin_name}' disabled.").format(plugin_name=plugin.name()),
                    persistent=True
                )

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
        self.settings_button.setVisible(False)
        if not current:
            self.name_label.clear()
            self.version_author_label.clear()
            self.description_browser.clear()
            self.compat_label.clear()
            self.dependencies_label.clear()
            return

        plugin_id = current.data(Qt.UserRole)
        plugin = self.manager.get_plugin(plugin_id)
        if plugin:
            self.name_label.setText(plugin.name())

            version_info = f"{_('Version')}: {plugin.version()}"
            author_info = f"{_('Author')}: {plugin.author()}"
            url = plugin.url()

            html_info = f"{version_info}  |  {author_info}"
            if url:
                html_info += f"<br><a href='{url}'>{_('Visit Plugin Homepage')}</a>"

            self.version_author_label.setText(html_info)

            if plugin_id in self.manager.incompatible_plugins:
                info = self.manager.incompatible_plugins[plugin_id]
                self.compat_label.setText(
                    f"<b style='color:#E74C3C;'>{_('Incompatible')}</b><br>"
                    f"<small>{_('Requires App Version')}: <b>{info['required']}</b> | {_('Current')}: {info['current']}</small>"
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

            deps = plugin.dependencies()
            if deps:
                dep_names = [self.manager.get_plugin(dep_id).name() for dep_id in deps if
                             self.manager.get_plugin(dep_id)]
                self.dependencies_label.setText(f"<b>{_('Dependencies')}:</b> {', '.join(dep_names)}")
                self.dependencies_label.setVisible(True)
            else:
                self.dependencies_label.setVisible(False)

            desc_html = f"<p>{plugin.description()}</p>"
            self.description_browser.setHtml(desc_html)

            method_on_instance_class = plugin.__class__.show_settings_dialog
            method_on_base_class = PluginBase.show_settings_dialog
            has_settings = method_on_instance_class is not method_on_base_class
            self.settings_button.setVisible(has_settings)

    def reload_plugins(self):
        self.manager.reload_plugins()
        self.populate_list()