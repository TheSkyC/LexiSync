# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtCore import QObject, Signal, QThreadPool, QTimer
import threading
import logging
from utils.enums import AIOperationType
from utils.constants import SUPPORTED_LANGUAGES
from services.ai_worker import AIWorker

logger = logging.getLogger(__name__)


class AITaskManager(QObject):
    # Signals
    batch_started = Signal(int)
    batch_progress = Signal(int, int)
    batch_finished = Signal(list, int, int)
    item_result = Signal(str, str, str, object)
    worker_log = Signal(str, str)

    def __init__(self, app_instance):
        super().__init__()
        self.app = app_instance
        self.thread_pool = QThreadPool.globalInstance()

        # State
        self.is_running = False
        self.queue = []
        self.total_items = 0
        self.completed_count = 0
        self.next_index = 0
        self.active_threads = 0
        self.successful_changes = []

        self.semaphore = None
        self.context_provider = None

    def start_batch(self, items, context_provider_func, concurrency_override=None, **worker_kwargs):
        if self.is_running:
            return False

        self.queue = items
        self.total_items = len(items)
        self.completed_count = 0
        self.next_index = 0
        self.active_threads = 0
        self.successful_changes = []
        self.context_provider = context_provider_func
        self.worker_kwargs = worker_kwargs
        self.is_running = True

        if concurrency_override is not None:
            max_concurrency = int(concurrency_override)
        else:
            max_concurrency = self.app.config.get("ai_max_concurrent_requests", 1)

        max_concurrency = max(1, max_concurrency)

        self.semaphore = threading.Semaphore(max_concurrency)

        self.batch_started.emit(self.total_items)

        # Initial dispatch
        for _ in range(max_concurrency):
            if self.next_index < self.total_items:
                self._dispatch_next()
            else:
                break
        return True

    def stop(self):
        if not self.is_running:
            return
        self.is_running = False
        if self.active_threads == 0:
            self._finalize()

    def _dispatch_next(self):
        if not self.is_running: return
        if self.next_index >= self.total_items: return

        # Try to acquire semaphore without blocking UI
        if self.semaphore.acquire(blocking=False):
            if not self.is_running:
                self.semaphore.release()
                return

            # Double check index after acquire
            if self.next_index >= self.total_items:
                self.semaphore.release()
                return

            ts_obj = self.queue[self.next_index]
            self.next_index += 1
            self.active_threads += 1

            # Prepare Worker Data
            plugin_placeholders = {}
            if hasattr(self.app, 'plugin_manager'):
                plugin_placeholders = self.app.plugin_manager.run_hook('get_ai_translation_context') or {}

            target_lang_code = self.app.current_target_language if self.app.is_project_mode else self.app.target_language
            target_lang_name = next((name for name, code in SUPPORTED_LANGUAGES.items() if code == target_lang_code),
                                    target_lang_code)

            worker = AIWorker(
                self.app,
                ts_id=ts_obj.id,
                operation_type=AIOperationType.BATCH_TRANSLATION,
                original_text=ts_obj.original_semantic,
                target_lang=target_lang_name,
                context_provider=self.context_provider,
                plugin_placeholders=plugin_placeholders,
                **self.worker_kwargs
            )

            # Connect Signals
            worker.signals.result.connect(self.item_result)
            worker.signals.result.connect(self._collect_success_for_undo)
            worker.signals.finished.connect(self._on_worker_finished)
            worker.signals.log_message.connect(self.worker_log)
            self.thread_pool.start(worker)

    def _on_worker_finished(self):
        self.semaphore.release()
        self.active_threads -= 1
        self.completed_count += 1

        self.batch_progress.emit(self.completed_count, self.total_items)

        if self.is_running:
            if self.next_index < self.total_items:
                interval = self.app.config.get("ai_api_interval", 200)
                QTimer.singleShot(interval, self._dispatch_next)
            elif self.active_threads == 0:
                self._finalize()
        elif self.active_threads == 0:
            self._finalize()

    def _collect_success_for_undo(self, ts_id, text, error, op_type):
        if not error and text:
            pass

    def _finalize(self):
        self.batch_finished.emit(
            self.successful_changes,
            self.completed_count,
            self.total_items
        )

        self.is_running = False

        # Reset state
        self.queue = []
        self.context_provider = None
        self.total_items = 0
        self.completed_count = 0