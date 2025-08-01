# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import sys
import os
import logging
import re
from PySide6.QtWidgets import QApplication
from main_window import OverwatchLocalizerApp

def setup_plugin_library_path():
    try:
        from utils.path_utils import get_plugin_libs_path
        plugin_libs_path = get_plugin_libs_path()
        if plugin_libs_path not in sys.path:
            sys.path.insert(0, plugin_libs_path)
            logging.info(f"Plugin library path added: {plugin_libs_path}")
    except Exception as e:
        logging.error(f"Error setting up plugin library path: {e}", exc_info=True)

if __name__ == "__main__":
    setup_plugin_library_path()
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stdout,
    )
    app = QApplication(sys.argv)
    main_window = OverwatchLocalizerApp()
    main_window.show()
    try:
        sys.exit(app.exec())
    except KeyboardInterrupt:
        print("\nExit")