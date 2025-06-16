import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog, scrolledtext
import re
import os
import shutil
import json
import datetime
import tkinter.font
import time
import threading
from copy import deepcopy
from difflib import SequenceMatcher
from openpyxl import Workbook, load_workbook

from components.virtual_treeview import VirtualTreeview
from dialogs.ai_settings_dialog import AISettingsDialog
from dialogs.search_dialog import AdvancedSearchDialog
from services.ai_translator import AITranslator
from services.code_file_service import extract_translatable_strings, save_translated_code
from services.project_service import load_project, save_project
from utils import config_manager
from utils.constants import *

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    TkinterDnD = None
    print("提示: tkinterdnd2 未找到, 文件拖放功能不可用。pip install tkinterdnd2-universal")

try:
    import requests
except ImportError:
    requests = None
    print("提示: requests 未找到, AI翻译功能不可用。pip install requests")


class OverwatchLocalizerApp:
    def __init__(self, root):
        self.root = root
        if TkinterDnD and isinstance(root, TkinterDnD.Tk):
            pass
        elif TkinterDnD:
            self.root = TkinterDnD.DnDWrapper(self.root)

        self.root.title(f"Overwatch Localizer - v{APP_VERSION}")
        self.root.geometry("1600x900")
        self.root.title(f"Overwatch Localizer - v{APP_VERSION}")
        self.root.geometry("1600x900")

        self.ACTION_MAP = {
            'open_code_file': {'method': self.open_code_file_dialog, 'desc': '打开代码文件'},
            'open_project': {'method': self.open_project_dialog, 'desc': '打开项目'},
            'save_project': {'method': self.save_project_dialog, 'desc': '保存项目'},
            'save_code_file': {'method': self.save_code_file, 'desc': '保存到新代码文件'},
            'undo': {'method': self.undo_action, 'desc': '撤销'},
            'redo': {'method': self.redo_action, 'desc': '恢复'},
            'find_replace': {'method': self.show_advanced_search_dialog, 'desc': '查找/替换'},
            'copy_original': {'method': self.copy_selected_original_text_menu, 'desc': '复制原文'},
            'paste_translation': {'method': self.paste_clipboard_to_selected_translation_menu, 'desc': '粘贴到译文'},
            'ai_translate_selected': {'method': self.ai_translate_selected_from_menu, 'desc': 'AI翻译选中项'},
            'toggle_reviewed': {'method': self.cm_toggle_reviewed_status, 'desc': '切换审阅状态'},
            'toggle_ignored': {'method': self.cm_toggle_ignored_status, 'desc': '切换忽略状态'},
            'apply_and_next': {'method': self.apply_and_select_next_untranslated, 'desc': '应用并到下一未译项'},
        }
        self.current_code_file_path = None
        self.current_project_file_path = None
        self.original_raw_code_content = ""
        self.current_project_modified = False
        self.project_custom_instructions = ""

        self.translatable_objects = []
        self.displayed_string_ids = []

        self.translation_memory = {}
        self.current_tm_file = None

        self.undo_history = []
        self.redo_history = []
        self.current_selected_ts_id = None

        self.config = config_manager.load_config()
        self.ai_translator = AITranslator(
            api_key=self.config.get("ai_api_key"),
            model_name=self.config.get("ai_model_name", "deepseek-chat"),
            api_url=self.config.get("ai_api_base_url", DEFAULT_API_URL)
        )
        self.ai_translation_batch_ids_queue = []
        self.is_ai_translating_batch = False
        self.ai_batch_total_items = 0
        self.ai_batch_dispatched_count = 0
        self.ai_batch_completed_count = 0
        self.ai_batch_successful_translations_for_undo = []
        self.ai_batch_semaphore = None
        self.ai_batch_next_item_index = 0
        self.ai_batch_active_threads = 0

        self.deduplicate_strings_var = tk.BooleanVar(value=self.config.get("deduplicate", False))
        self.show_ignored_var = tk.BooleanVar(value=self.config.get("show_ignored", True))
        self.show_untranslated_var = tk.BooleanVar(value=self.config.get("show_untranslated", False))
        self.show_translated_var = tk.BooleanVar(value=self.config.get("show_translated", False))
        self.show_unreviewed_var = tk.BooleanVar(value=self.config.get("show_unreviewed", False))
        self.search_var = tk.StringVar()

        self.auto_save_tm_var = tk.BooleanVar(value=self.config.get("auto_save_tm", False))
        self.auto_backup_tm_on_save_var = tk.BooleanVar(value=self.config.get("auto_backup_tm_on_save", True))

        self._ignored_tag_font = None
        self.icons = self._load_icons()
        self.placeholder_regex = re.compile(r'\{(\d+)\}')
        self._placeholder_validation_job = None

        self._apply_theme()
        self._setup_menu()
        self._setup_main_layout()
        self._setup_statusbar()
        self._setup_drag_drop()
        self._setup_treeview_context_menu()

        self._load_default_tm_excel()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.update_ui_state_after_file_load()
        self.update_ai_related_ui_state()
        self.update_counts_display()
        self.update_title()
        self.update_recent_files_menu()

    def _load_icons(self):
        return {}

    def _apply_theme(self):
        style = ttk.Style(self.root)
        try:
            available_themes = style.theme_names()
            if 'clam' in available_themes:
                style.theme_use('clam')
            elif 'vista' in available_themes:
                style.theme_use('vista')
            elif 'aqua' in available_themes:
                style.theme_use('aqua')
            elif 'alt' in available_themes:
                style.theme_use('alt')

            style.configure("Treeview.Heading", font=('Segoe UI', 10, 'bold'))
            style.configure("TNotebook.Tab", padding=[10, 5], font=('Segoe UI', 10))
            style.configure("Status.TFrame", relief=tk.SUNKEN, borderwidth=1)
            style.configure("Filter.TFrame")
            style.configure("Toolbar.TButton", padding=5)
        except tk.TclError:
            print("TTK 主题不可用或应用失败。")

    def _setup_drag_drop(self):
        if TkinterDnD:
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind('<<Drop>>', self.handle_drop)

    def handle_drop(self, event):
        if event.data:
            try:
                files = self.root.tk.splitlist(event.data)
                if files:
                    filepath = files[0]
                    if os.path.isfile(filepath):
                        if filepath.lower().endswith((".ow", ".txt")):
                            if self.prompt_save_if_modified():
                                self.open_code_file_path(filepath)
                        elif filepath.lower().endswith(PROJECT_FILE_EXTENSION):
                            if self.prompt_save_if_modified():
                                self.open_project_file(filepath)
                        else:
                            self.update_statusbar(f"拖放失败: 无效的文件类型 '{os.path.basename(filepath)}'")
                    else:
                        self.update_statusbar(f"拖放失败: '{os.path.basename(filepath)}' 不是一个文件。")
            except Exception as e:
                messagebox.showerror("拖放错误", f"处理拖放文件时出错: {e}", parent=self.root)
                self.update_statusbar("拖放处理错误")

    def save_config(self):
        config_manager.save_config(self)

    def add_to_recent_files(self, filepath):
        if not filepath: return
        recent_files = self.config.get("recent_files", [])
        if filepath in recent_files:
            recent_files.remove(filepath)
        recent_files.insert(0, filepath)
        self.config["recent_files"] = recent_files[:10]
        self.update_recent_files_menu()
        self.save_config()

    def update_recent_files_menu(self):
        self.recent_files_menu.delete(0, tk.END)
        recent_files = self.config.get("recent_files", [])
        if not recent_files:
            self.recent_files_menu.add_command(label="无历史记录", state=tk.DISABLED)
            return

        for i, filepath in enumerate(recent_files):
            label = f"{i + 1}: {filepath}"
            self.recent_files_menu.add_command(label=label, command=lambda p=filepath: self.open_recent_file(p))
        self.recent_files_menu.add_separator()
        self.recent_files_menu.add_command(label="清除历史记录", command=self.clear_recent_files)

    def open_recent_file(self, filepath):
        if not os.path.exists(filepath):
            messagebox.showerror("文件未找到", f"文件 '{filepath}' 不存在。", parent=self.root)
            recent_files = self.config.get("recent_files", [])
            if filepath in recent_files:
                recent_files.remove(filepath)
                self.config["recent_files"] = recent_files
                self.update_recent_files_menu()
            return

        if not self.prompt_save_if_modified():
            return

        if filepath.lower().endswith(PROJECT_FILE_EXTENSION):
            self.open_project_file(filepath)
        elif filepath.lower().endswith((".ow", ".txt")):
            self.open_code_file_path(filepath)

    def clear_recent_files(self):
        if messagebox.askyesno("确认", "确定要清除所有最近文件历史记录吗？", parent=self.root):
            self.config["recent_files"] = []
            self.update_recent_files_menu()
            self.save_config()

    def about(self):
        messagebox.showinfo("关于 Overwatch Localizer",
                            f"守望先锋自定义代码翻译工具\n\n"
                            f"版本: {APP_VERSION}\n"
                            "作者：骰子掷上帝\n"
                            "国服ID：小鸟游六花#56683 / 亚服：小鳥游六花#31665", parent=self.root)

    def on_closing(self):
        if not self.prompt_save_if_modified():
            return

        if self.is_ai_translating_batch:
            if messagebox.askyesno("AI翻译进行中",
                                   "AI批量翻译仍在进行中。确定要退出吗？\n未完成的翻译将丢失。", parent=self.root):
                self.stop_batch_ai_translation(silent=True)
            else:
                return

        if self.current_tm_file and self.translation_memory:
            self.save_tm_to_excel(self.current_tm_file, silent=True, backup=self.auto_backup_tm_on_save_var.get())
        elif self.translation_memory:
            default_tm_path = self._get_default_tm_excel_path()
            if default_tm_path:
                self.save_tm_to_excel(default_tm_path, silent=True, backup=self.auto_backup_tm_on_save_var.get())

        self.save_config()
        self.root.destroy()

    def _setup_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # --- File Menu ---
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="文件", menu=file_menu)
        file_menu.add_command(label="打开代码文件...", command=self.ACTION_MAP['open_code_file']['method'])
        file_menu.add_command(label="打开项目...", command=self.ACTION_MAP['open_project']['method'])
        file_menu.add_separator()
        file_menu.add_command(label="版本对比/导入新版代码...", command=self.compare_with_new_version, state=tk.DISABLED)
        file_menu.add_separator()
        file_menu.add_command(label="保存项目", command=self.ACTION_MAP['save_project']['method'], state=tk.DISABLED)
        file_menu.add_command(label="保存项目", command=self.ACTION_MAP['save_project']['method'], state=tk.DISABLED)
        file_menu.add_command(label="项目另存为...", command=self.save_project_as_dialog, state=tk.DISABLED)
        file_menu.add_separator()
        file_menu.add_command(label="保存翻译到新代码文件", command=self.ACTION_MAP['save_code_file']['method'],
                              state=tk.DISABLED)
        # ... (other file menu items remain the same) ...
        file_menu.add_separator()
        file_menu.add_command(label="导入Excel翻译 (项目)", command=self.import_project_translations_from_excel,
                              state=tk.DISABLED)
        file_menu.add_command(label="导出到Excel (项目)", command=self.export_project_translations_to_excel,
                              state=tk.DISABLED)
        file_menu.add_separator()
        file_menu.add_command(label="导入翻译记忆库 (Excel)", command=self.import_tm_excel_dialog)
        file_menu.add_command(label="导出当前记忆库 (Excel)", command=self.export_tm_excel_dialog)
        file_menu.add_separator()
        self.recent_files_menu = tk.Menu(file_menu, tearoff=0)
        file_menu.add_cascade(label="最近打开文件", menu=self.recent_files_menu)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.on_closing)
        self.file_menu = file_menu

        # --- Edit Menu ---
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="编辑", menu=edit_menu)
        edit_menu.add_command(label="撤销", command=self.ACTION_MAP['undo']['method'], state=tk.DISABLED)
        edit_menu.add_command(label="恢复", command=self.ACTION_MAP['redo']['method'], state=tk.DISABLED)
        edit_menu.add_separator()
        edit_menu.add_command(label="查找/替换...", command=self.ACTION_MAP['find_replace']['method'],
                              state=tk.DISABLED)
        edit_menu.add_separator()
        edit_menu.add_command(label="复制原文", command=self.ACTION_MAP['copy_original']['method'], state=tk.DISABLED)
        edit_menu.add_command(label="粘贴到译文", command=self.ACTION_MAP['paste_translation']['method'],
                              state=tk.DISABLED)
        self.edit_menu = edit_menu

        # --- View Menu (no changes) ---
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="视图", menu=view_menu)
        view_menu.add_checkbutton(label="去重显示", variable=self.deduplicate_strings_var,
                                  command=self.refresh_treeview_preserve_selection)
        view_menu.add_checkbutton(label="显示已忽略项", variable=self.show_ignored_var,
                                  command=self.refresh_treeview_preserve_selection)
        view_menu.add_checkbutton(label="仅显示未翻译", variable=self.show_untranslated_var,
                                  command=self.refresh_treeview_preserve_selection)
        view_menu.add_checkbutton(label="仅显示已翻译", variable=self.show_translated_var,
                                  command=self.refresh_treeview_preserve_selection)
        view_menu.add_checkbutton(label="仅显示未审阅", variable=self.show_unreviewed_var,
                                  command=self.refresh_treeview_preserve_selection)

        # --- Tools Menu ---
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="工具", menu=tools_menu)
        tools_menu.add_command(label="应用记忆库到未翻译项",
                               command=lambda: self.apply_tm_to_all_current_strings(only_if_empty=True, confirm=True),
                               state=tk.DISABLED)
        tools_menu.add_command(label="清空翻译记忆库 (内存)", command=self.clear_entire_translation_memory)
        tools_menu.add_separator()
        tools_menu.add_command(label="使用AI翻译 (选中项)", command=self.ACTION_MAP['ai_translate_selected']['method'],
                               state=tk.DISABLED)
        # ... (other tools menu items remain the same) ...
        tools_menu.add_command(label="使用AI翻译 (所有未翻译项)", command=self.ai_translate_all_untranslated,
                               state=tk.DISABLED)
        tools_menu.add_command(label="停止AI批量翻译", command=lambda: self.stop_batch_ai_translation(),
                               state=tk.DISABLED)
        tools_menu.add_separator()
        tools_menu.add_command(label="项目个性化翻译设置...", command=self.show_project_custom_instructions_dialog,
                               state=tk.DISABLED)
        tools_menu.add_command(label="AI翻译设置...", command=self.show_ai_settings_dialog)
        self.tools_menu = tools_menu

        # --- Settings Menu ---
        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="设置", menu=settings_menu)
        settings_menu.add_checkbutton(label="保存时自动备份记忆库", variable=self.auto_backup_tm_on_save_var,
                                      command=self.save_config)
        settings_menu.add_command(label="快捷键设置...", command=self.show_keybinding_dialog)

        # --- Help Menu (no changes) ---
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="帮助", menu=help_menu)
        help_menu.add_command(label="关于", command=self.about)

        # --- Dynamic Bindings ---
        self._setup_keybindings()
        self.update_menu_accelerators()

    def _setup_keybindings(self):
        for action in self.ACTION_MAP.keys():
            for key_seq in self.config.get('keybindings', {}).values():
                if key_seq: self.root.unbind_all(key_seq)
            for key_seq in DEFAULT_KEYBINDINGS.values():
                if key_seq: self.root.unbind_all(key_seq)

        for action, key_sequence in self.config.get('keybindings', {}).items():
            if key_sequence and action in self.ACTION_MAP:
                command = self.ACTION_MAP[action]['method']
                self.root.bind_all(key_sequence, lambda e, cmd=command: cmd(e) or "break")

    def update_menu_accelerators(self):
        bindings = self.config.get('keybindings', {})
        self.file_menu.entryconfig("打开代码文件...", accelerator=bindings.get('open_code_file', ''))
        self.file_menu.entryconfig("打开项目...", accelerator=bindings.get('open_project', ''))
        self.file_menu.entryconfig("保存项目", accelerator=bindings.get('save_project', ''))
        self.file_menu.entryconfig("保存翻译到新代码文件", accelerator=bindings.get('save_code_file', ''))

        self.edit_menu.entryconfig("撤销", accelerator=bindings.get('undo', ''))
        self.edit_menu.entryconfig("恢复", accelerator=bindings.get('redo', ''))
        self.edit_menu.entryconfig("查找/替换...", accelerator=bindings.get('find_replace', ''))
        self.edit_menu.entryconfig("复制原文", accelerator=bindings.get('copy_original', ''))
        self.edit_menu.entryconfig("粘贴到译文", accelerator=bindings.get('paste_translation', ''))

        self.tools_menu.entryconfig("使用AI翻译 (选中项)", accelerator=bindings.get('ai_translate_selected', ''))

    def show_keybinding_dialog(self):
        from dialogs.keybinding_dialog import KeybindingDialog
        KeybindingDialog(self.root, "快捷键设置", self)

    def _setup_main_layout(self):
        main_frame = ttk.Frame(self.root, padding="5")
        main_frame.pack(expand=True, fill=tk.BOTH)

        self.paned_window = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        self.paned_window.pack(expand=True, fill=tk.BOTH, pady=(5, 0))

        self.left_pane = ttk.Frame(self.paned_window)
        self.paned_window.add(self.left_pane, weight=7)

        self._setup_filter_toolbar(self.left_pane)
        self._setup_treeview_panel(self.left_pane)

        self.right_pane = ttk.Frame(self.paned_window)
        self.paned_window.add(self.right_pane, weight=3)
        self._setup_details_pane(self.right_pane)

    def _setup_filter_toolbar(self, parent):
        toolbar = ttk.Frame(parent, style="Filter.TFrame", padding=5)
        toolbar.pack(side=tk.TOP, fill=tk.X, pady=(0, 5))

        ttk.Label(toolbar, text="筛选:").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Checkbutton(toolbar, text="去重", variable=self.deduplicate_strings_var,
                        command=self.refresh_treeview_preserve_selection).pack(side=tk.LEFT, padx=3)
        ttk.Checkbutton(toolbar, text="已忽略", variable=self.show_ignored_var,
                        command=self.refresh_treeview_preserve_selection).pack(side=tk.LEFT, padx=3)
        ttk.Checkbutton(toolbar, text="未翻译", variable=self.show_untranslated_var,
                        command=self.refresh_treeview_preserve_selection).pack(side=tk.LEFT, padx=3)
        ttk.Checkbutton(toolbar, text="已翻译", variable=self.show_translated_var,
                        command=self.refresh_treeview_preserve_selection).pack(side=tk.LEFT, padx=3)
        ttk.Checkbutton(toolbar, text="未审阅", variable=self.show_unreviewed_var,
                        command=self.refresh_treeview_preserve_selection).pack(side=tk.LEFT, padx=3)

        search_frame = ttk.Frame(toolbar)
        search_frame.pack(side=tk.RIGHT, padx=5)

        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=25, font=('Segoe UI', 9))
        self.search_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.search_entry.bind("<Return>", lambda e: self.find_string_from_toolbar())
        self.search_entry.bind("<FocusIn>", lambda e: self.search_entry.config(
            foreground="black") if self.search_var.get() == "快速搜索..." else None)
        self.search_entry.bind("<FocusOut>", lambda e: self.search_entry.config(
            foreground="grey") if not self.search_var.get() else None)
        if not self.search_var.get():
            self.search_entry.insert(0, "快速搜索...")
            self.search_entry.config(foreground="grey")

        search_button = ttk.Button(search_frame, text="查找", command=self.find_string_from_toolbar,
                                   style="Toolbar.TButton")
        search_button.pack(side=tk.LEFT)

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
            right_click_callback=self.show_treeview_context_menu,
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
                              command=lambda c=col_key: self._sort_treeview_column(c, False))
            self.tree.column(col_key, width=col_widths.get(col_key, 100),
                             anchor=col_align.get(col_key, tk.W),
                             stretch=(col_key not in ["seq_id", "status", "reviewed", "line"]))

        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        self._configure_treeview_tags()

    def _setup_treeview_context_menu(self):
        self.tree_context_menu = tk.Menu(self.tree, tearoff=0)
        self.tree_context_menu.add_command(label="复制原文", command=self.cm_copy_original)
        self.tree_context_menu.add_command(label="复制译文", command=self.cm_copy_translation)
        self.tree_context_menu.add_separator()
        self.tree_context_menu.add_command(label="标记为已忽略", command=lambda: self.cm_set_ignored_status(True))
        self.tree_context_menu.add_command(label="取消标记已忽略", command=lambda: self.cm_set_ignored_status(False))
        self.tree_context_menu.add_separator()
        self.tree_context_menu.add_command(label="标记为已审阅", command=lambda: self.cm_set_reviewed_status(True))
        self.tree_context_menu.add_command(label="标记为未审阅", command=lambda: self.cm_set_reviewed_status(False))
        self.tree_context_menu.add_separator()
        self.tree_context_menu.add_command(label="编辑注释...", command=self.cm_edit_comment)
        self.tree_context_menu.add_separator()
        self.tree_context_menu.add_command(label="应用记忆库到选中项", command=self.cm_apply_tm_to_selected)
        self.tree_context_menu.add_command(label="清除选中项译文", command=self.cm_clear_selected_translations)
        self.tree_context_menu.add_separator()
        self.tree_context_menu.add_command(label="使用AI翻译选中项", command=self.cm_ai_translate_selected)

    def show_treeview_context_menu(self, event):
        selected_iids = self.tree.selection()
        if not selected_iids:
            return

        self.tree_context_menu.post(event.x_root, event.y_root)

    def _sort_treeview_column(self, col, reverse):
        if not self.tree._data: return

        col_index = -1
        try:
            col_index = self.tree.columns.index(col)
        except ValueError:
            return

        def get_sort_key(iid):
            try:
                values = self.tree._data[iid]['values']
                value = values[col_index]
                if col in ("seq_id", "line"):
                    return int(value)
                elif col == "reviewed":
                    return 1 if value == "✔" else 0
                elif isinstance(value, str):
                    return value.lower()
                return value
            except (ValueError, TypeError, IndexError):
                return 0

        sorted_iids = sorted(self.tree._ordered_iids, key=get_sort_key, reverse=reverse)

        self.tree._sync_data_order(sorted_iids)
        self.tree.heading(col, command=lambda: self._sort_treeview_column(col, not reverse))

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
        self.translation_edit_text.bind("<FocusOut>", self.apply_translation_focus_out)
        self.translation_edit_text.bind("<KeyRelease>", self.schedule_placeholder_validation)

        trans_scrollbar = ttk.Scrollbar(trans_frame, orient="vertical", command=self.translation_edit_text.yview)
        trans_scrollbar.grid(row=0, column=1, sticky="ns")
        self.translation_edit_text.config(yscrollcommand=trans_scrollbar.set)

        trans_actions_frame = ttk.Frame(top_section_frame)
        trans_actions_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        self.apply_btn = ttk.Button(trans_actions_frame, text="应用翻译", command=self.apply_translation_from_button,
                                    state=tk.DISABLED, style="Toolbar.TButton")
        self.apply_btn.pack(side=tk.LEFT, padx=(0, 10))
        self.ai_translate_current_btn = ttk.Button(trans_actions_frame, text="AI翻译选中项",
                                                   command=self.ai_translate_selected_from_button, state=tk.DISABLED,
                                                   style="Toolbar.TButton")
        self.ai_translate_current_btn.pack(side=tk.RIGHT, padx=5)

        ttk.Label(top_section_frame, text="注释:").pack(anchor=tk.W, padx=5, pady=(5, 2))
        comment_frame = ttk.Frame(top_section_frame)
        comment_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        comment_frame.grid_rowconfigure(0, weight=1)
        comment_frame.grid_columnconfigure(0, weight=1)

        self.comment_edit_text = tk.Text(comment_frame, height=3, wrap=tk.WORD, relief=tk.SOLID, borderwidth=1,
                                         undo=True, font=('Segoe UI', 10))
        self.comment_edit_text.grid(row=0, column=0, sticky="nsew")
        self.comment_edit_text.bind("<FocusOut>", self.apply_comment_focus_out)

        comment_scrollbar = ttk.Scrollbar(comment_frame, orient="vertical", command=self.comment_edit_text.yview)
        comment_scrollbar.grid(row=0, column=1, sticky="ns")
        self.comment_edit_text.config(yscrollcommand=comment_scrollbar.set)

        comment_actions_frame = ttk.Frame(top_section_frame)
        comment_actions_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        self.apply_comment_btn = ttk.Button(comment_actions_frame, text="应用注释",
                                            command=self.apply_comment_from_button, state=tk.DISABLED,
                                            style="Toolbar.TButton")
        self.apply_comment_btn.pack(side=tk.LEFT)

        status_frame = ttk.Frame(top_section_frame)
        status_frame.pack(fill=tk.X, padx=5, pady=5)
        self.ignore_var = tk.BooleanVar()
        self.toggle_ignore_btn = ttk.Checkbutton(status_frame, text="忽略此字符串", variable=self.ignore_var,
                                                 command=self.toggle_ignore_selected_checkbox, state=tk.DISABLED)
        self.toggle_ignore_btn.pack(side=tk.LEFT, padx=5)
        self.reviewed_var = tk.BooleanVar()
        self.toggle_reviewed_btn = ttk.Checkbutton(status_frame, text="已审阅", variable=self.reviewed_var,
                                                   command=self.toggle_reviewed_selected_checkbox, state=tk.DISABLED)
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
        self.tm_suggestions_listbox.bind("<Double-1>", self.apply_tm_suggestion_from_listbox)
        tm_actions_frame = ttk.Frame(tm_section_frame)
        tm_actions_frame.pack(fill=tk.X, pady=(0, 0), padx=5)
        self.update_selected_tm_btn = ttk.Button(tm_actions_frame, text="更新选中项记忆",
                                                 command=self.update_tm_for_selected_string, state=tk.DISABLED,
                                                 style="Toolbar.TButton")
        self.update_selected_tm_btn.pack(side=tk.LEFT, padx=(0, 5))
        self.clear_selected_tm_btn = ttk.Button(tm_actions_frame, text="清除选中项记忆",
                                                command=self.clear_tm_for_selected_string, state=tk.DISABLED,
                                                style="Toolbar.TButton")
        self.clear_selected_tm_btn.pack(side=tk.LEFT, padx=5)

        self.original_text_display.tag_configure('placeholder', foreground='mediumseagreen', font=('Segoe UI', 10))
        self.original_text_display.tag_configure('placeholder_missing', background='#FFDDDD', foreground='red')
        self.translation_edit_text.tag_configure('placeholder', foreground='mediumseagreen', font=('Segoe UI', 10))
        self.translation_edit_text.tag_configure('placeholder_extra', background='#FFEBCD', foreground='orange red')

    def _setup_statusbar(self):
        self.statusbar_frame = ttk.Frame(self.root, style="Status.TFrame")
        self.statusbar_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.statusbar_text = tk.StringVar()
        self.statusbar_text.set("准备就绪")
        statusbar_label = ttk.Label(self.statusbar_frame, textvariable=self.statusbar_text, anchor=tk.W, padding=(5, 2))
        statusbar_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.counts_text = tk.StringVar()
        self.counts_label_widget = ttk.Label(self.statusbar_frame, textvariable=self.counts_text, anchor=tk.E,
                                             padding=(5, 2))
        self.counts_label_widget.pack(side=tk.RIGHT, padx=10)

        self.progress_bar = ttk.Progressbar(self.statusbar_frame, orient=tk.HORIZONTAL, length=150, mode='determinate')

        self.update_counts_display()

        extra_info = []
        if not TkinterDnD: extra_info.append("tkinterdnd2 未找到 (无拖放功能)")
        if not requests: extra_info.append("requests 未找到 (无AI翻译功能)")
        if extra_info: self.update_statusbar(self.statusbar_text.get() + " | 提示: " + ", ".join(extra_info) + "。")

    def update_statusbar(self, text, persistent=False):
        self.statusbar_text.set(text)
        self.root.update_idletasks()
        if not persistent:
            self.root.after(5000, lambda: self.clear_statusbar_if_unchanged(text))

    def clear_statusbar_if_unchanged(self, original_text):
        if self.statusbar_text.get() == original_text:
            self.statusbar_text.set("准备就绪")

    def update_counts_display(self):
        if not hasattr(self, 'translatable_objects'): return
        displayed_count = len(self.displayed_string_ids)
        translated_visible = 0
        untranslated_visible = 0
        ignored_visible = 0

        for ts_id in self.displayed_string_ids:
            ts_obj = self._find_ts_obj_by_id(ts_id)
            if ts_obj:
                if ts_obj.is_ignored:
                    ignored_visible += 1
                elif ts_obj.translation.strip():
                    translated_visible += 1
                else:
                    untranslated_visible += 1

        self.counts_text.set(
            f"显示: {displayed_count} | 已译: {translated_visible} | 未译: {untranslated_visible} | 已忽略: {ignored_visible}")

    def update_title(self):
        base_title = f"Overwatch Localizer - v{APP_VERSION}"
        file_name_part = ""
        if self.current_project_file_path:
            file_name_part = os.path.basename(self.current_project_file_path)
        elif self.current_code_file_path:
            file_name_part = os.path.basename(self.current_code_file_path)

        modified_indicator = "*" if self.current_project_modified else ""

        if file_name_part:
            self.root.title(f"{base_title} - {file_name_part}{modified_indicator}")
        else:
            self.root.title(base_title)

    def update_ui_state_after_file_load(self, file_or_project_loaded=False):
        has_content = bool(self.translatable_objects) and file_or_project_loaded
        state = tk.NORMAL if has_content else tk.DISABLED
        self.file_menu.entryconfig("版本对比/导入新版代码...", state=tk.NORMAL if self.current_code_file_path and has_content else tk.DISABLED)
        self.file_menu.entryconfig("保存翻译到新代码文件",
                                   state=tk.NORMAL if self.current_code_file_path and has_content else tk.DISABLED)
        self.file_menu.entryconfig("保存项目",
                                   state=tk.NORMAL if self.current_code_file_path or self.current_project_file_path else tk.DISABLED)
        self.file_menu.entryconfig("项目另存为...",
                                   state=tk.NORMAL if has_content else tk.DISABLED)

        self.file_menu.entryconfig("导入Excel翻译 (项目)", state=state)
        self.file_menu.entryconfig("导出到Excel (项目)", state=state)

        self.edit_menu.entryconfig("查找/替换...", state=state)
        self.edit_menu.entryconfig("复制原文", state=tk.DISABLED if not has_content else (
            tk.NORMAL if self.current_selected_ts_id else tk.DISABLED))
        self.edit_menu.entryconfig("粘贴到译文", state=tk.DISABLED if not has_content else (
            tk.NORMAL if self.current_selected_ts_id else tk.DISABLED))

        self.edit_menu.entryconfig("撤销", state=tk.NORMAL if self.undo_history else tk.DISABLED)
        self.edit_menu.entryconfig("恢复", state=tk.NORMAL if self.redo_history else tk.DISABLED)

        self.tools_menu.entryconfig("应用记忆库到未翻译项", state=state)
        self.tools_menu.entryconfig("项目个性化翻译设置...",
                                    state=tk.NORMAL if self.current_project_file_path else tk.DISABLED)

        self.update_ai_related_ui_state()
        self.update_title()

    def update_ai_related_ui_state(self):
        ai_available = requests is not None
        file_loaded_and_has_strings = bool(self.translatable_objects)
        item_selected = self.current_selected_ts_id is not None
        can_start_ai_ops = ai_available and file_loaded_and_has_strings and not self.is_ai_translating_batch
        try:
            self.tools_menu.entryconfig("使用AI翻译 (选中项)",
                                        state=tk.NORMAL if can_start_ai_ops and item_selected else tk.DISABLED)
            self.tools_menu.entryconfig("使用AI翻译 (所有未翻译项)",
                                        state=tk.NORMAL if can_start_ai_ops else tk.DISABLED)
            self.tools_menu.entryconfig("停止AI批量翻译",
                                        state=tk.NORMAL if self.is_ai_translating_batch else tk.DISABLED)
            self.tools_menu.entryconfig("AI翻译设置...",
                                        state=tk.NORMAL if ai_available else tk.DISABLED)
        except tk.TclError as e:
            print(f"Error updating AI menu states: {e}")

        if hasattr(self, 'ai_translate_current_btn'):
            self.ai_translate_current_btn.config(state=tk.NORMAL if can_start_ai_ops and item_selected else tk.DISABLED)

        if hasattr(self, 'progress_bar') and hasattr(self, 'counts_label_widget'):
            if self.is_ai_translating_batch:
                if not self.progress_bar.winfo_ismapped():
                    self.progress_bar.pack(side=tk.RIGHT, padx=5, pady=2, before=self.counts_label_widget)
                self.progress_bar.config(mode='determinate')
            else:
                if self.progress_bar.winfo_ismapped():
                    self.progress_bar.pack_forget()

    def mark_project_modified(self, modified=True):
        if self.current_project_modified != modified:
            self.current_project_modified = modified
            self.update_title()

    def add_to_undo_history(self, action_type, data):
        self.undo_history.append({'type': action_type, 'data': deepcopy(data)})
        if len(self.undo_history) > MAX_UNDO_HISTORY:
            self.undo_history.pop(0)
        self.redo_history.clear()
        try:
            self.edit_menu.entryconfig("撤销", state=tk.NORMAL)
            self.edit_menu.entryconfig("恢复", state=tk.DISABLED)
        except tk.TclError:
            pass
        self.mark_project_modified()

    def _find_ts_obj_by_id(self, obj_id):
        for ts_obj in self.translatable_objects:
            if ts_obj.id == obj_id:
                return ts_obj
        return None

    def undo_action(self, event=None):
        focused = self.root.focus_get()
        if event and isinstance(focused, (tk.Text, scrolledtext.ScrolledText, ttk.Entry)):
            is_main_editor = False
            if hasattr(self.translation_edit_text, 'text') and focused == self.translation_edit_text.text:
                is_main_editor = True
            elif hasattr(self, 'comment_edit_text') and hasattr(self.comment_edit_text,
                                                                'text') and focused == self.comment_edit_text.text:
                is_main_editor = True

            if is_main_editor:
                try:
                    focused.edit_undo()
                    return
                except tk.TclError:
                    pass

        if not self.undo_history:
            self.update_statusbar("没有可撤销的操作")
            return

        action_log = self.undo_history.pop()
        action_type, action_data = action_log['type'], action_log['data']
        redo_payload_data = None
        changed_ids = set()

        if action_type == 'single_change':
            obj_id = action_data['string_id']
            field = action_data['field']
            val_to_restore = action_data['old_value']

            ts_obj = self._find_ts_obj_by_id(obj_id)
            if ts_obj:
                current_val_before_undo = getattr(ts_obj,
                                                  field) if field != 'translation' else ts_obj.get_translation_for_storage_and_tm()

                if field == 'translation':
                    ts_obj.set_translation_internal(val_to_restore.replace("\\n", "\n"))
                else:
                    setattr(ts_obj, field, val_to_restore)

                redo_payload_data = {'string_id': obj_id, 'field': field,
                                     'old_value': val_to_restore,
                                     'new_value': current_val_before_undo}
                self.update_statusbar(f"撤销: ID {str(obj_id)[:8]}... '{field}' -> '{str(val_to_restore)[:30]}'")
                changed_ids.add(obj_id)
            else:
                self.update_statusbar(f"撤销错误: 未找到对象ID {obj_id}")
                self.edit_menu.entryconfig("恢复", state=tk.NORMAL if self.redo_history else tk.DISABLED)
                return

        elif action_type in ['bulk_change', 'bulk_excel_import', 'bulk_ai_translate', 'bulk_context_menu',
                             'bulk_replace_all']:
            temp_redo_changes = []
            for item_change in action_data['changes']:
                obj_id, field, val_to_restore = item_change['string_id'], item_change['field'], item_change['old_value']
                ts_obj = self._find_ts_obj_by_id(obj_id)
                if ts_obj:
                    current_val_before_undo = getattr(ts_obj,
                                                      field) if field != 'translation' else ts_obj.get_translation_for_storage_and_tm()
                    if field == 'translation':
                        ts_obj.set_translation_internal(val_to_restore.replace("\\n", "\n"))
                    else:
                        setattr(ts_obj, field, val_to_restore)
                    temp_redo_changes.append({'string_id': obj_id, 'field': field,
                                              'old_value': val_to_restore,
                                              'new_value': current_val_before_undo})
                    changed_ids.add(obj_id)
            redo_payload_data = {'changes': temp_redo_changes}
            self.update_statusbar(f"撤销: 批量更改 ({len(temp_redo_changes)} 项)")

        if redo_payload_data:
            self.redo_history.append({'type': action_type, 'data': redo_payload_data})

        self.refresh_treeview(preserve_selection=True)

        if self.current_selected_ts_id in changed_ids:
            self.on_tree_select(None)

        if not self.undo_history: self.edit_menu.entryconfig("撤销", state=tk.DISABLED)
        self.edit_menu.entryconfig("恢复", state=tk.NORMAL if self.redo_history else tk.DISABLED)
        self.mark_project_modified()

    def redo_action(self, event=None):
        focused = self.root.focus_get()
        if event and isinstance(focused, (tk.Text, scrolledtext.ScrolledText, ttk.Entry)):
            is_main_editor = False
            if hasattr(self.translation_edit_text, 'text') and focused == self.translation_edit_text.text:
                is_main_editor = True
            elif hasattr(self, 'comment_edit_text') and hasattr(self.comment_edit_text,
                                                                'text') and focused == self.comment_edit_text.text:
                is_main_editor = True

            if is_main_editor:
                try:
                    focused.edit_redo()
                    return
                except tk.TclError:
                    pass

        if not self.redo_history:
            self.update_statusbar("没有可恢复的操作")
            return

        action_log = self.redo_history.pop()
        action_type, action_data_to_apply = action_log['type'], action_log['data']
        undo_payload_data = None
        changed_ids = set()

        if action_type == 'single_change':
            obj_id = action_data_to_apply['string_id']
            field = action_data_to_apply['field']

            val_to_set = action_data_to_apply['new_value']

            ts_obj = self._find_ts_obj_by_id(obj_id)
            if ts_obj:
                current_val_before_redo = getattr(ts_obj,
                                                  field) if field != 'translation' else ts_obj.get_translation_for_storage_and_tm()

                if field == 'translation':
                    ts_obj.set_translation_internal(val_to_set.replace("\\n", "\n"))
                else:
                    setattr(ts_obj, field, val_to_set)

                undo_payload_data = {'string_id': obj_id, 'field': field,
                                     'old_value': current_val_before_redo,
                                     'new_value': val_to_set}
                self.update_statusbar(f"恢复: ID {str(obj_id)[:8]}... '{field}' -> '{str(val_to_set)[:30]}'")
                changed_ids.add(obj_id)
            else:
                self.update_statusbar(f"恢复错误: 未找到对象ID {obj_id}")
                self.edit_menu.entryconfig("撤销", state=tk.NORMAL if self.undo_history else tk.DISABLED)
                return

        elif action_type in ['bulk_change', 'bulk_excel_import', 'bulk_ai_translate', 'bulk_context_menu',
                             'bulk_replace_all']:
            temp_undo_changes = []
            for item_change in action_data_to_apply['changes']:
                obj_id, field, val_to_set = item_change['string_id'], item_change['field'], item_change['new_value']
                ts_obj = self._find_ts_obj_by_id(obj_id)
                if ts_obj:
                    current_val_before_redo = getattr(ts_obj,
                                                      field) if field != 'translation' else ts_obj.get_translation_for_storage_and_tm()
                    if field == 'translation':
                        ts_obj.set_translation_internal(val_to_set.replace("\\n", "\n"))
                    else:
                        setattr(ts_obj, field, val_to_set)
                    temp_undo_changes.append({'string_id': obj_id, 'field': field,
                                              'old_value': current_val_before_redo,
                                              'new_value': val_to_set})
                    changed_ids.add(obj_id)
            undo_payload_data = {'changes': temp_undo_changes}
            self.update_statusbar(f"恢复: 批量更改 ({len(temp_undo_changes)} 项)")

        if undo_payload_data:
            self.undo_history.append({'type': action_type, 'data': undo_payload_data})
            if len(self.undo_history) > MAX_UNDO_HISTORY:
                self.undo_history.pop(0)

        self.refresh_treeview(preserve_selection=True)
        if self.current_selected_ts_id in changed_ids:
            self.on_tree_select(None)

        if not self.redo_history: self.edit_menu.entryconfig("恢复", state=tk.DISABLED)
        self.edit_menu.entryconfig("撤销", state=tk.NORMAL if self.undo_history else tk.DISABLED)
        self.mark_project_modified()

    def open_code_file_dialog(self, event=None):
        if not self.prompt_save_if_modified(): return

        filepath = filedialog.askopenfilename(
            title="选择守望先锋自定义代码文件",
            filetypes=(("Overwatch Workshop Files", "*.ow;*.txt"), ("All Files", "*.*")),
            initialdir=self.config.get("last_dir", os.getcwd()),
            parent=self.root
        )
        if filepath:
            self.open_code_file_path(filepath)

    def open_code_file_path(self, filepath):
        if self.is_ai_translating_batch:
            messagebox.showwarning("操作受限", "AI批量翻译正在进行中。请等待其完成或停止后再打开新文件。",
                                   parent=self.root)
            return

        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                self.original_raw_code_content = f.read()

            self.current_code_file_path = filepath
            self.current_project_file_path = None
            self.project_custom_instructions = ""
            self.add_to_recent_files(filepath)
            self.config["last_dir"] = os.path.dirname(filepath)
            self.save_config()

            self.update_statusbar("正在提取字符串...", persistent=True)
            self.root.update_idletasks()

            self.translatable_objects = extract_translatable_strings(self.original_raw_code_content)
            self.apply_tm_to_all_current_strings(silent=True, only_if_empty=True)

            self.undo_history.clear()
            self.redo_history.clear()
            self.current_selected_ts_id = None
            self.mark_project_modified(False)

            self.refresh_treeview()
            self.update_statusbar(
                f"已加载 {len(self.translatable_objects)} 个可翻译字符串从 {os.path.basename(filepath)}",
                persistent=True)
            self.update_ui_state_after_file_load(file_or_project_loaded=True)

        except Exception as e:
            messagebox.showerror("错误", f"无法打开或解析代码文件 '{os.path.basename(filepath)}': {e}",
                                 parent=self.root)
            self._reset_app_state()
            self.update_statusbar("代码文件加载失败", persistent=True)
        self.update_counts_display()

    def open_project_dialog(self, event=None):
        if not self.prompt_save_if_modified(): return

        filepath = filedialog.askopenfilename(
            title="打开项目文件",
            filetypes=(("Overwatch Project Files", f"*{PROJECT_FILE_EXTENSION}"), ("All Files", "*.*")),
            initialdir=self.config.get("last_dir", os.getcwd()),
            parent=self.root
        )
        if filepath:
            self.open_project_file(filepath)

    def open_project_file(self, project_filepath):
        if self.is_ai_translating_batch:
            messagebox.showwarning("操作受限", "AI批量翻译正在进行中。", parent=self.root)
            return

        try:
            loaded_data = load_project(project_filepath)
            project_data = loaded_data["project_data"]

            self.current_code_file_path = loaded_data["original_code_file_path"]
            self.original_raw_code_content = loaded_data["original_raw_code_content"]
            self.translatable_objects = loaded_data["translatable_objects"]

            self.project_custom_instructions = project_data.get("project_custom_instructions", "")

            tm_path_from_project = project_data.get("current_tm_file_path")
            if tm_path_from_project and os.path.exists(tm_path_from_project):
                self.load_tm_from_excel(tm_path_from_project, silent=True)
            elif tm_path_from_project:
                messagebox.showwarning("项目警告", f"项目关联的翻译记忆库文件 '{tm_path_from_project}' 未找到。",
                                       parent=self.root)

            filter_settings = project_data.get("filter_settings", {})
            self.deduplicate_strings_var.set(filter_settings.get("deduplicate", False))
            self.show_ignored_var.set(filter_settings.get("show_ignored", True))
            self.show_untranslated_var.set(filter_settings.get("show_untranslated", False))
            self.show_translated_var.set(filter_settings.get("show_translated", False))
            self.show_unreviewed_var.set(filter_settings.get("show_unreviewed", False))

            self.current_project_file_path = project_filepath
            self.add_to_recent_files(project_filepath)
            self.config["last_dir"] = os.path.dirname(project_filepath)
            self.save_config()

            self.undo_history.clear()
            self.redo_history.clear()
            self.current_selected_ts_id = None
            self.mark_project_modified(False)

            ui_state = project_data.get("ui_state", {})
            self.search_var.set(ui_state.get("search_term", ""))

            self.refresh_treeview()

            selected_id_from_proj = ui_state.get("selected_ts_id")
            if selected_id_from_proj and self.tree.exists(selected_id_from_proj):
                self.tree.selection_set(selected_id_from_proj)
                self.tree.focus(selected_id_from_proj)
                self.tree.see(selected_id_from_proj)
                self.on_tree_select(None)

            self.update_statusbar(f"项目 '{os.path.basename(project_filepath)}' 已加载。", persistent=True)
            self.update_ui_state_after_file_load(file_or_project_loaded=True)

        except Exception as e:
            messagebox.showerror("打开项目错误", f"无法加载项目文件 '{os.path.basename(project_filepath)}': {e}",
                                 parent=self.root)
            self._reset_app_state()
            self.update_statusbar("项目文件加载失败。", persistent=True)
        self.update_counts_display()

    def _reset_app_state(self):
        self.current_code_file_path = None
        self.current_project_file_path = None
        self.original_raw_code_content = ""
        self.project_custom_instructions = ""
        self.translatable_objects = []
        self.redo_history.clear()
        self.current_selected_ts_id = None
        self.mark_project_modified(False)
        self.refresh_treeview()
        self.clear_details_pane()
        self.update_ui_state_after_file_load(file_or_project_loaded=False)
        self.update_title()

    def prompt_save_if_modified(self):
        if self.current_project_modified:
            response = messagebox.askyesnocancel("未保存的更改",
                                                 "当前项目有未保存的更改。是否保存？",
                                                 parent=self.root)
            if response is True:
                return self.save_project_dialog()
            elif response is False:
                return True
            else:
                return False
        return True

    def refresh_treeview_preserve_selection(self, item_to_reselect_after=None):
        self.refresh_treeview(preserve_selection=True, item_to_reselect_after=item_to_reselect_after)

    def _configure_treeview_tags(self):
        try:
            if self._ignored_tag_font is None and hasattr(self.tree, 'cget'):
                font_description = self.tree.cget("font")
                if font_description:
                    base_font = tkinter.font.nametofont(font_description)
                    self._ignored_tag_font = tkinter.font.Font(
                        family=base_font.actual("family"),
                        size=base_font.actual("size"),
                        slant="italic"
                    )

            ignored_fg = "#707070"

            if self._ignored_tag_font:
                self.tree.tag_configure('ignored_row_visual', font=self._ignored_tag_font, foreground=ignored_fg)
            else:
                self.tree.tag_configure('ignored_row_visual', foreground=ignored_fg)

            self.tree.tag_configure('auto_ignored_visual', foreground="#a0a0a0",
                                    font=self._ignored_tag_font if self._ignored_tag_font else None)
            self.tree.tag_configure('translated_row_visual', foreground="darkblue")
            self.tree.tag_configure('untranslated_row_visual', foreground="darkred")
            self.tree.tag_configure('reviewed_visual',
                                    foreground="darkgreen")
            self.tree.tag_configure('search_highlight', background='yellow', foreground='black')

            self.original_text_display.tag_configure('placeholder', foreground='darkblue',
                                                     font=('Segoe UI', 10, 'bold'))
            self.original_text_display.tag_configure('placeholder_missing', background='#FFDDDD', foreground='red')
            self.translation_edit_text.tag_configure('placeholder', foreground='darkblue',
                                                     font=('Segoe UI', 10, 'bold'))
            self.translation_edit_text.tag_configure('placeholder_extra', background='#FFEBCD', foreground='orange red')


        except Exception as e:
            print(f"Error configuring treeview tags/font: {e}")
            self.tree.tag_configure('ignored_row_visual', foreground="#777777")
            self.tree.tag_configure('translated_row_visual', foreground="blue")
            self.tree.tag_configure('untranslated_row_visual', foreground="red")
            self.tree.tag_configure('reviewed_visual', foreground="green")
            self.tree.tag_configure('search_highlight', background='yellow', foreground='black')

    def refresh_treeview(self, preserve_selection=True, item_to_reselect_after=None):
        old_selection = self.tree.selection()
        old_focus = self.tree.focus()

        self.tree.delete(*self.tree.get_children())
        self.displayed_string_ids = []

        processed_originals_for_dedup = set()
        seq_id_counter = 1
        search_term = self.search_var.get().lower()
        if search_term == "快速搜索...": search_term = ""

        for ts_obj in self.translatable_objects:
            if self.deduplicate_strings_var.get():
                if ts_obj.original_semantic in processed_originals_for_dedup:
                    continue
            if not self.show_ignored_var.get() and ts_obj.is_ignored:
                continue
            has_translation = bool(ts_obj.translation.strip())
            if self.show_untranslated_var.get() and has_translation and not ts_obj.is_ignored:
                continue
            if self.show_translated_var.get() and not has_translation and not ts_obj.is_ignored:
                continue
            if self.show_unreviewed_var.get() and ts_obj.is_reviewed:
                continue
            if search_term:
                if not (search_term in ts_obj.original_semantic.lower() or
                        search_term in ts_obj.get_translation_for_ui().lower() or
                        search_term in ts_obj.comment.lower()):
                    continue

            if self.deduplicate_strings_var.get():
                processed_originals_for_dedup.add(ts_obj.original_semantic)

            tags = []
            status_char = ""
            if ts_obj.is_ignored:
                tags.append('ignored_row_visual')
                status_char = "I"
                if ts_obj.was_auto_ignored:
                    tags.append('auto_ignored_visual')
                    status_char = "A"
            elif ts_obj.translation.strip():
                tags.append('translated_row_visual')
                status_char = "T"
                if ts_obj.is_reviewed:
                    tags.append('reviewed_visual')
            else:
                tags.append('untranslated_row_visual')
                status_char = "U"
                if ts_obj.is_reviewed:
                    tags.append('reviewed_visual')

            values = (
                seq_id_counter, status_char,
                ts_obj.original_semantic.replace("\n", "↵"),
                ts_obj.get_translation_for_ui().replace("\n", "↵"),
                ts_obj.comment.replace("\n", "↵")[:50],
                "✔" if ts_obj.is_reviewed else "",
                ts_obj.line_num_in_file
            )

            self.tree.insert("", "end", iid=ts_obj.id, values=values, tags=tuple(tags))
            self.displayed_string_ids.append(ts_obj.id)
            seq_id_counter += 1

        if preserve_selection:
            if item_to_reselect_after and self.tree.exists(item_to_reselect_after):
                self.tree.selection_set((item_to_reselect_after,))
                self.tree.focus(item_to_reselect_after)
                self.tree.see(item_to_reselect_after)
            else:
                new_selection = [iid for iid in old_selection if self.tree.exists(iid)]
                if new_selection:
                    self.tree.selection_set(tuple(new_selection))
                    if old_focus and self.tree.exists(old_focus):
                        self.tree.focus(old_focus)
                        self.tree.see(old_focus)
                    else:
                        self.tree.focus(new_selection[0])
                        self.tree.see(new_selection[0])

        self.update_counts_display()
        self.on_tree_select(None)

    def find_string_from_toolbar(self):
        search_term = self.search_var.get()
        if search_term == "快速搜索...":
            self.search_var.set("")

        self.refresh_treeview_preserve_selection()

        if self.displayed_string_ids:
            first_match_id = self.displayed_string_ids[0]
            if self.tree.exists(first_match_id) and self.tree.focus() != first_match_id:
                self.tree.selection_set(first_match_id)
                self.tree.focus(first_match_id)
                self.tree.see(first_match_id)
                self.on_tree_select(None)
            self.update_statusbar(f"已按 '{self.search_var.get()}' 筛选。")
        elif self.search_var.get() and self.search_var.get() != "快速搜索...":
            self.update_statusbar(f"当前筛选条件下未找到 '{self.search_var.get()}'")
        else:
            self.update_statusbar("搜索已清除。")

        if not self.search_var.get() and hasattr(self.search_entry, 'insert'):
            self.search_entry.insert(0, "快速搜索...")
            self.search_entry.config(foreground="grey")

    def _get_ts_obj_from_tree_iid(self, tree_iid):
        if not tree_iid: return None
        return self._find_ts_obj_by_id(tree_iid)

    def on_tree_select(self, event):
        if self.current_selected_ts_id:
            ts_obj_before_change = self._find_ts_obj_by_id(self.current_selected_ts_id)
            if ts_obj_before_change:
                current_editor_text = self.translation_edit_text.get("1.0", tk.END).rstrip('\n')
                if current_editor_text != ts_obj_before_change.get_translation_for_ui():
                    self._apply_translation_to_model(ts_obj_before_change, current_editor_text, source="manual_focus_out")

        focused_iid = self.tree.focus()
        if self.current_selected_ts_id == focused_iid and event is not None:
            return

        if not focused_iid:
            self.clear_details_pane()
            self.current_selected_ts_id = None
            self.update_ui_state_for_selection(None)
            return

        ts_obj = self._find_ts_obj_by_id(focused_iid)
        if not ts_obj:
            self.clear_details_pane()
            self.current_selected_ts_id = None
            self.update_ui_state_for_selection(None)
            return

        self.current_selected_ts_id = ts_obj.id

        self.original_text_display.config(state=tk.NORMAL)
        self.original_text_display.delete("1.0", tk.END)
        self.original_text_display.insert("1.0", ts_obj.original_semantic)
        self.original_text_display.config(state=tk.DISABLED)

        self.translation_edit_text.delete("1.0", tk.END)
        self.translation_edit_text.insert("1.0", ts_obj.get_translation_for_ui())
        self.translation_edit_text.edit_reset()

        self._update_placeholder_highlights()

        self.comment_edit_text.delete("1.0", tk.END)
        self.comment_edit_text.insert("1.0", ts_obj.comment)
        self.comment_edit_text.edit_reset()

        self.context_text_display.config(state=tk.NORMAL)
        self.context_text_display.delete("1.0", tk.END)
        self.context_text_display.tag_remove("highlight", "1.0", tk.END)
        if ts_obj.context_lines:
            for i, line_text in enumerate(ts_obj.context_lines):
                self.context_text_display.insert(tk.END, line_text + "\n")
                if i == ts_obj.current_line_in_context_idx:
                    self.context_text_display.tag_add("highlight", f"{i + 1}.0", f"{i + 1}.end")
            if ts_obj.current_line_in_context_idx >= 0:
                self.context_text_display.see(f"{ts_obj.current_line_in_context_idx + 1}.0")
        self.context_text_display.config(state=tk.DISABLED)

        self.ignore_var.set(ts_obj.is_ignored)
        ignore_label = "忽略此字符串"
        if ts_obj.is_ignored and ts_obj.was_auto_ignored:
            ignore_label += " (自动)"
        self.toggle_ignore_btn.config(text=ignore_label)

        self.reviewed_var.set(ts_obj.is_reviewed)
        self.update_tm_suggestions_for_text(ts_obj.original_semantic)

        if hasattr(self, 'clear_selected_tm_btn'):
            self.clear_selected_tm_btn.config(
                state=tk.NORMAL if ts_obj.original_semantic in self.translation_memory else tk.DISABLED)

        self.update_statusbar(f"选中: \"{ts_obj.original_semantic[:30].replace(chr(10),'↵')}...\" (行: {ts_obj.line_num_in_file})", persistent=True)
        self.update_ui_state_for_selection(self.current_selected_ts_id)

    def schedule_placeholder_validation(self, event=None):
        if self._placeholder_validation_job:
            self.root.after_cancel(self._placeholder_validation_job)
        self._placeholder_validation_job = self.root.after(150, self._update_placeholder_highlights)

    def _update_placeholder_highlights(self):
        if not self.current_selected_ts_id:
            return

        ts_obj = self._find_ts_obj_by_id(self.current_selected_ts_id)
        if not ts_obj:
            return

        original_text = ts_obj.original_semantic
        translated_text = self.translation_edit_text.get("1.0", tk.END)

        original_placeholders = set(self.placeholder_regex.findall(original_text))
        translated_placeholders = set(self.placeholder_regex.findall(translated_text))
        missing_in_translation = original_placeholders - translated_placeholders
        extra_in_translation = translated_placeholders - original_placeholders

        self.original_text_display.config(state=tk.NORMAL)
        try:
            self.original_text_display.tag_remove('placeholder', '1.0', tk.END)
            self.original_text_display.tag_remove('placeholder_missing', '1.0', tk.END)
            for match in self.placeholder_regex.finditer(original_text):
                start, end = match.span()
                tag = 'placeholder_missing' if match.group(1) in missing_in_translation else 'placeholder'
                start_coord = f"1.0+{start}c"
                end_coord = f"1.0+{end}c"
                self.original_text_display.tag_add(tag, start_coord, end_coord)
        finally:
            self.original_text_display.config(state=tk.DISABLED)

        self.translation_edit_text.tag_remove('placeholder', '1.0', tk.END)
        self.translation_edit_text.tag_remove('placeholder_extra', '1.0', tk.END)
        for match in self.placeholder_regex.finditer(translated_text):
            start, end = match.span()
            tag = 'placeholder_extra' if match.group(1) in extra_in_translation else 'placeholder'
            start_coord = f"1.0+{start}c"
            end_coord = f"1.0+{end}c"
            self.translation_edit_text.tag_add(tag, start_coord, end_coord)

        self.root.update_idletasks()

    def update_ui_state_for_selection(self, selected_id):
        state = tk.NORMAL if selected_id else tk.DISABLED

        try:
            self.edit_menu.entryconfig("复制原文", state=state)
            self.edit_menu.entryconfig("粘贴到译文", state=state)
        except tk.TclError:
            pass

        if hasattr(self, 'apply_btn'): self.apply_btn.config(state=state)
        if hasattr(self, 'toggle_ignore_btn'): self.toggle_ignore_btn.config(state=state)
        if hasattr(self, 'toggle_reviewed_btn'): self.toggle_reviewed_btn.config(state=state)
        if hasattr(self, 'apply_comment_btn'): self.apply_comment_btn.config(state=state)
        if hasattr(self, 'update_selected_tm_btn'): self.update_selected_tm_btn.config(state=state)

        if not selected_id and hasattr(self, 'clear_selected_tm_btn'):
            self.clear_selected_tm_btn.config(state=tk.DISABLED)
        self.update_ai_related_ui_state()

    def clear_details_pane(self):
        self.translation_edit_text.delete(1.0, tk.END)
        self.comment_edit_text.delete(1.0, tk.END)
        self.reviewed_var.set(False)

        self.original_text_display.config(state=tk.NORMAL)
        self.original_text_display.delete("1.0", tk.END)
        self.original_text_display.config(state=tk.DISABLED)

        self.translation_edit_text.delete("1.0", tk.END)
        self.comment_edit_text.delete("1.0", tk.END)

        self.context_text_display.config(state=tk.NORMAL)
        self.context_text_display.delete("1.0", tk.END)
        self.context_text_display.config(state=tk.DISABLED)

        self.ignore_var.set(False)
        self.reviewed_var.set(False)

        self.apply_btn["state"] = tk.DISABLED
        self.apply_comment_btn["state"] = tk.DISABLED
        self.toggle_ignore_btn["state"] = tk.DISABLED
        self.toggle_reviewed_btn["state"] = tk.DISABLED
        self.tm_suggestions_listbox.delete(0, tk.END)

    def _apply_translation_to_model(self, ts_obj, new_translation_from_ui, source="manual"):
        if new_translation_from_ui == ts_obj.translation:
            return False

        old_translation_for_undo = ts_obj.get_translation_for_storage_and_tm()
        ts_obj.set_translation_internal(new_translation_from_ui)
        new_translation_for_tm_storage = ts_obj.get_translation_for_storage_and_tm()

        primary_change_data = {
            'string_id': ts_obj.id,
            'field': 'translation',
            'old_value': old_translation_for_undo,
            'new_value': new_translation_for_tm_storage
        }

        if ts_obj.original_semantic not in self.translation_memory:
            if new_translation_from_ui.strip():
                self.translation_memory[ts_obj.original_semantic] = new_translation_for_tm_storage
        else:
            pass

        undo_action_type = 'single_change'
        undo_data_payload = primary_change_data

        all_changes_for_undo_list = [primary_change_data]
        for other_ts_obj in self.translatable_objects:
            if other_ts_obj.id != ts_obj.id and \
                    other_ts_obj.original_semantic == ts_obj.original_semantic and \
                    other_ts_obj.translation != new_translation_from_ui:
                old_other_translation_for_undo = other_ts_obj.get_translation_for_storage_and_tm()
                other_ts_obj.set_translation_internal(new_translation_from_ui)
                all_changes_for_undo_list.append({
                    'string_id': other_ts_obj.id,
                    'field': 'translation',
                    'old_value': old_other_translation_for_undo,
                    'new_value': new_translation_for_tm_storage
                })
        if len(all_changes_for_undo_list) > 1:
            undo_action_type = 'bulk_change'
            undo_data_payload = {'changes': all_changes_for_undo_list}

        if source not in ["ai_batch_item"]:
            self.add_to_undo_history(undo_action_type, undo_data_payload)
        else:
            return primary_change_data

        self.refresh_treeview(preserve_selection=True)
        self.update_statusbar(f"翻译已应用: \"{ts_obj.original_semantic[:20].replace(chr(10), '↵')}...\"")

        if self.current_selected_ts_id == ts_obj.id:
            tm_exists_for_selected = ts_obj.original_semantic in self.translation_memory
            self.clear_selected_tm_btn.config(state=tk.NORMAL if tm_exists_for_selected else tk.DISABLED)
            self.update_tm_suggestions_for_text(ts_obj.original_semantic)

        self.mark_project_modified()
        return True

    def apply_translation_from_button(self):
        if not self.current_selected_ts_id: return
        ts_obj = self._find_ts_obj_by_id(self.current_selected_ts_id)
        if not ts_obj: return

        new_translation_ui = self.translation_edit_text.get("1.0", tk.END).rstrip('\n')
        self._apply_translation_to_model(ts_obj, new_translation_ui, source="manual_button")

    def apply_translation_focus_out(self, event=None):
        if not self.current_selected_ts_id: return
        if event and event.widget != self.translation_edit_text:
            return

        ts_obj = self._find_ts_obj_by_id(self.current_selected_ts_id)
        if not ts_obj: return

        new_translation_ui = self.translation_edit_text.get("1.0", tk.END).rstrip('\n')
        if new_translation_ui != ts_obj.get_translation_for_ui():
            self._apply_translation_to_model(ts_obj, new_translation_ui, source="manual_focus_out")

    def apply_comment_from_button(self):
        if not self.current_selected_ts_id: return
        ts_obj = self._find_ts_obj_by_id(self.current_selected_ts_id)
        if not ts_obj: return
        new_comment = self.comment_edit_text.get("1.0", tk.END).rstrip('\n')
        self._apply_comment_to_model(ts_obj, new_comment)

    def apply_comment_focus_out(self, event=None):
        if not self.current_selected_ts_id: return
        if event and event.widget != self.comment_edit_text: return

        ts_obj = self._find_ts_obj_by_id(self.current_selected_ts_id)
        if not ts_obj: return
        new_comment = self.comment_edit_text.get("1.0", tk.END).rstrip('\n')
        if new_comment != ts_obj.comment:
            self._apply_comment_to_model(ts_obj, new_comment)

    def _apply_comment_to_model(self, ts_obj, new_comment):
        if new_comment == ts_obj.comment: return False

        old_comment = ts_obj.comment
        ts_obj.comment = new_comment

        self.add_to_undo_history('single_change', {
            'string_id': ts_obj.id, 'field': 'comment',
            'old_value': old_comment, 'new_value': new_comment
        })
        self.refresh_treeview(preserve_selection=True)
        self.update_statusbar(f"注释已更新 for ID {str(ts_obj.id)[:8]}...")
        self.mark_project_modified()
        return True

    def toggle_ignore_selected_checkbox(self):
        if not self.current_selected_ts_id: return
        ts_obj = self._find_ts_obj_by_id(self.current_selected_ts_id)
        if not ts_obj: return

        new_ignore_state = self.ignore_var.get()
        if new_ignore_state == ts_obj.is_ignored: return

        primary_change = {
            'string_id': ts_obj.id, 'field': 'is_ignored',
            'old_value': ts_obj.is_ignored, 'new_value': new_ignore_state
        }

        ts_obj.is_ignored = new_ignore_state
        if not new_ignore_state:
            ts_obj.was_auto_ignored = False

        all_changes_for_undo = [primary_change]
        for other_ts_obj in self.translatable_objects:
            if other_ts_obj.id != ts_obj.id and \
                    other_ts_obj.original_semantic == ts_obj.original_semantic and \
                    other_ts_obj.is_ignored != new_ignore_state:

                old_other_ignore = other_ts_obj.is_ignored
                other_ts_obj.is_ignored = new_ignore_state
                if not new_ignore_state: other_ts_obj.was_auto_ignored = False
                all_changes_for_undo.append({
                    'string_id': other_ts_obj.id, 'field': 'is_ignored',
                    'old_value': old_other_ignore, 'new_value': new_ignore_state
                })

        undo_action_type = 'bulk_change' if len(all_changes_for_undo) > 1 else 'single_change'
        undo_data_payload = {'changes': all_changes_for_undo} if undo_action_type == 'bulk_change' else primary_change

        self.add_to_undo_history(undo_action_type, undo_data_payload)

        self.refresh_treeview_and_select_neighbor(ts_obj.id)

        self.update_statusbar(f"ID {str(ts_obj.id)[:8]}... 忽略状态 -> {'是' if new_ignore_state else '否'}")
        self.mark_project_modified()

    def toggle_reviewed_selected_checkbox(self):
        if not self.current_selected_ts_id: return
        ts_obj = self._find_ts_obj_by_id(self.current_selected_ts_id)
        if not ts_obj: return

        new_reviewed_state = self.reviewed_var.get()
        if new_reviewed_state == ts_obj.is_reviewed: return

        old_reviewed_state = ts_obj.is_reviewed
        ts_obj.is_reviewed = new_reviewed_state

        self.add_to_undo_history('single_change', {
            'string_id': ts_obj.id, 'field': 'is_reviewed',
            'old_value': old_reviewed_state, 'new_value': new_reviewed_state
        })
        self.refresh_treeview_and_select_neighbor(ts_obj.id)
        self.update_statusbar(f"ID {str(ts_obj.id)[:8]}... 审阅状态 -> {'是' if new_reviewed_state else '否'}")
        self.mark_project_modified()

    def refresh_treeview_and_select_neighbor(self, removed_item_id):
        all_iids_before = list(self.tree.get_children(''))
        neighbor_to_select = None
        if removed_item_id in all_iids_before:
            try:
                idx = all_iids_before.index(removed_item_id)
                if idx + 1 < len(all_iids_before):
                    neighbor_to_select = all_iids_before[idx + 1]
                elif idx - 1 >= 0:
                    neighbor_to_select = all_iids_before[idx - 1]
            except ValueError:
                pass

        self.refresh_treeview(preserve_selection=True, item_to_reselect_after=neighbor_to_select)

    def save_code_file_content(self, filepath_to_save):
        if not self.original_raw_code_content:
            messagebox.showerror("错误", "没有原始代码文件内容可用于保存。\n请确保项目关联的代码文件已加载。",
                                 parent=self.root)
            return False
        try:
            save_translated_code(filepath_to_save, self.original_raw_code_content, self.translatable_objects, self)
            self.update_statusbar(f"代码文件已保存到: {os.path.basename(filepath_to_save)}", persistent=True)
            return True
        except Exception as e_save:
            messagebox.showerror("保存错误", f"无法保存代码文件: {e_save}", parent=self.root)
            return False

    def save_code_file(self, event=None):
        if not self.current_code_file_path:
            messagebox.showerror("错误", "无原始代码文件路径。", parent=self.root)
            return

        if not self.original_raw_code_content:
            messagebox.showerror("错误", "无原始代码内容可保存。", parent=self.root)
            return

        base, ext = os.path.splitext(self.current_code_file_path)
        new_filepath = f"{base}_translated{ext}"

        if os.path.exists(new_filepath):
            if not messagebox.askyesno("确认覆盖",
                                       f"文件 '{os.path.basename(new_filepath)}' 已存在。是否覆盖？\n将会创建一个备份文件 (.bak)。",
                                       parent=self.root):
                return

        self.save_code_file_content(new_filepath)

    def save_project_dialog(self, event=None):
        if self.current_project_file_path:
            return self.save_project_file(self.current_project_file_path)
        else:
            return self.save_project_as_dialog()

    def save_project_as_dialog(self, event=None):
        if not self.translatable_objects and not self.current_code_file_path:
            messagebox.showinfo("提示", "没有内容可保存为项目。\n请先打开一个代码文件。", parent=self.root)
            return False

        initial_dir = os.path.dirname(
            self.current_project_file_path or self.current_code_file_path or self.config.get("last_dir", os.getcwd()))

        default_proj_name = "my_project"
        if self.current_project_file_path:
            default_proj_name = os.path.splitext(os.path.basename(self.current_project_file_path))[0]
        elif self.current_code_file_path:
            default_proj_name = os.path.splitext(os.path.basename(self.current_code_file_path))[0]

        initial_file = default_proj_name + PROJECT_FILE_EXTENSION

        filepath = filedialog.asksaveasfilename(
            defaultextension=PROJECT_FILE_EXTENSION,
            filetypes=(("Overwatch Project Files", f"*{PROJECT_FILE_EXTENSION}"), ("All Files", "*.*")),
            initialdir=initial_dir,
            initialfile=initial_file,
            title="项目另存为",
            parent=self.root
        )
        if filepath:
            return self.save_project_file(filepath)
        return False

    def save_project_file(self, project_filepath):
        if save_project(project_filepath, self):
            self.current_project_file_path = project_filepath
            self.add_to_recent_files(project_filepath)
            self.mark_project_modified(False)
            self.update_statusbar(f"项目已保存到: {os.path.basename(project_filepath)}", persistent=True)
            self.update_title()
            self.config["last_dir"] = os.path.dirname(project_filepath)
            self.save_config()
            self.tools_menu.entryconfig("项目个性化翻译设置...", state=tk.NORMAL)
            return True
        return False

    def export_project_translations_to_excel(self):
        if not self.translatable_objects:
            messagebox.showinfo("提示", "无数据可导出。", parent=self.root)
            return

        default_filename = "project_translations.xlsx"
        if self.current_project_file_path:
            base, _ = os.path.splitext(os.path.basename(self.current_project_file_path))
            default_filename = f"{base}_translations.xlsx"
        elif self.current_code_file_path:
            base, _ = os.path.splitext(os.path.basename(self.current_code_file_path))
            default_filename = f"{base}_translations.xlsx"

        filepath = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=(("Excel files", "*.xlsx"),),
            initialfile=default_filename,
            title="导出项目翻译到Excel",
            parent=self.root
        )
        if not filepath: return

        wb = Workbook()
        ws = wb.active
        ws.title = "Translations"
        headers = ["UUID", "类型", "原文 (Semantic)", "译文", "注释", "是否审阅", "是否忽略", "源文件行号",
                   "原文 (Raw)"]
        ws.append(headers)

        items_to_export = [self._find_ts_obj_by_id(ts_id) for ts_id in self.displayed_string_ids if
                           self._find_ts_obj_by_id(ts_id)]
        if not items_to_export and self.translatable_objects:
            items_to_export = self.translatable_objects

        for ts_obj in items_to_export:
            ws.append([
                ts_obj.id,
                ts_obj.string_type,
                ts_obj.original_semantic,
                ts_obj.get_translation_for_storage_and_tm(),
                ts_obj.comment,
                "是" if ts_obj.is_reviewed else "否",
                "是" if ts_obj.is_ignored else "否",
                ts_obj.line_num_in_file,
                ts_obj.original_raw
            ])
        try:
            wb.save(filepath)
            self.update_statusbar(f"项目翻译已导出到: {os.path.basename(filepath)}")
        except Exception as e:
            messagebox.showerror("导出错误", f"无法导出项目翻译到Excel: {e}", parent=self.root)

    def import_project_translations_from_excel(self):
        if not self.translatable_objects:
            messagebox.showinfo("提示", "请先加载代码文件或项目以匹配导入的翻译。", parent=self.root)
            return

        filepath = filedialog.askopenfilename(
            filetypes=(("Excel files", "*.xlsx"),),
            title="从Excel导入项目翻译",
            parent=self.root
        )
        if not filepath: return

        try:
            wb = load_workbook(filepath, read_only=True)
            ws = wb.active

            header_row_values = [cell.value for cell in ws[1]]
            if not header_row_values or not all(isinstance(h, str) for h in header_row_values if h is not None):
                messagebox.showerror("导入错误", "Excel表头格式不正确或为空。", parent=self.root)
                return

            try:
                uuid_col_idx = header_row_values.index("UUID")
                trans_col_idx = header_row_values.index("译文")
                comment_col_idx = header_row_values.index("注释") if "注释" in header_row_values else -1
                reviewed_col_idx = header_row_values.index("是否审阅") if "是否审阅" in header_row_values else -1
                ignored_col_idx = header_row_values.index("是否忽略") if "是否忽略" in header_row_values else -1
                orig_col_idx = header_row_values.index(
                    "原文 (Semantic)") if "原文 (Semantic)" in header_row_values else -1
            except ValueError:
                messagebox.showerror("导入错误",
                                     "Excel表头必须包含 'UUID' 和 '译文' 列。\n可选列: '注释', '是否审阅', '是否忽略', '原文 (Semantic)'。",
                                     parent=self.root)
                return

            imported_count = 0
            changes_for_undo = []

            for r_idx, row_cells in enumerate(ws.iter_rows(min_row=2, values_only=True)):
                try:
                    obj_id_from_excel = row_cells[uuid_col_idx]
                    if obj_id_from_excel is None: continue

                    ts_obj = self._find_ts_obj_by_id(str(obj_id_from_excel))
                    if not ts_obj:
                        continue

                    if orig_col_idx != -1 and row_cells[orig_col_idx] is not None:
                        if ts_obj.original_semantic != str(row_cells[orig_col_idx]):
                            print(
                                f"警告: Excel行 {r_idx + 2}, UUID {obj_id_from_excel} - 原文与Excel中的不匹配。仍将导入数据。")

                    translation_from_excel_raw = str(row_cells[trans_col_idx]) if row_cells[
                                                                                      trans_col_idx] is not None else ""
                    translation_for_model = translation_from_excel_raw.replace("\\n", "\n")
                    if ts_obj.translation != translation_for_model:
                        changes_for_undo.append({'string_id': ts_obj.id, 'field': 'translation',
                                                 'old_value': ts_obj.get_translation_for_storage_and_tm(),
                                                 'new_value': translation_from_excel_raw})
                        ts_obj.set_translation_internal(translation_for_model)
                        if translation_for_model.strip():
                            self.translation_memory[ts_obj.original_semantic] = translation_from_excel_raw
                        imported_count += 1

                    if comment_col_idx != -1 and row_cells[comment_col_idx] is not None:
                        comment_from_excel = str(row_cells[comment_col_idx])
                        if ts_obj.comment != comment_from_excel:
                            changes_for_undo.append(
                                {'string_id': ts_obj.id, 'field': 'comment', 'old_value': ts_obj.comment,
                                 'new_value': comment_from_excel})
                            ts_obj.comment = comment_from_excel
                            if not imported_count: imported_count = 1

                    if reviewed_col_idx != -1 and row_cells[reviewed_col_idx] is not None:
                        reviewed_str = str(row_cells[reviewed_col_idx]).lower()
                        is_reviewed_excel = reviewed_str in ["是", "true", "yes", "1"]
                        if ts_obj.is_reviewed != is_reviewed_excel:
                            changes_for_undo.append(
                                {'string_id': ts_obj.id, 'field': 'is_reviewed', 'old_value': ts_obj.is_reviewed,
                                 'new_value': is_reviewed_excel})
                            ts_obj.is_reviewed = is_reviewed_excel
                            if not imported_count: imported_count = 1

                    if ignored_col_idx != -1 and row_cells[ignored_col_idx] is not None:
                        ignored_str = str(row_cells[ignored_col_idx]).lower()
                        is_ignored_excel = ignored_str in ["是", "true", "yes", "1"]
                        if ts_obj.is_ignored != is_ignored_excel:
                            changes_for_undo.append(
                                {'string_id': ts_obj.id, 'field': 'is_ignored', 'old_value': ts_obj.is_ignored,
                                 'new_value': is_ignored_excel})
                            ts_obj.is_ignored = is_ignored_excel
                            if not is_ignored_excel: ts_obj.was_auto_ignored = False
                            if not imported_count: imported_count = 1

                except Exception as cell_err:
                    print(f"处理 Excel 行 {r_idx + 2} 时出错: {cell_err}。跳过此行。")

            if changes_for_undo:
                self.add_to_undo_history('bulk_excel_import', {'changes': changes_for_undo})
                self.mark_project_modified()

            self.refresh_treeview(preserve_selection=True)
            if self.current_selected_ts_id: self.on_tree_select(None)

            self.update_statusbar(f"从Excel导入/更新了 {len(changes_for_undo)} 个字段 ({imported_count} 个项目受影响)。")

        except ValueError as ve:
            messagebox.showerror("导入错误", f"处理Excel文件时出错 (可能是列名问题): {ve}", parent=self.root)
        except Exception as e:
            messagebox.showerror("导入错误", f"无法从Excel导入项目翻译: {e}", parent=self.root)

    def _get_default_tm_excel_path(self):
        return os.path.join(os.getcwd(), TM_FILE_EXCEL)

    def _load_default_tm_excel(self):
        default_tm_path = self._get_default_tm_excel_path()
        if os.path.exists(default_tm_path):
            self.load_tm_from_excel(default_tm_path, silent=True)

    def load_tm_from_excel(self, filepath, silent=False):
        try:
            workbook = load_workbook(filepath, read_only=True)
            sheet = workbook.active
            loaded_count = 0
            new_tm_data = {}

            header = [cell.value for cell in sheet[1]]
            original_col_idx, translation_col_idx = -1, -1

            if header and len(header) >= 2:
                for i, col_name in enumerate(header):
                    if isinstance(col_name, str):
                        if "original" in col_name.lower() or "原文" in col_name:
                            original_col_idx = i
                        if "translation" in col_name.lower() or "译文" in col_name:
                            translation_col_idx = i

            if original_col_idx == -1 or translation_col_idx == -1:
                if not silent:
                    messagebox.showwarning("TM加载警告",
                                           f"无法从 '{os.path.basename(filepath)}' 的表头确定原文/译文列。"
                                           f"将尝试默认使用前两列 (A=原文, B=译文)。", parent=self.root)
                original_col_idx, translation_col_idx = 0, 1

            start_row = 2 if header else 1
            for row_idx, row in enumerate(sheet.iter_rows(min_row=start_row, values_only=True)):
                if len(row) > max(original_col_idx, translation_col_idx):
                    original_val = row[original_col_idx]
                    translation_val = row[translation_col_idx]
                    if original_val is not None and translation_val is not None:
                        original = str(original_val)
                        translation_with_literal_slash_n = str(translation_val)

                        if original.strip():
                            new_tm_data[original] = translation_with_literal_slash_n
                            loaded_count += 1

            self.translation_memory.update(new_tm_data)

            if not silent:
                messagebox.showinfo("翻译记忆库",
                                    f"从 '{os.path.basename(filepath)}' 加载/合并了 {loaded_count} 条Excel记忆库记录。",
                                    parent=self.root)
            self.current_tm_file = filepath
            self.update_statusbar(f"翻译记忆库已从 '{os.path.basename(filepath)}' (Excel) 加载。")

        except Exception as e:
            if not silent:
                messagebox.showerror("错误", f"无法加载Excel翻译记忆库: {e}", parent=self.root)
            self.update_statusbar(f"加载Excel翻译记忆库失败: {e}")

    def save_tm_to_excel(self, filepath_to_save, silent=False, backup=True):
        if not self.translation_memory:
            if not silent:
                messagebox.showinfo("翻译记忆库", "记忆库为空，无需保存。", parent=self.root)
            return

        if backup and self.auto_backup_tm_on_save_var.get() and os.path.exists(filepath_to_save):
            try:
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_dir = os.path.join(os.path.dirname(filepath_to_save), "tm_backups")
                os.makedirs(backup_dir, exist_ok=True)

                base_name, ext = os.path.splitext(os.path.basename(filepath_to_save))
                backup_filename = f"{base_name}_{timestamp}{ext}"
                backup_path = os.path.join(backup_dir, backup_filename)

                shutil.copy2(filepath_to_save, backup_path)
            except Exception as e_backup:
                if not silent:
                    if self.root.winfo_exists():
                        messagebox.showwarning("备份失败", f"无法为记忆库创建备份: {e_backup}", parent=self.root)

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "TranslationMemory"
        sheet['A1'] = "Original"
        sheet['B1'] = "Translation"

        row_num = 2
        for original, translation_with_literal_slash_n in self.translation_memory.items():
            sheet[f'A{row_num}'] = original
            sheet[f'B{row_num}'] = translation_with_literal_slash_n
            row_num += 1

        try:
            workbook.save(filepath_to_save)
            if not silent:
                messagebox.showinfo("翻译记忆库", f"记忆库已保存到 '{os.path.basename(filepath_to_save)}'.",
                                    parent=self.root)
            self.current_tm_file = filepath_to_save
            self.update_statusbar(f"记忆库已保存到 '{os.path.basename(filepath_to_save)}'.")
        except Exception as e_save:
            if not silent:
                messagebox.showerror("错误", f"无法保存翻译记忆库: {e_save}", parent=self.root)

    def import_tm_excel_dialog(self):
        filepath = filedialog.askopenfilename(
            title="导入翻译记忆库 (Excel)",
            filetypes=(("Excel files", "*.xlsx"), ("All files", "*.*")),
            defaultextension=".xlsx",
            parent=self.root
        )
        if not filepath: return

        self.load_tm_from_excel(filepath)

        if self.translatable_objects and \
                messagebox.askyesno("应用记忆库", "记忆库已导入。是否立即将其应用于当前项目中未翻译的字符串？",
                                    parent=self.root):
            self.apply_tm_to_all_current_strings(only_if_empty=True)

    def export_tm_excel_dialog(self):
        if not self.translation_memory:
            messagebox.showinfo("翻译记忆库", "当前记忆库为空，无法导出。", parent=self.root)
            return

        initial_tm_filename = os.path.basename(
            self.current_tm_file if self.current_tm_file else self._get_default_tm_excel_path())
        filepath = filedialog.asksaveasfilename(
            title="导出/另存为当前记忆库 (Excel)",
            filetypes=(("Excel files", "*.xlsx"), ("All files", "*.*")),
            defaultextension=".xlsx",
            initialfile=initial_tm_filename,
            parent=self.root
        )
        if not filepath: return
        self.save_tm_to_excel(filepath, backup=False)

    def clear_entire_translation_memory(self):
        if not self.translation_memory:
            messagebox.showinfo("清除记忆库", "翻译记忆库已经为空。", parent=self.root)
            return

        if messagebox.askyesno("确认清除",
                               "确定要清除内存中所有的翻译记忆库条目吗？\n"
                               "此操作无法撤销，但不会立即修改磁盘上的TM文件（除非之后保存）。", parent=self.root):
            self.translation_memory.clear()
            self.update_statusbar("整个翻译记忆库已在内存中清空。")

            if self.current_selected_ts_id:
                ts_obj = self._find_ts_obj_by_id(self.current_selected_ts_id)
                if ts_obj:
                    self.update_tm_suggestions_for_text(ts_obj.original_semantic)
                if hasattr(self, 'clear_selected_tm_btn'):
                    self.clear_selected_tm_btn.config(state=tk.DISABLED)

    def update_tm_for_selected_string(self):
        if not self.current_selected_ts_id:
            messagebox.showinfo("提示", "请先选择一个字符串。", parent=self.root)
            return

        ts_obj = self._find_ts_obj_by_id(self.current_selected_ts_id)
        if not ts_obj:
            messagebox.showerror("错误", "未找到选中的项目数据。", parent=self.root)
            return
        current_translation_ui = self.translation_edit_text.get("1.0", tk.END).rstrip('\n')

        if not current_translation_ui.strip():
            if messagebox.askyesno("确认更新记忆库",
                                   f"当前译文为空。是否要用空译文更新/覆盖记忆库中对于:\n'{ts_obj.original_semantic[:100].replace(chr(10), '↵')}...' \n的条目？\n(这通常意味着将来此原文会自动翻译为空)",
                                   parent=self.root, icon='warning'):
                translation_for_tm_storage = ""
            else:
                self.update_statusbar("更新记忆库已取消。")
                return
        else:
            translation_for_tm_storage = current_translation_ui.replace("\n", "\\n")

        self.translation_memory[ts_obj.original_semantic] = translation_for_tm_storage
        self.update_statusbar(f"记忆库已为原文 '{ts_obj.original_semantic[:30].replace(chr(10), '↵')}...' 更新。")
        self.update_tm_suggestions_for_text(ts_obj.original_semantic)
        if hasattr(self, 'clear_selected_tm_btn'): self.clear_selected_tm_btn.config(
            state=tk.NORMAL)
        if hasattr(self, 'update_selected_tm_btn'): self.update_selected_tm_btn.config(state=tk.NORMAL)

        if self.auto_save_tm_var.get() and self.current_tm_file:
            self.save_tm_to_excel(self.current_tm_file, silent=True)
        elif self.auto_save_tm_var.get():
            self.save_tm_to_excel(self._get_default_tm_excel_path(), silent=True)
        self.mark_project_modified()

    def clear_tm_for_selected_string(self):
        if not self.current_selected_ts_id:
            messagebox.showinfo("提示", "请先选择一个字符串。", parent=self.root)
            return
        ts_obj = self._find_ts_obj_by_id(self.current_selected_ts_id)
        if not ts_obj: return

        if ts_obj.original_semantic in self.translation_memory:
            if messagebox.askyesno("确认清除",
                                   f"确定要从记忆库中移除原文为:\n'{ts_obj.original_semantic[:100].replace(chr(10), '↵')}...' \n的条目吗?",
                                   parent=self.root):
                del self.translation_memory[ts_obj.original_semantic]
                self.update_statusbar(f"已为选中项清除记忆库条目。")
                self.update_tm_suggestions_for_text(ts_obj.original_semantic)
                if hasattr(self, 'clear_selected_tm_btn'): self.clear_selected_tm_btn.config(
                    state=tk.DISABLED)
                self.mark_project_modified()
        else:
            messagebox.showinfo("提示", "当前选中项在翻译记忆库中没有条目。", parent=self.root)

    def update_tm_suggestions_for_text(self, original_semantic_text):
        self.tm_suggestions_listbox.delete(0, tk.END)
        if not original_semantic_text: return

        if original_semantic_text in self.translation_memory:
            suggestion_from_tm = self.translation_memory[original_semantic_text]
            suggestion_for_ui = suggestion_from_tm.replace("\\n", "\n")
            self.tm_suggestions_listbox.insert(tk.END, f"(100% 精确匹配): {suggestion_for_ui}")
            self.tm_suggestions_listbox.itemconfig(tk.END, {'fg': 'darkgreen'})

        original_lower = original_semantic_text.lower()
        for tm_orig, tm_trans_with_slash_n in self.translation_memory.items():
            if tm_orig.lower() == original_lower and tm_orig != original_semantic_text:
                suggestion_for_ui = tm_trans_with_slash_n.replace("\\n", "\n")
                self.tm_suggestions_listbox.insert(tk.END, f"(大小写不符): {suggestion_for_ui}")
                self.tm_suggestions_listbox.itemconfig(tk.END, {'fg': 'orange red'})
                break

        fuzzy_matches = []
        for tm_orig, tm_trans_with_slash_n in self.translation_memory.items():
            if tm_orig == original_semantic_text or tm_orig.lower() == original_lower:
                continue

            ratio = SequenceMatcher(None, original_semantic_text, tm_orig).ratio()

            if ratio > 0.65:
                fuzzy_matches.append((ratio, tm_orig, tm_trans_with_slash_n))

        fuzzy_matches.sort(key=lambda x: x[0], reverse=True)

        for ratio, orig_match_text, trans_match_text in fuzzy_matches[:3]:
            suggestion_for_ui = trans_match_text.replace("\\n", "\n")
            display_orig_match = orig_match_text[:40].replace("\n", "↵") + ("..." if len(orig_match_text) > 40 else "")
            self.tm_suggestions_listbox.insert(tk.END,
                                               f"({ratio * 100:.0f}% ~ {display_orig_match}): {suggestion_for_ui}")
            self.tm_suggestions_listbox.itemconfig(tk.END, {'fg': 'purple'})

    def apply_tm_suggestion_from_listbox(self, event):
        selected_indices = self.tm_suggestions_listbox.curselection()
        if not selected_indices: return

        selected_suggestion_full_ui = self.tm_suggestions_listbox.get(selected_indices[0])
        try:
            translation_text_ui = selected_suggestion_full_ui.split("): ", 1)[1].strip()
        except IndexError:
            translation_text_ui = selected_suggestion_full_ui.strip()

        self.translation_edit_text.delete('1.0', tk.END)
        self.translation_edit_text.insert('1.0', translation_text_ui)

        if self.current_selected_ts_id:
            ts_obj = self._find_ts_obj_by_id(self.current_selected_ts_id)
            if ts_obj:
                self._apply_translation_to_model(ts_obj, translation_text_ui, source="tm_suggestion")

        self.update_statusbar("已应用翻译记忆库建议。")

    def apply_tm_to_all_current_strings(self, silent=False, only_if_empty=False, confirm=False):
        if not self.translatable_objects:
            if not silent: messagebox.showinfo("信息", "没有字符串可应用记忆库。", parent=self.root)
            return 0
        if not self.translation_memory:
            if not silent: messagebox.showinfo("信息", "翻译记忆库为空。", parent=self.root)
            return 0

        if confirm and not only_if_empty:
            if not messagebox.askyesno("确认操作", "这将使用记忆库中的翻译覆盖所有匹配的现有翻译。\n确定要继续吗？",
                                       parent=self.root):
                return 0

        applied_count = 0
        bulk_changes_for_undo = []
        for ts_obj in self.translatable_objects:
            if ts_obj.is_ignored: continue

            if only_if_empty and ts_obj.translation.strip() != "":
                continue

            if ts_obj.original_semantic in self.translation_memory:
                translation_from_tm_storage = self.translation_memory[ts_obj.original_semantic]
                translation_for_model_ui = translation_from_tm_storage.replace("\\n", "\n")

                if ts_obj.translation != translation_for_model_ui:
                    old_translation_for_undo = ts_obj.get_translation_for_storage_and_tm()
                    ts_obj.set_translation_internal(translation_for_model_ui)

                    bulk_changes_for_undo.append({
                        'string_id': ts_obj.id, 'field': 'translation',
                        'old_value': old_translation_for_undo,
                        'new_value': translation_from_tm_storage
                    })
                    applied_count += 1

        if applied_count > 0:
            if bulk_changes_for_undo:
                self.add_to_undo_history('bulk_change', {'changes': bulk_changes_for_undo})
                self.mark_project_modified()

            self.refresh_treeview(preserve_selection=True)
            if self.current_selected_ts_id: self.on_tree_select(None)

            if not silent:
                messagebox.showinfo("翻译记忆库", f"已向 {applied_count} 个字符串应用记忆库翻译。", parent=self.root)
            self.update_statusbar(f"已向 {applied_count} 个字符串应用记忆库翻译。")
        elif not silent:
            messagebox.showinfo("翻译记忆库", "没有可自动应用的翻译 (或无需更改)。", parent=self.root)

        return applied_count

    def show_advanced_search_dialog(self, event=None):
        if not self.translatable_objects:
            messagebox.showinfo("提示", "请先加载文件或项目。", parent=self.root)
            return
        AdvancedSearchDialog(self.root, "查找与替换", self)

    def copy_selected_original_text_menu(self, event=None):
        self.cm_copy_original()
        return "break"

    def paste_clipboard_to_selected_translation_menu(self, event=None):
        self.cm_paste_to_translation()
        return "break"

    def show_project_custom_instructions_dialog(self):
        if not self.current_project_file_path:
            messagebox.showerror("错误", "此功能仅在打开项目文件后可用。", parent=self.root)
            return

        new_instructions = simpledialog.askstring("项目个性化翻译设置",
                                                  "输入此项目的特定翻译指令 (例如：'将“英雄”翻译为“干员”'，'风格要活泼可爱')。\n这些指令将在AI翻译时使用。",
                                                  initialvalue=self.project_custom_instructions,
                                                  parent=self.root)

        if new_instructions is not None and new_instructions != self.project_custom_instructions:
            self.project_custom_instructions = new_instructions
            self.mark_project_modified()
            self.update_statusbar("项目个性化翻译设置已更新。")

    def show_ai_settings_dialog(self):
        if not requests:
            messagebox.showerror("功能不可用", "requests库未安装，AI翻译功能无法使用。\n请运行: pip install requests",
                                 parent=self.root)
            return
        AISettingsDialog(self.root, "AI翻译设置", self.config, self.save_config, self.ai_translator)

    def _check_ai_prerequisites(self, show_error=True):
        if not requests:
            if show_error:
                messagebox.showerror("AI功能不可用",
                                     "Python 'requests' 库未找到。请安装它 (pip install requests) 以使用AI翻译功能。",
                                     parent=self.root)
            return False
        if not self.config.get("ai_api_key"):
            if show_error:
                messagebox.showerror("API Key缺失", "API Key 未设置。请前往“工具 > AI翻译设置”进行配置。",
                                     parent=self.root)
            return False
        return True

    def apply_and_select_next_untranslated(self, event=None):
        if not self.current_selected_ts_id:
            return

        self.apply_translation_from_button()

        try:
            current_idx = self.displayed_string_ids.index(self.current_selected_ts_id)
        except (ValueError, IndexError):
            return

        next_untranslated_id = None

        for i in range(current_idx + 1, len(self.displayed_string_ids)):
            next_id = self.displayed_string_ids[i]
            ts_obj = self._find_ts_obj_by_id(next_id)
            if ts_obj and not ts_obj.translation.strip() and not ts_obj.is_ignored:
                next_untranslated_id = next_id
                break

        if not next_untranslated_id:
            for i in range(0, current_idx):
                next_id = self.displayed_string_ids[i]
                ts_obj = self._find_ts_obj_by_id(next_id)
                if ts_obj and not ts_obj.translation.strip() and not ts_obj.is_ignored:
                    next_untranslated_id = next_id
                    break

        if next_untranslated_id:
            self.tree.selection_set(next_untranslated_id)
            self.tree.focus(next_untranslated_id)
            self.tree.see(next_untranslated_id)
            self.on_tree_select(None)
            self.translation_edit_text.focus_set()
        else:
            self.update_statusbar("没有更多未翻译项。")

    def _generate_ai_context_strings(self, current_ts_id_to_exclude):
        contexts = {
            "translation_context": "",
            "original_context": ""
        }

        try:
            current_item_index = \
                [i for i, ts in enumerate(self.translatable_objects) if ts.id == current_ts_id_to_exclude][0]
        except IndexError:
            return contexts

        if self.config.get("ai_use_translation_context", False):
            trans_context_items = []
            max_neighbors = self.config.get("ai_context_neighbors", 0)
            preceding_context = []
            count = 0
            for i in range(current_item_index - 1, -1, -1):
                if max_neighbors > 0 and count >= max_neighbors: break
                ts = self.translatable_objects[i]
                if ts.translation.strip() and not ts.is_ignored:
                    orig_for_ctx = ts.original_semantic.replace("|", " ").replace("\n", " ")[:100]
                    trans_for_ctx = ts.get_translation_for_storage_and_tm().replace("|", " ").replace("\\n", " ")[:100]
                    preceding_context.append(f"{orig_for_ctx} -> {trans_for_ctx}")
                    count += 1
            succeeding_context = []
            count = 0
            for i in range(current_item_index + 1, len(self.translatable_objects)):
                if max_neighbors > 0 and count >= max_neighbors: break
                ts = self.translatable_objects[i]
                if ts.translation.strip() and not ts.is_ignored:
                    orig_for_ctx = ts.original_semantic.replace("|", " ").replace("\n", " ")[:100]
                    trans_for_ctx = ts.get_translation_for_storage_and_tm().replace("|", " ").replace("\\n", " ")[:100]
                    succeeding_context.append(f"{orig_for_ctx} -> {trans_for_ctx}")
                    count += 1
            trans_context_items = list(reversed(preceding_context)) + succeeding_context
            contexts["translation_context"] = " ||| ".join(trans_context_items)

        if self.config.get("ai_use_original_context", True):
            orig_context_items = []
            max_neighbors = self.config.get("ai_original_context_neighbors", 3)
            start_idx = max(0, current_item_index - max_neighbors)
            end_idx = min(len(self.translatable_objects), current_item_index + max_neighbors + 1)

            for i in range(start_idx, end_idx):
                if i == current_item_index: continue
                ts = self.translatable_objects[i]
                if not ts.is_ignored:
                    orig_context_items.append(ts.original_semantic.replace("|", " ").replace("\n", " "))
            contexts["original_context"] = " ||| ".join(orig_context_items)

        return contexts

    def _perform_ai_translation_threaded(self, ts_id, original_text, target_language, prompt_template, context_dict,
                                         custom_instructions, is_batch_item):
        try:
            translated_text = self.ai_translator.translate(
                original_text,
                target_language,
                prompt_template,
                translation_context=context_dict.get("translation_context", ""),
                custom_instructions=custom_instructions,
                original_context=context_dict.get("original_context", "")
            )
            self.root.after(0, self._handle_ai_translation_result, ts_id, translated_text, None, is_batch_item)
        except Exception as e:
            self.root.after(0, self._handle_ai_translation_result, ts_id, None, e, is_batch_item)
        finally:
            if is_batch_item and self.ai_batch_semaphore is not None:
                self.ai_batch_semaphore.release()
                self.root.after(0, self._decrement_active_threads_and_dispatch_more)

    def _initiate_single_ai_translation(self, ts_id_to_translate):
        # ... (This method needs to be updated to call the new context generation function) ...
        if not self._check_ai_prerequisites(): return
        if not ts_id_to_translate:
            return
        if self.is_ai_translating_batch:
            messagebox.showwarning("AI翻译进行中", "AI批量翻译正在进行中。请等待其完成或停止。", parent=self.root)
            return

        ts_obj = self._find_ts_obj_by_id(ts_id_to_translate)
        if not ts_obj: return

        if ts_obj.is_ignored:
            messagebox.showinfo("已忽略", "选中的字符串已被标记为忽略，不会进行AI翻译。", parent=self.root)
            return

        if ts_obj.translation.strip() and \
                not messagebox.askyesno("覆盖确认", "此字符串已有翻译。是否使用AI翻译覆盖现有译文？", parent=self.root):
            return

        self.update_statusbar(f"AI正在翻译选中项: \"{ts_obj.original_semantic[:30].replace(chr(10), '↵')}...\"")
        context_dict = self._generate_ai_context_strings(ts_obj.id)
        prompt_template = self.config.get("ai_prompt_template", DEFAULT_AI_PROMPT_TEMPLATE)
        target_language = self.config.get("ai_target_language", "中文")

        thread = threading.Thread(target=self._perform_ai_translation_threaded,
                                  args=(ts_obj.id, ts_obj.original_semantic, target_language,
                                        prompt_template, context_dict, self.project_custom_instructions, False),
                                  daemon=True)
        thread.start()

    def _dispatch_next_ai_batch_item(self):

        if not self.is_ai_translating_batch: return
        if self.ai_batch_next_item_index >= self.ai_batch_total_items: return

        if self.ai_batch_semaphore.acquire(blocking=False):
            if not self.is_ai_translating_batch:
                self.ai_batch_semaphore.release()
                return

            if self.ai_batch_next_item_index >= self.ai_batch_total_items:
                self.ai_batch_semaphore.release()
                return

            current_item_idx = self.ai_batch_next_item_index
            self.ai_batch_next_item_index += 1
            self.ai_batch_active_threads += 1

            ts_id = self.ai_translation_batch_ids_queue[current_item_idx]
            ts_obj = self._find_ts_obj_by_id(ts_id)

            self.update_statusbar(
                f"AI批量: 处理中 {current_item_idx + 1}/{self.ai_batch_total_items} (并发: {self.ai_batch_active_threads})...",
                persistent=True)

            if ts_obj and not ts_obj.is_ignored and not ts_obj.translation.strip():
                context_dict = self._generate_ai_context_strings(ts_obj.id)
                prompt_template = self.config.get("ai_prompt_template", DEFAULT_AI_PROMPT_TEMPLATE)
                target_language = self.config.get("ai_target_language", "中文")

                thread = threading.Thread(target=self._perform_ai_translation_threaded,
                                          args=(ts_obj.id, ts_obj.original_semantic, target_language,
                                                prompt_template, context_dict, self.project_custom_instructions, True),
                                          daemon=True)
                thread.start()
            else:
                self.ai_batch_semaphore.release()
                self.ai_batch_active_threads -= 1
                self.ai_batch_completed_count += 1
                if self.is_ai_translating_batch:
                    if self.ai_batch_next_item_index < self.ai_batch_total_items:
                        self.root.after(0, self._dispatch_next_ai_batch_item)
                    elif self.ai_batch_active_threads == 0 and self.ai_batch_completed_count >= self.ai_batch_total_items:
                        self._finalize_batch_ai_translation()

    def cm_toggle_reviewed_status(self, event=None):
        if self.current_selected_ts_id:
            self.cm_set_reviewed_status(not self.reviewed_var.get())

    def cm_toggle_ignored_status(self, event=None):
        if self.current_selected_ts_id:
            self.cm_set_ignored_status(not self.ignore_var.get())

    def _decrement_active_threads_and_dispatch_more(self):
        if not self.is_ai_translating_batch:
            if self.ai_batch_active_threads > 0: self.ai_batch_active_threads -= 1
            if self.ai_batch_active_threads == 0:
                self._finalize_batch_ai_translation()
            return

        if self.ai_batch_active_threads > 0:
            self.ai_batch_active_threads -= 1

        if self.ai_batch_next_item_index < self.ai_batch_total_items:
            interval = self.config.get("ai_api_interval", 200)
            self.root.after(interval, self._dispatch_next_ai_batch_item)
        elif self.ai_batch_active_threads == 0 and self.ai_batch_completed_count >= self.ai_batch_total_items:
            self._finalize_batch_ai_translation()

    def _handle_ai_translation_result(self, ts_id, translated_text, error_object, is_batch_item):
        ts_obj = self._find_ts_obj_by_id(ts_id)

        if not ts_obj:
            if is_batch_item: self.ai_batch_completed_count += 1
            return

        if error_object:
            error_msg = f"AI翻译失败 for \"{ts_obj.original_semantic[:20].replace(chr(10), '↵')}...\": {error_object}"
            self.update_statusbar(error_msg)
            if not is_batch_item:
                messagebox.showerror("AI翻译错误",
                                     f"对 \"{ts_obj.original_semantic[:50]}...\" 的AI翻译失败:\n{error_object}",
                                     parent=self.root)
        elif translated_text is not None and translated_text.strip():
            apply_source = "ai_batch_item" if is_batch_item else "ai_selected"
            cleaned_translation = translated_text.strip()

            if is_batch_item:
                old_undo_val = ts_obj.get_translation_for_storage_and_tm()
                ts_obj.set_translation_internal(cleaned_translation)
                if cleaned_translation:
                    self.translation_memory[ts_obj.original_semantic] = ts_obj.get_translation_for_storage_and_tm()

                self.ai_batch_successful_translations_for_undo.append({
                    'string_id': ts_obj.id,
                    'field': 'translation',
                    'old_value': old_undo_val,
                    'new_value': ts_obj.get_translation_for_storage_and_tm()
                })
            else:
                self._apply_translation_to_model(ts_obj, cleaned_translation, source=apply_source)

            if self.tree.exists(ts_obj.id):
                current_values = list(self.tree.item(ts_obj.id, 'values'))
                current_values[1] = "T"
                current_values[3] = cleaned_translation.replace("\n", "↵")
                self.tree.item(ts_obj.id, values=tuple(current_values), tags=('translated_row_visual',))

            if self.current_selected_ts_id == ts_obj.id:
                self.translation_edit_text.delete("1.0", tk.END)
                self.translation_edit_text.insert("1.0", ts_obj.get_translation_for_ui())
                self.schedule_placeholder_validation()
                self.update_tm_suggestions_for_text(ts_obj.original_semantic)
                if hasattr(self, 'clear_selected_tm_btn'):
                    self.clear_selected_tm_btn.config(
                        state=tk.NORMAL if ts_obj.original_semantic in self.translation_memory else tk.DISABLED)

            if not is_batch_item:
                self.update_statusbar(f"AI翻译成功: \"{ts_obj.original_semantic[:20].replace(chr(10), '↵')}...\"")
        elif translated_text is not None and not translated_text.strip():
            self.update_statusbar(f"AI返回空翻译 for \"{ts_obj.original_semantic[:20].replace(chr(10), '↵')}...\"")

        if is_batch_item:
            self.ai_batch_completed_count += 1

            if self.ai_batch_total_items > 0:
                progress_percent = (self.ai_batch_completed_count / self.ai_batch_total_items) * 100
                if hasattr(self, 'progress_bar'): self.progress_bar['value'] = progress_percent
            else:
                progress_percent = 0

            self.update_statusbar(
                f"AI批量: {self.ai_batch_completed_count}/{self.ai_batch_total_items} 完成 ({progress_percent:.0f}%).",
                persistent=True)

            if self.ai_batch_completed_count >= self.ai_batch_total_items and self.ai_batch_active_threads == 0:
                self._finalize_batch_ai_translation()

        if not self.is_ai_translating_batch and not is_batch_item:
            self.update_ai_related_ui_state()

    def ai_translate_selected_from_menu(self, event=None):
        self.cm_ai_translate_selected()

    def ai_translate_selected_from_button(self):
        self._initiate_single_ai_translation(self.current_selected_ts_id)

    def _initiate_single_ai_translation(self, ts_id_to_translate):
        if not self._check_ai_prerequisites(): return
        if not ts_id_to_translate:
            return
        if self.is_ai_translating_batch:
            messagebox.showwarning("AI翻译进行中", "AI批量翻译正在进行中。请等待其完成或停止。", parent=self.root)
            return

        ts_obj = self._find_ts_obj_by_id(ts_id_to_translate)
        if not ts_obj: return

        if ts_obj.is_ignored:
            messagebox.showinfo("已忽略", "选中的字符串已被标记为忽略，不会进行AI翻译。", parent=self.root)
            return

        if ts_obj.translation.strip() and \
                not messagebox.askyesno("覆盖确认", "此字符串已有翻译。是否使用AI翻译覆盖现有译文？", parent=self.root):
            return

        self.update_statusbar(f"AI正在翻译选中项: \"{ts_obj.original_semantic[:30].replace(chr(10), '↵')}...\"")
        context_str = self._generate_ai_context_strings(ts_obj.id)
        prompt_template = self.config.get("ai_prompt_template", DEFAULT_AI_PROMPT_TEMPLATE)
        target_language = self.config.get("ai_target_language", "中文")

        thread = threading.Thread(target=self._perform_ai_translation_threaded,
                                  args=(ts_obj.id, ts_obj.original_semantic, target_language,
                                        prompt_template, context_str, self.project_custom_instructions, False),
                                  daemon=True)
        thread.start()

    def ai_translate_all_untranslated(self):
        if not self._check_ai_prerequisites(): return
        if self.is_ai_translating_batch:
            messagebox.showwarning("AI翻译进行中", "AI批量翻译已在进行中。", parent=self.root)
            return

        self.ai_translation_batch_ids_queue = [
            ts.id for ts in self.translatable_objects
            if not ts.is_ignored and not ts.translation.strip()
        ]

        if not self.ai_translation_batch_ids_queue:
            messagebox.showinfo("无需翻译", "没有找到未翻译且未忽略的字符串。", parent=self.root)
            return

        self.ai_batch_total_items = len(self.ai_translation_batch_ids_queue)
        api_interval_ms = self.config.get('ai_api_interval', 200)
        max_concurrency = self.config.get('ai_max_concurrent_requests', 1)

        avg_api_time_estimate_s = 3.0
        if max_concurrency == 1:
            estimated_time_s = self.ai_batch_total_items * (avg_api_time_estimate_s + api_interval_ms / 1000.0)
            concurrency_text = "顺序执行"
        else:
            estimated_time_s = (self.ai_batch_total_items / max_concurrency) * avg_api_time_estimate_s + \
                               (self.ai_batch_total_items / max_concurrency) * (
                                       api_interval_ms / 1000.0)
            concurrency_text = f"最多 {max_concurrency} 并发"

        if not messagebox.askyesno("确认批量翻译",
                                   f"将对 {self.ai_batch_total_items} 个未翻译字符串进行AI翻译 ({concurrency_text})。\n"
                                   f"API调用间隔 {api_interval_ms}ms (并发时为任务间最小间隔)。\n"
                                   f"预计耗时约 {estimated_time_s:.1f} 秒。\n"
                                   f"是否继续？", parent=self.root):
            self.ai_translation_batch_ids_queue = []
            return

        self.is_ai_translating_batch = True
        self.ai_batch_completed_count = 0
        self.ai_batch_successful_translations_for_undo = []
        self.ai_batch_next_item_index = 0
        self.ai_batch_active_threads = 0
        self.ai_batch_semaphore = threading.Semaphore(max_concurrency)

        if hasattr(self, 'progress_bar'): self.progress_bar['value'] = 0
        self.update_ai_related_ui_state()
        self.update_statusbar(f"AI批量翻译开始 ({concurrency_text})...", persistent=True)

        for _ in range(max_concurrency):
            if self.ai_batch_next_item_index < self.ai_batch_total_items:
                self._dispatch_next_ai_batch_item()
            else:
                break

    def _dispatch_next_ai_batch_item(self):
        if not self.is_ai_translating_batch: return
        if self.ai_batch_next_item_index >= self.ai_batch_total_items: return

        if self.ai_batch_semaphore.acquire(blocking=False):
            if not self.is_ai_translating_batch:
                self.ai_batch_semaphore.release()
                return

            if self.ai_batch_next_item_index >= self.ai_batch_total_items:
                self.ai_batch_semaphore.release()
                return

            current_item_idx = self.ai_batch_next_item_index
            self.ai_batch_next_item_index += 1
            self.ai_batch_active_threads += 1

            ts_id = self.ai_translation_batch_ids_queue[current_item_idx]
            ts_obj = self._find_ts_obj_by_id(ts_id)

            self.update_statusbar(
                f"AI批量: 处理中 {current_item_idx + 1}/{self.ai_batch_total_items} (并发: {self.ai_batch_active_threads})...",
                persistent=True)

            if ts_obj and not ts_obj.is_ignored and not ts_obj.translation.strip():
                context_str = self._generate_ai_context_string(ts_obj.id)
                prompt_template = self.config.get("ai_prompt_template", DEFAULT_AI_PROMPT_TEMPLATE)
                target_language = self.config.get("ai_target_language", "中文")

                thread = threading.Thread(target=self._perform_ai_translation_threaded,
                                          args=(ts_obj.id, ts_obj.original_semantic, target_language,
                                                prompt_template, context_str, self.project_custom_instructions, True),
                                          daemon=True)
                thread.start()
            else:
                self.ai_batch_semaphore.release()
                self.ai_batch_active_threads -= 1
                self.ai_batch_completed_count += 1
                if self.is_ai_translating_batch:
                    if self.ai_batch_next_item_index < self.ai_batch_total_items:
                        self.root.after(0, self._dispatch_next_ai_batch_item)
                    elif self.ai_batch_active_threads == 0 and self.ai_batch_completed_count >= self.ai_batch_total_items:
                        self._finalize_batch_ai_translation()

    def _finalize_batch_ai_translation(self):
        if not self.is_ai_translating_batch and self.ai_batch_active_threads > 0:
            return

        if self.ai_batch_successful_translations_for_undo:
            self.add_to_undo_history('bulk_ai_translate', {'changes': self.ai_batch_successful_translations_for_undo})
            self.mark_project_modified()
            self.check_batch_placeholder_mismatches()

        success_count = len(self.ai_batch_successful_translations_for_undo)
        processed_items = self.ai_batch_completed_count

        self.update_statusbar(
            f"AI批量翻译完成。成功翻译 {success_count}/{processed_items} 项 (共 {self.ai_batch_total_items} 项计划)。",
            persistent=True)

        self.is_ai_translating_batch = False
        self.ai_translation_batch_ids_queue = []
        self.ai_batch_successful_translations_for_undo = []
        self.ai_batch_semaphore = None
        self.ai_batch_active_threads = 0
        self.ai_batch_next_item_index = 0
        self.ai_batch_total_items = 0
        self.ai_batch_completed_count = 0

        self.update_ai_related_ui_state()
        self.refresh_treeview(preserve_selection=True)

    def check_batch_placeholder_mismatches(self):
        mismatched_items = []
        for change in self.ai_batch_successful_translations_for_undo:
            ts_obj = self._find_ts_obj_by_id(change['string_id'])
            if not ts_obj: continue

            original_placeholders = set(self.placeholder_regex.findall(ts_obj.original_semantic))
            translated_placeholders = set(self.placeholder_regex.findall(ts_obj.translation))

            if original_placeholders != translated_placeholders:
                mismatched_items.append(ts_obj)

        if mismatched_items:
            msg = f"AI批量翻译后，发现 {len(mismatched_items)} 项的占位符不匹配。\n是否为这些项批量添加注释“占位符不匹配”？"
            if messagebox.askyesno("占位符不匹配", msg, parent=self.root):
                bulk_comment_changes = []
                for ts_obj in mismatched_items:
                    old_comment = ts_obj.comment
                    new_comment = (old_comment + " 占位符不匹配").strip()
                    if ts_obj.comment != new_comment:
                        ts_obj.comment = new_comment
                        bulk_comment_changes.append({
                            'string_id': ts_obj.id, 'field': 'comment',
                            'old_value': old_comment, 'new_value': new_comment
                        })
                if bulk_comment_changes:
                    self.add_to_undo_history('bulk_context_menu', {'changes': bulk_comment_changes})
                    self.refresh_treeview_preserve_selection()
                    self.update_statusbar(f"为 {len(bulk_comment_changes)} 个占位符不匹配项添加了注释。")

    def stop_batch_ai_translation(self, silent=False):
        if not self.is_ai_translating_batch:
            if not silent:
                messagebox.showinfo("提示", "没有正在进行的AI批量翻译任务。", parent=self.root)
            return

        was_translating = self.is_ai_translating_batch
        self.is_ai_translating_batch = False

        if not silent:
            messagebox.showinfo("AI批量翻译", "AI批量翻译已请求停止。\n已派发的任务将继续完成，请稍候。", parent=self.root)

        self.update_statusbar("AI批量翻译正在停止...等待已派发任务完成。", persistent=True)

        if was_translating and self.ai_batch_active_threads == 0:
            self._finalize_batch_ai_translation()
        else:
            self.update_ai_related_ui_state()

    def _get_selected_ts_objects(self):
        selected_iids = self.tree.selection()
        if not selected_iids: return []
        return [self._find_ts_obj_by_id(iid) for iid in selected_iids if self._find_ts_obj_by_id(iid)]

    def cm_copy_original(self):
        selected_objs = self._get_selected_ts_objects()
        if not selected_objs: return
        text_to_copy = "\n".join([ts.original_semantic for ts in selected_objs])
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text_to_copy)
            self.update_statusbar(f"复制了 {len(selected_objs)} 项原文到剪贴板。")
        except tk.TclError:
            self.update_statusbar("复制失败。无法访问剪贴板。")

    def cm_copy_translation(self):
        selected_objs = self._get_selected_ts_objects()
        if not selected_objs: return
        text_to_copy = "\n".join([ts.get_translation_for_ui() for ts in selected_objs])
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text_to_copy)
            self.update_statusbar(f"复制了 {len(selected_objs)} 项译文到剪贴板。")
        except tk.TclError:
            self.update_statusbar("复制失败。无法访问剪贴板。")

    def cm_paste_to_translation(self):
        if not self.current_selected_ts_id:
            self.update_statusbar("请选中一个项目。")
            return

        ts_obj = self._find_ts_obj_by_id(self.current_selected_ts_id)
        if not ts_obj: return

        try:
            clipboard_content = self.root.clipboard_get()
        except tk.TclError:
            self.update_statusbar("从剪贴板粘贴失败。")
            return

        if isinstance(clipboard_content, str):
            self.translation_edit_text.delete('1.0', tk.END)
            self.translation_edit_text.insert('1.0', clipboard_content)
            cleaned_content = clipboard_content.rstrip('\n')
            self._apply_translation_to_model(ts_obj, cleaned_content, source="manual_paste")
            self.update_statusbar(f"剪贴板内容已粘贴到译文。")
        else:
            self.update_statusbar("粘贴失败：剪贴板内容非文本。")

    def cm_set_ignored_status(self, ignore_flag):
        selected_objs = self._get_selected_ts_objects()
        if not selected_objs: return

        bulk_changes = []
        for ts_obj in selected_objs:
            if ts_obj.is_ignored != ignore_flag:
                old_val = ts_obj.is_ignored
                ts_obj.is_ignored = ignore_flag
                if not ignore_flag: ts_obj.was_auto_ignored = False
                bulk_changes.append(
                    {'string_id': ts_obj.id, 'field': 'is_ignored', 'old_value': old_val, 'new_value': ignore_flag})

        if bulk_changes:
            self.add_to_undo_history('bulk_context_menu', {'changes': bulk_changes})
            self.refresh_treeview_and_select_neighbor(selected_objs[0].id)
            self.update_statusbar(f"{len(bulk_changes)} 项忽略状态已更新。")
            self.mark_project_modified()

    def cm_set_reviewed_status(self, reviewed_flag):
        selected_objs = self._get_selected_ts_objects()
        if not selected_objs: return

        bulk_changes = []
        for ts_obj in selected_objs:
            if ts_obj.is_reviewed != reviewed_flag:
                old_val = ts_obj.is_reviewed
                ts_obj.is_reviewed = reviewed_flag
                bulk_changes.append(
                    {'string_id': ts_obj.id, 'field': 'is_reviewed', 'old_value': old_val, 'new_value': reviewed_flag})

        if bulk_changes:
            self.add_to_undo_history('bulk_context_menu', {'changes': bulk_changes})
            self.refresh_treeview_and_select_neighbor(selected_objs[0].id)
            self.update_statusbar(f"{len(bulk_changes)} 项审阅状态已更新。")
            self.mark_project_modified()

    def cm_edit_comment(self):
        selected_objs = self._get_selected_ts_objects()
        if not selected_objs: return

        initial_comment = selected_objs[0].comment if len(selected_objs) == 1 else ""
        prompt_text = f"为选中的 {len(selected_objs)} 项输入注释:" if len(
            selected_objs) > 1 else f"原文:\n{selected_objs[0].original_semantic[:100]}...\n\n输入注释:"

        new_comment = simpledialog.askstring("编辑注释", prompt_text,
                                             initialvalue=initial_comment, parent=self.root)

        if new_comment is not None:
            bulk_changes = []
            for ts_obj in selected_objs:
                if ts_obj.comment != new_comment:
                    old_comment = ts_obj.comment
                    ts_obj.comment = new_comment
                    bulk_changes.append({
                        'string_id': ts_obj.id, 'field': 'comment',
                        'old_value': old_comment, 'new_value': new_comment
                    })

            if bulk_changes:
                self.add_to_undo_history('bulk_context_menu', {'changes': bulk_changes})
                self.refresh_treeview_preserve_selection()
                if self.current_selected_ts_id in [c['string_id'] for c in bulk_changes]:
                    self.comment_edit_text.delete("1.0", tk.END)
                    self.comment_edit_text.insert("1.0", new_comment)
                self.update_statusbar(f"为 {len(bulk_changes)} 项更新了注释。")
                self.mark_project_modified()

    def cm_apply_tm_to_selected(self):
        selected_objs = self._get_selected_ts_objects()
        if not selected_objs: return
        if not self.translation_memory:
            messagebox.showinfo("提示", "翻译记忆库为空。", parent=self.root)
            return

        applied_count = 0
        bulk_changes = []
        for ts_obj in selected_objs:
            if ts_obj.is_ignored: continue
            if ts_obj.original_semantic in self.translation_memory:
                tm_translation_storage = self.translation_memory[ts_obj.original_semantic]
                tm_translation_ui = tm_translation_storage.replace("\\n", "\n")
                if ts_obj.translation != tm_translation_ui:
                    old_val = ts_obj.get_translation_for_storage_and_tm()
                    ts_obj.set_translation_internal(tm_translation_ui)
                    bulk_changes.append({'string_id': ts_obj.id, 'field': 'translation', 'old_value': old_val,
                                         'new_value': tm_translation_storage})
                    applied_count += 1

        if bulk_changes:
            self.add_to_undo_history('bulk_context_menu', {'changes': bulk_changes})
            self.refresh_treeview_preserve_selection()
            self.on_tree_select(None)
            self.update_statusbar(f"向 {applied_count} 个选中项应用了记忆库翻译。")
            self.mark_project_modified()
        elif selected_objs:
            messagebox.showinfo("提示", "选中项无匹配记忆或无需更新。", parent=self.root)

    def cm_clear_selected_translations(self):
        selected_objs = self._get_selected_ts_objects()
        if not selected_objs: return

        if not messagebox.askyesno("确认清除", f"确定要清除选中的 {len(selected_objs)} 项的译文吗？", parent=self.root):
            return

        bulk_changes = []
        for ts_obj in selected_objs:
            if ts_obj.translation.strip() != "":
                old_val = ts_obj.get_translation_for_storage_and_tm()
                ts_obj.set_translation_internal("")
                bulk_changes.append(
                    {'string_id': ts_obj.id, 'field': 'translation', 'old_value': old_val, 'new_value': ""})

        if bulk_changes:
            self.add_to_undo_history('bulk_context_menu', {'changes': bulk_changes})
            self.refresh_treeview_preserve_selection()
            self.on_tree_select(None)
            self.update_statusbar(f"清除了 {len(bulk_changes)} 项译文。")
            self.mark_project_modified()

    def cm_ai_translate_selected(self):
        selected_objs = self._get_selected_ts_objects()
        if not selected_objs: return
        if not self._check_ai_prerequisites(): return
        if self.is_ai_translating_batch:
            messagebox.showwarning("AI翻译进行中", "AI批量翻译正在进行中。", parent=self.root)
            return

        items_to_translate = []
        for ts_obj in selected_objs:
            if ts_obj.is_ignored: continue
            if ts_obj.translation.strip():
                if len(selected_objs) > 1:
                    continue
                if not messagebox.askyesno("覆盖确认",
                                           f"字符串 \"{ts_obj.original_semantic[:30]}...\" 已有翻译。\n是否使用AI翻译覆盖？",
                                           parent=self.root):
                    continue
            items_to_translate.append(ts_obj)

        if not items_to_translate:
            messagebox.showinfo("AI翻译", "没有符合条件的选中项可供AI翻译。", parent=self.root)
            return

        count = 0
        for ts_obj in items_to_translate:
            self._initiate_single_ai_translation(ts_obj.id)
            count += 1
            if count < len(items_to_translate):
                time.sleep(max(0.1, self.config.get("ai_api_interval", 200) / 1000.0))

        if count > 0:
            self.update_statusbar(f"已为 {count} 个选中项启动AI翻译。")

        # In app.py


    def compare_with_new_version(self, event=None):
            if not self.current_code_file_path or not self.translatable_objects:
                messagebox.showerror("错误", "请先打开一个已保存的项目或代码文件。", parent=self.root)
                return

            filepath = filedialog.askopenfilename(
                title="选择新版本的代码文件进行对比",
                filetypes=(("Overwatch Workshop Files", "*.ow;*.txt"), ("All Files", "*.*")),
                initialdir=os.path.dirname(self.current_code_file_path),
                parent=self.root
            )
            if not filepath:
                return

            try:
                with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                    new_code_content = f.read()

                # --- Progress Bar Setup ---
                self.progress_bar.pack(side=tk.RIGHT, padx=5, pady=2, before=self.counts_label_widget)
                self.progress_bar['value'] = 0
                self.update_statusbar("正在解析新文件...", persistent=True)
                self.root.update_idletasks()

                new_strings = extract_translatable_strings(new_code_content)
                old_strings = self.translatable_objects

                old_map = {s.original_semantic: s for s in old_strings}
                new_map = {s.original_semantic: s for s in new_strings}

                diff_results = {
                    'added': [],
                    'removed': [],
                    'modified': [],
                    'unchanged': []
                }

                total_steps = len(old_map) + len(new_map)
                current_step = 0

                # --- Step 1: Find unchanged strings ---
                self.update_statusbar("步骤 1/3: 正在匹配完全相同的字符串...", persistent=True)
                for old_semantic, old_obj in old_map.items():
                    current_step += 1
                    if old_semantic in new_map:
                        new_obj = new_map[old_semantic]
                        new_obj.translation = old_obj.translation
                        new_obj.comment = old_obj.comment
                        new_obj.is_ignored = old_obj.is_ignored
                        new_obj.is_reviewed = old_obj.is_reviewed
                        diff_results['unchanged'].append({'old_obj': old_obj, 'new_obj': new_obj})
                    self.progress_bar['value'] = (current_step / total_steps) * 100
                    if current_step % 20 == 0: self.root.update_idletasks()

                # --- Step 2: Find modified strings with high similarity ---
                self.update_statusbar("步骤 2/3: 正在匹配高度相似的字符串...", persistent=True)
                unmatched_old = [s for s in old_strings if s.original_semantic not in new_map]
                unmatched_new = [s for s in new_strings if s.original_semantic not in old_map]
                new_pool = unmatched_new[:]

                for i, old_obj in enumerate(unmatched_old):
                    current_step += 1
                    best_match = None
                    highest_similarity = 0.0

                    for new_obj in new_pool:
                        similarity = SequenceMatcher(None, old_obj.original_semantic, new_obj.original_semantic).ratio()
                        if similarity > highest_similarity:
                            highest_similarity = similarity
                            best_match = new_obj

                    if highest_similarity >= 0.95 and best_match:
                        best_match.translation = old_obj.translation
                        best_match.comment = f"[继承自旧版] {old_obj.comment}".strip()
                        best_match.is_ignored = old_obj.is_ignored
                        best_match.is_reviewed = False

                        diff_results['modified'].append({
                            'old_obj': old_obj,
                            'new_obj': best_match,
                            'similarity': highest_similarity
                        })
                        new_pool.remove(best_match)
                    else:
                        diff_results['removed'].append({'old_obj': old_obj})

                    self.progress_bar['value'] = (current_step / total_steps) * 100
                    if i % 10 == 0: self.root.update_idletasks()

                # --- Step 3: Identify added strings ---
                self.update_statusbar("步骤 3/3: 正在识别新增和移除的字符串...", persistent=True)
                for new_obj in new_pool:
                    current_step += 1
                    diff_results['added'].append({'new_obj': new_obj})
                    self.progress_bar['value'] = (current_step / total_steps) * 100

                self.progress_bar['value'] = 100
                self.update_statusbar("对比完成，正在生成报告...", persistent=True)

                # --- Generate Summary and Show Dialog ---
                summary = (
                    f"对比完成。发现 "
                    f"{len(diff_results['added'])} 个新增项, "
                    f"{len(diff_results['removed'])} 个移除项, "
                    f"以及 {len(diff_results['modified'])} 个修改/继承项。"
                )
                diff_results['summary'] = summary

                from dialogs.diff_dialog import DiffDialog
                dialog = DiffDialog(self.root, "版本对比结果", diff_results)

                # --- Cleanup and Update Project ---
                self.progress_bar.pack_forget()  # Hide progress bar after dialog closes

                if dialog.result:
                    self.update_statusbar("正在应用更新...", persistent=True)

                    self.translatable_objects = new_strings
                    self.original_raw_code_content = new_code_content
                    self.current_code_file_path = filepath

                    self.apply_tm_to_all_current_strings(silent=True, only_if_empty=True)

                    self.mark_project_modified()
                    self.refresh_treeview()
                    self.update_statusbar(f"项目已更新至新版本: {os.path.basename(filepath)}", persistent=True)
                else:
                    self.update_statusbar("版本更新已取消。")

            except Exception as e:
                self.progress_bar.pack_forget()
                messagebox.showerror("对比失败", f"处理文件或对比时发生错误: {e}", parent=self.root)
                self.update_statusbar("版本对比失败。")