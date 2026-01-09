# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton
from PySide6.QtGui import QIcon, QColor, QCursor
from PySide6.QtCore import (Qt, Signal, QSize, QEvent, QPropertyAnimation, QEasingCurve,
                            Property, QParallelAnimationGroup)
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

        # 背景色动画属性
        self._bg_opacity = 0.0
        self._border_opacity = 0.0

        # 动画组
        self._animation_group = None

        if icon_name:
            icon_path = get_resource_path(f"icons/{icon_name}")
            self.setIcon(QIcon(icon_path))
            self.setIconSize(QSize(14, 14))

        self.setCursor(Qt.PointingHandCursor)
        self._update_style()
        self.toggled.connect(self._on_toggled)

    def event(self, event):
        if event.type() == QEvent.Enter:
            if self._tooltip_text:
                self._custom_tooltip.show_tooltip(QCursor.pos(), self._tooltip_text, delay=500)
        elif event.type() == QEvent.Leave:
            self._custom_tooltip.hide()
        elif event.type() == QEvent.MouseButtonPress:
            self._custom_tooltip.hide()

        return super().event(event)

    def _on_toggled(self, checked):
        """选中状态切换时的动画"""
        # 停止之前的动画
        if self._animation_group:
            self._animation_group.stop()

        self._animation_group = QParallelAnimationGroup(self)

        # 背景透明度动画
        bg_anim = QPropertyAnimation(self, b"bg_opacity")
        bg_anim.setDuration(250)
        bg_anim.setEasingCurve(QEasingCurve.OutCubic)
        bg_anim.setStartValue(self._bg_opacity)
        bg_anim.setEndValue(0.15 if checked else 0.0)

        # 边框透明度动画
        border_anim = QPropertyAnimation(self, b"border_opacity")
        border_anim.setDuration(250)
        border_anim.setEasingCurve(QEasingCurve.OutCubic)
        border_anim.setStartValue(self._border_opacity)
        border_anim.setEndValue(1.0 if checked else 0.0)

        self._animation_group.addAnimation(bg_anim)
        self._animation_group.addAnimation(border_anim)
        self._animation_group.start()

    def get_bg_opacity(self):
        return self._bg_opacity

    def set_bg_opacity(self, value):
        self._bg_opacity = value
        self._update_style()

    bg_opacity = Property(float, get_bg_opacity, set_bg_opacity)

    def get_border_opacity(self):
        return self._border_opacity

    def set_border_opacity(self, value):
        self._border_opacity = value
        self._update_style()

    border_opacity = Property(float, get_border_opacity, set_border_opacity)

    def _update_style(self):
        """动态生成样式"""
        base_color = QColor(self.color_hex)

        # 计算当前背景色
        bg_alpha = self._bg_opacity
        checked_bg_str = f"rgba({base_color.red()}, {base_color.green()}, {base_color.blue()}, {bg_alpha})"

        # 边框透明度
        border_color = QColor(self.color_hex)
        border_color.setAlphaF(self._border_opacity)
        border_str = f"rgba({border_color.red()}, {border_color.green()}, {border_color.blue()}, {self._border_opacity})"

        # 文字颜色根据选中状态插值
        text_color = QColor("#606266")
        if self.isChecked():
            # 插值到主题色
            target = QColor(self.color_hex)
            factor = self._border_opacity
            r = int(text_color.red() + (target.red() - text_color.red()) * factor)
            g = int(text_color.green() + (target.green() - text_color.green()) * factor)
            b = int(text_color.blue() + (target.blue() - text_color.blue()) * factor)
            text_color = QColor(r, g, b)

        text_color_str = text_color.name()

        css = f"""
            QPushButton {{
                background-color: {checked_bg_str if self.isChecked() else '#F2F3F5'};
                border: 1px solid {border_str if self.isChecked() else 'transparent'};
                border-radius: 12px;
                padding: 4px 10px;
                color: {text_color_str};
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {'#E5E6EB' if not self.isChecked() else checked_bg_str};
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