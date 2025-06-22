# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import polib
import os
import datetime
from models.translatable_string import TranslatableString
from services.code_file_service import extract_translatable_strings
from utils.constants import APP_VERSION
from utils.localization import _


def _po_entry_to_translatable_string(entry, full_code_lines=None, original_file_path=None):
    line_num = 0
    if hasattr(entry, 'occurrences') and entry.occurrences:
        try:
            # occurrences is a list of (filename, line_number) tuples
            # We take the first one for line number context
            _path, lnum_str = entry.occurrences[0]
            if lnum_str.isdigit():
                line_num = int(lnum_str)
        except (ValueError, IndexError, TypeError):
            pass

    ts = TranslatableString(
        original_raw=entry.msgid,
        original_semantic=entry.msgid,
        line_num=line_num,
        char_pos_start_in_file=0, # PO entries don't have char positions
        char_pos_end_in_file=len(entry.msgid), # Approximate end position
        full_code_lines=full_code_lines if full_code_lines else [],
        string_type="PO Import"
    )
    ts.translation = entry.msgstr

    source_comments = []
    if entry.occurrences:
        # Format occurrences for display
        source_comments.append(f"#: {' '.join(f'{p}:{l}' for p, l in entry.occurrences)}")
    if entry.tcomment: # Translator comments
        source_comments.append(f"#. {entry.tcomment}")
    if entry.comment: # Extracted comments (developer comments)
        source_comments.append(f"# {entry.comment}")
    if entry.flags:
        source_comments.append(f"#, {', '.join(entry.flags)}")
    if entry.previous_msgid: # Obsolete entries' previous msgid
        previous_entries = entry.previous_msgid if isinstance(entry.previous_msgid, list) else [entry.previous_msgid]
        for p_msgid in previous_entries:
            source_comments.append(f"#| msgid \"{p_msgid}\"")

    ts.source_comment = "\n".join(source_comments)
    ts.comment = entry.comment or "" # Use the developer comment as the primary comment field

    if 'fuzzy' in entry.flags:
        ts.minor_warnings.append(_("Translation is marked as fuzzy and needs review."))

    # Determine reviewed status
    if not ts.translation.strip() or 'fuzzy' in entry.flags:
        ts.is_reviewed = False
    elif "# OWLocalizer:reviewed" in ts.source_comment: # Custom flag for reviewed
        ts.is_reviewed = True
    else:
        ts.is_reviewed = False # Default to unreviewed if no translation or fuzzy, or no explicit flag

    # Determine ignored status
    if "# OWLocalizer:ignored" in ts.source_comment: # Custom flag for ignored
        ts.is_ignored = True
        ts.was_auto_ignored = False # Not auto-ignored if explicitly marked

    return ts


def extract_to_pot(code_content, extraction_patterns, project_name="Untitled Project", app_version_from_app=APP_VERSION,
                   original_file_name="source_code"):
    pot_file = polib.POFile(wrapwidth=0) # wrapwidth=0 to prevent line wrapping
    pot_file.metadata = {
        'Project-Id-Version': f'{project_name} {app_version_from_app}',
        'Report-Msgid-Bugs-To': '', # Can be customized
        'POT-Creation-Date': datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M%z"),
        'MIME-Version': '1.0',
        'Content-Type': 'text/plain; charset=utf-8',
        'Content-Transfer-Encoding': '8bit',
        'Generated-By': f'OverwatchLocalizer {app_version_from_app}',
    }
    translatable_objects = extract_translatable_strings(code_content, extraction_patterns)
    for ts_obj in translatable_objects:
        entry = polib.POEntry(
            msgid=ts_obj.original_semantic,
            msgstr='', # POT files have empty msgstr
            occurrences=[(original_file_name, str(ts_obj.line_num_in_file))],
            comment=ts_obj.comment # Use the comment field for developer comments
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
        if entry.msgid == "" and not translatable_objects: # Skip the empty msgid for metadata if it's the first entry
            continue
        ts = _po_entry_to_translatable_string(entry, full_code_lines, original_file_path_for_context)
        translatable_objects.append(ts)

    # Sort by line number for better display, but handle cases where line_num is 0 (e.g., new entries or unassociated)
    translatable_objects.sort(
        key=lambda x: (x.line_num_in_file if x.line_num_in_file > 0 else float('inf'), x.original_semantic))
    return translatable_objects, po_file.metadata


def save_to_po(filepath, translatable_objects, metadata=None, original_file_name="source_code"):
    po_file = polib.POFile(wrapwidth=0)
    if metadata:
        po_file.metadata = metadata
    # Update revision date
    po_file.metadata['PO-Revision-Date'] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M%z")
    # Ensure Content-Type and Content-Transfer-Encoding are set for PO files
    po_file.metadata['Content-Type'] = 'text/plain; charset=utf-8'
    po_file.metadata['Content-Transfer-Encoding'] = '8bit'

    for ts_obj in translatable_objects:
        if ts_obj.id == "##NEW_ENTRY##" or not ts_obj.original_semantic: # Skip the special new entry
            continue

        entry_flags = []
        if not ts_obj.is_reviewed and ts_obj.translation.strip():
            entry_flags.append('fuzzy')

        # Combine comments for PO file
        translator_comment_lines = []
        if ts_obj.comment:
            translator_comment_lines.append(ts_obj.comment)

        # Add custom OWLocalizer flags as comments
        if ts_obj.is_reviewed:
            translator_comment_lines.append("# OWLocalizer:reviewed")
        if ts_obj.is_ignored:
            translator_comment_lines.append("# OWLocalizer:ignored")

        # The 'comment' field in POEntry is for extracted comments (developer comments),
        # while 'tcomment' is for translator comments.
        # We'll put our combined comments into 'tcomment' for clarity.
        # The original 'comment' from extraction should ideally go into 'comment'.
        # For simplicity, if ts_obj.comment is user-edited, we'll treat it as translator comment.
        # If it was from extraction, it would be in ts_obj.source_comment (which is not saved back directly).

        # Let's refine: if ts_obj.comment is not empty, it's a translator comment.
        # If ts_obj.source_comment contains original PO comments, we should try to preserve them.
        # This requires a more complex mapping. For now, let's assume ts_obj.comment is the primary user-facing comment.

        # For simplicity, let's put all user-generated comments and internal flags into tcomment.
        # The original extracted comment (if any) would have been part of ts_obj.source_comment
        # but is not directly stored in ts_obj.comment for round-tripping.
        # This is a limitation if you want to preserve original developer comments separately from translator comments.

        # A better approach for round-tripping PO files would be to store original POEntry fields
        # within TranslatableString, but that complicates the model.
        # For now, we'll just use ts_obj.comment as the translator comment.

        entry_occurrences = []
        if ts_obj.line_num_in_file > 0:
            entry_occurrences.append((original_file_name, str(ts_obj.line_num_in_file)))

        entry = polib.POEntry(
            msgid=ts_obj.original_semantic,
            msgstr=ts_obj.translation,
            tcomment="\n".join(translator_comment_lines) if translator_comment_lines else "", # Translator comments
            occurrences=entry_occurrences,
            flags=entry_flags
        )

        po_file.append(entry)

    po_file.save(filepath)