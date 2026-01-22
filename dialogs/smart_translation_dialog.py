# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSplitter,
    QTextEdit, QProgressBar, QStackedWidget, QWidget,
    QGroupBox, QCheckBox, QSpinBox, QComboBox, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QDoubleSpinBox, QGridLayout, QButtonGroup ,QRadioButton
)
from PySide6.QtCore import Qt, QThread, Signal, QObject, QEvent
from dialogs.test_translation_dialog import TestTranslationDialog
from dialogs.interactive_review_dialog import InteractiveReviewDialog
from dialogs.resource_save_options_dialog import ResourceSaveOptionsDialog
from dialogs.resource_conflict_dialog import ResourceConflictDialog
from services.smart_translation_service import SmartTranslationService
from services.ai_worker import AIWorker
from utils.enums import AIOperationType
from utils.keyword_matcher import KeywordMatcher
from utils.localization import _
from ui_components.tooltip import Tooltip
from ui_components.styled_button import StyledButton
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import re
import json
import uuid
from datetime import datetime
import threading
import logging

logger = logging.getLogger(__name__)


class IndexBuildWorker(QObject):
    finished = Signal()
    progress = Signal(int)

    def __init__(self, app, knowledge_base):
        super().__init__()
        self.app = app
        self.knowledge_base = knowledge_base
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            if self.knowledge_base:
                self.app.plugin_manager.run_hook(
                    'build_retrieval_index',
                    self.knowledge_base,
                    progress_callback=self.progress.emit,
                    check_cancel=lambda: self._is_cancelled
                )
        except Exception as e:
            logger.error(f"Index build failed: {e}")
        finally:
            self.finished.emit()


class AnalysisWorker(QObject):
    """Phase 1 分析工作线程"""
    progress = Signal(str)
    finished = Signal(str, str, float, list)   # style_guide, glossary_md, recommended_temp, context_list
    error = Signal(str)

    def __init__(self, app, samples, all_items, source_lang, target_lang,
                 term_mode="fast", max_threads=1, use_context=True,
                 batch_size=50, orphan_ratio=0.2, inject_glossary=False,
                 do_style_analysis=True, do_term_extraction=True):
        super().__init__()
        self.app = app
        self.samples = samples
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.all_items = all_items
        self.term_mode = term_mode
        self.max_threads = max_threads
        self.use_context = use_context
        self.batch_size = batch_size
        self.orphan_ratio = orphan_ratio
        self.inject_glossary = inject_glossary
        self._is_cancelled = False
        self.glossary_matcher = None
        self.do_style_analysis = do_style_analysis
        self.do_term_extraction = do_term_extraction

    def run(self):
        """执行分析任务"""
        try:
            translator = self.app.ai_translator
            self._load_existing_glossary()

            clean_style_guide = ""
            rec_temp = 0.3
            glossary_md = ""
            terms_data = []

            # 步骤1: 风格分析
            if self.do_style_analysis:
                if self._is_cancelled: return
                self.progress.emit(_("Analyzing style and tone..."))
                raw_style_guide = self._analyze_style(translator)
                clean_style_guide, rec_temp = self._parse_and_strip_temperature(raw_style_guide)

            # 步骤2: 术语提取
            if self.do_term_extraction:
                if self._is_cancelled: return
                self.progress.emit(_("Extracting key terminology..."))

                terms_data = self._extract_terms(translator)
                logger.debug(f"[SmartTrans] Total terms extracted: {len(terms_data)}")

                # 混合模式增强：如果是 Deep 模式且开启了上下文，追加原文例句
                if self.term_mode == "deep" and self.use_context:
                    self.progress.emit(_("Augmenting AI explanations with source snippets..."))
                    total_c = len(terms_data)
                    for i, item in enumerate(terms_data):
                        if self._is_cancelled: return
                        # 查找原文例句
                        snippet = SmartTranslationService.find_context_snippets(item['term'], self.all_items)
                        if snippet:
                            # 组合 AI 解释和原文例句
                            ai_explanation = item.get('context', '')
                            if ai_explanation:
                                item['context'] = f"<b>[AI]:</b> {ai_explanation}<br><b>[Ref]:</b> {snippet}"
                            else:
                                item['context'] = snippet

                # 步骤3: 术语翻译
                if self._is_cancelled: return
                glossary_md = ""
                if self.term_mode == "fast":
                    self.progress.emit(_("Running frequency analysis (Fast Mode)..."))
                    candidates = SmartTranslationService.extract_terms_frequency_based(self.all_items, 100)

                    if self.glossary_matcher:
                        candidates = [c for c in candidates if not self.glossary_matcher.extract_keywords(c)]

                    terms_data = [{"term": c, "context": ""} for c in candidates]
                    if self.use_context:
                        self.progress.emit(_("Scanning context snippets for terms..."))
                        total_c = len(terms_data)
                        for i, item in enumerate(terms_data):
                            if self._is_cancelled: return
                            if i % 10 == 0:
                                self.progress.emit(_("Scanning context: {i}/{t}").format(i=i + 1, t=total_c))

                            snippet = SmartTranslationService.find_context_snippets(item['term'], self.all_items)
                            item['context'] = snippet

                    self.progress.emit(_("Translating terms with context..."))
                    glossary_md = self._translate_terms(translator, terms_data, style_guide=clean_style_guide)

                elif self.term_mode == "deep":
                    self.progress.emit(_("Translating {count} unique terms...").format(count=len(terms_data)))
                    glossary_md = self._translate_terms(translator, terms_data, style_guide=clean_style_guide)

            self.finished.emit(clean_style_guide, glossary_md, rec_temp, terms_data)

        except Exception as e:
            logger.error(f"Analysis failed: {e}", exc_info=True)
            self.error.emit(str(e))

    def _create_smart_batches(self, items, batch_size=50, merge_threshold_ratio=0.2):
        """
        创建智能批次。
        如果最后一批的数量少于 batch_size * ratio (例如 50 * 0.2 = 10)，
        则将其合并到倒数第二批中，防止产生过小的孤立批次。
        """
        total = len(items)
        if total == 0: return []

        # 如果总量本身就只比一个批次多一点点 (例如 55 个，阈值是 60)，直接作为一个批次
        # 50 * (1 + 0.2) = 60
        if total <= batch_size * (1 + merge_threshold_ratio):
            return [items]

        # 标准分批
        batches = [items[i:i + batch_size] for i in range(0, total, batch_size)]

        # 检查最后一批
        if len(batches) > 1:
            last_batch = batches[-1]
            # 如果最后一批太小 (比如只有 1-10 个)
            if len(last_batch) < (batch_size * merge_threshold_ratio):
                # 合并到倒数第二批
                prev_batch = batches[-2]
                batches[-2] = prev_batch + last_batch
                batches.pop()  # 移除最后一个

        return batches

    def _parse_and_strip_temperature(self, text):
        """从风格指南中提取温度并将其从文本中移除"""
        import re
        rec_temp = 0.3  # 默认值

        # 匹配 "Recommended Temperature" 后面的第一个数字 (如 0.5, .5, 1.0)
        pattern = r'[\-\*]*\s*(\*\*)?Recommended Temperature(\*\*)?:\s*([0-1]?\.?\d+)'

        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                val_str = match.group(3)
                val = float(val_str)
                rec_temp = max(0.1, min(1.0, val))
                # 移除整行
                text = re.sub(r'[\-\*]*\s*(\*\*)?Recommended Temperature(\*\*)?:\s*.*(\n|$)', '', text, flags=re.IGNORECASE)
            except ValueError:
                pass

        return text.strip(), rec_temp

    def _analyze_style(self, translator):
        """分析翻译风格"""
        style_prompt = SmartTranslationService.generate_style_guide_prompt(
            self.samples, self.source_lang, self.target_lang
        )
        style_guide = translator.translate("Analyze these samples.", style_prompt)
        return style_guide.strip()

    def _load_existing_glossary(self):
        """Load existing glossary terms into matcher"""
        if not self.inject_glossary:
            return

        self.progress.emit(_("Loading existing glossary for consistency..."))
        try:
            all_terms = {}
            def load_from_db(db_path):
                if not db_path or not os.path.exists(db_path): return
                import sqlite3
                try:
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    query = """
                        SELECT t_source.term_text, t_target.term_text 
                        FROM term_translations tt
                        JOIN terms t_source ON tt.source_term_id = t_source.id
                        JOIN terms t_target ON tt.target_term_id = t_target.id
                        WHERE t_source.language_code = ? AND t_target.language_code = ?
                    """
                    cursor.execute(query, (self.source_lang, self.target_lang))
                    for row in cursor.fetchall():
                        all_terms[row[0]] = row[1]
                    conn.close()
                except Exception as e:
                    logger.error(f"Failed to load glossary from {db_path}: {e}")

            load_from_db(self.app.glossary_service.global_db_path)
            load_from_db(self.app.glossary_service.project_db_path)

            if all_terms:
                self.glossary_matcher = KeywordMatcher(case_sensitive=False)
                self.glossary_matcher.add_keywords(all_terms)
                logger.info(f"Loaded {len(all_terms)} terms for consistency check.")

        except Exception as e:
            logger.error(f"Error loading glossary: {e}")

    def _extract_terms(self, translator):
        """提取关键术语 (返回 [{'term':..., 'context':...}])"""
        if self.term_mode == "deep":
            self.progress.emit(_("Starting Deep Scan (Threads: {n})...").format(n=self.max_threads))
            all_terms_dict = {}
            seen_terms_lower = set()

            batches = self._create_smart_batches(
                self.all_items,
                batch_size=self.batch_size,
                merge_threshold_ratio=self.orphan_ratio
            )
            total_batches = len(batches)
            completed_batches = 0
            lock = threading.Lock()

            def process_batch(batch_items):
                if self._is_cancelled: return []
                batch_text = "\n".join([t.original_semantic for t in batch_items])
                existing_terms_str = ""
                if self.glossary_matcher:
                    found = self.glossary_matcher.extract_keywords(batch_text)
                    found_terms = sorted(list(set([f['term'] for f in found])))
                    if found_terms:
                        existing_terms_str = "- " + "\n- ".join(found_terms[:50])

                prompt = SmartTranslationService.extract_terms_batch_prompt(batch_text, existing_terms_str)

                try:
                    resp = translator.translate("Extract terms.", prompt)
                    valid, terms = SmartTranslationService.validate_terms_json(resp)
                    return terms if valid else []
                except Exception as e:
                    logger.warning(f"Batch extraction failed: {e}")
                    return []

            with ThreadPoolExecutor(max_workers=self.max_threads) as executor:
                futures = {executor.submit(process_batch, batch): batch for batch in batches}

                for future in as_completed(futures):
                    if self._is_cancelled:
                        logger.info("AnalysisWorker cancelled during extraction loop.")
                        executor.shutdown(wait=False, cancel_futures=True)
                        return []

                    try:
                        result_items = future.result()
                        with lock:
                            for item in result_items:
                                t = item['term'].strip()
                                # Length check
                                if len(t.split()) > 5 or len(t) > 25: continue
                                # Punctuation check
                                if t.endswith(('。', '.', '!', '！', '?', '？', ':', '：')): continue
                                t_lower = t.lower()

                                if self.glossary_matcher:
                                    matches = self.glossary_matcher.extract_keywords(t)
                                    if any(m['term'].lower() == t_lower for m in matches):
                                        continue

                                if t_lower not in seen_terms_lower:
                                    all_terms_dict[t] = item
                                    seen_terms_lower.add(t_lower)
                                else:
                                    existing_key = next((k for k in all_terms_dict if k.lower() == t_lower), None)
                                    if existing_key:
                                        if not all_terms_dict[existing_key].get('context') and item.get('context'):
                                            all_terms_dict[existing_key]['context'] = item['context']

                            completed_batches += 1
                            self.progress.emit(
                                _("Deep Scan: Batch {c}/{t}...").format(c=completed_batches, t=total_batches))
                    except Exception as e:
                        logger.error(f"Error processing batch result: {e}")

            return list(all_terms_dict.values())
        return []

    def _translate_terms(self, translator, terms_data_list, style_guide=""):
        """翻译术语列表"""
        if not terms_data_list:
            return "| Source | Target |\n|--------|--------|\n"

        # 配置批次大小
        batches = self._create_smart_batches(
            terms_data_list,
            batch_size=self.batch_size,
            merge_threshold_ratio=self.orphan_ratio
        )
        total_batches = len(batches)

        self.progress.emit(_("Translating terms in {t} batches (Threads: {n})...").format(
            t=total_batches, n=self.max_threads))

        results = ["| Source | Target |\n|--------|--------|"]
        completed_batches = 0
        lock = threading.Lock()

        def process_batch(batch_items):
            if self._is_cancelled: return ""
            try:
                # Find sub-terms for consistency
                reference_glossary_str = ""
                if self.glossary_matcher:
                    batch_text_blob = " ".join([item['term'] for item in batch_items])
                    found_refs = self.glossary_matcher.extract_keywords(batch_text_blob)

                    # Deduplicate and format
                    unique_refs = {}
                    for ref in found_refs:
                        term = ref['term']
                        translation = ref['data']
                        if term not in unique_refs:
                            unique_refs[term] = translation

                    if unique_refs:
                        lines = [f"- {k}: {v}" for k, v in unique_refs.items()]
                        reference_glossary_str = "\n".join(lines[:30])  # Limit context size

                terms_json = json.dumps(batch_items, ensure_ascii=False)

                translate_prompt = SmartTranslationService.translate_terms_with_context_prompt(
                    terms_json, self.target_lang, style_guide, reference_glossary_str
                )

                glossary_raw = translator.translate(terms_json, translate_prompt)
                return SmartTranslationService.clean_ai_response(glossary_raw, "markdown")
            except Exception as e:
                logger.warning(f"Term batch translation failed: {e}")
                return ""

        with ThreadPoolExecutor(max_workers=self.max_threads) as executor:
            futures = {executor.submit(process_batch, batch): batch for batch in batches}

            for future in as_completed(futures):
                if self._is_cancelled:
                    executor.shutdown(wait=False, cancel_futures=True)
                    return ""

                batch_result = future.result()
                if batch_result:
                    with lock:
                        results.append(batch_result)
                        completed_batches += 1
                        self.progress.emit(
                            _("Translating terms: Batch {c}/{t} done...").format(c=completed_batches, t=total_batches)
                        )

        return "\n".join(results)

    def cancel(self):
        """取消分析任务"""
        self._is_cancelled = True


class SmartTranslationDialog(QDialog):
    """智能批量翻译对话框"""

    def __init__(self, parent):
        super().__init__(parent)
        self.app = parent
        self.setWindowTitle(_("Intelligent Batch Translation"))
        self.resize(800, 700)
        self.setModal(False)
        self.tooltip = Tooltip(self)
        self._last_hovered_row = -1

        # 数据成员
        self.target_items = []
        self.analysis_samples = []
        self._cached_glossary_dict = {}
        self.style_guide = ""
        self.glossary_content = ""
        self.retrieval_enabled = False
        self._original_prompt_structure = None

        # 初始化信号连接标志位
        self._signals_connected = False

        # 线程管理
        self.analysis_thread = None
        self.analysis_worker = None

        # 初始化UI和检查插件
        self.setup_ui()
        self.check_plugins()


    def setup_ui(self):
        """设置UI布局"""
        layout = QVBoxLayout(self)

        # 配置 -> 预览 -> 执行
        self.stack = QStackedWidget()

        self.page_config = self._create_config_page()
        self.page_preview = self._create_preview_page()
        self.page_monitor = self._create_monitor_page()

        self.stack.addWidget(self.page_config)
        self.stack.addWidget(self.page_preview)
        self.stack.addWidget(self.page_monitor)

        layout.addWidget(self.stack)

    def _create_config_page(self):
        """创建配置页面"""
        page = QWidget()
        layout = QVBoxLayout(page)

        layout.addWidget(self._create_scope_group())
        layout.addWidget(self._create_strategy_group())
        layout.addWidget(self._create_advanced_group())

        layout.addStretch()

        # 底部按钮
        btn_layout = QHBoxLayout()
        btn_analyze = StyledButton(_("Analyze & Preview"), on_click=self.start_analysis, btn_type="success")
        btn_layout.addStretch()
        btn_layout.addWidget(btn_analyze)
        layout.addLayout(btn_layout)

        return page

    def _create_scope_group(self):
        """创建作用域选择组"""
        scope_group = QGroupBox(_("Scope"))
        scope_layout = QVBoxLayout(scope_group)

        self.scope_combo = QComboBox()
        self.scope_combo.addItems([
            _("All Untranslated Items"),
            _("All Items"),
            _("Selected Items")
        ])
        scope_layout.addWidget(self.scope_combo)

        return scope_group

    def _create_strategy_group(self):
        """创建策略选择组"""
        strat_group = QGroupBox(_("Strategy"))
        strat_layout = QVBoxLayout(strat_group)
        strat_layout.setSpacing(15)

        # --- Group 1: Context Sources (Used during Translation Phase) ---
        context_box = QGroupBox(_("Context Sources"))
        context_box.setStyleSheet(
            "QGroupBox { border: 1px solid #DDD; border-radius: 4px; margin-top: 5px; } "
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px; font-weight: bold; }"
        )
        context_layout = QGridLayout(context_box)
        context_layout.setContentsMargins(10, 15, 10, 10)
        context_layout.setVerticalSpacing(8)

        # 1. Neighboring Context
        self.chk_neighbors = QCheckBox(_("Neighboring Text"))
        self.chk_neighbors.setChecked(True)
        self.chk_neighbors.setToolTip(
            _("Include nearby original and translated text to help AI understand the context."))

        self.spin_neighbors = QSpinBox()
        self.spin_neighbors.setRange(1, 20)
        self.spin_neighbors.setValue(3)
        self.spin_neighbors.setSuffix(_(" lines"))
        self.chk_neighbors.stateChanged.connect(self.spin_neighbors.setEnabled)

        context_layout.addWidget(self.chk_neighbors, 0, 0)
        context_layout.addWidget(self.spin_neighbors, 0, 1)

        # 2. Semantic Retrieval
        self.chk_retrieval = QCheckBox(_("Semantic Retrieval"))
        self.chk_retrieval.setChecked(True)
        self.chk_retrieval.setToolTip(
            _("Search for semantically similar texts in the project to maintain consistency."))

        self.spin_retrieval = QSpinBox()
        self.spin_retrieval.setRange(1, 20)
        self.spin_retrieval.setValue(5)
        self.spin_retrieval.setSuffix(_(" items"))
        self.chk_retrieval.stateChanged.connect(self.spin_retrieval.setEnabled)

        # Retrieval Mode Combo
        self.combo_retrieval_mode = QComboBox()
        self.combo_retrieval_mode.addItem(_("Auto (Best)"), "auto")
        self.combo_retrieval_mode.addItem("TF-IDF", "tfidf")
        self.combo_retrieval_mode.addItem("Local LLM", "onnx")

        # Check availability via plugin
        plugin = self.app.plugin_manager.get_plugin("com_theskyc_retrieval_enhancer")
        if plugin:
            status = plugin.get_available_backends()
            model = self.combo_retrieval_mode.model()
            if not status.get('tfidf'): model.item(1).setEnabled(False)
            if not status.get('onnx'): model.item(2).setEnabled(False)
        else:
            self.combo_retrieval_mode.setEnabled(False)

        context_layout.addWidget(self.chk_retrieval, 1, 0)

        retrieval_opts = QHBoxLayout()
        retrieval_opts.setContentsMargins(0, 0, 0, 0)
        retrieval_opts.addWidget(self.spin_retrieval)
        retrieval_opts.addWidget(self.combo_retrieval_mode)
        context_layout.addLayout(retrieval_opts, 1, 1)

        # 3. TM
        tm_container = QWidget()
        tm_layout = QHBoxLayout(tm_container)
        tm_layout.setContentsMargins(0, 0, 0, 0)

        self.chk_use_tm = QCheckBox(_("Translation Memory"))
        self.chk_use_tm.setChecked(True)

        self.tm_mode_group = QButtonGroup(self)
        self.rb_tm_exact = QRadioButton(_("Exact"))
        self.rb_tm_fuzzy = QRadioButton(_("Fuzzy"))
        self.rb_tm_fuzzy.setChecked(True)
        self.tm_mode_group.addButton(self.rb_tm_exact)
        self.tm_mode_group.addButton(self.rb_tm_fuzzy)

        self.lbl_tm_threshold = QLabel(_("Threshold:"))
        self.spin_tm_threshold = QDoubleSpinBox()
        self.spin_tm_threshold.setRange(0.1, 1.0)
        self.spin_tm_threshold.setSingleStep(0.05)
        self.spin_tm_threshold.setValue(0.75)

        self.chk_use_tm.toggled.connect(self.rb_tm_exact.setEnabled)
        self.chk_use_tm.toggled.connect(self.rb_tm_fuzzy.setEnabled)
        self.chk_use_tm.toggled.connect(self._update_tm_threshold_state)
        self.rb_tm_exact.toggled.connect(self._update_tm_threshold_state)
        self.rb_tm_fuzzy.toggled.connect(self._update_tm_threshold_state)

        tm_layout.addWidget(self.chk_use_tm)
        tm_layout.addStretch(1)
        tm_layout.addWidget(self.rb_tm_exact)
        tm_layout.addSpacing(10)
        tm_layout.addWidget(self.rb_tm_fuzzy)
        tm_layout.addSpacing(15)
        tm_layout.addWidget(self.lbl_tm_threshold)
        tm_layout.addWidget(self.spin_tm_threshold)
        # Removed trailing addStretch() to align right

        context_layout.addWidget(tm_container, 2, 0, 1, 2)

        # 4. Glossary Database
        self.chk_use_glossary_db = QCheckBox(_("Existing Glossary Database"))
        self.chk_use_glossary_db.setChecked(True)
        self.chk_use_glossary_db.setToolTip(_("Use established terms from the database during translation."))
        context_layout.addWidget(self.chk_use_glossary_db, 3, 0, 1, 2)

        strat_layout.addWidget(context_box)

        # --- Group 2: Analysis & Glossary Generation (Phase 1) ---
        analysis_box = QGroupBox(_("Analysis & Glossary Generation"))
        analysis_box.setStyleSheet(
            "QGroupBox { border: 1px solid #DDD; border-radius: 4px; margin-top: 5px; } "
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px; font-weight: bold; }"
        )
        analysis_layout = QVBoxLayout(analysis_box)
        analysis_layout.setContentsMargins(10, 15, 10, 10)

        # Analyze Style
        self.chk_analyze_style = QCheckBox(_("Analyze Style"))
        self.chk_analyze_style.setChecked(True)
        self.chk_analyze_style.setToolTip(_("Generate a style guide based on the source text."))
        analysis_layout.addWidget(self.chk_analyze_style)

        self.chk_extract_terms = QCheckBox(_("Extract Terminology"))
        self.chk_extract_terms.setChecked(True)
        self.chk_extract_terms.setToolTip(_("Extract and translate key terms from the text."))
        analysis_layout.addWidget(self.chk_extract_terms)

        # Sub-options Container (Term extraction options)
        analysis_options_widget = QWidget()
        analysis_options_layout = QVBoxLayout(analysis_options_widget)
        analysis_options_layout.setContentsMargins(20, 0, 0, 0)  # Indent
        analysis_options_layout.setSpacing(8)

        # Generation Method
        method_layout = QHBoxLayout()
        method_layout.addWidget(QLabel(_("Generation Method:")))
        self.term_mode_combo = QComboBox()
        self.term_mode_combo.addItem(_("Fast (Frequency-based)"), "fast")
        self.term_mode_combo.addItem(_("Deep (AI-Scan)"), "deep")
        self.term_mode_combo.setToolTip(
            _("Fast: Scans high-frequency words locally, then AI filters them. Cheap & Fast.\n"
              "Deep: AI reads ALL texts to find terms. Expensive & Slow but thorough.")
        )
        method_layout.addWidget(self.term_mode_combo)
        method_layout.addStretch()
        analysis_options_layout.addLayout(method_layout)

        # Reference Existing Terms
        self.chk_inject_glossary = QCheckBox(_("Reference Existing Terms"))
        self.chk_inject_glossary.setChecked(True)
        self.chk_inject_glossary.setToolTip(
            _("During analysis, check against the existing glossary to avoid duplicates and ensure compound word consistency (e.g., 'File Manager' uses 'File').")
        )
        analysis_options_layout.addWidget(self.chk_inject_glossary)

        # Enhance Context
        self.chk_term_context = QCheckBox(_("Enhance Terms with Contextual Examples"))
        self.chk_term_context.setChecked(False)
        self.chk_term_context.setToolTip(
            _("Provide example sentences for each extracted term to help the AI disambiguate meanings (e.g., 'Home' as 'Base' vs 'Menu').")
        )
        analysis_options_layout.addWidget(self.chk_term_context)

        analysis_layout.addWidget(analysis_options_widget)
        strat_layout.addWidget(analysis_box)

        # Logic: Disable sub-options if analysis is unchecked
        self.chk_extract_terms.toggled.connect(analysis_options_widget.setEnabled)

        return strat_group

    def _create_advanced_group(self):
        adv_group = QGroupBox(_("Advanced Configuration"))
        adv_layout = QVBoxLayout(adv_group)

        # Row 1: Concurrency, Batch Size, Orphan Ratio
        row1 = QHBoxLayout()

        # Concurrency
        row1.addWidget(QLabel(_("Threads:")))
        self.thread_spinbox = QSpinBox()
        self.thread_spinbox.setRange(1, 16)
        self.thread_spinbox.setValue(self.app.config.get("ai_max_concurrent_requests", 4))
        self.thread_spinbox.setToolTip(_("Parallel requests count."))
        row1.addWidget(self.thread_spinbox)

        row1.addSpacing(15)

        # Batch Size
        row1.addWidget(QLabel(_("Batch Size:")))
        self.batch_size_spinbox = QSpinBox()
        self.batch_size_spinbox.setRange(1, 500)
        self.batch_size_spinbox.setSingleStep(10)
        self.batch_size_spinbox.setValue(50)
        self.batch_size_spinbox.setToolTip(_("Items per AI request."))
        row1.addWidget(self.batch_size_spinbox)

        row1.addSpacing(15)

        # Orphan Ratio
        row1.addWidget(QLabel(_("Orphan Ratio:")))
        self.orphan_ratio_spinbox = QDoubleSpinBox()
        self.orphan_ratio_spinbox.setRange(0.0, 1.0)
        self.orphan_ratio_spinbox.setSingleStep(0.05)
        self.orphan_ratio_spinbox.setValue(0.2)
        self.orphan_ratio_spinbox.setToolTip(_("Merge last batch if smaller than this ratio of Batch Size."))
        row1.addWidget(self.orphan_ratio_spinbox)

        row1.addStretch()
        adv_layout.addLayout(row1)

        # Row 2: Self-Repair, Timeout
        row2 = QHBoxLayout()

        # Self-Repair
        row2.addWidget(QLabel(_("Self-Repair:")))
        self.repair_spinbox = QSpinBox()
        self.repair_spinbox.setRange(0, 3)
        self.repair_spinbox.setValue(1)
        self.repair_spinbox.setSuffix(_(" times"))
        self.repair_spinbox.setToolTip(_("Max retries if validation fails."))
        row2.addWidget(self.repair_spinbox)

        row2.addSpacing(15)

        # Timeout
        row2.addWidget(QLabel(_("Timeout:")))
        self.timeout_spinbox = QSpinBox()
        self.timeout_spinbox.setRange(10, 300)
        self.timeout_spinbox.setSingleStep(5)
        self.timeout_spinbox.setValue(60)
        self.timeout_spinbox.setSuffix(" s")
        self.timeout_spinbox.setToolTip(_("Max time to wait for AI response."))
        row2.addWidget(self.timeout_spinbox)

        row2.addStretch()
        adv_layout.addLayout(row2)

        return adv_group

    def _create_preview_page(self):
        """创建预览页面"""
        page = QWidget()
        layout = QVBoxLayout(page)

        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel(_("Recommended Temperature:")))

        self.temp_spinbox = QDoubleSpinBox()
        self.temp_spinbox.setRange(0.0, 1.5)
        self.temp_spinbox.setSingleStep(0.1)
        self.temp_spinbox.setValue(0.3)  # 默认值
        self.temp_spinbox.setToolTip(
            _("Lower values (0.1) are more deterministic/precise.\nHigher values (0.8) are more creative."))
        top_bar.addWidget(self.temp_spinbox)
        top_bar.addStretch()

        layout.addLayout(top_bar)

        splitter = QSplitter(Qt.Horizontal)

        # 风格指南编辑器
        splitter.addWidget(self._create_style_guide_widget())

        # 术语表编辑器
        splitter.addWidget(self._create_glossary_widget())

        splitter.setSizes([400, 400])
        layout.addWidget(splitter)

        # 底部按钮
        # Back
        btn_layout = QHBoxLayout()
        btn_back = StyledButton(_("Back"), on_click=lambda: self.stack.setCurrentIndex(0), btn_type="default")

        # Test Lab
        btn_test = StyledButton(_("Test Lab"), on_click=self.open_test_lab, btn_type="purple")

        # Interactive Review Button
        btn_review = StyledButton(_("Start Interactive Review"), on_click=self.start_interactive_review, btn_type="primary")

        # Batch Translation
        btn_start = StyledButton(_("Start Batch Translation"), on_click=self.start_translation, btn_type="success")


        btn_layout.addWidget(btn_back)
        btn_layout.addWidget(btn_test)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_review)
        btn_layout.addWidget(btn_start)

        layout.addLayout(btn_layout)
        return page

    def _create_style_guide_widget(self):
        """创建风格指南编辑器"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel(_("Generated Style Guide:")))

        self.edit_style = QTextEdit()
        self.edit_style.setPlaceholderText(_("Style guide will appear here after analysis..."))
        layout.addWidget(self.edit_style)

        return widget

    def _create_glossary_widget(self):
        """创建术语表编辑器"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Header with button
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel(_("Extracted Glossary:")))
        header_layout.addStretch()

        self.btn_save_glossary = StyledButton(_("Save to Glossary..."), on_click=self.on_save_glossary_clicked,
                                              btn_type="primary", size="small")
        header_layout.addWidget(self.btn_save_glossary)

        layout.addLayout(header_layout)

        self.table_glossary = QTableWidget()

        self.table_glossary.setColumnCount(3)

        self.table_glossary.setHorizontalHeaderLabels(["", _("Source"), _("Target")])

        # 设置列宽行为
        header = self.table_glossary.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)

        self.table_glossary.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_glossary.setSortingEnabled(True)

        self.table_glossary.setMouseTracking(True)
        self.table_glossary.viewport().installEventFilter(self)

        layout.addWidget(self.table_glossary)

        return widget

    def _create_monitor_page(self):
        """创建执行监控页面"""
        page = QWidget()
        layout = QVBoxLayout(page)

        self.lbl_status = QLabel(_("Initializing..."))
        self.lbl_status.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(self.lbl_status)

        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet(
            "background-color: #1E1E1E; color: #D4D4D4; "
            "font-family: Consolas, monospace;"
        )
        layout.addWidget(self.log_view)

        self.btn_stop = StyledButton(_("Stop"), on_click=self.stop_translation, btn_type="danger")
        layout.addWidget(self.btn_stop)

        return page

    def eventFilter(self, obj, event):
        if obj == self.table_glossary.viewport():
            if event.type() == QEvent.MouseMove:
                index = self.table_glossary.indexAt(event.pos())
                if index.isValid() and index.column() == 1:  # 1: Source
                    row = index.row()
                    if row != self._last_hovered_row:
                        self._last_hovered_row = row
                        item = self.table_glossary.item(row, 1)
                        term = item.text()  # 获取当前术语
                        context = item.data(Qt.UserRole)

                        if context:
                            # 高亮关键词
                            # 1. 转义术语中的正则特殊字符 (如 +, ?, *)
                            escaped_term = re.escape(term)

                            # 2. 定义高亮样式 (黄色背景，黑色文字，圆角)
                            hl_style = "background-color: #FFEB3B; color: #000; font-weight: bold; padding: 0 2px; border-radius: 2px;"

                            # 3. 正则替换
                            try:
                                highlighted_context = re.sub(
                                    f"(?i)({escaped_term})",
                                    f"<span style='{hl_style}'>\\1</span>",
                                    context
                                )
                            except Exception:
                                highlighted_context = context

                            html = (
                                f"<b style='color:#4CAF50;'>{_('Context / Usage')}:</b><br>"
                                f"<div style='margin-top:4px; color:#DDD;'>{highlighted_context}</div>"
                            )
                            self.tooltip.show_tooltip(event.globalPos(), html, delay=0)
                        else:
                            self.tooltip.hide()
                else:
                    self.tooltip.hide()
                    self._last_hovered_row = -1

            elif event.type() == QEvent.Leave:
                self.tooltip.hide()
                self._last_hovered_row = -1

        return super().eventFilter(obj, event)

    def _update_tm_threshold_state(self):
        """Enable/Disable threshold spinbox based on TM settings."""
        tm_enabled = self.chk_use_tm.isChecked()
        is_fuzzy = self.rb_tm_fuzzy.isChecked()
        self.lbl_tm_threshold.setEnabled(tm_enabled and is_fuzzy)
        self.spin_tm_threshold.setEnabled(tm_enabled and is_fuzzy)

    def _on_index_build_progress(self, percent):
        if percent >= self._next_progress_milestone:
            self.log(_("Building index: {percent}%...").format(percent=percent), "INFO")
            self._next_progress_milestone += 25

    def on_save_glossary_clicked(self):
        # 1. Collect selected terms
        entries_to_save = []
        for row in range(self.table_glossary.rowCount()):
            check_item = self.table_glossary.item(row, 0)
            if check_item and check_item.checkState() == Qt.Checked:
                src_item = self.table_glossary.item(row, 1)
                tgt_item = self.table_glossary.item(row, 2)
                if src_item and tgt_item:
                    src = src_item.text().strip()
                    tgt = tgt_item.text().strip()
                    ctx = src_item.data(Qt.UserRole) or ""
                    if src and tgt:
                        entries_to_save.append({'source': src, 'target': tgt, 'context': ctx})

        if not entries_to_save:
            QMessageBox.warning(self, _("Warning"), _("No terms selected to save."))
            return

        # 2. Show Generic Options Dialog
        opt_dialog = ResourceSaveOptionsDialog(self, resource_type='glossary', has_project=self.app.is_project_mode,
                                               count=len(entries_to_save))
        if not opt_dialog.exec():
            return

        options = opt_dialog.get_data()
        target_db = options['target_db']
        strategy = options['strategy']
        save_context = options.get('save_context', False)

        # 3. Determine DB Path
        db_path = self.app.glossary_service.project_db_path if target_db == 'project' else self.app.glossary_service.global_db_path
        if not db_path:
            QMessageBox.critical(self, _("Error"), _("Target database not available."))
            return

        source_lang = self.app.source_language
        target_lang = self.app.current_target_language if self.app.is_project_mode else self.app.target_language

        current_filename = "Unknown File"
        if self.app.is_project_mode:
            current_filename = self.app.get_current_active_filename()
        elif self.app.current_po_file_path:
            current_filename = os.path.basename(self.app.current_po_file_path)
        elif self.app.current_code_file_path:
            current_filename = os.path.basename(self.app.current_code_file_path)

        source_key = f"smart_extract::{current_filename}"
        display_name = f"{current_filename} (Smart Extract)"

        # 4. Check Conflicts
        src_terms = [e['source'] for e in entries_to_save]
        all_conflicts = self.app.glossary_service.find_conflicts(db_path, src_terms, source_lang, target_lang)

        real_conflicts = {}
        for entry in entries_to_save:
            src_key = entry['source'].strip().lower()
            new_target = entry['target'].strip()

            if src_key in all_conflicts:
                existing_targets = all_conflicts[src_key]['existing_targets']
                is_identical = any(t.strip() == new_target for t in existing_targets)

                if not is_identical:
                    real_conflicts[src_key] = all_conflicts[src_key]

        # 5. Resolve Conflicts
        resolutions = {}
        if strategy == 'manual' and real_conflicts:
            conflict_dialog = ResourceConflictDialog(self, real_conflicts, entries_to_save, resource_type='glossary')
            if not conflict_dialog.exec():
                return
            resolutions = conflict_dialog.resolutions

        # 6. Prepare Final List
        final_entries = []
        for entry in entries_to_save:
            src_key = entry['source'].strip().lower()
            action = 'new'
            term_id = None

            if src_key in real_conflicts:
                conflict_info = real_conflicts[src_key]
                term_id = conflict_info['id']
                if strategy == 'manual':
                    action = resolutions.get(src_key, 'skip')
                else:
                    action = strategy
            elif src_key in all_conflicts:
                conflict_info = all_conflicts[src_key]
                term_id = conflict_info['id']
                action = 'overwrite'

            final_entries.append({
                'source': entry['source'],
                'target': entry['target'],
                'comment': entry['context'] if save_context else "",
                'action': action,
                'term_id': term_id
            })

        # 7. Execute Save
        success, msg = self.app.glossary_service.batch_save_entries(
            db_path, final_entries, source_lang, target_lang, source_key
        )

        if success:
            saved_count = len([e for e in final_entries if e['action'] != 'skip'])
            glossary_dir = os.path.dirname(db_path)
            total_count = self.app.glossary_service.get_entry_count_by_source(glossary_dir, source_key)

            self.app.glossary_service.register_source_in_manifest(
                glossary_dir, source_key, display_name, total_count, source_lang, target_lang
            )

            QMessageBox.information(self, _("Success"), msg)
            self.app.glossary_analysis_cache.clear()
        else:
            QMessageBox.critical(self, _("Error"), msg)

    def open_test_lab(self):
        self._cache_glossary_from_ui()

        if self.chk_retrieval.isChecked() and self.retrieval_enabled:
            self._build_retrieval_index_async()

        dialog = TestTranslationDialog(self, self.app)
        dialog.exec()

    def check_plugins(self):
        """检查可用插件"""
        plugin = self.app.plugin_manager.get_plugin("com_theskyc_retrieval_enhancer")

        is_available = False
        if plugin:
            # Check if at least one backend is available
            backends = plugin.get_available_backends()
            if backends.get('tfidf') or backends.get('onnx'):
                is_available = True

        if is_available:
            self.retrieval_enabled = True
        else:
            self.retrieval_enabled = False

    # ==================== 阶段1：分析 ====================

    def start_analysis(self):
        """启动分析阶段"""
        # 1. 确定作用域
        self.target_items = self._determine_scope()

        if not self.target_items:
            QMessageBox.warning(
                self,
                _("Warning"),
                _("No items found in the selected scope.")
            )
            return

        # 2. 智能采样
        self.analysis_samples = SmartTranslationService.intelligent_sampling(
            self.target_items, 100
        )

        # 3. 如果都不需要分析，直接跳到预览页
        analyze_style = self.chk_analyze_style.isChecked()
        extract_terms = self.chk_extract_terms.isChecked()
        if not analyze_style and not extract_terms:
            self.stack.setCurrentIndex(1)
            return

        # 4. 启动分析线程
        self._start_analysis_thread()


    def _cache_glossary_from_ui(self):
        self._cached_glossary_dict = {}
        for row in range(self.table_glossary.rowCount()):
            check_item = self.table_glossary.item(row, 0)
            if check_item and check_item.checkState() == Qt.Checked:
                src_item = self.table_glossary.item(row, 1)
                tgt_item = self.table_glossary.item(row, 2)
                if src_item and tgt_item:
                    src = src_item.text().strip()
                    tgt = tgt_item.text().strip()
                    if src and tgt:
                        # 存入字典，key为原文
                        self._cached_glossary_dict[src] = tgt

        count = len(self._cached_glossary_dict)
        if count > 0:
            self.log(_("Indexed {count} glossary terms for context injection.").format(count=count), "INFO")

    def _determine_scope(self):
        """根据用户选择确定翻译作用域"""
        scope_idx = self.scope_combo.currentIndex()
        all_objs = self.app.translatable_objects

        if scope_idx == 0:  # 未翻译项
            return [ts for ts in all_objs if not ts.translation.strip() and not ts.is_ignored]
        elif scope_idx == 1:  # 所有项
            return [ts for ts in all_objs if not ts.is_ignored]
        elif scope_idx == 2:  # 选中项
            return self.app._get_selected_ts_objects_from_sheet()

        return []

    def _capture_context_config(self):
        """Capture all necessary UI states for context generation."""
        return {
            "temperature": self.temp_spinbox.value(),
            "use_neighbors": self.chk_neighbors.isChecked(),
            "neighbors_count": self.spin_neighbors.value(),
            "use_retrieval": self.chk_retrieval.isChecked() and self.retrieval_enabled,
            "retrieval_mode": self.combo_retrieval_mode.currentData(),
            "retrieval_limit": self.spin_retrieval.value(),
            "use_tm": self.chk_use_tm.isChecked(),
            "tm_mode": "fuzzy" if self.rb_tm_fuzzy.isChecked() else "exact",
            "tm_threshold": self.spin_tm_threshold.value(),
            "tm_limit": self.spin_retrieval.value(),
            "use_glossary_db": self.chk_use_glossary_db.isChecked(),
            "style_guide_text": self.edit_style.toPlainText(),
            "cached_glossary": self._cached_glossary_dict.copy()
        }

    def _generate_local_neighbor_context(self, current_ts_id, config=None):
        contexts = {"translation_context": "", "original_context": ""}

        if config is None:
            use_neighbors = self.chk_neighbors.isChecked()
            max_neighbors = self.spin_neighbors.value()
        else:
            use_neighbors = config["use_neighbors"]
            max_neighbors = config["neighbors_count"]

        if not use_neighbors:
            return contexts

        try:
            # Find index
            all_objs = self.app.translatable_objects
            current_idx = -1
            for i, ts in enumerate(all_objs):
                if ts.id == current_ts_id:
                    current_idx = i
                    break

            if current_idx == -1:
                return contexts

            # 1. Untranslated Context (Originals)
            context_items = []
            # Preceding
            count = 0
            for i in range(current_idx - 1, -1, -1):
                if count >= max_neighbors: break
                ts = all_objs[i]
                if not ts.is_ignored:
                    context_items.insert(0, ts.original_semantic)
                    count += 1
            # Succeeding
            count = 0
            for i in range(current_idx + 1, len(all_objs)):
                if count >= max_neighbors: break
                ts = all_objs[i]
                if not ts.is_ignored:
                    context_items.append(ts.original_semantic)
                    count += 1

            if context_items:
                formatted_items = [f"- \"{item.replace(chr(10), ' ').strip()}\"" for item in context_items]
                contexts["original_context"] = "\n".join(formatted_items)

            # 2. Translated Context
            context_pairs = []
            # Preceding
            count = 0
            for i in range(current_idx - 1, -1, -1):
                if count >= max_neighbors: break
                ts = all_objs[i]
                if ts.translation.strip() and not ts.is_ignored:
                    context_pairs.insert(0, (ts.original_semantic, ts.get_translation_for_ui()))
                    count += 1
            # Succeeding
            count = 0
            for i in range(current_idx + 1, len(all_objs)):
                if count >= max_neighbors: break
                ts = all_objs[i]
                if ts.translation.strip() and not ts.is_ignored:
                    context_pairs.append((ts.original_semantic, ts.get_translation_for_ui()))
                    count += 1

            if context_pairs:
                header = f"| {_('Original')} | {_('Translation')} |\n|---|---|\n"
                rows = [
                    f"| {orig.replace('|', '\\|').replace(chr(10), ' ')} | {trans.replace('|', '\\|').replace(chr(10), ' ')} |"
                    for orig, trans in context_pairs]
                contexts["translation_context"] = header + "\n".join(rows)

        except Exception as e:
            logger.error(f"Error generating local neighbor context: {e}")

        return contexts

    def _start_analysis_thread(self):
        """启动分析工作线程"""
        # 防止重复启动
        if self.analysis_thread:
            try:
                if self.analysis_thread.isRunning():
                    QMessageBox.warning(self, _("Warning"), _("Analysis is already running. Please wait or stop it first."))
                    return
            except RuntimeError:
                self.analysis_thread = None

        analyze_style = self.chk_analyze_style.isChecked()
        extract_terms = self.chk_extract_terms.isChecked()
        if not analyze_style and not extract_terms:
            self.stack.setCurrentIndex(1)
            return

        self.stack.setCurrentIndex(2)
        self.lbl_status.setText(_("Phase 1/2: Analyzing Content..."))
        self.progress_bar.setRange(0, 0)

        # Get thread count from UI
        max_threads = self.thread_spinbox.value()

        self.analysis_thread = QThread()
        self.analysis_worker = AnalysisWorker(
            self.app,
            self.analysis_samples,
            self.target_items,
            self.app.source_language,
            self._get_target_language(),
            self.term_mode_combo.currentData(),
            max_threads=max_threads,
            use_context=self.chk_term_context.isChecked(),
            batch_size=self.batch_size_spinbox.value(),
            orphan_ratio=self.orphan_ratio_spinbox.value(),
            inject_glossary=self.chk_inject_glossary.isChecked(),
            do_style_analysis=analyze_style,
            do_term_extraction=extract_terms
        )
        self.analysis_worker.moveToThread(self.analysis_thread)

        self.analysis_thread.started.connect(self.analysis_worker.run)
        self.analysis_worker.progress.connect(self._on_analysis_progress)
        self.analysis_worker.finished.connect(self._on_analysis_finished)
        self.analysis_worker.error.connect(self._on_analysis_error)

        self.analysis_worker.finished.connect(self.analysis_thread.quit)
        self.analysis_worker.error.connect(self.analysis_thread.quit)
        self.analysis_thread.finished.connect(self._cleanup_analysis_thread)
        self.analysis_thread.finished.connect(self.analysis_thread.deleteLater)

        self.analysis_thread.start()

    def _cleanup_analysis_thread(self):
        """清理分析线程引用"""
        self.analysis_thread = None
        self.analysis_worker = None

    def _get_target_language(self):
        """获取目标语言"""
        if self.app.is_project_mode:
            return self.app.current_target_language
        return self.app.target_language

    def _on_analysis_progress(self, message):
        """分析进度回调"""
        self.log(message, "INFO")

    def _on_analysis_finished(self, style, glossary, recommended_temp, terms_data):
        """分析完成回调"""
        self.log(_("Analysis completed successfully"), "SUCCESS")

        self.style_guide = style
        self.glossary_content = glossary

        # 更新预览页面
        self.edit_style.setPlainText(style)
        self._populate_glossary_table(glossary, terms_data)

        # 设置温度值
        self.temp_spinbox.setValue(recommended_temp)
        self.log(_("AI recommended temperature: {temp}").format(temp=recommended_temp), "INFO")

        # 切换到预览页
        self.stack.setCurrentIndex(1)

    def _on_analysis_error(self, error_msg):
        """分析错误回调"""
        self.log(_("Analysis failed: {error}").format(error=error_msg), "ERROR")
        QMessageBox.critical(
            self,
            _("Error"),
            _("Analysis failed:\n") + error_msg
        )
        self.stack.setCurrentIndex(0)

    def _populate_glossary_table(self, markdown_text, terms_data=None):
        """从Markdown文本填充术语表"""
        logger.info(f"Populating glossary table. Markdown length: {len(markdown_text)}")
        self.table_glossary.setSortingEnabled(False)
        self.table_glossary.setRowCount(0)

        # 构建上下文映射表 {term: context}
        context_map = {}
        if terms_data:
            for item in terms_data:
                if isinstance(item, dict):
                    context_map[item.get('term')] = item.get('context', '')

        if not markdown_text or not markdown_text.strip():
            self.table_glossary.setSortingEnabled(True)
            return

        lines = markdown_text.strip().split('\n')
        parsed_entries = []
        for line in lines:
            # 跳过分隔线和空行
            if not line.strip() or '---' in line or '===' in line:
                continue

            # 解析表格行
            parts = [p.strip() for p in line.split('|') if p.strip()]

            if len(parts) < 2:
                continue

            source_text = parts[0]
            target_text = parts[1] if len(parts) > 1 else ""

            # 跳过表头
            if self._is_table_header(source_text, target_text):
                continue

            # 收集数据
            context = context_map.get(source_text, "")
            parsed_entries.append((source_text, target_text, context))

        logger.info(f"Parsed {len(parsed_entries)} entries.")

        # 排序
        parsed_entries.sort(key=lambda x: x[0].lower())

        # 添加行
        for src, tgt, ctx in parsed_entries:
            self._add_glossary_row(src, tgt, ctx)
        logger.info(f"Table row count after population: {self.table_glossary.rowCount()}")

        self.table_glossary.setSortingEnabled(True)

    def _is_table_header(self, source, target):
        """判断是否为表头"""
        source_lower = source.lower()
        target_lower = target.lower()

        header_keywords = ['source', 'term', 'original', 'target', 'translation']

        return source_lower in header_keywords and target_lower in header_keywords

    def _add_glossary_row(self, source, target, context=""):
        """添加术语表行"""
        row = self.table_glossary.rowCount()
        self.table_glossary.insertRow(row)

        # 列0: 复选框
        check_item = QTableWidgetItem()
        check_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        check_item.setCheckState(Qt.Checked)
        self.table_glossary.setItem(row, 0, check_item)

        # 列1: 源文本 (存储 Context 到 UserRole)
        src_item = QTableWidgetItem(source)
        # 存储上下文数据
        if context:
            src_item.setData(Qt.UserRole, context)

        self.table_glossary.setItem(row, 1, src_item)

        # 列2: 目标文本
        self.table_glossary.setItem(row, 2, QTableWidgetItem(target))

    def _get_glossary_string_from_table(self):
        """从表格获取术语表字符串"""
        lines = []

        for row in range(self.table_glossary.rowCount()):
            check_item = self.table_glossary.item(row, 0)

            # 只包含勾选的项
            if check_item and check_item.checkState() == Qt.Checked:
                src_item = self.table_glossary.item(row, 1)
                tgt_item = self.table_glossary.item(row, 2)

                if src_item and tgt_item:
                    src = src_item.text().strip()
                    tgt = tgt_item.text().strip()

                    if src and tgt:
                        lines.append(f"- {src}: {tgt}")

        if not lines:
            return _("No glossary terms provided.")

        return "\n".join(lines)

    # ==================== 阶段2：翻译 ====================

    def start_interactive_review(self):
        # 预处理术语表
        self._cache_glossary_from_ui()

        # 检查 AI
        if not self.app._check_ai_prerequisites():
            return

        # 构建索引
        if self.chk_retrieval.isChecked() and self.retrieval_enabled:
            self._build_retrieval_index_async()

        # 捕获配置快照 (包含最新的 Style Guide 和 Glossary)
        config_snapshot = self._capture_context_config()

        # 创建 Context Provider
        context_provider = lambda ts_id: self.app._generate_universal_context(ts_id, config_snapshot)

        # 启动对话框
        if not self.target_items:
            QMessageBox.warning(self, _("Warning"), _("No items to review."))
            return

        dialog = InteractiveReviewDialog(self, self.app, self.target_items, context_provider, config_snapshot)
        dialog.exec()

        # 6. 刷新主界面
        self.app.refresh_sheet_preserve_selection()
        self.app.update_counts_display()

    def start_translation(self):
        """启动翻译阶段"""
        # 预处理术语表
        self._cache_glossary_from_ui()

        # 切换UI到监控模式
        self._switch_to_translation_mode()

        # 检查是否需要构建索引
        if self.chk_retrieval.isChecked() and self.retrieval_enabled:
            self.lbl_status.setText(_("Phase 2a: Building Knowledge Base..."))
            self.progress_bar.setRange(0, 0)  # 忙碌状态

            # 准备知识库数据
            knowledge_base = []
            for ts in self.app.translatable_objects:
                if ts.translation.strip() and not ts.is_ignored:
                    knowledge_base.append({
                        'source': ts.original_semantic,
                        'target': ts.translation
                    })

            if knowledge_base:
                self.log(_("Building retrieval index with {count} items...").format(count=len(knowledge_base)), "INFO")
                self._next_progress_milestone = 25
                # 启动索引构建线程
                self.index_thread = QThread()
                self.index_worker = IndexBuildWorker(self.app, knowledge_base)
                self.index_worker.moveToThread(self.index_thread)

                self.index_thread.started.connect(self.index_worker.run)
                self.index_worker.progress.connect(self._on_index_build_progress)
                self.index_worker.finished.connect(self.index_thread.quit)
                self.index_worker.finished.connect(self._on_index_build_complete)
                self.index_thread.finished.connect(self.index_thread.deleteLater)
                self.index_worker.finished.connect(self.index_worker.deleteLater)

                self.index_thread.start()
                return

            else:
                self.log(_("No translated items found for index. Skipping RAG."), "WARNING")

        self._execute_batch_translation()

    def _switch_to_translation_mode(self):
        """切换UI到翻译模式"""
        self.stack.setCurrentIndex(2)
        self.lbl_status.setText(_("Phase 2/2: Translating..."))
        self.progress_bar.setRange(0, len(self.target_items))
        self.progress_bar.setValue(0)
        self.btn_stop.setText(_("Stop"))
        self.btn_stop.setEnabled(True)
        self.log_view.clear()

    def _build_retrieval_index_async(self):
        # 准备数据
        knowledge_base = []
        for ts in self.app.translatable_objects:
            if ts.translation.strip() and not ts.is_ignored:
                knowledge_base.append({
                    'source': ts.original_semantic,
                    'target': ts.translation
                })

        if not knowledge_base:
            return

        self.log(_("Background: Updating retrieval index with {count} items...").format(count=len(knowledge_base)),
                 "INFO")

        # 启动后台线程
        self._bg_thread = QThread()
        self._bg_worker = IndexBuildWorker(self.app, knowledge_base)
        self._bg_worker.moveToThread(self._bg_thread)

        self._bg_thread.started.connect(self._bg_worker.run)
        self._bg_worker.finished.connect(self._bg_thread.quit)
        self._bg_worker.finished.connect(self._bg_worker.deleteLater)
        self._bg_thread.finished.connect(self._bg_thread.deleteLater)

        self._bg_worker.finished.connect(lambda: self.log(_("Background index update complete."), "INFO"))

        self._bg_thread.start()

    def _on_index_build_complete(self):
        """索引构建完成的回调"""
        self.log("✓ Knowledge base ready.", "SUCCESS")
        self._execute_batch_translation()

    def _execute_batch_translation(self):
        """执行实际的批量翻译逻辑 (原 start_translation 的后半部分)"""
        self.lbl_status.setText(_("Phase 2b: Translating..."))
        self.progress_bar.setRange(0, len(self.target_items))
        self.progress_bar.setValue(0)

        # 连接AI管理器信号
        self._connect_ai_manager_signals()

        current_temp = self.temp_spinbox.value()
        concurrency = self.thread_spinbox.value()
        repair_limit = self.repair_spinbox.value()
        timeout = self.timeout_spinbox.value()

        config_snapshot = self._capture_context_config()
        context_provider = lambda ts_id: self.app._generate_universal_context(ts_id, config_snapshot)

        # 开始批量翻译
        self.app.ai_manager.start_batch(
            self.target_items,
            context_provider,
            concurrency_override=concurrency,
            temperature=current_temp,
            self_repair_limit=repair_limit,
            api_timeout=timeout
        )

    def _connect_ai_manager_signals(self):
        """连接AI管理器信号"""
        if self._signals_connected:
            return

        self.app.ai_manager.batch_progress.connect(self.on_batch_progress)
        self.app.ai_manager.item_result.connect(self.on_item_result)
        self.app.ai_manager.batch_finished.connect(self.on_batch_finished)
        self.app.ai_manager.worker_log.connect(self.on_worker_log)
        self._signals_connected = True

    def on_worker_log(self, message, level):
        self.log(message, level)

    def _disconnect_ai_manager_signals(self):
        """断开AI管理器信号"""
        if not self._signals_connected:
            return

        try:
            self.app.ai_manager.batch_progress.disconnect(self.on_batch_progress)
            self.app.ai_manager.item_result.disconnect(self.on_item_result)
            self.app.ai_manager.batch_finished.disconnect(self.on_batch_finished)
        except (RuntimeError, TypeError):
            pass
        finally:
            self._signals_connected = False

    def on_batch_progress(self, current, total):
        """批量翻译进度回调"""
        self.progress_bar.setValue(current)
        self.lbl_status.setText(f"Translating {current}/{total}...")

    def on_item_result(self, ts_id, text, error, op_type):
        """单项翻译结果回调"""
        ts_obj = self.app._find_ts_obj_by_id(ts_id)
        if not ts_obj:
            return

        preview = ts_obj.original_semantic[:30]

        if error:
            self.log(_("✗ Failed: {preview}... - {error}").format(preview=preview, error=error), "ERROR")
        else:
            self.log(_("✓ Translated: {preview}...").format(preview=preview), "SUCCESS")

    def on_batch_finished(self, results, completed, total):
        """批量翻译完成回调"""
        self.lbl_status.setText(_("Translation Complete!"))
        self.btn_stop.setText(_("Close"))

        # 断开停止按钮的原有连接
        try:
            self.btn_stop.clicked.disconnect()
        except:
            pass

        self.btn_stop.clicked.connect(self.accept)

        # 断开AI管理器信号
        self._disconnect_ai_manager_signals()

        # 显示统计信息
        success_rate = (completed / total * 100) if total > 0 else 0
        self.log(
            f"✓ Completed: {completed}/{total} ({success_rate:.1f}%)",
            "SUCCESS"
        )

    def stop_translation(self):
        """停止操作 (分析、翻译)"""
        self.log("Stopping operation...", "WARNING")

        # 停止翻译阶段 (Phase 2)
        if self.app.ai_manager.is_running:
            self.app.ai_manager.stop()
            self.log("Translation task manager stopped.", "INFO")

        # 停止分析阶段 (Phase 1)
        if hasattr(self, 'analysis_worker') and self.analysis_worker:
            self.analysis_worker.cancel()
            self.log("Analysis worker cancellation requested.", "INFO")

        # 强制终止分析线程
        if hasattr(self, 'analysis_thread') and self.analysis_thread and self.analysis_thread.isRunning():
            self.analysis_thread.requestInterruption()
            self.analysis_thread.quit()
            self.analysis_thread.wait(500)
            if self.analysis_thread.isRunning():
                self.log("Force terminating analysis thread...", "WARNING")
                self.analysis_thread.terminate()
                self.analysis_thread.wait()
            self.analysis_thread = None
            self.analysis_worker = None

        if hasattr(self, 'index_worker') and self.index_worker:
            self.index_worker.cancel()
            self.log("Index build cancellation requested.", "INFO")

        # 更新 UI 状态
        self.lbl_status.setText(_("Operation Stopped"))
        self.progress_bar.setValue(0)
        self.btn_stop.setEnabled(False)

        # 允许用户返回配置页重试
        self.btn_stop.setText(_("Close"))
        try:
            self.btn_stop.clicked.disconnect()
        except:
            pass
        self.btn_stop.clicked.connect(self.accept)

        self.btn_stop.setEnabled(True)


    def log(self, message, level="INFO"):
        """
        添加日志到视图

        Args:
            message: 日志消息
            level: 日志级别 (INFO/SUCCESS/ERROR/WARNING)
        """
        color_map = {
            "INFO": "#D4D4D4",
            "SUCCESS": "#4CAF50",
            "ERROR": "#F44336",
            "WARNING": "#FFC107"
        }

        display_map = {
            "INFO": _("INFO"),
            "SUCCESS": _("SUCCESS"),
            "ERROR": _("ERROR"),
            "WARNING": _("WARNING")
        }

        display_level = display_map.get(level, level)
        color = color_map.get(level, "#D4D4D4")
        html = f'<span style="color: {color}">[{display_level}] {message}</span>'
        self.log_view.append(html)


    def closeEvent(self, event):
        """对话框关闭事件"""
        # 取消正在运行的分析
        if self.analysis_worker:
            self.analysis_worker.cancel()

        # 断开信号
        self._disconnect_ai_manager_signals()

        super().closeEvent(event)