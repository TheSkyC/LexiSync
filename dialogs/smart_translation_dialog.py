# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QProgressBar, QStackedWidget, QWidget,
    QGroupBox, QCheckBox, QSpinBox, QComboBox, QMessageBox, QSplitter,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QDoubleSpinBox
)
from PySide6.QtCore import Qt, QThread, Signal, QObject
from utils.localization import _
from services.smart_translation_service import SmartTranslationService
from services.ai_worker import AIWorker
from utils.enums import AIOperationType
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
import json
import uuid
import threading
import logging

logger = logging.getLogger(__name__)


class AnalysisWorker(QObject):
    """Phase 1 分析工作线程"""
    progress = Signal(str)
    finished = Signal(str, str, float)  # style_guide, glossary_md, recommended_temp
    error = Signal(str)

    def __init__(self, app, samples, all_items, source_lang, target_lang, term_mode="fast", max_threads=1):
        super().__init__()
        self.app = app
        self.samples = samples
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.all_items = all_items
        self.term_mode = term_mode
        self.max_threads = max_threads
        self._is_cancelled = False

    def run(self):
        """执行分析任务"""
        try:
            translator = self.app.ai_translator

            # 步骤1: 风格分析
            if self._is_cancelled:
                return

            self.progress.emit(_("Analyzing style and tone..."))
            raw_style_guide = self._analyze_style(translator)
            clean_style_guide, rec_temp = self._parse_and_strip_temperature(raw_style_guide)

            # 步骤2: 术语提取
            if self._is_cancelled:
                return

            self.progress.emit(_("Extracting key terminology..."))
            terms_list = self._extract_terms(translator)

            # 步骤3: 术语翻译
            if self._is_cancelled:
                return

            glossary_md = ""

            if self.term_mode == "fast":
                self.progress.emit(_("Running frequency analysis (Fast Mode)..."))
                candidates = SmartTranslationService.extract_terms_frequency_based(self.all_items, 100)
                candidates_str = ", ".join(candidates)

                self.progress.emit(_("AI filtering and translating terms..."))
                prompt = SmartTranslationService.filter_and_translate_terms_prompt(candidates_str, self.target_lang)
                glossary_md = translator.translate("Filter and translate.", prompt)

            elif self.term_mode == "deep":
                self.progress.emit(f"Translating {len(terms_list)} unique terms...")
                glossary_md = self._translate_terms(translator, terms_list)

            self.finished.emit(clean_style_guide, glossary_md, rec_temp)

        except Exception as e:
            logger.error(f"Analysis failed: {e}", exc_info=True)
            self.error.emit(str(e))

    def _parse_and_strip_temperature(self, text):
        """从风格指南中提取温度并将其从文本中移除"""
        import re
        rec_temp = 0.3  # 默认回退值

        pattern = r'[\-\*]*\s*(\*\*)?Recommended Temperature(\*\*)?:\s*([0-9.]+).*?(\n|$)'

        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                val = float(match.group(3))
                rec_temp = max(0.1, min(1.0, val))
                text = text.replace(match.group(0), "")
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

    def _extract_terms(self, translator):
        """提取关键术语"""

        if self.term_mode == "deep":
            self.progress.emit(_("Starting Deep Scan (Parallel Threads: {n})...").format(n=self.max_threads))
            all_terms = set()
            batch_size = 50
            batches = [self.all_items[i:i + batch_size] for i in range(0, len(self.all_items), batch_size)]
            total_batches = len(batches)
            completed_batches = 0
            lock = threading.Lock()

            def process_batch(batch_items):
                if self._is_cancelled: return []
                batch_text = "\n".join([t.original_semantic for t in batch_items])
                prompt = SmartTranslationService.extract_terms_batch_prompt(batch_text)
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
                        executor.shutdown(wait=False, cancel_futures=True)
                        return []

                    result_terms = future.result()
                    with lock:
                        all_terms.update(result_terms)
                        completed_batches += 1
                        self.progress.emit(f"Deep Scan: Batch {completed_batches}/{total_batches}...")
            return list(all_terms)

        else:
            term_prompt = SmartTranslationService.extract_terms_prompt(self.samples)
            terms_json_str = translator.translate("Extract terms.", term_prompt)
            is_valid, result = SmartTranslationService.validate_terms_json(terms_json_str)
            if not is_valid:
                return []
            return result

    def _translate_terms(self, translator, terms_list):
        """翻译术语列表"""
        if not terms_list:
            return "| Source | Target |\n|--------|--------|\n"

        BATCH_SIZE = 50
        batches = [terms_list[i:i + BATCH_SIZE] for i in range(0, len(terms_list), BATCH_SIZE)]
        total_batches = len(batches)
        self.progress.emit(_("Translating terms in {t} batches (Threads: {n})...").format(
            t=total_batches, n=self.max_threads))

        results = ["| Source | Target |\n|--------|--------|"]
        completed_batches = 0
        lock = threading.Lock()

        def process_batch(batch_items):
            if self._is_cancelled: return ""
            try:
                terms_json = json.dumps(batch_items, ensure_ascii=False)
                translate_prompt = SmartTranslationService.translate_terms_prompt(
                    terms_json, self.target_lang
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
        self.resize(900, 700)
        self.setModal(False)

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

        # 作用域选择
        layout.addWidget(self._create_scope_group())

        # 策略选择
        layout.addWidget(self._create_strategy_group())

        layout.addStretch()

        # 底部按钮
        btn_layout = QHBoxLayout()
        btn_analyze = QPushButton(_("Analyze & Preview"))
        btn_analyze.clicked.connect(self.start_analysis)
        btn_analyze.setStyleSheet("font-weight: bold; padding: 8px;")
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
            _("Selected Items Only")
        ])
        scope_layout.addWidget(self.scope_combo)

        return scope_group

    def _create_strategy_group(self):
        """创建策略选择组"""
        strat_group = QGroupBox(_("Strategy"))
        strat_layout = QVBoxLayout(strat_group)

        # Term Extraction Mode
        term_layout = QHBoxLayout()
        term_layout.addWidget(QLabel(_("Term Extraction:")))
        self.term_mode_combo = QComboBox()
        self.term_mode_combo.addItem(_("Fast (Frequency-based)"), "fast")
        self.term_mode_combo.addItem(_("Deep (AI-Scan All)"), "deep")
        self.term_mode_combo.setToolTip(
            _("Fast: Scans high-frequency words locally, then AI filters them. Cheap & Fast.\n"
              "Deep: AI reads ALL texts to find terms. Expensive & Slow but thorough.")
        )
        term_layout.addWidget(self.term_mode_combo)
        strat_layout.addLayout(term_layout)

        # Concurrency Setting
        thread_layout = QHBoxLayout()
        thread_layout.addWidget(QLabel(_("Concurrency (Threads):")))
        self.thread_spinbox = QSpinBox()
        self.thread_spinbox.setRange(1, 16)
        default_threads = self.app.config.get("ai_max_concurrent_requests", 3)
        self.thread_spinbox.setValue(default_threads)
        self.thread_spinbox.setToolTip(_("Number of parallel AI requests for Deep Scan and Translation Phase."))
        thread_layout.addWidget(self.thread_spinbox)
        thread_layout.addStretch()
        strat_layout.addLayout(thread_layout)

        # Existing Checkboxes
        self.chk_analyze = QCheckBox(_("Auto-analyze Style & Terminology"))
        self.chk_analyze.setChecked(True)
        strat_layout.addWidget(self.chk_analyze)

        self.chk_retrieval = QCheckBox(_("Use Semantic Context Retrieval"))
        self.chk_retrieval.setChecked(True)
        strat_layout.addWidget(self.chk_retrieval)

        self.retrieval_info = QLabel(_("Context Source: Basic Fuzzy Match (Plugin not found)"))
        self.retrieval_info.setStyleSheet("color: gray; margin-left: 20px;")
        strat_layout.addWidget(self.retrieval_info)

        return strat_group

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
        btn_layout = QHBoxLayout()
        btn_back = QPushButton(_("Back"))
        btn_back.clicked.connect(lambda: self.stack.setCurrentIndex(0))

        btn_start = QPushButton(_("Start Translation"))
        btn_start.clicked.connect(self.start_translation)
        btn_start.setStyleSheet(
            "background-color: #4CAF50; color: white; "
            "font-weight: bold; padding: 8px;"
        )

        btn_layout.addWidget(btn_back)
        btn_layout.addStretch()
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
        layout.setContentsMargins(5, 0, 0, 0)
        layout.addWidget(QLabel(_("Extracted Glossary:")))

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

        self.btn_stop = QPushButton(_("Stop"))
        self.btn_stop.clicked.connect(self.stop_translation)
        layout.addWidget(self.btn_stop)

        return page

    def check_plugins(self):
        """检查可用插件"""
        plugin = self.app.plugin_manager.get_plugin("com_theskyc_retrieval_enhancer")
        if plugin and plugin.is_ready:
            self.retrieval_enabled = True
            self.retrieval_info.setText(
                _("Context Source: TF-IDF Semantic Retrieval (Plugin Active)")
            )
            self.retrieval_info.setStyleSheet("color: green; margin-left: 20px;")
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

        # 3. 如果不需要分析，直接跳到预览页
        if not self.chk_analyze.isChecked():
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
            self.log(f"Indexed {count} glossary terms for context injection.", "INFO")

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

    def _start_analysis_thread(self):
        """启动分析工作线程"""
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
            max_threads=max_threads
        )
        self.analysis_worker.moveToThread(self.analysis_thread)

        self.analysis_thread.started.connect(self.analysis_worker.run)
        self.analysis_worker.progress.connect(self._on_analysis_progress)
        self.analysis_worker.finished.connect(self._on_analysis_finished)
        self.analysis_worker.error.connect(self._on_analysis_error)

        self.analysis_worker.finished.connect(self.analysis_thread.quit)
        self.analysis_worker.error.connect(self.analysis_thread.quit)
        self.analysis_thread.finished.connect(self.analysis_thread.deleteLater)

        self.analysis_thread.start()

    def _get_target_language(self):
        """获取目标语言"""
        if self.app.is_project_mode:
            return self.app.current_target_language
        return self.app.target_language

    def _on_analysis_progress(self, message):
        """分析进度回调"""
        self.log(message, "INFO")

    def _on_analysis_finished(self, style, glossary, recommended_temp):
        """分析完成回调"""
        self.log(_("Analysis completed successfully"), "SUCCESS")

        self.style_guide = style
        self.glossary_content = glossary

        # 更新预览页面
        self.edit_style.setPlainText(style)
        self._populate_glossary_table(glossary)

        # 设置温度值
        self.temp_spinbox.setValue(recommended_temp)
        self.log(f"AI recommended temperature: {recommended_temp}", "INFO")

        # 切换到预览页
        self.stack.setCurrentIndex(1)

    def _on_analysis_error(self, error_msg):
        """分析错误回调"""
        self.log(f"Analysis failed: {error_msg}", "ERROR")
        QMessageBox.critical(
            self,
            _("Error"),
            _("Analysis failed:\n") + error_msg
        )
        self.stack.setCurrentIndex(0)

    def _populate_glossary_table(self, markdown_text):
        """从Markdown文本填充术语表"""
        self.table_glossary.setSortingEnabled(False)
        self.table_glossary.setRowCount(0)

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
            parsed_entries.append((source_text, target_text))

        # 按原文进行 A-Z 排序
        parsed_entries.sort(key=lambda x: x[0].lower())

        # 添加行
        for src, tgt in parsed_entries:
            self._add_glossary_row(src, tgt)

        # 恢复排序功能
        self.table_glossary.setSortingEnabled(True)

    def _is_table_header(self, source, target):
        """判断是否为表头"""
        source_lower = source.lower()
        target_lower = target.lower()

        header_keywords = ['source', 'term', 'original', 'target', 'translation']

        return source_lower in header_keywords and target_lower in header_keywords

    def _add_glossary_row(self, source, target):
        """添加术语表行"""
        row = self.table_glossary.rowCount()
        self.table_glossary.insertRow(row)

        # 列0: 复选框
        check_item = QTableWidgetItem()
        check_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        check_item.setCheckState(Qt.Checked)
        self.table_glossary.setItem(row, 0, check_item)

        # 列1: 源文本
        self.table_glossary.setItem(row, 1, QTableWidgetItem(source))

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

    def start_translation(self):
        """启动翻译阶段"""
        # 预处理术语表
        self._cache_glossary_from_ui()

        # 切换UI状态
        self._switch_to_translation_mode()

        # 异步构建检索索引
        if self.chk_retrieval.isChecked() and self.retrieval_enabled:
            self._build_retrieval_index_async()

        # 注入智能提示词结构
        self._inject_smart_prompt_structure()

        # 连接AI管理器信号
        self._connect_ai_manager_signals()
        current_temp = self.temp_spinbox.value()
        concurrency = self.thread_spinbox.value()

        # 开始批量翻译
        self.app.ai_manager.start_batch(
            self.target_items,
            self.custom_context_provider,
            concurrency_override=concurrency,
            temperature=current_temp
        )

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
        """异步构建检索索引"""

        def build_task():
            try:
                self.log("Building semantic index...", "INFO")

                knowledge_base = []
                for ts in self.app.translatable_objects:
                    if ts.translation.strip() and not ts.is_ignored:
                        knowledge_base.append({
                            'source': ts.original_semantic,
                            'target': ts.translation
                        })

                self.app.plugin_manager.run_hook('build_retrieval_index', knowledge_base)
                self.log(f"✓ Index built with {len(knowledge_base)} items.", "SUCCESS")

            except Exception as e:
                self.log(f"⚠ Index build failed: {str(e)}", "WARNING")
                logger.error(f"Retrieval index build error: {e}", exc_info=True)

        # 在后台线程执行
        threading.Thread(target=build_task, daemon=True).start()

    def _inject_smart_prompt_structure(self):
        """注入智能翻译专用提示词结构"""
        # 保存原始配置
        self._original_prompt_structure = deepcopy(
            self.app.config.get("ai_prompt_structure")
        )

        # 创建智能提示词结构
        smart_structure = self._create_smart_prompt_structure()

        # 覆盖全局配置
        self.app.config["ai_prompt_structure"] = smart_structure

    def _create_smart_prompt_structure(self):
        """创建智能提示词结构"""
        src_lang = self.app.source_language
        tgt_lang = self._get_target_language()

        return [
            {
                "id": str(uuid.uuid4()),
                "type": "Structural Content",
                "enabled": True,
                "content": (
                    f"You are a professional localization expert translating UI text from {src_lang} to {tgt_lang}. These texts are from standard PO/POT localization files."
                )
            },
            {
                "id": str(uuid.uuid4()),
                "type": "Structural Content",
                "enabled": True,
                "content": (
                    "CRITICAL: Preserve ALL placeholders exactly as-is:\n"
                    "- Format specifiers: %s, %d, %f, %.2f, etc.\n"
                    "- Named placeholders: {variable}, %{count}, {{name}}\n"
                    "- Template syntax: ${var}, [[key]], <placeholder>\n"
                    "The quantity, order, and names must match the original perfectly."
                )
            },
            {
                "id": str(uuid.uuid4()),
                "type": "Structural Content",
                "enabled": True,
                "content": (
                    "CRITICAL: Preserve ALL formatting exactly:\n"
                    "- Escape sequences: \\n, \\t, \\r, \\\"\n"
                    "- HTML tags: <br>, <b>, <i>, <span>, <a>, etc.\n"
                    "- Do NOT convert between \\n and <br>\n"
                    "- Match the original format character-by-character"
                )
            },
            {
                "id": str(uuid.uuid4()),
                "type": "Structural Content",
                "enabled": True,
                "content": (
                    "Do not add or remove any characters, symbols, or spaces not present in the original text, unless required by the target language's punctuation conventions."
                )
            },
            {
                "id": str(uuid.uuid4()),
                "type": "Dynamic Instruction",
                "enabled": True,
                "content": "### Translation Style Guide\n[Style Guide]"
            },
            {
                "id": str(uuid.uuid4()),
                "type": "Dynamic Instruction",
                "enabled": True,
                "content": "### Terminology Glossary\n[Glossary]"
            },
            {
                "id": str(uuid.uuid4()),
                "type": "Dynamic Instruction",
                "enabled": True,
                "content": (
                    "### Reference Context\n"
                    "[Semantic Context]\n"
                    "[Untranslated Context]\n"
                    "[Translated Context]"
                )
            },
            {
                "id": str(uuid.uuid4()),
                "type": "Static Instruction",
                "enabled": True,
                "content": "Output ONLY the final translation. No explanations, no notes."
            }
        ]

    def _connect_ai_manager_signals(self):
        """连接AI管理器信号"""
        if self._signals_connected:
            return

        self.app.ai_manager.batch_progress.connect(self.on_batch_progress)
        self.app.ai_manager.item_result.connect(self.on_item_result)
        self.app.ai_manager.batch_finished.connect(self.on_batch_finished)
        self._signals_connected = True

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


    def custom_context_provider(self, ts_id):
        try:
            # 1. 获取基础上下文（邻近项）
            base_context = self.app._generate_ai_context_strings(ts_id)

            # 2. 获取语义上下文（RAG检索）
            semantic_context = ""
            if self.chk_retrieval.isChecked() and self.retrieval_enabled:
                semantic_context = self._get_semantic_context(ts_id)

            # 3. 获取术语表
            relevant_glossary = ""
            ts_obj = self.app._find_ts_obj_by_id(ts_id)
            if ts_obj and self._cached_glossary_dict:
                original_text = ts_obj.original_semantic
                matched_terms = []
                for term_src, term_tgt in self._cached_glossary_dict.items():
                    if term_src.lower() in original_text.lower():
                        matched_terms.append(f"- {term_src}: {term_tgt}")

                if matched_terms:
                    relevant_glossary = "\n".join(matched_terms)

            # 3. 组合所有上下文
            return {
                "original_context": base_context.get("original_context", ""),
                "translation_context": base_context.get("translation_context", ""),
                "[Style Guide]": self.edit_style.toPlainText(),
                "[Glossary]": relevant_glossary,
                "[Semantic Context]": semantic_context
            }

        except Exception as e:
            logger.error(f"Error in context provider for {ts_id}: {e}", exc_info=True)

            # 返回最小上下文，确保不阻塞翻译流程
            return {
                "original_context": "",
                "translation_context": "",
                "[Style Guide]": self.edit_style.toPlainText(),
                "[Glossary]": "",
                "[Semantic Context]": ""
            }

    def _get_semantic_context(self, ts_id):
        # 获取语义检索上下文
        try:
            ts_obj = self.app._find_ts_obj_by_id(ts_id)
            if not ts_obj:
                return ""

            # 调用插件进行检索
            results = self.app.plugin_manager.run_hook(
                'retrieve_context',
                ts_obj.original_semantic
            )

            if not results:
                return ""

            # 格式化结果（限制数量和长度）
            lines = []
            for r in results[:5]:  # 最多5个结果
                src = r.get('source', '')[:60]
                tgt = r.get('target', '')[:60]
                if src and tgt:
                    lines.append(f"- {src}... → {tgt}...")

            if lines:
                return "Similar Translations:\n" + "\n".join(lines)

            return ""

        except Exception as e:
            logger.warning(f"Semantic retrieval failed for {ts_id}: {e}")
            return ""


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
            self.log(f"✗ Failed: {preview}... - {error}", "ERROR")
        else:
            self.log(f"✓ Translated: {preview}...", "SUCCESS")

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

        # 恢复原始提示词结构
        self._restore_original_prompt_structure()

        # 断开AI管理器信号
        self._disconnect_ai_manager_signals()

        # 显示统计信息
        success_rate = (completed / total * 100) if total > 0 else 0
        self.log(
            f"✓ Completed: {completed}/{total} ({success_rate:.1f}%)",
            "SUCCESS"
        )

    def _restore_original_prompt_structure(self):
        """恢复原始提示词结构"""
        if self._original_prompt_structure:
            self.app.config["ai_prompt_structure"] = self._original_prompt_structure
            self.app.save_config()
            self._original_prompt_structure = None

    def stop_translation(self):
        """停止翻译"""
        self.app.ai_manager.stop()
        self.log("Stopping translation...", "WARNING")


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

        color = color_map.get(level, "#D4D4D4")
        html = f'<span style="color: {color}">[{level}] {message}</span>'
        self.log_view.append(html)


    def closeEvent(self, event):
        """对话框关闭事件"""
        # 取消正在运行的分析
        if self.analysis_worker:
            self.analysis_worker.cancel()

        # 恢复原始配置
        self._restore_original_prompt_structure()

        # 断开信号
        self._disconnect_ai_manager_signals()

        super().closeEvent(event)