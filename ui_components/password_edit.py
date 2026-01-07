# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QLineEdit, QAbstractButton
from PySide6.QtGui import Qt, QPainter, QColor, QPen, QCursor
from PySide6.QtCore import QSize, QPropertyAnimation, QEasingCurve, Property, QRectF, QPointF, Slot
from .tooltip import Tooltip
from utils.localization import _


class EyeButton(QAbstractButton):
    """自定义眼睛按钮，带切换动画"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(24, 24)

        # 颜色配置
        self._color = QColor("#666666")
        self._color_hover = QColor("#333333")
        self._is_hovered = False

        # 动画参数：0.0 = 显示密码(眼睛睁开), 1.0 = 隐藏密码(眼睛闭合+斜线)
        self._anim_progress = 1.0  # 初始状态：隐藏密码
        self._anim = QPropertyAnimation(self, b"anim_progress", self)
        self._anim.setDuration(250)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

        # 状态切换连接
        self.toggled.connect(self._start_animation)

        # Tooltip
        self._custom_tooltip = Tooltip(self)
        self._tooltip_text = ""

    def setToolTip(self, text):
        self._tooltip_text = text

    def enterEvent(self, event):
        self._is_hovered = True
        self.update()
        if self._tooltip_text:
            self._custom_tooltip.show_tooltip(QCursor.pos(), self._tooltip_text, delay=600)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._is_hovered = False
        self.update()
        self._custom_tooltip.hide()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self._custom_tooltip.hide()
        super().mousePressEvent(event)

    @Property(float)
    def anim_progress(self):
        return self._anim_progress

    @anim_progress.setter
    def anim_progress(self, value):
        self._anim_progress = value
        self.update()

    def _start_animation(self, checked):
        self._anim.stop()
        self._anim.setEndValue(0.0 if checked else 1.0)
        self._anim.start()

    def set_checked_silent(self, checked):
        """无动画设置状态"""
        self.blockSignals(True)
        self.setChecked(checked)
        self._anim_progress = 0.0 if checked else 1.0
        self.update()
        self.blockSignals(False)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 选择颜色
        color = self._color_hover if self._is_hovered else self._color
        pen = QPen(color, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)

        # 绘制区域居中
        rect = self.rect()
        center_x = rect.width() / 2
        center_y = rect.height() / 2

        # 眼睛外轮廓参数
        eye_width = 16
        eye_height = 10
        eye_rect = QRectF(
            center_x - eye_width / 2,
            center_y - eye_height / 2,
            eye_width,
            eye_height
        )

        # 眼睛外轮廓
        # 上弧线
        painter.drawArc(
            eye_rect,
            0 * 16,  # 起始角度
            180 * 16  # 跨越角度
        )
        # 下弧线
        painter.drawArc(
            eye_rect,
            180 * 16,  # 起始角度
            180 * 16  # 跨越角度
        )

        # 瞳孔
        pupil_size = 4 * (1 - self._anim_progress * 0.7)  # 从4缩小到1.2
        if pupil_size > 0.5:
            painter.setBrush(color)
            painter.drawEllipse(
                QPointF(center_x, center_y),
                pupil_size / 2,
                pupil_size / 2
            )

        # 斜线
        if self._anim_progress > 0.01:
            # 斜线的透明度和长度随动画进度变化
            line_color = QColor(color)
            line_color.setAlphaF(self._anim_progress)
            painter.setPen(QPen(line_color, 2, Qt.SolidLine, Qt.RoundCap))

            # 斜线从右上到左下
            line_length = 18 * self._anim_progress
            offset = line_length / 2
            painter.drawLine(
                QPointF(center_x - offset, center_y - offset),
                QPointF(center_x + offset, center_y + offset)
            )

    def sizeHint(self):
        return QSize(24, 24)


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

        # 使用自定义眼睛按钮
        self._toggle_button = EyeButton(self)
        self._toggle_button.setFocusPolicy(Qt.NoFocus)

        # 初始化按钮状态（未选中 = 隐藏密码）
        self._toggle_button.set_checked_silent(False)
        self._toggle_button.setToolTip(_("Show Password"))
        self._toggle_button.clicked.connect(self._on_toggle)

        self.setStyleSheet("""
            QLineEdit {
                padding-right: 32px; 
            }
        """)

    def resizeEvent(self, event):
        super().resizeEvent(event)

        button_size = 24
        padding = 4

        self._toggle_button.setGeometry(
            self.width() - button_size - padding,
            (self.height() - button_size) // 2,
            button_size,
            button_size
        )

    @Slot()
    def _on_toggle(self):
        cursor_pos = self.cursorPosition()

        if self.echoMode() == QLineEdit.Password:
            # 切换到显示密码
            self.setEchoMode(QLineEdit.Normal)
            self._toggle_button.setToolTip(_("Hide Password"))
        else:
            # 切换到隐藏密码
            self.setEchoMode(QLineEdit.Password)
            self._toggle_button.setToolTip(_("Show Password"))

        self.setCursorPosition(cursor_pos)
        self.setFocus()