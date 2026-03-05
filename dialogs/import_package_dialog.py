# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QProgressBar, QFrame, QLineEdit,
                               QMessageBox, QFileDialog)
from PySide6.QtCore import Qt, QThread
from PySide6.QtGui import QFont
from services.package_service import ExtractWorker
from ui_components.password_edit import PasswordEdit
from utils.localization import _
import os


class ImportPackageDialog(QDialog):
    def __init__(self, parent, package_path, pack_info):
        super().__init__(parent)
        self.app = parent
        self.package_path = package_path
        self.pack_info = pack_info
        self.extracted_path = None

        self.setWindowTitle(_("Import Project Package"))
        self.resize(500, 400)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Header
        title = QLabel(self.pack_info.get('project_name', 'Unknown Project'))
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        layout.addWidget(title)

        meta_text = f"{_('Source Language')}: {self.pack_info.get('source_lang', 'en')} | " \
                    f"{_('Created')}: {self.pack_info.get('created_at', '')[:10]}"
        layout.addWidget(QLabel(meta_text))

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #DDD;")
        layout.addWidget(line)

        # Progress Section
        layout.addWidget(QLabel(f"<b>{_('Translation Progress')}</b>"))

        langs = self.pack_info.get('languages', {})
        for lang, stats in langs.items():
            row = QHBoxLayout()
            row.addWidget(QLabel(lang), 1)

            pb = QProgressBar()
            total = stats.get('total', 0)
            translated = stats.get('translated', 0)
            percent = int((translated / total) * 100) if total > 0 else 0

            pb.setValue(percent)
            pb.setStyleSheet("QProgressBar::chunk { background-color: #4CAF50; }")
            row.addWidget(pb, 3)

            row.addWidget(QLabel(f"{translated}/{total}"), 1)
            layout.addLayout(row)

        # Resources
        res_text = []
        if self.pack_info.get('includes_tm'): res_text.append("Translation Memory")
        if self.pack_info.get('includes_glossary'): res_text.append("Glossary")
        if res_text:
            layout.addWidget(QLabel(f"<b>{_('Included Resources')}:</b> {', '.join(res_text)}"))

        layout.addStretch()

        # Password Field
        self.pwd_input = QLineEdit()
        self.pwd_input = PasswordEdit()
        self.pwd_input.setPlaceholderText(_("This package is encrypted. Enter password..."))

        if self.pack_info.get('is_encrypted'):
            layout.addWidget(self.pwd_input)

        # Status
        self.status_label = QLabel()
        layout.addWidget(self.status_label)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton(_("Cancel"))
        btn_cancel.clicked.connect(self.reject)

        self.btn_import = QPushButton(_("Extract & Open..."))
        self.btn_import.setStyleSheet("background-color: #409EFF; color: white; font-weight: bold;")
        self.btn_import.clicked.connect(self.start_extraction)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(self.btn_import)
        layout.addLayout(btn_layout)

    def start_extraction(self):
        pwd = self.pwd_input.text() if self.pack_info.get('is_encrypted') else None
        if self.pack_info.get('is_encrypted') and not pwd:
            QMessageBox.warning(self, _("Warning"), _("Please enter the password."))
            return

        target_dir = QFileDialog.getExistingDirectory(self, _("Select folder to extract project"))
        if not target_dir: return

        # Create a subfolder for the project
        proj_folder = os.path.join(target_dir, self.pack_info.get('project_name', 'Imported_Project'))
        os.makedirs(proj_folder, exist_ok=True)

        self.btn_import.setEnabled(False)
        self.pwd_input.setEnabled(False)

        self.thread = QThread()
        self.worker = ExtractWorker(self.package_path, proj_folder, pwd)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(lambda v, m: self.status_label.setText(m))
        self.worker.finished.connect(self.on_extracted)

        self.thread.start()

    def on_extracted(self, success, msg):
        self.thread.quit()
        self.thread.wait()

        if success:
            self.extracted_path = msg
            self.accept()
        else:
            self.btn_import.setEnabled(True)
            self.pwd_input.setEnabled(True)
            if msg == "INVALID_PASSWORD":
                self.status_label.setText(f"<span style='color:red;'>{_('Incorrect password.')}</span>")
                self.pwd_input.clear()
                self.pwd_input.setFocus()
            else:
                self.status_label.setText(f"<span style='color:red;'>{_('Extraction failed')}: {msg}</span>")