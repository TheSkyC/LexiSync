# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import polib
import os
import datetime
from models.translatable_string import TranslatableString
from services.code_file_service import extract_translatable_strings
from utils.constants import APP_VERSION


def _po_entry_to_translatable_string(entry, full_code_lines=None, original_file_path=None):
    line_num = 0
    char_pos_start = 0

    if hasattr(entry, 'occurrences') and entry.occurrences:
        try:
            path, lnum_str = entry.occurrences[0]
            if lnum_str.isdigit():
                line_num = int(lnum_str)
        except (ValueError, IndexError, TypeError):
            pass

    string_type = "PO Import"

    ts = TranslatableString(
        original_raw=entry.msgid,
        original_semantic=entry.msgid,
        line_num=line_num,
        char_pos_start_in_file=char_pos_start,
        char_pos_end_in_file=char_pos_start + len(entry.msgid),
        full_code_lines=full_code_lines if full_code_lines else [],
        string_type=string_type
    )
    ts.translation = entry.msgstr

    all_comments = []
    if entry.comment:
        all_comments.append(entry.comment)
    if hasattr(entry, 'tcomment') and entry.tcomment:
        all_comments.append(entry.tcomment)

    full_comment = "\n".join(all_comments).strip()

    # --- REVISED is_reviewed LOGIC ---
    # An entry is considered reviewed ONLY if it has our custom reviewed flag.
    # It is considered NOT reviewed if:
    # - It has no translation.
    # - It has a 'fuzzy' flag.
    # - It doesn't have our custom flag.
    if not ts.translation.strip() or 'fuzzy' in entry.flags:
        ts.is_reviewed = False
    elif "# OWLocalizer:reviewed" in full_comment:
        ts.is_reviewed = True
    else:
        ts.is_reviewed = False
    # --- END OF REVISED LOGIC ---

    # Set ignored status based on another custom flag
    if "# OWLocalizer:ignored" in full_comment:
        ts.is_ignored = True

    # Clean up our custom flags from the comment that is shown to the user
    ts.comment = full_comment.replace("# OWLocalizer:reviewed", "").replace("# OWLocalizer:ignored", "").strip()

    return ts


def extract_to_pot(code_content, extraction_patterns, project_name="Untitled Project", app_version_from_app=APP_VERSION,
                   original_file_name="source_code"):
    pot_file = polib.POFile()
    pot_file.metadata = {
        'Project-Id-Version': f'{project_name} {app_version_from_app}',
        'POT-Creation-Date': datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M%z"),
        'MIME-Version': '1.0',
        'Content-Type': 'text/plain; charset=utf-8',
        'Content-Transfer-Encoding': '8bit',
        'Generated-By': f'OverwatchLocalizer {app_version_from_app}',
        'Language': '',
    }

    translatable_objects = extract_translatable_strings(code_content, extraction_patterns)

    for ts_obj in translatable_objects:
        entry = polib.POEntry(
            msgid=ts_obj.original_semantic,
            msgstr='',
            occurrences=[(original_file_name, str(ts_obj.line_num_in_file))],
            comment=ts_obj.comment
        )
        pot_file.append(entry)
    return pot_file


def load_from_po(filepath, original_code_content_for_context=None, original_file_path_for_context=None):
    po_file = polib.pofile(filepath, encoding='utf-8', wrapwidth=0)
    translatable_objects = []
    full_code_lines = []

    if original_code_content_for_context:
        full_code_lines = original_code_content_for_context.splitlines()

    for entry in po_file:
        if entry.obsolete:
            continue

        if entry.msgid == "" and not translatable_objects:
            continue

        ts = _po_entry_to_translatable_string(entry, full_code_lines, original_file_path_for_context)
        translatable_objects.append(ts)

    translatable_objects.sort(
        key=lambda x: (x.line_num_in_file if x.line_num_in_file > 0 else float('inf'), x.original_semantic))

    return translatable_objects, po_file.metadata


def save_to_po(filepath, translatable_objects, metadata=None, original_file_name="source_code"):
    # ... (po_file and metadata setup remains the same) ...
    po_file = polib.POFile(wrapwidth=0)
    # ...

    for ts_obj in translatable_objects:
        if ts_obj.id == "##NEW_ENTRY##":
            continue
        if not ts_obj.original_semantic:
            continue

        # --- REVISED COMMENT AND FLAG HANDLING ---
        entry_comment = ts_obj.comment
        entry_flags = []

        # Handle 'fuzzy' flag
        if not ts_obj.is_reviewed and ts_obj.translation.strip():
            entry_flags.append('fuzzy')

        # Handle our custom flags by adding them to the comment
        if ts_obj.is_reviewed:
            entry_comment = (entry_comment + "\n# OWLocalizer:reviewed").strip()
        if ts_obj.is_ignored:
            entry_comment = (entry_comment + "\n# OWLocalizer:ignored").strip()
        # --- END OF REVISED HANDLING ---

        entry_occurrences = []
        if ts_obj.line_num_in_file > 0:
            entry_occurrences.append((original_file_name, str(ts_obj.line_num_in_file)))

        entry = polib.POEntry(
            msgid=ts_obj.original_semantic,
            msgstr=ts_obj.translation,
            comment=entry_comment,
            occurrences=entry_occurrences,
            flags=entry_flags
        )
        po_file.append(entry)

    po_file.save(filepath)