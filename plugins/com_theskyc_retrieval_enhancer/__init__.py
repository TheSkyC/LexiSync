# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from plugins.plugin_base import PluginBase
from .core import RetrievalCore
from .ui.settings_dialog import SettingsDialog
from .utils.cache_service import CacheViewerService
from PySide6.QtWidgets import QMessageBox
import os
import logging

logger = logging.getLogger(__name__)

class RetrievalEnhancerPlugin(PluginBase):
    def __init__(self):
        super().__init__()
        self.core = None

    def plugin_id(self) -> str:
        return "com_theskyc_retrieval_enhancer"

    def name(self) -> str:
        return self._("Retrieval Enhancer")

    def description(self) -> str:
        return self._("Provides advanced semantic retrieval using TF-IDF or Local LLM (ONNX).")

    def version(self) -> str:
        return "2.5.0"

    def author(self) -> str:
        return "TheSkyC"

    def external_dependencies(self) -> dict:
        return {
            'scikit-learn': '>=1.0',
            'numpy': '',
            'onnxruntime': '',
            'tokenizers': ''
        }

    def setup(self, main_window, plugin_manager):
        super().setup(main_window, plugin_manager)
        plugin_dir = os.path.join(plugin_manager.plugin_dir, self.plugin_id())
        self.core = RetrievalCore(plugin_dir)

    def show_settings_dialog(self, parent_widget) -> bool:
        dialog = SettingsDialog(parent_widget, self.core, self._)
        dialog.exec()

        if dialog.model_was_changed():
            self.core.clear_all_backends()
            QMessageBox.information(
                parent_widget,
                self._("Model Changed"),
                self._("The active model has been changed.\n"
                       "Please re-open the 'Smart Translation' dialog to rebuild the index with the new model.")
            )
            return True
        return False

    # --- Hooks ---
    def register_resource_viewers(self) -> list:
        return [{
            'id': 'retrieval_cache',
            'name': self._("Retrieval Cache Viewer"),
            'service': CacheViewerService(self.core.cache_db_path)
        }]

    def build_retrieval_index(self, data_list: list, progress_callback=None, check_cancel=None):
        """Hook called by SmartTranslationDialog to build index."""
        logger.info(f"[RetrievalPlugin] Building index for {len(data_list)} items...")
        result = self.core.build_index(data_list, progress_callback, check_cancel)
        logger.info(f"[RetrievalPlugin] Build index result: {result}")
        return result

    def retrieve_context(self, query_text: str, limit: int = 3, mode: str = "auto"):
        """
        Hook called to retrieve similar items.
        mode: 'auto', 'tfidf', 'onnx'
        """
        logger.info(f"[RetrievalPlugin] Querying: '{query_text[:30]}...' (Mode: {mode})")

        results = self.core.retrieve(query_text, limit, mode)

        if results:
            top_score = results[0].get('score', 0)
            logger.info(f"[RetrievalPlugin] Found {len(results)} matches. Top score: {top_score:.4f}")
        else:
            logger.info("[RetrievalPlugin] No matches found.")
        return results

    def get_available_backends(self) -> dict:
        """Returns status of backends: {'tfidf': bool, 'onnx': bool}"""
        return {
            'tfidf': self.core.tfidf_backend.is_available(),
            'onnx': self.core.onnx_backend.is_available()
        }