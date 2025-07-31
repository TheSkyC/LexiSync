# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QLabel
from PySide6.QtGui import QPainter
from PySide6.QtCore import Qt, QSize

from PySide6.QtWidgets import QLabel, QSizePolicy
from PySide6.QtGui import QPainter
from PySide6.QtCore import Qt, QSize


class ElidedLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def sizeHint(self):
        original_hint = super().sizeHint()
        if self.maximumWidth() != 16777215:
            limited_width = min(original_hint.width(), self.maximumWidth())
            return QSize(limited_width, original_hint.height())

        return original_hint

    def minimumSizeHint(self):
        metrics = self.fontMetrics()
        min_width = metrics.horizontalAdvance("...") + self.contentsMargins().left() + self.contentsMargins().right()
        height = super().minimumSizeHint().height()
        return QSize(min_width, height)

    def paintEvent(self, event):
        painter = QPainter(self)
        metrics = painter.fontMetrics()
        elided_text = metrics.elidedText(self.text(), Qt.ElideRight, self.width())
        painter.drawText(self.rect(), self.alignment(), elided_text)