# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import sys
import logging

def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stdout,
    )
    from PySide6.QtWidgets import QApplication
    from main_window import OverwatchLocalizerApp
    app = QApplication(sys.argv)
    main_window = OverwatchLocalizerApp()
    main_window.show()
    try:
        sys.exit(app.exec())
    except KeyboardInterrupt:
        print("\nExit")

if __name__ == "__main__":
    main()