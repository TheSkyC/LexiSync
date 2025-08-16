# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette


class DropOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        palette = self.palette()
        palette.setColor(QPalette.Window, QColor(0, 0, 0, 80))
        self.setPalette(palette)
        self.setAutoFillBackground(True)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        self.message_label = QLabel(self)
        self.message_label.setAlignment(Qt.AlignCenter)
        self.message_label.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 0, 0, 180);
                color: white;
                font-size: 24px;
                font-weight: bold;
                padding: 20px 40px;
                border-radius: 15px;
            }
        """)
        layout.addWidget(self.message_label)

        self.hide()

    def show_message(self, text: str):
        self.message_label.setText(text)
        self.show()
        self.raise_()