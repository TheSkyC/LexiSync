# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QGroupBox, QRadioButton,
                               QCheckBox, QDialogButtonBox, QLabel, QTableWidget,
                               QTableWidgetItem, QComboBox, QHeaderView, QHBoxLayout, QPushButton)
from PySide6.QtCore import Qt
from utils.localization import _


class SaveGlossaryOptionsDialog(QDialog):
    def __init__(self, parent, has_project):
        super().__init__(parent)
        self.setWindowTitle(_("Save to Glossary"))
        self.resize(400, 350)

        layout = QVBoxLayout(self)

        # 1. Target Database
        target_group = QGroupBox(_("Target Database"))
        target_layout = QVBoxLayout(target_group)
        self.rb_global = QRadioButton(_("Global Glossary"))
        self.rb_project = QRadioButton(_("Project Glossary"))

        self.rb_global.setChecked(True)
        if not has_project:
            self.rb_project.setEnabled(False)
            self.rb_project.setToolTip(_("No project currently open"))

        target_layout.addWidget(self.rb_global)
        target_layout.addWidget(self.rb_project)
        layout.addWidget(target_group)

        # 2. Conflict Strategy
        strat_group = QGroupBox(_("Conflict Resolution"))
        strat_layout = QVBoxLayout(strat_group)
        self.rb_skip = QRadioButton(_("Skip existing entries"))
        self.rb_overwrite = QRadioButton(_("Overwrite existing entries"))
        self.rb_merge = QRadioButton(_("Merge (Add as alternative)"))
        self.rb_manual = QRadioButton(_("Manual Intervention"))

        self.rb_manual.setChecked(True)  # Default to manual for safety

        strat_layout.addWidget(self.rb_skip)
        strat_layout.addWidget(self.rb_overwrite)
        strat_layout.addWidget(self.rb_merge)
        strat_layout.addWidget(self.rb_manual)
        layout.addWidget(strat_group)

        # 3. Options
        opt_group = QGroupBox(_("Options"))
        opt_layout = QVBoxLayout(opt_group)
        self.chk_context = QCheckBox(_("Save Context as Comment"))
        self.chk_context.setChecked(True)
        opt_layout.addWidget(self.chk_context)
        layout.addWidget(opt_group)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self):
        target = 'project' if self.rb_project.isChecked() else 'global'

        strategy = 'manual'
        if self.rb_skip.isChecked():
            strategy = 'skip'
        elif self.rb_overwrite.isChecked():
            strategy = 'overwrite'
        elif self.rb_merge.isChecked():
            strategy = 'merge'

        return {
            'target_db': target,
            'strategy': strategy,
            'save_context': self.chk_context.isChecked()
        }


class GlossaryConflictDialog(QDialog):
    def __init__(self, parent, conflicts, new_entries):
        """
        conflicts: dict from service.find_conflicts
        new_entries: list of dicts {'source':, 'target':, ...}
        """
        super().__init__(parent)
        self.setWindowTitle(_("Resolve Conflicts"))
        self.resize(800, 600)
        self.conflicts = conflicts
        self.new_entries = new_entries
        self.resolutions = {}  # source_lower -> action

        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        layout.addWidget(
            QLabel(_("The following terms already exist in the glossary. Please choose an action for each.")))

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            [_("Source Term"), _("Existing Translation"), _("New Translation"), _("Action")])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.table.setColumnWidth(3, 150)

        layout.addWidget(self.table)

        self.populate_table()

        # Batch Actions
        batch_layout = QHBoxLayout()
        batch_layout.addWidget(QLabel(_("Set all to:")))
        btn_skip_all = QPushButton(_("Skip"))
        btn_over_all = QPushButton(_("Overwrite"))
        btn_merge_all = QPushButton(_("Merge"))

        btn_skip_all.clicked.connect(lambda: self.set_all_actions('skip'))
        btn_over_all.clicked.connect(lambda: self.set_all_actions('overwrite'))
        btn_merge_all.clicked.connect(lambda: self.set_all_actions('merge'))

        batch_layout.addWidget(btn_skip_all)
        batch_layout.addWidget(btn_over_all)
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
            src_lower = entry['source'].strip().lower()
            if src_lower in self.conflicts:
                conflict_info = self.conflicts[src_lower]

                row = self.table.rowCount()
                self.table.insertRow(row)

                # Source
                self.table.setItem(row, 0, QTableWidgetItem(conflict_info['original_text']))

                # Existing
                existing_str = "; ".join(conflict_info['existing_targets'])
                self.table.setItem(row, 1, QTableWidgetItem(existing_str))

                # New
                self.table.setItem(row, 2, QTableWidgetItem(entry['target']))

                # Action Combo
                combo = QComboBox()
                combo.addItem(_("Skip"), 'skip')
                combo.addItem(_("Overwrite"), 'overwrite')
                combo.addItem(_("Merge"), 'merge')
                combo.setCurrentIndex(2)  # Default Merge

                # Store source key in combo to retrieve later
                combo.setProperty("source_key", src_lower)

                self.table.setCellWidget(row, 3, combo)

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
            src_key = combo.property("source_key")
            action = combo.currentData()
            self.resolutions[src_key] = action
        super().accept()