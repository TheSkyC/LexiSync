# Copyright (c) 2025-2026, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from datetime import datetime
import hashlib
import secrets
import time
import uuid

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from lexisync.services.permissions import ALL_PERMISSIONS, DEFAULT_ROLE_PERMISSIONS
from lexisync.utils.localization import _

# ─── Constants ────────────────────────────────────────────────────────────────

AVAILABLE_ROLES = ["admin", "reviewer", "translator", "viewer"]

# ─── Helpers ──────────────────────────────────────────────────────────────────


def hash_password(password: str, salt: str | None = None) -> str:
    if not salt:
        salt = secrets.token_hex(8)
    h = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return f"{salt}${h}"


def _make_scroll(widget: QWidget) -> QScrollArea:
    sa = QScrollArea()
    sa.setWidgetResizable(True)
    sa.setFrameShape(QFrame.NoFrame)
    sa.setWidget(widget)
    return sa


# ─── Reusable Sub-Widgets ─────────────────────────────────────────────────────


class PermissionSelectorWidget(QWidget):
    def __init__(self, initial_grants: set[str] | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self._boxes: dict[str, QCheckBox] = {}
        self._manual_grants: set[str] = initial_grants if initial_grants is not None else set()
        self._inherited_perms: set[str] = set()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        for key, label in ALL_PERMISSIONS.items():
            cb = QCheckBox(_(label))
            self._boxes[key] = cb
            layout.addWidget(cb)
            cb.clicked.connect(lambda _, k=key: self._on_box_clicked(k))

        layout.addStretch()
        self._update_styles()

    def _on_box_clicked(self, key: str):
        cb = self._boxes[key]
        if key in self._inherited_perms:
            cb.setChecked(True)
            return

        if cb.isChecked():
            self._manual_grants.add(key)
        else:
            self._manual_grants.discard(key)
        self._update_styles()

    def set_data(self, manual_grants: set[str], inherited: set[str]):
        self._manual_grants = manual_grants
        self._inherited_perms = inherited
        self._update_styles()

    def set_role_preset(self, role: str):
        preset_perms = DEFAULT_ROLE_PERMISSIONS.get(role, set())
        self._manual_grants = set(preset_perms)
        self._update_styles()

    def _update_styles(self):
        for key, cb in self._boxes.items():
            cb.blockSignals(True)
            is_inherited = key in self._inherited_perms
            is_manual = key in self._manual_grants

            if is_inherited:
                cb.setChecked(True)
                cb.setStyleSheet("color: rgba(0, 0, 0, 100); font-style: italic;")
                cb.setText(_(ALL_PERMISSIONS[key]) + " " + _("(Inherited)"))
            elif is_manual:
                cb.setChecked(True)
                cb.setStyleSheet("color: #2563eb; font-weight: bold;")
                cb.setText(_(ALL_PERMISSIONS[key]))
            else:
                cb.setChecked(False)
                cb.setStyleSheet("")
                cb.setText(_(ALL_PERMISSIONS[key]))

            cb.blockSignals(False)

    def get_selected(self) -> list[str]:
        return list(self._manual_grants)

    def get_manual_grants(self) -> list[str]:
        return list(self._manual_grants)


class ScopeEditorWidget(QWidget):
    def __init__(self, scope: dict | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        lang_grp = QGroupBox(_("Language Scope  (empty = all languages)"))
        lang_ly = QVBoxLayout(lang_grp)
        hint_lang = QLabel(_("One BCP-47 / locale code per line, e.g.  zh_CN  /  ja_JP"))
        hint_lang.setStyleSheet("color: gray; font-size: 11px;")
        self.lang_edit = QTextEdit()
        self.lang_edit.setFixedHeight(80)
        self.lang_edit.setPlaceholderText("zh_CN\nja_JP\nde_DE")
        lang_ly.addWidget(hint_lang)
        lang_ly.addWidget(self.lang_edit)
        layout.addWidget(lang_grp)

        file_grp = QGroupBox(_("File Scope  (empty = all files, supports wildcards)"))
        file_ly = QVBoxLayout(file_grp)
        hint_file = QLabel(_("One pattern per line.  Examples:  messages.po  /  *.py  /  ui_*.ts"))
        hint_file.setStyleSheet("color: gray; font-size: 11px;")
        self.file_edit = QTextEdit()
        self.file_edit.setFixedHeight(80)
        self.file_edit.setPlaceholderText("messages.po\n*.py")
        file_ly.addWidget(hint_file)
        file_ly.addWidget(self.file_edit)
        layout.addWidget(file_grp)
        layout.addStretch()

        if scope:
            langs = scope.get("languages")
            if langs:
                self.lang_edit.setPlainText("\n".join(langs))
            files = scope.get("files")
            if files:
                self.file_edit.setPlainText("\n".join(files))

    def get_scope(self) -> dict | None:
        langs_raw = self.lang_edit.toPlainText().strip()
        files_raw = self.file_edit.toPlainText().strip()
        langs = [l.strip() for l in langs_raw.splitlines() if l.strip()] if langs_raw else None
        files = [f.strip() for f in files_raw.splitlines() if f.strip()] if files_raw else None
        if langs is None and files is None:
            return None
        return {"languages": langs, "files": files}


# ─── User Edit Dialog ─────────────────────────────────────────────────────────


class UserEditDialog(QDialog):
    def __init__(self, parent: QWidget, user_data: dict | None, groups: list[dict]):
        super().__init__(parent)
        self._user = user_data or {}
        self._groups = groups
        self._is_new = user_data is None
        self.setWindowTitle(
            _("Add User") if self._is_new else _("Edit User — {u}").format(u=self._user.get("username", ""))
        )
        self.setMinimumSize(520, 620)
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        tabs = QTabWidget()

        # ── Tab: Basic ──
        basic_w = QWidget()
        basic_l = QFormLayout(basic_w)
        basic_l.setRowWrapPolicy(QFormLayout.WrapAllRows)

        self.w_username = QLineEdit(self._user.get("username", ""))
        self.w_username.setReadOnly(not self._is_new)
        basic_l.addRow(_("Username:"), self.w_username)

        self.w_password = QLineEdit()
        self.w_password.setEchoMode(QLineEdit.Password)
        self.w_password.setPlaceholderText(_("Leave blank to keep current") if not self._is_new else "")
        basic_l.addRow(_("Password:"), self.w_password)

        self.w_role = QComboBox()
        self.w_role.addItems(AVAILABLE_ROLES)
        self.w_role.setCurrentText(self._user.get("role", "translator"))
        basic_l.addRow(_("Base Role:"), self.w_role)

        self.w_active = QCheckBox(_("Account is active"))
        self.w_active.setChecked(self._user.get("is_active", True))
        basic_l.addRow("", self.w_active)

        tabs.addTab(basic_w, _("Basic"))

        # ── Tab: Groups ──
        grp_w = QWidget()
        grp_l = QVBoxLayout(grp_w)
        grp_l.addWidget(QLabel(_("Group membership:")))
        self.w_groups = QListWidget()
        user_gids = set(self._user.get("groups", []))
        for g in self._groups:
            item = QListWidgetItem(g["name"])
            item.setData(Qt.UserRole, g["id"])
            item.setToolTip(g.get("description", ""))
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if g["id"] in user_gids else Qt.Unchecked)
            self.w_groups.addItem(item)
        grp_l.addWidget(self.w_groups)
        tabs.addTab(grp_w, _("Groups"))

        self.w_role.currentIndexChanged.connect(self._refresh_permission_previews)
        self.w_groups.itemChanged.connect(self._refresh_permission_previews)

        # ── Tab: Permissions ──
        cp_inner = QWidget()
        cp_l = QVBoxLayout(cp_inner)
        cp_l.addWidget(
            QLabel(
                _(
                    "These are applied ON TOP OF (or REMOVED FROM) the permissions\nthat come from the user's role + group memberships."
                )
            )
        )
        custom = self._user.get("custom_permissions") or {}

        grant_grp = QGroupBox(_("Extra Grant  ＋"))
        grant_layout = QVBoxLayout(grant_grp)
        self.w_grant = PermissionSelectorWidget(initial_grants=set(custom.get("grant", [])))
        grant_layout.addWidget(self.w_grant)
        cp_l.addWidget(grant_grp)

        revoke_grp = QGroupBox(_("Force Revoke  −"))
        revoke_layout = QVBoxLayout(revoke_grp)
        self.w_revoke = PermissionSelectorWidget(initial_grants=set(custom.get("revoke", [])))
        revoke_layout.addWidget(self.w_revoke)
        cp_l.addWidget(revoke_grp)

        cp_l.addStretch()
        tabs.addTab(_make_scroll(cp_inner), _("Permissions"))

        self._refresh_permission_previews()

        # ── Tab: Scope ──
        scope_inner = QWidget()
        sl = QVBoxLayout(scope_inner)
        self.w_scope = ScopeEditorWidget(self._user.get("scope"))
        sl.addWidget(self.w_scope)
        sl.addStretch()
        tabs.addTab(_make_scroll(scope_inner), _("Scope"))

        root.addWidget(tabs)
        self._add_ok_cancel(root)

    def _refresh_permission_previews(self):
        role = self.w_role.currentText()
        inherited = set(DEFAULT_ROLE_PERMISSIONS.get(role, set()))

        selected_group_ids = [
            self.w_groups.item(i).data(Qt.UserRole)
            for i in range(self.w_groups.count())
            if self.w_groups.item(i).checkState() == Qt.Checked
        ]

        for g_id in selected_group_ids:
            group_data = next((g for g in self._groups if g["id"] == g_id), None)
            if group_data:
                inherited.update(group_data.get("permissions", []))

        if hasattr(self, "w_grant"):
            current_manual = set(self.w_grant.get_selected())
            current_manual.difference_update(inherited)
            self.w_grant.set_data(current_manual, inherited)

    def _add_ok_cancel(self, layout: QVBoxLayout) -> None:
        bar = QHBoxLayout()
        bar.addStretch()
        ok_btn = QPushButton(_("Save"))
        ok_btn.clicked.connect(self.accept)
        cn_btn = QPushButton(_("Cancel"))
        cn_btn.clicked.connect(self.reject)
        bar.addWidget(ok_btn)
        bar.addWidget(cn_btn)
        layout.addLayout(bar)

    def get_data(self) -> dict:
        selected_groups = [
            self.w_groups.item(i).data(Qt.UserRole)
            for i in range(self.w_groups.count())
            if self.w_groups.item(i).checkState() == Qt.Checked
        ]
        data: dict = {
            "username": self.w_username.text().strip(),
            "role": self.w_role.currentText(),
            "is_active": self.w_active.isChecked(),
            "groups": selected_groups,
            "custom_permissions": {
                "grant": self.w_grant.get_selected(),
                "revoke": self.w_revoke.get_selected(),
            },
            "scope": self.w_scope.get_scope(),
        }
        pwd = self.w_password.text()
        if pwd:
            data["password_hash"] = hash_password(pwd)
        elif not self._is_new:
            data["password_hash"] = self._user.get("password_hash", "")
        return data


# ─── Group Edit Dialog ────────────────────────────────────────────────────────


class GroupEditDialog(QDialog):
    def __init__(self, parent: QWidget, group_data: dict | None, all_users: list[dict]):
        super().__init__(parent)
        self._group = group_data or {}
        self._all_users = all_users
        self._is_new = group_data is None
        self.setWindowTitle(
            _("New Group") if self._is_new else _("Edit Group — {n}").format(n=self._group.get("name", ""))
        )
        self.setMinimumSize(480, 600)
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        tabs = QTabWidget()

        # ── Tab: Basic ──
        basic_w = QWidget()
        basic_l = QFormLayout(basic_w)
        basic_l.setRowWrapPolicy(QFormLayout.WrapAllRows)

        self.w_name = QLineEdit(self._group.get("name", ""))
        self.w_name.setPlaceholderText(_("e.g.  CN Translation Team"))
        basic_l.addRow(_("Group Name:"), self.w_name)

        self.w_desc = QLineEdit(self._group.get("description", ""))
        basic_l.addRow(_("Description:"), self.w_desc)

        preset_row = QHBoxLayout()
        self.w_preset = QComboBox()
        self.w_preset.addItem(_("— apply role preset —"), "")
        for r in AVAILABLE_ROLES:
            self.w_preset.addItem(r, r)
        apply_btn = QPushButton(_("Apply"))
        apply_btn.clicked.connect(self._apply_preset)
        preset_row.addWidget(self.w_preset, 1)
        preset_row.addWidget(apply_btn)
        basic_l.addRow(_("Permission Preset:"), preset_row)
        tabs.addTab(basic_w, _("Basic"))

        # ── Tab: Members ──
        mem_w = QWidget()
        mem_l = QVBoxLayout(mem_w)
        mem_l.addWidget(QLabel(_("Select users to add to this group:")))
        self.w_members = QListWidget()
        gid = self._group.get("id")
        for u in self._all_users:
            item = QListWidgetItem(u["username"])
            item.setData(Qt.UserRole, u["username"])
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            is_member = gid in u.get("groups", []) if gid else False
            item.setCheckState(Qt.Checked if is_member else Qt.Unchecked)
            self.w_members.addItem(item)
        mem_l.addWidget(self.w_members)
        tabs.addTab(mem_w, _("Members"))

        # ── Tab: Permissions ──
        perm_inner = QWidget()
        pl = QVBoxLayout(perm_inner)
        self.w_perms = PermissionSelectorWidget(initial_grants=set(self._group.get("permissions", [])))
        pl.addWidget(self.w_perms)
        pl.addStretch()
        tabs.addTab(_make_scroll(perm_inner), _("Permissions"))

        # ── Tab: Scope ──
        scope_inner = QWidget()
        sl = QVBoxLayout(scope_inner)
        self.w_scope = ScopeEditorWidget(self._group.get("scope"))
        sl.addWidget(self.w_scope)
        sl.addStretch()
        tabs.addTab(_make_scroll(scope_inner), _("Scope"))

        root.addWidget(tabs)
        self._add_ok_cancel(root)

    def _apply_preset(self) -> None:
        role = self.w_preset.currentData()
        if role:
            self.w_perms.set_role_preset(role)

    def _add_ok_cancel(self, layout: QVBoxLayout) -> None:
        bar = QHBoxLayout()
        bar.addStretch()
        ok_btn = QPushButton(_("Save"))
        ok_btn.clicked.connect(self.accept)
        cn_btn = QPushButton(_("Cancel"))
        cn_btn.clicked.connect(self.reject)
        bar.addWidget(ok_btn)
        bar.addWidget(cn_btn)
        layout.addLayout(bar)

    def get_data(self) -> tuple[dict, list[str]]:
        group_dict = {
            "id": self._group.get("id", str(uuid.uuid4())),
            "name": self.w_name.text().strip(),
            "description": self.w_desc.text().strip(),
            "permissions": self.w_perms.get_selected(),
            "scope": self.w_scope.get_scope(),
        }
        selected_users = [
            self.w_members.item(i).data(Qt.UserRole)
            for i in range(self.w_members.count())
            if self.w_members.item(i).checkState() == Qt.Checked
        ]
        return group_dict, selected_users


# ─── Token Generate Dialog ────────────────────────────────────────────────────


class TokenGenerateDialog(QDialog):
    def __init__(self, parent: QWidget, groups: list[dict]):
        super().__init__(parent)
        self._groups = groups
        self.setWindowTitle(_("Generate Access Token"))
        self.setMinimumSize(520, 640)
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        tabs = QTabWidget()

        # ── Tab: Basic ──
        basic_w = QWidget()
        basic_l = QFormLayout(basic_w)
        basic_l.setRowWrapPolicy(QFormLayout.WrapAllRows)

        self.w_role = QComboBox()
        self.w_role.addItems(AVAILABLE_ROLES)
        basic_l.addRow(_("Base Role:"), self.w_role)

        self.w_exp = QComboBox()
        self.w_exp.addItem(_("1 Hour"), 3600)
        self.w_exp.addItem(_("12 Hours"), 43200)
        self.w_exp.addItem(_("24 Hours"), 86400)
        self.w_exp.addItem(_("7 Days"), 604800)
        self.w_exp.addItem(_("30 Days"), 2592000)
        self.w_exp.addItem(_("Never"), 0)
        basic_l.addRow(_("Expiration:"), self.w_exp)

        self.w_max_uses = QSpinBox()
        self.w_max_uses.setRange(0, 9999)
        self.w_max_uses.setValue(0)
        self.w_max_uses.setSpecialValueText(_("Unlimited"))
        self.w_max_uses.setToolTip(_("0 = unlimited uses"))
        basic_l.addRow(_("Max Uses:"), self.w_max_uses)

        self.w_desc = QLineEdit()
        self.w_desc.setPlaceholderText(_("e.g. Temporary translator for Acme project"))
        basic_l.addRow(_("Description:"), self.w_desc)

        tabs.addTab(basic_w, _("Basic"))

        # ── Tab: Security ──
        sec_w = QWidget()
        sec_l = QVBoxLayout(sec_w)

        ip_grp = QGroupBox(_("IP Whitelist  (empty = allow any IP)"))
        ip_ly = QVBoxLayout(ip_grp)
        ip_hint = QLabel(
            _("One IP address or wildcard pattern per line.\nExamples:  192.168.1.*  /  10.0.0.5  /  172.16.*.*")
        )
        ip_hint.setStyleSheet("color: gray; font-size: 11px;")
        ip_hint.setWordWrap(True)
        self.w_ip = QTextEdit()
        self.w_ip.setFixedHeight(100)
        self.w_ip.setPlaceholderText("192.168.1.*\n10.0.0.42")
        ip_ly.addWidget(ip_hint)
        ip_ly.addWidget(self.w_ip)
        sec_l.addWidget(ip_grp)
        sec_l.addStretch()
        tabs.addTab(sec_w, _("Security"))

        # ── Tab: Permissions ──
        perm_w = QWidget()
        perm_l = QVBoxLayout(perm_w)
        self.w_override_perms = QCheckBox(_("Override role with explicit permission list"))
        self.w_override_perms.setToolTip(
            _(
                "When checked, the token ignores the role's default permissions\nand uses exactly the permissions you select below."
            )
        )
        perm_l.addWidget(self.w_override_perms)

        perm_inner = QWidget()
        pil = QVBoxLayout(perm_inner)
        self.w_perms = PermissionSelectorWidget()
        self.w_perms.setEnabled(False)
        self.w_perms.set_role_preset(self.w_role.currentText())
        pil.addWidget(self.w_perms)
        pil.addStretch()
        perm_l.addWidget(_make_scroll(perm_inner))

        self.w_override_perms.toggled.connect(self.w_perms.setEnabled)
        self.w_override_perms.toggled.connect(
            lambda checked: self.w_perms.set_role_preset(self.w_role.currentText()) if not checked else None
        )
        self.w_role.currentTextChanged.connect(
            lambda r: self.w_perms.set_role_preset(r) if not self.w_override_perms.isChecked() else None
        )
        tabs.addTab(perm_w, _("Permissions"))

        # ── Tab: Scope ──
        scope_inner = QWidget()
        sl = QVBoxLayout(scope_inner)
        self.w_scope = ScopeEditorWidget()
        sl.addWidget(self.w_scope)
        sl.addStretch()
        tabs.addTab(_make_scroll(scope_inner), _("Scope"))

        root.addWidget(tabs)

        bar = QHBoxLayout()
        bar.addStretch()
        ok_btn = QPushButton(_("Generate"))
        ok_btn.clicked.connect(self.accept)
        cn_btn = QPushButton(_("Cancel"))
        cn_btn.clicked.connect(self.reject)
        bar.addWidget(ok_btn)
        bar.addWidget(cn_btn)
        root.addLayout(bar)

    def get_data(self) -> dict:
        ip_text = self.w_ip.toPlainText().strip()
        ip_whitelist = [ip.strip() for ip in ip_text.splitlines() if ip.strip()] or None

        exp_secs = self.w_exp.currentData()
        expires_at = time.time() + exp_secs if exp_secs > 0 else None

        permissions = self.w_perms.get_selected() if self.w_override_perms.isChecked() else None

        max_uses = self.w_max_uses.value()
        return {
            "token": str(uuid.uuid4()).replace("-", "")[:16],
            "role": self.w_role.currentText(),
            "expires_at": expires_at,
            "description": self.w_desc.text().strip(),
            "max_uses": max_uses if max_uses > 0 else None,
            "use_count": 0,
            "ip_whitelist": ip_whitelist,
            "permissions": permissions,
            "scope": self.w_scope.get_scope(),
        }


# ─── Main Dialog ──────────────────────────────────────────────────────────────


class CloudUserManagerDialog(QDialog):
    def __init__(self, parent: QWidget, app_instance):
        super().__init__(parent)
        self.app = app_instance
        self.setWindowTitle(_("Cloud Collaboration Management"))
        self.resize(860, 620)
        self.setModal(True)

        for key, default in [("cloud_users", []), ("cloud_tokens", []), ("cloud_groups", [])]:
            if key not in self.app.config:
                self.app.config[key] = default

        if not self.app.config["cloud_users"]:
            self.app.config["cloud_users"].append(
                {
                    "username": "admin",
                    "password_hash": hash_password("admin"),
                    "role": "admin",
                    "is_active": True,
                    "groups": [],
                    "custom_permissions": {},
                    "scope": None,
                }
            )
            self.app.save_config()
            QMessageBox.information(
                self,
                _("Notice"),
                _(
                    "No users found. A default 'admin' user has been created with password 'admin'. Please change it immediately."
                ),
            )

        self.users: list[dict] = self.app.config["cloud_users"]
        self.tokens: list[dict] = self.app.config["cloud_tokens"]
        self.groups: list[dict] = self.app.config["cloud_groups"]

        self._build_ui()

    def _filter_table(self, table: QTableWidget, text: str):
        text = text.lower()
        for row in range(table.rowCount()):
            match = False
            for col in range(table.columnCount() - 1):  # Skip actions column
                item = table.item(row, col)
                if item and text in item.text().lower():
                    match = True
                    break
            table.setRowHidden(row, not match)

    # ── UI assembly ───────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self._on_tab_changed)

        self._build_users_tab()
        self._build_groups_tab()
        self._build_tokens_tab()
        self._build_audit_tab()

        root.addWidget(self.tabs)

        bar = QHBoxLayout()
        bar.addStretch()
        close_btn = QPushButton(_("Close"))
        close_btn.clicked.connect(self.accept)
        bar.addWidget(close_btn)
        root.addLayout(bar)

        self._refresh_all()

    # ── Users tab ─────────────────────────────────────────────────────────────

    def _build_users_tab(self) -> None:
        w = QWidget()
        ly = QVBoxLayout(w)

        search_ly = QHBoxLayout()
        self.search_users = QLineEdit()
        self.search_users.setPlaceholderText(_("Search users..."))
        self.search_users.textChanged.connect(lambda text: self._filter_table(self.tbl_users, text))
        search_ly.addWidget(self.search_users)
        ly.addLayout(search_ly)

        self.tbl_users = QTableWidget(0, 5)
        self.tbl_users.setHorizontalHeaderLabels([_("Username"), _("Role"), _("Groups"), _("Status"), _("Actions")])
        hdr = self.tbl_users.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.Stretch)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.tbl_users.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_users.setEditTriggers(QAbstractItemView.NoEditTriggers)
        ly.addWidget(self.tbl_users)

        btns = QHBoxLayout()
        add_btn = QPushButton(_("Add User"))
        add_btn.clicked.connect(self._add_user)
        btns.addWidget(add_btn)
        btns.addStretch()
        ly.addLayout(btns)

        self.tabs.addTab(w, _("Accounts"))

    def _refresh_users_table(self) -> None:
        self.tbl_users.setRowCount(0)
        for idx, user in enumerate(self.users):
            self.tbl_users.insertRow(idx)
            self.tbl_users.setItem(idx, 0, QTableWidgetItem(user["username"]))
            self.tbl_users.setItem(idx, 1, QTableWidgetItem(user["role"]))

            gids = set(user.get("groups", []))
            gnames = ", ".join(g["name"] for g in self.groups if g["id"] in gids) or "—"
            self.tbl_users.setItem(idx, 2, QTableWidgetItem(gnames))

            is_active = user.get("is_active", True)
            status_text = _("Active") if is_active else _("Disabled")
            status_item = QTableWidgetItem(status_text)
            status_item.setForeground(QColor("green") if is_active else QColor("red"))
            self.tbl_users.setItem(idx, 3, status_item)

            aw = QWidget()
            al = QHBoxLayout(aw)
            al.setContentsMargins(2, 2, 2, 2)
            eb = QPushButton(_("Edit"))
            eb.clicked.connect(lambda _, u=user["username"]: self._edit_user(u))
            db = QPushButton(_("Delete"))
            db.clicked.connect(lambda _, u=user["username"]: self._delete_user(u))
            al.addWidget(eb)
            al.addWidget(db)
            self.tbl_users.setCellWidget(idx, 4, aw)
        self._filter_table(self.tbl_users, self.search_users.text())

    def _add_user(self) -> None:
        dlg = UserEditDialog(self, None, self.groups)
        if not dlg.exec():
            return
        data = dlg.get_data()
        if not data["username"]:
            QMessageBox.warning(self, _("Error"), _("Username cannot be empty."))
            return
        if not data.get("password_hash"):
            QMessageBox.warning(self, _("Error"), _("Password cannot be empty for a new user."))
            return
        if any(u["username"] == data["username"] for u in self.users):
            QMessageBox.warning(self, _("Error"), _("Username already exists."))
            return
        self.users.append(data)
        self._save()

    def _edit_user(self, username: str) -> None:
        user = next((u for u in self.users if u["username"] == username), None)
        if not user:
            return
        dlg = UserEditDialog(self, dict(user), self.groups)
        if not dlg.exec():
            return
        data = dlg.get_data()
        data["username"] = username  # username is immutable
        for i, u in enumerate(self.users):
            if u["username"] == username:
                self.users[i] = data
                break
        self._save()

    def _delete_user(self, username: str) -> None:
        admins = [u for u in self.users if u["role"] == "admin"]
        if len(admins) == 1 and admins[0]["username"] == username:
            QMessageBox.warning(self, _("Error"), _("Cannot delete the last admin user."))
            return
        if QMessageBox.question(self, _("Confirm"), _("Delete user '{u}'?").format(u=username)) == QMessageBox.Yes:
            self.users = [u for u in self.users if u["username"] != username]
            self._save()

    # ── Groups tab ────────────────────────────────────────────────────────────

    def _build_groups_tab(self) -> None:
        w = QWidget()
        ly = QVBoxLayout(w)

        search_ly = QHBoxLayout()
        self.search_groups = QLineEdit()
        self.search_groups.setPlaceholderText(_("Search groups..."))
        self.search_groups.textChanged.connect(lambda text: self._filter_table(self.tbl_groups, text))
        search_ly.addWidget(self.search_groups)
        ly.addLayout(search_ly)

        self.tbl_groups = QTableWidget(0, 3)
        self.tbl_groups.setHorizontalHeaderLabels([_("Name"), _("Description"), _("Actions")])
        hdr = self.tbl_groups.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tbl_groups.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_groups.setEditTriggers(QAbstractItemView.NoEditTriggers)
        ly.addWidget(self.tbl_groups)

        btns = QHBoxLayout()
        add_btn = QPushButton(_("New Group"))
        add_btn.clicked.connect(self._add_group)
        btns.addWidget(add_btn)
        btns.addStretch()
        ly.addLayout(btns)

        self.tabs.addTab(w, _("Groups / Organizations"))

    def _refresh_groups_table(self) -> None:
        self.tbl_groups.setRowCount(0)
        for idx, g in enumerate(self.groups):
            self.tbl_groups.insertRow(idx)
            self.tbl_groups.setItem(idx, 0, QTableWidgetItem(g["name"]))
            self.tbl_groups.setItem(idx, 1, QTableWidgetItem(g.get("description", "")))

            aw = QWidget()
            al = QHBoxLayout(aw)
            al.setContentsMargins(2, 2, 2, 2)
            eb = QPushButton(_("Edit"))
            eb.clicked.connect(lambda _, gid=g["id"]: self._edit_group(gid))
            db = QPushButton(_("Delete"))
            db.clicked.connect(lambda _, gid=g["id"]: self._delete_group(gid))
            al.addWidget(eb)
            al.addWidget(db)
            self.tbl_groups.setCellWidget(idx, 2, aw)
        self._filter_table(self.tbl_groups, self.search_groups.text())

    def _update_group_members(self, gid: str, members: list[str]):
        for u in self.users:
            u_groups = u.get("groups", [])
            if u["username"] in members:
                if gid not in u_groups:
                    u_groups.append(gid)
            elif gid in u_groups:
                u_groups.remove(gid)
            u["groups"] = u_groups

    def _add_group(self) -> None:
        dlg = GroupEditDialog(self, None, self.users)
        if not dlg.exec():
            return
        g_data, members = dlg.get_data()
        if not g_data["name"]:
            QMessageBox.warning(self, _("Error"), _("Group name cannot be empty."))
            return
        self.groups.append(g_data)
        self._update_group_members(g_data["id"], members)
        self._save()

    def _edit_group(self, gid: str) -> None:
        g = next((g for g in self.groups if g["id"] == gid), None)
        if not g:
            return
        dlg = GroupEditDialog(self, dict(g), self.users)
        if not dlg.exec():
            return
        g_data, members = dlg.get_data()
        g_data["id"] = gid
        for i, gr in enumerate(self.groups):
            if gr["id"] == gid:
                self.groups[i] = g_data
                break
        self._update_group_members(gid, members)
        self._save()

    def _delete_group(self, gid: str) -> None:
        g = next((gr for gr in self.groups if gr["id"] == gid), None)
        if not g:
            return
        if (
            QMessageBox.question(
                self,
                _("Confirm"),
                _("Delete group '{n}'?\nMembers will lose the group's permissions.").format(n=g["name"]),
            )
            != QMessageBox.Yes
        ):
            return
        self.groups = [gr for gr in self.groups if gr["id"] != gid]
        for u in self.users:
            u["groups"] = [x for x in u.get("groups", []) if x != gid]
        self._save()

    # ── Tokens tab ────────────────────────────────────────────────────────────

    def _build_tokens_tab(self) -> None:
        w = QWidget()
        ly = QVBoxLayout(w)

        search_ly = QHBoxLayout()
        self.search_tokens = QLineEdit()
        self.search_tokens.setPlaceholderText(_("Search tokens..."))
        self.search_tokens.textChanged.connect(lambda text: self._filter_table(self.tbl_tokens, text))
        search_ly.addWidget(self.search_tokens)
        ly.addLayout(search_ly)

        self.tbl_tokens = QTableWidget(0, 6)
        self.tbl_tokens.setHorizontalHeaderLabels(
            [_("Token"), _("Role"), _("Expires"), _("Uses"), _("IP Whitelist"), _("Description")]
        )
        hdr = self.tbl_tokens.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(5, QHeaderView.Stretch)
        self.tbl_tokens.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_tokens.setEditTriggers(QAbstractItemView.NoEditTriggers)
        ly.addWidget(self.tbl_tokens)

        btns = QHBoxLayout()
        gen_btn = QPushButton(_("Generate Token"))
        gen_btn.clicked.connect(self._add_token)
        revoke_btn = QPushButton(_("Revoke Selected"))
        revoke_btn.clicked.connect(self._revoke_token)
        revoke_exp_btn = QPushButton(_("Revoke Expired"))
        revoke_exp_btn.clicked.connect(self._revoke_expired_tokens)
        link_btn = QPushButton(_("Copy Login Link"))
        link_btn.clicked.connect(self._copy_link)

        btns.addWidget(gen_btn)
        btns.addWidget(revoke_btn)
        btns.addWidget(revoke_exp_btn)
        btns.addStretch()
        btns.addWidget(link_btn)
        ly.addLayout(btns)

        self.tabs.addTab(w, _("Access Tokens"))

    def _refresh_tokens_table(self) -> None:
        self.tbl_tokens.setRowCount(0)
        now = time.time()
        for idx, t in enumerate(self.tokens):
            self.tbl_tokens.insertRow(idx)
            self.tbl_tokens.setItem(idx, 0, QTableWidgetItem(t["token"]))
            self.tbl_tokens.setItem(idx, 1, QTableWidgetItem(t["role"]))

            exp = t.get("expires_at")
            if not exp:
                exp_str = _("Never")
            elif exp < now:
                exp_str = _("⚠ Expired")
            else:
                exp_str = datetime.fromtimestamp(exp).strftime("%Y-%m-%d %H:%M")
            self.tbl_tokens.setItem(idx, 2, QTableWidgetItem(exp_str))

            max_u = t.get("max_uses")
            use_c = t.get("use_count", 0)
            uses_str = f"{use_c} / {max_u}" if max_u else f"{use_c} / ∞"
            self.tbl_tokens.setItem(idx, 3, QTableWidgetItem(uses_str))

            ips = t.get("ip_whitelist")
            self.tbl_tokens.setItem(idx, 4, QTableWidgetItem(", ".join(ips) if ips else _("Any")))
            self.tbl_tokens.setItem(idx, 5, QTableWidgetItem(t.get("description", "")))
        self._filter_table(self.tbl_tokens, self.search_tokens.text())

    def _add_token(self) -> None:
        dlg = TokenGenerateDialog(self, self.groups)
        if not dlg.exec():
            return
        data = dlg.get_data()
        self.tokens.append(data)
        self._save()
        QApplication.clipboard().setText(data["token"])
        QMessageBox.information(
            self,
            _("Success"),
            _("Token generated and copied to clipboard:\n\n{token}").format(token=data["token"]),
        )

    def _revoke_token(self) -> None:
        row = self.tbl_tokens.currentRow()
        if row < 0:
            return
        val = self.tbl_tokens.item(row, 0).text()
        if QMessageBox.question(self, _("Confirm"), _("Revoke this token?")) == QMessageBox.Yes:
            self.tokens = [t for t in self.tokens if t["token"] != val]
            self._save()

    def _revoke_expired_tokens(self) -> None:
        now = time.time()
        valid_tokens = []
        revoked_count = 0
        for t in self.tokens:
            if t.get("expires_at") and t["expires_at"] < now:
                revoked_count += 1
            else:
                valid_tokens.append(t)

        if revoked_count > 0:
            self.tokens = valid_tokens
            self._save()
            QMessageBox.information(self, _("Success"), _("Revoked {n} expired tokens.").format(n=revoked_count))
        else:
            QMessageBox.information(self, _("Info"), _("No expired tokens found."))

    def _copy_link(self) -> None:
        row = self.tbl_tokens.currentRow()
        if row < 0:
            return
        val = self.tbl_tokens.item(row, 0).text()
        import socket

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            url = f"http://{local_ip}:20455?token={val}"
            QApplication.clipboard().setText(url)
            self.app.update_statusbar(_("Link copied to clipboard."))
        except Exception:
            self.app.update_statusbar(_("Failed to get local IP."))

    # ── Audit Log tab ──────────────────────────────────────────────────────────

    def _build_audit_tab(self) -> None:
        w = QWidget()
        ly = QVBoxLayout(w)

        # Filter bar
        fb = QHBoxLayout()
        fb.addWidget(QLabel(_("User:")))
        self.w_audit_user = QLineEdit()
        self.w_audit_user.setPlaceholderText(_("all"))
        self.w_audit_user.setMaximumWidth(130)
        fb.addWidget(self.w_audit_user)
        fb.addWidget(QLabel(_("Action:")))
        self.w_audit_action = QComboBox()
        self.w_audit_action.addItem(_("All"), "")
        for a in ["login", "login_denied", "update_text", "update_status"]:
            self.w_audit_action.addItem(a, a)
        fb.addWidget(self.w_audit_action)
        refresh_btn = QPushButton(_("Refresh"))
        refresh_btn.clicked.connect(self._refresh_audit)
        fb.addWidget(refresh_btn)
        clear_btn = QPushButton(_("Clear"))
        clear_btn.clicked.connect(self._clear_audit)
        fb.addWidget(clear_btn)
        fb.addStretch()
        ly.addLayout(fb)

        self.tbl_audit = QTableWidget(0, 7)
        self.tbl_audit.setHorizontalHeaderLabels(
            [_("Time"), _("User"), _("Action"), _("IP"), _("Entry ID"), _("Old Value"), _("New Value")]
        )
        hdr = self.tbl_audit.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(5, QHeaderView.Stretch)
        hdr.setSectionResizeMode(6, QHeaderView.Stretch)
        self.tbl_audit.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_audit.setEditTriggers(QAbstractItemView.NoEditTriggers)
        ly.addWidget(self.tbl_audit)

        self.tabs.addTab(w, _("Audit Log"))

    def _refresh_audit(self) -> None:
        if not (self.app.web_service and self.app.web_service.isRunning()):
            self.tbl_audit.setRowCount(0)
            return
        uf = self.w_audit_user.text().strip() or None
        af = self.w_audit_action.currentData() or None
        entries = self.app.web_service.audit_log.get_entries(limit=500, user=uf, action=af)

        self.tbl_audit.setRowCount(0)
        for idx, e in enumerate(entries):
            self.tbl_audit.insertRow(idx)
            ts = e.get("timestamp", "")
            try:
                ts = datetime.fromisoformat(ts).strftime("%m-%d %H:%M:%S")
            except Exception:
                pass
            self.tbl_audit.setItem(idx, 0, QTableWidgetItem(ts))
            self.tbl_audit.setItem(idx, 1, QTableWidgetItem(e.get("user", "")))
            self.tbl_audit.setItem(idx, 2, QTableWidgetItem(e.get("action", "")))
            self.tbl_audit.setItem(idx, 3, QTableWidgetItem(e.get("ip", "")))
            self.tbl_audit.setItem(idx, 4, QTableWidgetItem(str(e.get("ts_id") or "")))
            self.tbl_audit.setItem(idx, 5, QTableWidgetItem(str(e.get("old_value") or "")[:100]))
            self.tbl_audit.setItem(idx, 6, QTableWidgetItem(str(e.get("new_value") or "")[:100]))

    def _clear_audit(self) -> None:
        if not (self.app.web_service and self.app.web_service.isRunning()):
            return
        if QMessageBox.question(self, _("Confirm"), _("Clear all audit log entries?")) == QMessageBox.Yes:
            self.app.web_service.audit_log.clear()
            self._refresh_audit()

    # ── Plumbing ──────────────────────────────────────────────────────────────

    def _on_tab_changed(self, idx: int) -> None:
        if self.tabs.widget(idx) is self.tabs.widget(3):  # Audit tab
            self._refresh_audit()

    def _refresh_all(self) -> None:
        self._refresh_users_table()
        self._refresh_groups_table()
        self._refresh_tokens_table()

    def _save(self) -> None:
        self.app.config["cloud_users"] = self.users
        self.app.config["cloud_tokens"] = self.tokens
        self.app.config["cloud_groups"] = self.groups
        self.app.save_config()
        self._refresh_all()
        # Hot-reload running server
        if self.app.web_service and self.app.web_service.isRunning():
            self.app.web_service.update_auth_data(self.users, self.tokens, self.groups)
