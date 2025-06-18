# dialogs/extraction_pattern_dialog.py
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox, filedialog
import json
import uuid
from copy import deepcopy
from utils.constants import EXTRACTION_PATTERN_PRESET_EXTENSION, DEFAULT_EXTRACTION_PATTERNS


class ExtractionPatternManagerDialog(tk.Toplevel):
    def __init__(self, parent, title, app_instance):
        super().__init__(parent)
        self.app = app_instance
        # Deepcopy to allow cancellation without affecting app.config immediately
        self.patterns_buffer = deepcopy(self.app.config.get("extraction_patterns", DEFAULT_EXTRACTION_PATTERNS))
        self.drag_data = {"item": None, "y": 0}
        self.result = None  # To indicate if changes were applied

        self.withdraw()
        if parent.winfo_viewable():
            self.transient(parent)
        if title:
            self.title(title)

        self.parent = parent
        self.geometry("800x600")

        main_container = ttk.Frame(self)
        main_container.pack(expand=True, fill=tk.BOTH, padx=5, pady=5)
        main_container.grid_rowconfigure(0, weight=1)  # Treeview area
        main_container.grid_rowconfigure(1, weight=0)  # Toolbar
        main_container.grid_rowconfigure(2, weight=0)  # Buttonbox
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

        ttk.Button(toolbar, text="新增", command=self.add_item).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="删除选中", command=self.delete_item).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="恢复默认", command=self.reset_to_defaults).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="导入预设", command=self.import_preset).pack(side=tk.RIGHT, padx=2)
        ttk.Button(toolbar, text="导出预设", command=self.export_preset).pack(side=tk.RIGHT, padx=2)

        tree_frame = ttk.Frame(master)
        tree_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        cols = ("enabled", "name", "string_type", "regex_pattern")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        self.tree.heading("enabled", text="启用")
        self.tree.heading("name", text="规则名称")
        self.tree.heading("string_type", text="字符串类型")
        self.tree.heading("regex_pattern", text="正则表达式")

        self.tree.column("enabled", width=50, anchor=tk.CENTER, stretch=False)
        self.tree.column("name", width=150, anchor=tk.W)
        self.tree.column("string_type", width=150, anchor=tk.W)
        self.tree.column("regex_pattern", width=400)

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
                pattern.get("name", "未命名规则"),
                pattern.get("string_type", "Custom"),
                pattern.get("regex_pattern_str", "")
            ))

    def on_press(self, event):
        item_iid = self.tree.identify_row(event.y)
        if item_iid:
            self.drag_data["item_iid"] = item_iid
            self.drag_data["y"] = event.y
            # Store index for reordering data list
            self.drag_data["index"] = self.tree.index(item_iid)

    def on_motion(self, event):
        dragged_item_iid = self.drag_data.get("item_iid")
        if not dragged_item_iid:
            return

        target_item_iid = self.tree.identify_row(event.y)
        if target_item_iid and target_item_iid != dragged_item_iid:
            # Move in tree for visual feedback
            self.tree.move(dragged_item_iid, "", self.tree.index(target_item_iid))

    def on_release(self, event):
        if not self.drag_data.get("item_iid"):
            return

        # Update the self.patterns_buffer based on the new order in the tree
        new_order_ids = self.tree.get_children()  # These are UUIDs

        # Create a map for quick lookup of pattern objects by ID
        patterns_map = {p["id"]: p for p in self.patterns_buffer}

        # Rebuild self.patterns_buffer in the new order
        self.patterns_buffer = [patterns_map[iid] for iid in new_order_ids if iid in patterns_map]

        self.drag_data["item_iid"] = None  # Reset drag data
        # No need to call populate_tree here as the tree itself reflects the order

    def add_item(self):
        new_pattern = {
            "id": str(uuid.uuid4()),
            "name": "新规则",
            "enabled": True,
            "string_type": "Custom",
            "regex_pattern_str": ""
        }
        # Add to buffer first
        self.patterns_buffer.append(new_pattern)
        # Then update tree
        self.populate_tree()  # Repopulate to ensure correct order if items were dragged
        self.tree.selection_set(new_pattern["id"])
        self.tree.see(new_pattern["id"])
        self.edit_item_by_id(new_pattern["id"])  # Open editor for new item

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

        dialog = ExtractionPatternItemEditor(self, "编辑提取规则", pattern_to_edit)
        if dialog.result:  # dialog.result contains the updated pattern data
            # Update the item in the buffer
            for i, p_item in enumerate(self.patterns_buffer):
                if p_item["id"] == item_id:
                    self.patterns_buffer[i] = dialog.result  # dialog.result should include the id
                    break
            self.populate_tree()

    def edit_item(self, event):  # Called on double-click
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return
        self.edit_item_by_id(item_id)

    def reset_to_defaults(self):
        if messagebox.askyesno("确认", "确定要将提取规则恢复为默认设置吗？\n当前所有自定义规则将丢失。", parent=self):
            self.patterns_buffer = deepcopy(DEFAULT_EXTRACTION_PATTERNS)
            self.populate_tree()

    def import_preset(self):
        filepath = filedialog.askopenfilename(
            title="导入提取规则预设",
            filetypes=(
            ("Overwatch Extraction Pattern Files", f"*{EXTRACTION_PATTERN_PRESET_EXTENSION}"), ("All Files", "*.*")),
            defaultextension=EXTRACTION_PATTERN_PRESET_EXTENSION,
            parent=self
        )
        if not filepath: return
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                preset = json.load(f)
            # Basic validation
            if isinstance(preset, list) and all("name" in p and "regex_pattern_str" in p for p in preset):
                # Ensure all items have IDs, generate if missing (for older presets)
                for p_item in preset:
                    if "id" not in p_item:
                        p_item["id"] = str(uuid.uuid4())
                    if "enabled" not in p_item:  # ensure enabled field
                        p_item["enabled"] = True
                    if "string_type" not in p_item:
                        p_item["string_type"] = "Custom"

                self.patterns_buffer = preset
                self.populate_tree()
                messagebox.showinfo("成功", "预设已成功导入。", parent=self)
            else:
                messagebox.showerror("错误", "预设文件格式不正确。", parent=self)
        except Exception as e:
            messagebox.showerror("导入失败", f"无法加载预设文件: {e}", parent=self)

    def export_preset(self):
        filepath = filedialog.asksaveasfilename(
            title="导出提取规则预设",
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
            messagebox.showinfo("成功", "预设已成功导出。", parent=self)
        except Exception as e:
            messagebox.showerror("导出失败", f"无法保存预设文件: {e}", parent=self)

    def buttonbox(self, master):
        box = ttk.Frame(master)
        ttk.Button(box, text="确定", width=10, command=self.ok, default=tk.ACTIVE).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(box, text="取消", width=10, command=self.cancel).pack(side=tk.LEFT, padx=5, pady=5)
        box.grid(row=2, column=0, sticky="e", padx=5, pady=5)

    def ok(self, event=None):
        self.apply_changes()
        self.destroy()

    def cancel(self, event=None):
        self.result = None  # Indicate no changes applied
        self.destroy()

    def apply_changes(self):
        # Only save if there's a change from the original config
        if self.patterns_buffer != self.app.config.get("extraction_patterns", DEFAULT_EXTRACTION_PATTERNS):
            self.app.config["extraction_patterns"] = deepcopy(self.patterns_buffer)
            self.app.save_config()
            self.app.update_statusbar("提取规则已更新。建议重新加载翻译文本。")
            self.result = True  # Indicate changes were applied
        else:
            self.result = False


class ExtractionPatternItemEditor(simpledialog.Dialog):
    def __init__(self, parent, title, initial_data):
        self.initial_data = initial_data  # This should include the 'id'
        super().__init__(parent, title)

    def body(self, master):
        self.geometry("700x350")  # Adjusted size
        master.columnconfigure(1, weight=1)
        master.rowconfigure(3, weight=1)  # Regex pattern text area

        # Name
        ttk.Label(master, text="规则名称:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.name_var = tk.StringVar(value=self.initial_data.get("name", ""))
        name_entry = ttk.Entry(master, textvariable=self.name_var)
        name_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=5)

        # Enabled Checkbox (moved next to name for better layout)
        self.enabled_var = tk.BooleanVar(value=self.initial_data.get("enabled", True))
        enabled_check = ttk.Checkbutton(master, text="启用此规则", variable=self.enabled_var)
        enabled_check.grid(row=0, column=2, padx=5, pady=5, sticky="w")

        # String Type
        ttk.Label(master, text="字符串类型:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.string_type_var = tk.StringVar(value=self.initial_data.get("string_type", "Custom"))
        string_type_entry = ttk.Entry(master, textvariable=self.string_type_var)
        string_type_entry.grid(row=1, column=1, columnspan=2, sticky="ew", padx=5, pady=5)
        ttk.Label(master, text="(用于TranslatableString分类)").grid(row=2, column=1, columnspan=2, sticky="w", padx=5,
                                                                    pady=2)

        # Regex Pattern
        ttk.Label(master, text="正则表达式:").grid(row=3, column=0, sticky="nw", padx=5, pady=5)
        self.regex_text = tk.Text(master, wrap=tk.WORD, height=8)  # Increased height
        self.regex_text.grid(row=3, column=1, columnspan=2, sticky="nsew", padx=5, pady=5)
        self.regex_text.insert("1.0", self.initial_data.get("regex_pattern_str", ""))

        # Regex help/info
        regex_info = "示例: (?:自定义字符串|Custom String)\\s*\\(\\s*\\\"  (必须以捕获引号前的部分结束，如 \\s*\\(\\s*\\\")"
        ttk.Label(master, text=regex_info, wraplength=450, justify=tk.LEFT).grid(row=4, column=1, columnspan=2,
                                                                                 sticky="w", padx=5, pady=2)

        return name_entry  # Initial focus

    def apply(self):
        # This method is called by simpledialog.Dialog's ok()
        # It should set self.result with the data to be returned
        self.result = {
            "id": self.initial_data["id"],  # Preserve the ID
            "name": self.name_var.get().strip(),
            "enabled": self.enabled_var.get(),
            "string_type": self.string_type_var.get().strip() or "Custom",
            "regex_pattern_str": self.regex_text.get("1.0", tk.END).strip()
        }
        if not self.result["name"]:
            messagebox.showerror("错误", "规则名称不能为空。", parent=self)
            self.result = None  # Prevent dialog from closing
            return
        if not self.result["regex_pattern_str"]:
            messagebox.showerror("错误", "正则表达式不能为空。", parent=self)
            self.result = None
            return