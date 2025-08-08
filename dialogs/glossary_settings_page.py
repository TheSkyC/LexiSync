# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, \
    QHeaderView, QAbstractItemView, QFileDialog, QMessageBox, QProgressDialog, QTableWidgetItem
from PySide6.QtCore import Qt, QThread, Signal
from .settings_pages import BaseSettingsPage
from utils.localization import _
from utils.path_utils import get_app_data_path
from services.glossary_service import MANIFEST_FILE, DB_FILE
import os
import logging
import datetime

class TbxImportThread(QThread):
    progress = Signal(str)
    finished = Signal(bool, str)

    def __init__(self, glossary_service, tbx_path, glossary_dir):
        super().__init__()
        self.glossary_service = glossary_service
        self.tbx_path = tbx_path
        self.glossary_dir = glossary_dir

    def run(self):
        success, message = self.glossary_service.import_from_tbx(
            self.tbx_path, self.glossary_dir, self.progress.emit
        )
        self.finished.emit(success, message)


class GlossarySettingsPage(BaseSettingsPage):
    def __init__(self, app_instance):
        super().__init__()
        self.app = app_instance
        self.glossary_service = self.app.glossary_service
        self.global_glossary_dir = os.path.join(get_app_data_path(), "glossary")
        self.manifest_path = os.path.join(self.global_glossary_dir, MANIFEST_FILE)

        # Toolbar
        toolbar_layout = QHBoxLayout()
        import_btn = QPushButton(_("Add from TBX..."))
        import_btn.clicked.connect(self.import_tbx)
        remove_btn = QPushButton(_("Remove Selected"))
        remove_btn.clicked.connect(self.remove_selected_source)
        toolbar_layout.addWidget(import_btn)
        toolbar_layout.addWidget(remove_btn)
        toolbar_layout.addStretch()
        self.page_layout.addLayout(toolbar_layout)

        # Table for displaying imported sources
        self.sources_table = QTableWidget()
        self.sources_table.setColumnCount(4)
        self.sources_table.setHorizontalHeaderLabels([
            _("Source File"), _("Term Count"), _("Import Date"), _("Original Path")
        ])
        self.sources_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.sources_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.sources_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.sources_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.sources_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.sources_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.page_layout.addWidget(self.sources_table)

        self.load_sources_into_table()

    def import_tbx(self):
        filepath, __ = QFileDialog.getOpenFileName(
            self, _("Select TBX File to Import"), "", "TBX Files (*.tbx);;All Files (*.*)"
        )
        if not filepath:
            return

        self.progress_dialog = QProgressDialog(_("Importing TBX file..."), _("Cancel"), 0, 100, self)
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setAutoClose(True)
        self.progress_dialog.show()

        self.import_thread = TbxImportThread(self.glossary_service, filepath, self.global_glossary_dir)
        self.import_thread.progress.connect(self.update_progress)
        self.import_thread.finished.connect(self.on_import_finished)
        self.progress_dialog.canceled.connect(self.import_thread.terminate)
        self.import_thread.start()

    def update_progress(self, message):
        if self.progress_dialog.wasCanceled():
            return
        self.progress_dialog.setLabelText(message)
        self.progress_dialog.setValue(self.progress_dialog.value() + 1)  # Simple progress increment

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
            _("Are you sure you want to remove all terms from '{source}'?\nThis action cannot be undone.").format(
                source=source_key),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.No:
            return

        success, message = self.glossary_service.remove_source(source_key, self.global_glossary_dir)
        if success:
            QMessageBox.information(self, _("Removal Successful"), message)
            self.load_sources_into_table()
        else:
            QMessageBox.critical(self, _("Removal Failed"), message)

    def load_sources_into_table(self):
        self.sources_table.setRowCount(0)
        manifest = self.glossary_service._read_manifest(self.manifest_path)
        sources = manifest.get("imported_sources", {})

        self.sources_table.setRowCount(len(sources))
        for row_idx, (filename, data) in enumerate(sources.items()):
            self.sources_table.setItem(row_idx, 0, QTableWidgetItem(filename))
            self.sources_table.setItem(row_idx, 1, QTableWidgetItem(str(data.get("term_count", "N/A"))))

            import_date_str = "N/A"
            if "import_date" in data:
                try:
                    dt = datetime.datetime.fromisoformat(data["import_date"].replace("Z", "+00:00"))
                    import_date_str = dt.strftime("%Y-%m-%d %H:%M")
                except ValueError:
                    import_date_str = data["import_date"]
            self.sources_table.setItem(row_idx, 2, QTableWidgetItem(import_date_str))

            self.sources_table.setItem(row_idx, 3, QTableWidgetItem(data.get("filepath", "N/A")))

    def load_terms_into_table(self):
        self.terms_table.setRowCount(0)
        db_path = os.path.join(self.global_glossary_dir, DB_FILE)
        if not os.path.exists(db_path):
            return

        try:
            with self.glossary_service._get_db_connection(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT t.source_term, GROUP_CONCAT(tr.target_term, '; ') 
                    FROM terms t 
                    JOIN translations tr ON t.id = tr.term_id 
                    GROUP BY t.id 
                    LIMIT 500
                """)
                rows = cursor.fetchall()
                self.terms_table.setRowCount(len(rows))
                for row_idx, row_data in enumerate(rows):
                    self.terms_table.setItem(row_idx, 0, QTableWidgetItem(row_data[0]))
                    self.terms_table.setItem(row_idx, 1, QTableWidgetItem(row_data[1]))
        except Exception as e:
            logging.error(f"Failed to load terms for display: {e}")

    def save_settings(self):
        pass