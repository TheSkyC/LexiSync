# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from lexisync.ui_components.styled_button import StyledButton
from lexisync.utils.localization import _


class ApprovalItemWidget(QWidget):
    def __init__(self, req_id, ip, context, resolve_callback, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)

        info_layout = QVBoxLayout()
        info_layout.addWidget(QLabel(f"<b>IP: {ip}</b>"))
        ctx_label = QLabel(context)
        ctx_label.setStyleSheet("color: gray; font-size: 11px;")
        info_layout.addWidget(ctx_label)
        layout.addLayout(info_layout, 1)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(5)
        allow_btn = StyledButton(
            _("Allow"), on_click=lambda: resolve_callback(req_id, True), btn_type="success", size="small"
        )
        reject_btn = StyledButton(
            _("Reject"), on_click=lambda: resolve_callback(req_id, False), btn_type="danger", size="small"
        )
        btn_layout.addWidget(allow_btn)
        btn_layout.addWidget(reject_btn)
        layout.addLayout(btn_layout)


class CloudDashboardPanel(QWidget):
    resolve_approval_signal = Signal(str, bool)
    track_user_signal = Signal(str)
    kick_user_signal = Signal(str)
    ban_ip_signal = Signal(str)
    open_user_manager_signal = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._approval_items = {}
        self._user_data_map = {}
        self.setup_ui()

    def setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)

        # ==================== 左侧：控制与统计 (20%) ====================
        left_panel = QFrame()
        left_panel.setStyleSheet("background-color: #F8F9FA; border: 1px solid #E4E7ED; border-radius: 6px;")
        left_layout = QVBoxLayout(left_panel)

        title_label = QLabel(f"<b>{_('Cloud Server')}</b>")
        title_label.setStyleSheet("font-size: 14px; border: none;")
        left_layout.addWidget(title_label)

        self.status_indicator = QLabel(_("Status: Offline"))
        self.status_indicator.setStyleSheet("color: #909399; font-weight: bold; border: none;")
        left_layout.addWidget(self.status_indicator)

        self.url_label = QLabel("-")
        self.url_label.setStyleSheet("color: #409EFF; font-size: 11px; border: none;")
        self.url_label.setWordWrap(True)
        self.url_label.setOpenExternalLinks(True)
        left_layout.addWidget(self.url_label)

        self.toggle_btn = StyledButton(_("Start Service"), btn_type="primary")
        left_layout.addWidget(self.toggle_btn)

        left_layout.addSpacing(20)

        self.manage_btn = StyledButton(_("Manage Users && Permissions"), btn_type="default")
        self.manage_btn.clicked.connect(self.open_user_manager_signal.emit)
        left_layout.addWidget(self.manage_btn)

        left_layout.addStretch()
        main_layout.addWidget(left_panel, 2)

        # ==================== 中间：用户与审批 (45%) ====================
        mid_panel = QWidget()
        mid_layout = QVBoxLayout(mid_panel)
        mid_layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("QTabWidget::pane { border: 1px solid #E4E7ED; border-radius: 4px; background: #FFF; }")

        # 用户表格
        self.user_table = QTableWidget(0, 4)
        self.user_table.setHorizontalHeaderLabels([_("Name"), _("Role"), _("IP"), _("Status")])
        self.user_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.user_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.user_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.user_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.user_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.user_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.user_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.user_table.customContextMenuRequested.connect(self._show_user_context_menu)
        self.user_table.setFrameShape(QFrame.NoFrame)
        self.tabs.addTab(self.user_table, _("Online Users (0)"))

        # 审批列表
        self.approval_list = QListWidget()
        self.approval_list.setFrameShape(QFrame.NoFrame)
        self.tabs.addTab(self.approval_list, _("Pending (0)"))

        mid_layout.addWidget(self.tabs)
        main_layout.addWidget(mid_panel, 4)

        # ==================== 右侧：实时日志 (35%) ====================
        right_panel = QFrame()
        right_panel.setStyleSheet("background-color: #FFFFFF; border: 1px solid #E4E7ED; border-radius: 6px;")
        right_layout = QVBoxLayout(right_panel)

        log_header = QHBoxLayout()
        log_title = QLabel(f"<b>{_('Activity Log')}</b>")
        log_title.setStyleSheet("border: none;")

        # 红点提示
        self.red_dot = QLabel("🔴")
        self.red_dot.setStyleSheet("color: #F56C6C; font-size: 10px; border: none;")
        self.red_dot.hide()

        log_header.addWidget(log_title)
        log_header.addWidget(self.red_dot)
        log_header.addStretch()

        clear_log_btn = QPushButton(_("Clear"))
        clear_log_btn.setCursor(Qt.PointingHandCursor)
        clear_log_btn.setStyleSheet(
            "border: none; color: #909399; text-decoration: underline; background: transparent;"
        )
        clear_log_btn.clicked.connect(lambda: self.log_list.clear())
        log_header.addWidget(clear_log_btn)

        right_layout.addLayout(log_header)

        self.log_list = QListWidget()
        self.log_list.setFrameShape(QFrame.NoFrame)
        from PySide6.QtGui import QFont

        self.log_list.setFont(QFont("Consolas", 11))

        self.log_list.setWordWrap(True)
        self.log_list.installEventFilter(self)

        right_layout.addWidget(self.log_list)
        main_layout.addWidget(right_panel, 3)

    def eventFilter(self, obj, event):
        if obj == self.log_list and event.type() == QEvent.Enter:
            self.red_dot.hide()
        return super().eventFilter(obj, event)

    def set_service_state(self, is_running, url=""):
        if is_running:
            self.toggle_btn.setText(_("Stop Cloud Service"))
            self.toggle_btn.set_btn_type("danger")
            self.status_indicator.setText(_("Status: Online"))
            self.status_indicator.setStyleSheet("color: #27AE60; font-weight: bold; border: none;")
            self.url_label.setText(f"<a href='{url}' style='color:#409EFF; text-decoration:none;'>{url}</a>")
        else:
            self.toggle_btn.setText(_("Start Cloud Service"))
            self.toggle_btn.set_btn_type("primary")
            self.status_indicator.setText(_("Status: Offline"))
            self.status_indicator.setStyleSheet("color: #909399; font-weight: bold; border: none;")
            self.url_label.setText("-")
            self.clear_all()

    def update_user_list(self, users):
        self.user_table.setRowCount(0)
        self._user_data_map.clear()
        self.tabs.setTabText(0, _("Online Users ({n})").format(n=len(users)))

        for i, u in enumerate(users):
            self.user_table.insertRow(i)
            self._user_data_map[u["name"]] = u

            name_item = QTableWidgetItem(u["name"])
            name_item.setData(Qt.UserRole, u["name"])
            self.user_table.setItem(i, 0, name_item)

            self.user_table.setItem(i, 1, QTableWidgetItem(_(u["role"].capitalize())))
            self.user_table.setItem(i, 2, QTableWidgetItem(u.get("ip", "Unknown")))

            status_text = _("Editing...") if u.get("editing_ts_id") else _("Idle")
            status_item = QTableWidgetItem(status_text)
            if u.get("editing_ts_id"):
                status_item.setForeground(QColor("#E6A23C"))
            self.user_table.setItem(i, 3, status_item)

    def update_user_focus(self, username, ts_id):
        if username in self._user_data_map:
            self._user_data_map[username]["editing_ts_id"] = ts_id
            # 刷新表格显示
            for row in range(self.user_table.rowCount()):
                if self.user_table.item(row, 0).data(Qt.UserRole) == username:
                    status_text = _("Editing...") if ts_id else _("Idle")
                    status_item = QTableWidgetItem(status_text)
                    if ts_id:
                        status_item.setForeground(QColor("#E6A23C"))
                    self.user_table.setItem(row, 3, status_item)
                    break

    def add_pending_approval(self, req_id, ip, context):
        item = QListWidgetItem(self.approval_list)
        widget = ApprovalItemWidget(req_id, ip, context, self._on_approval_resolved, self)
        item.setSizeHint(widget.sizeHint())
        self.approval_list.setItemWidget(item, widget)
        self._approval_items[req_id] = item
        self._update_approval_tab_title()

    def remove_pending_approval(self, req_id):
        if req_id in self._approval_items:
            item = self._approval_items.pop(req_id)
            row = self.approval_list.row(item)
            self.approval_list.takeItem(row)
            self._update_approval_tab_title()

    def _on_approval_resolved(self, req_id, approved):
        self.remove_pending_approval(req_id)
        self.resolve_approval_signal.emit(req_id, approved)

    def _update_approval_tab_title(self):
        count = self.approval_list.count()
        self.tabs.setTabText(1, _("Pending ({n})").format(n=count))
        if count > 0:
            self.tabs.tabBar().setTabTextColor(1, Qt.red)
        else:
            self.tabs.tabBar().setTabTextColor(1, Qt.black)

    def add_log(self, entry):
        time_str = entry.get("timestamp", "").split("T")[-1]
        action = entry.get("action", "")
        user = entry.get("user", "System")

        def trunc(text, max_len=25):
            if not text:
                return "<i>Empty</i>"
            text = str(text).replace("\n", "↵").replace("<", "&lt;").replace(">", "&gt;")
            return text[:max_len] + "..." if len(text) > max_len else text

        if action == "update_text":
            old_v = trunc(entry.get("old_value", ""))
            new_v = trunc(entry.get("new_value", ""))
            msg = f"[{time_str}] <b>{user}</b>: <span style='color:#F56C6C; text-decoration:line-through;'>{old_v}</span> ➔ <span style='color:#67C23A;'>{new_v}</span>"
        elif action == "update_status":
            old_s = _(entry.get("old_value", "None"))
            new_s = _(entry.get("new_value", "None"))
            msg = f"[{time_str}] <b>{user}</b> {_('changed status')}: <span style='color:#909399;'>[{old_s}]</span> ➔ <span style='color:#E6A23C;'>[{new_s}]</span>"
        elif action == "login":
            msg = f"[{time_str}] <b>{user}</b> <span style='color:#409EFF;'>{_('joined the session')}</span>"
        elif action == "login_denied":
            msg = f"[{time_str}] <b>{user}</b> <span style='color:#E6A23C;'>{_('was denied access')}</span>"
        else:
            return

        item = QListWidgetItem()
        self.log_list.insertItem(0, item)

        lbl = QLabel(msg)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("background: transparent; border: none;")
        item.setSizeHint(lbl.sizeHint())
        self.log_list.setItemWidget(item, lbl)

        if self.log_list.count() > 100:
            self.log_list.takeItem(100)

        # 触发红点
        if not self.log_list.underMouse():
            self.red_dot.show()

    def _show_user_context_menu(self, pos):
        item = self.user_table.itemAt(pos)
        if not item:
            return

        row = item.row()
        username = self.user_table.item(row, 0).data(Qt.UserRole)
        user_info = self._user_data_map.get(username)
        if not user_info:
            return

        menu = QMenu(self)

        ts_id = user_info.get("editing_ts_id")
        track_action = QAction(_("Track User (Locate row)"), self)
        if ts_id:
            track_action.triggered.connect(lambda: self.track_user_signal.emit(ts_id))
        else:
            track_action.setEnabled(False)
        menu.addAction(track_action)

        menu.addSeparator()

        kick_action = QAction(_("Kick User"), self)
        kick_action.triggered.connect(
            lambda: self._confirm_action(
                _("Kick"),
                _("Are you sure you want to disconnect {u}?").format(u=username),
                lambda: self.kick_user_signal.emit(username),
            )
        )
        menu.addAction(kick_action)

        ip = user_info.get("ip")
        if ip and ip != "127.0.0.1":
            ban_action = QAction(_("Ban IP ({ip})").format(ip=ip), self)
            ban_action.triggered.connect(
                lambda: self._confirm_action(
                    _("Ban IP"),
                    _("Are you sure you want to ban IP {ip}?").format(ip=ip),
                    lambda: self.ban_ip_signal.emit(ip),
                )
            )
            menu.addAction(ban_action)

        menu.exec(self.user_table.viewport().mapToGlobal(pos))

    def _confirm_action(self, title, text, callback):
        if QMessageBox.question(self, title, text) == QMessageBox.Yes:
            callback()

    def clear_all(self):
        self.user_table.setRowCount(0)
        self._user_data_map.clear()
        self.tabs.setTabText(0, _("Online Users (0)"))
        self.approval_list.clear()
        self._approval_items.clear()
        self._update_approval_tab_title()
