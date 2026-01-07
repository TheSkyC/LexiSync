# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QToolButton
from PySide6.QtCore import Signal, Qt, QSize
from PySide6.QtGui import QIcon, QCursor
from utils.path_utils import get_resource_path


class ToggleButton(QToolButton):
    toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setCheckable(True)
        self.setAutoRaise(True)
        self.setIconSize(QSize(24, 24))

        # 加载图标
        self.icon_on = QIcon(get_resource_path("icons/toggle-right.svg"))
        self.icon_off = QIcon(get_resource_path("icons/toggle-left.svg"))

        self.update_icon(False)
        self.clicked.connect(self._on_clicked)

        # 无边框样式
        self.setStyleSheet("""
            QToolButton {
                border: none;
                background: transparent;
                padding: 0px;
                margin: 0px;
            }
            QToolButton:pressed {
                padding: 0px; 
                background: transparent;
            }
        """)

    def _on_clicked(self):
        is_checked = self.isChecked()
        self.update_icon(is_checked)
        self.toggled.emit(is_checked)

    def update_icon(self, is_checked):
        self.setIcon(self.icon_on if is_checked else self.icon_off)

    def set_checked_silent(self, checked):
        self.blockSignals(True)
        self.setChecked(checked)
        self.update_icon(checked)
        self.blockSignals(False)