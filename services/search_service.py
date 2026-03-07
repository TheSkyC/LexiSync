# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import re

from PySide6.QtCore import QObject, Signal


class SearchService(QObject):
    highlights_changed = Signal()
    navigate_to = Signal(int, int)  # proxy_row, col

    def __init__(self, app_instance):
        super().__init__()
        self.app = app_instance

        # State
        self.search_results = []
        self.current_result_index = -1
        self.highlight_indices = set()
        self.current_focus_index = None

        # Persistent State
        self.last_term = ""
        self.last_replace_term = ""
        self.last_options = {"case": False, "in_orig": True, "in_trans": True, "in_comment": True}
        self._load_state_from_config()

    def clear(self):
        self.search_results.clear()
        self.highlight_indices.clear()
        self.current_result_index = -1
        self.current_focus_index = None
        self.highlights_changed.emit()

        if hasattr(self.app, "clear_search_markers"):
            self.app.clear_search_markers()

    def _load_state_from_config(self):
        ui_state = self.app.config.get("ui_state", {})
        search_state = ui_state.get("search_dialog", {})

        self.last_term = search_state.get("term", "")
        self.last_replace_term = search_state.get("replace_term", "")
        saved_options = search_state.get("options", {})

        self.last_options.update(saved_options)

    def _save_state_to_config(self):
        if "ui_state" not in self.app.config:
            self.app.config["ui_state"] = {}

        self.app.config["ui_state"]["search_dialog"] = {
            "term": self.last_term,
            "replace_term": self.last_replace_term,
            "options": self.last_options,
        }

    def perform_search(self, term, options):
        """
        Executes the search logic.
        options: dict with keys 'case', 'in_orig', 'in_trans', 'in_comment'
        Returns: int (count of matches)
        """
        if not term:
            self.clear()
            return 0

        self.last_term = term
        self._save_state_to_config()

        current_options_signature = options.copy()
        current_options_signature["term"] = term

        if self.last_options == current_options_signature and self.search_results:
            return len(self.search_results)

        # Reset
        self.search_results.clear()
        self.highlight_indices.clear()
        self.current_focus_index = None
        self.current_result_index = -1

        flags = 0 if options.get("case") else re.IGNORECASE
        try:
            pattern = re.compile(re.escape(term), flags)
        except re.error:
            return 0

        model = self.app.sheet_model

        for row in range(model.rowCount()):
            ts_obj = model.get_ts_object_by_visual_row(row)
            if not ts_obj:
                continue

            # --- 检查原文列 (Column 2) ---
            if options.get("in_orig") and (
                pattern.search(ts_obj.original_semantic)
                or (ts_obj.is_plural and pattern.search(ts_obj.original_plural))
            ):
                self._add_match(row, 2, ts_obj)

            # --- 检查译文列 (Column 3) ---
            if options.get("in_trans"):
                if ts_obj.is_plural:
                    if any(pattern.search(v) for v in ts_obj.plural_translations.values()):
                        self._add_match(row, 3, ts_obj)
                elif pattern.search(ts_obj.get_translation_for_ui()):
                    self._add_match(row, 3, ts_obj)

            # --- 检查注释列 (Column 4) ---
            if options.get("in_comment") and pattern.search(ts_obj.comment):
                self._add_match(row, 4, ts_obj)

        self.last_options = current_options_signature
        self.highlights_changed.emit()

        # Update MarkerBar
        if hasattr(self.app, "update_search_markers"):
            source_rows = []
            for res in self.search_results:
                ts_obj = res["obj"]
                raw_row = model.get_raw_index_by_id(ts_obj.id)
                if raw_row is not None:
                    source_rows.append(raw_row)

            self.app.update_search_markers(source_rows)

        return len(self.search_results)

    def _add_match(self, row, col, obj):
        self.search_results.append({"proxy_row": row, "col": col, "obj": obj})
        self.highlight_indices.add((row, col))

    def find_next(self):
        return self._navigate(1)

    def find_prev(self):
        return self._navigate(-1)

    def _navigate(self, direction):
        if not self.search_results:
            return -1, -1

        if self.current_result_index == -1:
            # Start from current selection if possible
            current_selection = self.app.table_view.selectionModel().currentIndex()
            start_row = current_selection.row() if current_selection.isValid() else -1

            if direction > 0:
                # Find first result after start_row
                for i, res in enumerate(self.search_results):
                    if res["proxy_row"] >= start_row:
                        if res["proxy_row"] > start_row:
                            self.current_result_index = i - 1
                        else:
                            self.current_result_index = i
                        break
                else:
                    self.current_result_index = -1  # Wrap around to 0 next step
            else:
                # Find last result before start_row
                for i in range(len(self.search_results) - 1, -1, -1):
                    if self.search_results[i]["proxy_row"] <= start_row:
                        if self.search_results[i]["proxy_row"] < start_row:
                            self.current_result_index = i + 1
                        else:
                            self.current_result_index = i
                        break
                else:
                    self.current_result_index = len(self.search_results)  # Wrap around

        # Advance index
        self.current_result_index = (self.current_result_index + direction) % len(self.search_results)

        res = self.search_results[self.current_result_index]
        self.current_focus_index = (res["proxy_row"], res["col"])
        self.highlights_changed.emit()
        self.navigate_to.emit(res["proxy_row"], res["col"])

        return self.current_result_index + 1, len(self.search_results)

    def set_replace_term(self, term):
        self.last_replace_term = term
        self._save_state_to_config()

    def replace_current(self, replace_with):
        if self.current_result_index == -1 or not self.search_results:
            return False

        res = self.search_results[self.current_result_index]
        ts_obj = res["obj"]
        col = res["col"]
        term = self.last_options.get("term", "")
        flags = 0 if self.last_options.get("case") else re.IGNORECASE
        pattern = re.compile(re.escape(term), flags)

        p_idx = 0
        if hasattr(self.app, "details_panel") and self.app.current_selected_ts_id == ts_obj.id:
            p_idx = getattr(self.app.details_panel, "current_plural_index", 0)

        success = False
        if col == 3:  # Translation
            current_text = ts_obj.plural_translations.get(p_idx, "") if ts_obj.is_plural else ts_obj.translation
            new_text, num = pattern.subn(replace_with, current_text, count=1)
            if num > 0:
                self.app._apply_translation_to_model(ts_obj, new_text, source="replace_current", plural_index=p_idx)
                success = True
        elif col == 4:  # Comment
            current_text = ts_obj.comment
            new_text, num = pattern.subn(replace_with, current_text, count=1)
            if num > 0:
                self.app._apply_comment_to_model(ts_obj, new_text)
                success = True

        if success:
            self.last_options = {}
        return success

    def replace_all(self, replace_with):
        if not self.search_results:
            return 0

        term = self.last_options.get("term", "")
        flags = 0 if self.last_options.get("case") else re.IGNORECASE
        pattern = re.compile(re.escape(term), flags)

        trans_results = [res for res in self.search_results if res["col"] == 3]
        comment_results = [res for res in self.search_results if res["col"] == 4]

        bulk_changes = []
        modified_ids = set()

        # Process Translations
        for res in trans_results:
            ts_obj = res["obj"]
            if ts_obj.id in modified_ids:
                continue

            indices = ts_obj.plural_translations.keys() if ts_obj.is_plural else [0]
            item_modified = False
            for p_idx in indices:
                current_text = ts_obj.plural_translations.get(p_idx, "") if ts_obj.is_plural else ts_obj.translation
                new_text, count = pattern.subn(replace_with, current_text)

                if count > 0:
                    old_val = current_text.replace("\n", "\\n")
                    ts_obj.set_translation_internal(new_text, plural_index=p_idx)
                    bulk_changes.append(
                        {
                            "string_id": ts_obj.id,
                            "field": "translation",
                            "old_value": old_val,
                            "new_value": ts_obj.get_translation_for_storage_and_tm(),
                            "plural_index": p_idx,
                        }
                    )
                    item_modified = True
            if item_modified:
                modified_ids.add(ts_obj.id)

        # Process Comments
        for res in comment_results:
            ts_obj = res["obj"]
            if ts_obj.id in modified_ids:
                continue

            current_text = ts_obj.comment
            new_text = pattern.sub(replace_with, current_text)

            if new_text != current_text:
                old_val = ts_obj.comment
                ts_obj.comment = new_text
                bulk_changes.append(
                    {"string_id": ts_obj.id, "field": "comment", "old_value": old_val, "new_value": new_text}
                )
                modified_ids.add(ts_obj.id)

        if bulk_changes:
            self.app.add_to_undo_history("bulk_replace_all", {"changes": bulk_changes})
            self.app.mark_modified()
            self.app.force_full_refresh(id_to_reselect=self.app.current_selected_ts_id)

            self.clear()

        return len(modified_ids)
