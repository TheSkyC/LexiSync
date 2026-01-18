# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QListWidget, QListWidgetItem,
                               QLabel, QAbstractItemView, QSizePolicy, QFrame)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QColor, QFont, QCursor
import os
from utils.localization import _

class RecentFileItemWidget(QWidget):
    def __init__(self, filename, path, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)  # 稍微调整边距
        layout.setSpacing(2)

        self.name_label = QLabel(filename)
        self.name_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #333;")

        self.path_label = QLabel(path)
        self.path_label.setStyleSheet("color: #888; font-size: 11px;")
        self.path_label.setWordWrap(False)

        layout.addWidget(self.name_label)
        layout.addWidget(self.path_label)

        self.setAttribute(Qt.WA_TransparentForMouseEvents)


class ScrollableRecentFileList(QWidget):
    file_clicked = Signal(str)

    def __init__(self, recent_files, parent=None):
        super().__init__(parent)
        self.recent_files = recent_files
        self.setup_ui()

    def setup_ui(self):
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)  # 0 边距
        layout.setSpacing(0)  # 0 间距

        self.list_widget = QListWidget()
        self.list_widget.setFrameShape(QListWidget.NoFrame)
        self.list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_widget.setCursor(Qt.PointingHandCursor)

        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: #FFFFFF;
                border: none;
                outline: none;
            }
            QListWidget::item {
                border-bottom: 1px solid #F5F5F5;
                padding: 0px;
                margin: 0px;
            }
            QListWidget::item:hover {
                background-color: #E6F7FF;
            }
            QListWidget::item:selected {
                background-color: #E6F7FF;
            }
            QScrollBar:vertical {
                border: none;
                background: #F5F5F5;
                width: 6px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #C1C1C1;
                min-height: 20px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: #A8A8A8;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        self.populate_list()

        self.adjust_height()

        self.list_widget.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list_widget)

    def populate_list(self):
        for entry in self.recent_files:
            path = entry if isinstance(entry, str) else entry.get("path", "")
            if not path: continue

            filename = os.path.basename(path)
            dirpath = os.path.dirname(path)

            item = QListWidgetItem(self.list_widget)
            item.setData(Qt.UserRole, path)

            widget = RecentFileItemWidget(filename, dirpath)

            item.setSizeHint(QSize(0, 50))

            self.list_widget.setItemWidget(item, widget)

    def adjust_height(self):
        count = self.list_widget.count()
        if count == 0:
            self.list_widget.setFixedHeight(0)
            self.setFixedHeight(0)
            return

        item_height = self.list_widget.sizeHintForRow(0)

        if item_height <= 0: item_height = 50

        max_visible_items = 8
        visible_items = min(count, max_visible_items)

        total_height = item_height * visible_items

        total_height += self.list_widget.frameWidth() * 2

        self.list_widget.setFixedHeight(total_height)
        self.setFixedHeight(total_height)
        self.updateGeometry()

    def _on_item_clicked(self, item):
        path = item.data(Qt.UserRole)
        if path:
            self.file_clicked.emit(path)