# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, \
    QApplication, QMessageBox, QLabel
from PySide6.QtCore import Qt, Signal, QTimer, QEvent, QSize
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QIcon, QColor, QPalette
from utils.path_utils import get_resource_path
from utils.localization import _


class RecentFileWidget(QWidget):
    def __init__(self, filename, dirpath, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self._is_hovered = False
        self._is_pressed = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(2)

        self.filename_label = QLabel(filename)
        self.filename_label.setStyleSheet("font-weight: bold; background-color: transparent;")

        self.path_label = QLabel(dirpath)
        self.path_label.setStyleSheet("color: #777; background-color: transparent;")

        layout.addWidget(self.filename_label)
        layout.addWidget(self.path_label)

        self.setAutoFillBackground(True)
        self._update_style()

    def _update_style(self):
        palette = self.palette()
        if self._is_pressed:
            palette.setColor(self.backgroundRole(), QColor("#E0E0E0"))  # Darker grey
        elif self._is_hovered:
            palette.setColor(self.backgroundRole(), QColor("#F5F5F5"))  # Lighter grey
        else:
            palette.setColor(self.backgroundRole(), Qt.transparent)  # Default transparent
        self.setPalette(palette)

    def enterEvent(self, event):
        self._is_hovered = True
        self._update_style()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._is_hovered = False
        self._is_pressed = False
        self._update_style()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._is_pressed = True
            self._update_style()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._is_pressed = False
            self._update_style()
        super().mouseReleaseEvent(event)

class ActionButton(QWidget):
    clicked = Signal()

    def __init__(self, icon_path: str, title: str, subtitle: str, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(80)

        self._is_pressed = False
        self._is_hovered = False

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(15, 10, 15, 10)
        main_layout.setSpacing(15)

        self.icon_label = QLabel()
        if icon_path:
            self.icon_label.setPixmap(QIcon(icon_path).pixmap(QSize(32, 32)))
        main_layout.addWidget(self.icon_label)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        self.title_label = QLabel(f"<b>{title}</b>")
        self.title_label.setStyleSheet("font-size: 16px; background-color: transparent;")

        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setStyleSheet("color: #555; background-color: transparent;")
        self.subtitle_label.setWordWrap(True)

        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.subtitle_label)
        text_layout.addStretch()

        main_layout.addLayout(text_layout, 1)

        self.setStyleSheet("""
            QWidget {
                border-radius: 8px;
            }
        """)
        self.setAutoFillBackground(True)
        self._update_style()

    def _update_style(self):
        palette = self.palette()
        if self._is_pressed:
            palette.setColor(self.backgroundRole(), QColor("#E0E0E0"))  # Darker grey for pressed
        elif self._is_hovered:
            palette.setColor(self.backgroundRole(), QColor("#F0F0F0"))  # Lighter grey for hover
        else:
            palette.setColor(self.backgroundRole(), QColor("#F5F7FA"))  # Default background
        self.setPalette(palette)

    def event(self, event):
        if event.type() == QEvent.Enter:
            self._is_hovered = True
            self._update_style()
        elif event.type() == QEvent.Leave:
            self._is_hovered = False
            self._is_pressed = False
            self._update_style()
        return super().event(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._is_pressed = True
            self._update_style()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            was_pressed = self._is_pressed
            self._is_pressed = False
            self._update_style()
            if was_pressed and self.rect().contains(event.pos()):
                self.clicked.emit()
        super().mouseReleaseEvent(event)


class WelcomeScreen(QWidget):
    request_main_window = Signal(str, str)

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.main_window_instance = None
        self.is_closed_by_user = True
        self.is_prewarming = False
        self.is_loading = False
        self.is_closed = False
        self.pending_action = None

        self.setWindowTitle("LexiSync")
        self.resize(800, 550)
        self.setStyleSheet("background-color: #FFFFFF;")
        self.setAcceptDrops(True)
        top_level_layout = QVBoxLayout(self)
        top_level_layout.setContentsMargins(0, 0, 0, 0)
        top_level_layout.setSpacing(0)

        main_content_widget = QWidget()
        main_layout = QHBoxLayout(main_content_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- Left: Action Panel ---
        action_panel = QWidget()
        action_panel.setStyleSheet("background-color: #F5F7FA;")
        action_layout = QVBoxLayout(action_panel)
        action_layout.setContentsMargins(20, 20, 20, 20)
        action_layout.setSpacing(15)
        action_layout.setAlignment(Qt.AlignTop)

        self.quick_edit_button = ActionButton(
            get_resource_path("icons/file.svg"),
            _("Quick Edit File"),
            _("Open a single file for fast translation")
        )
        self.new_project_button = ActionButton(
            get_resource_path("icons/folder.svg"),
            _("New Project"),
            _("Create a structured project folder")
        )
        self.open_project_button = ActionButton(
            get_resource_path("icons/folder-open.svg"),
            _("Open Project"),
            _("Open an existing project folder")
        )
        self.market_button = ActionButton(
            get_resource_path("icons/package.svg"),
            _("Plugin Marketplace"),
            _("Discover and install plugins")
        )
        self.settings_button = ActionButton(
            get_resource_path("icons/settings.svg"),
            _("Settings"),
            _("Configure the application")
        )

        action_layout.addWidget(self.quick_edit_button)
        action_layout.addWidget(self.new_project_button)
        action_layout.addWidget(self.open_project_button)
        action_layout.addStretch(1)
        action_layout.addWidget(self.market_button)
        action_layout.addWidget(self.settings_button)

        main_layout.addWidget(action_panel, 1)

        # --- Right: Recent Files Panel ---
        recent_panel = QWidget()
        recent_layout = QVBoxLayout(recent_panel)
        recent_layout.setContentsMargins(20, 20, 20, 20)

        recent_title = QLabel(f"<b>{_('Recent Files')}</b>")
        recent_title.setStyleSheet("font-size: 18px; margin-bottom: 10px;")

        self.recent_files_list = QListWidget()
        self.recent_files_list.setStyleSheet("""
            QListWidget {
                border: none;
                background-color: transparent;
                outline: none;
            }
        """)
        self.recent_files_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.recent_files_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.populate_recent_files()

        recent_layout.addWidget(recent_title)
        recent_layout.addWidget(self.recent_files_list, 1)

        # --- Bottom: Status Label ---
        main_layout.addWidget(recent_panel, 2)

        # 创建状态栏容器
        status_widget = QWidget()
        status_layout = QHBoxLayout(status_widget)
        status_layout.setContentsMargins(12, 5, 12, 5)
        status_layout.setSpacing(8)

        # 状态指示器圆点
        self.status_icon = QLabel("●")
        self.status_icon.setStyleSheet("color: #F39C12; font-size: 12px;")  # 初始为黄色

        # 状态文本
        self.status_label = QLabel()
        self.status_label.setText(_("Initializing..."))
        self.status_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.status_label.setStyleSheet("color: #606266;")

        status_layout.addWidget(self.status_icon)
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()

        status_widget.setStyleSheet("""
            background-color: #F5F7FA;
        """)
        status_widget.setFixedHeight(28)

        top_level_layout.addWidget(main_content_widget, 1)
        top_level_layout.addWidget(status_widget)

        # --- Connect Signals ---
        self.quick_edit_button.clicked.connect(lambda: self.on_action_triggered("open_code_file_dialog"))
        self.new_project_button.clicked.connect(lambda: self.on_action_triggered("new_project"))
        self.open_project_button.clicked.connect(lambda: self.on_action_triggered("open_project_dialog"))
        self.market_button.clicked.connect(lambda: self.on_action_triggered("show_marketplace"))
        self.settings_button.clicked.connect(lambda: self.on_action_triggered("show_settings"))
        self.recent_files_list.itemClicked.connect(self.on_recent_file_selected)

        self.start_prewarming()

    def set_status(self, text, status_type="loading"):
        """设置状态文本和图标颜色"""
        self.status_label.setText(text)

        color_map = {
            "loading": "#F39C12",  # 黄色 - 加载中/预热中
            "ready": "#27AE60",  # 绿色 - 准备就绪
            "error": "#E74C3C"  # 红色 - 错误
        }

        color = color_map.get(status_type, "#F39C12")
        self.status_icon.setStyleSheet(f"color: {color}; font-size: 12px;")

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and all(url.isLocalFile() for url in urls):
                event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls and urls[0].isLocalFile():
            filepath = urls[0].toLocalFile()
            self.on_action_triggered("open_specific_file", path=filepath)
            event.acceptProposedAction()

    def start_prewarming(self):
        if self.is_prewarming:
            return
        self.is_prewarming = True
        QTimer.singleShot(150, self.prewarm_main_window)

    def prewarm_main_window(self):
        try:
            self.set_status(_("Loading core libraries..."), "loading")
            QApplication.processEvents()
            if self.is_closed: return
            from main_window import LexiSyncApp
            from utils.path_utils import get_plugin_libs_path
            import sys
            import logging
            logger = logging.getLogger(__name__)

            self.set_status(_("Setting up plugin environment..."), "loading")
            QApplication.processEvents()
            if self.is_closed: return
            plugin_libs_path = get_plugin_libs_path()
            if plugin_libs_path not in sys.path:
                sys.path.insert(0, plugin_libs_path)
                logger.info(f"Plugin library path added: {plugin_libs_path}")

            self.set_status(_("Initializing main window and plugins..."), "loading")
            QApplication.processEvents()
            if self.is_closed: return
            self.main_window_instance = LexiSyncApp(self.config)
            self.main_window_instance.hide()
            if self.is_closed:
                self.main_window_instance.close()
                self.main_window_instance = None
                return
            self.set_status(_("Ready"), "ready")
            QApplication.processEvents()
            if self.pending_action:
                action, path = self.pending_action
                self.pending_action = None
                self.execute_main_window_action(action, path)

        except Exception as e:
            logger.error(f"Failed to prewarm main window: {e}")
            QMessageBox.critical(self, "Error", f"Failed to initialize the main application:\n{str(e)}")
            self.set_status(_("Initialization Failed!"), "error")
        finally:
            self.is_prewarming = False

    def on_action_triggered(self, action, path=""):
        if self.is_loading:
            return
        if self.main_window_instance is None:
            self.pending_action = (action, path)
            self.show_loading_message()
            if path:
                self.set_status(_("Initializing to open {filename}...").format(filename=os.path.basename(path)),
                                "loading")
            else:
                self.set_status(_("Waiting for initialization to complete..."), "loading")
            return
        if self.main_window_instance is None:
            self.pending_action = (action, path)
            self.show_loading_message()
            self.set_status(_("Waiting for initialization to complete..."), "loading")
            return
        self.execute_main_window_action(action, path)

    def execute_main_window_action(self, action, path):

        if self.is_loading:
            return
        self.is_loading = True
        try:
            success = self.main_window_instance.execute_action(action, path)
            if success:
                self.is_closed_by_user = False
                self.main_window_instance.show()
                self.close()
            else:
                self.main_window_instance.hide()
                self.show()
                self.setDisabled(False)
                self.set_status(_("Ready"), "ready")
        finally:
            self.is_loading = False

    def show_loading_message(self):
        self.setDisabled(True)
        QTimer.singleShot(200, self.check_main_window_ready)

    def check_main_window_ready(self):
        if self.main_window_instance is not None and self.pending_action:
            action, path = self.pending_action
            self.pending_action = None
            self.setDisabled(False)
            self.execute_main_window_action(action, path)
        elif self.pending_action:
            QTimer.singleShot(200, self.check_main_window_ready)

    def populate_recent_files(self):
        self.recent_files_list.clear()
        recent_files = self.config.get("recent_files", [])
        if not recent_files:
            item = QListWidgetItem(_("No recent files"))
            item.setForeground(Qt.gray)
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            self.recent_files_list.addItem(item)
            return

        for path in recent_files:
            filename = os.path.basename(path)
            dirpath = os.path.dirname(path)

            item = QListWidgetItem()
            item.setData(Qt.UserRole, path)

            widget = RecentFileWidget(filename, dirpath)

            item.setSizeHint(QSize(self.recent_files_list.viewport().width(), widget.sizeHint().height()))
            self.recent_files_list.addItem(item)
            self.recent_files_list.setItemWidget(item, widget)

    def on_recent_file_selected(self, item):
        path = item.data(Qt.UserRole)
        if path:
            self.on_action_triggered("open_specific_project", path)

    def closeEvent(self, event):
        if self.is_closed_by_user:
            self.is_closed = True
            if self.main_window_instance:
                self.main_window_instance.close()
            if self.is_prewarming:
                QApplication.quit()
        super().closeEvent(event)