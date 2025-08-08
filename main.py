# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import sys
import logging
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QObject
from utils import debug_utils
debug_utils.setup_debug_mode()
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
    log_level = logging.DEBUG if debug_utils.IS_DEBUG_MODE else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stdout,
    )
    app = QApplication(sys.argv)

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