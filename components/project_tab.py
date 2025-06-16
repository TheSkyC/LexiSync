import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog, scrolledtext
import re
import os
from copy import deepcopy
import time
import threading
from difflib import SequenceMatcher

from components.virtual_treeview import VirtualTreeview
from models.translatable_string import TranslatableString
from services.code_file_service import CodeFileService
from services.project_service import ProjectService
from utils import constants


class ProjectTab(ttk.Frame):
    def __init__(self, master, app_instance, file_path=None, is_project_file=False, **kwargs):
        super().__init__(master, **kwargs)
        self.app = app_instance
        self.loc = self.app.loc
        self.termbase = self.app.termbase_service

        self.current_code_file_path = None
        self.current_project_file_path = None
        self.original_raw_code_content = ""
        self.is_modified = False
        self.project_custom_instructions = ""

        self.translatable_objects = []
        self.displayed_string_ids = []

        self.undo_history = []
        self.redo_history = []
        self.current_selected_ts_id = None

        self.deduplicate_strings_var = tk.BooleanVar(value=False)
        self.show_ignored_var = tk.BooleanVar(value=True)
        self.show_untranslated_var = tk.BooleanVar(value=False)
        self.show_translated_var = tk.BooleanVar(value=False)
        self.show_unreviewed_var = tk.BooleanVar(value=False)
        self.search_var = tk.StringVar()

        self._ignored_tag_font = None
        self.placeholder_regex = re.compile(r'\{(\d+)\}')
        self._placeholder_validation_job = None
        self._term_tooltip = None
        self.is_docked = True
        self.docked_window = None

        self._setup_main_layout()
        self._setup_treeview_context_menu()
        self._configure_treeview_tags()

        if file_path:
            if is_project_file:
                self.open_project_file(file_path)
            else:
                self.open_code_file_path(file_path)

    def _setup_main_layout(self):
        self.paned_window = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.paned_window.pack(expand=True, fill=tk.BOTH, pady=(5, 0))

        self.left_pane = ttk.Frame(self.paned_window)
        self.paned_window.add(self.left_pane, weight=7)

        self._setup_filter_toolbar(self.left_pane)
        self._setup_treeview_panel(self.left_pane)

        self.right_pane_container = ttk.Frame(self.paned_window)
        self.paned_window.add(self.right_pane_container, weight=3)
        self._setup_details_pane(self.right_pane_container)

    def _setup_filter_toolbar(self, parent):
        toolbar = ttk.Frame(parent, padding=5)
        toolbar.pack(side=tk.TOP, fill=tk.X, pady=(0, 5))

        ttk.Label(toolbar, text=f"{self.loc('view_menu')}:").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Checkbutton(toolbar, text=self.loc('deduplicate'), variable=self.deduplicate_strings_var,
                        command=self.refresh_treeview).pack(side=tk.LEFT, padx=3)
        ttk.Checkbutton(toolbar, text=self.loc('show_ignored'), variable=self.show_ignored_var,
                        command=self.refresh_treeview).pack(side=tk.LEFT, padx=3)
        ttk.Checkbutton(toolbar, text=self.loc('show_untranslated'), variable=self.show_untranslated_var,
                        command=self.refresh_treeview).pack(side=tk.LEFT, padx=3)
        ttk.Checkbutton(toolbar, text=self.loc('show_translated'), variable=self.show_translated_var,
                        command=self.refresh_treeview).pack(side=tk.LEFT, padx=3)
        ttk.Checkbutton(toolbar, text=self.loc('show_unreviewed'), variable=self.show_unreviewed_var,
                        command=self.refresh_treeview).pack(side=tk.LEFT, padx=3)

        search_frame = ttk.Frame(toolbar)
        search_frame.pack(side=tk.RIGHT, padx=5)
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=25)
        self.search_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.search_entry.bind("<Return>", lambda e: self.find_string_from_toolbar())
        self.search_entry.bind("<FocusIn>", self._on_search_focus_in)
        self.search_entry.bind("<FocusOut>", self._on_search_focus_out)
        self._on_search_focus_out(None)

        ttk.Button(search_frame, text=self.loc('find_replace').split('/')[0].strip(),
                   command=self.find_string_from_toolbar).pack(side=tk.LEFT)

    def _on_search_focus_in(self, event):
        if self.search_var.get() == self.loc('quick_search_placeholder'):
            self.search_entry.delete(0, tk.END)
            self.search_entry.config(foreground="black")

    def _on_search_focus_out(self, event):
        if not self.search_var.get():
            self.search_entry.insert(0, self.loc('quick_search_placeholder'))
            self.search_entry.config(foreground="grey")

    def _setup_treeview_panel(self, parent):
        tree_frame = ttk.Frame(parent)
        tree_frame.pack(expand=True, fill=tk.BOTH)
        cols = ("seq_id", "status", "original", "translation", "comment", "reviewed", "line")
        self.tree = VirtualTreeview(tree_frame, columns=cols, show="headings", selectmode="extended",
                                    right_click_callback=self.show_treeview_context_menu)

        col_widths = {"seq_id": 40, "status": 30, "original": 300, "translation": 300, "comment": 150, "reviewed": 30,
                      "line": 50}
        col_align = {"seq_id": tk.E, "status": tk.CENTER, "original": tk.W, "translation": tk.W, "comment": tk.W,
                     "reviewed": tk.CENTER, "line": tk.CENTER}
        col_headings = {
            "seq_id": self.loc('col_seq_id'), "status": self.loc('col_status'), "original": self.loc('col_original'),
            "translation": self.loc('col_translation'), "comment": self.loc('col_comment'),
            "reviewed": self.loc('col_reviewed'), "line": self.loc('col_line')
        }

        for col_key in cols:
            self.tree.heading(col_key, text=col_headings.get(col_key, col_key.capitalize()),
                              command=lambda c=col_key: self._sort_treeview_column(c, False))
            self.tree.column(col_key, width=col_widths.get(col_key, 100), anchor=col_align.get(col_key, tk.W),
                             stretch=(col_key not in ["seq_id", "status", "reviewed", "line"]))

        self.tree.pack(expand=True, fill=tk.BOTH)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

    def _setup_details_pane(self, parent_frame):
        self.details_pane = ttk.LabelFrame(parent_frame, text=self.loc('details_panel_title'), padding="5")
        self.details_pane.pack(expand=True, fill=tk.BOTH, padx=0, pady=0)

        self.dock_button = ttk.Button(self.details_pane, text=self.loc('dock_panel'), command=self.toggle_dock)
        self.dock_button.pack(anchor='ne', padx=5, pady=2)

        details_paned_window = ttk.PanedWindow(self.details_pane, orient=tk.VERTICAL)
        details_paned_window.pack(fill=tk.BOTH, expand=True)

        top_section_frame = ttk.Frame(details_paned_window, padding=5)
        details_paned_window.add(top_section_frame, weight=4)
        top_section_frame.columnconfigure(0, weight=1)

        ttk.Label(top_section_frame, text=self.loc('original_text_label')).pack(anchor=tk.W, padx=5, pady=(0, 2))
        self.original_text_display = scrolledtext.ScrolledText(top_section_frame, height=3, wrap=tk.WORD,
                                                               state=tk.DISABLED, relief=tk.SOLID, borderwidth=1,
                                                               font=('Segoe UI', 10))
        self.original_text_display.pack(fill=tk.X, expand=False, padx=5, pady=(0, 5))
        self.original_text_display.bind("<Enter>", self._on_text_enter)
        self.original_text_display.bind("<Leave>", self._on_text_leave)
        self.original_text_display.bind("<Motion>", self._on_text_motion)

        ttk.Label(top_section_frame, text=self.loc('translation_text_label')).pack(anchor=tk.W, padx=5, pady=(5, 2))
        self.translation_edit_text = scrolledtext.ScrolledText(top_section_frame, height=5, wrap=tk.WORD,
                                                               relief=tk.SOLID, borderwidth=1, undo=True,
                                                               font=('Segoe UI', 10))
        self.translation_edit_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        self.translation_edit_text.bind("<FocusOut>", self.apply_translation_focus_out)
        self.translation_edit_text.bind("<KeyRelease>", self.schedule_placeholder_validation)

        trans_actions_frame = ttk.Frame(top_section_frame)
        trans_actions_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        self.apply_btn = ttk.Button(trans_actions_frame, text=self.loc('apply_translation_button'),
                                    command=self.apply_translation_from_button, state=tk.DISABLED)
        self.apply_btn.pack(side=tk.LEFT, padx=(0, 10))
        self.ai_translate_current_btn = ttk.Button(trans_actions_frame, text=self.loc('ai_translate_button'),
                                                   command=self.app.ai_translate_selected, state=tk.DISABLED)
        self.ai_translate_current_btn.pack(side=tk.RIGHT, padx=5)

        ttk.Label(top_section_frame, text=self.loc('comment_label')).pack(anchor=tk.W, padx=5, pady=(5, 2))
        self.comment_edit_text = scrolledtext.ScrolledText(top_section_frame, height=3, wrap=tk.WORD, relief=tk.SOLID,
                                                           borderwidth=1, undo=True, font=('Segoe UI', 10))
        self.comment_edit_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        self.comment_edit_text.bind("<FocusOut>", self.apply_comment_focus_out)

        comment_actions_frame = ttk.Frame(top_section_frame)
        comment_actions_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        self.apply_comment_btn = ttk.Button(comment_actions_frame, text=self.loc('apply_comment_button'),
                                            command=self.apply_comment_from_button, state=tk.DISABLED)
        self.apply_comment_btn.pack(side=tk.LEFT)

        status_frame = ttk.Frame(top_section_frame)
        status_frame.pack(fill=tk.X, padx=5, pady=5)
        self.ignore_var = tk.BooleanVar()
        self.toggle_ignore_btn = ttk.Checkbutton(status_frame, text=self.loc('ignore_string_checkbox'),
                                                 variable=self.ignore_var, command=self.toggle_ignore_selected_checkbox,
                                                 state=tk.DISABLED)
        self.toggle_ignore_btn.pack(side=tk.LEFT, padx=5)
        self.reviewed_var = tk.BooleanVar()
        self.toggle_reviewed_btn = ttk.Checkbutton(status_frame, text=self.loc('reviewed_checkbox'),
                                                   variable=self.reviewed_var,
                                                   command=self.toggle_reviewed_selected_checkbox, state=tk.DISABLED)
        self.toggle_reviewed_btn.pack(side=tk.LEFT, padx=15)

        context_section_frame = ttk.Frame(details_paned_window, padding=5)
        details_paned_window.add(context_section_frame, weight=2)
        context_section_frame.columnconfigure(0, weight=1)
        context_section_frame.rowconfigure(1, weight=1)
        ttk.Label(context_section_frame, text=self.loc('context_preview_label')).pack(anchor=tk.W, padx=5, pady=(0, 2))
        self.context_text_display = scrolledtext.ScrolledText(context_section_frame, height=6, wrap=tk.WORD,
                                                              state=tk.DISABLED, relief=tk.SOLID, borderwidth=1,
                                                              font=("Consolas", 9))
        self.context_text_display.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        self.context_text_display.tag_config("highlight", background="yellow", foreground="black")

        tm_section_frame = ttk.Frame(details_paned_window, padding=5)
        details_paned_window.add(tm_section_frame, weight=2)
        tm_section_frame.columnconfigure(0, weight=1)
        tm_section_frame.rowconfigure(1, weight=1)

        ttk.Label(tm_section_frame, text=self.loc('tm_matches_label')).pack(anchor=tk.W, pady=(0, 2), padx=5)
        self.tm_suggestions_listbox = tk.Listbox(tm_section_frame, height=4, relief=tk.SOLID, borderwidth=1)
        self.tm_suggestions_listbox.pack(fill=tk.BOTH, expand=True, pady=(0, 5), padx=5)
        self.tm_suggestions_listbox.bind("<Double-1>", self.apply_tm_suggestion_from_listbox)

        ttk.Label(tm_section_frame, text=self.loc('termbase_matches_label')).pack(anchor=tk.W, pady=(0, 2), padx=5)
        self.tb_matches_listbox = tk.Listbox(tm_section_frame, height=2, relief=tk.SOLID, borderwidth=1)
        self.tb_matches_listbox.pack(fill=tk.BOTH, expand=True, pady=(0, 5), padx=5)

    def _setup_treeview_context_menu(self):
        self.tree_context_menu = tk.Menu(self.tree, tearoff=0)
        self.tree_context_menu.add_command(label=self.loc('copy_original'), command=self.cm_copy_original)
        self.tree_context_menu.add_command(label=self.loc('col_translation'), command=self.cm_copy_translation)
        self.tree_context_menu.add_separator()
        self.tree_context_menu.add_command(label=self.loc('ignore_string_checkbox'),
                                           command=lambda: self.cm_set_ignored_status(True))
        self.tree_context_menu.add_command(label=f"取消{self.loc('ignore_string_checkbox')}",
                                           command=lambda: self.cm_set_ignored_status(False))
        self.tree_context_menu.add_separator()
        self.tree_context_menu.add_command(label=self.loc('reviewed_checkbox'),
                                           command=lambda: self.cm_set_reviewed_status(True))
        self.tree_context_menu.add_command(label=f"取消{self.loc('reviewed_checkbox')}",
                                           command=lambda: self.cm_set_reviewed_status(False))
        self.tree_context_menu.add_separator()
        self.tree_context_menu.add_command(label=f"{self.loc('col_comment')}...", command=self.cm_edit_comment)
        self.tree_context_menu.add_separator()
        self.tree_context_menu.add_command(label=self.loc('apply_tm_untranslated'),
                                           command=self.cm_apply_tm_to_selected)
        self.tree_context_menu.add_command(label=f"清除选中项{self.loc('col_translation')}",
                                           command=self.cm_clear_selected_translations)
        self.tree_context_menu.add_separator()
        self.tree_context_menu.add_command(label=self.loc('ai_translate_selected'),
                                           command=self.app.ai_translate_selected)

    def show_treeview_context_menu(self, event):
        if not self.tree.selection(): return
        self.tree_context_menu.post(event.x_root, event.y_root)

    def _sort_treeview_column(self, col, reverse):
        if not self.tree._data: return
        col_index = self.tree.columns.index(col)

        def get_sort_key(iid):
            try:
                values = self.tree._data[iid]['values']
                value = values[col_index]
                if col in ("seq_id", "line"): return int(value)
                if col == "reviewed": return 1 if value == "✔" else 0
                return str(value).lower()
            except (ValueError, TypeError, IndexError):
                return 0

        sorted_iids = sorted(self.tree._ordered_iids, key=get_sort_key, reverse=reverse)
        self.tree._sync_data_order(sorted_iids)
        self.tree.heading(col, command=lambda: self._sort_treeview_column(col, not reverse))

    def _configure_treeview_tags(self):
        try:
            if self._ignored_tag_font is None and hasattr(self.tree, 'cget'):
                font_desc = self.tree.cget("font")
                if font_desc:
                    base_font = tk.font.nametofont(font_desc)
                    self._ignored_tag_font = tk.font.Font(family=base_font.actual("family"),
                                                          size=base_font.actual("size"), slant="italic")

            self.tree.tag_configure('ignored_row_visual', font=self._ignored_tag_font, foreground="#707070")
            self.tree.tag_configure('auto_ignored_visual', foreground="#a0a0a0", font=self._ignored_tag_font)
            self.tree.tag_configure('translated_row_visual', foreground="darkblue")
            self.tree.tag_configure('untranslated_row_visual', foreground="darkred")
            self.tree.tag_configure('reviewed_visual', foreground="darkgreen")
            self.tree.tag_configure('inherited_visual', foreground="purple")
            self.tree.tag_configure('search_highlight', background='yellow', foreground='black')

            self.original_text_display.tag_configure('placeholder', foreground='darkblue',
                                                     font=('Segoe UI', 10, 'bold'))
            self.original_text_display.tag_configure('placeholder_missing', background='#FFDDDD', foreground='red')
            self.original_text_display.tag_configure('term', background='lightcyan')
            self.translation_edit_text.tag_configure('placeholder', foreground='darkblue',
                                                     font=('Segoe UI', 10, 'bold'))
            self.translation_edit_text.tag_configure('placeholder_extra', background='#FFEBCD', foreground='orange red')
        except Exception as e:
            print(f"Error configuring treeview tags: {e}")

    def open_code_file_path(self, filepath):
        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                self.original_raw_code_content = f.read()
            self.current_code_file_path = filepath
            self.app.config_manager.set("last_dir", os.path.dirname(filepath))
            self.app.update_statusbar(self.loc('status_extracting_strings'), persistent=True)
            self.translatable_objects = CodeFileService.extract_translatable_strings(self.original_raw_code_content)
            self.app.apply_tm_to_all_current_strings(self, silent=True, only_if_empty=True)
            self.mark_modified(False)
            self.refresh_treeview()
            self.app.update_statusbar(
                self.loc('status_strings_loaded', os.path.basename(filepath), len(self.translatable_objects)),
                persistent=True)
        except Exception as e:
            messagebox.showerror(self.loc('error'),
                                 f"Failed to open or parse code file '{os.path.basename(filepath)}': {e}")
            self.app.close_current_tab()

    def open_project_file(self, project_filepath):
        try:
            project_data = ProjectService.open_project(project_filepath)

            self.current_code_file_path = project_data["original_code_file_path"]
            self.original_raw_code_content = project_data['original_raw_code_content']
            self.translatable_objects = project_data['translatable_objects']
            self.project_custom_instructions = project_data.get("project_custom_instructions", "")

            if project_data['code_load_warning']:
                messagebox.showwarning(self.loc('warning'), project_data['code_load_warning'])

            tm_path = project_data.get("current_tm_file_path")
            if tm_path and os.path.exists(tm_path):
                self.app.load_tm_from_excel(tm_path, silent=True)

            self.current_project_file_path = project_filepath
            self.app.config_manager.set("last_dir", os.path.dirname(project_filepath))
            self.mark_modified(False)
            self.refresh_treeview()
            self.app.update_statusbar(self.loc('status_project_loaded', os.path.basename(project_filepath)),
                                      persistent=True)
        except Exception as e:
            messagebox.showerror(self.loc('error'),
                                 f"Failed to load project file '{os.path.basename(project_filepath)}': {e}")
            self.app.close_current_tab()

    def save_project(self, ask_path=False):
        if not self.current_project_file_path or ask_path:
            initial_dir = os.path.dirname(self.current_project_file_path or self.current_code_file_path or os.getcwd())
            default_name = os.path.splitext(os.path.basename(self.current_code_file_path or "unnamed"))[0]

            filepath = filedialog.asksaveasfilename(
                defaultextension=constants.PROJECT_FILE_EXTENSION,
                filetypes=[("Overwatch Project Files", f"*{constants.PROJECT_FILE_EXTENSION}"), ("All Files", "*.*")],
                initialdir=initial_dir,
                initialfile=f"{default_name}{constants.PROJECT_FILE_EXTENSION}",
                title=self.loc('save_project_as')
            )
            if not filepath:
                return False
            self.current_project_file_path = filepath

        project_data = {
            "version": constants.APP_VERSION,
            "original_code_file_path": self.current_code_file_path or "",
            "translatable_objects_data": [ts.to_dict() for ts in self.translatable_objects],
            "project_custom_instructions": self.project_custom_instructions,
            "current_tm_file_path": self.app.current_tm_file or "",
        }

        try:
            ProjectService.save_project(self.current_project_file_path, project_data)
            self.mark_modified(False)
            self.app.update_statusbar(
                self.loc('status_project_saved', os.path.basename(self.current_project_file_path)), persistent=True)
            self.app.add_to_recent_files(self.current_project_file_path)
            return True
        except IOError as e:
            messagebox.showerror(self.loc('error'), str(e))
            return False

    def mark_modified(self, modified=True):
        if self.is_modified == modified:
            return
        self.is_modified = modified
        self.app.update_tab_title(self)

    def get_tab_text(self):
        base_name = "Untitled"
        if self.current_project_file_path:
            base_name = os.path.basename(self.current_project_file_path)
        elif self.current_code_file_path:
            base_name = os.path.basename(self.current_code_file_path)

        return f"{base_name}{self.loc('status_modified_indicator') if self.is_modified else ''}"

    def refresh_treeview(self, preserve_selection=True, item_to_reselect_after=None):
        old_selection = self.tree.selection()
        old_focus = self.tree.focus()

        self.tree.delete(*self.tree.get_children())
        self.displayed_string_ids = []

        processed_originals = set()
        seq_id = 1
        search_term = self.search_var.get().lower()
        if search_term == self.loc('quick_search_placeholder').lower():
            search_term = ""

        for ts_obj in self.translatable_objects:
            if self.deduplicate_strings_var.get() and ts_obj.original_semantic in processed_originals:
                continue
            if not self.show_ignored_var.get() and ts_obj.is_ignored:
                continue
            has_trans = bool(ts_obj.translation.strip())
            if self.show_untranslated_var.get() and has_trans and not ts_obj.is_ignored:
                continue
            if self.show_translated_var.get() and not has_trans and not ts_obj.is_ignored:
                continue
            if self.show_unreviewed_var.get() and ts_obj.is_reviewed:
                continue
            if search_term and not (
                    search_term in ts_obj.original_semantic.lower() or search_term in ts_obj.get_translation_for_ui().lower()):
                continue

            if self.deduplicate_strings_var.get():
                processed_originals.add(ts_obj.original_semantic)

            tags = []
            status = ""
            if ts_obj.is_ignored:
                tags.append('ignored_row_visual')
                status = "I"
                if ts_obj.was_auto_ignored:
                    tags.append('auto_ignored_visual')
                    status = "A"
            elif has_trans:
                tags.append('translated_row_visual')
                status = "T"
            else:
                tags.append('untranslated_row_visual')
                status = "U"

            if ts_obj.is_reviewed:
                tags.append('reviewed_visual')
            if ts_obj.is_inherited:
                tags.append('inherited_visual')
                status += "h"

            values = (
                seq_id, status,
                ts_obj.original_semantic.replace("\n", "↵"),
                ts_obj.get_translation_for_ui().replace("\n", "↵"),
                ts_obj.comment.replace("\n", "↵")[:50],
                "✔" if ts_obj.is_reviewed else "",
                ts_obj.line_num_in_file
            )
            self.tree.insert("", "end", iid=ts_obj.id, values=values, tags=tuple(tags))
            self.displayed_string_ids.append(ts_obj.id)
            seq_id += 1

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

        self.app.update_counts_display()
        self.on_tree_select(None)

    def find_string_from_toolbar(self):
        self.refresh_treeview()
        if self.displayed_string_ids:
            self.tree.selection_set(self.displayed_string_ids[0])
            self.tree.focus(self.displayed_string_ids[0])
            self.tree.see(self.displayed_string_ids[0])

    def on_tree_select(self, event):
        if self.current_selected_ts_id:
            ts_obj_before = self._find_ts_obj_by_id(self.current_selected_ts_id)
            if ts_obj_before:
                editor_text = self.translation_edit_text.get("1.0", tk.END).rstrip('\n')
                if editor_text != ts_obj_before.get_translation_for_ui():
                    self._apply_translation_to_model(ts_obj_before, editor_text, source="auto_save_on_select")

        focused_iid = self.tree.focus()
        if not focused_iid:
            self.clear_details_pane()
            self.current_selected_ts_id = None
            self.app.update_ui_state()
            return

        ts_obj = self._find_ts_obj_by_id(focused_iid)
        if not ts_obj: return

        self.current_selected_ts_id = ts_obj.id
        self.update_details_pane_for_selection(ts_obj)
        self.app.update_ui_state()

    def update_details_pane_for_selection(self, ts_obj):
        self.original_text_display.config(state=tk.NORMAL)
        self.original_text_display.delete("1.0", tk.END)
        self.original_text_display.insert("1.0", ts_obj.original_semantic)
        self._highlight_terms_in_original()
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
        if ts_obj.context_lines:
            for i, line in enumerate(ts_obj.context_lines):
                self.context_text_display.insert(tk.END, line + "\n")
                if i == ts_obj.current_line_in_context_idx:
                    self.context_text_display.tag_add("highlight", f"{i + 1}.0", f"{i + 1}.end")
        self.context_text_display.config(state=tk.DISABLED)

        self.ignore_var.set(ts_obj.is_ignored)
        self.reviewed_var.set(ts_obj.is_reviewed)

        self.update_tm_suggestions_for_text(ts_obj.original_semantic)
        self.update_tb_matches_for_text(ts_obj.original_semantic)

    def clear_details_pane(self):
        for widget in [self.original_text_display, self.translation_edit_text, self.comment_edit_text,
                       self.context_text_display]:
            widget.config(state=tk.NORMAL)
            widget.delete("1.0", tk.END)
            if widget != self.translation_edit_text and widget != self.comment_edit_text:
                widget.config(state=tk.DISABLED)
        self.tm_suggestions_listbox.delete(0, tk.END)
        self.tb_matches_listbox.delete(0, tk.END)
        self.ignore_var.set(False)
        self.reviewed_var.set(False)

    def _find_ts_obj_by_id(self, obj_id):
        return next((ts for ts in self.translatable_objects if ts.id == obj_id), None)

    def add_to_undo_history(self, action_type, data):
        self.undo_history.append({'type': action_type, 'data': deepcopy(data)})
        if len(self.undo_history) > constants.MAX_UNDO_HISTORY:
            self.undo_history.pop(0)
        self.redo_history.clear()
        self.mark_modified()
        self.app.update_ui_state()

    def undo_action(self):
        if not self.undo_history: return
        action = self.undo_history.pop()
        self._process_undo_redo(action, self.redo_history, is_undo=True)
        self.app.update_ui_state()

    def redo_action(self):
        if not self.redo_history: return
        action = self.redo_history.pop()
        self._process_undo_redo(action, self.undo_history, is_undo=False)
        self.app.update_ui_state()

    def _process_undo_redo(self, action, history_to_add_to, is_undo):
        action_type = action['type']
        data = action['data']
        reverse_changes = []

        changes = data.get('changes', [data])
        for change in changes:
            obj_id = change['string_id']
            field = change['field']
            value_to_restore = change['old_value'] if is_undo else change['new_value']

            ts_obj = self._find_ts_obj_by_id(obj_id)
            if not ts_obj: continue

            current_value = getattr(ts_obj,
                                    field) if field != 'translation' else ts_obj.get_translation_for_storage_and_tm()

            if is_undo:
                reverse_changes.append(
                    {'string_id': obj_id, 'field': field, 'old_value': value_to_restore, 'new_value': current_value})
            else:
                reverse_changes.append(
                    {'string_id': obj_id, 'field': field, 'old_value': current_value, 'new_value': value_to_restore})

            if field == 'translation':
                ts_obj.set_translation_internal(value_to_restore.replace("\\n", "\n"))
            else:
                setattr(ts_obj, field, value_to_restore)

        reverse_action_type = action_type
        if len(reverse_changes) == 1:
            history_to_add_to.append({'type': 'single_change', 'data': reverse_changes[0]})
        else:
            history_to_add_to.append({'type': reverse_action_type, 'data': {'changes': reverse_changes}})

        self.refresh_treeview(preserve_selection=True)
        if self.current_selected_ts_id:
            self.on_tree_select(None)
        self.mark_modified()

    def _apply_translation_to_model(self, ts_obj, new_translation, source="manual"):
        if new_translation == ts_obj.translation: return False

        old_translation = ts_obj.get_translation_for_storage_and_tm()
        ts_obj.set_translation_internal(new_translation)
        new_translation_stored = ts_obj.get_translation_for_storage_and_tm()

        if new_translation.strip():
            self.app.translation_memory[ts_obj.original_semantic] = new_translation_stored

        change_data = {'string_id': ts_obj.id, 'field': 'translation', 'old_value': old_translation,
                       'new_value': new_translation_stored}

        if source not in ["ai_batch_item"]:
            self.add_to_undo_history('single_change', change_data)

        self.refresh_treeview(preserve_selection=True)
        self.mark_modified()
        return True

    def apply_translation_from_button(self):
        if not self.current_selected_ts_id: return
        ts_obj = self._find_ts_obj_by_id(self.current_selected_ts_id)
        if not ts_obj: return
        new_translation = self.translation_edit_text.get("1.0", tk.END).rstrip('\n')
        self._apply_translation_to_model(ts_obj, new_translation)

    def apply_translation_focus_out(self, event):
        if not self.current_selected_ts_id: return
        ts_obj = self._find_ts_obj_by_id(self.current_selected_ts_id)
        if not ts_obj: return
        new_translation = self.translation_edit_text.get("1.0", tk.END).rstrip('\n')
        if new_translation != ts_obj.get_translation_for_ui():
            self._apply_translation_to_model(ts_obj, new_translation)

    def apply_and_go_next(self, event=None):
        if not self.current_selected_ts_id: return "break"

        ts_obj = self._find_ts_obj_by_id(self.current_selected_ts_id)
        if ts_obj:
            new_translation = self.translation_edit_text.get("1.0", tk.END).rstrip('\n')
            self._apply_translation_to_model(ts_obj, new_translation)

        all_iids = self.tree.get_children()
        untranslated_iids = [
            iid for iid in all_iids
            if not self._find_ts_obj_by_id(iid).translation.strip() and not self._find_ts_obj_by_id(iid).is_ignored
        ]

        if not untranslated_iids:
            try:
                current_idx = all_iids.index(self.current_selected_ts_id)
                next_idx = (current_idx + 1) % len(all_iids)
                next_iid = all_iids[next_idx]
                self.tree.selection_set(next_iid)
                self.tree.focus(next_iid)
                self.tree.see(next_iid)
            except (ValueError, IndexError):
                pass
            return "break"

        try:
            current_idx_in_untranslated = untranslated_iids.index(self.current_selected_ts_id)
            next_iid = untranslated_iids[(current_idx_in_untranslated + 1) % len(untranslated_iids)]
        except ValueError:
            next_iid = untranslated_iids[0]

        self.tree.selection_set(next_iid)
        self.tree.focus(next_iid)
        self.tree.see(next_iid)
        return "break"

    def _highlight_terms_in_original(self):
        self.original_text_display.tag_remove('term', '1.0', tk.END)
        content = self.original_text_display.get('1.0', tk.END)
        for term in self.termbase.get_all_terms():
            start_idx = '1.0'
            while True:
                pos = self.original_text_display.search(term, start_idx, stopindex=tk.END, nocase=True)
                if not pos:
                    break
                end_pos = f"{pos}+{len(term)}c"
                self.original_text_display.tag_add('term', pos, end_pos)
                start_idx = end_pos

    def _on_text_enter(self, event):
        self._on_text_motion(event)

    def _on_text_leave(self, event):
        if self._term_tooltip:
            self._term_tooltip.destroy()
            self._term_tooltip = None

    def _on_text_motion(self, event):
        widget = event.widget
        index = widget.index(f"@{event.x},{event.y}")
        tags = widget.tag_names(index)

        if 'term' in tags:
            word_range = widget.tag_prevrange('term', index + "+1c")
            if not word_range:
                word_range = widget.tag_nextrange('term', index)

            if word_range:
                term = widget.get(word_range[0], word_range[1])
                translation = self.termbase.get_term(term)
                if translation:
                    if self._term_tooltip: self._term_tooltip.destroy()
                    self._term_tooltip = tk.Toplevel(self)
                    self._term_tooltip.wm_overrideredirect(True)
                    self._term_tooltip.wm_geometry(f"+{event.x_root + 10}+{event.y_root + 10}")
                    label = ttk.Label(self._term_tooltip, text=f"{term} -> {translation}", background="lightyellow",
                                      relief="solid", borderwidth=1, padding=2)
                    label.pack()
                    return

        if self._term_tooltip:
            self._term_tooltip.destroy()
            self._term_tooltip = None

    def toggle_dock(self):
        if self.is_docked:
            self.docked_window = tk.Toplevel(self.app.root)
            self.docked_window.title(self.loc('details_panel_title'))
            self.docked_window.geometry("500x700")
            self.details_pane.pack_forget()
            self.details_pane.pack(in_=self.docked_window, expand=True, fill=tk.BOTH)
            self.dock_button.config(text=self.loc('undock_panel'))
            self.docked_window.protocol("WM_DELETE_WINDOW", self.toggle_dock)
        else:
            self.details_pane.pack_forget()
            self.details_pane.pack(in_=self.right_pane_container, expand=True, fill=tk.BOTH)
            self.dock_button.config(text=self.loc('dock_panel'))
            self.docked_window.destroy()
            self.docked_window = None
        self.is_docked = not self.is_docked

    def update_tm_suggestions_for_text(self, original_text):
        self.tm_suggestions_listbox.delete(0, tk.END)
        if not original_text: return

        if original_text in self.app.translation_memory:
            suggestion = self.app.translation_memory[original_text].replace("\\n", "\n")
            self.tm_suggestions_listbox.insert(tk.END, f"(100%): {suggestion}")
            self.tm_suggestions_listbox.itemconfig(tk.END, {'fg': 'darkgreen'})

        matches = []
        for tm_orig, tm_trans in self.app.translation_memory.items():
            if tm_orig == original_text: continue
            ratio = SequenceMatcher(None, original_text, tm_orig).ratio()
            if ratio > 0.65:
                matches.append((ratio, tm_orig, tm_trans))

        matches.sort(key=lambda x: x[0], reverse=True)
        for ratio, _, trans in matches[:3]:
            suggestion = trans.replace("\\n", "\n")
            self.tm_suggestions_listbox.insert(tk.END, f"({ratio:.0%}): {suggestion}")
            self.tm_suggestions_listbox.itemconfig(tk.END, {'fg': 'purple'})

    def update_tb_matches_for_text(self, original_text):
        self.tb_matches_listbox.delete(0, tk.END)
        mappings = self.termbase.get_mappings_for_text(original_text)
        if mappings:
            for m in mappings.split(','):
                self.tb_matches_listbox.insert(tk.END, m.strip())

    def apply_tm_suggestion_from_listbox(self, event):
        selected = self.tm_suggestions_listbox.curselection()
        if not selected: return

        full_text = self.tm_suggestions_listbox.get(selected[0])
        try:
            translation = full_text.split("): ", 1)[1].strip()
        except IndexError:
            translation = full_text

        self.translation_edit_text.delete('1.0', tk.END)
        self.translation_edit_text.insert('1.0', translation)
        self.apply_translation_from_button()

    # Dummy methods for context menu actions, real logic will be more complex
    def cm_copy_original(self):
        if self.current_selected_ts_id:
            ts_obj = self._find_ts_obj_by_id(self.current_selected_ts_id)
            if ts_obj:
                self.app.root.clipboard_clear()
                self.app.root.clipboard_append(ts_obj.original_semantic)

    def cm_copy_translation(self):
        if self.current_selected_ts_id:
            ts_obj = self._find_ts_obj_by_id(self.current_selected_ts_id)
            if ts_obj:
                self.app.root.clipboard_clear()
                self.app.root.clipboard_append(ts_obj.get_translation_for_ui())

    def cm_set_ignored_status(self, ignore_flag):
        self._bulk_update_status('is_ignored', ignore_flag)

    def cm_set_reviewed_status(self, reviewed_flag):
        self._bulk_update_status('is_reviewed', reviewed_flag)

    def _bulk_update_status(self, field, value):
        selected_iids = self.tree.selection()
        if not selected_iids: return

        changes = []
        for iid in selected_iids:
            ts_obj = self._find_ts_obj_by_id(iid)
            if ts_obj and getattr(ts_obj, field) != value:
                old_value = getattr(ts_obj, field)
                setattr(ts_obj, field, value)
                changes.append({'string_id': iid, 'field': field, 'old_value': old_value, 'new_value': value})

        if changes:
            self.add_to_undo_history('bulk_status_change', {'changes': changes})
            self.refresh_treeview(preserve_selection=True)

    def cm_edit_comment(self):
        selected_iids = self.tree.selection()
        if not selected_iids: return

        initial_comment = self._find_ts_obj_by_id(selected_iids[0]).comment if len(selected_iids) == 1 else ""
        new_comment = simpledialog.askstring("Edit Comment", "Enter new comment:", initialvalue=initial_comment)

        if new_comment is not None:
            changes = []
            for iid in selected_iids:
                ts_obj = self._find_ts_obj_by_id(iid)
                if ts_obj and ts_obj.comment != new_comment:
                    old_comment = ts_obj.comment
                    ts_obj.comment = new_comment
                    changes.append(
                        {'string_id': iid, 'field': 'comment', 'old_value': old_comment, 'new_value': new_comment})
            if changes:
                self.add_to_undo_history('bulk_comment_change', {'changes': changes})
                self.refresh_treeview(preserve_selection=True)

    def cm_apply_tm_to_selected(self):
        self.app.apply_tm_to_all_current_strings(self, only_if_empty=False, selected_only=True)

    def cm_clear_selected_translations(self):
        selected_iids = self.tree.selection()
        if not selected_iids: return
        if not messagebox.askyesno(self.loc('confirm'), f"Clear translations for {len(selected_iids)} items?"): return

        changes = []
        for iid in selected_iids:
            ts_obj = self._find_ts_obj_by_id(iid)
            if ts_obj and ts_obj.translation.strip():
                old_trans = ts_obj.get_translation_for_storage_and_tm()
                ts_obj.set_translation_internal("")
                changes.append({'string_id': iid, 'field': 'translation', 'old_value': old_trans, 'new_value': ""})

        if changes:
            self.add_to_undo_history('bulk_clear_translation', {'changes': changes})
            self.refresh_treeview(preserve_selection=True)

    def schedule_placeholder_validation(self, event=None):
        if self._placeholder_validation_job:
            self.after_cancel(self._placeholder_validation_job)
        self._placeholder_validation_job = self.after(150, self._update_placeholder_highlights)

    def _update_placeholder_highlights(self):
        if not self.current_selected_ts_id: return
        ts_obj = self._find_ts_obj_by_id(self.current_selected_ts_id)
        if not ts_obj: return

        original_text = ts_obj.original_semantic
        translated_text = self.translation_edit_text.get("1.0", tk.END)

        original_placeholders = set(self.placeholder_regex.findall(original_text))
        translated_placeholders = set(self.placeholder_regex.findall(translated_text))
        missing = original_placeholders - translated_placeholders
        extra = translated_placeholders - original_placeholders

        for tag in ['placeholder', 'placeholder_missing', 'placeholder_extra']:
            self.original_text_display.tag_remove(tag, '1.0', tk.END)
            self.translation_edit_text.tag_remove(tag, '1.0', tk.END)

        for match in self.placeholder_regex.finditer(original_text):
            start, end = f"1.0+{match.start()}c", f"1.0+{match.end()}c"
            tag = 'placeholder_missing' if match.group(1) in missing else 'placeholder'
            self.original_text_display.tag_add(tag, start, end)

        for match in self.placeholder_regex.finditer(translated_text):
            start, end = f"1.0+{match.start()}c", f"1.0+{match.end()}c"
            tag = 'placeholder_extra' if match.group(1) in extra else 'placeholder'
            self.translation_edit_text.tag_add(tag, start, end)

    def apply_comment_from_button(self):
        if not self.current_selected_ts_id: return
        ts_obj = self._find_ts_obj_by_id(self.current_selected_ts_id)
        if not ts_obj: return
        new_comment = self.comment_edit_text.get("1.0", tk.END).rstrip('\n')
        self._apply_comment_to_model(ts_obj, new_comment)

    def apply_comment_focus_out(self, event=None):
        if not self.current_selected_ts_id: return
        ts_obj = self._find_ts_obj_by_id(self.current_selected_ts_id)
        if not ts_obj: return
        new_comment = self.comment_edit_text.get("1.0", tk.END).rstrip('\n')
        if new_comment != ts_obj.comment:
            self._apply_comment_to_model(ts_obj, new_comment)

    def _apply_comment_to_model(self, ts_obj, new_comment):
        if new_comment == ts_obj.comment: return False
        old_comment = ts_obj.comment
        ts_obj.comment = new_comment
        self.add_to_undo_history('single_change', {'string_id': ts_obj.id, 'field': 'comment', 'old_value': old_comment,
                                                   'new_value': new_comment})
        self.refresh_treeview(preserve_selection=True)
        self.mark_modified()
        return True

    def toggle_ignore_selected_checkbox(self):
        if not self.current_selected_ts_id: return
        self._bulk_update_status('is_ignored', self.ignore_var.get())

    def toggle_reviewed_selected_checkbox(self):
        if not self.current_selected_ts_id: return
        self._bulk_update_status('is_reviewed', self.reviewed_var.get())