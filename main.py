# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QObject
from utils import debug_utils
from utils.single_instance import raise_existing_instance, SingleInstanceServer

debug_utils.setup_debug_mode()
app_controller = None
import logging
logger = logging.getLogger(__name__)


class AppController(QObject):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.main_window = None
        self.welcome_screen = None
        self.instance_server = SingleInstanceServer(self)
        if self.instance_server.start():
            self.instance_server.request_activation.connect(self.bring_to_front)

    def start(self):
        from ui_components.welcome_screen import WelcomeScreen
        self.welcome_screen = WelcomeScreen(self.config)
        self.welcome_screen.request_main_window.connect(self.handle_welcome_request)
        self.welcome_screen.show()

    def bring_to_front(self):
        logger.info("Activation requested from another instance.")
        target = None
        if self.main_window and self.main_window.isVisible():
            target = self.main_window
        elif self.welcome_screen and self.welcome_screen.isVisible():
            target = self.welcome_screen

        if target:
            target.showNormal()
            target.activateWindow()
            target.raise_()

    def handle_welcome_request(self, action, path):
        logger.info(f"Welcome screen requested action: {action}, path: {path}")


if __name__ == "__main__":
    log_level = logging.DEBUG if debug_utils.IS_DEBUG_MODE else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stdout,
    )
    app = QApplication(sys.argv)

    if raise_existing_instance():
        logger.info("Another instance is already running. Exiting.")
        sys.exit(0)

    app.setStyleSheet("""
        QPushButton {
            background-color: #FFFFFF;
            border: 1px solid #DCDFE6;
            color: #606266;
            padding: 5px 15px;
            border-radius: 4px;
            font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
            font-size: 13px;
            font-weight: 500;
        }
        QPushButton:hover {
            background-color: #ECF5FF;
            border-color: #C6E2FF;
            color: #409EFF;
        }
        QPushButton:pressed {
            background-color: #3A8EE6;
            border-color: #3A8EE6;
            color: #FFFFFF;
        }
        QPushButton:disabled {
            background-color: #F5F7FA;
            border-color: #E4E7ED;
            color: #C0C4CC;
        }
    """)
    from utils.config_manager import load_config
    from utils.localization import lang_manager

    config = load_config()
    language_code = config.get('language')
    if not language_code:
        language_code = lang_manager.get_best_match_language()
        config['language'] = language_code
    lang_manager.setup_translation(language_code)

    app_controller = AppController(config)
    app_controller.start()

    sys.exit(app.exec())