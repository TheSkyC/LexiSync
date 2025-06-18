# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import tkinter as tk
from app import OverwatchLocalizerApp

try:
    from tkinterdnd2 import TkinterDnD
except ImportError:
    TkinterDnD = None

if __name__ == "__main__":
    try:
        if TkinterDnD:
            root = TkinterDnD.Tk()
        else:
            root = tk.Tk()
        app = OverwatchLocalizerApp(root)
        root.mainloop()
    except KeyboardInterrupt:
        print("\nExit")