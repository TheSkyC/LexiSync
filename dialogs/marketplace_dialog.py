# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QWidget, QTextBrowser, QFrame,
    QMessageBox, QSplitter
)
from PySide6.QtCore import Qt, QSize, QThread, Signal, QUrl
from PySide6.QtGui import QFont, QDesktopServices, QMouseEvent
from utils.constants import APP_VERSION
import requests
import os
import tempfile
import re
from utils.localization import _

class FetchIndexThread(QThread):
    finished = Signal(dict, str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            response = requests.get(self.url, timeout=10)
            response.raise_for_status()
            data = response.json()
            self.finished.emit(data, None)
        except Exception as e:
            self.finished.emit(None, str(e))


class DownloadPluginThread(QThread):
    finished = Signal(str, str)

    def __init__(self, url, temp_dir):
        super().__init__()
        self.url = url
        self.temp_dir = temp_dir

    def run(self):
        try:
            response = requests.get(self.url, stream=True, timeout=60)
            response.raise_for_status()

            if 'content-disposition' in response.headers:
                disposition = response.headers['content-disposition']
                filenames = re.findall('filename="(.+)"', disposition)
                if filenames:
                    filename = filenames[0]
                else:
                    filename = self.url.split('/')[-1]
            else:
                filename = self.url.split('/')[-1]

            if not filename.endswith('.zip'):
                filename += '.zip'

            temp_filepath = os.path.join(self.temp_dir, filename)

            with open(temp_filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            self.finished.emit(temp_filepath, None)
        except Exception as e:
            self.finished.emit(None, str(e))

class ClickableLabel(QLabel):
    clicked = Signal(str)

    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("""
            QLabel {
                background-color: #E9ECEF;
                color: #495057;
                padding: 2px 6px;
                border-radius: 4px;
                font-size: 11px;
            }
            QLabel:hover {
                background-color: #DEE2E6;
            }
        """)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.text())
        super().mousePressEvent(event)

class PluginMarketplaceItem(QWidget):
    tag_clicked = Signal(str)

    def __init__(self, plugin_data, parent=None):
        super().__init__(parent)
        self.plugin_data = plugin_data

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(5)

        top_layout = QHBoxLayout()
        top_layout.setSpacing(10)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        self.name_label = QLabel(f"<b>{plugin_data['name']}</b>")
        self.name_label.setFont(QFont("Segoe UI", 11))

        self.author_label = QLabel(f"<small>{_('by')} {plugin_data['author']}</small>")
        self.author_label.setStyleSheet("color: #666;")

        self.desc_label = QLabel(plugin_data['description'])
        self.desc_label.setWordWrap(True)

        info_layout.addWidget(self.name_label)
        info_layout.addWidget(self.author_label)
        info_layout.addWidget(self.desc_label)
        info_layout.addStretch()

        top_layout.addLayout(info_layout, 1)

        self.install_button = QPushButton()
        self.install_button.setFixedSize(90, 32)
        self.install_button.setObjectName("installButton")
        top_layout.addWidget(self.install_button)

        main_layout.addLayout(top_layout)

        if plugin_data.get('tags'):
            self.tags_layout = QHBoxLayout()
            self.tags_layout.setContentsMargins(0, 5, 0, 0)
            self.tags_layout.setSpacing(5)
            for tag in plugin_data['tags']:
                tag_label = ClickableLabel(tag)
                tag_label.clicked.connect(self.tag_clicked.emit)
                self.tags_layout.addWidget(tag_label)
            self.tags_layout.addStretch()
            main_layout.addLayout(self.tags_layout)

    def set_status(self, status, version_info=""):
        if status == 'installed':
            self.install_button.setText(_("Installed"))
            self.install_button.setEnabled(False)
            self.install_button.setProperty("status", "installed")
        elif status == 'update_available':
            self.install_button.setText(_("Update"))
            self.install_button.setEnabled(True)
            self.install_button.setProperty("status", "update")
        else:
            self.install_button.setText(_("Install"))
            self.install_button.setEnabled(True)
            self.install_button.setProperty("status", "install")

        self.install_button.style().unpolish(self.install_button)
        self.install_button.style().polish(self.install_button)

class PluginMarketplaceDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.app = parent
        self.manager = self.app.plugin_manager
        self.market_data = None
        self.installed_plugins_map = {}
        self.active_tags = set()
        self.tag_buttons = {}
        self.temp_dir_for_download = None

        self.setWindowTitle(_("Plugin Marketplace"))
        self.setModal(True)
        self.resize(1000, 700)
        self.setup_styles()
        self.setup_ui()
        self.load_market_index()

    def setup_styles(self):
        self.setStyleSheet("""
            QDialog { background-color: #F5F7FA; }
            QSplitter::handle { background-color: #E4E7ED; }
            QLineEdit { padding: 8px; border: 1px solid #DCDFE6; border-radius: 4px; }
            QListWidget { border: none; background-color: #FFFFFF; }
            QFrame#detailsContainer { background-color: #FFFFFF; border-left: 1px solid #E4E7ED; }
            QTextBrowser { border: none; background-color: transparent; }
            QPushButton {
                padding: 8px 16px; border-radius: 4px; border: 1px solid #DCDFE6;
                background-color: #FFFFFF; font-weight: 500;
            }
            QPushButton:hover { background-color: #ECF5FF; color: #409EFF; border-color: #C6E2FF; }

            QPushButton[status="install"] { background-color: #409EFF; color: white; border: none; }
            QPushButton[status="install"]:hover { background-color: #66B1FF; }

            QPushButton[status="update"] { background-color: #E6A23C; color: white; border: none; }
            QPushButton[status="update"]:hover { background-color: #EBB563; }

            QPushButton[status="installed"] { background-color: #F5F7FA; color: #909399; border: 1px solid #E4E7ED; }

            QPushButton#tagButton {
                padding: 4px 10px; font-size: 12px;
            }
            QPushButton#tagButton:checked {
                background-color: #409EFF; color: white; border-color: #409EFF;
            }
        """)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 10, 0, 10)

        filter_container = QWidget()
        filter_layout = QVBoxLayout(filter_container)
        filter_layout.setContentsMargins(10, 0, 10, 5)
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText(_("Search plugins..."))
        self.search_box.textChanged.connect(self.filter_plugins)

        self.tags_bar = QHBoxLayout()
        self.tags_bar.setContentsMargins(0, 5, 0, 0)
        self.tags_bar.setSpacing(8)
        self.tags_bar.setAlignment(Qt.AlignLeft)

        filter_layout.addWidget(self.search_box)
        filter_layout.addLayout(self.tags_bar)
        main_layout.addWidget(filter_container)

        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter, 1)

        self.plugin_list = QListWidget()
        self.plugin_list.currentItemChanged.connect(self.update_details_panel)
        splitter.addWidget(self.plugin_list)

        details_container = QFrame()
        details_container.setObjectName("detailsContainer")
        details_layout = QVBoxLayout(details_container)
        details_layout.setContentsMargins(15, 15, 15, 15)

        self.detail_name = QLabel("<h2>" + _("Select a plugin") + "</h2>")
        self.detail_author_version = QLabel()
        self.detail_compat = QLabel()
        self.detail_links = QLabel()
        self.detail_links.setOpenExternalLinks(True)
        self.detail_desc = QTextBrowser()
        self.detail_desc.setOpenExternalLinks(True)
        self.detail_install_button = QPushButton()
        self.detail_install_button.setFixedHeight(36)
        self.detail_install_button.setObjectName("installButton")
        self.detail_install_button.clicked.connect(self.on_install_button_clicked)

        details_layout.addWidget(self.detail_name)
        details_layout.addWidget(self.detail_author_version)
        details_layout.addWidget(self.detail_compat)
        details_layout.addWidget(self.detail_links)
        details_layout.addWidget(self.detail_desc, 1)
        details_layout.addWidget(self.detail_install_button)

        splitter.addWidget(details_container)
        splitter.setSizes([350, 550])

        bottom_bar = QHBoxLayout()
        bottom_bar.setContentsMargins(10, 0, 10, 0)
        self.status_label = QLabel(_("Loading marketplace..."))
        close_button = QPushButton(_("Close"))
        close_button.clicked.connect(self.accept)
        bottom_bar.addWidget(self.status_label)
        bottom_bar.addStretch()
        bottom_bar.addWidget(close_button)
        main_layout.addLayout(bottom_bar)

    def load_market_index(self):
        self.status_label.setText(_("Fetching plugin index..."))
        self.fetch_thread = FetchIndexThread(self.manager.get_market_url())
        self.fetch_thread.finished.connect(self.on_index_loaded)
        self.fetch_thread.start()
    def on_index_loaded(self, data, error_message):
        if error_message:
            self.status_label.setText(_("Error: Could not load marketplace index. {error}").format(error=error_message))
            QMessageBox.critical(self, _("Network Error"), _("Failed to fetch plugin list from the server."))
            return
        self.market_data = data
        self.refresh_installed_plugins_map()
        self.populate_tags_bar()
        self.populate_plugin_list()
        self.status_label.setText(
            _("Marketplace loaded. Found {count} plugins.").format(count=len(data.get('plugins', []))))

    def refresh_installed_plugins_map(self):
        self.installed_plugins_map = {p.plugin_id(): p.version() for p in self.manager.plugins}

    def populate_tags_bar(self):
        while self.tags_bar.count():
            item = self.tags_bar.takeAt(0)
            if widget := item.widget():
                widget.deleteLater()
        self.tag_buttons.clear()

        if not self.market_data or 'plugins' not in self.market_data:
            return
        all_tags = set()
        for plugin in self.market_data['plugins']:
            for tag in plugin.get('tags', []):
                all_tags.add(tag)
        all_btn = QPushButton(_("All"))
        all_btn.setObjectName("tagButton")
        all_btn.setCheckable(True)
        all_btn.setChecked(True)
        all_btn.toggled.connect(self.on_all_tag_toggled)
        self.tags_bar.addWidget(all_btn)
        self.tag_buttons['All'] = all_btn

        for tag in sorted(list(all_tags)):
            btn = QPushButton(tag)
            btn.setObjectName("tagButton")
            btn.setCheckable(True)
            btn.toggled.connect(lambda checked, t=tag: self.on_tag_toggled(t, checked))
            self.tags_bar.addWidget(btn)
            self.tag_buttons[tag] = btn
        self.tags_bar.addStretch()

    def on_all_tag_toggled(self, checked):
        if checked:
            self.active_tags.clear()
            for tag, btn in self.tag_buttons.items():
                if tag != 'All' and btn.isChecked():
                    btn.setChecked(False)
            self.filter_plugins()

    def on_tag_toggled(self, tag, checked):
        if checked:
            self.active_tags.add(tag)
            if self.tag_buttons['All'].isChecked():
                self.tag_buttons['All'].setChecked(False)
        else:
            self.active_tags.discard(tag)
            if not self.active_tags:
                self.tag_buttons['All'].setChecked(True)

        self.filter_plugins()

    def on_item_tag_clicked(self, tag):
        if tag in self.tag_buttons:
            self.tag_buttons[tag].setChecked(True)

    def populate_plugin_list(self):
        self.plugin_list.clear()
        if not self.market_data or 'plugins' not in self.market_data:
            return

        for plugin_data in self.market_data['plugins']:
            item = QListWidgetItem(self.plugin_list)
            widget = PluginMarketplaceItem(plugin_data)
            widget.tag_clicked.connect(self.on_item_tag_clicked)

            plugin_id = plugin_data['id']
            if plugin_id in self.installed_plugins_map:
                if self.installed_plugins_map[plugin_id] < plugin_data['version']:
                    widget.set_status('update_available')
                else:
                    widget.set_status('installed')
            else:
                widget.set_status('not_installed')

            widget.install_button.clicked.connect(lambda checked=False, p=plugin_data: self.install_plugin(p))

            item.setSizeHint(widget.sizeHint())
            self.plugin_list.addItem(item)
            self.plugin_list.setItemWidget(item, widget)

    def filter_plugins(self):
        search_text = self.search_box.text().lower()
        for i in range(self.plugin_list.count()):
            item = self.plugin_list.item(i)
            widget = self.plugin_list.itemWidget(item)
            plugin_data = widget.plugin_data

            text_match = (
                    not search_text or
                    search_text in plugin_data['name'].lower() or
                    search_text in plugin_data['author'].lower() or
                    search_text in plugin_data['description'].lower()
            )

            plugin_tags = set(plugin_data.get('tags', []))
            tag_match = (
                    not self.active_tags or
                    self.active_tags.issubset(plugin_tags)
            )

            item.setHidden(not (text_match and tag_match))

    def update_details_panel(self, current_item, previous_item):
        if not current_item:
            self.detail_name.setText("<h2>" + _("Select a plugin") + "</h2>")
            self.detail_author_version.clear()
            self.detail_compat.clear()
            self.detail_links.clear()
            self.detail_desc.clear()
            self.detail_install_button.hide()
            return

        self.detail_install_button.show()
        widget = self.plugin_list.itemWidget(current_item)
        plugin_data = widget.plugin_data

        self.detail_name.setText(f"<h2>{plugin_data['name']}</h2>")
        self.detail_author_version.setText(
            f"{_('by')} {plugin_data['author']} | {_('Version')}: {plugin_data['version']}")

        if APP_VERSION.startswith(plugin_data['compatible_app_version']):
            self.detail_compat.setText(f"<b style='color:green;'>{_('Compatible')}</b> {_('with your app version.')}")
        else:
            self.detail_compat.setText(
                f"<b style='color:orange;'>{_('Incompatible')}</b> {_('Requires v{req}').format(req=plugin_data['compatible_app_version'])}")

        links = []
        if 'homepage_url' in plugin_data:
            links.append(f"<a href='{plugin_data['homepage_url']}'>{_('Homepage')}</a>")
        if 'issue_tracker_url' in plugin_data:
            links.append(f"<a href='{plugin_data['issue_tracker_url']}'>{_('Report Issue')}</a>")
        self.detail_links.setText(" | ".join(links))

        self.detail_desc.setMarkdown(plugin_data.get('description_long_md', plugin_data['description']))
        try:
            self.detail_install_button.clicked.disconnect()
        except RuntimeError:
            pass
        self.detail_install_button.clicked.connect(lambda: self.install_plugin(plugin_data))
        item_widget = self.plugin_list.itemWidget(current_item)
        status_property = item_widget.install_button.property("status")
        text = item_widget.install_button.text()
        is_enabled = item_widget.install_button.isEnabled()
        self.detail_install_button.setText(text)
        self.detail_install_button.setEnabled(is_enabled)
        self.detail_install_button.setProperty("status", status_property)
        self.detail_install_button.style().unpolish(self.detail_install_button)
        self.detail_install_button.style().polish(self.detail_install_button)

    def on_install_button_clicked(self):
        pass

    def install_plugin(self, plugin_data):
        self.status_label.setText(_("Downloading {plugin_name}...").format(plugin_name=plugin_data['name']))
        self.temp_dir_for_download = tempfile.TemporaryDirectory()
        self.download_thread = DownloadPluginThread(plugin_data['download_url'], self.temp_dir_for_download.name)
        self.download_thread.finished.connect(lambda path, err: self.on_download_finished(path, err, plugin_data))
        self.download_thread.start()

    def on_download_finished(self, temp_filepath, error_message, plugin_data):
        if error_message:
            self.status_label.setText(_("Download failed: {error}").format(error=error_message))
            QMessageBox.critical(self, _("Download Error"), error_message)
            if self.temp_dir_for_download:
                self.temp_dir_for_download.cleanup()
            return
        self.status_label.setText(_("Installing {plugin_name}...").format(plugin_name=plugin_data['name']))
        installed_id, install_error = self.manager.install_plugin_from_zip(temp_filepath)
        if self.temp_dir_for_download:
            self.temp_dir_for_download.cleanup()

        if install_error:
            self.status_label.setText(_("Installation failed: {error}").format(error=install_error))
            QMessageBox.critical(self, _("Installation Error"), install_error)
        else:
            self.status_label.setText(
                _("Successfully installed {plugin_name}.").format(plugin_name=plugin_data['name']))
            QMessageBox.information(self, _("Success"),
                                    _("Plugin installed successfully. Please restart the application to take effect."))
            self.refresh_installed_plugins_map()
            self.populate_plugin_list()
            self.update_details_panel(self.plugin_list.currentItem(), None)

    def closeEvent(self, event):
        if hasattr(self, 'fetch_thread') and self.fetch_thread.isRunning():
            self.fetch_thread.terminate()
        if hasattr(self, 'download_thread') and self.download_thread.isRunning():
            self.download_thread.terminate()
        if self.temp_dir_for_download:
            self.temp_dir_for_download.cleanup()
        super().closeEvent(event)