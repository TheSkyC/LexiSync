# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit,
                               QPushButton, QDialogButtonBox, QFileDialog,
                               QListWidget, QListWidgetItem, QHBoxLayout,
                               QComboBox, QMessageBox, QCheckBox, QTabWidget, QWidget,
                               QLabel, QGroupBox)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QDragMoveEvent, QDragLeaveEvent
import os
from utils.localization import _
from utils.constants import SUPPORTED_LANGUAGES
import logging

logger = logging.getLogger(__name__)


class DropListWidget(QListWidget):
    """A QListWidget that provides visual feedback for drag-and-drop."""
    files_dropped = Signal(list, str)  # files, widget_type

    def __init__(self, widget_type, parent=None):
        super().__init__(parent)
        self.widget_type = widget_type  # 'source', 'glossary', 'tm'
        self.setAcceptDrops(True)
        self.setStyleSheet("QListWidget { border: 1px solid #ccc; border-radius: 4px; }")

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            valid_files = []

            for url in urls:
                if url.isLocalFile():
                    filepath = url.toLocalFile()
                    ext = os.path.splitext(filepath)[1].lower()

                    if self.widget_type == 'source' and ext in ['.ow', '.txt', '.po', '.pot']:
                        valid_files.append(filepath)
                    elif self.widget_type == 'glossary' and ext == '.tbx':
                        valid_files.append(filepath)
                    elif self.widget_type == 'tm' and ext == '.xlsx':
                        valid_files.append(filepath)

            if valid_files:
                self.setStyleSheet("QListWidget { border: 2px dashed #409EFF; background-color: #f0f9ff; }")
                event.acceptProposedAction()
            else:
                self.setStyleSheet("QListWidget { border: 2px dashed #ff6b6b; background-color: #fff0f0; }")
                event.ignore()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self.setStyleSheet("QListWidget { border: 1px solid #ccc; border-radius: 4px; }")

    def dropEvent(self, event: QDropEvent):
        self.setStyleSheet("QListWidget { border: 1px solid #ccc; border-radius: 4px; }")

        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            valid_files = []

            for url in urls:
                if url.isLocalFile():
                    filepath = url.toLocalFile()
                    ext = os.path.splitext(filepath)[1].lower()

                    if self.widget_type == 'source' and ext in ['.ow', '.txt', '.po', '.pot']:
                        valid_files.append(filepath)
                    elif self.widget_type == 'glossary' and ext == '.tbx':
                        valid_files.append(filepath)
                    elif self.widget_type == 'tm' and ext == '.xlsx':
                        valid_files.append(filepath)

            if valid_files:
                self.files_dropped.emit(valid_files, self.widget_type)
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()


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

        source_files_widget = QWidget()
        source_files_layout = QVBoxLayout(source_files_widget)
        source_files_layout.setContentsMargins(0, 0, 0, 0)

        self.source_files_list = DropListWidget('source')
        self.source_files_list.setToolTip(
            _("Drag and drop .ow, .txt, .po, or .pot files here or use the buttons below."))
        self.source_files_list.setFixedHeight(120)
        self.source_files_list.files_dropped.connect(self.handle_files_dropped)

        source_buttons_layout = QHBoxLayout()
        add_file_button = QPushButton(_("Add..."))
        remove_file_button = QPushButton(_("Remove"))
        source_buttons_layout.addStretch()
        source_buttons_layout.addWidget(add_file_button)
        source_buttons_layout.addWidget(remove_file_button)

        source_files_layout.addWidget(self.source_files_list)
        source_files_layout.addLayout(source_buttons_layout)

        basic_layout.addRow(_("Project Name:"), self.project_name_edit)
        basic_layout.addRow(_("Location:"), location_layout)
        basic_layout.addRow(_("Source Language:"), self.source_lang_combo)
        basic_layout.addRow(_("Initial Target Language:"), self.target_lang_combo)
        basic_layout.addRow(_("Source Files:"), source_files_widget)

        self.tab_widget.addTab(basic_tab, _("Basic Settings"))

        # --- Tab 2: Resources ---
        resources_tab = QWidget()
        resources_layout = QVBoxLayout(resources_tab)

        glossary_group = QGroupBox(_("Project Glossary"))
        glossary_layout = QVBoxLayout(glossary_group)

        self.glossary_files_list = DropListWidget('glossary')
        self.glossary_files_list.setToolTip(_("Drag and drop .tbx files here or use the buttons below."))
        self.glossary_files_list.setFixedHeight(80)
        self.glossary_files_list.files_dropped.connect(self.handle_files_dropped)

        add_glossary_button = QPushButton(_("Add..."))
        remove_glossary_button = QPushButton(_("Remove"))
        glossary_buttons_layout = QHBoxLayout()
        glossary_buttons_layout.addStretch()
        glossary_buttons_layout.addWidget(add_glossary_button)
        glossary_buttons_layout.addWidget(remove_glossary_button)
        glossary_layout.addWidget(self.glossary_files_list)
        glossary_layout.addLayout(glossary_buttons_layout)
        self.use_global_glossary_checkbox = QCheckBox(_("Use Global Glossary"))
        self.use_global_glossary_checkbox.setChecked(True)
        glossary_layout.addWidget(self.use_global_glossary_checkbox)
        resources_layout.addWidget(glossary_group)

        tm_group = QGroupBox(_("Project Translation Memory"))
        tm_layout = QVBoxLayout(tm_group)

        self.tm_files_list = DropListWidget('tm')
        self.tm_files_list.setToolTip(_("Drag and drop .xlsx files here or use the buttons below."))
        self.tm_files_list.setFixedHeight(80)
        self.tm_files_list.files_dropped.connect(self.handle_files_dropped)

        add_tm_button = QPushButton(_("Add..."))
        remove_tm_button = QPushButton(_("Remove"))
        tm_buttons_layout = QHBoxLayout()
        tm_buttons_layout.addStretch()
        tm_buttons_layout.addWidget(add_tm_button)
        tm_buttons_layout.addWidget(remove_tm_button)
        tm_layout.addWidget(self.tm_files_list)
        tm_layout.addLayout(tm_buttons_layout)
        self.use_global_tm_checkbox = QCheckBox(_("Use Global Translation Memory"))
        self.use_global_tm_checkbox.setChecked(True)
        tm_layout.addWidget(self.use_global_tm_checkbox)
        resources_layout.addWidget(tm_group)

        resources_layout.addStretch()
        self.tab_widget.addTab(resources_tab, _("Resources"))

        main_layout.addWidget(self.tab_widget)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        main_layout.addWidget(button_box)

        # --- Connections ---
        self.browse_button.clicked.connect(self.browse_location)
        add_file_button.clicked.connect(self.add_source_files)
        remove_file_button.clicked.connect(lambda: self._remove_item(self.source_files_list, self.source_files))
        add_glossary_button.clicked.connect(self.add_glossary_files)
        remove_glossary_button.clicked.connect(lambda: self._remove_item(self.glossary_files_list, self.glossary_files))
        add_tm_button.clicked.connect(self.add_tm_files)
        remove_tm_button.clicked.connect(lambda: self._remove_item(self.tm_files_list, self.tm_files))
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

    def handle_files_dropped(self, files, widget_type):
        """处理从DropListWidget发射的文件拖放信号"""
        try:
            if widget_type == 'source':
                self._process_source_files(files)
                logger.info(f"Added {len(files)} source files via drag-drop")
            elif widget_type == 'glossary':
                self._process_generic_files(files, self.glossary_files, self.glossary_files_list)
                logger.info(f"Added {len(files)} glossary files via drag-drop")
            elif widget_type == 'tm':
                self._process_generic_files(files, self.tm_files, self.tm_files_list)
                logger.info(f"Added {len(files)} TM files via drag-drop")
            else:
                logger.warning(f"Unknown widget type: {widget_type}")
        except Exception as e:
            logger.error(f"Error processing dropped files: {e}")
            QMessageBox.warning(self, _("Error"), _("Failed to process dropped files: {}").format(str(e)))

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
            self._process_generic_files(filepaths, self.glossary_files, self.glossary_files_list)

    def add_tm_files(self):
        filepaths, __ = QFileDialog.getOpenFileNames(
            self, _("Select TM Files"), "", f"{_('Excel Files')} (*.xlsx)"
        )
        if filepaths:
            self._process_generic_files(filepaths, self.tm_files, self.tm_files_list)

    def _process_source_files(self, filepaths):
        added_count = 0
        for path in filepaths:
            if not any(f['path'] == path for f in self.source_files):
                file_type = 'po' if path.lower().endswith(('.po', '.pot')) else 'code'
                file_info = {'path': path, 'type': file_type}
                self.source_files.append(file_info)
                self.source_files_list.addItem(QListWidgetItem(os.path.basename(path)))
                added_count += 1

        if added_count > 0:
            logger.info(f"Added {added_count} source files")

    def _process_generic_files(self, filepaths, data_list, list_widget):
        added_count = 0
        for path in filepaths:
            if path not in data_list:
                data_list.append(path)
                list_widget.addItem(QListWidgetItem(os.path.basename(path)))
                added_count += 1

        if added_count > 0:
            list_name = "glossary" if data_list is self.glossary_files else "TM"
            logger.info(f"Added {added_count} {list_name} files")

    def _remove_item(self, list_widget, data_list):
        current_item = list_widget.currentItem()
        if not current_item:
            return

        item_text = current_item.text()
        row = list_widget.row(current_item)

        if data_list is self.source_files:
            data_list[:] = [f for f in data_list if os.path.basename(f['path']) != item_text]
        else:
            data_list[:] = [p for p in data_list if os.path.basename(p) != item_text]
        list_widget.takeItem(row)

    def get_data(self):
        return {
            "name": self.project_name_edit.text(),
            "location": self.location_edit.text(),
            "source_lang": self.source_lang_combo.currentData(),
            "target_langs": [self.target_lang_combo.currentData()],
            "source_files": self.source_files,
            "glossary_files": self.glossary_files,
            "tm_files": self.tm_files,
            "use_global_tm": self.use_global_tm_checkbox.isChecked(),
            "use_global_glossary": self.use_global_glossary_checkbox.isChecked()
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