# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import sys
from PySide6.QtWidgets import QApplication
from main_window import OverwatchLocalizerApp

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = OverwatchLocalizerApp()
    main_window.show()
    try:
        sys.exit(app.exec())
    except KeyboardInterrupt:
        print("\nExit")