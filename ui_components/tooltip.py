# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QLabel, QApplication
from PySide6.QtCore import Qt, QPoint, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPalette, QColor


class Tooltip(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.ToolTip | Qt.FramelessWindowHint)
        self.setWindowOpacity(0.0)  # Start invisible
        self.setAlignment(Qt.AlignLeft)
        self.setIndent(5)
        self.setWordWrap(True)

        self.setStyleSheet("""
            QLabel {
                background-color: #333333;
                color: #FFFFFF;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
            }
        """)

        # Animation Setup
        self.opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        self.target_opacity = 0.95
        self.opacity_anim.finished.connect(self._on_animation_finished)
        self._is_fading_out = False

    def show_tooltip(self, pos: QPoint, text: str):
        self.setText(text)
        self.adjustSize()

        screen_geometry = QApplication.primaryScreen().availableGeometry()

        x = pos.x() + 15
        y = pos.y() + 20

        if x + self.width() > screen_geometry.right():
            x = pos.x() - self.width() - 15
        if y + self.height() > screen_geometry.bottom():
            y = pos.y() - self.height() - 20

        self.move(x, y)

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

    def hide(self):
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