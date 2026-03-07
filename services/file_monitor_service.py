# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from contextlib import contextmanager
import logging
import os
import time

from PySide6.QtCore import QObject, Signal
from watchdog.events import FileModifiedEvent, FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)


class FileMonitorService(QObject):
    """
    文件监控服务，使用 Watchdog 库。
    提供防抖和重载信号。
    """

    file_changed_on_disk = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.observer = None
        self._monitored_file = None
        self._last_modified_time = 0
        self._is_ignoring = False

    def start_monitoring(self, filepath: str):
        """开始监控指定的文件。"""
        self.stop_monitoring()
        if not filepath or not os.path.exists(filepath):
            return

        self._monitored_file = os.path.normpath(filepath)
        self._last_modified_time = os.path.getmtime(self._monitored_file)

        # Watchdog 监控的是目录，所以我们获取文件所在的目录
        path_to_watch = os.path.dirname(self._monitored_file)

        event_handler = _ChangeHandler(self._monitored_file, self._on_file_modified)

        # 创建并启动 Observer
        self.observer = Observer()
        try:
            self.observer.schedule(event_handler, path_to_watch, recursive=False)
            self.observer.start()
            logger.info(f"Started monitoring file: {self._monitored_file}")
        except Exception as e:
            logger.error(f"Failed to start file monitoring for {path_to_watch}: {e}")
            self.observer = None

    def stop_monitoring(self):
        """停止所有监控。"""
        if self.observer:
            try:
                self.observer.stop()
                self.observer.join(timeout=1)
            except Exception as e:
                logger.error(f"Error stopping file monitor observer: {e}")
            finally:
                self.observer = None

        if self._monitored_file:
            logger.info(f"Stopped monitoring file: {self._monitored_file}")
            self._monitored_file = None

    def _on_file_modified(self):
        """文件系统事件的回调。"""
        if self._is_ignoring or not self._monitored_file:
            return

        try:
            current_mtime = os.path.getmtime(self._monitored_file)
            if current_mtime > self._last_modified_time:
                logger.info(f"External change detected for: {self._monitored_file}")
                self._last_modified_time = current_mtime
                self.file_changed_on_disk.emit(self._monitored_file)
        except FileNotFoundError:
            logger.warning(f"Monitored file was deleted: {self._monitored_file}")
            self.stop_monitoring()
        except Exception as e:
            logger.error(f"Error checking file modification time: {e}")

    def update_last_known_mtime(self):
        """在内部保存后，手动更新文件的最后修改时间戳。"""
        if self._monitored_file and os.path.exists(self._monitored_file):
            try:
                self._last_modified_time = os.path.getmtime(self._monitored_file)
            except OSError as e:
                logger.warning(f"Could not update mtime for {self._monitored_file}: {e}")

    @contextmanager
    def ignore_changes(self):
        """
        一个上下文管理器，用于在代码块执行期间临时忽略文件变更。
        """
        self._is_ignoring = True
        logger.debug("File monitor ignoring changes.")
        try:
            yield
        finally:
            self._is_ignoring = False
            logger.debug("File monitor resumed watching.")
            # 立即更新一次时间戳，防止刚保存完就触发重载
            self.update_last_known_mtime()


class _ChangeHandler(FileSystemEventHandler):
    """Watchdog 的事件处理器。"""

    def __init__(self, target_file, callback):
        self.target_file = target_file
        self.callback = callback
        self._last_event_time = 0
        self._debounce_interval = 0.5  # 500ms 防抖

    def on_modified(self, event: FileModifiedEvent):
        # 确保是文件修改事件，且路径匹配
        if not event.is_directory and os.path.normpath(event.src_path) == self.target_file:
            # 简单的时间戳防抖
            current_time = time.time()
            if current_time - self._last_event_time > self._debounce_interval:
                self._last_event_time = current_time
                self.callback()
