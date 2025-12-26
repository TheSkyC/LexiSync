# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QComboBox, QSplitter, QWidget, QGroupBox,
    QTabWidget, QDoubleSpinBox, QMessageBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QTextCursor
from services.smart_translation_service import SmartTranslationService
from services.ai_worker import AIWorker
from utils.enums import AIOperationType
from utils.localization import _
import logging

logger = logging.getLogger(__name__)


class TestTranslationDialog(QDialog):
    def __init__(self, parent_dialog, app_instance):
        super().__init__(parent_dialog)
        self.parent_dialog = parent_dialog  # SmartTranslationDialog
        self.app = app_instance
        self.setWindowTitle(_("Translation Test Lab"))
        self.resize(1000, 700)

        self.current_ts_obj = None
        self._is_first_chunk = True
        self._current_worker = None

        self.setup_ui()
        self.load_smart_sample()

        self.setStyleSheet("""
            QScrollBar:vertical {
                border: none;
                background: #F0F0F0;
                width: 10px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:vertical {
                background: #C0C0C0;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: #A0A0A0;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        splitter = QSplitter(Qt.Horizontal)

        # --- Left Panel: Input & Config ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        # 1. Source Selection
        src_group = QGroupBox(_("Source Text"))
        src_layout = QVBoxLayout(src_group)

        controls_layout = QHBoxLayout()
        self.sample_type_combo = QComboBox()
        self.sample_type_combo.addItems([
            _("Most Complex (Variables/Tags)"),
            _("Longest Text"),
            _("Random Sample"),
            _("Manual Input")
        ])
        self.sample_type_combo.currentIndexChanged.connect(self.load_smart_sample)

        btn_refresh = QPushButton(_("Next Sample"))
        btn_refresh.clicked.connect(self.load_smart_sample)

        controls_layout.addWidget(self.sample_type_combo)
        controls_layout.addWidget(btn_refresh)
        src_layout.addLayout(controls_layout)

        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText(_("Enter text to test..."))
        src_layout.addWidget(self.input_edit)
        left_layout.addWidget(src_group)

        # 2. Temporary Overrides
        override_group = QGroupBox(_("Temporary Overrides"))
        override_layout = QVBoxLayout(override_group)

        temp_layout = QHBoxLayout()
        temp_layout.addWidget(QLabel(_("Temperature:")))
        self.temp_spin = QDoubleSpinBox()
        self.temp_spin.setRange(0.0, 1.5)
        self.temp_spin.setSingleStep(0.1)
        self.temp_spin.setValue(self.parent_dialog.temp_spinbox.value())
        temp_layout.addWidget(self.temp_spin)
        override_layout.addLayout(temp_layout)

        self.style_override = QTextEdit()
        self.style_override.setPlaceholderText(_("Modify Style Guide here for testing..."))
        self.style_override.setPlainText(self.parent_dialog.edit_style.toPlainText())
        override_layout.addWidget(QLabel(_("Style Guide:")))
        override_layout.addWidget(self.style_override)
        left_layout.addWidget(override_group)

        self.btn_action = QPushButton(_("▶ Run Test"))
        self.btn_action.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 10px;")
        self.btn_action.clicked.connect(self.on_action_clicked)
        left_layout.addWidget(self.btn_action)

        splitter.addWidget(left_widget)

        # --- Right Panel: Result & Context ---
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        # 1. Result
        res_group = QGroupBox(_("Translation Result"))
        res_layout = QVBoxLayout(res_group)
        self.output_view = QTextEdit()
        self.output_view.setReadOnly(True)
        self.output_view.setStyleSheet("background-color: #F0F0F0; font-size: 14px;")
        res_layout.addWidget(self.output_view)
        right_layout.addWidget(res_group)

        # 2. Context Inspector
        ctx_group = QGroupBox(_("Context Inspector"))
        ctx_layout = QVBoxLayout(ctx_group)
        self.ctx_tabs = QTabWidget()

        self.tab_glossary = QTextEdit()
        self.tab_glossary.setReadOnly(True)
        self.ctx_tabs.addTab(self.tab_glossary, _("Injected Glossary"))

        self.tab_tm = QTextEdit()
        self.tab_tm.setReadOnly(True)
        self.ctx_tabs.addTab(self.tab_tm, _("TM / RAG"))

        self.tab_full_prompt = QTextEdit()
        self.tab_full_prompt.setReadOnly(True)
        self.ctx_tabs.addTab(self.tab_full_prompt, _("Full Prompt"))

        ctx_layout.addWidget(self.ctx_tabs)
        right_layout.addWidget(ctx_group)

        splitter.addWidget(right_widget)
        splitter.setSizes([400, 600])

        main_layout.addWidget(splitter)

    def on_action_clicked(self):
        if self._current_worker:
            self.stop_test()
        else:
            self.run_test()

    def load_smart_sample(self):
        mode = self.sample_type_combo.currentIndex()
        items = self.parent_dialog.target_items
        if not items: return

        import random
        selected = None

        if mode == 0:  # Complex
            # 简单的复杂度评分：长度 + 变量数 * 5
            def complexity(ts):
                return len(ts.original_semantic) + (
                            ts.original_semantic.count('%') + ts.original_semantic.count('{')) * 10

            sorted_items = sorted(items, key=complexity, reverse=True)
            pool = sorted_items[:20]
            selected = random.choice(pool)

        elif mode == 1:  # Longest
            sorted_items = sorted(items, key=lambda x: len(x.original_semantic), reverse=True)
            pool = sorted_items[:20]
            selected = random.choice(pool)

        elif mode == 2:  # Random
            selected = random.choice(items)

        elif mode == 3:  # Manual
            self.input_edit.clear()
            self.input_edit.setFocus()
            self.current_ts_obj = None
            return

        if selected:
            self.current_ts_obj = selected
            self.input_edit.setPlainText(selected.original_semantic)

    def run_test(self):
        text = self.input_edit.toPlainText().strip()
        if not text: return

        self.btn_action.setText(_("⏹ Stop"))
        self.btn_action.setStyleSheet("background-color: #F44336; color: white; font-weight: bold; padding: 10px;")

        self.output_view.clear()
        self.output_view.setPlainText(_("Translating..."))
        self._is_first_chunk = True
        self.tab_glossary.clear()
        self.tab_tm.clear()
        self.tab_full_prompt.clear()

        # 1. 准备上下文
        ts_id = self.current_ts_obj.id if self.current_ts_obj else "manual_test"

        # 临时替换 Style Guide
        original_style = self.parent_dialog.edit_style.toPlainText()
        self.parent_dialog.edit_style.setPlainText(self.style_override.toPlainText())

        # 获取上下文
        if self.current_ts_obj:
            config_snapshot = self.parent_dialog._capture_context_config()
            context_dict = self.parent_dialog._worker_context_provider(ts_id, config_snapshot)
        else:
            # 手动输入的模拟上下文
            context_dict = self._simulate_context(text)
        self.parent_dialog.edit_style.setPlainText(original_style)

        # 2. 展示上下文到 Inspector
        self.tab_glossary.setPlainText(context_dict.get('[Glossary]', _("No glossary terms injected.")))
        self.tab_tm.setPlainText(context_dict.get('[Semantic Context]', _("No TM/RAG matches.")))

        # 3. 启动 Worker
        target_lang = self.parent_dialog._get_target_language()

        self._current_worker = AIWorker(
            self.app,
            ts_id=ts_id,
            operation_type=AIOperationType.TRANSLATION,
            original_text=text,
            target_lang=target_lang,
            context_dict=context_dict,
            temperature=self.temp_spin.value(),
            stream=True
        )

        self._current_worker.signals.result.connect(self.on_result)
        self._current_worker.signals.stream_chunk.connect(self.on_stream_chunk)
        self._current_worker.signals.final_prompt_ready.connect(self.on_prompt_ready)
        self._current_worker.signals.finished.connect(self.on_worker_finished)

        self.app.ai_thread_pool.start(self._current_worker)

    def stop_test(self):
        if self._current_worker:
            try:
                self._current_worker.signals.stream_chunk.disconnect(self.on_stream_chunk)
                self._current_worker.signals.result.disconnect(self.on_result)
                self._current_worker.signals.finished.disconnect(self.on_worker_finished)
            except:
                pass
            self._current_worker = None

        self.output_view.append(f"\n[{_('Stopped by user')}]")
        self.reset_button_state()

    def reset_button_state(self):
        self.btn_action.setText(_("▶ Run Test"))
        self.btn_action.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 10px;")
        self._current_worker = None

    def on_worker_finished(self):
        self.reset_button_state()

    def _simulate_context(self, text):
        # 1. Glossary
        glossary_lines = []
        if self.parent_dialog._cached_glossary_dict:
            for src, tgt in self.parent_dialog._cached_glossary_dict.items():
                if src.lower() in text.lower():
                    glossary_lines.append(f"- {src}: {tgt}")

        # 2. TM
        tm_context = ""
        if self.parent_dialog.chk_use_tm.isChecked():
            tm_limit = self.parent_dialog.spin_retrieval.value()
            tm_context = self.parent_dialog._fetch_tm_context(text, limit=tm_limit)

        return {
            "original_context": "",
            "translation_context": "",
            "[Style Guide]": self.style_override.toPlainText(),
            "[Glossary]": "\n".join(glossary_lines),
            "[Semantic Context]": tm_context
        }

    def on_stream_chunk(self, chunk):
        if self._is_first_chunk:
            self.output_view.clear()
            self._is_first_chunk = False

        cursor = self.output_view.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(chunk)
        self.output_view.setTextCursor(cursor)

    def on_prompt_ready(self, prompt):
        self.tab_full_prompt.setPlainText(prompt)

    def on_result(self, ts_id, text, error, op_type):
        if error:
            self.output_view.setPlainText(f"Error: {error}")
        else:
            pass