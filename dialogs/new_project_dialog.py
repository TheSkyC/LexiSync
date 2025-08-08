# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit,
                               QPushButton, QDialogButtonBox, QFileDialog,
                               QListWidget, QListWidgetItem, QHBoxLayout,
                               QComboBox, QMessageBox, QCheckBox)
from utils.localization import _
from utils.constants import SUPPORTED_LANGUAGES

class NewProjectDialog(QDialog):
    def __init__(self, parent=None, app_instance=None):
        super().__init__(parent)
        self.app = app_instance
        self.source_files = []

        self.setWindowTitle(_("New Project"))
        self.setModal(True)
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.project_name_edit = QLineEdit()
        self.location_edit = QLineEdit()
        self.browse_button = QPushButton("...")
        self.browse_button.setFixedWidth(30)

        location_layout = QHBoxLayout()
        location_layout.addWidget(self.location_edit)
        location_layout.addWidget(self.browse_button)

        self.source_lang_combo = QComboBox()
        self.target_lang_combo = QComboBox()
        self._populate_lang_combos()

        self.source_files_list = QListWidget()
        self.source_files_list.setFixedHeight(100)
        add_file_button = QPushButton(_("Add Source File..."))

        form_layout.addRow(_("Project Name:"), self.project_name_edit)
        form_layout.addRow(_("Location:"), location_layout)
        form_layout.addRow(_("Source Language:"), self.source_lang_combo)
        form_layout.addRow(_("Initial Target Language:"), self.target_lang_combo)
        form_layout.addRow(_("Source Files:"), self.source_files_list)
        form_layout.addRow("", add_file_button)
        self.use_global_tm_checkbox = QCheckBox(_("Use Global Translation Memory"))
        self.use_global_tm_checkbox.setChecked(True)
        self.use_global_tm_checkbox.setToolTip(
            _("If checked, the project will be able to read suggestions from the global TM (read-only).")
        )
        form_layout.addRow("", self.use_global_tm_checkbox)

        layout.addLayout(form_layout)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(button_box)

        self.browse_button.clicked.connect(self.browse_location)
        add_file_button.clicked.connect(self.add_source_file)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

    def _populate_lang_combos(self):
        for name, code in sorted(SUPPORTED_LANGUAGES.items()):
            self.source_lang_combo.addItem(name, code)
            self.target_lang_combo.addItem(name, code)
        self.source_lang_combo.setCurrentText("English")
        self.target_lang_combo.setCurrentText("简体中文")

    def browse_location(self):
        directory = QFileDialog.getExistingDirectory(self, _("Select Project Location"))
        if directory:
            self.location_edit.setText(directory)

    def add_source_file(self):
        filepath, __ = QFileDialog.getOpenFileName(
            self, _("Select Source File"), "",
            _("All Supported Files (*.ow *.txt *.po *.pot);;All Files (*.*)")
        )
        if filepath:
            file_info = {'path': filepath, 'type': 'code'}
            self.source_files.append(file_info)
            self.source_files_list.addItem(QListWidgetItem(filepath))

    def get_data(self):
        return {
            "name": self.project_name_edit.text(),
            "location": self.location_edit.text(),
            "source_lang": self.source_lang_combo.currentData(),
            "target_langs": [self.target_lang_combo.currentData()],
            "source_files": self.source_files,
            "use_global_tm": self.use_global_tm_checkbox.isChecked()
        }

    def accept(self):
        data = self.get_data()
        if not data['name'] or not data['location'] or not data['source_files']:
            QMessageBox.warning(self, _("Missing Information"), _("Project name, location, and at least one source file are required."))
            return
        if data['source_lang'] == data['target_langs'][0]:
            QMessageBox.warning(self, _("Invalid Languages"), _("Source and target languages cannot be the same."))
            return
        super().accept()