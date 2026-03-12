# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import hashlib
import secrets
import time
import uuid

from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from lexisync.utils.localization import _


def hash_password(password: str, salt: str | None = None) -> str:
    if not salt:
        salt = secrets.token_hex(8)
    h = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return f"{salt}${h}"


class CloudUserManagerDialog(QDialog):
    def __init__(self, parent, app_instance):
        super().__init__(parent)
        self.app = app_instance
        self.setWindowTitle(_("Cloud Collaboration Management"))
        self.resize(700, 500)
        self.setModal(True)

        # 确保配置存在
        if "cloud_users" not in self.app.config:
            self.app.config["cloud_users"] = []
        if "cloud_tokens" not in self.app.config:
            self.app.config["cloud_tokens"] = []

        # 如果没有任何用户，创建一个默认的 admin
        if not self.app.config["cloud_users"]:
            default_pwd = "admin"
            self.app.config["cloud_users"].append(
                {"username": "admin", "password_hash": hash_password(default_pwd), "role": "admin"}
            )
            self.app.save_config()
            QMessageBox.information(
                self,
                _("Notice"),
                _("No users found. A default 'admin' user has been created with password 'admin'. Please change it."),
            )

        self.users = self.app.config["cloud_users"]
        self.tokens = self.app.config["cloud_tokens"]

        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()

        # --- Tab 1: Users ---
        self.users_tab = QWidget()
        users_layout = QVBoxLayout(self.users_tab)

        self.users_table = QTableWidget(0, 3)
        self.users_table.setHorizontalHeaderLabels([_("Username"), _("Role"), _("Actions")])
        self.users_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.users_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.users_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.users_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.users_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        users_layout.addWidget(self.users_table)

        users_btn_layout = QHBoxLayout()
        add_user_btn = QPushButton(_("Add User"))
        add_user_btn.clicked.connect(self.add_user)
        users_btn_layout.addWidget(add_user_btn)
        users_btn_layout.addStretch()
        users_layout.addLayout(users_btn_layout)

        self.tabs.addTab(self.users_tab, _("Accounts"))

        # --- Tab 2: Tokens ---
        self.tokens_tab = QWidget()
        tokens_layout = QVBoxLayout(self.tokens_tab)

        self.tokens_table = QTableWidget(0, 4)
        self.tokens_table.setHorizontalHeaderLabels([_("Token"), _("Role"), _("Expires"), _("Description")])
        self.tokens_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tokens_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tokens_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tokens_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.tokens_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tokens_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tokens_layout.addWidget(self.tokens_table)

        tokens_btn_layout = QHBoxLayout()
        add_token_btn = QPushButton(_("Generate Token"))
        add_token_btn.clicked.connect(self.add_token)
        revoke_token_btn = QPushButton(_("Revoke Selected"))
        revoke_token_btn.clicked.connect(self.revoke_token)
        copy_link_btn = QPushButton(_("Copy Link"))
        copy_link_btn.clicked.connect(self.copy_token_link)

        tokens_btn_layout.addWidget(add_token_btn)
        tokens_btn_layout.addWidget(revoke_token_btn)
        tokens_btn_layout.addStretch()
        tokens_btn_layout.addWidget(copy_link_btn)
        tokens_layout.addLayout(tokens_btn_layout)

        self.tabs.addTab(self.tokens_tab, _("Access Tokens"))

        layout.addWidget(self.tabs)

        # Close Button
        close_btn = QPushButton(_("Close"))
        close_btn.clicked.connect(self.accept)
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        btn_box.addWidget(close_btn)
        layout.addLayout(btn_box)

        self.refresh_users_table()
        self.refresh_tokens_table()

    # --- User Methods ---
    def refresh_users_table(self):
        self.users_table.setRowCount(0)
        for idx, user in enumerate(self.users):
            self.users_table.insertRow(idx)
            self.users_table.setItem(idx, 0, QTableWidgetItem(user["username"]))
            self.users_table.setItem(idx, 1, QTableWidgetItem(user["role"]))

            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(2, 2, 2, 2)

            pwd_btn = QPushButton(_("Reset Password"))
            pwd_btn.clicked.connect(lambda checked, u=user["username"]: self.reset_password(u))
            del_btn = QPushButton(_("Delete"))
            del_btn.clicked.connect(lambda checked, u=user["username"]: self.delete_user(u))

            action_layout.addWidget(pwd_btn)
            action_layout.addWidget(del_btn)
            self.users_table.setCellWidget(idx, 2, action_widget)

    def add_user(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(_("Add User"))
        layout = QFormLayout(dialog)

        user_edit = QLineEdit()
        pwd_edit = QLineEdit()
        pwd_edit.setEchoMode(QLineEdit.Password)
        role_combo = QComboBox()
        role_combo.addItems(["admin", "reviewer", "translator", "viewer"])

        layout.addRow(_("Username:"), user_edit)
        layout.addRow(_("Password:"), pwd_edit)
        layout.addRow(_("Role:"), role_combo)

        btn_box = QHBoxLayout()
        save_btn = QPushButton(_("Save"))
        save_btn.clicked.connect(dialog.accept)
        btn_box.addWidget(save_btn)
        layout.addRow(btn_box)

        if dialog.exec():
            username = user_edit.text().strip()
            pwd = pwd_edit.text()
            if not username or not pwd:
                QMessageBox.warning(self, _("Error"), _("Username and password cannot be empty."))
                return
            if any(u["username"] == username for u in self.users):
                QMessageBox.warning(self, _("Error"), _("Username already exists."))
                return

            self.users.append(
                {"username": username, "password_hash": hash_password(pwd), "role": role_combo.currentText()}
            )
            self.save_data()

    def reset_password(self, username):
        new_pwd, ok = QInputDialog.getText(
            self, _("Reset Password"), _("Enter new password for {user}:").format(user=username), QLineEdit.Password
        )
        if ok and new_pwd:
            for u in self.users:
                if u["username"] == username:
                    u["password_hash"] = hash_password(new_pwd)
                    self.save_data()
                    QMessageBox.information(self, _("Success"), _("Password updated."))
                    break

    def delete_user(self, username):
        if username == "admin" and len([u for u in self.users if u["role"] == "admin"]) == 1:
            QMessageBox.warning(self, _("Error"), _("Cannot delete the last admin user."))
            return
        reply = QMessageBox.question(self, _("Confirm"), _("Delete user {user}?").format(user=username))
        if reply == QMessageBox.Yes:
            self.users = [u for u in self.users if u["username"] != username]
            self.save_data()

    # --- Token Methods ---
    def refresh_tokens_table(self):
        self.tokens_table.setRowCount(0)
        current_time = time.time()
        for idx, token_data in enumerate(self.tokens):
            self.tokens_table.insertRow(idx)
            self.tokens_table.setItem(idx, 0, QTableWidgetItem(token_data["token"]))
            self.tokens_table.setItem(idx, 1, QTableWidgetItem(token_data["role"]))

            exp = token_data.get("expires_at")
            if not exp:
                exp_str = _("Never")
            elif exp < current_time:
                exp_str = _("Expired")
            else:
                import datetime

                exp_str = datetime.datetime.fromtimestamp(exp).strftime("%Y-%m-%d %H:%M")

            self.tokens_table.setItem(idx, 2, QTableWidgetItem(exp_str))
            self.tokens_table.setItem(idx, 3, QTableWidgetItem(token_data.get("description", "")))

    def add_token(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(_("Generate Token"))
        layout = QFormLayout(dialog)

        role_combo = QComboBox()
        role_combo.addItems(["admin", "reviewer", "translator", "viewer"])

        exp_combo = QComboBox()
        exp_combo.addItem(_("1 Hour"), 3600)
        exp_combo.addItem(_("24 Hours"), 86400)
        exp_combo.addItem(_("7 Days"), 604800)
        exp_combo.addItem(_("Never"), 0)

        desc_edit = QLineEdit()
        desc_edit.setPlaceholderText(_("e.g., Temporary translator"))

        layout.addRow(_("Role:"), role_combo)
        layout.addRow(_("Expiration:"), exp_combo)
        layout.addRow(_("Description:"), desc_edit)

        btn_box = QHBoxLayout()
        save_btn = QPushButton(_("Generate"))
        save_btn.clicked.connect(dialog.accept)
        btn_box.addWidget(save_btn)
        layout.addRow(btn_box)

        if dialog.exec():
            token_val = str(uuid.uuid4()).replace("-", "")[:12]
            exp_seconds = exp_combo.currentData()
            expires_at = time.time() + exp_seconds if exp_seconds > 0 else None

            self.tokens.append(
                {
                    "token": token_val,
                    "role": role_combo.currentText(),
                    "expires_at": expires_at,
                    "description": desc_edit.text(),
                }
            )
            self.save_data()

            # 自动复制
            from PySide6.QtWidgets import QApplication

            QApplication.clipboard().setText(token_val)
            QMessageBox.information(
                self, _("Success"), _("Token generated and copied to clipboard:\n\n{token}").format(token=token_val)
            )

    def revoke_token(self):
        row = self.tokens_table.currentRow()
        if row < 0:
            return
        token_val = self.tokens_table.item(row, 0).text()
        reply = QMessageBox.question(self, _("Confirm"), _("Revoke this token?"))
        if reply == QMessageBox.Yes:
            self.tokens = [t for t in self.tokens if t["token"] != token_val]
            self.save_data()

    def copy_token_link(self):
        row = self.tokens_table.currentRow()
        if row < 0:
            return
        token_val = self.tokens_table.item(row, 0).text()
        import socket

        from PySide6.QtWidgets import QApplication

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            url = f"http://{local_ip}:20455?token={token_val}"
            QApplication.clipboard().setText(url)
            self.app.update_statusbar(_("Link copied to clipboard."))
        except Exception:
            self.app.update_statusbar(_("Failed to get local IP."))

    def save_data(self):
        self.app.config["cloud_users"] = self.users
        self.app.config["cloud_tokens"] = self.tokens
        self.app.save_config()
        self.refresh_users_table()
        self.refresh_tokens_table()

        # 通知运行中的服务器更新内存数据
        if self.app.web_service and self.app.web_service.isRunning():
            self.app.web_service.update_auth_data(self.users, self.tokens)
