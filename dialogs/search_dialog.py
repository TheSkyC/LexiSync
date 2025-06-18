# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
import re

class AdvancedSearchDialog(simpledialog.Dialog):
    def __init__(self, parent, title, app_instance):
        self.app = app_instance
        self.search_term_var = tk.StringVar()
        self.replace_term_var = tk.StringVar()
        self.case_sensitive_var = tk.BooleanVar(value=False)
        self.regex_var = tk.BooleanVar(value=False)
        self.whole_word_var = tk.BooleanVar(value=False)

        self.last_found_tree_iid = None
        self.search_results_iids = []
        self.current_search_index = -1

        super().__init__(parent, title)

    def body(self, master):
        master.columnconfigure(1, weight=1)

        ttk.Label(master, text="查找内容:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.search_entry = ttk.Entry(master, textvariable=self.search_term_var, width=40)
        self.search_entry.grid(row=0, column=1, columnspan=2, sticky=tk.EW, padx=5, pady=2)
        self.search_entry.bind("<Return>", lambda e: self._find_next())

        ttk.Label(master, text="替换为:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.replace_entry = ttk.Entry(master, textvariable=self.replace_term_var, width=40)
        self.replace_entry.grid(row=1, column=1, columnspan=2, sticky=tk.EW, padx=5, pady=2)

        options_frame = ttk.Frame(master)
        options_frame.grid(row=2, column=0, columnspan=3, sticky=tk.W, padx=5, pady=5)
        ttk.Checkbutton(options_frame, text="区分大小写", variable=self.case_sensitive_var).pack(side=tk.LEFT, padx=2)
        ttk.Checkbutton(options_frame, text="正则表达式", variable=self.regex_var, state=tk.DISABLED).pack(side=tk.LEFT,
                                                                                                           padx=2)
        ttk.Checkbutton(options_frame, text="全字匹配", variable=self.whole_word_var, state=tk.DISABLED).pack(
            side=tk.LEFT, padx=2)

        self.results_label = ttk.Label(master, text="")
        self.results_label.grid(row=3, column=0, columnspan=3, sticky=tk.W, padx=5, pady=2)

        return self.search_entry

    def buttonbox(self):
        box = ttk.Frame(self)

        ttk.Button(box, text="查找下一个", command=self._find_next).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(box, text="替换", command=self._replace_current).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(box, text="全部替换 (可见项)", command=lambda: self._replace_all(in_view=True)).pack(side=tk.LEFT,
                                                                                                        padx=5, pady=5)
        ttk.Button(box, text="全部替换 (文档)", command=lambda: self._replace_all(in_view=False)).pack(side=tk.LEFT,
                                                                                                       padx=5, pady=5)
        ttk.Button(box, text="关闭", command=self.ok).pack(side=tk.LEFT, padx=5, pady=5)

        self.bind("<Escape>", self.cancel)
        box.pack(pady=5)

    def _clear_search_highlights(self):
        self.app.tree.tag_configure('search_highlight', background='')

    def _perform_search(self):
        self.search_results_iids = []
        self.current_search_index = -1
        self._clear_search_highlights()

        search_term = self.search_term_var.get()
        if not search_term:
            self.results_label.config(text="请输入查找内容。")
            return

        case_sensitive = self.case_sensitive_var.get()
        items_to_search = self.app.translatable_objects

        for ts_obj in items_to_search:
            original_text = ts_obj.original_semantic
            translated_text = ts_obj.get_translation_for_ui()

            match_in_original = False
            match_in_translation = False

            if case_sensitive:
                if search_term in original_text:
                    match_in_original = True
                if search_term in translated_text:
                    match_in_translation = True
            else:
                if search_term.lower() in original_text.lower():
                    match_in_original = True
                if search_term.lower() in translated_text.lower():
                    match_in_translation = True

            if match_in_original or match_in_translation:
                self.search_results_iids.append(ts_obj.id)
                if self.app.tree.exists(ts_obj.id):
                    self.app.tree.item(ts_obj.id, tags=('search_highlight',))

        if self.search_results_iids:
            self.results_label.config(text=f"找到 {len(self.search_results_iids)} 个匹配项。")
            self.app.tree.tag_configure('search_highlight', background='yellow', foreground='black')
        else:
            self.results_label.config(text="未找到匹配项。")

    def _find_next(self):
        search_term = self.search_term_var.get()
        if not search_term:
            self.results_label.config(text="请输入查找内容。")
            return

        if not self.search_results_iids:
            self._perform_search()

        if not self.search_results_iids:
            return

        self.current_search_index += 1
        if self.current_search_index >= len(self.search_results_iids):
            self.current_search_index = 0

        if self.search_results_iids:
            target_iid = self.search_results_iids[self.current_search_index]
            if self.app.tree.exists(target_iid):
                self.app.tree.selection_set(target_iid)
                self.app.tree.focus(target_iid)
                self.app.tree.see(target_iid)
                self.app.on_tree_select(None)
                self.last_found_tree_iid = target_iid
                self.results_label.config(
                    text=f"匹配项 {self.current_search_index + 1}/{len(self.search_results_iids)}")
            else:
                self.results_label.config(
                    text=f"匹配项 {self.current_search_index + 1}/{len(self.search_results_iids)} (当前不可见)")
                start_idx = self.current_search_index
                for i in range(len(self.search_results_iids)):
                    next_idx = (start_idx + i) % len(self.search_results_iids)
                    potential_iid = self.search_results_iids[next_idx]
                    if self.app.tree.exists(potential_iid):
                        self.current_search_index = next_idx
                        self.app.tree.selection_set(potential_iid)
                        self.app.tree.focus(potential_iid)
                        self.app.tree.see(potential_iid)
                        self.app.on_tree_select(None)
                        self.last_found_tree_iid = potential_iid
                        self.results_label.config(
                            text=f"匹配项 {self.current_search_index + 1}/{len(self.search_results_iids)}")
                        break

    def _replace_current(self):
        if not self.last_found_tree_iid or not self.app.tree.exists(self.last_found_tree_iid):
            messagebox.showinfo("无选中项", "请先查找一个项目以替换。", parent=self)
            return

        ts_obj = self.app._find_ts_obj_by_id(self.last_found_tree_iid)
        if not ts_obj: return

        search_term = self.search_term_var.get()
        replace_term = self.replace_term_var.get()
        case_sensitive = self.case_sensitive_var.get()

        if not search_term:
            messagebox.showerror("错误", "查找内容不能为空。", parent=self)
            return

        changes_made = False
        current_translation_ui = ts_obj.get_translation_for_ui()

        new_translation_ui = ""
        if case_sensitive:
            new_translation_ui = current_translation_ui.replace(search_term, replace_term, 1)
        else:
            start_index = current_translation_ui.lower().find(search_term.lower())
            if start_index != -1:
                new_translation_ui = current_translation_ui[:start_index] + \
                                     replace_term + \
                                     current_translation_ui[start_index + len(search_term):]
            else:
                new_translation_ui = current_translation_ui

        if new_translation_ui != current_translation_ui:
            self.app._apply_translation_to_model(ts_obj, new_translation_ui.rstrip('\n'), source="replace_current")
            changes_made = True
            self.results_label.config(text="已替换。")
            if self.app.current_selected_ts_id == ts_obj.id:
                self.app.translation_edit_text.delete("1.0", tk.END)
                self.app.translation_edit_text.insert("1.0", new_translation_ui.rstrip('\n'))
        else:
            self.results_label.config(text="当前选中项译文中未找到匹配（或替换无变化）。")

        if changes_made:
            self._find_next()

    def _replace_all(self, in_view=False):
        search_term = self.search_term_var.get()
        replace_term = self.replace_term_var.get()
        case_sensitive = self.case_sensitive_var.get()

        if not search_term:
            messagebox.showerror("错误", "查找内容不能为空。", parent=self)
            return

        items_to_process_ids = []
        if in_view:
            items_to_process_ids = self.app.displayed_string_ids
        else:
            items_to_process_ids = [ts.id for ts in self.app.translatable_objects]

        if not items_to_process_ids:
            messagebox.showinfo("无项目", "没有可供替换的项目。", parent=self)
            return

        confirm_msg = f"确定要在 {'可见项' if in_view else '整个文档'} 中将所有 \"{search_term}\" 替换为 \"{replace_term}\" 吗？\n此操作将影响译文。"
        if not messagebox.askyesno("确认全部替换", confirm_msg, parent=self):
            return

        replaced_count = 0
        bulk_changes_for_undo = []

        for ts_id in items_to_process_ids:
            ts_obj = self.app._find_ts_obj_by_id(ts_id)
            if not ts_obj or ts_obj.is_ignored:
                continue

            old_translation_for_undo = ts_obj.get_translation_for_storage_and_tm()
            current_translation_ui = ts_obj.get_translation_for_ui()
            new_translation_ui = ""

            if case_sensitive:
                new_translation_ui = current_translation_ui.replace(search_term, replace_term)
            else:
                try:
                    pattern = re.compile(re.escape(search_term), re.IGNORECASE)
                    new_translation_ui = pattern.sub(replace_term, current_translation_ui)
                except re.error:
                    messagebox.showerror("错误", "查找内容无法编译为有效的正则表达式。", parent=self)
                    return

            if new_translation_ui != current_translation_ui:
                ts_obj.set_translation_internal(new_translation_ui.rstrip('\n'))
                if new_translation_ui.strip():
                    self.app.translation_memory[ts_obj.original_semantic] = ts_obj.get_translation_for_storage_and_tm()

                bulk_changes_for_undo.append({
                    'string_id': ts_obj.id,
                    'field': 'translation',
                    'old_value': old_translation_for_undo,
                    'new_value': ts_obj.get_translation_for_storage_and_tm()
                })
                replaced_count += 1

        if bulk_changes_for_undo:
            self.app.add_to_undo_history('bulk_replace_all', {'changes': bulk_changes_for_undo})
            self.app.refresh_treeview_preserve_selection()
            if self.app.current_selected_ts_id:
                self.app.on_tree_select(None)
            messagebox.showinfo("全部替换完成", f"已在 {replaced_count} 个项目的译文中执行替换。", parent=self)
        else:
            messagebox.showinfo("全部替换", "未找到可替换的匹配项 (或替换无变化)。", parent=self)

        self._perform_search()

    def apply(self):
        self._clear_search_highlights()
        self.app.refresh_treeview_preserve_selection()