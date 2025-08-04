# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import sys
import logging
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QObject, QTimer, Qt
app_controller = None

class AppController(QObject):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.main_window = None
        self.welcome_screen = None

    def start(self):
        from ui_components.welcome_screen import WelcomeScreen
        self.welcome_screen = WelcomeScreen(self.config)
        self.welcome_screen.request_main_window.connect(self.handle_welcome_request)
        self.welcome_screen.show()

    def handle_welcome_request(self, action, path):
        logging.info(f"Welcome screen requested action: {action}, path: {path}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stdout,
    )
    app = QApplication(sys.argv)

    from utils.config_manager import load_config
    from utils.localization import lang_manager

    config = load_config()
    lang_manager.setup_translation(config.get('language'))

    app_controller = AppController(config)
    app_controller.start()

    sys.exit(app.exec())