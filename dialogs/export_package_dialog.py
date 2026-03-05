# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QCheckBox, QLineEdit, QProgressBar, QMessageBox,
                               QGroupBox, QPushButton, QFileDialog, QWidget)
from PySide6.QtCore import Qt, QThread
from services.package_service import PackageWorker, HAS_PYZIPPER
from ui_components.password_edit import PasswordEdit
from utils.localization import _
import os


class ExportPackageDialog(QDialog):
    def __init__(self, app_instance, parent=None):
        super().__init__(parent)
        self.app = app_instance
        self.setWindowTitle(_("Export Project Package (.lexipack)"))
        self.resize(500, 550)

        self.worker_thread = None
        self.worker = None

        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)

        # --- 1. Languages Group ---
        lang_group = QGroupBox(_("Target Languages to Include"))
        lang_layout = QVBoxLayout(lang_group)

        self.lang_checkboxes = {}
        langs = self.app.project_config.get('target_languages', [])
        for lang in langs:
            cb = QCheckBox(lang)
            cb.setChecked(True)
            self.lang_checkboxes[lang] = cb
            lang_layout.addWidget(cb)

        if not langs:
            lang_layout.addWidget(QLabel(_("No target languages found.")))

        main_layout.addWidget(lang_group)

        # --- 2. Resources Group ---
        res_group = QGroupBox(_("Additional Resources"))
        res_layout = QVBoxLayout(res_group)

        self.cb_tm = QCheckBox(_("Include Project Translation Memory (TM)"))
        self.cb_tm.setChecked(True)
        self.cb_glossary = QCheckBox(_("Include Project Glossary"))
        self.cb_glossary.setChecked(True)

        res_layout.addWidget(self.cb_tm)
        res_layout.addWidget(self.cb_glossary)

        main_layout.addWidget(res_group)

        # --- 3. Security Group ---
        sec_group = QGroupBox(_("Security Settings"))
        sec_layout = QVBoxLayout(sec_group)

        self.cb_encrypt = QCheckBox(_("Enable Password Protection (AES-256)"))
        sec_layout.addWidget(self.cb_encrypt)

        self.pwd_input = PasswordEdit()
        self.pwd_input.setPlaceholderText(_("Enter password..."))
        self.pwd_input.setEnabled(False)
        sec_layout.addWidget(self.pwd_input)

        self.cb_encrypt.toggled.connect(self.pwd_input.setEnabled)

        if not HAS_PYZIPPER:
            self.cb_encrypt.setEnabled(False)
            self.cb_encrypt.setText(_("Enable Password Protection (Requires 'pyzipper' library)"))

        main_layout.addWidget(sec_group)

        main_layout.addStretch()

        # --- 4. Progress Area (Hidden by default) ---
        self.progress_widget = QWidget()
        progress_layout = QVBoxLayout(self.progress_widget)
        progress_layout.setContentsMargins(0, 0, 0, 0)

        self.status_label = QLabel("")
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)

        progress_layout.addWidget(self.status_label)
        progress_layout.addWidget(self.progress_bar)
        self.progress_widget.hide()

        main_layout.addWidget(self.progress_widget)

        # --- 5. Buttons ---
        btn_layout = QHBoxLayout()
        self.btn_cancel = QPushButton(_("Cancel"))
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_export = QPushButton(_("Export Package..."))
        self.btn_export.setStyleSheet("background-color: #409EFF; color: white; font-weight: bold;")
        self.btn_export.clicked.connect(self.start_export)

        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_export)

        main_layout.addLayout(btn_layout)

    def get_options(self):
        selected_langs = [lang for lang, cb in self.lang_checkboxes.items() if cb.isChecked()]
        pwd = self.pwd_input.text() if self.cb_encrypt.isChecked() else None

        return {
            'langs': selected_langs,
            'include_tm': self.cb_tm.isChecked(),
            'include_glossary': self.cb_glossary.isChecked(),
            'password': pwd
        }

    def validate_inputs(self, options):
        if not options['langs']:
            QMessageBox.warning(self, _("Warning"), _("Please select at least one language to export."))
            return False

        if self.cb_encrypt.isChecked() and len(options['password']) < 4:
            QMessageBox.warning(self, _("Warning"), _("Password must be at least 4 characters long."))
            return False

        return True

    def start_export(self):
        options = self.get_options()
        if not self.validate_inputs(options):
            return

        default_name = f"{self.app.project_config.get('name', 'Project')}.lexipack"
        export_path, __ = QFileDialog.getSaveFileName(
            self, _("Save Package As"),
            os.path.join(self.app.config.get('last_dir', ''), default_name),
            "LexiSync Package (*.lexipack)"
        )

        if not export_path:
            return

        # Disable UI during export
        self.btn_export.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        for cb in self.lang_checkboxes.values(): cb.setEnabled(False)
        self.cb_tm.setEnabled(False)
        self.cb_glossary.setEnabled(False)
        self.cb_encrypt.setEnabled(False)
        self.pwd_input.setEnabled(False)

        # Show progress
        self.progress_widget.show()
        self.status_label.setText(_("Initializing..."))
        self.progress_bar.setValue(0)

        # Start Thread
        self.worker_thread = QThread()
        self.worker = PackageWorker(self.app.current_project_path, export_path, options)
        self.worker.moveToThread(self.worker_thread)

        self.worker_thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.on_finished)

        self.worker_thread.start()

    def update_progress(self, val, msg):
        self.progress_bar.setValue(val)
        self.status_label.setText(msg)

    def on_finished(self, success, msg):
        self.worker_thread.quit()
        self.worker_thread.wait()

        self.btn_cancel.setEnabled(True)
        self.btn_cancel.setText(_("Close"))

        if success:
            self.status_label.setText(_("Packaging completed successfully!"))
            self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            self.progress_bar.setValue(100)
            QMessageBox.information(self, _("Success"), _("Project package saved to:\n{path}").format(path=msg))
            self.accept()
        else:
            self.status_label.setText(_("Packaging failed."))
            self.status_label.setStyleSheet("color: #F44336; font-weight: bold;")
            QMessageBox.critical(self, _("Error"), _("Packaging failed:\n{error}").format(error=msg))

            # Re-enable UI for retry
            self.btn_export.setEnabled(True)
            for cb in self.lang_checkboxes.values(): cb.setEnabled(True)
            self.cb_tm.setEnabled(True)
            self.cb_glossary.setEnabled(True)
            self.cb_encrypt.setEnabled(HAS_PYZIPPER)
            self.pwd_input.setEnabled(self.cb_encrypt.isChecked())

    def closeEvent(self, event):
        if self.worker_thread and self.worker_thread.isRunning():
            QMessageBox.warning(self, _("Warning"), _("Packaging is in progress. Please wait."))
            event.ignore()
            return
        super().closeEvent(event)