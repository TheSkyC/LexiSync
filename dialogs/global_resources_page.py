# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTabWidget, QLabel, QHBoxLayout,
                               QPushButton, QTableWidget, QHeaderView, QAbstractItemView,
                               QFileDialog, QMessageBox, QProgressDialog, QTableWidgetItem)
from PySide6.QtCore import QThread, Signal, Qt
from .settings_pages import BaseSettingsPage
from .glossary_settings_page import GlossarySettingsPage
from utils.localization import _
from .tm_import_dialog import TMImportDialog
from services.tm_service import MANIFEST_FILE as TM_MANIFEST_FILE
from utils.path_utils import get_app_data_path
from datetime import datetime
import os
import logging
logger = logging.getLogger(__name__)

class TMImportThread(QThread):
    progress = Signal(str)
    finished = Signal(bool, str)

    def __init__(self, tm_service, file_path, tm_dir, source_lang, target_lang):
        super().__init__()
        self.tm_service = tm_service
        self.file_path = file_path
        self.tm_dir = tm_dir
        self.source_lang = source_lang
        self.target_lang = target_lang

    def run(self):
        success, message = self.tm_service.import_from_file(
            self.file_path, self.tm_dir, self.source_lang, self.target_lang, self.progress.emit
        )
        self.finished.emit(success, message)


class TMSettingsPage(BaseSettingsPage):
    def __init__(self, app_instance):
        super().__init__()
        self.app = app_instance
        self.tm_service = self.app.tm_service
        self.global_tm_dir = os.path.join(get_app_data_path(), "tm")
        self.manifest_path = os.path.join(self.global_tm_dir, TM_MANIFEST_FILE)

        # Toolbar
        toolbar_layout = QHBoxLayout()
        import_btn = QPushButton(_("Add from File..."))
        import_btn.clicked.connect(self.import_tm_file)
        remove_btn = QPushButton(_("Remove Selected"))
        remove_btn.clicked.connect(self.remove_selected_source)
        toolbar_layout.addWidget(import_btn)
        toolbar_layout.addWidget(remove_btn)
        toolbar_layout.addStretch()
        self.page_layout.addLayout(toolbar_layout)

        # Table for displaying imported sources
        self.sources_table = QTableWidget()
        self.sources_table.setColumnCount(5)
        self.sources_table.setHorizontalHeaderLabels([
            _("Source File"), _("Entry Count"), _("Source Lang"), _("Target Lang"), _("Import Date")
        ])
        self.sources_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.sources_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.sources_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.page_layout.addWidget(self.sources_table)

        self.load_sources_into_table()

    def import_tm_file(self):
        filepath, __ = QFileDialog.getOpenFileName(
            self, _("Select TM File to Import"), "",
            _("TM Files (*.jsonl *.xlsx);;All Files (*.*)")
        )
        if not filepath:
            return

        lang_dialog = TMImportDialog(self, os.path.basename(filepath))
        if not lang_dialog.exec():
            return

        lang_data = lang_dialog.get_data()
        source_lang = lang_data['source_lang']
        target_lang = lang_data['target_lang']

        self.progress_dialog = QProgressDialog(_("Importing TM file..."), _("Cancel"), 0, 100, self)
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setAutoClose(True)
        self.progress_dialog.show()

        self.import_thread = TMImportThread(
            self.tm_service, filepath, self.global_tm_dir, source_lang, target_lang
        )
        self.import_thread.progress.connect(self.update_progress)
        self.import_thread.finished.connect(self.on_import_finished)
        self.progress_dialog.canceled.connect(self.import_thread.terminate)
        self.import_thread.start()

    def update_progress(self, message):
        if self.progress_dialog.wasCanceled():
            return
        self.progress_dialog.setLabelText(message)
        self.progress_dialog.setValue(self.progress_dialog.value() + 5)

    def on_import_finished(self, success, message):
        self.progress_dialog.setValue(100)
        if success:
            QMessageBox.information(self, _("Import Successful"), message)
            self.load_sources_into_table()
        else:
            QMessageBox.critical(self, _("Import Failed"), message)

    def remove_selected_source(self):
        selected_items = self.sources_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, _("Warning"), _("Please select a source to remove."))
            return

        row = selected_items[0].row()
        source_key = self.sources_table.item(row, 0).text()

        reply = QMessageBox.question(
            self, _("Confirm Removal"),
            _("Are you sure you want to remove all TM entries from '{source}'?\nThis action cannot be undone.").format(
                source=source_key),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.No:
            return

        success, message = self.tm_service.remove_source(source_key, self.global_tm_dir)
        if success:
            QMessageBox.information(self, _("Removal Successful"), message)
            self.load_sources_into_table()
        else:
            QMessageBox.critical(self, _("Removal Failed"), message)

    def load_sources_into_table(self):
        self.sources_table.setRowCount(0)
        manifest = self.tm_service._read_manifest(self.manifest_path)
        sources = manifest.get("imported_sources", {})

        self.sources_table.setRowCount(len(sources))
        for row_idx, (filename, data) in enumerate(sources.items()):
            self.sources_table.setItem(row_idx, 0, QTableWidgetItem(filename))
            self.sources_table.setItem(row_idx, 1, QTableWidgetItem(str(data.get("tu_count", "N/A"))))
            self.sources_table.setItem(row_idx, 2, QTableWidgetItem(data.get("source_lang", "N/A")))
            self.sources_table.setItem(row_idx, 3, QTableWidgetItem(data.get("target_lang", "N/A")))

            import_date_str = "N/A"
            if "import_date" in data:
                try:
                    dt = datetime.fromisoformat(data["import_date"].replace("Z", "+00:00"))
                    import_date_str = dt.strftime("%Y-%m-%d %H:%M")
                except (ValueError, TypeError):
                    import_date_str = data["import_date"]
            self.sources_table.setItem(row_idx, 4, QTableWidgetItem(import_date_str))

    def save_settings(self):
        pass

class GlobalResourcesSettingsPage(BaseSettingsPage):
    def __init__(self, app_instance):
        super().__init__()
        self.app = app_instance
        self.page_layout.setContentsMargins(10, 10, 10, 10)

        self.tab_widget = QTabWidget()
        self.page_layout.addWidget(self.tab_widget)

        self.glossary_tab = GlossarySettingsPage(self.app)
        self.tab_widget.addTab(self.glossary_tab, _("Glossary"))

        self.tm_tab = TMSettingsPage(self.app)
        self.tab_widget.addTab(self.tm_tab, _("Translation Memory"))

    def save_settings(self):
        self.glossary_tab.save_settings()
        self.tm_tab.save_settings()