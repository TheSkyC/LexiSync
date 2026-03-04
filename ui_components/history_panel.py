# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QListWidget, QListWidgetItem,
                               QLabel, QToolBar, QLineEdit, QSizePolicy, QHBoxLayout,
                               QToolButton, QMenu)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon, QColor, QFont, QAction, QAction, QCursor
import os
from utils.path_utils import get_resource_path
from utils.localization import _


class HistoryItemWidget(QWidget):
    def __init__(self, record, is_current, is_redoable, current_file_id, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.record = record

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        # 1. Icon
        icon_name = record.get('icon_type', 'layers.svg')
        icon_path = get_resource_path(f"icons/{icon_name}")
        self.icon_label = QLabel()
        if os.path.exists(icon_path):
            self.icon_label.setPixmap(QIcon(icon_path).pixmap(QSize(16, 16)))
        layout.addWidget(self.icon_label)

        # 2. Text Content (Description + Timestamp)
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        self.desc_label = QLabel(record.get('description', _("Unknown Action")))
        font = self.desc_label.font()
        if is_current:
            font.setBold(True)
        self.desc_label.setFont(font)

        self.time_label = QLabel(record.get('timestamp', ''))
        self.time_label.setStyleSheet("font-size: 10px;")

        text_layout.addWidget(self.desc_label)
        text_layout.addWidget(self.time_label)
        layout.addLayout(text_layout, 1)

        # 3. Cross-file Jump Indicator
        record_file_id = record.get('file_id')
        if record_file_id and current_file_id and record_file_id != current_file_id:
            jump_icon_path = get_resource_path("icons/corner-right-up.svg")
            self.jump_label = QLabel()
            if os.path.exists(jump_icon_path):
                self.jump_label.setPixmap(QIcon(jump_icon_path).pixmap(QSize(14, 14)))
            self.jump_label.setToolTip(_("This action belongs to a different file. Clicking will jump to it."))
            layout.addWidget(self.jump_label)

        # Apply Styles based on state
        if is_redoable:
            self.desc_label.setStyleSheet("color: #999999;")
            self.time_label.setStyleSheet("color: #BBBBBB;")
            self.icon_label.setStyleSheet("opacity: 0.5;")
        else:
            self.desc_label.setStyleSheet("color: #333333;")
            self.time_label.setStyleSheet("color: #888888;")

        if is_current:
            self.setStyleSheet("background-color: #E6F7FF;")
        else:
            self.setStyleSheet("background-color: transparent;")

        self._update_item_style(is_current, is_redoable)

    def _update_item_style(self, is_current, is_redoable):
        bg_color = "#E6F7FF" if is_current else "transparent"

        style = f"""
            HistoryItemWidget {{
                background-color: {bg_color};
                border: none;
            }}
            QLabel {{
                background-color: transparent;
                border: none;
            }}
        """

        if is_redoable:
            self.desc_label.setStyleSheet("color: #999999; background: transparent;")
            self.time_label.setStyleSheet("color: #BBBBBB; background: transparent;")
        else:
            self.desc_label.setStyleSheet("color: #333333; background: transparent;")
            self.time_label.setStyleSheet("color: #888888; background: transparent;")

        self.setStyleSheet(style)


class HistoryPanel(QWidget):
    jump_requested = Signal(int)
    clear_requested = Signal()
    revert_to_requested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.undo_history = []
        self.redo_history = []
        self.current_file_id = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        self.toolbar = QToolBar()
        self.toolbar.setIconSize(QSize(16, 16))
        self.toolbar.setStyleSheet("QToolBar { border-bottom: 1px solid #E0E0E0; background: #F8F9FA; }")

        # Clear Action
        clear_icon = QIcon(get_resource_path("icons/trash.svg"))
        self.clear_action = self.toolbar.addAction(clear_icon, _("Clear History"))
        self.clear_action.triggered.connect(self.clear_requested.emit)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.toolbar.addWidget(spacer)

        # Search Box
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(_("Filter history..."))
        self.search_edit.setMaximumWidth(150)
        self.search_edit.setStyleSheet("""
            QLineEdit { border: 1px solid #DCDFE6; border-radius: 3px; padding: 2px 5px; font-size: 11px; }
            QLineEdit:focus { border-color: #409EFF; }
        """)
        self.search_edit.textChanged.connect(self._filter_list)
        self.toolbar.addWidget(self.search_edit)

        layout.addWidget(self.toolbar)

        # List Widget
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.NoSelection)
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_context_menu)
        self.list_widget.setStyleSheet("""
            QListWidget { 
                border: none; 
                background-color: #FFFFFF; 
                outline: 0;
            }
            QListWidget::item { 
                border-bottom: 1px solid #F0F0F0; 
                padding: 0px;
            }
            QListWidget::item:hover { 
                background-color: #F5F7FA; 
            }
            QListWidget::item:selected {
                background-color: transparent;
            }
        """)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list_widget)

    def _show_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if not item: return

        index = item.data(Qt.UserRole)
        current_state_index = -1
        for i in range(self.list_widget.count()):
            widget = self.list_widget.itemWidget(self.list_widget.item(i))
            if widget and hasattr(widget, 'record') and widget.record.get('is_current'):
                current_state_index = i
                break

        if index < current_state_index:
            return

        menu = QMenu(self)

        # 1. 还原更改
        revert_icon = QIcon(get_resource_path("icons/corner-up-left.svg"))
        revert_action = QAction(revert_icon, _("Revert Changes"), self)

        revert_action.setEnabled(index >= current_state_index)

        revert_action.triggered.connect(lambda: self.revert_to_requested.emit(index))
        revert_action.hovered.connect(lambda: self.preview_revert(index, True))
        menu.aboutToHide.connect(lambda: self.preview_revert(index, False))

        menu.addAction(revert_action)

        # 2. 创建分支 (预留)
        branch_icon = QIcon(get_resource_path("icons/git-branch.svg"))
        branch_action = QAction(branch_icon, _("Create Branch from here"), self)
        branch_action.setEnabled(False)
        menu.addAction(branch_action)

        menu.exec(QCursor.pos())

    def preview_revert(self, target_index, is_previewing):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            widget = self.list_widget.itemWidget(item)
            if widget:
                if is_previewing and i <= target_index:
                    widget.setStyleSheet("background-color: #FFEBEE; color: #D32F2F;")
                else:
                    widget._update_item_style(widget.record.get('is_current'), widget.record.get('is_redoable'))

    def refresh(self, undo_history, redo_history, current_file_id):
        self.undo_history = undo_history
        self.redo_history = redo_history
        self.current_file_id = current_file_id

        self.list_widget.clear()

        chronological_list = list(undo_history) + list(reversed(redo_history))
        full_list = list(reversed(chronological_list))
        current_state_index = len(redo_history)

        for i, record in enumerate(full_list):
            is_redoable = i < current_state_index
            is_current = i == current_state_index

            record['is_current'] = is_current
            record['is_redoable'] = is_redoable

            item = QListWidgetItem(self.list_widget)
            item.setData(Qt.UserRole, i)
            item.setData(Qt.UserRole + 1, record.get('description', '').lower())

            widget = HistoryItemWidget(record, is_current, is_redoable, current_file_id)
            item.setSizeHint(widget.sizeHint())

            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, widget)

        self._filter_list(self.search_edit.text())

    def update_ui_texts(self):
        self.clear_action.setText(_("Clear History"))
        self.search_edit.setPlaceholderText(_("Filter history..."))
        self.refresh(self.undo_history, self.redo_history, self.current_file_id)

    def _filter_list(self, text):
        text = text.lower()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            desc = item.data(Qt.UserRole + 1)
            item.setHidden(bool(text and text not in desc))

    def _on_item_clicked(self, item):
        index = item.data(Qt.UserRole)
        self.jump_requested.emit(index)