# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QCheckBox, QDialog, QDialogButtonBox, QGroupBox, QRadioButton, QVBoxLayout

from lexisync.utils.localization import _


class ExportQADialog(QDialog):
    def __init__(self, parent, is_project_mode=False):
        super().__init__(parent)
        self.is_project_mode = is_project_mode
        self.setWindowTitle(_("Export QA Report"))
        self.setMinimumWidth(400)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # 1. 导出范围
        scope_group = QGroupBox(_("Export Scope"))
        scope_layout = QVBoxLayout(scope_group)
        self.rb_current = QRadioButton(_("Current File / Filtered View"))
        self.rb_project = QRadioButton(_("Whole Project (Scan all files)"))
        self.rb_current.setChecked(True)

        if not self.is_project_mode:
            self.rb_project.setEnabled(False)
            self.rb_project.setToolTip(_("Only available in Project Mode"))

        scope_layout.addWidget(self.rb_current)
        scope_layout.addWidget(self.rb_project)
        layout.addWidget(scope_group)

        # 2. 严重程度过滤
        level_group = QGroupBox(_("Include Severity Levels"))
        level_layout = QVBoxLayout(level_group)
        self.chk_error = QCheckBox(_("Errors (Critical issues)"))
        self.chk_warning = QCheckBox(_("Warnings (Potential issues)"))
        self.chk_info = QCheckBox(_("Info (Suggestions)"))
        self.chk_error.setChecked(True)
        self.chk_warning.setChecked(True)
        self.chk_info.setChecked(False)

        level_layout.addWidget(self.chk_error)
        level_layout.addWidget(self.chk_warning)
        level_layout.addWidget(self.chk_info)
        layout.addWidget(level_group)

        # 3. 额外选项
        opt_group = QGroupBox(_("Additional Options"))
        opt_layout = QVBoxLayout(opt_group)
        self.chk_ignored = QCheckBox(_("Include issues marked as 'Ignored'"))
        self.chk_ignored.setChecked(False)
        opt_layout.addWidget(self.chk_ignored)
        layout.addWidget(opt_group)

        # 按钮
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.button(QDialogButtonBox.Ok).setText(_("Export..."))
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_config(self):
        return {
            "scope": "project" if self.rb_project.isChecked() else "current",
            "levels": {
                "error": self.chk_error.isChecked(),
                "warning": self.chk_warning.isChecked(),
                "info": self.chk_info.isChecked(),
            },
            "include_ignored": self.chk_ignored.isChecked(),
        }
