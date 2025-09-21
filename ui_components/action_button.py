# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtCore import Qt, Signal, QEvent, QSize
from PySide6.QtGui import QIcon, QMouseEvent, QColor

class ActionButton(QWidget):
    clicked = Signal()

    def __init__(self, icon_path: str, title: str, subtitle: str, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(80)

        self._is_pressed = False
        self._is_hovered = False

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(15, 10, 15, 10)
        main_layout.setSpacing(15)

        self.icon_label = QLabel()
        if icon_path:
            self.icon_label.setPixmap(QIcon(icon_path).pixmap(QSize(32, 32)))
        main_layout.addWidget(self.icon_label)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        self.title_label = QLabel(f"<b>{title}</b>")
        self.title_label.setStyleSheet("font-size: 16px; background-color: transparent;")

        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setStyleSheet("color: #555; background-color: transparent;")
        self.subtitle_label.setWordWrap(True)

        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.subtitle_label)
        text_layout.addStretch()

        main_layout.addLayout(text_layout, 1)

        self.setProperty("class", "action-button")
        self.setAutoFillBackground(True) # Important for palette to work
        self._update_style()

    def _update_style(self):
        palette = self.palette()
        if self._is_pressed:
            palette.setColor(self.backgroundRole(), QColor("#E0E0E0")) # Darker grey for pressed
        elif self._is_hovered:
            palette.setColor(self.backgroundRole(), QColor("#F0F0F0")) # Lighter grey for hover
        else:
            palette.setColor(self.backgroundRole(), QColor("#F5F7FA")) # Default background
        self.setPalette(palette)

    def enterEvent(self, event: QEvent):
        self._is_hovered = True
        self._update_style()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent):
        self._is_hovered = False
        self._is_pressed = False
        self._update_style()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._is_pressed = True
            self._update_style()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            was_pressed = self._is_pressed
            self._is_pressed = False
            self._update_style()
            if was_pressed and self.rect().contains(event.pos()):
                self.clicked.emit()
        super().mouseReleaseEvent(event)