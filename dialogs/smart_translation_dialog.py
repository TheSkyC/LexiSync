# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QProgressBar, QStackedWidget, QWidget,
    QGroupBox, QCheckBox, QSpinBox, QComboBox, QMessageBox, QSplitter
)
from PySide6.QtCore import Qt, QThread, Signal, QObject
from utils.localization import _
from services.smart_translation_service import SmartTranslationService
from services.ai_worker import AIWorker
from utils.enums import AIOperationType
from copy import deepcopy
import json
import logging

logger = logging.getLogger(__name__)


class AnalysisWorker(QObject):
    """Worker for Phase 1: Analysis"""
    progress = Signal(str)
    finished = Signal(str, str)  # style_guide, glossary_md
    error = Signal(str)

    def __init__(self, app, samples, source_lang, target_lang):
        super().__init__()
        self.app = app
        self.samples = samples
        self.source_lang = source_lang
        self.target_lang = target_lang
        self._is_cancelled = False

    def run(self):
        try:
            translator = self.app.ai_translator

            # 1. Style Analysis
            if self._is_cancelled: return
            self.progress.emit(_("Analyzing style and tone..."))
            style_prompt = SmartTranslationService.generate_style_guide_prompt(
                self.samples, self.source_lang, self.target_lang
            )
            style_guide = translator.translate("Analyze these samples.", style_prompt)

            # 2. Term Extraction
            if self._is_cancelled: return
            self.progress.emit(_("Extracting key terminology..."))
            term_prompt = SmartTranslationService.extract_terms_prompt(self.samples)
            terms_json_str = translator.translate("Extract terms.", term_prompt)

            # 3. Term Translation
            if self._is_cancelled: return
            self.progress.emit(_("Pre-translating terminology..."))
            # Clean up potential markdown code blocks from AI response
            terms_clean = terms_json_str.replace("```json", "").replace("```", "").strip()
            glossary_md = translator.translate(
                terms_clean,
                SmartTranslationService.translate_terms_prompt(terms_clean, self.target_lang)
            )

            self.finished.emit(style_guide, glossary_md)

        except Exception as e:
            self.error.emit(str(e))

    def cancel(self):
        self._is_cancelled = True


class SmartTranslationDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.app = parent
        self.setWindowTitle(_("Intelligent Batch Translation"))
        self.resize(900, 700)
        self.setModal(False)  # Non-modal to allow interaction with main window if needed

        # Data
        self.target_items = []
        self.analysis_samples = []
        self.style_guide = ""
        self.glossary_content = ""
        self.retrieval_enabled = False

        self.setup_ui()
        self.check_plugins()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Stacked Widget for phases
        self.stack = QStackedWidget()

        # Page 1: Configuration
        self.page_config = QWidget()
        self.setup_config_page(self.page_config)
        self.stack.addWidget(self.page_config)

        # Page 2: Preview
        self.page_preview = QWidget()
        self.setup_preview_page(self.page_preview)
        self.stack.addWidget(self.page_preview)

        # Page 3: Execution (Monitor)
        self.page_monitor = QWidget()
        self.setup_monitor_page(self.page_monitor)
        self.stack.addWidget(self.page_monitor)

        layout.addWidget(self.stack)

    def setup_config_page(self, page):
        layout = QVBoxLayout(page)

        # Scope
        scope_group = QGroupBox(_("Scope"))
        scope_layout = QVBoxLayout(scope_group)
        self.scope_combo = QComboBox()
        self.scope_combo.addItems([
            _("All Untranslated Items"),
            _("All Items (Overwrite)"),
            _("Selected Items Only")
        ])
        scope_layout.addWidget(self.scope_combo)
        layout.addWidget(scope_group)

        # Strategy
        strat_group = QGroupBox(_("Strategy"))
        strat_layout = QVBoxLayout(strat_group)

        self.chk_analyze = QCheckBox(_("Auto-analyze Style & Terminology"))
        self.chk_analyze.setChecked(True)
        strat_layout.addWidget(self.chk_analyze)

        self.chk_retrieval = QCheckBox(_("Use Semantic Context Retrieval"))
        self.chk_retrieval.setChecked(True)
        strat_layout.addWidget(self.chk_retrieval)

        self.retrieval_info = QLabel(_("Context Source: Basic Fuzzy Match (Plugin not found)"))
        self.retrieval_info.setStyleSheet("color: gray; margin-left: 20px;")
        strat_layout.addWidget(self.retrieval_info)

        layout.addWidget(strat_group)
        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_analyze = QPushButton(_("Analyze & Preview"))
        btn_analyze.clicked.connect(self.start_analysis)
        btn_analyze.setStyleSheet("font-weight: bold; padding: 8px;")
        btn_layout.addStretch()
        btn_layout.addWidget(btn_analyze)
        layout.addLayout(btn_layout)

    def setup_preview_page(self, page):
        layout = QVBoxLayout(page)

        splitter = QSplitter(Qt.Horizontal)

        # Style Guide
        style_widget = QWidget()
        style_layout = QVBoxLayout(style_widget)
        style_layout.addWidget(QLabel(_("Generated Style Guide:")))
        self.edit_style = QTextEdit()
        style_layout.addWidget(self.edit_style)
        splitter.addWidget(style_widget)

        # Glossary
        glossary_widget = QWidget()
        glossary_layout = QVBoxLayout(glossary_widget)
        glossary_layout.addWidget(QLabel(_("Extracted Glossary (Markdown):")))
        self.edit_glossary = QTextEdit()
        glossary_layout.addWidget(self.edit_glossary)
        splitter.addWidget(glossary_widget)

        layout.addWidget(splitter)

        btn_layout = QHBoxLayout()
        btn_back = QPushButton(_("Back"))
        btn_back.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        btn_start = QPushButton(_("Start Translation"))
        btn_start.clicked.connect(self.start_translation)
        btn_start.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;")

        btn_layout.addWidget(btn_back)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_start)
        layout.addLayout(btn_layout)

    def setup_monitor_page(self, page):
        layout = QVBoxLayout(page)

        self.lbl_status = QLabel(_("Initializing..."))
        self.lbl_status.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(self.lbl_status)

        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet("background-color: #1E1E1E; color: #D4D4D4; font-family: Consolas;")
        layout.addWidget(self.log_view)

        self.btn_stop = QPushButton(_("Stop"))
        self.btn_stop.clicked.connect(self.stop_translation)
        layout.addWidget(self.btn_stop)

    def check_plugins(self):
        # Check if Retrieval Enhancer is available
        plugin = self.app.plugin_manager.get_plugin("com_theskyc_retrieval_enhancer")
        if plugin and plugin.is_ready:
            self.retrieval_enabled = True
            self.retrieval_info.setText(_("Context Source: TF-IDF Semantic Retrieval (Plugin Active)"))
            self.retrieval_info.setStyleSheet("color: green; margin-left: 20px;")
        else:
            self.retrieval_enabled = False

    def log(self, message, level="INFO"):
        color = "#D4D4D4"
        if level == "SUCCESS":
            color = "#4CAF50"
        elif level == "ERROR":
            color = "#F44336"
        elif level == "WARNING":
            color = "#FFC107"

        html = f'<span style="color: {color}">[{level}] {message}</span>'
        self.log_view.append(html)

    def start_analysis(self):
        # 1. Determine Scope
        scope_idx = self.scope_combo.currentIndex()
        all_objs = self.app.translatable_objects

        if scope_idx == 0:  # Untranslated
            self.target_items = [ts for ts in all_objs if not ts.translation.strip() and not ts.is_ignored]
        elif scope_idx == 1:  # All
            self.target_items = [ts for ts in all_objs if not ts.is_ignored]
        elif scope_idx == 2:  # Selected
            self.target_items = self.app._get_selected_ts_objects_from_sheet()

        if not self.target_items:
            QMessageBox.warning(self, _("Warning"), _("No items found in the selected scope."))
            return

        # 2. Sampling
        self.analysis_samples = SmartTranslationService.intelligent_sampling(self.target_items, 100)

        if not self.chk_analyze.isChecked():
            # Skip analysis, go straight to preview (empty) or start
            self.stack.setCurrentIndex(1)
            return

        # 3. Start Analysis Thread
        self.stack.setCurrentIndex(2)  # Use monitor page for progress
        self.lbl_status.setText(_("Phase 1/2: Analyzing Content..."))
        self.progress_bar.setRange(0, 0)  # Indeterminate

        self.analysis_thread = QThread()
        self.analysis_worker = AnalysisWorker(
            self.app, self.analysis_samples,
            self.app.source_language,
            self.app.current_target_language if self.app.is_project_mode else self.app.target_language
        )
        self.analysis_worker.moveToThread(self.analysis_thread)

        self.analysis_thread.started.connect(self.analysis_worker.run)
        self.analysis_worker.progress.connect(lambda msg: self.log(msg))
        self.analysis_worker.finished.connect(self.on_analysis_finished)
        self.analysis_worker.error.connect(self.on_analysis_error)
        self.analysis_worker.finished.connect(self.analysis_thread.quit)
        self.analysis_thread.finished.connect(self.analysis_thread.deleteLater)

        self.analysis_thread.start()

    def on_analysis_finished(self, style, glossary):
        self.edit_style.setPlainText(style)
        self.edit_glossary.setPlainText(glossary)
        self.stack.setCurrentIndex(1)  # Go to Preview

    def on_analysis_error(self, error_msg):
        self.log(f"Analysis failed: {error_msg}", "ERROR")
        QMessageBox.critical(self, _("Error"), error_msg)
        self.stack.setCurrentIndex(0)  # Go back

    def start_translation(self):
        # 1. UI 状态切换
        self.stack.setCurrentIndex(2)
        self.lbl_status.setText(_("Phase 2/2: Translating..."))
        self.progress_bar.setRange(0, len(self.target_items))
        self.progress_bar.setValue(0)
        self.btn_stop.setText(_("Stop"))
        self.btn_stop.setEnabled(True)

        # 2. 构建检索索引 (如果启用)
        if self.chk_retrieval.isChecked() and self.retrieval_enabled:
            self.log("Building semantic index...", "INFO")
            knowledge_base = []
            for ts in self.app.translatable_objects:
                if ts.translation.strip() and not ts.is_ignored:
                    knowledge_base.append({
                        'source': ts.original_semantic,
                        'target': ts.translation
                    })

            self.app.plugin_manager.run_hook('build_retrieval_index', knowledge_base)
            self.log(f"Index built with {len(knowledge_base)} items.", "SUCCESS")

        # 3. 临时注入专用提示词结构
        self._original_prompt_structure = deepcopy(self.app.config.get("ai_prompt_structure"))
        src_lang = self.app.source_language
        tgt_lang = self.app.current_target_language if self.app.is_project_mode else self.app.target_language

        smart_structure = [
            {
                "id": "smart_1",
                "type": "Structural Content",
                "enabled": True,
                "content": f"You are a professional translator. Translate the following text from {src_lang} to {tgt_lang}."
            },
            {
                "id": "smart_2",
                "type": "Dynamic Instruction",
                "enabled": True,
                "content": "Style Guide:\n[Style Guide]"
            },
            {
                "id": "smart_3",
                "type": "Dynamic Instruction",
                "enabled": True,
                "content": "Terminology:\n[Glossary]"
            },
            {
                "id": "smart_4",
                "type": "Dynamic Instruction",
                "enabled": True,
                "content": "Reference Context:\n[Semantic Context]\n[Untranslated Context]\n[Translated Context]"
            },
            {
                "id": "smart_5",
                "type": "Static Instruction",
                "enabled": True,
                "content": "Output ONLY the translation."
            },
        ]
        # 覆盖全局配置
        self.app.config["ai_prompt_structure"] = smart_structure

        # 4. 配置 AI 管理器信号
        self.app.ai_manager.batch_progress.connect(self.on_batch_progress)
        self.app.ai_manager.item_result.connect(self.on_item_result)
        self.app.ai_manager.batch_finished.connect(self.on_batch_finished)

        # 5. 开始批量任务
        self.app.ai_manager.start_batch(self.target_items, self.custom_context_provider)

    def custom_context_provider(self, ts_id):
        # 1. Get Base Context (Neighbors)
        base_context = self.app._generate_ai_context_strings(ts_id)

        # 2. Get Semantic Context (RAG)
        semantic_context = ""
        ts_obj = self.app._find_ts_obj_by_id(ts_id)
        if self.chk_retrieval.isChecked() and self.retrieval_enabled and ts_obj:
            results = self.app.plugin_manager.run_hook('retrieve_context', ts_obj.original_semantic)
            if results:
                lines = [f"- Source: {r['source']}\n  Target: {r['target']}" for r in results]
                semantic_context = "Similar Translations:\n" + "\n".join(lines)

        # 3. Combine
        return {
            "original_context": base_context["original_context"],
            "translation_context": base_context["translation_context"],
            "[Style Guide]": self.edit_style.toPlainText(),
            "[Glossary]": self.edit_glossary.toPlainText(),
            "[Semantic Context]": semantic_context
        }

    def on_batch_progress(self, current, total):
        self.progress_bar.setValue(current)
        self.lbl_status.setText(f"Translating {current}/{total}...")

    def on_item_result(self, ts_id, text, error, op_type):
        ts_obj = self.app._find_ts_obj_by_id(ts_id)
        if error:
            self.log(f"Failed: {ts_obj.original_semantic[:20]}... - {error}", "ERROR")
        else:
            self.log(f"Translated: {ts_obj.original_semantic[:20]}...", "SUCCESS")

    def on_batch_finished(self, results, completed, total):
        self.lbl_status.setText(_("Translation Complete!"))
        self.btn_stop.setText(_("Close"))
        self.btn_stop.clicked.disconnect()
        self.btn_stop.clicked.connect(self.accept)

        if hasattr(self, '_original_prompt_structure') and self._original_prompt_structure:
            self.app.config["ai_prompt_structure"] = self._original_prompt_structure
            self.app.save_config()

        try:
            self.app.ai_manager.batch_progress.disconnect(self.on_batch_progress)
            self.app.ai_manager.item_result.disconnect(self.on_item_result)
            self.app.ai_manager.batch_finished.disconnect(self.on_batch_finished)
        except:
            pass

    def stop_translation(self):
        self.app.ai_manager.stop()
        self.log("Stopping...", "WARNING")