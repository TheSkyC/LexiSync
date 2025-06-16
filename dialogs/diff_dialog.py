import tkinter as tk
from tkinter import ttk, simpledialog


class DiffDialog(simpledialog.Dialog):
    def __init__(self, parent, title, diff_results):
        self.diff_results = diff_results
        super().__init__(parent, title)

    def body(self, master):
        self.geometry("1200x700")

        # 配置主框架的网格权重
        master.grid_rowconfigure(0, weight=1)
        master.grid_columnconfigure(0, weight=1)

        # 创建主容器框架
        main_frame = ttk.Frame(master)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # 配置主容器的网格
        main_frame.grid_rowconfigure(0, weight=1)  # 树视图行可扩展
        main_frame.grid_rowconfigure(1, weight=0)  # 水平滚动条行固定
        main_frame.grid_columnconfigure(0, weight=1)  # 树视图列可扩展
        main_frame.grid_columnconfigure(1, weight=0)  # 垂直滚动条列固定

        # 创建树视图
        cols = ("status", "old_text", "new_text", "similarity")
        self.tree = ttk.Treeview(
            main_frame,
            columns=cols,
            show="headings",
            height=20  # 设置初始高度，实际会被网格拉伸
        )

        # 创建滚动条
        vsb = ttk.Scrollbar(main_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(main_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        # 布局组件
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        # 配置树视图列
        self.tree.heading("status", text="状态")
        self.tree.heading("old_text", text="旧版原文")
        self.tree.heading("new_text", text="新版原文")
        self.tree.heading("similarity", text="相似度")

        self.tree.column("status", width=80, anchor=tk.W)
        self.tree.column("old_text", width=500, anchor=tk.W)
        self.tree.column("new_text", width=500, anchor=tk.W)
        self.tree.column("similarity", width=80, anchor=tk.CENTER)

        # 配置样式标签
        self.tree.tag_configure('added', background='#DFF0D8', foreground='#3C763D')
        self.tree.tag_configure('removed', background='#F2DEDE', foreground='#A94442')
        self.tree.tag_configure('modified', background='#FCF8E3', foreground='#8A6D3B')

        # 填充数据
        self.populate_tree()

        # 绑定窗口大小变化事件
        self.bind("<Configure>", self.on_window_resize)

        return self.tree

    def on_window_resize(self, event):
        """处理窗口大小变化事件"""
        # 获取窗口当前高度
        window_height = self.winfo_height()
        # 计算树视图的合适高度（减去按钮区域和滚动条的高度）
        tree_height = max(10, (window_height - 100) // 20)  # 20是每行的大致高度
        self.tree.configure(height=tree_height)

    def populate_tree(self):
        for item in self.diff_results['added']:
            self.tree.insert("", "end",
                             values=("新增", "", item['new_obj'].original_semantic, "N/A"),
                             tags=('added',))

        for item in self.diff_results['removed']:
            self.tree.insert("", "end",
                             values=("移除", item['old_obj'].original_semantic, "", "N/A"),
                             tags=('removed',))

        for item in self.diff_results['modified']:
            sim_str = f"{item['similarity']:.2%}"
            self.tree.insert("", "end",
                             values=("修改/继承", item['old_obj'].original_semantic,
                                     item['new_obj'].original_semantic, sim_str),
                             tags=('modified',))

    def buttonbox(self):
        box = ttk.Frame(self)
        ttk.Button(box, text="确认并更新项目", width=18, command=self.ok, default=tk.ACTIVE).pack(
            side=tk.LEFT, padx=5, pady=5)
        ttk.Button(box, text="取消", width=10, command=self.cancel).pack(
            side=tk.LEFT, padx=5, pady=5)
        self.bind("<Escape>", self.cancel)
        box.pack()

    def apply(self):
        self.result = True
