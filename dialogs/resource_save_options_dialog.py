# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QGroupBox, QRadioButton,
                               QCheckBox, QDialogButtonBox, QLabel, QFrame, QHBoxLayout)
from PySide6.QtCore import Qt
from utils.localization import _


class ResourceSaveOptionsDialog(QDialog):
    def __init__(self, parent, resource_type: str, has_project: bool, count: int = 0):
        """
        :param resource_type: 'tm' or 'glossary'
        :param has_project: Whether a project is currently open
        :param count: Number of items to save (optional, for display)
        """
        super().__init__(parent)
        self.resource_type = resource_type

        title = _("Save to Translation Memory") if resource_type == 'tm' else _("Save to Glossary")
        self.setWindowTitle(title)

        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        if count > 0:
            info_frame = QFrame()
            info_frame.setObjectName("infoFrame")
            info_frame.setStyleSheet("""
                QFrame#infoFrame {
                    background-color: #E3F2FD; /* Light Blue */
                    border: 1px solid #BBDEFB;
                    border-radius: 4px;
                }
                QLabel {
                    color: #0D47A1; /* Dark Blue Text */
                    font-weight: bold;
                    border: none;
                    background: transparent;
                }
            """)
            info_layout = QHBoxLayout(info_frame)
            info_layout.setContentsMargins(10, 8, 10, 8)

            info_text = _("Ready to save {count} items.").format(count=count)
            info_label = QLabel(info_text)
            info_layout.addWidget(info_label)

            layout.addWidget(info_frame)

        # 1. Target Database
        target_group = QGroupBox(_("Target Database"))
        target_layout = QVBoxLayout(target_group)
        target_layout.setSpacing(8)

        global_text = _("Global TM") if resource_type == 'tm' else _("Global Glossary")
        project_text = _("Project TM") if resource_type == 'tm' else _("Project Glossary")

        self.rb_global = QRadioButton(global_text)
        self.rb_project = QRadioButton(project_text)

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
        strat_layout.setSpacing(8)

        self.rb_manual = QRadioButton(_("Manual Intervention"))
        self.rb_skip = QRadioButton(_("Skip existing entries"))
        self.rb_overwrite = QRadioButton(_("Overwrite existing entries"))

        # Merge is only for Glossary
        self.rb_merge = None
        if resource_type == 'glossary':
            self.rb_merge = QRadioButton(_("Merge"))

        # Tooltips
        self.rb_manual.setToolTip(_("Show a dialog to resolve conflicts one by one."))
        self.rb_overwrite.setToolTip(_("Update existing entries with new translations."))
        self.rb_skip.setToolTip(_("Keep existing entries and ignore new ones."))

        # Default selection
        self.rb_manual.setChecked(True)

        strat_layout.addWidget(self.rb_manual)
        strat_layout.addWidget(self.rb_overwrite)
        strat_layout.addWidget(self.rb_skip)
        if self.rb_merge:
            strat_layout.addWidget(self.rb_merge)

        layout.addWidget(strat_group)

        # 3. Options (Glossary Only)
        if resource_type == 'glossary':
            opt_group = QGroupBox(_("Options"))
            opt_layout = QVBoxLayout(opt_group)
            self.chk_context = QCheckBox(_("Save Context as Comment"))
            self.chk_context.setChecked(True)
            opt_layout.addWidget(self.chk_context)
            layout.addWidget(opt_group)

        layout.addStretch()

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
        elif self.rb_merge and self.rb_merge.isChecked():
            strategy = 'merge'

        data = {
            'target_db': target,
            'strategy': strategy
        }

        if self.resource_type == 'glossary':
            data['save_context'] = self.chk_context.isChecked()

        return data