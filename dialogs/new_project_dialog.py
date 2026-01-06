# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit,
                               QPushButton, QFileDialog, QLabel, QGroupBox,
                               QListWidgetItem, QHBoxLayout, QTabWidget,
                               QComboBox, QMessageBox, QCheckBox, QWidget,
                               QTreeWidget, QTreeWidgetItem, QHeaderView)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QDragMoveEvent
import os
from datetime import datetime
from ui_components.styled_button import StyledButton
from utils.text_utils import format_file_size
from utils.constants import SUPPORTED_LANGUAGES
from utils.localization import _
import logging

logger = logging.getLogger(__name__)


class DropTreeWidget(QTreeWidget):
    files_dropped = Signal(list, str)

    def __init__(self, widget_type, parent=None):
        super().__init__(parent)
        self.widget_type = widget_type
        self.setAcceptDrops(True)
        self.setRootIsDecorated(False)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(True)
        self.setSelectionBehavior(QTreeWidget.SelectRows)
        self.setStyleSheet("QTreeWidget { border: 1px solid #ccc; border-radius: 4px; }")

        header = self.header()
        if widget_type == 'source':
            self.setHeaderLabels([_("File Name"), _("Type"), _("Size"), _("Path")])
            header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
            header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
            header.setSectionResizeMode(3, QHeaderView.Stretch)
            self.setColumnWidth(1, 70)
            self.setColumnWidth(2, 70)
        else:
            self.setHeaderLabels([_("File Name"), _("Size"), _("Modified"), _("Path")])
            header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
            header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
            header.setSectionResizeMode(3, QHeaderView.Stretch)
            self.setColumnWidth(1, 70)
            self.setColumnWidth(2, 70)

    def add_file_item(self, filepath, file_info=None):
        try:
            stat = os.stat(filepath)
            filename = os.path.basename(filepath)
            size_str = format_file_size(stat.st_size)

            item = QTreeWidgetItem()
            item.setText(0, filename)

            if self.widget_type == 'source':
                ext = os.path.splitext(filepath)[1].lower()
                type_map = {'.po': 'PO', '.pot': 'POT', '.ow': 'Code', '.txt': 'Code'}
                type_display = type_map.get(ext, 'Code')
                item.setText(1, type_display)
                item.setText(2, size_str)
                item.setText(3, filepath)
            else:
                modified_time = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                item.setText(1, size_str)
                item.setText(2, modified_time)
                item.setText(3, filepath)

            item.setToolTip(0, filepath)
            self.addTopLevelItem(item)
            return item
        except OSError:
            return None

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            can_accept = False
            for url in urls:
                if url.isLocalFile():
                    filepath = url.toLocalFile()
                    ext = os.path.splitext(filepath)[1].lower()
                    if self.widget_type == 'source' and ext in ['.ow', '.txt', '.po', '.pot']:
                        can_accept = True
                        break
                    elif self.widget_type == 'glossary' and ext == '.tbx':
                        can_accept = True
                        break
                    elif self.widget_type == 'tm' and ext == '.xlsx':
                        can_accept = True
                        break

            if can_accept:
                self.setStyleSheet("QTreeWidget { border: 2px dashed #409EFF; background-color: #f0f9ff; }")
                event.acceptProposedAction()
            else:
                self.setStyleSheet("QTreeWidget { border: 2px dashed #F56C6C; background-color: #fef0f0; }")
                event.ignore()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self.setStyleSheet("QTreeWidget { border: 1px solid #ccc; border-radius: 4px; }")

    def dropEvent(self, event: QDropEvent):
        self.setStyleSheet("QTreeWidget { border: 1px solid #ccc; border-radius: 4px; }")
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
        self.setMinimumHeight(600)

        main_layout = QVBoxLayout(self)
        self.tab_widget = QTabWidget()

        # Tab 1: Basic Settings
        basic_tab = QWidget()
        basic_layout = QFormLayout(basic_tab)

        self.project_name_edit = QLineEdit()
        self.location_edit = QLineEdit()
        self.browse_button = StyledButton("...", on_click=self.browse_location, size="small")
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

        self.source_files_tree = DropTreeWidget('source')
        self.source_files_tree.setToolTip(_("Drag and drop files here"))
        self.source_files_tree.setMinimumHeight(150)
        self.source_files_tree.files_dropped.connect(self.handle_files_dropped)

        source_buttons_layout = QHBoxLayout()
        add_file_button = StyledButton(_("Add..."), on_click=self.add_source_files)
        remove_file_button = StyledButton(_("Remove"), on_click=lambda: self._remove_item(self.source_files_tree, self.source_files), btn_type="danger")

        source_buttons_layout.addStretch()
        source_buttons_layout.addWidget(add_file_button)
        source_buttons_layout.addWidget(remove_file_button)

        source_files_layout.addWidget(self.source_files_tree)
        source_files_layout.addLayout(source_buttons_layout)

        basic_layout.addRow(_("Project Name:"), self.project_name_edit)
        basic_layout.addRow(_("Location:"), location_layout)
        basic_layout.addRow(_("Source Language:"), self.source_lang_combo)
        basic_layout.addRow(_("Initial Target Language:"), self.target_lang_combo)
        basic_layout.addRow(_("Source Files:"), source_files_widget)

        self.tab_widget.addTab(basic_tab, _("Basic Settings"))

        # Tab 2: Resources
        resources_tab = QWidget()
        resources_layout = QVBoxLayout(resources_tab)

        glossary_group = QGroupBox(_("Project Glossary"))
        glossary_layout = QVBoxLayout(glossary_group)
        self.glossary_files_tree = DropTreeWidget('glossary')
        self.glossary_files_tree.setToolTip(_("Drag and drop .tbx files here"))
        self.glossary_files_tree.setMaximumHeight(120)
        self.glossary_files_tree.files_dropped.connect(self.handle_files_dropped)

        glossary_bottom_layout = QHBoxLayout()
        self.use_global_glossary_checkbox = QCheckBox(_("Use Global Glossary"))
        self.use_global_glossary_checkbox.setChecked(True)
        add_glossary_button = StyledButton(_("Add..."), on_click=self.add_glossary_files)
        remove_glossary_button = StyledButton(_("Remove"), on_click=lambda: self._remove_item(self.glossary_files_tree, self.glossary_files), btn_type="danger")

        glossary_bottom_layout.addWidget(self.use_global_glossary_checkbox)
        glossary_bottom_layout.addStretch()
        glossary_bottom_layout.addWidget(add_glossary_button)
        glossary_bottom_layout.addWidget(remove_glossary_button)

        glossary_layout.addWidget(self.glossary_files_tree)
        glossary_layout.addLayout(glossary_bottom_layout)
        resources_layout.addWidget(glossary_group)

        tm_group = QGroupBox(_("Project Translation Memory"))
        tm_layout = QVBoxLayout(tm_group)
        self.tm_files_tree = DropTreeWidget('tm')
        self.tm_files_tree.setToolTip(_("Drag and drop .xlsx files here"))
        self.tm_files_tree.setMaximumHeight(120)
        self.tm_files_tree.files_dropped.connect(self.handle_files_dropped)

        tm_bottom_layout = QHBoxLayout()
        self.use_global_tm_checkbox = QCheckBox(_("Use Global Translation Memory"))
        self.use_global_tm_checkbox.setChecked(True)
        add_tm_button = StyledButton(_("Add..."), on_click=self.add_tm_files)
        remove_tm_button = StyledButton(_("Remove"), on_click=lambda: self._remove_item(self.tm_files_tree, self.tm_files), btn_type="danger")

        tm_bottom_layout.addWidget(self.use_global_tm_checkbox)
        tm_bottom_layout.addStretch()
        tm_bottom_layout.addWidget(add_tm_button)
        tm_bottom_layout.addWidget(remove_tm_button)

        tm_layout.addWidget(self.tm_files_tree)
        tm_layout.addLayout(tm_bottom_layout)
        resources_layout.addWidget(tm_group)

        resources_layout.addStretch()
        self.tab_widget.addTab(resources_tab, _("Resources"))

        main_layout.addWidget(self.tab_widget)

        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 10, 0, 0)
        button_layout.setSpacing(15)
        button_layout.addStretch()

        self.ok_button = StyledButton(_("OK"), on_click=self.accept, btn_type="primary", size="large")
        self.cancel_button = StyledButton(_("Cancel"), on_click=self.reject, btn_type="default", size="large")

        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)

        main_layout.addLayout(button_layout)


    def dragMoveEvent(self, event: QDragMoveEvent):
        pass

    def handle_files_dropped(self, files, widget_type):
        if widget_type == 'source':
            self._process_source_files(files)
        elif widget_type == 'glossary':
            self._process_generic_files(files, self.glossary_files, self.glossary_files_tree)
        elif widget_type == 'tm':
            self._process_generic_files(files, self.tm_files, self.tm_files_tree)

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
            self._process_generic_files(filepaths, self.glossary_files, self.glossary_files_tree)

    def add_tm_files(self):
        filepaths, __ = QFileDialog.getOpenFileNames(
            self, _("Select TM Files"), "", f"{_('Excel Files')} (*.xlsx)"
        )
        if filepaths:
            self._process_generic_files(filepaths, self.tm_files, self.tm_files_tree)

    def _process_source_files(self, filepaths):
        for path in filepaths:
            if not any(f['path'] == path for f in self.source_files):
                normalized_path = path.replace('\\', '/')
                file_type = 'po' if normalized_path.lower().endswith(('.po', '.pot')) else 'code'
                file_info = {'path': normalized_path, 'type': file_type}
                if self.source_files_tree.add_file_item(path, file_info):
                    self.source_files.append(file_info)

    def _process_generic_files(self, filepaths, data_list, tree_widget):
        for path in filepaths:
            normalized_path = path.replace('\\', '/')
            if normalized_path not in data_list:
                if tree_widget.add_file_item(normalized_path):
                    data_list.append(normalized_path)

    def _remove_item(self, tree_widget, data_list):
        current_item = tree_widget.currentItem()
        if not current_item:
            return

        filepath = current_item.text(tree_widget.columnCount() - 1)

        if data_list is self.source_files:
            data_list[:] = [f for f in data_list if f['path'] != filepath]
        else:
            data_list[:] = [p for p in data_list if p != filepath]

        root = tree_widget.invisibleRootItem()
        root.removeChild(current_item)

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