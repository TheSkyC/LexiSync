# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton
from PySide6.QtGui import QIcon, QColor, QCursor
from PySide6.QtCore import Qt, Signal, QSize, QEvent
from utils.path_utils import get_resource_path
from ui_components.tooltip import Tooltip

class OptionButton(QPushButton):
    def __init__(self, key, label, icon_name, color_hex="#409EFF", tooltip_text="", parent=None):
        super().__init__(parent)
        self.key = key
        self.color_hex = color_hex
        self.setCheckable(True)
        self.setText(label)

        self._tooltip_text = tooltip_text
        self._custom_tooltip = Tooltip(self)

        if icon_name:
            icon_path = get_resource_path(f"icons/{icon_name}")
            self.setIcon(QIcon(icon_path))
            self.setIconSize(QSize(14, 14))

        self.setCursor(Qt.PointingHandCursor)
        self._update_style()
        self.toggled.connect(self._update_style)

    def event(self, event):
        if event.type() == QEvent.Enter:
            if self._tooltip_text:
                self._custom_tooltip.show_tooltip(QCursor.pos(), self._tooltip_text, delay=500)
        elif event.type() == QEvent.Leave:
            self._custom_tooltip.hide()
        elif event.type() == QEvent.MouseButtonPress:
            self._custom_tooltip.hide()

        return super().event(event)

    def _update_style(self):
        # 动态生成样式，根据选中状态和自定义颜色
        base_color = QColor(self.color_hex)

        # 计算浅色背景
        light_bg = QColor(base_color)
        light_bg.setAlpha(30)  # 12% opacity roughly
        light_bg_str = f"rgba({base_color.red()}, {base_color.green()}, {base_color.blue()}, 0.1)"

        # 选中时的背景
        checked_bg_str = f"rgba({base_color.red()}, {base_color.green()}, {base_color.blue()}, 0.15)"

        css = f"""
            QPushButton {{
                background-color: #F2F3F5;
                border: 1px solid transparent;
                border-radius: 12px;
                padding: 4px 10px;
                color: #606266;
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: #E5E6EB;
            }}
            QPushButton:checked {{
                background-color: {checked_bg_str};
                color: {self.color_hex};
                border: 1px solid {self.color_hex};
            }}
        """
        self.setStyleSheet(css)


class OptionSelector(QWidget):
    selectionChanged = Signal(list)

    def __init__(self, options, parent=None):
        super().__init__(parent)
        self._buttons = {}
        self._options_config = options
        self.setup_ui()

    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        for option in self._options_config:
            key, label, icon, color = option[:4]
            tooltip = option[4] if len(option) > 4 else ""

            btn = OptionButton(key, label, icon, color, tooltip)
            btn.toggled.connect(self._on_button_toggled)
            layout.addWidget(btn)
            self._buttons[key] = btn

        layout.addStretch()

    def _on_button_toggled(self):
        self.selectionChanged.emit(self.get_selection())

    def get_selection(self) -> list:
        """获取当前选中的 key 列表"""
        return [key for key, btn in self._buttons.items() if btn.isChecked()]

    def set_selection(self, keys: list):
        """设置选中的 key"""
        self.blockSignals(True)
        for key, btn in self._buttons.items():
            btn.setChecked(key in (keys or []))
        self.blockSignals(False)

    def set_option_enabled(self, key, enabled):
        """启用或禁用特定选项"""
        if key in self._buttons:
            self._buttons[key].setEnabled(enabled)
            if not enabled:
                self._buttons[key].setChecked(False)