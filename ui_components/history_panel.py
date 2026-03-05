# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QListWidget, QListWidgetItem,
                               QLabel, QToolBar, QLineEdit, QSizePolicy, QHBoxLayout,
                               QMenu)
from PySide6.QtCore import Qt, Signal, QSize, QEvent
from PySide6.QtGui import QIcon, QCursor, QAction
import os
import datetime
from utils.path_utils import get_resource_path
from utils.localization import _
from ui_components.tooltip import Tooltip


def get_relative_time_from_hms(time_str):
    """
    将 HH:MM:SS 转换为相对时间（如 "2 mins ago"）。
    """
    if not time_str:
        return ""
    try:
        now = datetime.datetime.now()
        t = datetime.datetime.strptime(time_str, "%H:%M:%S").time()
        record_time = datetime.datetime.combine(now.date(), t)

        if record_time > now:
            record_time -= datetime.timedelta(days=1)

        diff = now - record_time
        seconds = diff.total_seconds()

        if seconds < 60:
            return _("Just now")
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return _("{m} mins ago").format(m=minutes) if minutes > 1 else _("1 min ago")
        else:
            hours = int(seconds / 3600)
            return _("{h} hours ago").format(h=hours) if hours > 1 else _("1 hour ago")
    except Exception:
        return time_str


class HistoryItemWidget(QWidget):
    def __init__(self, record, is_current, is_redoable, current_file_id, seq_num, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.record = record
        self.is_current = is_current
        self.is_redoable = is_redoable

        self._custom_tooltip = Tooltip(self)
        self._tooltip_html = self._build_tooltip_html(record)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        icon_name = record.get('icon_type', 'layers.svg')
        icon_path = get_resource_path(f"icons/{icon_name}")
        self.icon_label = QLabel()
        if os.path.exists(icon_path):
            self.icon_label.setPixmap(QIcon(icon_path).pixmap(QSize(16, 16)))
        layout.addWidget(self.icon_label)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)

        self.desc_label = QLabel(record.get('description', _("Unknown Action")))
        font = self.desc_label.font()
        if is_current:
            font.setBold(True)
        self.desc_label.setFont(font)
        text_layout.addWidget(self.desc_label)

        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 0, 0, 0)

        self.time_label = QLabel(record.get('timestamp', ''))
        self.time_label.setStyleSheet("font-size: 10px;")
        bottom_row.addWidget(self.time_label)

        bottom_row.addStretch()

        self.seq_label = QLabel(f"#{seq_num}")
        self.seq_label.setStyleSheet("font-size: 10px; color: #A0A0A0; font-weight: bold;")
        bottom_row.addWidget(self.seq_label)

        text_layout.addLayout(bottom_row)
        layout.addLayout(text_layout, 1)

        record_file_id = record.get('file_id')
        if record_file_id and current_file_id and record_file_id != current_file_id:
            jump_icon_path = get_resource_path("icons/corner-right-up.svg")
            self.jump_label = QLabel()
            if os.path.exists(jump_icon_path):
                self.jump_label.setPixmap(QIcon(jump_icon_path).pixmap(QSize(14, 14)))
            self.jump_label.setToolTip(_("This action belongs to a different file."))
            layout.addWidget(self.jump_label)

        self._update_item_style(is_current, is_redoable)

    def _build_tooltip_html(self, record):
        action_type = record.get('type', '')
        data = record.get('data', {})
        desc = record.get('description', _("Unknown Action"))
        time_str = record.get('timestamp', '')
        rel_time = get_relative_time_from_hms(time_str)

        html = f"<b style='color:#409EFF; font-size:13px;'>{desc}</b>"
        html += f" <span style='color:#AAAAAA; font-size:11px;'>({rel_time})</span>"
        html += "<hr style='border-color: #555; margin: 6px 0;'>"

        def truncate(text, length=60):
            if not text: return "<i>Empty</i>"
            text = str(text).replace('\n', '↵').replace('<', '&lt;').replace('>', '&gt;')
            return text[:length] + "..." if len(text) > length else text

        if action_type == 'single_change':
            field = data.get('field', 'unknown')
            old_val = data.get('old_value', '')
            new_val = data.get('new_value', '')

            html += f"<div style='color:#CCCCCC; margin-bottom:2px;'><b>{_('Field')}:</b> {field}</div>"
            html += f"<div style='color:#F56C6C;'><b>-</b> {truncate(old_val)}</div>"
            html += f"<div style='color:#67C23A;'><b>+</b> {truncate(new_val)}</div>"

        elif action_type in ['bulk_change', 'bulk_ai_translate', 'bulk_excel_import', 'bulk_context_menu',
                             'bulk_replace_all']:
            changes = data.get('changes', [])
            count = len(changes)
            html += f"<div style='color:#CCCCCC; margin-bottom:4px;'>{_('Affected items')}: {count}</div>"

            preview_limit = 3
            for i, change in enumerate(changes[:preview_limit]):
                old_val = change.get('old_value', '')
                new_val = change.get('new_value', '')
                html += f"<div style='margin-bottom:4px;'>"
                html += f"<div style='color:#F56C6C; font-size:11px;'><b>-</b> {truncate(old_val, 40)}</div>"
                html += f"<div style='color:#67C23A; font-size:11px;'><b>+</b> {truncate(new_val, 40)}</div>"
                html += f"</div>"

            if count > preview_limit:
                html += f"<div style='color:#888888; font-style:italic; font-size:11px;'>... {_('and {n} more').format(n=count - preview_limit)}</div>"
        else:
            html += f"<div style='color:#CCCCCC;'>{_('No detailed preview available.')}</div>"

        return html

    def event(self, event):
        if event.type() == QEvent.Enter:
            if self._tooltip_html:
                self._custom_tooltip.show_tooltip(QCursor.pos(), self._tooltip_html, delay=400)
        elif event.type() == QEvent.Leave or event.type() == QEvent.MouseButtonPress:
            self._custom_tooltip.hide()
        return super().event(event)

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
            self.seq_label.setStyleSheet("color: #DDDDDD; background: transparent;")
            self.icon_label.setStyleSheet("opacity: 0.4;")
        else:
            self.desc_label.setStyleSheet("color: #333333; background: transparent;")
            self.time_label.setStyleSheet("color: #888888; background: transparent;")
            self.seq_label.setStyleSheet("color: #A0A0A0; background: transparent;")
            self.icon_label.setStyleSheet("opacity: 1.0;")

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

        self.toolbar = QToolBar()
        self.toolbar.setIconSize(QSize(16, 16))
        self.toolbar.setStyleSheet("QToolBar { border-bottom: 1px solid #E0E0E0; background: #F8F9FA; }")

        clear_icon = QIcon(get_resource_path("icons/trash.svg"))
        self.clear_action = self.toolbar.addAction(clear_icon, _("Clear History"))
        self.clear_action.triggered.connect(self.clear_requested.emit)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.toolbar.addWidget(spacer)

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

    def _get_current_state_index(self):
        for i in range(self.list_widget.count()):
            widget = self.list_widget.itemWidget(self.list_widget.item(i))
            if widget and hasattr(widget, 'record') and widget.record.get('is_current'):
                return i
        return -1

    def _show_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if not item: return

        index = item.data(Qt.UserRole)
        current_state_index = self._get_current_state_index()

        menu = QMenu(self)

        # 1. 移动指针操作 (Undo/Redo to here)
        if index > current_state_index:
            # 撤销至此 (向下跳)
            jump_icon = QIcon(get_resource_path("icons/corner-up-left.svg"))
            jump_action = QAction(jump_icon, _("Undo to here"), self)
            jump_action.triggered.connect(lambda: self.jump_requested.emit(index))
            jump_action.hovered.connect(
                lambda: self.preview_jump(index, current_state_index, is_redo=False, is_previewing=True))
            menu.aboutToHide.connect(
                lambda: self.preview_jump(index, current_state_index, is_redo=False, is_previewing=False))
            menu.addAction(jump_action)

        elif index < current_state_index:
            # 重做至此 (向上跳)
            jump_icon = QIcon(get_resource_path("icons/corner-up-right.svg"))
            jump_action = QAction(jump_icon, _("Redo to here"), self)
            jump_action.triggered.connect(lambda: self.jump_requested.emit(index))
            jump_action.hovered.connect(
                lambda: self.preview_jump(index, current_state_index, is_redo=True, is_previewing=True))
            menu.aboutToHide.connect(
                lambda: self.preview_jump(index, current_state_index, is_redo=True, is_previewing=False))
            menu.addAction(jump_action)

        # 2. 破坏性还原操作 (Revert selected and subsequent)
        if index >= current_state_index:
            if menu.actions():
                menu.addSeparator()
            revert_icon = QIcon(get_resource_path("icons/delete.svg"))
            revert_action = QAction(revert_icon, _("Revert selected and subsequent changes"), self)
            revert_action.triggered.connect(lambda: self.revert_to_requested.emit(index))
            revert_action.hovered.connect(lambda: self.preview_destructive_revert(index, True))
            menu.aboutToHide.connect(lambda: self.preview_destructive_revert(index, False))
            menu.addAction(revert_action)

        menu.exec(QCursor.pos())

    def _reset_all_previews(self):
        for i in range(self.list_widget.count()):
            widget = self.list_widget.itemWidget(self.list_widget.item(i))
            if widget:
                widget._update_item_style(widget.record.get('is_current'), widget.record.get('is_redoable'))

    def preview_jump(self, target_index, current_state_index, is_redo, is_previewing):
        """预览指针跳转 (黄色/绿色)"""
        self._reset_all_previews()
        if not is_previewing:
            return

        for i in range(self.list_widget.count()):
            widget = self.list_widget.itemWidget(self.list_widget.item(i))
            if not widget: continue

            if not is_redo and current_state_index <= i < target_index:
                # 撤销预览：黄色 (不包含目标项)
                widget.setStyleSheet("background-color: #FFF9C4; color: #F57F17;")
            elif is_redo and target_index <= i < current_state_index:
                # 重做预览：绿色
                widget.setStyleSheet("background-color: #E8F5E9; color: #2E7D32;")

    def preview_destructive_revert(self, target_index, is_previewing):
        """预览破坏性还原 (红色)"""
        self._reset_all_previews()
        if not is_previewing:
            return

        for i in range(self.list_widget.count()):
            widget = self.list_widget.itemWidget(self.list_widget.item(i))
            if not widget: continue

            if 0 <= i <= target_index:
                # 破坏性还原：红色 (包含目标项及之上所有项)
                widget.setStyleSheet("background-color: #FFEBEE; color: #D32F2F;")

    def refresh(self, undo_history, redo_history, current_file_id):
        self.undo_history = undo_history
        self.redo_history = redo_history
        self.current_file_id = current_file_id

        v_scrollbar = self.list_widget.verticalScrollBar()
        saved_scroll_value = v_scrollbar.value() if v_scrollbar else 0

        self.list_widget.clear()

        chronological_list = list(undo_history) + list(reversed(redo_history))
        full_list = list(reversed(chronological_list))

        current_state_index = len(redo_history)
        total_items = len(full_list)

        for i, record in enumerate(full_list):
            is_redoable = i < current_state_index
            is_current = i == current_state_index

            record['is_current'] = is_current
            record['is_redoable'] = is_redoable

            seq_num = total_items - i

            item = QListWidgetItem(self.list_widget)
            item.setData(Qt.UserRole, i)
            item.setData(Qt.UserRole + 1, record.get('description', '').lower())

            widget = HistoryItemWidget(record, is_current, is_redoable, current_file_id, seq_num)
            item.setSizeHint(widget.sizeHint())

            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, widget)

        self._filter_list(self.search_edit.text())

        if v_scrollbar:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: v_scrollbar.setValue(saved_scroll_value))

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