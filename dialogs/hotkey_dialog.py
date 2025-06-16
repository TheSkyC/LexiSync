import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
from utils import constants


class HotkeyDialog(simpledialog.Dialog):
    def __init__(self, parent, title, config_manager, hotkey_actions, rebind_callback):
        self.config_manager = config_manager
        self.hotkey_actions = hotkey_actions
        self.rebind_callback = rebind_callback
        self.hotkey_vars = {}
        super().__init__(parent, title)

    def body(self, master):
        master.columnconfigure(1, weight=1)

        ttk.Label(master, text="Action", font=('Segoe UI', 10, 'bold')).grid(row=0, column=0, padx=5, pady=5,
                                                                             sticky='w')
        ttk.Label(master, text="Hotkey", font=('Segoe UI', 10, 'bold')).grid(row=0, column=1, padx=5, pady=5,
                                                                             sticky='w')

        current_hotkeys = self.config_manager.get('hotkeys', constants.DEFAULT_HOTKEYS)

        for i, (action_id, action_name) in enumerate(self.hotkey_actions.items()):
            ttk.Label(master, text=action_name).grid(row=i + 1, column=0, padx=10, pady=3, sticky='w')

            hotkey_var = tk.StringVar(value=current_hotkeys.get(action_id, ""))
            self.hotkey_vars[action_id] = hotkey_var

            entry = ttk.Entry(master, textvariable=hotkey_var, width=30)
            entry.grid(row=i + 1, column=1, padx=5, pady=3, sticky='ew')

        return entry

    def buttonbox(self):
        box = ttk.Frame(self)
        ttk.Button(box, text="Reset to Defaults", command=self.reset_to_defaults).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(box, text="OK", width=10, command=self.ok, default=tk.ACTIVE).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(box, text="Cancel", width=10, command=self.cancel).pack(side=tk.LEFT, padx=5, pady=5)
        self.bind("<Return>", lambda e: self.ok())
        self.bind("<Escape>", lambda e: self.cancel())
        box.pack()

    def reset_to_defaults(self):
        if messagebox.askyesno("Confirm Reset", "Are you sure you want to reset all hotkeys to their default values?",
                               parent=self):
            for action_id, var in self.hotkey_vars.items():
                var.set(constants.DEFAULT_HOTKEYS.get(action_id, ""))

    def apply(self):
        new_hotkeys = {}
        for action_id, var in self.hotkey_vars.items():
            new_hotkeys[action_id] = var.get().strip()

        self.config_manager.set('hotkeys', new_hotkeys)
        self.rebind_callback()