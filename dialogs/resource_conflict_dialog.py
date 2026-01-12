# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QTableWidget, QTableWidgetItem, QComboBox,
                               QHeaderView, QPushButton, QDialogButtonBox, QAbstractItemView)
from PySide6.QtCore import Qt
from utils.localization import _


class ResourceConflictDialog(QDialog):
    def __init__(self, parent, conflicts: dict, new_entries: list, resource_type: str = 'glossary'):
        """
        :param conflicts: dict from service.find_conflicts
        :param new_entries: list of dicts {'source':, 'target':, ...}
        :param resource_type: 'tm' or 'glossary'
        """
        super().__init__(parent)
        self.resource_type = resource_type
        self.conflicts = conflicts
        self.new_entries = new_entries
        self.resolutions = {}  # source_key -> action

        title = _("Resolve Conflicts - TM") if resource_type == 'tm' else _("Resolve Conflicts - Glossary")
        self.setWindowTitle(title)
        self.resize(900, 600)

        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        info_text = _("The following entries already exist in the database. Please choose an action for each.")
        layout.addWidget(QLabel(info_text))

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)

        # Dynamic Headers
        src_header = _("Source Text") if self.resource_type == 'tm' else _("Source Term")
        self.table.setHorizontalHeaderLabels([
            src_header,
            _("Existing Translation"),
            _("New Translation"),
            _("Action")
        ])

        # Resize modes
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # Source gets space
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # Existing gets space
        header.setSectionResizeMode(2, QHeaderView.Stretch)  # New gets space
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        self.table.setColumnWidth(3, 130)

        # Enable Word Wrap (Option B)
        self.table.setWordWrap(True)
        self.table.setTextElideMode(Qt.ElideNone)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)

        layout.addWidget(self.table)

        self.populate_table()

        # Batch Actions
        batch_layout = QHBoxLayout()
        batch_layout.addWidget(QLabel(_("Set all to:")))

        btn_skip_all = QPushButton(_("Skip"))
        btn_skip_all.clicked.connect(lambda: self.set_all_actions('skip'))
        batch_layout.addWidget(btn_skip_all)

        btn_over_all = QPushButton(_("Overwrite"))
        btn_over_all.clicked.connect(lambda: self.set_all_actions('overwrite'))
        batch_layout.addWidget(btn_over_all)

        if self.resource_type == 'glossary':
            btn_merge_all = QPushButton(_("Merge"))
            btn_merge_all.clicked.connect(lambda: self.set_all_actions('merge'))
            batch_layout.addWidget(btn_merge_all)

        batch_layout.addStretch()
        layout.addLayout(batch_layout)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def populate_table(self):
        self.table.setRowCount(0)

        for entry in self.new_entries:
            raw_src_text = entry['source']

            # Key generation must match EXACTLY what was used to build the 'conflicts' dict
            if self.resource_type == 'glossary':
                # Glossary service usually strips and lowercases
                key = raw_src_text.strip().lower()
                display_text = raw_src_text.strip()
            else:
                # TM service uses exact raw string
                key = raw_src_text
                display_text = raw_src_text

            if key in self.conflicts:
                conflict_info = self.conflicts[key]

                row = self.table.rowCount()
                self.table.insertRow(row)

                # Source
                # Use the text from conflict info if available (to match DB representation), else current input
                item_src = QTableWidgetItem(conflict_info.get('original_text', display_text))
                item_src.setFlags(Qt.ItemIsEnabled)  # Read only
                self.table.setItem(row, 0, item_src)

                # Existing
                existing_targets = conflict_info.get('existing_targets', [])
                existing_str = "\n---\n".join(existing_targets)
                item_exist = QTableWidgetItem(existing_str)
                item_exist.setFlags(Qt.ItemIsEnabled)
                self.table.setItem(row, 1, item_exist)

                # New
                item_new = QTableWidgetItem(entry['target'])
                item_new.setFlags(Qt.ItemIsEnabled)
                self.table.setItem(row, 2, item_new)

                # Action Combo
                combo = QComboBox()
                combo.addItem(_("Skip"), 'skip')
                combo.addItem(_("Overwrite"), 'overwrite')

                if self.resource_type == 'glossary':
                    combo.addItem(_("Merge"), 'merge')
                    combo.setCurrentIndex(2)  # Default Merge for Glossary
                else:
                    combo.setCurrentIndex(1)  # Default Overwrite for TM

                # Store key in combo property
                combo.setProperty("conflict_key", key)
                self.table.setCellWidget(row, 3, combo)

        self.table.resizeRowsToContents()

    def set_all_actions(self, action_code):
        for row in range(self.table.rowCount()):
            combo = self.table.cellWidget(row, 3)
            index = combo.findData(action_code)
            if index != -1:
                combo.setCurrentIndex(index)

    def accept(self):
        # Collect results
        for row in range(self.table.rowCount()):
            combo = self.table.cellWidget(row, 3)
            key = combo.property("conflict_key")
            action = combo.currentData()
            self.resolutions[key] = action
        super().accept()