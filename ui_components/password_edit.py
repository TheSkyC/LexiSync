# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QLineEdit, QToolButton, QStyle
from PySide6.QtGui import QIcon, Qt, QCursor
from PySide6.QtCore import QSize, Slot
from utils.path_utils import get_resource_path
from utils.localization import _


class PasswordEdit(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setEchoMode(QLineEdit.Password)

        self.setInputMethodHints(
            Qt.ImhHiddenText |
            Qt.ImhNoPredictiveText |
            Qt.ImhNoAutoUppercase |
            Qt.ImhSensitiveData
        )

        self._toggle_button = QToolButton(self)
        self._toggle_button.setCursor(QCursor(Qt.ArrowCursor))
        self._toggle_button.setFocusPolicy(Qt.NoFocus)

        # 加载图标
        self._icon_eye = QIcon(get_resource_path("icons/eye.svg"))
        self._icon_eye_off = QIcon(get_resource_path("icons/eye-off.svg"))

        # 初始化按钮状态
        self._toggle_button.setIcon(self._icon_eye_off)
        self._toggle_button.setToolTip(_("Show Password"))
        self._toggle_button.clicked.connect(self._on_toggle)

        self.setStyleSheet("""
            QLineEdit {
                padding-right: 30px; 
            }
            QToolButton {
                border: none;
                background: transparent;
                padding: 0px;
                border-radius: 4px;
                opacity: 0.4;
            }
            QToolButton:hover {
                opacity: 1.0;
            }
            QToolButton:pressed {
                background-color: rgba(0, 0, 0, 0.05);
            }
        """)

    def resizeEvent(self, event):
        super().resizeEvent(event)

        button_height = self.height()
        button_width = 30

        self._toggle_button.setGeometry(
            self.width() - button_width,
            0,
            button_width,
            button_height
        )

    @Slot()
    def _on_toggle(self):
        cursor_pos = self.cursorPosition()

        if self.echoMode() == QLineEdit.Password:
            self.setEchoMode(QLineEdit.Normal)
            self._toggle_button.setIcon(self._icon_eye)
            self._toggle_button.setToolTip(_("Hide Password"))
        else:
            self.setEchoMode(QLineEdit.Password)
            self._toggle_button.setIcon(self._icon_eye_off)
            self._toggle_button.setToolTip(_("Show Password"))

        self.setCursorPosition(cursor_pos)
        self.setFocus()