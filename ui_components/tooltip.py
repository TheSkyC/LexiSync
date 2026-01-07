# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QLabel, QApplication
from PySide6.QtCore import Qt, QPoint, QPropertyAnimation, QEasingCurve, QRectF, QTimer
from PySide6.QtGui import QPainter, QColor, QBrush, QPen, QCursor


class Tooltip(QLabel):
    def __init__(self, parent=None, delay=100):
        super().__init__(parent, Qt.ToolTip | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowOpacity(0.0)

        self.setAlignment(Qt.AlignLeft)
        self.setIndent(5)
        self.setWordWrap(True)

        self.setStyleSheet("""
            QLabel {
                color: #FFFFFF;
                padding: 10px;
                font-size: 13px;
            }
        """)

        # Animation Setup
        self.opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        self.target_opacity = 0.95
        self.opacity_anim.finished.connect(self._on_animation_finished)
        self._is_fading_out = False

        # Delay Timer Setup
        self.default_delay = delay
        self._show_timer = QTimer(self)
        self._show_timer.setSingleShot(True)
        self._show_timer.timeout.connect(self._perform_show)

        self._pending_text = ""
        self._pending_pos = QPoint()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw background
        rect = self.rect()
        painter.setBrush(QBrush(QColor("#333333")))
        painter.setPen(QPen(QColor("#555555"), 1))

        # Draw rounded rect
        painter.drawRoundedRect(QRectF(rect).adjusted(0.5, 0.5, -0.5, -0.5), 6, 6)

        # Draw text
        super().paintEvent(event)

    def show_tooltip(self, pos: QPoint, text: str, delay: int = None):
        """
        Request to show the tooltip.
        :param pos: Global position to show.
        :param text: Tooltip content (HTML supported).
        :param delay: Delay in ms. If None, use default. If 0, show instantly.
        """
        target_delay = self.default_delay if delay is None else delay

        if self.isVisible() and not self._is_fading_out and self.text() == text:
            self._move_to_safe_pos(pos)
            return

        self._pending_text = text
        self._pending_pos = pos

        if target_delay <= 0:
            self._perform_show()
            return

        if self._show_timer.isActive():
            if self.text() != text:
                self._show_timer.start(target_delay)
        else:
            self._show_timer.start(target_delay)

    def _perform_show(self):
        """Actual logic to show the widget."""
        self._show_timer.stop()

        self.setText(self._pending_text)
        self.adjustSize()
        self._move_to_safe_pos(self._pending_pos)

        # Animation Logic: Fade In
        self._is_fading_out = False
        self.opacity_anim.stop()

        if not self.isVisible():
            self.setWindowOpacity(0.0)
            self.show()

        self.opacity_anim.setDuration(150)
        self.opacity_anim.setStartValue(self.windowOpacity())
        self.opacity_anim.setEndValue(self.target_opacity)
        self.opacity_anim.setEasingCurve(QEasingCurve.OutCubic)
        self.opacity_anim.start()

    def _move_to_safe_pos(self, pos: QPoint):
        screen_geometry = QApplication.primaryScreen().availableGeometry()

        x = pos.x() + 15
        y = pos.y() + 20

        if x + self.width() > screen_geometry.right():
            x = pos.x() - self.width() - 15
        if y + self.height() > screen_geometry.bottom():
            y = pos.y() - self.height() - 20

        self.move(x, y)

    def hide(self):
        # Stop pending timer
        self._show_timer.stop()

        # Animation Logic: Fade Out
        if not self.isVisible() or self._is_fading_out:
            return

        self._is_fading_out = True
        self.opacity_anim.stop()
        self.opacity_anim.setDuration(150)
        self.opacity_anim.setStartValue(self.windowOpacity())
        self.opacity_anim.setEndValue(0.0)
        self.opacity_anim.setEasingCurve(QEasingCurve.InCubic)
        self.opacity_anim.start()

    def _on_animation_finished(self):
        if self._is_fading_out:
            super().hide()
            self._is_fading_out = False
            self.setText("")