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
            # Use the first occurrence to get the line number
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

    ts.comment = "\n".join(all_comments).strip()
    ts.is_reviewed = not ('fuzzy' in entry.flags)

    if "# OWLocalizer:ignored" in ts.comment:
        ts.is_ignored = True

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

    # --- REVISED LOADING LOGIC ---
    for entry in po_file:
        # Skip only obsolete entries.
        # We allow entries with empty msgid to be loaded,
        # because the metadata header has an empty msgid, and we want to preserve it.
        # The main app logic will handle how to display/edit them.
        if entry.obsolete:
            continue

        # The first entry with an empty msgid is the header, we skip creating a string for it.
        if entry.msgid == "" and not translatable_objects:
            continue

        ts = _po_entry_to_translatable_string(entry, full_code_lines, original_file_path_for_context)
        translatable_objects.append(ts)
    # --- END OF REVISED LOGIC ---

    translatable_objects.sort(
        key=lambda x: (x.line_num_in_file if x.line_num_in_file > 0 else float('inf'), x.original_semantic))

    return translatable_objects, po_file.metadata


def save_to_po(filepath, translatable_objects, metadata=None, original_file_name="source_code"):
    po_file = polib.POFile(wrapwidth=0)
    if metadata:
        po_file.metadata = metadata
        if 'PO-Revision-Date' not in po_file.metadata or not po_file.metadata['PO-Revision-Date']:
            po_file.metadata['PO-Revision-Date'] = datetime.datetime.now(datetime.timezone.utc).strftime(
                "%Y-%m-%d %H:%M%z")
    else:
        po_file.metadata = {
            'Project-Id-Version': f'Overwatch Project {APP_VERSION}',
            'PO-Revision-Date': datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M%z"),
            'Last-Translator': 'User <user@example.com>',
            'Language-Team': 'LANGUAGE <LL@li.org>',
            'Language': '',
            'MIME-Version': '1.0',
            'Content-Type': 'text/plain; charset=utf-8',
            'Content-Transfer-Encoding': '8bit',
            'Generated-By': f'OverwatchLocalizer {APP_VERSION}'
        }

    for ts_obj in translatable_objects:
        # Skip creating entries for special internal objects like the "NEW" row
        if ts_obj.id == "##NEW_ENTRY##":
            continue

        entry_occurrences = []
        if ts_obj.line_num_in_file > 0:
            entry_occurrences.append((original_file_name, str(ts_obj.line_num_in_file)))

        entry_comment_parts = []
        if ts_obj.comment:
            regular_comments = []
            custom_flags = []
            for line in ts_obj.comment.splitlines():
                if line.startswith("# OWLocalizer:"):
                    custom_flags.append(line)
                else:
                    regular_comments.append(line)

            if regular_comments:
                entry_comment_parts.append("\n".join(regular_comments))
            if custom_flags:
                entry_comment_parts.extend(custom_flags)

        entry = polib.POEntry(
            msgid=ts_obj.original_semantic,
            msgstr=ts_obj.translation,
            comment="\n".join(entry_comment_parts).strip() if entry_comment_parts else "",
            occurrences=entry_occurrences,
            flags=[]
        )
        if not ts_obj.is_reviewed and ts_obj.translation.strip():
            entry.flags.append('fuzzy')

        if ts_obj.is_ignored:
            if "# OWLocalizer:ignored" not in entry.comment:
                entry.comment = (entry.comment + "\n# OWLocalizer:ignored").strip()
        else:
            if entry.comment:
                entry.comment = entry.comment.replace("# OWLocalizer:ignored", "").strip()

        po_file.append(entry)
    po_file.save(filepath)