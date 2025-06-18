# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import tkinter as tk
from tkinter import ttk, simpledialog, messagebox, filedialog
import json
import uuid
import re
from copy import deepcopy
from utils.constants import EXTRACTION_PATTERN_PRESET_EXTENSION, DEFAULT_EXTRACTION_PATTERNS
from utils.localization import setup_translation, get_available_languages, _

class ExtractionPatternManagerDialog(tk.Toplevel):
    def __init__(self, parent, title, app_instance):
        super().__init__(parent)
        self.app = app_instance
        self.patterns_buffer = deepcopy(self.app.config.get("extraction_patterns", DEFAULT_EXTRACTION_PATTERNS))
        self.drag_data = {"item": None, "y": 0}
        self.result = None

        self.withdraw()
        if parent.winfo_viewable():
            self.transient(parent)
        if title:
            self.title(title)

        self.parent = parent
        self.geometry("900x600")

        main_container = ttk.Frame(self)
        main_container.pack(expand=True, fill=tk.BOTH, padx=5, pady=5)
        main_container.grid_rowconfigure(0, weight=1)
        main_container.grid_rowconfigure(1, weight=0)
        main_container.grid_rowconfigure(2, weight=0)
        main_container.grid_columnconfigure(0, weight=1)

        self.initial_focus = self.body(main_container)
        self.buttonbox(main_container)

        self.protocol("WM_DELETE_WINDOW", self.cancel)
        if self.parent is not None:
            self.geometry(f"+{parent.winfo_rootx() + 50}+{parent.winfo_rooty() + 50}")

        self.deiconify()
        if self.initial_focus:
            self.initial_focus.focus_set()

        self.wait_visibility()
        self.grab_set()
        self.wait_window(self)

    def body(self, master):
        toolbar = ttk.Frame(master)
        toolbar.grid(row=1, column=0, sticky="ew", padx=5, pady=(5, 0))
        ttk.Button(toolbar, text=_("Add"), command=self.add_item).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text=_("Delete Selected"), command=self.delete_item).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text=_("Reset to Defaults"), command=self.reset_to_defaults).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text=_("Import Preset"), command=self.import_preset).pack(side=tk.RIGHT, padx=2)
        ttk.Button(toolbar, text=_("Export Preset"), command=self.export_preset).pack(side=tk.RIGHT, padx=2)

        tree_frame = ttk.Frame(master)
        tree_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        cols = ("enabled", "name", "string_type", "left_delimiter", "right_delimiter")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        self.tree.heading("enabled", text=_("Enabled"))
        self.tree.heading("name", text=_("Rule Name"))
        self.tree.heading("string_type", text=_("String Type"))
        self.tree.heading("left_delimiter", text=_("Left Delimiter (Regex)"))
        self.tree.heading("right_delimiter", text=_("Right Delimiter (Regex)"))

        self.tree.column("enabled", width=50, anchor=tk.CENTER, stretch=False)
        self.tree.column("name", width=150, anchor=tk.W)
        self.tree.column("string_type", width=150, anchor=tk.W)
        self.tree.column("left_delimiter", width=250)
        self.tree.column("right_delimiter", width=100)

        self.tree.bind("<Double-1>", self.edit_item)
        self.tree.bind("<ButtonPress-1>", self.on_press)
        self.tree.bind("<B1-Motion>", self.on_motion)
        self.tree.bind("<ButtonRelease-1>", self.on_release)

        self.populate_tree()
        return self.tree

    def populate_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for pattern in self.patterns_buffer:
            enabled_char = "✔" if pattern.get("enabled", True) else "✖"
            self.tree.insert("", "end", iid=pattern["id"], values=(
                enabled_char,
                pattern.get("name", _("Unnamed Rule")),
                pattern.get("string_type", _("Custom")),
                pattern.get("left_delimiter", ""),
                pattern.get("right_delimiter", "")
            ))

    def on_press(self, event):
        item_iid = self.tree.identify_row(event.y)
        if item_iid:
            self.drag_data["item_iid"] = item_iid
            self.drag_data["y"] = event.y
            self.drag_data["index"] = self.tree.index(item_iid)

    def on_motion(self, event):
        dragged_item_iid = self.drag_data.get("item_iid")
        if not dragged_item_iid:
            return
        target_item_iid = self.tree.identify_row(event.y)
        if target_item_iid and target_item_iid != dragged_item_iid:
            self.tree.move(dragged_item_iid, "", self.tree.index(target_item_iid))

    def on_release(self, event):
        if not self.drag_data.get("item_iid"):
            return
        new_order_ids = self.tree.get_children()
        patterns_map = {p["id"]: p for p in self.patterns_buffer}
        self.patterns_buffer = [patterns_map[iid] for iid in new_order_ids if iid in patterns_map]
        self.drag_data["item_iid"] = None

    def add_item(self):
        new_pattern = {
            "id": str(uuid.uuid4()),
            "name": _("New Rule"),
            "enabled": True,
            "string_type": _("Custom"),
            "left_delimiter": "",
            "right_delimiter": '"'
        }

        dialog = ExtractionPatternItemEditor(self, _("Add Extraction Rule"), new_pattern)
        if dialog.result:
            self.patterns_buffer.append(dialog.result)
            self.populate_tree()
            self.tree.selection_set(dialog.result["id"])
            self.tree.see(dialog.result["id"])

    def delete_item(self):
        selected_id_tuple = self.tree.selection()
        if not selected_id_tuple:
            return
        selected_id = selected_id_tuple[0]
        self.patterns_buffer = [p for p in self.patterns_buffer if p["id"] != selected_id]
        self.populate_tree()

    def edit_item_by_id(self, item_id):
        pattern_to_edit = next((p for p in self.patterns_buffer if p["id"] == item_id), None)
        if not pattern_to_edit:
            return

        dialog = ExtractionPatternItemEditor(self, _("Edit Extraction Rule"), pattern_to_edit)
        if dialog.result:
            for i, p_item in enumerate(self.patterns_buffer):
                if p_item["id"] == item_id:
                    self.patterns_buffer[i] = dialog.result
                    break
            self.populate_tree()

    def edit_item(self, event):
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return
        self.edit_item_by_id(item_id)

    def reset_to_defaults(self):
        if messagebox.askyesno(_("Confirm"), _("Are you sure you want to reset extraction rules to their default settings?\nAll current custom rules will be lost."), parent=self):
            self.patterns_buffer = deepcopy(DEFAULT_EXTRACTION_PATTERNS)
            self.populate_tree()

    def import_preset(self):
        filepath = filedialog.askopenfilename(
            title=_("Import Extraction Rule Preset"),
            filetypes=(
            ("Overwatch Extraction Pattern Files", f"*{EXTRACTION_PATTERN_PRESET_EXTENSION}"), ("All Files", "*.*")),
            defaultextension=EXTRACTION_PATTERN_PRESET_EXTENSION,
            parent=self
        )
        if not filepath: return
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                preset = json.load(f)
            if isinstance(preset, list) and all("name" in p and "left_delimiter" in p for p in preset):
                for p_item in preset:
                    if "id" not in p_item: p_item["id"] = str(uuid.uuid4())
                    if "enabled" not in p_item: p_item["enabled"] = True
                    if "string_type" not in p_item: p_item["string_type"] = _("Custom")
                    if "right_delimiter" not in p_item: p_item["right_delimiter"] = '"'
                self.patterns_buffer = preset
                messagebox.showinfo(_("Success"), _("Preset imported successfully."), parent=self)
                self.populate_tree()
            else:
                messagebox.showerror(_("Error"), _("Preset file format is incorrect."), parent=self)
        except Exception as e:
            messagebox.showerror(_("Import Failed"), _("Could not load preset file: {error}").format(error=e), parent=self)

    def export_preset(self):
        filepath = filedialog.asksaveasfilename(
            title=_("Export Extraction Rule Preset"),
            filetypes=(
            ("Overwatch Extraction Pattern Files", f"*{EXTRACTION_PATTERN_PRESET_EXTENSION}"), ("All Files", "*.*")),
            defaultextension=EXTRACTION_PATTERN_PRESET_EXTENSION,
            initialfile="my_extraction_patterns.owextract",
            parent=self
        )
        if not filepath: return
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.patterns_buffer, f, indent=4, ensure_ascii=False)
            messagebox.showinfo(_("Success"), _("Preset exported successfully."), parent=self)
        except Exception as e:
            messagebox.showerror(_("Export Failed"), _("Could not save preset file: {error}").format(error=e), parent=self)

    def buttonbox(self, master):
        box = ttk.Frame(master)
        ttk.Button(box, text=_("OK"), width=10, command=self.ok, default=tk.ACTIVE).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(box, text=_("Cancel"), width=10, command=self.cancel).pack(side=tk.LEFT, padx=5, pady=5)
        box.grid(row=2, column=0, sticky="e", padx=5, pady=5)

    def ok(self, event=None):
        self.apply_changes()
        self.destroy()

    def cancel(self, event=None):
        self.result = None
        self.destroy()

    def apply_changes(self):
        if self.patterns_buffer != self.app.config.get("extraction_patterns", DEFAULT_EXTRACTION_PATTERNS):
            self.app.config["extraction_patterns"] = deepcopy(self.patterns_buffer)
            self.app.save_config()
            self.app.update_statusbar(_("Extraction rules updated. Consider reloading the text."))
            self.result = True
        else:
            self.result = False


class ExtractionPatternItemEditor(simpledialog.Dialog):
    def __init__(self, parent, title, initial_data):
        self.initial_data = initial_data
        super().__init__(parent, title)

    def body(self, master):
        self.geometry("700x350")
        master.columnconfigure(1, weight=1)

        ttk.Label(master, text=_("Rule Name:")).grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.name_var = tk.StringVar(value=self.initial_data.get("name", ""))
        name_entry = ttk.Entry(master, textvariable=self.name_var)
        name_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=5)

        self.enabled_var = tk.BooleanVar(value=self.initial_data.get("enabled", True))
        ttk.Checkbutton(master, text=_("Enable this rule"), variable=self.enabled_var).grid(row=0, column=2, padx=5, pady=5,
                                                                                   sticky="w")

        ttk.Label(master, text=_("String Type:")).grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.string_type_var = tk.StringVar(value=self.initial_data.get("string_type", _("Custom")))
        ttk.Entry(master, textvariable=self.string_type_var).grid(row=1, column=1, columnspan=2, sticky="ew", padx=5,
                                                                  pady=5)

        ttk.Label(master, text=_("Left Delimiter:")).grid(row=2, column=0, sticky="nw", padx=5, pady=5)
        self.left_text = tk.Text(master, wrap=tk.WORD, height=4)
        self.left_text.grid(row=2, column=1, columnspan=2, sticky="nsew", padx=5, pady=5)
        self.left_text.insert("1.0", self.initial_data.get("left_delimiter", ""))

        ttk.Label(master, text=_("Right Delimiter:")).grid(row=3, column=0, sticky="nw", padx=5, pady=5)
        self.right_text = tk.Text(master, wrap=tk.WORD, height=4)
        self.right_text.grid(row=3, column=1, columnspan=2, sticky="nsew", padx=5, pady=5)
        self.right_text.insert("1.0", self.initial_data.get("right_delimiter", ""))

        button_frame = ttk.Frame(master)
        button_frame.grid(row=4, column=1, columnspan=2, sticky="w", padx=5)
        ttk.Button(button_frame, text=_("Escape for Regex (Left)"), command=lambda: self.convert_to_regex('left')).pack(side=tk.LEFT)
        ttk.Button(button_frame, text=_("Escape for Regex (Right)"), command=lambda: self.convert_to_regex('right')).pack(
            side=tk.LEFT, padx=5)

        return name_entry

    def convert_to_regex(self, target):
        widget = self.left_text if target == 'left' else self.right_text
        current_text = widget.get("1.0", tk.END).strip()
        escaped_text = re.escape(current_text)
        widget.delete("1.0", tk.END)
        widget.insert("1.0", escaped_text)

    def apply(self):
        self.result = {
            "id": self.initial_data["id"],
            "name": self.name_var.get().strip(),
            "enabled": self.enabled_var.get(),
            "string_type": self.string_type_var.get().strip() or _("Custom"),
            "left_delimiter": self.left_text.get("1.0", tk.END).strip(),
            "right_delimiter": self.right_text.get("1.0", tk.END).strip()
        }
        if not self.result["name"]:
            messagebox.showerror(_("Error"), _("Rule name cannot be empty."), parent=self)
            self.result = None
            return
        if not self.result["left_delimiter"] or not self.result["right_delimiter"]:
            messagebox.showerror(_("Error"), _("Left and right delimiters cannot be empty."), parent=self)
            self.result = None
            return