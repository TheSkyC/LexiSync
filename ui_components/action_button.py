# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, Signal, QEvent, QSize
from PySide6.QtGui import QIcon


class ActionButton(QWidget):
    clicked = Signal()

    def __init__(self, icon_path: str, title: str, subtitle: str, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(80)

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
        self.title_label.setStyleSheet("font-size: 16px;")

        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setStyleSheet("color: #555;")
        self.subtitle_label.setWordWrap(True)

        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.subtitle_label)
        text_layout.addStretch()

        main_layout.addLayout(text_layout, 1)

        self.setProperty("class", "action-button")
        self.setStyleSheet("""
            QWidget[class="action-button"] {
                background-color: #F5F7FA;
                border-radius: 8px;
            }
            QWidget[class="action-button"]:hover {
                background-color: #ECF5FF;
            }
        """)

    def event(self, event):
        if event.type() == QEvent.Enter:
            self.setStyleSheet("""
                QWidget[class="action-button"] {
                    background-color: #ECF5FF;
                    border: 1px solid #D3E8FF;
                    border-radius: 8px;
                }
            """)
        elif event.type() == QEvent.Leave:
            self.setStyleSheet("""
                QWidget[class="action-button"] {
                    background-color: #F5F7FA;
                    border: none;
                    border-radius: 8px;
                }
            """)
        return super().event(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)