import tkinter as tk
from tkinter import ttk, simpledialog, messagebox, filedialog
import json
import uuid
from copy import deepcopy
from utils.constants import PROMPT_PRESET_EXTENSION, DEFAULT_PROMPT_STRUCTURE, STRUCTURAL, STATIC, DYNAMIC


class PromptManagerDialog(tk.Toplevel):
    def __init__(self, parent, title, app_instance):
        super().__init__(parent)
        self.app = app_instance
        self.prompt_structure = deepcopy(self.app.config.get("ai_prompt_structure", DEFAULT_PROMPT_STRUCTURE))
        self.drag_data = {"item": None, "y": 0}
        self.result = None

        self.withdraw()
        if parent.winfo_viewable():
            self.transient(parent)
        if title:
            self.title(title)

        self.parent = parent
        self.geometry("1000x700")

        main_container = ttk.Frame(self)
        main_container.pack(expand=True, fill=tk.BOTH, padx=5, pady=5)
        main_container.grid_rowconfigure(0, weight=1)
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
        toolbar.grid(row=1, column=0, sticky="ew", padx=5, pady=5)

        ttk.Button(toolbar, text="新增", command=self.add_item).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="删除选中", command=self.delete_item).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="恢复默认", command=self.reset_to_defaults).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="导入预设", command=self.import_preset).pack(side=tk.RIGHT, padx=2)
        ttk.Button(toolbar, text="导出预设", command=self.export_preset).pack(side=tk.RIGHT, padx=2)

        tree_frame = ttk.Frame(master)
        tree_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        cols = ("enabled", "type", "content")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        self.tree.heading("enabled", text="启用")
        self.tree.heading("type", text="类型")
        self.tree.heading("content", text="内容")

        self.tree.column("enabled", width=50, anchor=tk.CENTER, stretch=False)
        self.tree.column("type", width=100, anchor=tk.W, stretch=False)
        self.tree.column("content", width=600)

        self.tree.bind("<Double-1>", self.edit_item)
        self.tree.bind("<ButtonPress-1>", self.on_press)
        self.tree.bind("<B1-Motion>", self.on_motion)
        self.tree.bind("<ButtonRelease-1>", self.on_release)

        self.populate_tree()
        return self.tree

    def populate_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for part in self.prompt_structure:
            enabled_char = "✔" if part.get("enabled", True) else "✖"
            self.tree.insert("", "end", iid=part["id"], values=(enabled_char, part["type"], part["content"]))

    def on_press(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.drag_data["item"] = item
            self.drag_data["y"] = event.y

    def on_motion(self, event):
        dragged_item = self.drag_data.get("item")
        if not dragged_item:
            return

        target_item = self.tree.identify_row(event.y)

        if target_item and target_item != dragged_item:
            self.tree.move(dragged_item, "", self.tree.index(target_item))

    def on_release(self, event):
        if not self.drag_data["item"]:
            return
        new_order_ids = self.tree.get_children()
        self.prompt_structure.sort(key=lambda p: new_order_ids.index(p["id"]))
        self.drag_data["item"] = None

    def add_item(self):
        new_part = {"id": str(uuid.uuid4()), "type": STATIC, "enabled": True, "content": "新指令"}
        self.prompt_structure.append(new_part)
        self.populate_tree()
        self.tree.selection_set(new_part["id"])
        self.tree.see(new_part["id"])

    def delete_item(self):
        selected_id = self.tree.selection()
        if not selected_id:
            return
        selected_id = selected_id[0]
        self.prompt_structure = [p for p in self.prompt_structure if p["id"] != selected_id]
        self.populate_tree()

    def edit_item(self, event):
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return

        part_to_edit = next((p for p in self.prompt_structure if p["id"] == item_id), None)
        if not part_to_edit:
            return

        dialog = PromptItemEditor(self, "编辑提示词片段", part_to_edit)
        if dialog.result:
            part_to_edit.update(dialog.result)
            self.populate_tree()

    def reset_to_defaults(self):
        if messagebox.askyesno("确认", "确定要将提示词恢复为默认设置吗？\n当前所有自定义内容将丢失。", parent=self):
            self.prompt_structure = deepcopy(DEFAULT_PROMPT_STRUCTURE)
            self.populate_tree()

    def import_preset(self):
        filepath = filedialog.askopenfilename(
            title="导入提示词预设",
            filetypes=(("Overwatch Prompt Files", f"*{PROMPT_PRESET_EXTENSION}"), ("All Files", "*.*")),
            defaultextension=PROMPT_PRESET_EXTENSION,
            parent=self
        )
        if not filepath: return
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                preset = json.load(f)
            if isinstance(preset, list) and all("content" in p for p in preset):
                self.prompt_structure = preset
                self.populate_tree()
                messagebox.showinfo("成功", "预设已成功导入。", parent=self)
            else:
                messagebox.showerror("错误", "预设文件格式不正确。", parent=self)
        except Exception as e:
            messagebox.showerror("导入失败", f"无法加载预设文件: {e}", parent=self)

    def export_preset(self):
        filepath = filedialog.asksaveasfilename(
            title="导出提示词预设",
            filetypes=(("Overwatch Prompt Files", f"*{PROMPT_PRESET_EXTENSION}"), ("All Files", "*.*")),
            defaultextension=PROMPT_PRESET_EXTENSION,
            initialfile="my_prompt_preset.owprompt",
            parent=self
        )
        if not filepath: return
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.prompt_structure, f, indent=4, ensure_ascii=False)
            messagebox.showinfo("成功", "预设已成功导出。", parent=self)
        except Exception as e:
            messagebox.showerror("导出失败", f"无法保存预设文件: {e}", parent=self)

    def buttonbox(self, master):
        box = ttk.Frame(master)
        ttk.Button(box, text="确定", width=10, command=self.ok, default=tk.ACTIVE).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(box, text="取消", width=10, command=self.cancel).pack(side=tk.LEFT, padx=5, pady=5)
        box.grid(row=2, column=0, sticky="e", padx=5, pady=5)

    def ok(self, event=None):
        self.apply()
        self.destroy()

    def cancel(self, event=None):
        self.destroy()

    def apply(self):
        self.app.config["ai_prompt_structure"] = self.prompt_structure
        self.app.save_config()
        self.app.update_statusbar("AI提示词结构已更新。")


class PromptItemEditor(simpledialog.Dialog):
    def __init__(self, parent, title, initial_data):
        self.initial_data = initial_data
        super().__init__(parent, title)

    def body(self, master):
        self.geometry("600x400")
        master.rowconfigure(1, weight=1)
        master.columnconfigure(1, weight=1)

        ttk.Label(master, text="类型:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.type_var = tk.StringVar(value=self.initial_data["type"])
        type_menu = ttk.Combobox(master, textvariable=self.type_var, values=[STRUCTURAL, STATIC, DYNAMIC],
                                 state="readonly")
        type_menu.grid(row=0, column=1, sticky="ew", padx=5, pady=5)

        self.enabled_var = tk.BooleanVar(value=self.initial_data.get("enabled", True))
        enabled_check = ttk.Checkbutton(master, text="启用此片段", variable=self.enabled_var)
        enabled_check.grid(row=0, column=2, padx=5, pady=5)

        ttk.Label(master, text="内容:").grid(row=1, column=0, sticky="nw", padx=5, pady=5)
        self.content_text = tk.Text(master, wrap=tk.WORD, height=10)
        self.content_text.grid(row=1, column=1, columnspan=2, sticky="nsew", padx=5, pady=5)
        self.content_text.insert("1.0", self.initial_data["content"])

        return self.content_text

    def apply(self):
        self.result = {
            "type": self.type_var.get(),
            "enabled": self.enabled_var.get(),
            "content": self.content_text.get("1.0", tk.END).strip()
        }