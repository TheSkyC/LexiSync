# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt, Signal, QSize
from utils.path_utils import get_resource_path
from utils.localization import _


class CapabilityButton(QPushButton):
    def __init__(self, key, label, icon_name, parent=None):
        super().__init__(parent)
        self.key = key
        self.setCheckable(True)
        self.setText(label)

        icon_path = get_resource_path(f"icons/{icon_name}")
        self.setIcon(QIcon(icon_path))
        self.setIconSize(QSize(14, 14))

        self.setCursor(Qt.PointingHandCursor)

        # 样式：选中时深色背景，未选中时浅色背景
        self.setStyleSheet("""
            QPushButton {
                background-color: #F2F3F5;
                border: none;
                border-radius: 12px;
                padding: 4px 10px;
                color: #606266;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #E5E6EB;
            }
            QPushButton:checked {
                background-color: #E6F7FF;
                color: #409EFF;
                border: 1px solid #BAE7FF;
            }
        """)


class CapabilitySelector(QWidget):
    # 当选择发生变化时发射信号，参数为选中的 key 列表
    selectionChanged = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._buttons = {}
        self.setup_ui()

    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # 定义能力类型
        capabilities = [
            ("vision", _("Vision"), "eye.svg"),
            ("reasoning", _("Reasoning"), "cpu.svg"),
            ("tools", _("Tools"), "tool.svg")
        ]

        for key, label, icon in capabilities:
            btn = CapabilityButton(key, label, icon)
            btn.toggled.connect(self._on_button_toggled)
            layout.addWidget(btn)
            self._buttons[key] = btn

        layout.addStretch()

    def _on_button_toggled(self):
        self.selectionChanged.emit(self.get_selection())

    def get_selection(self) -> list:
        """获取当前选中的能力列表"""
        return [key for key, btn in self._buttons.items() if btn.isChecked()]

    def set_selection(self, keys: list):
        """设置选中的能力"""
        self.blockSignals(True)
        for key, btn in self._buttons.items():
            btn.setChecked(key in (keys or []))
        self.blockSignals(False)