import tkinter as tk
from tkinter import ttk, scrolledtext
import re
from components.virtual_treeview import VirtualTreeview


class ProjectTab(ttk.Frame):
    def __init__(self, master, app_instance, **kwargs):
        super().__init__(master, **kwargs)
        self.app = app_instance

        self.current_code_file_path = None
        self.current_project_file_path = None
        self.original_raw_code_content = ""
        self.current_project_modified = False
        self.project_custom_instructions = ""
        self.translatable_objects = []
        self.displayed_string_ids = []
        self.undo_history = []
        self.redo_history = []
        self.current_selected_ts_id = None
        self.placeholder_regex = re.compile(r'\{(\d+)\}')
        self._placeholder_validation_job = None

        self._setup_main_layout()

    def _setup_main_layout(self):
        self.paned_window = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.paned_window.pack(expand=True, fill=tk.BOTH, pady=(5, 0))

        self.left_pane = ttk.Frame(self.paned_window)
        self.paned_window.add(self.left_pane, weight=7)

        self._setup_treeview_panel(self.left_pane)

        self.right_pane = ttk.Frame(self.paned_window)
        self.paned_window.add(self.right_pane, weight=3)
        self._setup_details_pane(self.right_pane)

    def _setup_treeview_panel(self, parent):
        tree_frame = ttk.Frame(parent)
        tree_frame.pack(expand=True, fill=tk.BOTH, padx=0, pady=0)
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        cols = ("seq_id", "status", "original", "translation", "comment", "reviewed", "line")
        hsb = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)

        self.tree = VirtualTreeview(
            tree_frame,
            columns=cols,
            show="headings",
            selectmode="extended",
            right_click_callback=self.app.show_treeview_context_menu,
            xscrollcommand=hsb.set
        )
        hsb.config(command=self.tree.xview)
        self.tree.grid(row=0, column=0, sticky="nsew")
        hsb.grid(row=1, column=0, sticky="ew")

        col_widths = {"seq_id": 40, "status": 30, "original": 300, "translation": 300, "comment": 150, "reviewed": 30,
                      "line": 50}
        col_align = {"seq_id": tk.E, "status": tk.CENTER, "original": tk.W, "translation": tk.W, "comment": tk.W,
                     "reviewed": tk.CENTER, "line": tk.CENTER}
        col_headings = {"seq_id": "#", "status": "S", "original": "原文", "translation": "译文", "comment": "注释",
                        "reviewed": "✔", "line": "行号"}

        for col_key in cols:
            self.tree.heading(col_key, text=col_headings.get(col_key, col_key.capitalize()),
                              command=lambda c=col_key: self.app._sort_treeview_column(c, False))
            self.tree.column(col_key, width=col_widths.get(col_key, 100),
                             anchor=col_align.get(col_key, tk.W),
                             stretch=(col_key not in ["seq_id", "status", "reviewed", "line"]))

        self.tree.bind("<<TreeviewSelect>>", self.app.on_tree_select)
        self.app._configure_treeview_tags_for_tab(self)

    def _setup_details_pane(self, parent_frame):
        details_outer_frame = ttk.LabelFrame(parent_frame, text="编辑与详细信息", padding="5")
        details_outer_frame.pack(expand=True, fill=tk.BOTH, padx=5, pady=0)

        details_paned_window = ttk.PanedWindow(details_outer_frame, orient=tk.VERTICAL)
        details_paned_window.pack(fill=tk.BOTH, expand=True)

        top_section_frame = ttk.Frame(details_paned_window, padding=5)
        details_paned_window.add(top_section_frame, weight=4)
        top_section_frame.columnconfigure(0, weight=1)

        ttk.Label(top_section_frame, text="原文 (Ctrl+Shift+C 复制):").pack(anchor=tk.W, padx=5, pady=(0, 2))
        orig_frame = ttk.Frame(top_section_frame)
        orig_frame.pack(fill=tk.X, expand=False, padx=5, pady=(0, 5))
        orig_frame.grid_rowconfigure(0, weight=1)
        orig_frame.grid_columnconfigure(0, weight=1)
        self.original_text_display = tk.Text(orig_frame, height=3, wrap=tk.WORD, state=tk.DISABLED, relief=tk.SOLID,
                                             borderwidth=1, font=('Segoe UI', 10))
        self.original_text_display.grid(row=0, column=0, sticky="nsew")
        orig_scrollbar = ttk.Scrollbar(orig_frame, orient="vertical", command=self.original_text_display.yview)
        orig_scrollbar.grid(row=0, column=1, sticky="ns")
        self.original_text_display.config(yscrollcommand=orig_scrollbar.set)

        ttk.Label(top_section_frame, text="译文 (Ctrl+Shift+V 粘贴):").pack(anchor=tk.W, padx=5, pady=(5, 2))
        trans_frame = ttk.Frame(top_section_frame)
        trans_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        trans_frame.grid_rowconfigure(0, weight=1)
        trans_frame.grid_columnconfigure(0, weight=1)
        self.translation_edit_text = tk.Text(trans_frame, height=5, wrap=tk.WORD, relief=tk.SOLID, borderwidth=1,
                                             undo=True, font=('Segoe UI', 10))
        self.translation_edit_text.grid(row=0, column=0, sticky="nsew")
        self.translation_edit_text.bind("<FocusOut>", self.app.apply_translation_focus_out)
        self.translation_edit_text.bind("<KeyRelease>", self.app.schedule_placeholder_validation)
        trans_scrollbar = ttk.Scrollbar(trans_frame, orient="vertical", command=self.translation_edit_text.yview)
        trans_scrollbar.grid(row=0, column=1, sticky="ns")
        self.translation_edit_text.config(yscrollcommand=trans_scrollbar.set)

        trans_actions_frame = ttk.Frame(top_section_frame)
        trans_actions_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        self.apply_btn = ttk.Button(trans_actions_frame, text="应用翻译",
                                    command=self.app.apply_translation_from_button, state=tk.DISABLED,
                                    style="Toolbar.TButton")
        self.apply_btn.pack(side=tk.LEFT, padx=(0, 10))
        self.ai_translate_current_btn = ttk.Button(trans_actions_frame, text="AI翻译选中项",
                                                   command=self.app.ai_translate_selected_from_button,
                                                   state=tk.DISABLED, style="Toolbar.TButton")
        self.ai_translate_current_btn.pack(side=tk.RIGHT, padx=5)

        ttk.Label(top_section_frame, text="注释:").pack(anchor=tk.W, padx=5, pady=(5, 2))
        comment_frame = ttk.Frame(top_section_frame)
        comment_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        comment_frame.grid_rowconfigure(0, weight=1)
        comment_frame.grid_columnconfigure(0, weight=1)
        self.comment_edit_text = tk.Text(comment_frame, height=3, wrap=tk.WORD, relief=tk.SOLID, borderwidth=1,
                                         undo=True, font=('Segoe UI', 10))
        self.comment_edit_text.grid(row=0, column=0, sticky="nsew")
        self.comment_edit_text.bind("<FocusOut>", self.app.apply_comment_focus_out)
        comment_scrollbar = ttk.Scrollbar(comment_frame, orient="vertical", command=self.comment_edit_text.yview)
        comment_scrollbar.grid(row=0, column=1, sticky="ns")
        self.comment_edit_text.config(yscrollcommand=comment_scrollbar.set)

        comment_actions_frame = ttk.Frame(top_section_frame)
        comment_actions_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        self.apply_comment_btn = ttk.Button(comment_actions_frame, text="应用注释",
                                            command=self.app.apply_comment_from_button, state=tk.DISABLED,
                                            style="Toolbar.TButton")
        self.apply_comment_btn.pack(side=tk.LEFT)

        status_frame = ttk.Frame(top_section_frame)
        status_frame.pack(fill=tk.X, padx=5, pady=5)
        self.ignore_var = tk.BooleanVar()
        self.toggle_ignore_btn = ttk.Checkbutton(status_frame, text="忽略此字符串", variable=self.ignore_var,
                                                 command=self.app.toggle_ignore_selected_checkbox, state=tk.DISABLED)
        self.toggle_ignore_btn.pack(side=tk.LEFT, padx=5)
        self.reviewed_var = tk.BooleanVar()
        self.toggle_reviewed_btn = ttk.Checkbutton(status_frame, text="已审阅", variable=self.reviewed_var,
                                                   command=self.app.toggle_reviewed_selected_checkbox,
                                                   state=tk.DISABLED)
        self.toggle_reviewed_btn.pack(side=tk.LEFT, padx=15)

        context_section_frame = ttk.Frame(details_paned_window, padding=5)
        details_paned_window.add(context_section_frame, weight=2)
        context_section_frame.columnconfigure(0, weight=1)
        context_section_frame.rowconfigure(1, weight=1)
        ttk.Label(context_section_frame, text="上下文预览:").pack(anchor=tk.W, padx=5, pady=(0, 2))
        ctx_frame = ttk.Frame(context_section_frame)
        ctx_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        ctx_frame.grid_rowconfigure(0, weight=1)
        ctx_frame.grid_columnconfigure(0, weight=1)
        self.context_text_display = tk.Text(ctx_frame, height=6, wrap=tk.WORD, state=tk.DISABLED, relief=tk.SOLID,
                                            borderwidth=1, font=("Consolas", 9))
        self.context_text_display.grid(row=0, column=0, sticky="nsew")
        self.context_text_display.tag_config("highlight", background="yellow", foreground="black")
        ctx_scrollbar = ttk.Scrollbar(ctx_frame, orient="vertical", command=self.context_text_display.yview)
        ctx_scrollbar.grid(row=0, column=1, sticky="ns")
        self.context_text_display.config(yscrollcommand=ctx_scrollbar.set)

        tm_section_frame = ttk.Frame(details_paned_window, padding=5)
        details_paned_window.add(tm_section_frame, weight=1)
        tm_section_frame.columnconfigure(0, weight=1)
        tm_section_frame.rowconfigure(1, weight=1)
        ttk.Label(tm_section_frame, text="翻译记忆库匹配:").pack(anchor=tk.W, pady=(0, 2), padx=5)
        self.tm_suggestions_listbox = tk.Listbox(tm_section_frame, height=4, relief=tk.SOLID, borderwidth=1,
                                                 font=('Segoe UI', 10))
        self.tm_suggestions_listbox.pack(fill=tk.BOTH, expand=True, pady=(0, 5), padx=5)
        self.tm_suggestions_listbox.bind("<Double-1>", self.app.apply_tm_suggestion_from_listbox)
        tm_actions_frame = ttk.Frame(tm_section_frame)
        tm_actions_frame.pack(fill=tk.X, pady=(0, 0), padx=5)
        self.update_selected_tm_btn = ttk.Button(tm_actions_frame, text="更新选中项记忆",
                                                 command=self.app.update_tm_for_selected_string, state=tk.DISABLED,
                                                 style="Toolbar.TButton")
        self.update_selected_tm_btn.pack(side=tk.LEFT, padx=(0, 5))
        self.clear_selected_tm_btn = ttk.Button(tm_actions_frame, text="清除选中项记忆",
                                                command=self.app.clear_tm_for_selected_string, state=tk.DISABLED,
                                                style="Toolbar.TButton")
        self.clear_selected_tm_btn.pack(side=tk.LEFT, padx=5)

        self.original_text_display.tag_configure('placeholder', foreground='mediumseagreen', font=('Segoe UI', 10))
        self.original_text_display.tag_configure('placeholder_missing', background='#FFDDDD', foreground='red')
        self.translation_edit_text.tag_configure('placeholder', foreground='mediumseagreen', font=('Segoe UI', 10))
        self.translation_edit_text.tag_configure('placeholder_extra', background='#FFEBCD', foreground='orange red')