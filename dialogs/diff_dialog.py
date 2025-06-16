import tkinter as tk
from tkinter import ttk, simpledialog


class DiffDialog(simpledialog.Dialog):
    def __init__(self, parent, title, diff_results):
        self.diff_results = diff_results
        super().__init__(parent, title)

    def body(self, master):
        self.geometry("1200x700")

        # --- Configure grid weights for the master frame ---
        master.rowconfigure(0, weight=1)
        master.columnconfigure(0, weight=1)

        tree_frame = ttk.Frame(master)
        tree_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # --- Configure grid weights for the tree_frame ---
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        cols = ("status", "old_text", "new_text", "similarity")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        self.tree.heading("status", text="状态")
        self.tree.heading("old_text", text="旧版原文")
        self.tree.heading("new_text", text="新版原文")
        self.tree.heading("similarity", text="相似度")

        self.tree.column("status", width=80, anchor=tk.W)
        self.tree.column("old_text", width=500, anchor=tk.W)
        self.tree.column("new_text", width=500, anchor=tk.W)
        self.tree.column("similarity", width=80, anchor=tk.CENTER)

        self.tree.tag_configure('added', background='#DFF0D8', foreground='#3C763D')
        self.tree.tag_configure('removed', background='#F2DEDE', foreground='#A94442')
        self.tree.tag_configure('modified', background='#FCF8E3', foreground='#8A6D3B')

        self.populate_tree()

        return self.tree

    def populate_tree(self):
        for item in self.diff_results['added']:
            self.tree.insert("", "end", values=("新增", "", item['new_obj'].original_semantic, "N/A"), tags=('added',))

        for item in self.diff_results['removed']:
            self.tree.insert("", "end", values=("移除", item['old_obj'].original_semantic, "", "N/A"),
                             tags=('removed',))

        for item in self.diff_results['modified']:
            sim_str = f"{item['similarity']:.2%}"
            self.tree.insert("", "end", values=(
            "修改/继承", item['old_obj'].original_semantic, item['new_obj'].original_semantic, sim_str),
                             tags=('modified',))

    def buttonbox(self):
        box = ttk.Frame(self)
        ttk.Button(box, text="确认并更新项目", width=18, command=self.ok, default=tk.ACTIVE).pack(side=tk.LEFT, padx=5,
                                                                                                  pady=5)
        ttk.Button(box, text="取消", width=10, command=self.cancel).pack(side=tk.LEFT, padx=5, pady=5)
        self.bind("<Escape>", self.cancel)
        box.pack()

    def apply(self):
        # The actual update logic is handled in the main app,
        # so we just set a result flag here.
        self.result = True