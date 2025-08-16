# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTreeView, QFileSystemModel,
                               QMenu, QToolBar, QLineEdit, QCheckBox, QMessageBox,
                               QAbstractItemView, QApplication, QHeaderView,
                               QHBoxLayout, QWidgetAction, QSizePolicy)
from PySide6.QtCore import Qt, QDir, QModelIndex, Signal, QUrl, QSortFilterProxyModel, QSize
from PySide6.QtGui import QAction, QDesktopServices, QIcon
import os
from collections import deque
from utils.localization import _
from utils.path_utils import get_resource_path


class FileFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._show_all_types = False
        self.project_file_patterns = []

    def setProjectFilePatterns(self, patterns):
        self.project_file_patterns = patterns
        self.invalidateFilter()

    def setShowAllTypes(self, show_all):
        if self._show_all_types != show_all:
            self._show_all_types = show_all
            self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        source_index = self.sourceModel().index(source_row, 0, source_parent)
        if not source_index.isValid():
            return False

        file_info = self.sourceModel().fileInfo(source_index)

        if file_info.isDir():
            return True

        if self._show_all_types:
            return True

        from fnmatch import fnmatch
        for pattern in self.project_file_patterns:
            if fnmatch(file_info.fileName(), pattern):
                return True
        return False


class FileExplorerPanel(QWidget):
    file_double_clicked = Signal(str)

    def __init__(self, parent, app_instance):
        super().__init__(parent)
        self.app = app_instance

        self.history_stack = deque(maxlen=50)
        self.forward_stack = deque(maxlen=50)
        self.home_path = None
        self._is_navigating = False

        self.source_model = QFileSystemModel()
        self.source_model.setRootPath(QDir.rootPath())
        self.source_model.setReadOnly(False)
        self.source_model.setFilter(QDir.AllDirs | QDir.Files | QDir.NoDotAndDotDot)

        self.proxy_model = FileFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.source_model)
        self._update_file_patterns()

        self.setup_ui()
        self.setup_connections()
        self.toggle_show_all(self.show_all_checkbox.checkState())
        self._update_nav_buttons_state()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.nav_toolbar = QToolBar()
        self.nav_toolbar.setIconSize(QSize(16, 16))

        self.back_action = QAction(QIcon(get_resource_path("icons/arrow-left.svg")), _("Back"), self)
        self.forward_action = QAction(QIcon(get_resource_path("icons/arrow-right.svg")), _("Forward"), self)
        self.up_action = QAction(QIcon(get_resource_path("icons/arrow-up.svg")), _("Up"), self)
        self.refresh_action = QAction(QIcon(get_resource_path("icons/refresh.svg")), _("Refresh"), self)
        self.home_action = QAction(QIcon(get_resource_path("icons/home.svg")), _("Home"), self)

        self.nav_toolbar.addAction(self.back_action)
        self.nav_toolbar.addAction(self.forward_action)
        self.nav_toolbar.addAction(self.up_action)
        self.nav_toolbar.addAction(self.refresh_action)
        self.nav_toolbar.addAction(self.home_action)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.nav_toolbar.addWidget(spacer)

        self.filter_settings_action = QAction(QIcon(get_resource_path("icons/filter.svg")), _("Filter Settings"), self)
        self.nav_toolbar.addAction(self.filter_settings_action)
        self.filter_menu = QMenu(self)

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

        show_all_widget = QWidget()
        show_all_layout = QHBoxLayout(show_all_widget)
        show_all_layout.setContentsMargins(10, 5, 10, 5)
        self.show_all_checkbox = QCheckBox(_("Show All Files"))
        show_all_layout.addWidget(self.show_all_checkbox)

        show_all_action = QWidgetAction(self.filter_menu)
        show_all_action.setDefaultWidget(show_all_widget)
        self.filter_menu.addAction(show_all_action)

        layout.addWidget(self.nav_toolbar)

        self.tree_view = QTreeView()
        self.tree_view.setModel(self.proxy_model)
        self.tree_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_view.setSelectionMode(QTreeView.SelectionMode.ExtendedSelection)
        self.tree_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tree_view.setStyleSheet("""
            QTreeView {
                border: none;
                background-color: #FFFFFF;
                alternate-background-color: #F8F9FA;
            }
            QTreeView::item { padding: 4px; border-radius: 3px; }
            QTreeView::item:selected:active { background-color: #D4E6F1; color: black; }
            QTreeView::item:selected:!active { background-color: #EAF2F8; color: black; }
            QTreeView::item:hover:!selected { background-color: #F5F5F5; }
        """)
        self.tree_view.setHeaderHidden(True)
        for i in range(1, self.source_model.columnCount()):
            self.tree_view.hideColumn(i)
        self.tree_view.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.tree_view)

    def setup_connections(self):
        self.tree_view.doubleClicked.connect(self.on_double_clicked)
        self.tree_view.customContextMenuRequested.connect(self.show_context_menu)

        self.filter_settings_action.triggered.connect(self.show_filter_menu)
        self.filter_edit.textChanged.connect(self.filter_changed)
        self.show_all_checkbox.stateChanged.connect(self.toggle_show_all)

        self.back_action.triggered.connect(self.go_back)
        self.forward_action.triggered.connect(self.go_forward)
        self.up_action.triggered.connect(self.go_up)
        self.refresh_action.triggered.connect(self.refresh)
        self.home_action.triggered.connect(self.go_home)

    def _update_nav_buttons_state(self):
        self.back_action.setEnabled(len(self.history_stack) > 0)
        self.forward_action.setEnabled(len(self.forward_stack) > 0)

        current_path = self.source_model.rootPath()
        is_root = QDir(current_path).isRoot()
        self.up_action.setEnabled(not is_root)

        self.home_action.setEnabled(self.home_path is not None)

    def set_root_path(self, path, is_navigation_action=False):
        if not path or not os.path.isdir(path):
            return

        current_path = self.source_model.rootPath()
        if os.path.normpath(path) == os.path.normpath(current_path):
            return

        if not is_navigation_action and current_path != QDir.rootPath():
            self.history_stack.append(current_path)
            self.forward_stack.clear()

        if self.home_path is None:
            self.home_path = path

        self._is_navigating = True
        root_index = self.source_model.setRootPath(path)
        self.tree_view.setRootIndex(self.proxy_model.mapFromSource(root_index))
        self._is_navigating = False

        self.app.config['last_file_explorer_path'] = path
        self.app.save_config()
        self._update_nav_buttons_state()

    def go_back(self):
        if self.history_stack:
            current_path = self.source_model.rootPath()
            self.forward_stack.append(current_path)
            path_to_go = self.history_stack.pop()
            self.set_root_path(path_to_go, is_navigation_action=True)

    def go_forward(self):
        if self.forward_stack:
            current_path = self.source_model.rootPath()
            self.history_stack.append(current_path)
            path_to_go = self.forward_stack.pop()
            self.set_root_path(path_to_go, is_navigation_action=True)

    def go_up(self):
        current_path = self.source_model.rootPath()
        parent_path = os.path.dirname(current_path)
        if parent_path and parent_path != current_path:
            self.set_root_path(parent_path)

    def refresh(self):
        current_path = self.source_model.rootPath()
        self._is_navigating = True
        root_index = self.source_model.setRootPath("")
        root_index = self.source_model.setRootPath(current_path)
        self.tree_view.setRootIndex(self.proxy_model.mapFromSource(root_index))
        self._is_navigating = False
        self.app.update_statusbar(_("File explorer refreshed."))

    def go_home(self):
        if self.home_path and os.path.isdir(self.home_path):
            self.set_root_path(self.home_path)

    def select_file(self, path):
        if not path or not self.source_model.rootPath():
            return
        source_index = self.source_model.index(path)
        if source_index.isValid():
            proxy_index = self.proxy_model.mapFromSource(source_index)
            if proxy_index.isValid():
                self.tree_view.setCurrentIndex(proxy_index)
                parent_index = proxy_index.parent()
                while parent_index.isValid():
                    self.tree_view.expand(parent_index)
                    parent_index = parent_index.parent()
                self.tree_view.scrollTo(proxy_index, QTreeView.ScrollHint.PositionAtCenter)

    def on_double_clicked(self, proxy_index: QModelIndex):
        source_index = self.proxy_model.mapToSource(proxy_index)
        file_path = self.source_model.filePath(source_index)
        if self.source_model.isDir(source_index):
            self.set_root_path(file_path)
        else:
            self.file_double_clicked.emit(file_path)

    def _update_file_patterns(self):
        base_patterns = [
            "*.ow", "*.txt", "*.po", "*.pot", "*.owproj"
        ]
        plugin_patterns = []
        if hasattr(self.app, 'plugin_manager'):
            plugin_patterns = self.app.plugin_manager.get_all_supported_file_patterns()
        all_patterns = list(set(base_patterns + plugin_patterns))
        self.proxy_model.setProjectFilePatterns(all_patterns)

    def filter_changed(self, text):
        self.source_model.setNameFilters([f"*{text}*"])
        self.source_model.setNameFilterDisables(False)

    def show_filter_menu(self):
        button = self.nav_toolbar.widgetForAction(self.filter_settings_action)

        if button:
            button_pos = button.mapToGlobal(button.rect().bottomLeft())
            self.filter_menu.exec(button_pos)
        else:
            from PySide6.QtGui import QCursor
            self.filter_menu.exec(QCursor.pos())

    def toggle_show_all(self, state):
        is_checked = (state == Qt.CheckState.Checked.value)
        current_filter = QDir.AllDirs | QDir.Files | QDir.NoDotAndDotDot
        if is_checked:
            current_filter |= QDir.Hidden
        self.source_model.setFilter(current_filter)

        if not is_checked:
            self._update_file_patterns()
        self.proxy_model.setShowAllTypes(is_checked)

    def show_context_menu(self, pos):
        proxy_index_at_pos = self.tree_view.indexAt(pos)
        proxy_indexes = self.tree_view.selectedIndexes()
        if not proxy_indexes:
            return

        source_index_at_pos = self.proxy_model.mapToSource(proxy_index_at_pos)
        path_at_pos = self.source_model.filePath(source_index_at_pos)
        source_indexes = [self.proxy_model.mapToSource(idx) for idx in proxy_indexes]
        selected_paths = [self.source_model.filePath(idx) for idx in source_indexes if idx.column() == 0]
        if not selected_paths:
            return

        menu = QMenu()

        # 打开 (单选)
        if len(selected_paths) == 1:
            path = selected_paths[0]
            source_index = self.source_model.index(path)
            if not self.source_model.isDir(source_index):
                open_action = menu.addAction(_("Open"))
                open_action.triggered.connect(lambda checked=False, p=path: self.file_double_clicked.emit(p))

        # 重命名 (单选)
        if len(selected_paths) == 1:
            path = selected_paths[0]
            proxy_index_at_pos = self.tree_view.indexAt(pos)
            rename_action = menu.addAction(_("Rename"))
            rename_action.triggered.connect(lambda checked=False, idx=proxy_index_at_pos: self.tree_view.edit(idx))

        # 设为根目录
        if self.source_model.isDir(source_index_at_pos):
            menu.addSeparator()
            set_as_root_action = menu.addAction(_("Set as Root"))
            set_as_root_action.triggered.connect(lambda checked=False, p=path_at_pos: self.set_root_path(p))

        # 浏览本地文件 (第一项)
        first_path = selected_paths[0]
        reveal_action = menu.addAction(_("Reveal in File Explorer"))
        reveal_action.triggered.connect(
            lambda checked=False, p=first_path: QDesktopServices.openUrl(
                QUrl.fromLocalFile(os.path.dirname(p) if not os.path.isdir(p) else p))
        )

        # 删除
        delete_action = menu.addAction(_("Delete"))
        delete_action.triggered.connect(lambda checked=False, paths=selected_paths: self.delete_items(paths))

        menu.addSeparator()

        # 复制文件路径
        copy_path_action = menu.addAction(_("Copy Full Path"))
        copy_path_action.triggered.connect(
            lambda checked=False, paths=selected_paths: (
                QApplication.clipboard().setText('\n'.join(paths)),
                self.app.update_statusbar(
                    _("Copied {count} full path(s) to clipboard.").format(count=len(paths))
                )
            )
        )

        # 复制文件名称
        copy_name_action = menu.addAction(_("Copy File Name"))
        selected_names = [os.path.basename(p) for p in selected_paths]
        copy_name_action.triggered.connect(
            lambda checked=False, names=selected_names: (
                QApplication.clipboard().setText('\n'.join(names)),
                self.app.update_statusbar(
                    _("Copied {count} file name(s) to clipboard.").format(count=len(names))
                )
            )
        )

        # 插件动作
        if hasattr(self.app, 'plugin_manager'):
            plugin_menu_items = self.app.plugin_manager.run_hook('on_file_tree_context_menu', selected_paths)
            if plugin_menu_items:
                menu.addSeparator()
                self.app.plugin_manager._create_menu_from_structure(menu, plugin_menu_items)

        menu.exec(self.tree_view.viewport().mapToGlobal(pos))

    def delete_items(self, paths):
        reply = QMessageBox.warning(
            self, _("Confirm Deletion"),
            _("Are you sure you want to permanently delete the following item(s)?\n\n- {items}").format(
                items='\n- '.join(os.path.basename(p) for p in paths)
            ),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            for path in paths:
                try:
                    if os.path.isdir(path):
                        QDir(path).removeRecursively()
                    else:
                        os.remove(path)
                except Exception as e:
                    QMessageBox.critical(self, _("Error"),
                                         _("Failed to delete {path}: {error}").format(path=path, error=e))

    def update_ui_texts(self):
        self.filter_edit.setPlaceholderText(_("Filter files..."))
        self.show_all_checkbox.setText(_("Show All Files"))