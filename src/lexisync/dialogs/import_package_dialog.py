# Copyright (c) 2025-2026, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import os

from PySide6.QtCore import Qt, QThread
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from lexisync.services.package_service import ExtractWorker
from lexisync.ui_components.password_edit import PasswordEdit
from lexisync.utils.localization import _
from lexisync.utils.text_utils import format_file_size


class ImportPackageDialog(QDialog):
    def __init__(self, parent, package_path, pack_info):
        super().__init__(parent)
        self.app = parent
        self.package_path = package_path
        self.pack_info = pack_info
        self.extracted_path = None

        self.setWindowTitle(_("Import Project Package"))
        self.resize(700, 550)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # --- 1. Header Section ---
        header_layout = QHBoxLayout()

        # Project Icon/Title
        title_layout = QVBoxLayout()
        title = QLabel(self.pack_info.get("project_name", "Unknown Project"))
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: #333;")

        created_at = self.pack_info.get("created_at", "")[:16].replace("T", " ")
        subtitle = QLabel(f"{_('Created')}: {created_at}  |  {_('Source')}: {self.pack_info.get('source_lang', 'en')}")
        subtitle.setStyleSheet("color: #777;")

        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)
        header_layout.addLayout(title_layout)
        header_layout.addStretch()

        # Overview Badge
        overview = self.pack_info.get("overview", {})
        size_str = format_file_size(overview.get("total_size_bytes", 0))
        file_count = overview.get("total_files", 0)
        badge_text = f"{file_count} {_('Files')}\n{size_str}"
        badge = QLabel(badge_text)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet("""
            background-color: #E3F2FD;
            color: #0277BD;
            border: 1px solid #B3E5FC;
            border-radius: 6px;
            padding: 8px;
            font-weight: bold;
        """)
        header_layout.addWidget(badge)

        layout.addLayout(header_layout)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #DDD;")
        layout.addWidget(line)

        # --- 2. Language Stats Table ---
        layout.addWidget(QLabel(f"<b>{_('Translation Progress')}</b>"))

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([_("Language"), _("Progress"), _("Strings"), _("Chars"), _("Expansion")])

        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setStyleSheet("QTableWidget { border: 1px solid #DDD; background-color: #FAFAFA; }")

        langs = self.pack_info.get("languages", {})
        self.table.setRowCount(len(langs))

        for i, (lang, stats) in enumerate(langs.items()):
            # Language
            item_lang = QTableWidgetItem(lang)
            item_lang.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.table.setItem(i, 0, item_lang)

            # Progress Bar
            pb = QProgressBar()
            percent = stats.get("progress_percent", 0)
            pb.setValue(int(percent))
            pb.setStyleSheet(self._get_progress_style(percent))
            pb.setFormat(f"{percent}%")
            pb.setAlignment(Qt.AlignCenter)
            self.table.setCellWidget(i, 1, pb)

            # Strings
            done = stats.get("translated_strings", 0)
            total = stats.get("total_strings", 0)
            self.table.setItem(i, 2, QTableWidgetItem(f"{done}/{total}"))

            # Chars
            src_chars = stats.get("source_char_count", 0)
            trans_chars = stats.get("translation_char_count", 0)
            self.table.setItem(i, 3, QTableWidgetItem(f"{trans_chars}"))

            # Expansion
            ratio = trans_chars / src_chars if src_chars > 0 else 0
            item_ratio = QTableWidgetItem(f"{ratio:.2f}x")
            if ratio > 1.5 or ratio < 0.5:
                item_ratio.setForeground(QBrush(QColor("#F57C00")))  # Warning color
            self.table.setItem(i, 4, item_ratio)

        layout.addWidget(self.table)

        # --- 3. Resource Manifest ---
        res_group = QGroupBox(_("Included Resources"))
        res_layout = QHBoxLayout(res_group)

        manifest = self.pack_info.get("manifest", {})

        def create_res_label(count, label):
            lbl = QLabel(f"{count} {label}")
            lbl.setStyleSheet("color: #555; background-color: #F5F5F5; border-radius: 4px; padding: 4px 8px;")
            return lbl

        res_layout.addWidget(create_res_label(len(manifest.get("source", [])), _("Source Files")))
        res_layout.addWidget(create_res_label(len(manifest.get("tm", [])), _("TM Databases")))
        res_layout.addWidget(create_res_label(len(manifest.get("glossary", [])), _("Glossaries")))
        res_layout.addStretch()

        layout.addWidget(res_group)

        # --- 4. Password & Action ---
        layout.addStretch()

        self.pwd_input = PasswordEdit()
        self.pwd_input.setPlaceholderText(_("🔒 This package is encrypted. Enter password to unlock..."))
        self.pwd_input.setStyleSheet("padding: 6px; border: 1px solid #CCC; border-radius: 4px;")

        if overview.get("is_encrypted"):
            layout.addWidget(self.pwd_input)

        # Status Label
        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.status_label)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton(_("Cancel"))
        btn_cancel.setFixedSize(100, 36)
        btn_cancel.clicked.connect(self.reject)

        self.btn_import = QPushButton(_("Extract && Open Project"))
        self.btn_import.setFixedSize(180, 36)
        self.btn_import.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #43A047; }
        """)
        self.btn_import.clicked.connect(self.start_extraction)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(self.btn_import)
        layout.addLayout(btn_layout)

    def _get_progress_style(self, percent):
        color = "#4CAF50"  # Green
        if percent < 30:
            color = "#F44336"  # Red
        elif percent < 70:
            color = "#FF9800"  # Orange
        elif percent < 100:
            color = "#2196F3"  # Blue

        return f"""
            QProgressBar {{
                border: 1px solid #DDD;
                border-radius: 3px;
                text-align: center;
                background-color: #FFF;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                width: 1px;
            }}
        """

    def start_extraction(self):
        overview = self.pack_info.get("overview", {})
        pwd = self.pwd_input.text() if overview.get("is_encrypted") else None

        if overview.get("is_encrypted") and not pwd:
            QMessageBox.warning(self, _("Warning"), _("Please enter the password."))
            return

        # 密码校验
        if overview.get("is_encrypted"):
            self.status_label.setText(_("Verifying password..."))
            self.status_label.setStyleSheet("color: #666; font-style: italic;")
            QApplication.processEvents()

            success, error = ExtractWorker.verify_password(self.package_path, pwd)

            if not success:
                self.status_label.setText(f"<span style='color:red;'>{_('Incorrect password.')}</span>")
                self.pwd_input.selectAll()
                self.pwd_input.setFocus()
                return

            self.status_label.setText(
                f"<span style='color:green;'>{_('Password verified.')}</span> {_('Please select destination folder...')}"
            )
            QApplication.processEvents()
        else:
            self.status_label.setText(_("Please select destination folder..."))
            QApplication.processEvents()

        # 选择路径
        target_dir = QFileDialog.getExistingDirectory(self, _("Select folder to extract project"))

        if not target_dir:
            # 用户取消了选择，恢复提示
            self.status_label.setText(_("Extraction cancelled."))
            return

        proj_folder = os.path.join(target_dir, self.pack_info.get("project_name", "Imported_Project"))
        os.makedirs(proj_folder, exist_ok=True)

        self.btn_import.setEnabled(False)
        self.pwd_input.setEnabled(False)
        self.status_label.setText(_("Extracting..."))

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
                self.pwd_input.selectAll()
                self.pwd_input.setFocus()
            else:
                self.status_label.setText(f"<span style='color:red;'>{_('Extraction failed')}: {msg}</span>")
