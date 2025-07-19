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
    source_path = ""
    try:
        if hasattr(entry, 'occurrences') and entry.occurrences:
            first_occurrence = entry.occurrences[0]

            if isinstance(first_occurrence, (tuple, list)) and len(first_occurrence) >= 2:
                source_path = first_occurrence[0] or ""
                lnum_str = first_occurrence[1] or ""
                if lnum_str and str(lnum_str).isdigit():
                    line_num = int(lnum_str)
            elif isinstance(first_occurrence, str):
                source_path = first_occurrence
    except Exception as e:
        print(f"    Occurrences value was: {getattr(entry, 'occurrences', 'N/A')}")

    ts = TranslatableString(
        original_raw=entry.msgid,
        original_semantic=entry.msgid,
        line_num=line_num,
        char_pos_start_in_file=0,
        char_pos_end_in_file=len(entry.msgid),
        full_code_lines=full_code_lines if full_code_lines else [],
        string_type="PO Import",
        occurrences=entry.occurrences if hasattr(entry, 'occurrences') else []
    )
    ts.translation = entry.msgstr or ""

    all_comment_lines = []
    if entry.comment:
        all_comment_lines.extend(entry.comment.splitlines())
    if entry.tcomment:
        all_comment_lines.extend(entry.tcomment.splitlines())

    user_comment_lines = []
    po_meta_comment_lines = []

    for line in all_comment_lines:
        stripped_line = line.strip()
        if stripped_line.startswith('#.'):
            content = stripped_line[2:].strip()
            if content.startswith('OWLocalizer:'):
                if 'reviewed' in content:
                    ts.is_reviewed = True
                if 'ignored' in content:
                    ts.is_ignored = True
            else:
                user_comment_lines.append(content)
        elif stripped_line.startswith('#'):
            po_meta_comment_lines.append(stripped_line)
        else:
            user_comment_lines.append(line)

    if hasattr(entry, 'occurrences') and entry.occurrences:
        po_meta_comment_lines.append(
            f"#: {' '.join(f'{p}:{l}' for p, l in entry.occurrences if p is not None and l is not None)}")

    flags = getattr(entry, 'flags', [])
    if flags:
        po_meta_comment_lines.append(f"#, {', '.join(flags)}")

    previous_msgid = getattr(entry, 'previous_msgid', None)
    if previous_msgid:
        previous_entries = previous_msgid if isinstance(previous_msgid, list) else [previous_msgid]
        for p_msgid in previous_entries:
            po_meta_comment_lines.append(f"#| msgid \"{p_msgid}\"")

    ts.comment = "\n".join(user_comment_lines)
    ts.po_comment = "\n".join(sorted(list(set(po_meta_comment_lines))))

    if 'fuzzy' in flags:
        ts.is_fuzzy = True

    return ts


def _find_project_root(po_filepath: str) -> str | None:
    current_path = os.path.dirname(po_filepath)
    while True:
        if "locales" in os.listdir(current_path):
            return current_path

        parent_path = os.path.dirname(current_path)
        if parent_path == current_path:  # 到达文件系统根目录
            return None
        current_path = parent_path

def extract_to_pot(code_content, extraction_patterns, project_name="Untitled Project", app_version_from_app=APP_VERSION,
                   original_file_name="source_code"):
    pot_file = polib.POFile(wrapwidth=0)
    pot_file.metadata = {
        'Project-Id-Version': f'{project_name} {app_version_from_app}',
        'Report-Msgid-Bugs-To': '',
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
            msgstr='',
            occurrences=[(original_file_name, str(ts_obj.line_num_in_file))],
            comment=ts_obj.comment
        )
        pot_file.append(entry)
    return pot_file


def load_from_po(filepath):
    po_file = polib.pofile(filepath, encoding='utf-8', wrapwidth=0)
    translatable_objects = []
    project_root = _find_project_root(filepath)
    file_content_cache = {}
    for entry in po_file:
        if entry.obsolete or (entry.msgid == "" and not translatable_objects):
            continue

        full_code_lines = []
        if project_root and entry.occurrences:
            try:
                relative_path = entry.occurrences[0][0]
                normalized_rel_path = os.path.normpath(relative_path)
                full_source_path = os.path.join(project_root, normalized_rel_path)

                if full_source_path in file_content_cache:
                    full_code_lines = file_content_cache[full_source_path]
                elif os.path.exists(full_source_path):
                    with open(full_source_path, 'r', encoding='utf-8', errors='replace') as f:
                        lines = f.read().splitlines()
                        file_content_cache[full_source_path] = lines
                        full_code_lines = lines
            except Exception as e:
                print(f"Warning: Could not load context file for entry '{entry.msgid[:20]}...': {e}")

        ts = _po_entry_to_translatable_string(entry, full_code_lines)
        translatable_objects.append(ts)

    po_lang = po_file.metadata.get('Language', None)
    return translatable_objects, po_file.metadata, po_lang


def save_to_po(filepath, translatable_objects, metadata=None, original_file_name="source_code", app_instance=None):
    po_file = polib.POFile(wrapwidth=0)
    if metadata:
        po_file.metadata = metadata
    if app_instance and app_instance.target_language:
        po_file.metadata['Language'] = app_instance.target_language
    po_file.metadata['PO-Revision-Date'] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M%z")
    po_file.metadata['Content-Type'] = 'text/plain; charset=utf-8'
    po_file.metadata['Content-Transfer-Encoding'] = '8bit'
    for ts_obj in translatable_objects:
        if not ts_obj.original_semantic or ts_obj.id == "##NEW_ENTRY##":
            continue
        if ts_obj.is_reviewed or ts_obj.is_warning_ignored:
            ts_obj.is_fuzzy = False
        entry_flags = []
        if ts_obj.is_fuzzy:
            entry_flags.append('fuzzy')

        po_comment_lines = ts_obj.po_comment.splitlines()
        flags_line = next((line for line in po_comment_lines if line.strip().startswith('#,')), None)
        if flags_line:
            flags_str = flags_line.replace('#,', '').strip()
            entry_flags.extend([f.strip() for f in flags_str.split(',') if f.strip()])

        entry_flags = sorted(list(set(entry_flags)))
        if ts_obj.is_reviewed or ts_obj.is_warning_ignored:
            if 'fuzzy' in entry_flags:
                entry_flags.remove('fuzzy')
        entry_occurrences = ts_obj.occurrences
        if not entry_occurrences and ts_obj.line_num_in_file > 0:
            entry_occurrences = [(original_file_name, str(ts_obj.line_num_in_file))]
        user_comment_lines = ts_obj.comment.splitlines()
        if ts_obj.is_reviewed:
            user_comment_lines.append("#OWLocalizer:reviewed")
        if ts_obj.is_ignored:
            user_comment_lines.append("#OWLocalizer:ignored")
        translator_comment = "\n".join(user_comment_lines)
        po_comment_lines = ts_obj.po_comment.splitlines()
        developer_comment_lines = [
            line for line in po_comment_lines
            if not line.strip().startswith(('#:', '#,', '#|'))
        ]
        developer_comment = "\n".join(developer_comment_lines)
        entry = polib.POEntry(
            msgid=ts_obj.original_semantic,
            msgstr=ts_obj.translation,
            tcomment=translator_comment,
            comment=developer_comment,
            occurrences=entry_occurrences,
            flags=entry_flags
        )
        po_file.append(entry)
    try:
        po_file.save(filepath)
    except Exception as e:
        print(f"Error saving PO file to {filepath}: {e}")
        raise e