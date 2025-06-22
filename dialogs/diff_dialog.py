# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTreeWidget, QTreeWidgetItem, QHeaderView
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from utils.localization import _

class DiffDialog(QDialog):
    def __init__(self, parent, title, diff_results):
        super().__init__(parent)
        self.diff_results = diff_results
        self.result = None

        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(1200, 700)

        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        summary_text = self.diff_results.get('summary', _('Comparison Results Summary'))
        summary_label = QLabel(summary_text)
        summary_label.setWordWrap(True)
        summary_label.setStyleSheet("font-weight: bold;")
        main_layout.addWidget(summary_label)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([_("Status"), _("Old Version Original"), _("New Version Original"), _("Similarity")])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(2, QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        main_layout.addWidget(self.tree)

        self.populate_tree()

        button_box = QHBoxLayout()
        confirm_btn = QPushButton(_("Confirm and Update Project"))
        confirm_btn.clicked.connect(self.accept)
        button_box.addWidget(confirm_btn)

        cancel_btn = QPushButton(_("Cancel"))
        cancel_btn.clicked.connect(self.reject)
        button_box.addWidget(cancel_btn)

        main_layout.addLayout(button_box)

    def populate_tree(self):
        for item_data in self.diff_results['added']:
            item = QTreeWidgetItem(self.tree, [_("Added"), "", item_data['new_obj'].original_semantic, "N/A"])
            item.setBackground(0, QColor("#DFF0D8"))
            item.setForeground(0, QColor("#3C763D"))
            item.setBackground(1, QColor("#DFF0D8"))
            item.setForeground(1, QColor("#3C763D"))
            item.setBackground(2, QColor("#DFF0D8"))
            item.setForeground(2, QColor("#3C763D"))
            item.setBackground(3, QColor("#DFF0D8"))
            item.setForeground(3, QColor("#3C763D"))


        for item_data in self.diff_results['removed']:
            item = QTreeWidgetItem(self.tree, [_("Removed"), item_data['old_obj'].original_semantic, "", "N/A"])
            item.setBackground(0, QColor("#F2DEDE"))
            item.setForeground(0, QColor("#A94442"))
            item.setBackground(1, QColor("#F2DEDE"))
            item.setForeground(1, QColor("#A94442"))
            item.setBackground(2, QColor("#F2DEDE"))
            item.setForeground(2, QColor("#A94442"))
            item.setBackground(3, QColor("#F2DEDE"))
            item.setForeground(3, QColor("#A94442"))

        for item_data in self.diff_results['modified']:
            sim_str = f"{item_data['similarity']:.2%}"
            item = QTreeWidgetItem(self.tree, [_("Modified/Inherited"), item_data['old_obj'].original_semantic,
                                             item_data['new_obj'].original_semantic, sim_str])
            item.setBackground(0, QColor("#FCF8E3"))
            item.setForeground(0, QColor("#8A6D3B"))
            item.setBackground(1, QColor("#FCF8E3"))
            item.setForeground(1, QColor("#8A6D3B"))
            item.setBackground(2, QColor("#FCF8E3"))
            item.setForeground(2, QColor("#8A6D3B"))
            item.setBackground(3, QColor("#FCF8E3"))
            item.setForeground(3, QColor("#8A6D3B"))

    def accept(self):
        self.result = True
        super().accept()

    def reject(self):
        self.result = False
        super().reject()