# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QLabel, QApplication
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QPalette, QColor


class Tooltip(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.ToolTip | Qt.FramelessWindowHint)
        self.setWindowOpacity(0.95)
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
        self.show()