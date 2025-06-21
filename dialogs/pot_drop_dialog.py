# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import tkinter as tk
from tkinter import ttk, simpledialog
from utils.localization import _


class POTDropDialog(simpledialog.Dialog):
    def body(self, master):
        ttk.Label(master, text=_("A POT file was dropped. What would you like to do?")).pack(pady=10, padx=10)
        return None

    def buttonbox(self):
        box = ttk.Frame(self)

        update_btn = ttk.Button(box, text=_("Update from POT"), command=lambda: self.done("update"))
        update_btn.pack(side=tk.LEFT, padx=5, pady=5)

        import_btn = ttk.Button(box, text=_("Import as New File"), command=lambda: self.done("import"))
        import_btn.pack(side=tk.LEFT, padx=5, pady=5)

        cancel_btn = ttk.Button(box, text=_("Cancel"), command=self.cancel)
        cancel_btn.pack(side=tk.LEFT, padx=5, pady=5)

        self.bind("<Escape>", self.cancel)

        box.pack()

    def done(self, result):
        self.result = result
        self.destroy()