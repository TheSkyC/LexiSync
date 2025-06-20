# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
import re
from utils.localization import _


class AdvancedSearchDialog(simpledialog.Dialog):
    def __init__(self, parent, title, app_instance):
        self.app = app_instance
        self.search_term_var = tk.StringVar()
        self.replace_term_var = tk.StringVar()
        self.case_sensitive_var = tk.BooleanVar(value=False)
        self.regex_var = tk.BooleanVar(value=False)
        self.whole_word_var = tk.BooleanVar(value=False)

        self.last_found_row_index = -1
        self.search_results_indices = []
        self.current_search_index = -1

        super().__init__(parent, title)

    def body(self, master):
        master.columnconfigure(1, weight=1)

        ttk.Label(master, text=_("Find what:")).grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.search_entry = ttk.Entry(master, textvariable=self.search_term_var, width=40)
        self.search_entry.grid(row=0, column=1, columnspan=2, sticky=tk.EW, padx=5, pady=2)
        self.search_entry.bind("<Return>", lambda e: self._find_next())

        ttk.Label(master, text=_("Replace with:")).grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.replace_entry = ttk.Entry(master, textvariable=self.replace_term_var, width=40)
        self.replace_entry.grid(row=1, column=1, columnspan=2, sticky=tk.EW, padx=5, pady=2)

        options_frame = ttk.Frame(master)
        options_frame.grid(row=2, column=0, columnspan=3, sticky=tk.W, padx=5, pady=5)
        ttk.Checkbutton(options_frame, text=_("Case sensitive"), variable=self.case_sensitive_var).pack(side=tk.LEFT,
                                                                                                        padx=2)
        ttk.Checkbutton(options_frame, text=_("Regular expression"), variable=self.regex_var, state=tk.DISABLED).pack(
            side=tk.LEFT,
            padx=2)
        ttk.Checkbutton(options_frame, text=_("Whole word"), variable=self.whole_word_var, state=tk.DISABLED).pack(
            side=tk.LEFT, padx=2)

        self.results_label = ttk.Label(master, text="")
        self.results_label.grid(row=3, column=0, columnspan=3, sticky=tk.W, padx=5, pady=2)

        return self.search_entry

    def buttonbox(self):
        box = ttk.Frame(self)

        ttk.Button(box, text=_("Find Next"), command=self._find_next).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(box, text=_("Replace"), command=self._replace_current).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(box, text=_("Replace All (Visible)"), command=lambda: self._replace_all(in_view=True)).pack(
            side=tk.LEFT,
            padx=5, pady=5)
        ttk.Button(box, text=_("Replace All (Document)"), command=lambda: self._replace_all(in_view=False)).pack(
            side=tk.LEFT,
            padx=5, pady=5)
        ttk.Button(box, text=_("Close"), command=self.ok).pack(side=tk.LEFT, padx=5, pady=5)

        self.bind("<Escape>", self.cancel)
        box.pack(pady=5)

    def _clear_search_highlights(self):
        self.app.sheet.dehighlight_all()
        self.app._apply_row_highlighting()
        self.app.sheet.redraw()

    def _perform_search(self):
        self.search_results_indices = []
        self.current_search_index = -1
        self._clear_search_highlights()

        search_term = self.search_term_var.get()
        if not search_term:
            self.results_label.config(text=_("Please enter a search term."))
            return

        case_sensitive = self.case_sensitive_var.get()

        for row_idx, ts_id in enumerate(self.app.displayed_string_ids):
            ts_obj = self.app._find_ts_obj_by_id(ts_id)
            if not ts_obj: continue

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
                self.search_results_indices.append(row_idx)
                self.app.sheet.highlight_cells(row=row_idx, bg='yellow', fg='black', redraw=False)

        self.app.sheet.redraw()

        if self.search_results_indices:
            self.results_label.config(text=_("Found {count} matches.").format(count=len(self.search_results_indices)))
        else:
            self.results_label.config(text=_("No matches found."))

    def _find_next(self):
        search_term = self.search_term_var.get()
        if not search_term:
            self.results_label.config(text=_("Please enter a search term."))
            return

        if not self.search_results_indices:
            self._perform_search()

        if not self.search_results_indices:
            return

        self.current_search_index += 1
        if self.current_search_index >= len(self.search_results_indices):
            self.current_search_index = 0

        if self.search_results_indices:
            target_row_index = self.search_results_indices[self.current_search_index]

            self.app.sheet.select_row(target_row_index, add_to_selection=False)
            self.app.sheet.see(row=target_row_index, keep_xscroll=True)
            self.app.on_sheet_select(None)
            self.last_found_row_index = target_row_index

            self.results_label.config(
                text=_("Match {current}/{total}").format(current=self.current_search_index + 1,
                                                         total=len(self.search_results_indices)))

    def _replace_current(self):
        if self.last_found_row_index == -1:
            messagebox.showinfo(_("No Selection"), _("Please find an item to replace first."), parent=self)
            return

        if self.last_found_row_index >= len(self.app.displayed_string_ids):
            return

        ts_id = self.app.displayed_string_ids[self.last_found_row_index]
        ts_obj = self.app._find_ts_obj_by_id(ts_id)
        if not ts_obj: return

        search_term = self.search_term_var.get()
        replace_term = self.replace_term_var.get()
        case_sensitive = self.case_sensitive_var.get()

        if not search_term:
            messagebox.showerror(_("Error"), _("Find what cannot be empty."), parent=self)
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
            self.results_label.config(text=_("Replaced."))
            if self.app.current_selected_ts_id == ts_obj.id:
                self.app.translation_edit_text.delete("1.0", tk.END)
                self.app.translation_edit_text.insert("1.0", new_translation_ui.rstrip('\n'))
        else:
            self.results_label.config(text=_("No match found in current translation (or no change after replace)."))

        if changes_made:
            self._find_next()

    def _replace_all(self, in_view=False):
        search_term = self.search_term_var.get()
        replace_term = self.replace_term_var.get()
        case_sensitive = self.case_sensitive_var.get()

        if not search_term:
            messagebox.showerror(_("Error"), _("Find what cannot be empty."), parent=self)
            return

        items_to_process_ids = []
        if in_view:
            items_to_process_ids = self.app.displayed_string_ids
        else:
            items_to_process_ids = [ts.id for ts in self.app.translatable_objects]

        if not items_to_process_ids:
            messagebox.showinfo(_("No Items"), _("No items available for replacement."), parent=self)
            return

        scope_text = _("visible items") if in_view else _("the entire document")
        confirm_msg = _(
            "Are you sure you want to replace all \"{search_term}\" with \"{replace_term}\" in {scope}?\nThis operation will affect translations.").format(
            search_term=search_term, replace_term=replace_term, scope=scope_text
        )
        if not messagebox.askyesno(_("Confirm Replace All"), confirm_msg, parent=self):
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
                    messagebox.showerror(_("Error"), _("Find what cannot be compiled into a valid regular expression."),
                                         parent=self)
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
            self.app.refresh_sheet_preserve_selection()
            if self.app.current_selected_ts_id:
                self.app.on_sheet_select(None)
            messagebox.showinfo(_("Replace All Complete"),
                                _("Replaced in {count} items' translations.").format(count=replaced_count), parent=self)
        else:
            messagebox.showinfo(_("Replace All"), _("No replaceable matches found (or no change after replace)."),
                                parent=self)

        self._perform_search()

    def apply(self):
        self._clear_search_highlights()
        self.app.refresh_sheet_preserve_selection()