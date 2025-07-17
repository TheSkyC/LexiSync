# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QListWidgetItem, QHBoxLayout, QLabel, QTextBrowser, \
    QPushButton, QSplitter, QWidget
from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices
from utils.localization import _


class PluginManagerDialog(QDialog):
    def __init__(self, parent, manager):
        super().__init__(parent)
        self.manager = manager
        self.config = manager.main_window.config
        self.setWindowTitle(_("Plugin Manager"))
        self.setModal(True)
        self.resize(750, 550)

        main_layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        self.plugin_list = QListWidget()
        self.plugin_list.currentItemChanged.connect(self.update_details)
        self.plugin_list.itemChanged.connect(self.toggle_plugin_from_list)
        splitter.addWidget(self.plugin_list)

        details_widget = QWidget()
        details_layout = QVBoxLayout(details_widget)
        self.name_label = QLabel()
        self.name_label.setStyleSheet("font-weight: bold; font-size: 16px;")
        self.version_author_label = QLabel()
        self.dependencies_label = QLabel()
        self.dependencies_label.setWordWrap(True)
        self.description_browser = QTextBrowser()
        self.description_browser.setOpenExternalLinks(True)

        details_layout.addWidget(self.name_label)
        details_layout.addWidget(self.version_author_label)
        details_layout.addWidget(self.dependencies_label)
        details_layout.addWidget(self.description_browser)
        splitter.addWidget(details_widget)

        splitter.setSizes([250, 500])

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
            item = QListWidgetItem(plugin.name())
            item.setData(Qt.UserRole, plugin.plugin_id())
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            is_enabled = plugin.plugin_id() in enabled_plugins
            item.setCheckState(Qt.Checked if is_enabled else Qt.Unchecked)
            self.plugin_list.addItem(item)
        self.plugin_list.blockSignals(False)

        if self.plugin_list.count() > 0:
            self.plugin_list.setCurrentRow(0)

    def update_details(self, current, previous):
        if not current:
            self.name_label.clear()
            self.version_author_label.clear()
            self.description_browser.clear()
            self.dependencies_label.clear()
            return

        plugin_id = current.data(Qt.UserRole)
        plugin = self.manager.get_plugin(plugin_id)
        if plugin:
            self.name_label.setText(plugin.name())
            self.version_author_label.setText(
                f"{_('Version')}: {plugin.version()}  |  {_('Author')}: {plugin.author()}")

            deps = plugin.dependencies()
            if deps:
                self.dependencies_label.setText(f"<b>{_('Dependencies')}:</b> {', '.join(deps)}")
                self.dependencies_label.setVisible(True)
            else:
                self.dependencies_label.setVisible(False)

            desc_html = f"<p>{plugin.description()}</p>"
            if plugin.url():
                desc_html += f"<p><a href='{plugin.url()}'>{_('Visit Plugin Homepage')}</a></p>"
            self.description_browser.setHtml(desc_html)

    def toggle_plugin_from_list(self, item):
        plugin_id = item.data(Qt.UserRole)
        is_checked = item.checkState() == Qt.Checked

        enabled_plugins = self.config.get('enabled_plugins', [])

        if is_checked:
            if not self.manager.check_dependencies(plugin_id):
                item.setCheckState(Qt.Unchecked)
                return
            if plugin_id not in enabled_plugins:
                enabled_plugins.append(plugin_id)
        else:
            if plugin_id in enabled_plugins:
                enabled_plugins.remove(plugin_id)

        self.config['enabled_plugins'] = enabled_plugins
        self.manager.main_window.save_config()
        self.manager.invalidate_cache()

    def reload_plugins(self):
        self.manager.reload_plugins()
        self.populate_list()