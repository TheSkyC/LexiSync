# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QFrame, QProgressBar, QSplitter, QWidget,
    QMessageBox, QCheckBox, QGraphicsOpacityEffect,
    QApplication,
)
from PySide6.QtCore import Qt, QTimer, Signal, QObject, QSize, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QKeySequence, QColor, QFont, QTextCursor, QShortcut

from services.ai_worker import AIWorker
from utils.enums import AIOperationType, WarningType
from services.validation_service import validate_string
from models.translatable_string import TranslatableString
from ui_components.tooltip import Tooltip
from utils.localization import _
import collections
import logging

logger = logging.getLogger(__name__)


class ReviewController(QObject):
    item_ready = Signal(str, str)  # ts_id, translated_text
    buffer_status = Signal(int)

    def __init__(self, app, items, context_provider, config_snapshot):
        super().__init__()
        self.app = app
        self.all_items = items
        self.items_queue = collections.deque(items)
        self.result_buffer = {}  # {ts_id: translation}
        self.processing_ids = set()
        self.context_provider = context_provider
        self.config_snapshot = config_snapshot

        self.buffer_limit = 5  # 预加载数量
        self.is_stopped = False

    def start_prefetch(self):
        """启动预加载"""
        self._fill_buffer()

    def _fill_buffer(self):
        """填充缓冲区到目标大小"""
        if self.is_stopped:
            return

        # 检查是否需要补充
        current_buffer_size = len(self.result_buffer)
        active_tasks = len(self.processing_ids)

        needed = self.buffer_limit - (current_buffer_size + active_tasks)

        if needed <= 0:
            return

        # 启动 Worker
        for _ in range(needed):
            if not self.items_queue:
                break

            ts_obj = self.items_queue.popleft()
            self._spawn_worker(ts_obj)

    def _spawn_worker(self, ts_obj):
        """生成一个翻译工作线程"""
        self.processing_ids.add(ts_obj.id)

        # 获取上下文
        context_dict = self.context_provider(ts_obj.id)

        # 获取目标语言名称
        target_lang_code = self.app.current_target_language if self.app.is_project_mode else self.app.target_language
        from utils.constants import SUPPORTED_LANGUAGES
        target_lang_name = next((name for name, code in SUPPORTED_LANGUAGES.items() if code == target_lang_code),
                                target_lang_code)

        worker = AIWorker(
            self.app,
            ts_id=ts_obj.id,
            operation_type=AIOperationType.TRANSLATION,
            original_text=ts_obj.original_semantic,
            target_lang=target_lang_name,
            context_dict=context_dict,
            temperature=self.config_snapshot.get("temperature", 0.3),
            stream=False
        )

        worker.signals.result.connect(self._on_worker_result)
        self.app.ai_thread_pool.start(worker)

    def _on_worker_result(self, ts_id, text, error, op_type):
        """处理工作线程返回的翻译结果"""
        if ts_id in self.processing_ids:
            self.processing_ids.remove(ts_id)

        if not error and text:
            self.result_buffer[ts_id] = text
            self.item_ready.emit(ts_id, text)
        else:
            # 如果失败，存入空字符串，UI层会显示错误或允许重试
            logger.warning(f"Translation failed for {ts_id}: {error}")
            self.result_buffer[ts_id] = ""
            self.item_ready.emit(ts_id, "")

        self.buffer_status.emit(len(self.result_buffer))

        self._fill_buffer()

    def get_result(self, ts_id):
        if ts_id in self.result_buffer:
            result = self.result_buffer.pop(ts_id)
            self.buffer_status.emit(len(self.result_buffer))

            # 立即尝试填充缓冲区
            self._fill_buffer()
            return result
        return None

    def stop(self):
        """停止预加载"""
        self.is_stopped = True


class InteractiveReviewDialog(QDialog):
    def __init__(self, parent, app, items, context_provider, config_snapshot):
        super().__init__(parent)
        self.app = app
        self.items = items
        self.total_count = len(items)
        self.current_index = 0
        self.context_provider = context_provider

        # Controller
        self.controller = ReviewController(app, list(items), context_provider, config_snapshot)
        self.controller.item_ready.connect(self._on_item_ready)
        self.controller.buffer_status.connect(self._update_buffer_indicator)

        # Auto-Run State
        self.is_auto_running = False
        self.auto_run_timer = QTimer(self)
        self.auto_run_timer.setInterval(800)
        self.auto_run_timer.timeout.connect(self._process_auto_run)

        self.setWindowTitle(_("Interactive Review Mode"))
        self.resize(1100, 750)
        self.setModal(True)

        self.setup_ui()
        self.controller.start_prefetch()
        self.load_current_item()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # --- 1. Header ---
        header = QFrame()
        header.setStyleSheet("background-color: #F5F7FA; border-bottom: 1px solid #E0E0E0;")
        header.setFixedHeight(60)
        header_layout = QHBoxLayout(header)

        self.progress_label = QLabel("0 / 0")
        self.progress_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #333;")

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #4CAF50; border-radius: 4px; }")

        self.buffer_indicator = QLabel(_("Buffer: 0"))
        self.buffer_indicator.setStyleSheet("color: #999; font-size: 12px;")

        header_layout.addWidget(self.progress_label)
        header_layout.addWidget(self.progress_bar, 1)
        header_layout.addWidget(self.buffer_indicator)

        main_layout.addWidget(header)

        # --- 2. Main Content (Splitter) ---
        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet("QSplitter::handle { background-color: #E0E0E0; }")

        # Left: Context & Source
        left_panel = QWidget()
        left_panel.setStyleSheet("background-color: #FFFFFF;")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(20, 20, 20, 20)

        lbl_source = QLabel(_("Source Text"))
        lbl_source.setStyleSheet("color: #666; font-weight: bold; text-transform: uppercase; font-size: 11px;")

        self.source_view = QTextEdit()
        self.source_view.setReadOnly(True)
        self.source_view.setStyleSheet("border: none; font-size: 16px; color: #2C3E50; background: transparent;")

        lbl_context = QLabel(_("Context Reference"))
        lbl_context.setStyleSheet(
            "color: #666; font-weight: bold; text-transform: uppercase; font-size: 11px; margin-top: 20px;")

        self.context_view = QTextEdit()
        self.context_view.setReadOnly(True)
        self.context_view.setStyleSheet(
            "border: 1px solid #EEE; border-radius: 6px; background-color: #FAFAFA; padding: 10px; font-size: 13px;")

        left_layout.addWidget(lbl_source)
        left_layout.addWidget(self.source_view, 1)
        left_layout.addWidget(lbl_context)
        left_layout.addWidget(self.context_view, 2)

        # Right: Editor & Validation
        right_panel = QWidget()
        right_panel.setStyleSheet("background-color: #FFFFFF;")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(20, 20, 20, 20)

        lbl_trans = QLabel(_("Translation"))
        lbl_trans.setStyleSheet("color: #4CAF50; font-weight: bold; text-transform: uppercase; font-size: 11px;")

        self.editor = QTextEdit()
        self.editor.setStyleSheet("""
            QTextEdit {
                border: 2px solid #E0E0E0; 
                border-radius: 6px; 
                background-color: #FAFAFA;
                font-size: 18px;
                padding: 15px;
            }
        """)
        self.editor.setPlaceholderText(_("Translation will appear here..."))
        self.editor.textChanged.connect(self._validate_current)

        self.validation_banner = QLabel()
        self.validation_banner.setStyleSheet("""
            QLabel {
                background-color: #FFEBEE;
                border: 1px solid #EF5350;
                border-radius: 4px;
                padding: 10px;
                color: #B71C1C;
                font-size: 12px;
            }
        """)
        self.validation_banner.setWordWrap(True)
        self.validation_banner.hide()

        right_layout.addWidget(lbl_trans)
        right_layout.addWidget(self.editor, 1)
        right_layout.addWidget(self.validation_banner)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([400, 600])

        main_layout.addWidget(splitter, 1)

        # --- 3. Footer (Actions) ---
        footer = QFrame()
        footer.setFixedHeight(80)
        footer.setStyleSheet("background-color: #FFFFFF;")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 10, 20, 10)

        self.chk_auto_run = QCheckBox(_("Auto-Run (Stop on Error)"))
        self.chk_auto_run.setStyleSheet("""
            QCheckBox {
                font-weight: bold; 
                color: #555;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #999;
                border-radius: 3px;
                background-color: white;
            }
            QCheckBox::indicator:hover {
                border-color: #4CAF50;
            }
            QCheckBox::indicator:checked {
                background-color: #4CAF50;
                border-color: #4CAF50;
                image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iOSIgdmlld0JveD0iMCAwIDEyIDkiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxwYXRoIGQ9Ik0xMSAxTDQuNSA3LjVMMSA0IiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIvPgo8L3N2Zz4K);
            }
        """)
        self.chk_auto_run.toggled.connect(self._toggle_auto_run)

        footer_layout.addWidget(self.chk_auto_run)
        footer_layout.addStretch()

        # Buttons
        self.btn_skip = QPushButton(_("Skip (Ctrl+Right)"))
        self.btn_skip.setFixedSize(140, 45)
        self.btn_skip.clicked.connect(self.skip_current)

        self.btn_accept = QPushButton(_("Accept (Enter)"))
        self.btn_accept.setFixedSize(160, 45)
        self.btn_accept.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50; 
                color: white; 
                font-weight: bold; 
                font-size: 14px; 
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:disabled { background-color: #CCC; }
        """)
        self.btn_accept.clicked.connect(self.accept_current)

        footer_layout.addWidget(self.btn_skip)
        footer_layout.addWidget(self.btn_accept)

        main_layout.addWidget(footer)

        # Shortcuts
        QShortcut(QKeySequence("Ctrl+Right"), self, self.skip_current)
        QShortcut(QKeySequence(Qt.Key_Return), self, self.accept_current)
        QShortcut(QKeySequence(Qt.Key_Enter), self, self.accept_current)

    def _update_buffer_indicator(self, buffer_size):
        self.buffer_indicator.setText(f"Buffer: {buffer_size}")

    def load_current_item(self):
        """加载当前项目"""
        if self.current_index >= self.total_count:
            self._finish_review()
            return

        self.current_ts = self.items[self.current_index]

        # Update Progress
        self.progress_label.setText(f"{self.current_index + 1} / {self.total_count}")
        self.progress_bar.setValue(int((self.current_index / self.total_count) * 100))

        # Update Source
        self.source_view.setPlainText(self.current_ts.original_semantic)

        # Update Context (Async fetch if needed, but usually fast enough here)
        self._render_context()

        # Check Buffer
        cached_translation = self.controller.get_result(self.current_ts.id)

        if cached_translation is not None:
            self.editor.setPlainText(cached_translation)
            self.editor.setEnabled(True)
            self.btn_accept.setEnabled(True)
            self._validate_current()

            # 如果是自动模式，且已经有结果，触发计时器
            if self.is_auto_running:
                self.auto_run_timer.start()
        else:
            # Waiting for AI
            self.editor.setPlaceholderText(_("AI is translating..."))
            self.editor.clear()
            self.editor.setEnabled(False)
            self.btn_accept.setEnabled(False)
            self.validation_banner.hide()
            # 暂停自动运行，等待回调
            self.auto_run_timer.stop()

    def _on_item_ready(self, ts_id, text):
        """当某个项目的翻译准备好时调用"""
        # 更新缓冲区指示器在buffer_status信号中处理

        if self.current_ts and ts_id == self.current_ts.id:
            self.editor.setPlainText(text)
            self.editor.setEnabled(True)
            self.btn_accept.setEnabled(True)
            self._validate_current()

            if self.is_auto_running:
                self.auto_run_timer.start()

    def _render_context(self):
        """渲染上下文信息"""
        ctx = self.context_provider(self.current_ts.id)

        html = ""

        # 1. Glossary
        if ctx.get('[Glossary]'):
            html += f"<h4 style='color:#673AB7'>{_('Glossary Matches')}</h4>"
            lines = ctx['[Glossary]'].split('\n')
            for line in lines:
                if line.strip():
                    html += f"<div style='margin-bottom:4px; color:#333;'>{line}</div>"
            html += "<hr>"

        # 2. TM / Semantic
        if ctx.get('[Semantic Context]'):
            html += f"<h4 style='color:#009688'>{_('Similar Texts (TM/RAG)')}</h4>"
            content = ctx['[Semantic Context]'].replace('\n', '<br>')
            html += f"<div style='color:#555; font-size:12px;'>{content}</div>"
            html += "<hr>"

        # 3. Neighbors
        if ctx.get('original_context'):
            html += f"<h4 style='color:#607D8B'>{_('Nearby Text')}</h4>"
            content = ctx['original_context'].replace('\n', '<br>')
            html += f"<div style='color:#777; font-style:italic;'>{content}</div>"

        self.context_view.setHtml(html)

    def _validate_current(self):
        """验证当前翻译"""
        text = self.editor.toPlainText()
        if not text:
            self.validation_banner.hide()
            return False

        # 创建临时对象进行验证
        temp_ts = TranslatableString("", self.current_ts.original_semantic, 0, 0, 0, [])
        temp_ts.translation = text

        validate_string(temp_ts, self.app.config, self.app)

        errors = []
        for wt, msg in temp_ts.warnings:
            errors.append(f"• {msg}")

        # 长度检查等 Minor Warnings 也可以视为阻断自动运行的理由
        for wt, msg in temp_ts.minor_warnings:
            errors.append(f"• {msg}")

        if errors:
            self.validation_banner.setText("\n".join(errors))
            self.validation_banner.show()
            self.editor.setStyleSheet(
                "border: 2px solid #F44336; background-color: #FAFAFA; font-size: 18px; padding: 15px;")
            return False
        else:
            self.validation_banner.hide()
            self.editor.setStyleSheet(
                "border: 2px solid #4CAF50; background-color: #FAFAFA; font-size: 18px; padding: 15px;")
            return True

    def _toggle_auto_run(self, checked):
        """切换自动运行模式"""
        self.is_auto_running = checked
        if checked:
            self.btn_accept.setText(_("Auto-Running..."))
            # 立即处理当前项（如果已就绪）
            if self.editor.isEnabled():
                self._process_auto_run()
        else:
            self.btn_accept.setText(_("Accept (Enter)"))
            self.auto_run_timer.stop()

    def _process_auto_run(self):
        """处理自动运行逻辑"""
        if not self.is_auto_running:
            return
        if not self.editor.isEnabled():  # 等待 AI 中
            return

        # 检查是否有错误
        is_valid = self._validate_current()

        if is_valid:
            self.accept_current()
        else:
            # 有错误，暂停自动运行
            self.chk_auto_run.setChecked(False)
            self.validation_banner.setText(
                self.validation_banner.text() + f"\n\n[{_('Auto-Run Paused due to Error')}]"
            )
            QApplication.alert(self)  # 闪烁任务栏

    def accept_current(self):
        """接受当前翻译"""
        text = self.editor.toPlainText()
        self.app._apply_translation_to_model(self.current_ts, text, source="interactive_review")
        self.current_ts.is_reviewed = True
        self._next()

    def skip_current(self):
        """跳过当前项目"""
        self._next()

    def _next(self):
        """移动到下一个项目"""
        self.current_index += 1
        self.load_current_item()

    def _finish_review(self):
        """完成审阅"""
        self.controller.stop()
        QMessageBox.information(self, _("Review Complete"), _("You have reviewed all items in the list."))
        self.accept()

    def closeEvent(self, event):
        """对话框关闭事件"""
        self.controller.stop()
        super().closeEvent(event)