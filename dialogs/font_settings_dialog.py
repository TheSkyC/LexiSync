# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import tkinter as tk
from tkinter import ttk, font, messagebox
from utils.localization import _
from utils.config_manager import get_default_font_settings


class FontSettingsDialog(tk.Toplevel):
    def __init__(self, parent, title, app_instance):
        super().__init__(parent)
        self.app = app_instance
        self.config = app_instance.config
        self.font_settings_buffer = self.config["font_settings"].copy()

        self.withdraw()
        self.transient(parent)
        self.title(title)
        self.geometry("600x450")

        self.available_fonts = sorted([f for f in font.families() if not f.startswith('@')])

        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(expand=True, fill="both")

        self.create_widgets(main_frame)
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.deiconify()
        self.wait_window(self)

    def create_widgets(self, master):
        self.override_var = tk.BooleanVar(value=self.font_settings_buffer["override_default_fonts"])
        override_check = ttk.Checkbutton(master, text=_("Override default font settings"), variable=self.override_var,
                                         command=self.toggle_controls)
        override_check.pack(anchor="w", pady=(0, 10))

        self.notebook = ttk.Notebook(master)
        self.notebook.pack(expand=True, fill="both")

        self.script_tabs = {}
        scripts = self.font_settings_buffer["scripts"]
        for script_name, settings in scripts.items():
            frame = ttk.Frame(self.notebook, padding="10")
            self.notebook.add(frame, text=script_name.capitalize())
            self.create_font_selector(frame, script_name, settings)

        code_frame = ttk.Frame(self.notebook, padding="10")
        self.create_font_selector(code_frame, "code_context", self.font_settings_buffer["code_context"])

        button_frame = ttk.Frame(master)
        button_frame.pack(fill="x", pady=(10, 0))

        ttk.Button(button_frame, text=_("Reset to Defaults"), command=self.reset_to_defaults).pack(side="left")
        ttk.Button(button_frame, text=_("OK"), command=self.ok).pack(side="right", padx=5)
        ttk.Button(button_frame, text=_("Cancel"), command=self.cancel).pack(side="right")

        self.toggle_controls()

    def create_font_selector(self, parent, script_name, settings):
        parent.columnconfigure(1, weight=1)
        ttk.Label(parent, text=_("Font Family:")).grid(row=0, column=0, sticky="w", pady=5)
        family_var = tk.StringVar(value=settings["family"])
        family_combo = ttk.Combobox(parent, textvariable=family_var, values=self.available_fonts)
        family_combo.grid(row=0, column=1, sticky="ew", padx=5)

        ttk.Label(parent, text=_("Size:")).grid(row=1, column=0, sticky="w", pady=5)
        size_var = tk.IntVar(value=settings["size"])
        size_spin = ttk.Spinbox(parent, from_=6, to=72, textvariable=size_var, width=5)
        size_spin.grid(row=1, column=1, sticky="w", padx=5)

        ttk.Label(parent, text=_("Style:")).grid(row=2, column=0, sticky="w", pady=5)
        style_var = tk.StringVar(value=settings["style"])
        style_combo = ttk.Combobox(parent, textvariable=style_var, values=["normal", "bold", "italic", "bold italic"],
                                   state="readonly", width=12)
        style_combo.grid(row=2, column=1, sticky="w", padx=5)

        self.script_tabs[script_name] = {
            "frame": parent,
            "family": family_var,
            "size": size_var,
            "style": style_var
        }

    def toggle_controls(self):
        state = "normal" if self.override_var.get() else "disabled"
        for child in self.notebook.winfo_children():
            for widget in child.winfo_children():
                widget.configure(state=state)

    def reset_to_defaults(self):
        if messagebox.askyesno(_("Confirmation"), _("Reset all font settings to default?"), parent=self):
            default_settings = get_default_font_settings()
            self.font_settings_buffer = default_settings.copy()
            self.override_var.set(default_settings["override_default_fonts"])
            for script, controls in self.script_tabs.items():
                if script in default_settings["scripts"]:
                    settings = default_settings["scripts"][script]
                elif script == "code_context":
                    settings = default_settings["code_context"]
                else:
                    continue
                controls["family"].set(settings["family"])
                controls["size"].set(settings["size"])
                controls["style"].set(settings["style"])
            self.toggle_controls()

    def apply(self):
        new_settings = self.font_settings_buffer.copy()
        new_settings["override_default_fonts"] = self.override_var.get()
        for script, controls in self.script_tabs.items():
            if script in new_settings["scripts"]:
                target = new_settings["scripts"][script]
            elif script == "code_context":
                target = new_settings["code_context"]
            else:
                continue
            target["family"] = controls["family"].get()
            target["size"] = controls["size"].get()
            target["style"] = controls["style"].get()

        self.config["font_settings"] = new_settings
        self.app.save_config()
        messagebox.showinfo(_("Restart Required"),
                            _("Font settings have been changed. Please restart the application for the changes to take effect."),
                            parent=self)
        return True

    def ok(self):
        if self.apply():
            self.destroy()

    def cancel(self):
        self.destroy()