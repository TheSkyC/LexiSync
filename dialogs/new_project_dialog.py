# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit,
                               QPushButton, QDialogButtonBox, QFileDialog,
                               QListWidget, QListWidgetItem, QHBoxLayout,
                               QComboBox, QMessageBox, QCheckBox, QTabWidget, QWidget,
                               QLabel)
from PySide6.QtCore import Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent
import os
from utils.localization import _
from utils.constants import SUPPORTED_LANGUAGES


class NewProjectDialog(QDialog):
    def __init__(self, parent=None, app_instance=None):
        super().__init__(parent)
        self.app = app_instance
        self.source_files = []
        self.glossary_files = []
        self.tm_files = []

        self.setWindowTitle(_("New Project"))
        self.setModal(True)
        self.setMinimumWidth(600)
        self.setAcceptDrops(True)

        main_layout = QVBoxLayout(self)
        self.tab_widget = QTabWidget()

        # --- Tab 1: Basic Settings ---
        basic_tab = QWidget()
        basic_layout = QFormLayout(basic_tab)

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
        self.source_files_list.setToolTip(_("Drag and drop files here or use the button below."))
        self.source_files_list.setStyleSheet("QListWidget { border: 1px solid #ccc; border-radius: 4px; }")
        self.source_files_list.setFixedHeight(120)
        add_file_button = QPushButton(_("Add Source File(s)..."))

        basic_layout.addRow(_("Project Name:"), self.project_name_edit)
        basic_layout.addRow(_("Location:"), location_layout)
        basic_layout.addRow(_("Source Language:"), self.source_lang_combo)
        basic_layout.addRow(_("Initial Target Language:"), self.target_lang_combo)
        basic_layout.addRow(_("Source Files:"), self.source_files_list)
        basic_layout.addRow("", add_file_button)

        self.tab_widget.addTab(basic_tab, _("Basic Settings"))

        # --- Tab 2: Resources ---
        resources_tab = QWidget()
        resources_layout = QVBoxLayout(resources_tab)

        # Glossary
        glossary_group = QWidget()
        glossary_layout = QVBoxLayout(glossary_group)
        glossary_layout.setContentsMargins(0, 0, 0, 0)
        glossary_layout.addWidget(QLabel(f"<b>{_('Project Glossary')}</b>"))
        self.glossary_files_list = QListWidget()
        self.glossary_files_list.setFixedHeight(80)
        add_glossary_button = QPushButton(_("Add Glossary File (.tbx)..."))
        glossary_layout.addWidget(self.glossary_files_list)
        glossary_layout.addWidget(add_glossary_button, 0, Qt.AlignRight)
        resources_layout.addWidget(glossary_group)

        # Translation Memory
        tm_group = QWidget()
        tm_layout = QVBoxLayout(tm_group)
        tm_layout.setContentsMargins(0, 0, 0, 0)
        tm_layout.addWidget(QLabel(f"<b>{_('Project Translation Memory')}</b>"))
        self.tm_files_list = QListWidget()
        self.tm_files_list.setFixedHeight(80)
        add_tm_button = QPushButton(_("Add TM File (.xlsx)..."))
        tm_layout.addWidget(self.tm_files_list)
        tm_layout.addWidget(add_tm_button, 0, Qt.AlignRight)
        resources_layout.addWidget(tm_group)

        self.use_global_tm_checkbox = QCheckBox(_("Use Global Translation Memory"))
        self.use_global_tm_checkbox.setChecked(True)
        self.use_global_tm_checkbox.setToolTip(
            _("If checked, the project will be able to read suggestions from the global TM (read-only).")
        )
        resources_layout.addWidget(self.use_global_tm_checkbox)
        resources_layout.addStretch()

        self.tab_widget.addTab(resources_tab, _("Resources"))

        main_layout.addWidget(self.tab_widget)

        # --- Dialog Buttons ---
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        main_layout.addWidget(button_box)

        # --- Connections ---
        self.browse_button.clicked.connect(self.browse_location)
        add_file_button.clicked.connect(self.add_source_files)
        add_glossary_button.clicked.connect(self.add_glossary_files)
        add_tm_button.clicked.connect(self.add_tm_files)
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

    def add_source_files(self):
        filepaths, __ = QFileDialog.getOpenFileNames(
            self, _("Select Source Files"), "",
            _("All Supported Files (*.ow *.txt *.po *.pot);;All Files (*.*)")
        )
        if filepaths:
            self._process_source_files(filepaths)

    def add_glossary_files(self):
        filepaths, __ = QFileDialog.getOpenFileNames(
            self, _("Select Glossary Files"), "", f"{_('TBX Files')} (*.tbx)"
        )
        if filepaths:
            for path in filepaths:
                if path not in self.glossary_files:
                    self.glossary_files.append(path)
                    self.glossary_files_list.addItem(QListWidgetItem(os.path.basename(path)))

    def add_tm_files(self):
        filepaths, __ = QFileDialog.getOpenFileNames(
            self, _("Select TM Files"), "", f"{_('Excel Files')} (*.xlsx)"
        )
        if filepaths:
            for path in filepaths:
                if path not in self.tm_files:
                    self.tm_files.append(path)
                    self.tm_files_list.addItem(QListWidgetItem(os.path.basename(path)))

    def _process_source_files(self, filepaths):
        for path in filepaths:
            if not any(f['path'] == path for f in self.source_files):
                file_type = 'po' if path.lower().endswith(('.po', '.pot')) else 'code'
                file_info = {'path': path, 'type': file_type}
                self.source_files.append(file_info)
                self.source_files_list.addItem(QListWidgetItem(os.path.basename(path)))

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        filepaths = [url.toLocalFile() for url in urls if url.isLocalFile()]
        if filepaths:
            self._process_source_files(filepaths)

    def get_data(self):
        return {
            "name": self.project_name_edit.text(),
            "location": self.location_edit.text(),
            "source_lang": self.source_lang_combo.currentData(),
            "target_langs": [self.target_lang_combo.currentData()],
            "source_files": self.source_files,
            "glossary_files": self.glossary_files,
            "tm_files": self.tm_files,
            "use_global_tm": self.use_global_tm_checkbox.isChecked()
        }

    def accept(self):
        data = self.get_data()
        if not data['name'] or not data['location'] or not data['source_files']:
            QMessageBox.warning(self, _("Missing Information"),
                                _("Project name, location, and at least one source file are required."))
            self.tab_widget.setCurrentIndex(0)
            return
        if data['source_lang'] == data['target_langs'][0]:
            QMessageBox.warning(self, _("Invalid Languages"), _("Source and target languages cannot be the same."))
            self.tab_widget.setCurrentIndex(0)
            return
        super().accept()