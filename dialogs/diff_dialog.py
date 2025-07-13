# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTreeView,
    QHeaderView, QFrame, QTextEdit
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItemModel, QStandardItem, QColor, QFont, QIcon
from utils.localization import _
import difflib

class DiffDialog(QDialog):
    def __init__(self, parent, title, diff_results):
        super().__init__(parent)
        self.diff_results = diff_results
        self.result = None

        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(1200, 700)

        self.setup_ui()
        self.populate_tree()
        self.setStyleSheet("""
            QDialog {
                background-color: #FAFAFA;
            }
            QTreeView {
                border: 1px solid #E0E0E0;
                border-radius: 8px;
                background-color: #FFFFFF;
                alternate-background-color: #F8F9FA;
            }
            QTreeView::item {
                padding: 6px 4px;
                min-height: 20px;
            }
            QTreeView::item:selected:active {
                background-color: #D4E6F1;
                color: #1A5276;
            }
            QTreeView::item:selected:!active {
                background-color: #EAF2F8;
                color: #2874A6;
            }
            QTreeView::item:hover {
                background-color: #F8F9F9;
            }
            QTreeView::branch {
                background: transparent;
            }
            QHeaderView::section {
                background-color: #F1F3F5;
                padding: 6px;
                border: none;
                border-bottom: 1px solid #E0E0E0;
                font-weight: bold;
            }
            QPushButton {
                font-size: 13px;
                padding: 8px 16px;
                border: 1px solid #CCCCCC;
                border-radius: 6px;
                background-color: #FFFFFF;
            }
            QPushButton:hover {
                background-color: #F0F8FF;
                border-color: #007BFF;
            }
            QPushButton#confirmButton {
                background-color: #28A745;
                color: white;
                border: none;
                font-weight: bold;
            }
            QPushButton#confirmButton:hover {
                background-color: #218838;
            }
        """)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self._adjust_column_widths)

    def _adjust_column_widths(self):
        header = self.tree.header()
        if not header:
            return
        total_width = header.width()
        first_col_width = int(total_width * 0.85)
        header.setSectionResizeMode(0, QHeaderView.Interactive)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        self.tree.setColumnWidth(0, first_col_width)
        header.setSectionResizeMode(1, QHeaderView.Stretch)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        summary_text = self.diff_results.get('summary', _('Comparison Results Summary'))
        summary_label = QLabel(summary_text)
        summary_label.setWordWrap(True)
        summary_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #333; margin-bottom: 5px;")
        main_layout.addWidget(summary_label)

        # Main content area with two panels
        content_frame = QFrame()
        content_layout = QHBoxLayout(content_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)
        main_layout.addWidget(content_frame, 1)

        # Left panel: Tree view
        tree_container = QFrame()
        tree_container_layout = QVBoxLayout(tree_container)
        self.tree = QTreeView()
        self.tree.setAlternatingRowColors(True)
        self.tree.setRootIsDecorated(True)
        self.tree.setEditTriggers(QTreeView.NoEditTriggers)

        tree_container_layout.addWidget(self.tree)
        content_layout.addWidget(tree_container, 2)

        # Right panel: Inline diff view
        diff_view_container = QFrame()
        diff_view_container_layout = QVBoxLayout(diff_view_container)
        diff_view_container.setStyleSheet(
            "QFrame { border: 1px solid #E0E0E0; border-radius: 8px; background-color: #FFFFFF; }")
        diff_view_container_layout.addWidget(QLabel(_("Inline Differences")))
        self.diff_view = QTextEdit()
        self.diff_view.setReadOnly(True)
        self.diff_view.setFont(QFont("Consolas", 10))
        diff_view_container_layout.addWidget(self.diff_view)
        content_layout.addWidget(diff_view_container, 1)

        self.model = QStandardItemModel()
        self.tree.setModel(self.model)

        self.tree.selectionModel().selectionChanged.connect(self.on_selection_changed)

        # Buttons
        button_box = QHBoxLayout()
        confirm_btn = QPushButton(_("Confirm and Update Project"))
        confirm_btn.setObjectName("confirmButton")
        confirm_btn.clicked.connect(self.accept)
        button_box.addWidget(confirm_btn)

        button_box.addStretch(1)

        cancel_btn = QPushButton(_("Cancel"))
        cancel_btn.clicked.connect(self.reject)
        button_box.addWidget(cancel_btn)

        main_layout.addLayout(button_box)

    def populate_tree(self):
        self.model.setHorizontalHeaderLabels([_("Original"), _("Similarity")])

        # 新增项目
        added_items = self.diff_results.get('added', [])
        if added_items:
            added_root = QStandardItem(f"{_('Added')} ({len(added_items)})")
            added_root.setForeground(QColor("#28A745"))
            added_root.setFont(QFont("Segoe UI", 10, QFont.Bold))
            self.model.appendRow(added_root)
            for item_data in added_items:
                item = QStandardItem(item_data['new_obj'].original_semantic)
                item.setData(item_data, Qt.UserRole)
                added_root.appendRow([item, QStandardItem("N/A")])

        # 修改项目
        modified_items = self.diff_results.get('modified', [])
        if modified_items:
            modified_root = QStandardItem(f"{_('Modified/Inherited')} ({len(modified_items)})")
            modified_root.setForeground(QColor("#FFC107"))
            modified_root.setFont(QFont("Segoe UI", 10, QFont.Bold))
            self.model.appendRow(modified_root)
            for item_data in modified_items:
                sim_str = f"{item_data['similarity']:.1%}"
                item = QStandardItem(item_data['new_obj'].original_semantic)
                item.setData(item_data, Qt.UserRole)
                modified_root.appendRow([item, QStandardItem(sim_str)])

        # 移除项目
        removed_items = self.diff_results.get('removed', [])
        if removed_items:
            removed_root = QStandardItem(f"{_('Removed')} ({len(removed_items)})")
            removed_root.setForeground(QColor("#DC3545"))
            removed_root.setFont(QFont("Segoe UI", 10, QFont.Bold))
            self.model.appendRow(removed_root)
            for item_data in removed_items:
                item = QStandardItem(item_data['old_obj'].original_semantic)
                item.setData(item_data, Qt.UserRole)
                removed_root.appendRow([item, QStandardItem("N/A")])

        self.tree.expandAll()

    def on_selection_changed(self, selected, deselected):
        indexes = selected.indexes()
        if not indexes:
            self.diff_view.clear()
            return
        item = self.model.itemFromIndex(indexes[0])
        item_data = item.data(Qt.UserRole)

        if not item_data:
            self.diff_view.clear()
            return

        if 'old_obj' in item_data and 'new_obj' in item_data:  # Modified
            old_text = item_data['old_obj'].original_semantic
            new_text = item_data['new_obj'].original_semantic
            self.display_inline_diff(old_text, new_text)
        elif 'new_obj' in item_data:  # Added
            self.diff_view.setHtml(
                f"<font color='green'><b>{_('New')}:</b><br>{item_data['new_obj'].original_semantic.replace('<', '<').replace('>', '>')}</font>")
        elif 'old_obj' in item_data:  # Removed
            self.diff_view.setHtml(
                f"<font color='red'><b>{_('Removed')}:</b><br>{item_data['old_obj'].original_semantic.replace('<', '<').replace('>', '>')}</font>")

    def display_inline_diff(self, old_text, new_text):
        diff = difflib.ndiff(old_text.split(), new_text.split())
        html = ""
        for line in diff:
            word = line[2:].replace('<', '<').replace('>', '>')
            if line.startswith('+ '):
                html += f"<span style='background-color: #D4EDDA; color: #155724; border-radius: 3px; padding: 1px 3px;'>{word}</span> "
            elif line.startswith('- '):
                html += f"<span style='background-color: #F8D7DA; color: #721C24; text-decoration: line-through; border-radius: 3px; padding: 1px 3px;'>{word}</span> "
            elif line.startswith('? '):
                pass
            else:
                html += f"{word} "
        self.diff_view.setHtml(html)

    def accept(self):
        self.result = True
        super().accept()

    def reject(self):
        self.result = False
        super().reject()