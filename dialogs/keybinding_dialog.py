# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
from utils.constants import DEFAULT_KEYBINDINGS


class KeybindingDialog(simpledialog.Dialog):
    def __init__(self, parent, title, app_instance):
        self.app = app_instance
        self.key_vars = {}
        self.current_capture_entry = None

        self.pressed_modifiers = set()
        self.modifier_map = {
            'Control_L': 'Control', 'Control_R': 'Control',
            'Shift_L': 'Shift', 'Shift_R': 'Shift',
            'Alt_L': 'Alt', 'Alt_R': 'Alt', 'Alt_Gr': 'Alt',
            'Super_L': 'Command', 'Super_R': 'Command'
        }

        super().__init__(parent, title)

    def body(self, master):
        master.columnconfigure(1, weight=1)

        self.entries = {}
        row_idx = 1
        for action, details in self.app.ACTION_MAP.items():
            ttk.Label(master, text=details['desc'] + ":").grid(row=row_idx, column=0, sticky=tk.W, padx=5, pady=3)

            key_var = tk.StringVar(value=self.app.config['keybindings'].get(action, ''))
            entry = ttk.Entry(master, textvariable=key_var, width=25)
            entry.grid(row=row_idx, column=1, sticky=tk.EW, padx=5, pady=3)

            entry.bind("<FocusIn>", self.on_entry_focus)
            entry.bind("<FocusOut>", self.on_entry_blur)

            self.key_vars[action] = key_var
            self.entries[action] = entry
            row_idx += 1

        return None

    def on_entry_focus(self, event):
        self.current_capture_entry = event.widget
        self.current_capture_entry.config(foreground="red")

        self.pressed_modifiers.clear()
        self.bind_all("<KeyPress>", self.on_key_press, add="+")
        self.bind_all("<KeyRelease>", self.on_key_release, add="+")

    def on_entry_blur(self, event):
        if self.current_capture_entry:
            self.current_capture_entry.config(foreground="black")
        self.current_capture_entry = None

        self.unbind_all("<KeyPress>")
        self.unbind_all("<KeyRelease>")


    def on_key_press(self, event):
        if not self.current_capture_entry:
            return

        keysym = event.keysym

        if keysym in self.modifier_map:
            self.pressed_modifiers.add(self.modifier_map[keysym])
            return

        final_modifiers = list(dict.fromkeys(self.pressed_modifiers))

        main_key = keysym
        if len(main_key) == 1 and main_key.isalnum():
            main_key = main_key.upper()

        all_parts = final_modifiers + [main_key]
        key_sequence = f"<{'-'.join(all_parts)}>"

        for action, entry in self.entries.items():
            if entry == self.current_capture_entry:
                self.key_vars[action].set(key_sequence)
                break

        self.pressed_modifiers.clear()
        self.current_capture_entry.config(foreground="black")
        self.focus_set()
        return "break"

    def on_key_release(self, event):
        if not self.current_capture_entry:
            return

        keysym = event.keysym
        if keysym in self.modifier_map:
            modifier = self.modifier_map[keysym]
            if modifier in self.pressed_modifiers:
                self.pressed_modifiers.remove(modifier)

    def buttonbox(self):
        box = ttk.Frame(self)
        ttk.Button(box, text="重置为默认值", command=self.reset_to_defaults).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(box, text="确定", width=10, command=self.ok, default=tk.ACTIVE).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(box, text="取消", width=10, command=self.cancel).pack(side=tk.LEFT, padx=5, pady=5)
        self.bind("<Escape>", self.cancel)
        box.pack()

    def cancel(self):
        self.on_entry_blur(None)
        super().cancel()

    def ok(self, event=None):
        self.on_entry_blur(None)
        super().ok(event)

    def reset_to_defaults(self):
        if messagebox.askyesno("确认", "确定要将所有快捷键重置为默认设置吗？", parent=self):
            for action, key_sequence in DEFAULT_KEYBINDINGS.items():
                if action in self.key_vars:
                    self.key_vars[action].set(key_sequence)

    def apply(self):
        new_bindings = {}
        for action, key_var in self.key_vars.items():
            new_bindings[action] = key_var.get().strip()
        self.app.config['keybindings'] = new_bindings
        self.app.save_config()
        self.app._setup_keybindings()
        self.app.update_menu_accelerators()
        self.app.update_statusbar("快捷键已更新。")