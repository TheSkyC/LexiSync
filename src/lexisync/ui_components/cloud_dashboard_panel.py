# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QAction, QColor, QFont
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

# ── Design Tokens ─────────────────────────────────────────────────────────────
_CLR = {
    "bg_base": "#F0F2F5",
    "bg_panel": "#FFFFFF",
    "bg_left": "#1C2333",
    "text_primary": "#1A202C",
    "text_secondary": "#64748B",
    "text_muted": "#94A3B8",
    "text_on_dark": "#E2E8F0",
    "accent": "#4F8EF7",
    "success": "#22C55E",
    "warning": "#F59E0B",
    "danger": "#EF4444",
    "border": "#E2E8F0",
    "border_dark": "#2E3A50",
    "table_header": "#F8FAFC",
    "table_row_alt": "#FAFBFF",
    "table_sel": "#EFF6FF",
}

_RADIUS = "6px"
_PANEL_BASE = f"background-color: {_CLR['bg_panel']}; border: 1px solid {_CLR['border']}; border-radius: {_RADIUS};"
_LEFT_PANEL = f"background-color: {_CLR['bg_left']}; border: none; border-radius: {_RADIUS};"

# ── ApprovalItemWidget ─────────────────────────────────────────────────────────


class ApprovalItemWidget(QWidget):
    def __init__(self, req_id, ip, context, resolve_callback, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {_CLR['bg_panel']}; border: none;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(10)

        bar = QFrame()
        bar.setFixedWidth(3)
        bar.setStyleSheet(f"background: {_CLR['warning']}; border-radius: 1px; border: none;")
        layout.addWidget(bar)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        ip_lbl = QLabel(f"<b>{ip}</b>")
        ip_lbl.setStyleSheet(f"color: {_CLR['text_primary']}; font-size: 12px; border: none;")
        info_layout.addWidget(ip_lbl)

        ctx_label = QLabel(context)
        ctx_label.setStyleSheet(f"color: {_CLR['text_secondary']}; font-size: 10px; border: none;")
        ctx_label.setWordWrap(True)
        info_layout.addWidget(ctx_label)
        layout.addLayout(info_layout, 1)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)
        allow_btn = StyledButton(
            _("Allow"), on_click=lambda: resolve_callback(req_id, True), btn_type="success", size="small"
        )
        reject_btn = StyledButton(
            _("Reject"), on_click=lambda: resolve_callback(req_id, False), btn_type="danger", size="small"
        )
        btn_layout.addWidget(allow_btn)
        btn_layout.addWidget(reject_btn)
        layout.addLayout(btn_layout)


# ── CloudDashboardPanel ────────────────────────────────────────────────────────


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
        self.setStyleSheet(f"background: {_CLR['bg_base']};")
        self.setup_ui()

    def setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(10)

        main_layout.addWidget(self._build_left_panel(), 2)
        main_layout.addWidget(self._build_mid_panel(), 4)
        main_layout.addWidget(self._build_right_panel(), 3)

    def _build_left_panel(self) -> QFrame:
        panel = QFrame()
        panel.setStyleSheet(_LEFT_PANEL)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title_lbl = QLabel(_("Cloud Server"))
        title_lbl.setStyleSheet(f"color: {_CLR['text_on_dark']}; font-size: 14px; font-weight: bold; border: none;")
        layout.addWidget(title_lbl)

        status_row = QHBoxLayout()
        status_row.setSpacing(6)
        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet(f"color: {_CLR['text_muted']}; font-size: 10px; border: none;")
        self.status_indicator = QLabel(_("Offline"))
        self.status_indicator.setStyleSheet(
            f"color: {_CLR['text_muted']}; font-size: 12px; font-weight: bold; border: none;"
        )
        status_row.addWidget(self._status_dot)
        status_row.addWidget(self.status_indicator)
        status_row.addStretch()
        layout.addLayout(status_row)

        self.url_label = QLabel("—")
        self.url_label.setStyleSheet(f"color: {_CLR['accent']}; font-size: 11px; border: none;")
        self.url_label.setWordWrap(True)
        self.url_label.setOpenExternalLinks(True)
        layout.addWidget(self.url_label)

        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setStyleSheet(f"border: none; background: {_CLR['border_dark']}; max-height: 1px;")
        layout.addWidget(div)

        self.toggle_btn = StyledButton(_("Start Cloud Service"), btn_type="primary")
        layout.addWidget(self.toggle_btn)

        self.manage_btn = StyledButton(_("Manage Users & Permissions"), btn_type="default")
        self.manage_btn.clicked.connect(self.open_user_manager_signal.emit)
        layout.addWidget(self.manage_btn)

        layout.addStretch()
        return panel

    def _build_mid_panel(self) -> QWidget:
        panel = QFrame()
        panel.setStyleSheet(_PANEL_BASE)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: none; background: {_CLR["bg_panel"]}; }}
            QTabBar::tab {{ background: transparent; color: {_CLR["text_secondary"]}; padding: 8px 12px; font-size: 12px; border: none; border-bottom: 2px solid transparent; }}
            QTabBar::tab:selected {{ color: {_CLR["accent"]}; border-bottom: 2px solid {_CLR["accent"]}; font-weight: bold; }}
            QTabBar::tab:hover:!selected {{ color: {_CLR["text_primary"]}; }}
        """)

        self.user_table = QTableWidget(0, 4)
        self.user_table.setHorizontalHeaderLabels([_("Name"), _("Role"), _("IP"), _("Status")])
        self.user_table.setStyleSheet(f"""
            QTableWidget {{ background: {_CLR["bg_panel"]}; border: none; gridline-color: {_CLR["border"]}; font-size: 12px; color: {_CLR["text_primary"]}; }}
            QTableWidget::item {{ padding: 4px 8px; border: none; }}
            QTableWidget::item:selected {{ background: {_CLR["table_sel"]}; color: {_CLR["text_primary"]}; }}
            QHeaderView::section {{ background: {_CLR["table_header"]}; color: {_CLR["text_secondary"]}; font-size: 11px; font-weight: bold; padding: 6px 8px; border: none; border-bottom: 1px solid {_CLR["border"]}; }}
        """)
        self.user_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.user_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.user_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.user_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.user_table.verticalHeader().hide()
        self.user_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.user_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.user_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.user_table.customContextMenuRequested.connect(self._show_user_context_menu)
        self.user_table.setFrameShape(QFrame.NoFrame)
        self.user_table.setShowGrid(False)
        self.user_table.setAlternatingRowColors(True)
        self.user_table.setStyleSheet(
            self.user_table.styleSheet() + f"QTableWidget {{ alternate-background-color: {_CLR['table_row_alt']}; }}"
        )
        self.tabs.addTab(self.user_table, _("Online Users (0)"))

        self.approval_list = QListWidget()
        self.approval_list.setFrameShape(QFrame.NoFrame)
        self.approval_list.setStyleSheet(f"""
            QListWidget {{ background: {_CLR["bg_panel"]}; border: none; padding: 4px; }}
            QListWidget::item {{ background: {_CLR["bg_base"]}; border-radius: {_RADIUS}; margin-bottom: 4px; border: 1px solid {_CLR["border"]}; }}
        """)
        self.tabs.addTab(self.approval_list, _("Pending (0)"))

        layout.addWidget(self.tabs)
        return panel

    def _build_right_panel(self) -> QFrame:
        panel = QFrame()
        panel.setStyleSheet(_PANEL_BASE)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        header_row = QHBoxLayout()
        log_title = QLabel(_("Activity Log"))
        log_title.setStyleSheet(f"color: {_CLR['text_primary']}; font-size: 13px; font-weight: bold; border: none;")
        header_row.addWidget(log_title)

        self.red_dot = QLabel("●")
        self.red_dot.setStyleSheet(f"color: {_CLR['danger']}; font-size: 9px; border: none;")
        self.red_dot.hide()
        header_row.addWidget(self.red_dot)
        header_row.addStretch()

        clear_log_btn = QPushButton(_("Clear"))
        clear_log_btn.setCursor(Qt.PointingHandCursor)
        clear_log_btn.setStyleSheet(
            f"border: none; color: {_CLR['text_muted']}; background: transparent; font-size: 11px;"
        )
        clear_log_btn.clicked.connect(lambda: self.log_list.clear())
        header_row.addWidget(clear_log_btn)

        layout.addLayout(header_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"border: none; background: {_CLR['border']}; max-height: 1px;")
        layout.addWidget(sep)

        self.log_list = QListWidget()
        self.log_list.setFrameShape(QFrame.NoFrame)
        self.log_list.setFont(QFont("Consolas", 10))
        self.log_list.setWordWrap(True)
        self.log_list.setStyleSheet(f"""
            QListWidget {{ background: {_CLR["bg_panel"]}; border: none; }}
            QListWidget::item {{ padding: 4px; border-bottom: 1px solid {_CLR["border"]}; }}
            QListWidget::item:hover {{ background: {_CLR["table_row_alt"]}; }}
        """)
        self.log_list.installEventFilter(self)
        self.log_list.itemDoubleClicked.connect(self._on_log_double_clicked)
        layout.addWidget(self.log_list)

        return panel

    def eventFilter(self, obj, event):
        if obj == self.log_list and event.type() == QEvent.Enter:
            self.red_dot.hide()
        return super().eventFilter(obj, event)

    def _on_log_double_clicked(self, item):
        ts_id = item.data(Qt.UserRole)
        if ts_id:
            self.track_user_signal.emit(ts_id)

    def set_service_state(self, is_running, url=""):
        if is_running:
            self.toggle_btn.setText(_("Stop Cloud Service"))
            self.toggle_btn.set_btn_type("danger")
            self.status_indicator.setText(_("Online"))
            self.status_indicator.setStyleSheet(
                f"color: {_CLR['success']}; font-size: 12px; font-weight: bold; border: none;"
            )
            self._status_dot.setStyleSheet(f"color: {_CLR['success']}; font-size: 10px; border: none;")
            self.url_label.setText(f"<a href='{url}' style='color:{_CLR['accent']}; text-decoration:none;'>{url}</a>")
        else:
            self.toggle_btn.setText(_("Start Cloud Service"))
            self.toggle_btn.set_btn_type("primary")
            self.status_indicator.setText(_("Offline"))
            self.status_indicator.setStyleSheet(
                f"color: {_CLR['text_muted']}; font-size: 12px; font-weight: bold; border: none;"
            )
            self._status_dot.setStyleSheet(f"color: {_CLR['text_muted']}; font-size: 10px; border: none;")
            self.url_label.setText("—")
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
            name_item.setFont(QFont("", -1, QFont.Bold))
            self.user_table.setItem(i, 0, name_item)

            role_item = QTableWidgetItem(_(u["role"].capitalize()))
            role_item.setForeground(QColor(_CLR["text_secondary"]))
            self.user_table.setItem(i, 1, role_item)

            ip_item = QTableWidgetItem(u.get("ip", "Unknown"))
            ip_item.setForeground(QColor(_CLR["text_secondary"]))
            self.user_table.setItem(i, 2, ip_item)

            editing = bool(u.get("editing_ts_id"))
            status_text = _("Editing…") if editing else _("Idle")
            status_item = QTableWidgetItem(status_text)
            status_item.setForeground(QColor(_CLR["warning"]) if editing else QColor(_CLR["text_muted"]))
            self.user_table.setItem(i, 3, status_item)

        self.user_table.setRowHeight(0, 28)
        for r in range(self.user_table.rowCount()):
            self.user_table.setRowHeight(r, 28)

    def update_user_focus(self, username, ts_id):
        if username in self._user_data_map:
            self._user_data_map[username]["editing_ts_id"] = ts_id
            for row in range(self.user_table.rowCount()):
                if self.user_table.item(row, 0).data(Qt.UserRole) == username:
                    editing = bool(ts_id)
                    status_text = _("Editing…") if editing else _("Idle")
                    status_item = QTableWidgetItem(status_text)
                    status_item.setForeground(QColor(_CLR["warning"]) if editing else QColor(_CLR["text_muted"]))
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
        self.tabs.tabBar().setTabTextColor(1, QColor(_CLR["danger"]) if count > 0 else QColor(_CLR["text_secondary"]))

    def add_log(self, entry):
        time_str = entry.get("timestamp", "").split("T")[-1]
        if "." in time_str:
            time_str = time_str.rsplit(".", 1)[0]
        action = entry.get("action", "")
        user = entry.get("user", "System")

        def trunc(text, max_len=25):
            if not text:
                return "<i style='color:#94A3B8;'>empty</i>"
            text = str(text).replace("\n", "↵").replace("<", "&lt;").replace(">", "&gt;")
            return text[:max_len] + "…" if len(text) > max_len else text

        time_span = f"<span style='color:{_CLR['text_muted']};'>[{time_str}]</span>"
        user_span = f"<b style='color:{_CLR['text_primary']};'>{user}</b>"

        if action == "update_text":
            old_v = trunc(entry.get("old_value", ""))
            new_v = trunc(entry.get("new_value", ""))
            msg = (
                f"{time_span} {user_span}: "
                f"<span style='color:{_CLR['danger']}; text-decoration:line-through;'>{old_v}</span>"
                f" <span style='color:{_CLR['text_muted']};'>→</span> "
                f"<span style='color:{_CLR['success']};'>{new_v}</span>"
            )
        elif action == "update_status":
            old_s = _(entry.get("old_value", "None"))
            new_s = _(entry.get("new_value", "None"))
            msg = (
                f"{time_span} {user_span} "
                f"<span style='color:{_CLR['text_secondary']};'>{_('changed status')}</span>: "
                f"<span style='color:{_CLR['text_muted']};'>[{old_s}]</span> "
                f"<span style='color:{_CLR['text_muted']};'>→</span> "
                f"<span style='color:{_CLR['warning']};'>[{new_s}]</span>"
            )
        elif action == "login":
            msg = f"{time_span} {user_span} <span style='color:{_CLR['accent']};'>{_('joined the session')}</span>"
        elif action == "login_denied":
            msg = f"{time_span} {user_span} <span style='color:{_CLR['warning']};'>{_('was denied access')}</span>"
        else:
            return

        item = QListWidgetItem()
        item.setData(Qt.UserRole, entry.get("ts_id"))
        self.log_list.insertItem(0, item)

        lbl = QLabel(msg)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("background: transparent; border: none; padding: 2px;")
        lbl.setTextFormat(Qt.RichText)
        item.setSizeHint(lbl.sizeHint())
        self.log_list.setItemWidget(item, lbl)

        if self.log_list.count() > 100:
            self.log_list.takeItem(100)

        if not self.log_list.underMouse():
            self.red_dot.show()

    def load_history(self, entries):
        self.log_list.clear()
        for entry in reversed(entries):
            self.add_log(entry)
        self.red_dot.hide()

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
        menu.setStyleSheet(f"""
            QMenu {{ background: {_CLR["bg_panel"]}; border: 1px solid {_CLR["border"]}; padding: 4px; font-size: 12px; }}
            QMenu::item {{ padding: 6px 16px; color: {_CLR["text_primary"]}; }}
            QMenu::item:selected {{ background: {_CLR["table_sel"]}; color: {_CLR["accent"]}; }}
            QMenu::item:disabled {{ color: {_CLR["text_muted"]}; }}
            QMenu::separator {{ height: 1px; background: {_CLR["border"]}; margin: 4px 8px; }}
        """)

        ts_id = user_info.get("editing_ts_id")
        track_action = QAction(_("⌖  Track User (Locate row)"), self)
        if ts_id:
            track_action.triggered.connect(lambda: self.track_user_signal.emit(ts_id))
        else:
            track_action.setEnabled(False)
        menu.addAction(track_action)

        menu.addSeparator()

        kick_action = QAction(_("✕  Kick User"), self)
        kick_action.triggered.connect(
            lambda: self._confirm_action(
                _("Kick"),
                _("Are you sure you want to disconnect {u}?").format(u=username),
                lambda: self.kick_user_signal.emit(username),
            )
        )
        menu.addAction(kick_action)

        ip = user_info.get("ip")
        if ip and ip != "Unknown":
            ban_action = QAction(_("⊘  Ban IP ({ip})").format(ip=ip), self)
            if ip in ["127.0.0.1", "::1", "localhost"]:
                ban_action.setEnabled(False)
                ban_action.setText(ban_action.text() + _(" (Local)"))
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
