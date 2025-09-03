# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                               QPushButton, QTableWidget, QHeaderView, QAbstractItemView,
                               QFileDialog, QMessageBox, QProgressDialog, QTableWidgetItem,
                               QApplication, QLabel)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QMutex, QMutexLocker, QObject
from typing import Optional
from .settings_pages import BaseSettingsPage
from utils.localization import _
from utils.path_utils import get_app_data_path
from utils.tbx_parser import TBXParser
from services.glossary_service import MANIFEST_FILE as GLOSSARY_MANIFEST_FILE
from .import_configuration_dialog import ImportConfigurationDialog
from .tm_import_dialog import TMImportDialog
import os
import logging
import datetime
import gc
logger = logging.getLogger(__name__)


class TbxImportWorker(QObject):
    progress = Signal(str)
    finished = Signal(bool, str)

    def __init__(self, glossary_service, tbx_path, glossary_dir, source_lang, target_langs, is_bidirectional,
                 lang_mapping):
        super().__init__()
        self.glossary_service = glossary_service
        self.tbx_path = tbx_path
        self.glossary_dir = glossary_dir
        self.source_lang = source_lang
        self.target_langs = target_langs
        self.is_bidirectional = is_bidirectional
        self.lang_mapping = lang_mapping
        self._is_cancelled = False
        self._mutex = QMutex()

    def cancel(self):
        with QMutexLocker(self._mutex):
            self._is_cancelled = True

    def is_cancelled(self):
        with QMutexLocker(self._mutex):
            return self._is_cancelled

    def do_import(self):
        try:
            logger.info("Starting TBX import worker")

            if self.is_cancelled():
                self.finished.emit(False, "Operation was cancelled")
                return

            success, message = self.glossary_service.import_from_tbx(
                self.tbx_path, self.glossary_dir, self.source_lang,
                self.target_langs, self.is_bidirectional, self.lang_mapping,
                self.progress.emit
            )

            if self.is_cancelled():
                self.finished.emit(False, "Operation was cancelled")
                return

            logger.info(f"Import completed: success={success}, message={message}")
            self.finished.emit(success, message)

        except Exception as e:
            logger.exception("Error in TbxImportWorker.do_import()")
            self.finished.emit(False, f"Import failed with error: {str(e)}")


class SimpleProgressDialog(QWidget):
    cancelled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Importing..."))
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.CustomizeWindowHint)
        self.setWindowModality(Qt.ApplicationModal)
        self.resize(400, 100)

        layout = QVBoxLayout(self)

        self.label = QLabel(_("Importing TBX file..."))
        layout.addWidget(self.label)

        self.cancel_btn = QPushButton(_("Cancel"))
        self.cancel_btn.clicked.connect(self.cancel)
        layout.addWidget(self.cancel_btn)

    def setLabelText(self, text):
        self.label.setText(text)

    def cancel(self):
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setText(_("Cancelling..."))
        self.cancelled.emit()

    def closeEvent(self, event):
        self.cancel()
        event.ignore()

class GlossaryManagementTab(QWidget):
    def __init__(self, app_instance, context: str):
        super().__init__()
        self.app = app_instance
        self.context = context
        self.glossary_service = self.app.glossary_service

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        if self.context == "project":
            if not self.app.is_project_mode:
                self.setEnabled(False)
                layout = QVBoxLayout(self)
                layout.addWidget(QLabel(_("No project is open. This panel is disabled.")))
                return
            self.glossary_dir = os.path.join(self.app.current_project_path, "glossary")
        else:
            self.glossary_dir = os.path.join(get_app_data_path(), "glossary")

        self.manifest_path = os.path.join(self.glossary_dir, GLOSSARY_MANIFEST_FILE)

        self._import_thread = None
        self._progress_dialog = None
        self._import_worker = None
        self._cleanup_timer = QTimer()
        self._cleanup_timer.timeout.connect(self._delayed_cleanup)
        self._cleanup_timer.setSingleShot(True)

        self._setup_ui()
        self.load_sources_into_table()

    def _setup_ui(self):
        # Toolbar
        toolbar_layout = QHBoxLayout()
        import_btn = QPushButton(_("Add from TBX..."))
        import_btn.clicked.connect(self.import_tbx)
        remove_btn = QPushButton(_("Remove Selected"))
        remove_btn.clicked.connect(self.remove_selected_source)
        toolbar_layout.addWidget(import_btn)
        toolbar_layout.addWidget(remove_btn)
        toolbar_layout.addStretch()
        self.main_layout.addLayout(toolbar_layout)

        self.sources_table = QTableWidget()
        self.sources_table.setColumnCount(5)
        self.sources_table.setHorizontalHeaderLabels([
            _("Source File"), _("Entry Count"), _("Source Lang"),
            _("Target Lang(s)"), _("Import Date")
        ])
        self.sources_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.sources_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.sources_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.sources_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.sources_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.sources_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.main_layout.addWidget(self.sources_table)

    def closeEvent(self, event):
        logger.info("GlossarySettingsPage closeEvent called")
        self._force_cleanup()
        super().closeEvent(event)

    def _force_cleanup(self):
        try:
            logger.info("Starting force cleanup")

            if self._cleanup_timer:
                self._cleanup_timer.stop()

            if self._import_worker:
                self._import_worker.cancel()

            if self._import_thread and self._import_thread.isRunning():
                logger.info("Waiting for thread to finish")
                self._import_thread.quit()
                if not self._import_thread.wait(3000):
                    logger.warning("Thread did not finish gracefully, terminating")
                    self._import_thread.terminate()
                    self._import_thread.wait(1000)

            if self._progress_dialog:
                logger.info("Cleaning up progress dialog")
                self._progress_dialog.hide()
                self._progress_dialog.setParent(None)
                self._progress_dialog.deleteLater()
                self._progress_dialog = None

            if self._import_thread:
                logger.info("Cleaning up thread")
                self._import_thread.deleteLater()
                self._import_thread = None

            if self._import_worker:
                logger.info("Cleaning up worker")
                self._import_worker.setParent(None)
                self._import_worker.deleteLater()
                self._import_worker = None

            gc.collect()
            logger.info("Force cleanup completed")
        except Exception as e:
            logger.exception(f"Error during force cleanup: {e}")

    def _delayed_cleanup(self):
        try:
            logger.info("Starting delayed cleanup")

            if self._import_thread:
                if not self._import_thread.isRunning():
                    self._import_thread.deleteLater()
                    self._import_thread = None

            if self._import_worker:
                self._import_worker.setParent(None)
                self._import_worker.deleteLater()
                self._import_worker = None

            gc.collect()
            logger.info("Delayed cleanup completed")

        except Exception as e:
            logger.exception(f"Error during delayed cleanup: {e}")

    def import_tbx(self, filepath: Optional[str] = None):
        if self._import_thread and self._import_thread.isRunning():
            QMessageBox.warning(self, _("Import In Progress"),
                                _("An import operation is already in progress. Please wait for it to complete."))
            return
        self._force_cleanup()

        if not filepath:
            filepath, __ = QFileDialog.getOpenFileName(
                self, _("Select TBX File to Import"), "", "TBX Files (*.tbx);;All Files (*.*)"
            )
        if not filepath:
            return

        try:
            parser = TBXParser()
            parse_result = parser.parse_tbx(filepath, analyze_only=True)
            detected_languages = parse_result.get("detected_languages", [])
            if not detected_languages:
                QMessageBox.warning(self, _("Analysis Failed"),
                                    _("Could not detect any languages in the TBX file. Please check the file format."))
                return
        except Exception as e:
            logger.exception("TBX analysis failed")
            QMessageBox.critical(self, _("Parse Error"),
                                 _("Failed to analyze the TBX file: {error}").format(error=str(e)))
            return

        config_dialog = ImportConfigurationDialog(self, os.path.basename(filepath), detected_languages, "Glossary")
        if not config_dialog.exec():
            return

        import_settings = config_dialog.get_data()
        source_lang = import_settings['source_lang']
        target_langs = import_settings['target_langs']
        is_bidirectional = import_settings['is_bidirectional']
        lang_mapping = import_settings['lang_mapping']

        self._start_import_process(filepath, source_lang, target_langs, is_bidirectional, lang_mapping)

    def _start_import_process(self, filepath, source_lang, target_langs, is_bidirectional, lang_mapping):
        """启动导入过程"""
        try:
            logger.info("Starting import process")

            self._progress_dialog = SimpleProgressDialog(self)
            self._progress_dialog.cancelled.connect(self._cancel_import)

            self._import_thread = QThread()

            self._import_worker = TbxImportWorker(
                self.glossary_service, filepath, self.glossary_dir,
                source_lang, target_langs, is_bidirectional, lang_mapping
            )

            self._import_worker.moveToThread(self._import_thread)

            self._import_thread.started.connect(self._import_worker.do_import, Qt.DirectConnection)
            self._import_worker.progress.connect(self._update_progress, Qt.QueuedConnection)
            self._import_worker.finished.connect(self._on_import_finished, Qt.QueuedConnection)
            self._import_worker.finished.connect(self._import_thread.quit, Qt.QueuedConnection)
            self._import_thread.finished.connect(self._import_worker.deleteLater, Qt.QueuedConnection)

            self._progress_dialog.show()

            self._import_thread.start()
            logger.info("Import process started successfully")
        except Exception as e:
            logger.exception("Failed to start import process")
            QMessageBox.critical(self, _("Import Error"),
                                 _("Failed to start import: {error}").format(error=str(e)))
            self._force_cleanup()

    def _cancel_import(self):
        """取消导入操作"""
        try:
            logger.info("Cancelling import")
            if self._import_worker:
                self._import_worker.cancel()
            if self._progress_dialog:
                self._progress_dialog.hide()
        except Exception as e:
            logger.exception(f"Error cancelling import: {e}")

    def _update_progress(self, message):
        """更新进度"""
        try:
            if self._progress_dialog and not self._progress_dialog.wasCanceled():
                self._progress_dialog.setLabelText(message)
                QApplication.processEvents()
        except Exception as e:
            logger.exception(f"Error updating progress: {e}")

    def _on_import_finished(self, success, message):
        try:
            logger.info(f"Import finished - Success: {success}, Message: {message}")

            if self._progress_dialog:
                self._progress_dialog.hide()

            def handle_completion():
                try:
                    logger.info("Handling completion in timer callback")

                    if self._progress_dialog:
                        self._progress_dialog.setParent(None)
                        self._progress_dialog.deleteLater()
                        self._progress_dialog = None

                    if success:
                        self.load_sources_into_table()
                        QApplication.processEvents()

                        msg = QMessageBox(self)
                        msg.setIcon(QMessageBox.Information)
                        msg.setWindowTitle(_("Import Successful"))
                        msg.setText(message)
                        msg.setStandardButtons(QMessageBox.Ok)
                        msg.exec()
                    else:
                        msg = QMessageBox(self)
                        msg.setIcon(QMessageBox.Critical)
                        msg.setWindowTitle(_("Import Failed"))
                        msg.setText(message)
                        msg.setStandardButtons(QMessageBox.Ok)
                        msg.exec()

                    self._cleanup_timer.start(1000)
                    logger.info("Completion handling finished")

                except Exception as e:
                    logger.exception(f"Error in completion handler: {e}")
                    self._force_cleanup()

            QTimer.singleShot(200, handle_completion)

        except Exception as e:
            logger.exception(f"Error in _on_import_finished: {e}")
            self._force_cleanup()

    def remove_selected_source(self):
        selected_items = self.sources_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, _("Warning"), _("Please select a source to remove."))
            return

        row = selected_items[0].row()
        source_key = self.sources_table.item(row, 0).text()

        if self._import_thread and self._import_thread.isRunning():
            QMessageBox.warning(self, _("Operation In Progress"),
                                _("Cannot remove source while an import operation is in progress."))
            return

        reply = QMessageBox.question(
            self, _("Confirm Removal"),
            _("Are you sure you want to remove all terms from '{source}'?\nThis action cannot be undone.").format(
                source=source_key),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.No:
            return

        success, message = self.glossary_service.remove_source(source_key, self.glossary_dir)

        if success:
            QMessageBox.information(self, _("Removal Successful"), message)
            self.load_sources_into_table()
        else:
            QMessageBox.critical(self, _("Removal Failed"), message)

    def load_sources_into_table(self):
        try:
            self.sources_table.setRowCount(0)
            manifest = self.glossary_service._read_manifest(self.manifest_path)
            sources = manifest.get("imported_sources", {})

            self.sources_table.setRowCount(len(sources))
            for row_idx, (filename, data) in enumerate(sources.items()):
                # 列 0: Source File
                self.sources_table.setItem(row_idx, 0, QTableWidgetItem(filename))

                # 列 1: Entry Count
                self.sources_table.setItem(row_idx, 1, QTableWidgetItem(str(data.get("term_count", "N/A"))))

                # 列 2: Source Lang
                self.sources_table.setItem(row_idx, 2, QTableWidgetItem(data.get("source_lang", "N/A")))

                # 列 3: Target Lang(s)
                target_langs_list = data.get("target_langs", [])
                target_langs_str = ", ".join(target_langs_list)
                self.sources_table.setItem(row_idx, 3, QTableWidgetItem(target_langs_str))

                # 列 4: Import Date
                import_date_str = "N/A"
                if "import_date" in data:
                    try:
                        iso_str = data["import_date"].split('.')[0]  # 移除毫秒部分
                        dt = datetime.datetime.strptime(iso_str, "%Y-%m-%dT%H:%M:%S")
                        import_date_str = dt.strftime("%Y-%m-%d %H:%M")
                    except (ValueError, TypeError):
                        import_date_str = data["import_date"]
                self.sources_table.setItem(row_idx, 4, QTableWidgetItem(import_date_str))

        except Exception as e:
            logger.exception("Error in load_sources_into_table")


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

class TMManagementTab(QWidget):
    def __init__(self, app_instance, context: str):
        super().__init__()
        self.app = app_instance
        self.context = context
        self.tm_service = self.app.tm_service

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        if self.context == "project":
            if not self.app.is_project_mode:
                self.setEnabled(False)
                self.main_layout.addWidget(QLabel(_("No project open.")))  # 使用新布局
                return
            self.tm_dir = os.path.join(self.app.current_project_path, "tm")
        else:
            self.tm_dir = os.path.join(get_app_data_path(), "tm")

        self.manifest_path = os.path.join(self.tm_dir, "manifest.json")

        self._import_thread = None
        self._progress_dialog = None

        self._setup_ui()
        self.load_sources_into_table()

    def _setup_ui(self):
        toolbar_layout = QHBoxLayout()
        import_btn = QPushButton(_("Add from File..."))
        import_btn.clicked.connect(self.import_tm_file)
        remove_btn = QPushButton(_("Remove Selected"))
        remove_btn.clicked.connect(self.remove_selected_source)
        toolbar_layout.addWidget(import_btn)
        toolbar_layout.addWidget(remove_btn)
        toolbar_layout.addStretch()

        self.main_layout.addLayout(toolbar_layout)

        self.sources_table = QTableWidget()
        self.sources_table.setColumnCount(5)
        self.sources_table.setHorizontalHeaderLabels([
            _("Source File"), _("Entry Count"), _("Source Lang"), _("Target Lang"), _("Import Date")
        ])
        self.sources_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.sources_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.sources_table.setSelectionBehavior(QAbstractItemView.SelectRows)

        self.main_layout.addWidget(self.sources_table)

    def import_tm_file(self, filepath: Optional[str] = None):
        if not filepath:
            filepath, __ = QFileDialog.getOpenFileName(
                self, _("Select TM File to Import"), "",
                _("TM Files (*.xlsx;;All Files (*.*)")
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

        success, message = self.tm_service.remove_source(source_key, self.tm_dir)

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
                    iso_str = data["import_date"].split('.')[0]
                    dt = datetime.datetime.strptime(iso_str, "%Y-%m-%dT%H:%M:%S")
                    import_date_str = dt.strftime("%Y-%m-%d %H:%M")
                except (ValueError, TypeError):
                    import_date_str = data["import_date"]
            self.sources_table.setItem(row_idx, 4, QTableWidgetItem(import_date_str))

    def save_settings(self):
        pass
