# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QGroupBox, QLabel, QComboBox,
                               QProgressBar, QMessageBox, QHBoxLayout, QWidget, QListWidget, QListWidgetItem)
from PySide6.QtCore import Qt, QThread, Signal
from ui_components.styled_button import StyledButton
from ..utils.constants import SUPPORTED_MODELS
import uuid
import os
from PySide6.QtWidgets import QFileDialog
import logging
logger = logging.getLogger(__name__)

class DownloadThread(QThread):
    progress = Signal(int, str)
    finished = Signal(bool, str)

    def __init__(self, manager, model_id, mirror):
        super().__init__()
        self.manager = manager
        self.model_id = model_id
        self.mirror = mirror

    def run(self):
        try:
            self.manager.download_model(self.model_id, self.mirror, self.progress.emit)
            self.finished.emit(True, "")
        except Exception as e:
            self.finished.emit(False, str(e))


class ImportThread(QThread):
    finished = Signal(bool, str, int)  # success, message, dimension

    def __init__(self, manager, src_path, custom_id, core):
        super().__init__()
        self.manager = manager
        self.src_path = src_path
        self.custom_id = custom_id
        self.core = core

    def run(self):
        try:
            self.manager.import_local_model(self.src_path, self.custom_id)

            # Probe dimension
            from ..backends.onnx_backend import OnnxBackend
            temp_backend = OnnxBackend(self.core.cache_manager)
            model_path = self.manager.get_model_dir(self.custom_id)
            temp_backend.load_model(model_path, self.custom_id, expected_dim=None)

            if not temp_backend._ensure_loaded():
                raise ValueError("Imported model failed to load.")

            dummy_emb = temp_backend._compute_embeddings(["test"])
            dim = dummy_emb.shape[1] if dummy_emb is not None else -1

            if dim <= 0:
                raise ValueError("Could not determine model dimension.")

            self.finished.emit(True, "", dim)
        except Exception as e:
            self.finished.emit(False, str(e), -1)


class SettingsDialog(QDialog):
    def __init__(self, parent, core, translator):
        super().__init__(parent)
        self.core = core
        self._ = translator
        self.model_changed = False
        self.setWindowTitle(self._("Retrieval Enhancer Settings"))
        self.resize(600, 500)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # 1. Model Selection
        model_group = QGroupBox(self._("Model Selection"))
        model_layout = QVBoxLayout(model_group)

        self.model_list = QListWidget()
        self.model_list.currentItemChanged.connect(self.on_model_selected)
        model_layout.addWidget(self.model_list)

        # Info Panel
        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("color: #666; margin: 5px;")
        model_layout.addWidget(self.info_label)

        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_activate = StyledButton(self._("Activate"), on_click=self.activate_model, btn_type="success",
                                         size="small")
        self.btn_download = StyledButton(self._("Download"), on_click=self.start_download, btn_type="primary",
                                         size="small")
        self.btn_delete = StyledButton(self._("Delete Files"), on_click=self.delete_model_files, btn_type="danger",
                                       size="small")

        btn_layout.addWidget(self.btn_activate)
        btn_layout.addWidget(self.btn_download)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addStretch()

        model_layout.addLayout(btn_layout)
        layout.addWidget(model_group)

        # 2. Custom Import
        import_group = QGroupBox(self._("Custom Model"))
        import_layout = QHBoxLayout(import_group)
        self.btn_import = StyledButton(self._("Import Local ONNX Model..."), on_click=self.import_model,
                                       btn_type="default")
        import_layout.addWidget(self.btn_import)
        import_layout.addStretch()
        layout.addWidget(import_group)

        # 3. Download Settings
        dl_group = QGroupBox(self._("Download Settings"))
        dl_layout = QHBoxLayout(dl_group)
        dl_layout.addWidget(QLabel(self._("Mirror Source:")))
        self.combo_mirror = QComboBox()
        self.combo_mirror.addItem("HF-Mirror (China)", "https://hf-mirror.com")
        self.combo_mirror.addItem("Hugging Face", "https://huggingface.co")

        current_mirror = self.core.config.get("mirror", "https://hf-mirror.com")
        idx = self.combo_mirror.findData(current_mirror)
        if idx != -1: self.combo_mirror.setCurrentIndex(idx)
        self.combo_mirror.currentIndexChanged.connect(self.save_mirror_setting)

        dl_layout.addWidget(self.combo_mirror)
        layout.addWidget(dl_group)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel()
        layout.addWidget(self.status_label)

        # Footer
        footer = QHBoxLayout()
        self.btn_clear_cache = StyledButton(self._("Clear Vector Cache"), on_click=self.clear_cache, btn_type="warning",
                                            size="small")
        footer.addWidget(self.btn_clear_cache)
        footer.addStretch()
        btn_close = StyledButton(self._("Close"), on_click=self.accept, btn_type="default")
        footer.addWidget(btn_close)
        layout.addLayout(footer)

        self.refresh_list()

    def model_was_changed(self) -> bool:
        return self.model_changed

    def refresh_list(self):
        self.model_list.clear()
        active_id = self.core.config.get("active_model")

        # Built-in models
        for mid, info in SUPPORTED_MODELS.items():
            item = QListWidgetItem(f"[Built-in] {info['name']}")
            item.setData(Qt.UserRole, mid)
            item.setData(Qt.UserRole + 1, False)  # Is Custom
            if mid == active_id:
                item.setText(item.text() + f" ({self._('Active')})")
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            self.model_list.addItem(item)

        # Custom models
        customs = self.core.config.get("custom_models", {})
        for mid, info in customs.items():
            item = QListWidgetItem(f"[Custom] {info['name']}")
            item.setData(Qt.UserRole, mid)
            item.setData(Qt.UserRole + 1, True)
            if mid == active_id:
                item.setText(item.text() + f" ({self._('Active')})")
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            self.model_list.addItem(item)

    def on_model_selected(self, item, prev):
        if not item: return
        mid = item.data(Qt.UserRole)
        is_custom = item.data(Qt.UserRole + 1)

        is_installed = self.core.model_manager.is_model_installed(mid, is_custom)
        is_active = (mid == self.core.config.get("active_model"))

        # Update Info
        if is_custom:
            desc = self._("Custom imported model.")
        else:
            desc = SUPPORTED_MODELS[mid].get("description", "")

        status_text = self._("Installed") if is_installed else self._("Not Installed")
        color = "green" if is_installed else "red"

        self.info_label.setText(f"{desc}\n{self._('Status')}: <b style='color:{color}'>{status_text}</b>")

        # Update Buttons
        self.btn_activate.setEnabled(is_installed and not is_active)
        self.btn_delete.setEnabled(is_installed)

        if is_custom:
            self.btn_download.setVisible(False)
        else:
            self.btn_download.setVisible(True)
            self.btn_download.setText(self._("Re-download") if is_installed else self._("Download"))

    def start_download(self):
        item = self.model_list.currentItem()
        if not item: return
        mid = item.data(Qt.UserRole)

        self.toggle_ui(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        mirror = self.combo_mirror.currentData()
        self.thread = DownloadThread(self.core.model_manager, mid, mirror)
        self.thread.progress.connect(self.on_progress)
        self.thread.finished.connect(lambda s, m: self.on_download_finished(s, m, mid))
        self.thread.start()

    def on_progress(self, val, msg):
        self.progress_bar.setValue(val)
        self.status_label.setText(msg)

    def on_download_finished(self, success, msg, mid):
        self.toggle_ui(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText("")

        if success:
            QMessageBox.information(self, self._("Success"), self._("Model downloaded successfully."))
            self.on_model_selected(self.model_list.currentItem(), None)  # Refresh buttons

            # Auto activate if it's the first model
            if self.core.config.get("active_model") == mid:
                self.activate_model()
        else:
            QMessageBox.critical(self, self._("Error"), self._("Download failed: ") + msg)

    def import_model(self):
        dir_path = QFileDialog.getExistingDirectory(self, self._("Select Model Folder"))
        if not dir_path: return

        self.toggle_ui(False)
        self.status_label.setText(self._("Importing and verifying model..."))

        custom_id = f"custom_{uuid.uuid4().hex[:8]}"

        self.import_thread = ImportThread(self.core.model_manager, dir_path, custom_id, self.core)
        self.import_thread.finished.connect(
            lambda s, m, d: self.on_import_finished(s, m, d, custom_id, os.path.basename(dir_path)))
        self.import_thread.start()

    def on_import_finished(self, success, message, dimension, custom_id, model_name):
        self.toggle_ui(True)
        self.status_label.setText("")

        if success:
            if "custom_models" not in self.core.config:
                self.core.config["custom_models"] = {}

            self.core.config["custom_models"][custom_id] = {
                "name": model_name,
                "path": custom_id,
                "dim": dimension
            }
            self.core.save_config()
            self.refresh_list()
            QMessageBox.information(self, self._("Success"), self._("Model imported successfully."))
        else:
            QMessageBox.critical(self, self._("Error"), message)
            self.core.model_manager.delete_model(custom_id)

    def delete_model_files(self):
        item = self.model_list.currentItem()
        if not item: return
        mid = item.data(Qt.UserRole)
        is_custom = item.data(Qt.UserRole + 1)

        if mid == self.core.config.get("active_model"):
            QMessageBox.warning(self, self._("Warning"), self._("Cannot delete the currently active model."))
            return

        reply = QMessageBox.question(self, self._("Confirm"),
                                     self._("Are you sure you want to delete the model files?"),
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.core.model_manager.delete_model(mid)
            self.core.cache_manager.clear_model_cache(mid)  # Also clear cache

            if is_custom:
                del self.core.config["custom_models"][mid]
                self.core.save_config()
                self.refresh_list()
            else:
                self.on_model_selected(item, None)

    def activate_model(self):
        item = self.model_list.currentItem()
        if not item: return
        mid = item.data(Qt.UserRole)

        if mid != self.core.config.get("active_model"):
            self.model_changed = True

        self.core.config["active_model"] = mid
        self.core.save_config()
        self.refresh_list()
        QMessageBox.information(self, self._("Success"), self._("Model activated."))

    def clear_cache(self):
        reply = QMessageBox.question(self, self._("Confirm"), self._("Clear vector cache for ALL models?"),
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            success, message = self.core.cache_manager.clear_all_cache()
            if success:
                QMessageBox.information(self, self._("Success"), self._("Cache cleared."))
            else:
                QMessageBox.critical(self, self._("Error"), message)

    def save_mirror_setting(self):
        self.core.config["mirror"] = self.combo_mirror.currentData()
        self.core.save_config()

    def toggle_ui(self, enabled):
        self.btn_download.setEnabled(enabled)
        self.btn_activate.setEnabled(enabled)
        self.btn_delete.setEnabled(enabled)
        self.btn_import.setEnabled(enabled)