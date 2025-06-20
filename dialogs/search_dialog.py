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
        self.search_in_original_var = tk.BooleanVar(value=True)
        self.search_in_translation_var = tk.BooleanVar(value=True)
        self.search_in_comment_var = tk.BooleanVar(value=True)

        self.search_results = []
        self.current_result_index = -1
        self.last_search_options = {}

        super().__init__(parent, title)

    def body(self, master):
        master.columnconfigure(1, weight=1)

        ttk.Label(master, text=_("Find what:")).grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.search_entry = ttk.Entry(master, textvariable=self.search_term_var, width=40)
        self.search_entry.grid(row=0, column=1, columnspan=2, sticky=tk.EW, padx=5, pady=2)
        self.search_entry.bind("<Return>", lambda e: self._find_next())
        self.search_term_var.trace_add("write", self._on_search_term_changed)

        ttk.Label(master, text=_("Replace with:")).grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.replace_entry = ttk.Entry(master, textvariable=self.replace_term_var, width=40)
        self.replace_entry.grid(row=1, column=1, columnspan=2, sticky=tk.EW, padx=5, pady=2)

        options_frame = ttk.LabelFrame(master, text=_("Options"), padding=5)
        options_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=5, pady=5)

        ttk.Checkbutton(options_frame, text=_("Case sensitive"), variable=self.case_sensitive_var).pack(side=tk.LEFT,
                                                                                                        padx=5)

        search_in_frame = ttk.Frame(options_frame)
        search_in_frame.pack(side=tk.LEFT, padx=10)
        ttk.Label(search_in_frame, text=_("Search in:")).pack(side=tk.LEFT)
        ttk.Checkbutton(search_in_frame, text=_("Original"), variable=self.search_in_original_var).pack(side=tk.LEFT)
        ttk.Checkbutton(search_in_frame, text=_("Translation"), variable=self.search_in_translation_var).pack(
            side=tk.LEFT)
        ttk.Checkbutton(search_in_frame, text=_("Comment"), variable=self.search_in_comment_var).pack(side=tk.LEFT)

        self.results_label = ttk.Label(master, text="")
        self.results_label.grid(row=3, column=0, columnspan=3, sticky=tk.W, padx=5, pady=2)

        return self.search_entry

    def buttonbox(self):
        box = ttk.Frame(self)
        ttk.Button(box, text=_("Find Next"), command=self._find_next).pack(side=tk.LEFT, padx=2)
        ttk.Button(box, text=_("Find Previous"), command=self._find_prev).pack(side=tk.LEFT, padx=2)
        ttk.Button(box, text=_("Replace"), command=self._replace_current).pack(side=tk.LEFT, padx=2)
        ttk.Button(box, text=_("Replace All"), command=self._replace_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(box, text=_("Close"), command=self.destroy).pack(side=tk.RIGHT, padx=5)
        self.bind("<Escape>", lambda e: self.destroy())
        box.pack(pady=5)

    def destroy(self):
        self._clear_all_highlights()
        super().destroy()

    def _on_search_term_changed(self, *args):
        self.last_search_options = {}
        self.results_label.config(text="")

    def _get_current_search_options(self):
        return {
            "term": self.search_term_var.get(),
            "case": self.case_sensitive_var.get(),
            "in_orig": self.search_in_original_var.get(),
            "in_trans": self.search_in_translation_var.get(),
            "in_comment": self.search_in_comment_var.get()
        }

    def _perform_search(self):
        current_options = self._get_current_search_options()
        if self.last_search_options == current_options:
            return True

        self._clear_all_highlights()
        self.search_results = []
        self.current_result_index = -1

        term = current_options["term"]
        if not term:
            self.results_label.config(text=_("Please enter a search term."))
            return False

        flags = 0 if current_options["case"] else re.IGNORECASE
        try:
            pattern = re.compile(re.escape(term), flags)
        except re.error:
            self.results_label.config(text=_("Invalid search term."))
            return False

        for row_idx, ts_id in enumerate(self.app.displayed_string_ids):
            ts_obj = self.app._find_ts_obj_by_id(ts_id)
            if not ts_obj: continue

            if current_options["in_orig"] and pattern.search(ts_obj.original_semantic):
                self.search_results.append({"row": row_idx, "col": 2, "id": ts_id})
            if current_options["in_trans"] and pattern.search(ts_obj.get_translation_for_ui()):
                self.search_results.append({"row": row_idx, "col": 3, "id": ts_id})
            if current_options["in_comment"] and pattern.search(ts_obj.comment):
                self.search_results.append({"row": row_idx, "col": 4, "id": ts_id})

        self.search_results.sort(key=lambda r: (r["row"], r["col"]))
        self.last_search_options = current_options
        self._highlight_all_matches()

        if self.search_results:
            self.results_label.config(text=_("Found {count} matches.").format(count=len(self.search_results)))
        else:
            self.results_label.config(text=_("No matches found."))

        return bool(self.search_results)

    def _clear_all_highlights(self):
        self.app.sheet.dehighlight_all()
        self.app._apply_row_highlighting()
        self.app.sheet.redraw()

    def _highlight_all_matches(self):
        self.app.sheet.dehighlight_all()
        self.app._apply_row_highlighting()

        unique_rows = {res["row"] for res in self.search_results}
        if unique_rows:
            self.app.sheet.highlight_rows(rows=list(unique_rows), bg='#FFFACD', redraw=False)

        for res in self.search_results:
            self.app.sheet.highlight_cells(row=res["row"], column=res["col"], bg='#FFDAB9', redraw=False)

        self.app.sheet.redraw()

    def _update_current_selection_highlight(self):
        self._highlight_all_matches()
        if self.current_result_index != -1 and self.search_results:
            res = self.search_results[self.current_result_index]
            self.app.sheet.highlight_cells(row=res["row"], column=res["col"], bg='#7CFC00', fg='black', redraw=True)

    def _navigate_to_result(self):
        if not self.search_results:
            return

        res = self.search_results[self.current_result_index]
        self.app.sheet.select_cell(row=res["row"], column=res["col"])
        self.app.sheet.see(row=res["row"], column=res["col"], keep_xscroll=False)
        self.app.on_sheet_select()

        self.results_label.config(
            text=_("Match {current}/{total}").format(current=self.current_result_index + 1,
                                                     total=len(self.search_results))
        )
        self._update_current_selection_highlight()

    def _find_next(self):
        if not self._perform_search() or not self.search_results:
            return

        self.current_result_index = (self.current_result_index + 1) % len(self.search_results)
        self._navigate_to_result()

    def _find_prev(self):
        if not self._perform_search() or not self.search_results:
            return

        self.current_result_index = (self.current_result_index - 1 + len(self.search_results)) % len(
            self.search_results)
        self._navigate_to_result()

    def _replace_current(self):
        if self.current_result_index < 0 or self.current_result_index >= len(self.search_results):
            self._find_next()
            return

        res = self.search_results[self.current_result_index]
        ts_obj = self.app._find_ts_obj_by_id(res["id"])
        if not ts_obj: return

        term = self.search_term_var.get()
        replace_with = self.replace_term_var.get()
        if not term: return

        flags = 0 if self.case_sensitive_var.get() else re.IGNORECASE
        pattern = re.compile(re.escape(term), flags)

        # --- NEW LOGIC: Handle replacement based on column ---
        target_column_index = res["col"]

        if target_column_index == 3:  # Translation column
            current_text = ts_obj.get_translation_for_ui()
            new_text, num_replacements = pattern.subn(replace_with, current_text, count=1)
            if num_replacements > 0:
                self.app._apply_translation_to_model(ts_obj, new_text, source="replace_current")

        elif target_column_index == 4:  # Comment column
            current_text = ts_obj.comment
            new_text, num_replacements = pattern.subn(replace_with, current_text, count=1)
            if num_replacements > 0:
                self.app._apply_comment_to_model(ts_obj, new_text)

        else:  # Original column or other
            messagebox.showinfo(_("Info"), _("Match is not in a replaceable column (Translation or Comment)."),
                                parent=self)
        # --- END OF NEW LOGIC ---

        self._find_next()

    def _replace_all(self):
        if not self._perform_search() or not self.search_results:
            messagebox.showinfo(_("Replace All"), _("No matches found to replace."), parent=self)
            return

        term = self.search_term_var.get()
        replace_with = self.replace_term_var.get()

        # Filter results for replaceable columns (3: Translation, 4: Comment)
        trans_results = [res for res in self.search_results if res["col"] == 3]
        comment_results = [res for res in self.search_results if res["col"] == 4]

        if not trans_results and not comment_results:
            messagebox.showinfo(_("Replace All"), _("No matches found in Translation or Comment columns."), parent=self)
            return

        # Build confirmation message
        msg_parts = []
        if trans_results:
            msg_parts.append(_("{count} in Translation").format(count=len(trans_results)))
        if comment_results:
            msg_parts.append(_("{count} in Comment").format(count=len(comment_results)))

        confirm_msg = _("Are you sure you want to replace all occurrences?\nFound: {details}.").format(
            details=", ".join(msg_parts))
        if not messagebox.askyesno(_("Confirm Replace All"), confirm_msg, parent=self):
            return

        flags = 0 if self.case_sensitive_var.get() else re.IGNORECASE
        pattern = re.compile(re.escape(term), flags)

        bulk_changes = []

        # --- NEW: Process both translation and comment replacements ---
        # Use a set to process each object only once per field type
        processed_ids_trans = set()
        for res in trans_results:
            if res["id"] in processed_ids_trans: continue
            ts_obj = self.app._find_ts_obj_by_id(res["id"])
            if not ts_obj or ts_obj.is_ignored: continue

            old_text = ts_obj.get_translation_for_storage_and_tm()
            new_text = pattern.sub(replace_with, ts_obj.get_translation_for_ui())
            if new_text != ts_obj.get_translation_for_ui():
                ts_obj.set_translation_internal(new_text)
                bulk_changes.append({'string_id': ts_obj.id, 'field': 'translation', 'old_value': old_text,
                                     'new_value': ts_obj.get_translation_for_storage_and_tm()})
            processed_ids_trans.add(res["id"])

        processed_ids_comment = set()
        for res in comment_results:
            if res["id"] in processed_ids_comment: continue
            ts_obj = self.app._find_ts_obj_by_id(res["id"])
            if not ts_obj: continue

            old_text = ts_obj.comment
            new_text = pattern.sub(replace_with, old_text)
            if new_text != old_text:
                ts_obj.comment = new_text
                bulk_changes.append(
                    {'string_id': ts_obj.id, 'field': 'comment', 'old_value': old_text, 'new_value': new_text})
            processed_ids_comment.add(res["id"])
        # --- END OF NEW LOGIC ---

        if bulk_changes:
            self.app.add_to_undo_history('bulk_replace_all', {'changes': bulk_changes})
            self.app.mark_project_modified()
            self.app._run_and_refresh_with_validation()
            messagebox.showinfo(_("Replace All Complete"),
                                _("Changes made to {count} field(s).").format(count=len(bulk_changes)), parent=self)
        else:
            messagebox.showinfo(_("Replace All"), _("No occurrences were replaced."), parent=self)

        self.last_search_options = {}
        self.results_label.config(text=_("Replacement complete."))
        self._clear_all_highlights()