# Copyright (c) 2025-2026, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtGui import QCursor, QIcon
from PySide6.QtWidgets import QToolButton

from lexisync.ui_components.tooltip import Tooltip
from lexisync.utils.path_utils import get_resource_path


class HelpButton(QToolButton):
    def __init__(self, tooltip_text="", parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.custom_tooltip_text = tooltip_text

        self.tooltip_widget = Tooltip(self)

        icon_path = get_resource_path("icons/help-circle.svg")
        self.setIcon(QIcon(icon_path))
        self.setIconSize(QSize(14, 14))

        self.setStyleSheet("""
            QToolButton {
                border: none;
                background: transparent;
                padding: 0px;
            }
            QToolButton:hover {
                background-color: #E0E0E0;
                border-radius: 7px;
            }
        """)

        # Install event filter
        self.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj == self:
            if event.type() == QEvent.Enter:
                self.tooltip_widget.show_tooltip(QCursor.pos(), self.custom_tooltip_text)
                return True
            if event.type() == QEvent.Leave:
                self.tooltip_widget.hide()
                return True

            if event.type() == QEvent.MouseButtonPress:
                return True

        return super().eventFilter(obj, event)

    def set_tooltip_text(self, text):
        self.custom_tooltip_text = text
        if self.tooltip_widget.isVisible():
            self.tooltip_widget.show_tooltip(QCursor.pos(), text)
