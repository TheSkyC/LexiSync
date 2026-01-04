# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTreeView, QFileSystemModel,
                               QMenu, QToolBar, QLineEdit, QCheckBox, QMessageBox,
                               QAbstractItemView, QApplication, QHeaderView,
                               QHBoxLayout, QWidgetAction, QSizePolicy, QProgressBar)
from PySide6.QtCore import (Qt, QDir, QModelIndex, Signal, QUrl, QSortFilterProxyModel,
                            QSize, QTimer)
from PySide6.QtGui import QAction, QDesktopServices, QIcon
import os
from pathlib import Path
from collections import deque
from utils.localization import _
from utils.path_utils import get_resource_path
import logging
logger = logging.getLogger(__name__)

class CustomTreeView(QTreeView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._logger = logging.getLogger(__name__)
        self._prevent_horizontal_scroll = True

    def scrollTo(self, index, hint=QAbstractItemView.ScrollHint.EnsureVisible):
        try:
            if not index.isValid():
                return
            if self._prevent_horizontal_scroll:
                horizontal_scrollbar = self.horizontalScrollBar()
                current_horizontal_value = horizontal_scrollbar.value() if horizontal_scrollbar else 0
                super().scrollTo(index, hint)
                if horizontal_scrollbar:
                    horizontal_scrollbar.setValue(current_horizontal_value)
            else:
                super().scrollTo(index, hint)

        except Exception as e:
            self._logger.error(f"Error in custom scrollTo: {e}")
            try:
                super().scrollTo(index, hint)
            except Exception as fallback_error:
                self._logger.error(f"Error in fallback scrollTo: {fallback_error}")

    def setPreventHorizontalScroll(self, prevent):
        self._prevent_horizontal_scroll = prevent

class FileFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._show_all_types = False
        self.project_file_patterns = []
        self._project_mode_enabled = False
        self._project_source_paths = set()
        self._project_source_parent_dirs = set()

    def setProjectFilePatterns(self, patterns):
        try:
            if not isinstance(patterns, (list, tuple)):
                logger.warning("Invalid patterns type, expected list or tuple")
                patterns = []

            self.project_file_patterns = list(patterns) if patterns else []
            self.invalidateFilter()
            logger.debug(f"Updated file patterns: {self.project_file_patterns}")
        except Exception as e:
            logger.error(f"Error setting project file patterns: {e}")

    def setShowAllTypes(self, show_all):
        try:
            show_all = bool(show_all)
            if self._show_all_types != show_all:
                self._show_all_types = show_all
                self.invalidateFilter()
                logger.debug(f"Show all types set to: {show_all}")
        except Exception as e:
            logger.error(f"Error setting show all types: {e}")

    def setProjectMode(self, enabled: bool, source_paths: list = None):
        self._project_mode_enabled = enabled
        if enabled and source_paths:
            self._project_source_paths = {os.path.normpath(p) for p in source_paths}
            self._project_source_parent_dirs = {str(Path(p).parent) for p in self._project_source_paths}
        else:
            self._project_source_paths = set()
            self._project_source_parent_dirs = set()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        try:
            source_index = self.sourceModel().index(source_row, 0, source_parent)
            if not source_index.isValid():
                return False

            file_info = self.sourceModel().fileInfo(source_index)

            if self._project_mode_enabled:
                current_path = os.path.normpath(file_info.absoluteFilePath())

                if current_path in self._project_source_paths:
                    return True

                if file_info.isDir():
                    current_drive = os.path.splitdrive(current_path)[0]
                    for parent_dir in self._project_source_parent_dirs:
                        parent_drive = os.path.splitdrive(parent_dir)[0]
                        if current_drive.lower() == parent_drive.lower():
                            if os.path.commonpath([current_path, parent_dir]) == current_path:
                                return True

                return False

            if file_info.isDir():
                return True

            if self._show_all_types:
                return True

            if not self.project_file_patterns:
                return True

            from fnmatch import fnmatch
            file_name = file_info.fileName()
            for pattern in self.project_file_patterns:
                if fnmatch(file_name, pattern):
                    return True
            return False
        except Exception as e:
            logger.error(f"Error in filterAcceptsRow: {e}")
            return True


class FileExplorerPanel(QWidget):
    file_double_clicked = Signal(str)
    error_occurred = Signal(str, str)

    def __init__(self, parent, app_instance):
        super().__init__(parent)
        self.app = app_instance

        self._initialize_navigation_history()
        self._initialize_models()
        self._setup_ui_safely()
        self._setup_connections_safely()

        self._apply_initial_settings()

    def _initialize_navigation_history(self):
        try:
            self.history_stack = deque(maxlen=50)
            self.forward_stack = deque(maxlen=50)
            self.home_path = None
            self._is_navigating = False
        except Exception as e:
            logger.error(f"Error initializing navigation history: {e}")
            self.history_stack = deque()
            self.forward_stack = deque()
            self.home_path = None
            self._is_navigating = False

    def _initialize_models(self):
        try:
            self.source_model = QFileSystemModel()
            self.source_model.setRootPath(QDir.rootPath())
            self.source_model.setReadOnly(False)
            self.source_model.setFilter(QDir.AllDirs | QDir.Files | QDir.NoDotAndDotDot)

            self.proxy_model = FileFilterProxyModel(self)
            self.proxy_model.setSourceModel(self.source_model)
        except Exception as e:
            logger.error(f"Error initializing models: {e}")
            self._show_error(_("Initialization Error"), _("Failed to initialize file system models."))

    def _setup_ui_safely(self):
        try:
            self.setup_ui()
        except Exception as e:
            logger.error(f"Error setting up UI: {e}")
            self._show_error(_("UI Setup Error"), _("Failed to initialize user interface."))

    def _setup_connections_safely(self):
        try:
            self.setup_connections()
        except Exception as e:
            logger.error(f"Error setting up connections: {e}")
            self._show_error(_("Connection Error"), _("Failed to setup signal connections."))

    def _apply_initial_settings(self):
        try:
            if hasattr(self, 'show_all_checkbox'):
                self.toggle_show_all(self.show_all_checkbox.checkState())
            self._update_nav_buttons_state()
        except Exception as e:
            logger.error(f"Error applying initial settings: {e}")

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._create_navigation_toolbar()
        layout.addWidget(self.nav_toolbar)

        self._create_tree_view()
        layout.addWidget(self.tree_view)

    def _create_navigation_toolbar(self):
        try:
            self.nav_toolbar = QToolBar()
            self.nav_toolbar.setIconSize(QSize(16, 16))

            self._create_navigation_actions()

            spacer = QWidget()
            spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            self.nav_toolbar.addWidget(spacer)

            self._create_filter_menu()

        except Exception as e:
            logger.error(f"Error creating navigation toolbar: {e}")
            self.nav_toolbar = QToolBar()

    def _create_navigation_actions(self):
        action_configs = [
            ("back_action", "arrow-left.svg", _("Back")),
            ("forward_action", "arrow-right.svg", _("Forward")),
            ("up_action", "arrow-up.svg", _("Up")),
            ("refresh_action", "refresh.svg", _("Refresh")),
            ("home_action", "home.svg", _("Home"))
        ]

        for attr_name, icon_file, text in action_configs:
            try:
                icon_path = get_resource_path(f"icons/{icon_file}")
                if os.path.exists(icon_path):
                    icon = QIcon(icon_path)
                else:
                    icon = QIcon()
                    logger.warning(f"Icon not found: {icon_path}")

                action = QAction(icon, text, self)
                setattr(self, attr_name, action)
                self.nav_toolbar.addAction(action)
            except Exception as e:
                logger.error(f"Error creating action {attr_name}: {e}")
                action = QAction(text, self)
                setattr(self, attr_name, action)
                self.nav_toolbar.addAction(action)

    def _create_filter_menu(self):
        try:
            filter_icon_path = get_resource_path("icons/filter.svg")
            filter_icon = QIcon(filter_icon_path) if os.path.exists(filter_icon_path) else QIcon()

            self.filter_settings_action = QAction(filter_icon, _("Filter Settings"), self)
            self.nav_toolbar.addAction(self.filter_settings_action)
            self.filter_menu = QMenu(self)

            self._create_search_widget()

            self._create_show_all_widget()

        except Exception as e:
            logger.error(f"Error creating filter menu: {e}")

    def _create_search_widget(self):
        try:
            search_widget = QWidget()
            search_layout = QHBoxLayout(search_widget)
            search_layout.setContentsMargins(10, 5, 10, 5)
            self.filter_edit = QLineEdit()
            self.filter_edit.setPlaceholderText(_("Filter files..."))
            search_layout.addWidget(self.filter_edit)

            search_action = QWidgetAction(self.filter_menu)
            search_action.setDefaultWidget(search_widget)
            self.filter_menu.addAction(search_action)
            self.filter_menu.addSeparator()
        except Exception as e:
            logger.error(f"Error creating search widget: {e}")

    def _create_show_all_widget(self):
        try:
            filter_options_widget = QWidget()
            filter_options_layout = QVBoxLayout(filter_options_widget)
            filter_options_layout.setContentsMargins(10, 5, 10, 5)

            self.project_mode_checkbox = QCheckBox(_("Project Mode"))
            self.project_mode_checkbox.setEnabled(False)
            filter_options_layout.addWidget(self.project_mode_checkbox)

            self.show_all_checkbox = QCheckBox(_("Show All Files"))
            filter_options_layout.addWidget(self.show_all_checkbox)

            filter_action = QWidgetAction(self.filter_menu)
            filter_action.setDefaultWidget(filter_options_widget)
            self.filter_menu.addAction(filter_action)
        except Exception as e:
            logger.error(f"Error creating show all widget: {e}")

    def _create_tree_view(self):
        try:
            self.tree_view = CustomTreeView()
            self.tree_view.setModel(self.proxy_model)
            self.tree_view.setContextMenuPolicy(Qt.CustomContextMenu)
            self.tree_view.setSelectionMode(QTreeView.SelectionMode.ExtendedSelection)
            self.tree_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

            self.tree_view.setStyleSheet("""
                QTreeView {
                    border: none;
                    background-color: #FFFFFF;
                    alternate-background-color: #F8F9FA;
                    outline: 0;
                }
                QTreeView::item { 
                    padding: 4px; 
                    border-radius: 3px; 
                    min-height: 20px;
                }
                QTreeView::item:selected:active { 
                    background-color: #D4E6F1; 
                    color: black; 
                }
                QTreeView::item:selected:!active { 
                    background-color: #EAF2F8; 
                    color: black; 
                }
                QTreeView::item:hover:!selected { 
                    background-color: #F5F5F5; 
                }
            """)
            self._configure_tree_view_columns()

        except Exception as e:
            logger.error(f"Error creating tree view: {e}")
            self.tree_view = QTreeView()

    def _configure_tree_view_columns(self):
        try:
            for i in range(1, self.source_model.columnCount()):
                self.tree_view.hideColumn(i)
            header = self.tree_view.header()
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            self.tree_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self.tree_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            header.setMinimumSectionSize(150)
            header.setStretchLastSection(False)
            self.tree_view.setHeaderHidden(True)

        except Exception as e:
            logger.error(f"Error configuring tree view columns: {e}")

    def setup_connections(self):
        connection_configs = [
            (self.tree_view.doubleClicked, self.on_double_clicked),
            (self.tree_view.customContextMenuRequested, self.show_context_menu),
            (self.filter_settings_action.triggered, self.show_filter_menu),
            (self.back_action.triggered, self.go_back),
            (self.forward_action.triggered, self.go_forward),
            (self.up_action.triggered, self.go_up),
            (self.refresh_action.triggered, self.refresh),
            (self.home_action.triggered, self.go_home)
        ]

        for signal, slot in connection_configs:
            try:
                signal.connect(slot)
            except Exception as e:
                logger.error(f"Error connecting signal to slot {slot.__name__}: {e}")

        try:
            if hasattr(self, 'filter_edit'):
                self.filter_edit.textChanged.connect(self.filter_changed)
            if hasattr(self, 'project_mode_checkbox'):
                self.project_mode_checkbox.stateChanged.connect(self.toggle_project_mode)
            if hasattr(self, 'show_all_checkbox'):
                self.show_all_checkbox.stateChanged.connect(self.toggle_show_all)
        except Exception as e:
            logger.error(f"Error connecting filter signals: {e}")

    def _update_nav_buttons_state(self):
        try:
            if hasattr(self, 'back_action'):
                self.back_action.setEnabled(len(self.history_stack) > 0)
            if hasattr(self, 'forward_action'):
                self.forward_action.setEnabled(len(self.forward_stack) > 0)

            current_path = self.source_model.rootPath()
            is_root = QDir(current_path).isRoot() if current_path else True

            if hasattr(self, 'up_action'):
                self.up_action.setEnabled(not is_root)
            if hasattr(self, 'home_action'):
                self.home_action.setEnabled(self.home_path is not None)

        except Exception as e:
            logger.error(f"Error updating navigation button states: {e}")

    def set_root_path(self, path, is_navigation_action=False):
        try:
            if not path:
                logger.warning("Empty path provided to set_root_path")
                return False

            try:
                normalized_path = os.path.normpath(str(path))
                if not os.path.exists(normalized_path):
                    self._show_error(_("Path Error"), _("Path does not exist: {path}").format(path=path))
                    return False

                if not os.path.isdir(normalized_path):
                    self._show_error(_("Path Error"), _("Path is not a directory: {path}").format(path=path))
                    return False

            except Exception as e:
                logger.error(f"Error validating path {path}: {e}")
                self._show_error(_("Path Error"), _("Invalid path: {path}").format(path=path))
                return False

            current_path = self.source_model.rootPath()
            if normalized_path == os.path.normpath(current_path):
                return True

            if not is_navigation_action and current_path and current_path != QDir.rootPath():
                try:
                    self.history_stack.append(current_path)
                    self.forward_stack.clear()
                except Exception as e:
                    logger.error(f"Error updating navigation history: {e}")

            if self.home_path is None:
                self.home_path = normalized_path

            self._is_navigating = True
            try:
                root_index = self.source_model.setRootPath(normalized_path)
                if root_index.isValid():
                    proxy_root_index = self.proxy_model.mapFromSource(root_index)
                    self.tree_view.setRootIndex(proxy_root_index)
                else:
                    logger.warning(f"Invalid root index for path: {normalized_path}")
                    return False

            except Exception as e:
                logger.error(f"Error setting model root path: {e}")
                self._show_error(_("Navigation Error"), _("Failed to navigate to: {path}").format(path=path))
                return False
            finally:
                self._is_navigating = False

            try:
                if hasattr(self.app, 'config') and hasattr(self.app, 'save_config'):
                    self.app.config['last_file_explorer_path'] = normalized_path
            except Exception as e:
                logger.error(f"Error saving configuration: {e}")

            self._update_nav_buttons_state()
            logger.debug(f"Successfully navigated to: {normalized_path}")
            return True

        except Exception as e:
            logger.error(f"Unexpected error in set_root_path: {e}")
            self._show_error(_("Navigation Error"), _("Unexpected error occurred while navigating."))
            return False

    def go_back(self):
        try:
            if not self.history_stack:
                return

            current_path = self.source_model.rootPath()
            if current_path:
                self.forward_stack.append(current_path)

            path_to_go = self.history_stack.pop()
            self.set_root_path(path_to_go, is_navigation_action=True)

        except Exception as e:
            logger.error(f"Error in go_back: {e}")
            self._show_error(_("Navigation Error"), _("Failed to navigate back."))

    def go_forward(self):
        try:
            if not self.forward_stack:
                return

            current_path = self.source_model.rootPath()
            if current_path:
                self.history_stack.append(current_path)

            path_to_go = self.forward_stack.pop()
            self.set_root_path(path_to_go, is_navigation_action=True)

        except Exception as e:
            logger.error(f"Error in go_forward: {e}")
            self._show_error(_("Navigation Error"), _("Failed to navigate forward."))

    def go_up(self):
        try:
            current_path = self.source_model.rootPath()
            if not current_path:
                return

            parent_path = os.path.dirname(current_path)
            if parent_path and parent_path != current_path:
                self.set_root_path(parent_path)
            else:
                logger.debug("Already at root directory")

        except Exception as e:
            logger.error(f"Error in go_up: {e}")
            self._show_error(_("Navigation Error"), _("Failed to navigate to parent directory."))

    def refresh(self):
        try:
            current_path = self.source_model.rootPath()
            if not current_path:
                return

            self._is_navigating = True
            try:
                self.source_model.setRootPath("")
                root_index = self.source_model.setRootPath(current_path)
                if root_index.isValid():
                    proxy_root_index = self.proxy_model.mapFromSource(root_index)
                    self.tree_view.setRootIndex(proxy_root_index)

                    if hasattr(self.app, 'update_statusbar'):
                        self.app.update_statusbar(_("File explorer refreshed."))
                else:
                    logger.warning("Invalid root index during refresh")

            finally:
                self._is_navigating = False

        except Exception as e:
            logger.error(f"Error in refresh: {e}")
            self._show_error(_("Refresh Error"), _("Failed to refresh directory."))

    def go_home(self):
        try:
            if not self.home_path:
                logger.warning("Home path not set")
                return

            if not os.path.isdir(self.home_path):
                logger.warning(f"Home path no longer exists: {self.home_path}")
                self._show_error(_("Navigation Error"), _("Home directory no longer exists."))
                return

            self.set_root_path(self.home_path)

        except Exception as e:
            logger.error(f"Error in go_home: {e}")
            self._show_error(_("Navigation Error"), _("Failed to navigate to home directory."))

    def select_file(self, path):
        try:
            if not path or not self.source_model.rootPath():
                return False

            if not os.path.exists(path):
                logger.warning(f"File does not exist: {path}")
                return False

            source_index = self.source_model.index(path)
            if not source_index.isValid():
                logger.warning(f"Invalid source index for path: {path}")
                return False

            proxy_index = self.proxy_model.mapFromSource(source_index)
            if not proxy_index.isValid():
                logger.warning(f"Invalid proxy index for path: {path}")
                return False

            self.tree_view.setCurrentIndex(proxy_index)
            parent_index = proxy_index.parent()
            while parent_index.isValid():
                self.tree_view.expand(parent_index)
                parent_index = parent_index.parent()

            self.tree_view.scrollTo(proxy_index, QTreeView.ScrollHint.PositionAtCenter)
            return True

        except Exception as e:
            logger.error(f"Error in select_file: {e}")
            return False

    def on_double_clicked(self, proxy_index: QModelIndex):
        try:
            if not proxy_index.isValid():
                return

            source_index = self.proxy_model.mapToSource(proxy_index)
            if not source_index.isValid():
                return

            file_path = self.source_model.filePath(source_index)
            if not file_path:
                return

            if self.source_model.isDir(source_index):
                self.set_root_path(file_path)
            else:
                self.file_double_clicked.emit(file_path)

        except Exception as e:
            logger.error(f"Error in on_double_clicked: {e}")
            self._show_error(_("File Access Error"), _("Failed to open selected item."))

    def _update_file_patterns(self):
        try:
            base_patterns = ["*.ow", "*.txt", "*.po", "*.pot", "*.owproj"]
            plugin_patterns = []

            if hasattr(self.app, 'plugin_manager'):
                try:
                    plugin_patterns = self.app.plugin_manager.get_all_supported_file_patterns()
                    if not isinstance(plugin_patterns, (list, tuple)):
                        plugin_patterns = []
                except Exception as e:
                    logger.error(f"Error getting plugin file patterns: {e}")
                    plugin_patterns = []

            all_patterns = list(set(base_patterns + plugin_patterns))
            self.proxy_model.setProjectFilePatterns(all_patterns)

        except Exception as e:
            logger.error(f"Error updating file patterns: {e}")

    def filter_changed(self, text):
        try:
            filter_text = str(text).strip()
            if filter_text:
                self.source_model.setNameFilters([f"*{filter_text}*"])
            else:
                self.source_model.setNameFilters([])
            self.source_model.setNameFilterDisables(False)

        except Exception as e:
            logger.error(f"Error in filter_changed: {e}")

    def show_filter_menu(self):
        try:
            button = self.nav_toolbar.widgetForAction(self.filter_settings_action)
            if button:
                button_pos = button.mapToGlobal(button.rect().bottomLeft())
                self.filter_menu.exec(button_pos)
            else:
                from PySide6.QtGui import QCursor
                self.filter_menu.exec(QCursor.pos())

        except Exception as e:
            logger.error(f"Error showing filter menu: {e}")

    def enter_project_mode(self, source_files_info):
        self.project_mode_checkbox.setEnabled(True)
        self.project_mode_checkbox.setChecked(True)

        project_root = self.app.current_project_path
        abs_source_paths = [os.path.join(project_root, f['project_path']) for f in source_files_info]

        self.proxy_model.setProjectMode(True, abs_source_paths)

        source_dir_path = os.path.join(project_root, "source")
        if os.path.isdir(source_dir_path):
            self.set_root_path(source_dir_path)
            QTimer.singleShot(100, lambda: self.tree_view.expandAll())
        else:
            self.set_root_path(project_root)

    def exit_project_mode(self):
        self.project_mode_checkbox.setChecked(False)
        self.project_mode_checkbox.setEnabled(False)
        self.proxy_model.setProjectMode(False)
        last_path = self.app.config.get('last_file_explorer_path', QDir.homePath())
        if self.app.current_project_path and last_path.startswith(self.app.current_project_path):
             last_path = QDir.homePath()
        self.set_root_path(last_path)

    def toggle_project_mode(self, state):
        is_checked = (state == Qt.CheckState.Checked.value)
        if is_checked:
            source_files_info = self.app.project_config.get('source_files', [])
            project_root = self.app.current_project_path
            abs_source_paths = [os.path.join(project_root, f['project_path']) for f in source_files_info]
            self.proxy_model.setProjectMode(True, abs_source_paths)
        else:
            self.proxy_model.setProjectMode(False)

    def toggle_show_all(self, state):
        try:
            is_checked = (state == Qt.CheckState.Checked.value)
            current_filter = QDir.AllDirs | QDir.Files | QDir.NoDotAndDotDot

            if is_checked:
                current_filter |= QDir.Hidden

            self.source_model.setFilter(current_filter)

            if not is_checked:
                self._update_file_patterns()
            self.proxy_model.setShowAllTypes(is_checked)

        except Exception as e:
            logger.error(f"Error in toggle_show_all: {e}")

    def show_context_menu(self, pos):
        try:
            proxy_index_at_pos = self.tree_view.indexAt(pos)
            proxy_indexes = self.tree_view.selectedIndexes()

            if not proxy_indexes:
                return
            selected_paths = self._get_selected_paths(proxy_indexes)
            if not selected_paths:
                return

            source_index_at_pos = self.proxy_model.mapToSource(proxy_index_at_pos)
            path_at_pos = self.source_model.filePath(source_index_at_pos)

            menu = QMenu()
            self._populate_context_menu(menu, selected_paths, path_at_pos, proxy_index_at_pos, source_index_at_pos)
            menu.exec(self.tree_view.viewport().mapToGlobal(pos))

        except Exception as e:
            logger.error(f"Error showing context menu: {e}")

    def _get_selected_paths(self, proxy_indexes):
        selected_paths = []
        try:
            for proxy_idx in proxy_indexes:
                if proxy_idx.column() == 0:
                    source_idx = self.proxy_model.mapToSource(proxy_idx)
                    if source_idx.isValid():
                        path = self.source_model.filePath(source_idx)
                        if path and os.path.exists(path):
                            selected_paths.append(path)
        except Exception as e:
            logger.error(f"Error getting selected paths: {e}")
        return selected_paths

    def _populate_context_menu(self, menu, selected_paths, path_at_pos, proxy_index_at_pos, source_index_at_pos):
        try:
            # Open action (single selection, file only)
            if len(selected_paths) == 1:
                path = selected_paths[0]
                source_index = self.source_model.index(path)
                if source_index.isValid() and not self.source_model.isDir(source_index):
                    open_action = menu.addAction(_("Open"))
                    open_action.triggered.connect(lambda checked=False, p=path: self.file_double_clicked.emit(p))

            # Rename action (single selection)
            if len(selected_paths) == 1:
                rename_action = menu.addAction(_("Rename"))
                rename_action.triggered.connect(lambda checked=False, idx=proxy_index_at_pos: self._safe_edit_item(idx))

            # Set as root (directory only)
            if source_index_at_pos.isValid() and self.source_model.isDir(source_index_at_pos):
                menu.addSeparator()
                set_as_root_action = menu.addAction(_("Set as Root"))
                set_as_root_action.triggered.connect(lambda checked=False, p=path_at_pos: self.set_root_path(p))

            # Reveal in file explorer
            first_path = selected_paths[0]
            reveal_action = menu.addAction(_("Reveal in File Explorer"))
            reveal_action.triggered.connect(lambda checked=False, p=first_path: self._reveal_in_explorer(p))

            # Delete action
            delete_action = menu.addAction(_("Delete"))
            delete_action.triggered.connect(lambda checked=False, paths=selected_paths: self.delete_items(paths))

            menu.addSeparator()

            # Copy actions
            self._add_copy_actions(menu, selected_paths)

            # Plugin actions
            self._add_plugin_actions(menu, selected_paths)

        except Exception as e:
            logger.error(f"Error populating context menu: {e}")

    def _safe_edit_item(self, proxy_index):
        try:
            if proxy_index.isValid():
                self.tree_view.edit(proxy_index)
        except Exception as e:
            logger.error(f"Error editing item: {e}")
            self._show_error(_("Edit Error"), _("Failed to start editing the item."))

    def _reveal_in_explorer(self, path):
        try:
            if not path or not os.path.exists(path):
                self._show_error(_("File Error"), _("File or directory does not exist."))
                return

            if os.path.isfile(path):
                directory = os.path.dirname(path)
            else:
                directory = path

            url = QUrl.fromLocalFile(directory)
            if not QDesktopServices.openUrl(url):
                self._show_error(_("System Error"), _("Failed to open file explorer."))

        except Exception as e:
            logger.error(f"Error revealing in explorer: {e}")
            self._show_error(_("System Error"), _("Failed to reveal item in file explorer."))

    def _add_copy_actions(self, menu, selected_paths):
        try:
            copy_path_action = menu.addAction(_("Copy Full Path"))
            copy_path_action.triggered.connect(
                lambda checked=False, paths=selected_paths: self._copy_to_clipboard(
                    '\n'.join(paths),
                    _("Copied {count} full path(s) to clipboard.").format(count=len(paths))
                )
            )
            selected_names = [os.path.basename(p) for p in selected_paths]
            copy_name_action = menu.addAction(_("Copy File Name"))
            copy_name_action.triggered.connect(
                lambda checked=False, names=selected_names: self._copy_to_clipboard(
                    '\n'.join(names),
                    _("Copied {count} file name(s) to clipboard.").format(count=len(names))
                )
            )
        except Exception as e:
            logger.error(f"Error adding copy actions: {e}")

    def _add_plugin_actions(self, menu, selected_paths):
        try:
            if hasattr(self.app, 'plugin_manager'):
                try:
                    plugin_menu_items = self.app.plugin_manager.run_hook('on_file_tree_context_menu', selected_paths)
                    if plugin_menu_items:
                        menu.addSeparator()
                        self.app.plugin_manager._create_menu_from_structure(menu, plugin_menu_items)
                except Exception as e:
                    logger.error(f"Error adding plugin actions: {e}")
        except Exception as e:
            logger.error(f"Error in _add_plugin_actions: {e}")

    def _copy_to_clipboard(self, text, status_message):
        try:
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(text)
                if hasattr(self.app, 'update_statusbar'):
                    self.app.update_statusbar(status_message)
            else:
                self._show_error(_("Clipboard Error"), _("Failed to access system clipboard."))
        except Exception as e:
            logger.error(f"Error copying to clipboard: {e}")
            self._show_error(_("Clipboard Error"), _("Failed to copy to clipboard."))

    def delete_items(self, paths):
        try:
            if not paths:
                return
            valid_paths = []
            for path in paths:
                if os.path.exists(path):
                    valid_paths.append(path)
                else:
                    logger.warning(f"Path does not exist, skipping: {path}")

            if not valid_paths:
                self._show_error(_("Delete Error"), _("No valid items to delete."))
                return
            reply = QMessageBox.warning(
                self, _("Confirm Deletion"),
                _("Are you sure you want to permanently delete the following item(s)?\n\n- {items}").format(
                    items='\n- '.join(os.path.basename(p) for p in valid_paths)
                ),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )

            if reply != QMessageBox.Yes:
                return
            errors = []
            success_count = 0

            for path in valid_paths:
                try:
                    if os.path.isdir(path):
                        import shutil
                        shutil.rmtree(path)
                    else:
                        os.remove(path)
                    success_count += 1
                    logger.debug(f"Successfully deleted: {path}")
                except PermissionError:
                    error_msg = _("Permission denied: {path}").format(path=path)
                    errors.append(error_msg)
                    logger.error(f"Permission denied deleting {path}")
                except FileNotFoundError:
                    logger.warning(f"File not found during deletion: {path}")
                except Exception as e:
                    error_msg = _("Failed to delete {path}: {error}").format(path=path, error=str(e))
                    errors.append(error_msg)
                    logger.error(f"Error deleting {path}: {e}")

            if errors:
                error_text = "\n".join(errors)
                if success_count > 0:
                    message = _(
                        "Partially completed deletion. {success} item(s) deleted, but encountered errors:\n\n{errors}").format(
                        success=success_count, errors=error_text
                    )
                else:
                    message = _("Deletion failed with errors:\n\n{errors}").format(errors=error_text)
                self._show_error(_("Deletion Results"), message)
            else:
                if hasattr(self.app, 'update_statusbar'):
                    self.app.update_statusbar(_("Successfully deleted {count} item(s).").format(count=success_count))
            self.refresh()

        except Exception as e:
            logger.error(f"Unexpected error in delete_items: {e}")
            self._show_error(_("Delete Error"), _("An unexpected error occurred during deletion."))

    def update_ui_texts(self):
        try:
            if hasattr(self, 'filter_edit'):
                self.filter_edit.setPlaceholderText(_("Filter files..."))
            if hasattr(self, 'project_mode_checkbox'):
                self.project_mode_checkbox.setText(_("Project Mode"))
            if hasattr(self, 'show_all_checkbox'):
                self.show_all_checkbox.setText(_("Show All Files"))

            action_texts = {
                'back_action': _("Back"),
                'forward_action': _("Forward"),
                'up_action': _("Up"),
                'refresh_action': _("Refresh"),
                'home_action': _("Home"),
                'filter_settings_action': _("Filter Settings")
            }

            for action_name, text in action_texts.items():
                if hasattr(self, action_name):
                    getattr(self, action_name).setText(text)

        except Exception as e:
            logger.error(f"Error updating UI texts: {e}")

    def _show_error(self, title, message):
        try:
            logger.error(f"{title}: {message}")
            QMessageBox.critical(self, title, message)
            self.error_occurred.emit(title, message)

        except Exception as e:
            logger.critical(f"Failed to show error dialog: {e}")
            print(f"ERROR - {title}: {message}")

    def get_current_path(self):
        try:
            return self.source_model.rootPath() if self.source_model else None
        except Exception as e:
            logger.error(f"Error getting current path: {e}")
            return None

    def is_valid_state(self):
        try:
            return (hasattr(self, 'source_model') and
                    hasattr(self, 'proxy_model') and
                    hasattr(self, 'tree_view') and
                    self.source_model is not None and
                    self.proxy_model is not None and
                    self.tree_view is not None)
        except Exception as e:
            logger.error(f"Error checking widget state: {e}")
            return False

    def cleanup(self):
        try:
            if hasattr(self, 'tree_view') and self.tree_view:
                self.tree_view.doubleClicked.disconnect()
                self.tree_view.customContextMenuRequested.disconnect()

            if hasattr(self, 'proxy_model') and self.proxy_model:
                self.proxy_model.setSourceModel(None)

            if hasattr(self, 'source_model') and self.source_model:
                self.source_model = None

            logger.debug("File explorer panel cleaned up")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    def __del__(self):
        try:
            self.cleanup()
        except Exception as e:
            print(f"Error in FileExplorerPanel destructor: {e}")