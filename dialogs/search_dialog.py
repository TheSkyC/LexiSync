import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import re


class AdvancedSearchDialog(simpledialog.Dialog):
    def __init__(self, parent, title, project_tab_ref):
        self.tab = project_tab_ref
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

        ttk.Label(master, text="Find what:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.search_entry = ttk.Entry(master, textvariable=self.search_term_var, width=40)
        self.search_entry.grid(row=0, column=1, columnspan=2, sticky=tk.EW, padx=5, pady=2)
        self.search_entry.bind("<Return>", lambda e: self._find_next())

        ttk.Label(master, text="Replace with:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.replace_entry = ttk.Entry(master, textvariable=self.replace_term_var, width=40)
        self.replace_entry.grid(row=1, column=1, columnspan=2, sticky=tk.EW, padx=5, pady=2)

        options_frame = ttk.Frame(master)
        options_frame.grid(row=2, column=0, columnspan=3, sticky=tk.W, padx=5, pady=5)
        ttk.Checkbutton(options_frame, text="Case sensitive", variable=self.case_sensitive_var).pack(side=tk.LEFT,
                                                                                                     padx=2)

        self.results_label = ttk.Label(master, text="")
        self.results_label.grid(row=3, column=0, columnspan=3, sticky=tk.W, padx=5, pady=2)

        return self.search_entry

    def buttonbox(self):
        box = ttk.Frame(self)
        ttk.Button(box, text="Find Next", command=self._find_next).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(box, text="Replace", command=self._replace_current).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(box, text="Replace All (Visible)", command=lambda: self._replace_all(in_view=True)).pack(
            side=tk.LEFT, padx=5, pady=5)
        ttk.Button(box, text="Replace All (Document)", command=lambda: self._replace_all(in_view=False)).pack(
            side=tk.LEFT, padx=5, pady=5)
        ttk.Button(box, text="Close", command=self.ok).pack(side=tk.LEFT, padx=5, pady=5)
        self.bind("<Escape>", self.cancel)
        box.pack(pady=5)

    def _clear_search_highlights(self):
        self.tab.tree.tag_configure('search_highlight', background='')

    def _perform_search(self):
        self.search_results_iids = []
        self.current_search_index = -1
        self._clear_search_highlights()

        search_term = self.search_term_var.get()
        if not search_term:
            self.results_label.config(text="Please enter a search term.")
            return

        case_sensitive = self.case_sensitive_var.get()
        items_to_search = self.tab.translatable_objects

        for ts_obj in items_to_search:
            original_text = ts_obj.original_semantic
            translated_text = ts_obj.get_translation_for_ui()

            flags = 0 if case_sensitive else re.IGNORECASE
            try:
                if re.search(search_term, original_text, flags) or re.search(search_term, translated_text, flags):
                    self.search_results_iids.append(ts_obj.id)
                    if self.tab.tree.exists(ts_obj.id):
                        self.tab.tree.item(ts_obj.id, tags=('search_highlight',))
            except re.error:
                self.results_label.config(text="Invalid regular expression.")
                return

        if self.search_results_iids:
            self.results_label.config(text=f"Found {len(self.search_results_iids)} matches.")
            self.tab.tree.tag_configure('search_highlight', background='yellow', foreground='black')
        else:
            self.results_label.config(text="No matches found.")

    def _find_next(self):
        if not self.search_results_iids or self.search_term_var.get() != getattr(self, "_last_search_term", None):
            self._perform_search()
            self._last_search_term = self.search_term_var.get()

        if not self.search_results_iids: return

        self.current_search_index = (self.current_search_index + 1) % len(self.search_results_iids)

        target_iid = self.search_results_iids[self.current_search_index]
        if self.tab.tree.exists(target_iid):
            self.tab.tree.selection_set(target_iid)
            self.tab.tree.focus(target_iid)
            self.tab.tree.see(target_iid)
            self.tab.on_tree_select(None)
            self.last_found_tree_iid = target_iid
            self.results_label.config(text=f"Match {self.current_search_index + 1}/{len(self.search_results_iids)}")
        else:
            self.results_label.config(
                text=f"Match {self.current_search_index + 1}/{len(self.search_results_iids)} (not visible in current view)")

    def _replace_current(self):
        if not self.last_found_tree_iid or not self.tab.tree.exists(self.last_found_tree_iid):
            messagebox.showinfo("No Selection", "Please find an item to replace first.", parent=self)
            return

        ts_obj = self.tab._find_ts_obj_by_id(self.last_found_tree_iid)
        if not ts_obj: return

        search_term = self.search_term_var.get()
        replace_term = self.replace_term_var.get()
        case_sensitive = self.case_sensitive_var.get()

        if not search_term:
            messagebox.showerror("Error", "Find what cannot be empty.", parent=self)
            return

        current_translation = ts_obj.get_translation_for_ui()
        flags = 0 if case_sensitive else re.IGNORECASE

        try:
            new_translation, num_subs = re.subn(search_term, replace_term, current_translation, count=1, flags=flags)
        except re.error:
            messagebox.showerror("Error", "Invalid regular expression in 'Find what'.", parent=self)
            return

        if num_subs > 0:
            self.tab._apply_translation_to_model(ts_obj, new_translation.rstrip('\n'), source="replace_current")
            self.results_label.config(text="Replaced.")
            if self.tab.current_selected_ts_id == ts_obj.id:
                self.tab.translation_edit_text.delete("1.0", tk.END)
                self.tab.translation_edit_text.insert("1.0", new_translation.rstrip('\n'))
            self._find_next()
        else:
            self.results_label.config(text="No match in current selection's translation.")
            self._find_next()

    def _replace_all(self, in_view=False):
        search_term = self.search_term_var.get()
        replace_term = self.replace_term_var.get()
        case_sensitive = self.case_sensitive_var.get()

        if not search_term:
            messagebox.showerror("Error", "Find what cannot be empty.", parent=self)
            return

        items_to_process_ids = self.tab.displayed_string_ids if in_view else [ts.id for ts in
                                                                              self.tab.translatable_objects]

        if not messagebox.askyesno("Confirm Replace All",
                                   f"Are you sure you want to replace all occurrences in {'visible items' if in_view else 'the entire document'}?",
                                   parent=self):
            return

        replaced_count = 0
        bulk_changes = []
        flags = 0 if case_sensitive else re.IGNORECASE

        for ts_id in items_to_process_ids:
            ts_obj = self.tab._find_ts_obj_by_id(ts_id)
            if not ts_obj or ts_obj.is_ignored: continue

            current_translation = ts_obj.get_translation_for_ui()
            try:
                new_translation, num_subs = re.subn(search_term, replace_term, current_translation, flags=flags)
            except re.error:
                messagebox.showerror("Error", "Invalid regular expression in 'Find what'.", parent=self)
                return

            if num_subs > 0:
                old_value = ts_obj.get_translation_for_storage_and_tm()
                ts_obj.set_translation_internal(new_translation.rstrip('\n'))
                new_value = ts_obj.get_translation_for_storage_and_tm()
                bulk_changes.append(
                    {'string_id': ts_obj.id, 'field': 'translation', 'old_value': old_value, 'new_value': new_value})
                replaced_count += 1

        if bulk_changes:
            self.tab.add_to_undo_history('bulk_replace_all', {'changes': bulk_changes})
            self.tab.refresh_treeview(preserve_selection=True)
            if self.tab.current_selected_ts_id: self.tab.on_tree_select(None)
            messagebox.showinfo("Replace All Complete", f"Replacements were made in {replaced_count} items.",
                                parent=self)
        else:
            messagebox.showinfo("Replace All", "No replaceable matches were found.", parent=self)

        self._perform_search()

    def apply(self):
        self._clear_search_highlights()
        self.tab.refresh_treeview(preserve_selection=True)