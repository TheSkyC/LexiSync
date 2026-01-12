# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QAbstractButton
from PySide6.QtCore import (Qt, QSize, QPropertyAnimation, QEasingCurve,
                            Property, QRectF)
from PySide6.QtGui import QPainter, QColor, QBrush, QPen, QCursor
from .tooltip import Tooltip


class ToggleButton(QAbstractButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(32, 18)
        # 颜色配置
        self._bg_color_off = QColor("#E0E0E0")
        self._bg_color_on = QColor("#F57C00")
        self._circle_color = QColor("#FFFFFF")

        # 动画参数
        self._circle_position = 0.0
        self._anim = QPropertyAnimation(self, b"circle_position", self)
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.OutQuad)

        # 状态切换连接
        self.toggled.connect(self._start_animation)

        # 初始化自定义 Tooltip
        self._custom_tooltip = Tooltip(self)
        self._tooltip_text = ""

    def setToolTip(self, text):
        self._tooltip_text = text

    def enterEvent(self, event):
        if self._tooltip_text:
            self._custom_tooltip.show_tooltip(QCursor.pos(), self._tooltip_text, delay=600)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._custom_tooltip.hide()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self._custom_tooltip.hide()
        super().mousePressEvent(event)

    # 定义 Qt 属性供动画使用
    @Property(float)
    def circle_position(self):
        return self._circle_position

    @circle_position.setter
    def circle_position(self, pos):
        self._circle_position = pos
        self.update()  # 触发重绘

    def _start_animation(self, checked):
        self._anim.stop()
        start_val = 0.0 if checked else 1.0
        self._circle_position = start_val
        self._anim.setStartValue(start_val)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def set_checked_silent(self, checked):
        """无动画设置状态"""
        if self.isChecked() == checked:
            return

        self.blockSignals(True)
        self.setChecked(checked)
        self._circle_position = 1.0 if checked else 0.0
        self.update()
        self.blockSignals(False)


    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 绘制背景
        rect = self.rect()
        radius = rect.height() / 2

        current_bg = QColor(self._bg_color_off)
        if self._circle_position > 0:
            r = self._bg_color_off.red() + (self._bg_color_on.red() - self._bg_color_off.red()) * self._circle_position
            g = self._bg_color_off.green() + (
                        self._bg_color_on.green() - self._bg_color_off.green()) * self._circle_position
            b = self._bg_color_off.blue() + (
                        self._bg_color_on.blue() - self._bg_color_off.blue()) * self._circle_position
            current_bg = QColor(int(r), int(g), int(b))

        painter.setBrush(QBrush(current_bg))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, radius, radius)

        # 绘制圆点
        padding = 3
        circle_dia = rect.height() - padding * 2

        # 计算圆点 X 坐标
        start_x = padding
        end_x = rect.width() - padding - circle_dia
        current_x = start_x + (end_x - start_x) * self._circle_position

        painter.setBrush(QBrush(self._circle_color))
        painter.drawEllipse(QRectF(current_x, padding, circle_dia, circle_dia))

    def sizeHint(self):
        return QSize(32, 18)