# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtCore import QThread, Signal
import logging


class PreloaderThread(QThread):
    finished = Signal(object, str)  # main_window_instance, error_message

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.setPriority(QThread.LowPriority)

    def run(self):
        logging.info("PreloaderThread: Starting to create MainWindow instance in background...")
        main_window_instance = None
        error_message = ""
        try:
            # 导入和路径设置现在都在这个线程里完成
            from main_window import OverwatchLocalizerApp
            from utils.path_utils import get_plugin_libs_path
            import sys

            plugin_libs_path = get_plugin_libs_path()
            if plugin_libs_path not in sys.path:
                sys.path.insert(0, plugin_libs_path)

            main_window_instance = OverwatchLocalizerApp(self.config)

            logging.info("PreloaderThread: MainWindow instance created successfully.")

        except Exception as e:
            error_message = str(e)
            logging.error(f"PreloaderThread failed: {e}", exc_info=True)

        # 将创建好的实例（或None）和错误信息发射出去
        self.finished.emit(main_window_instance, error_message)