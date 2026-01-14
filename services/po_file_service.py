# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0
import polib
import os
import datetime
from pathlib import Path
import uuid
from models.translatable_string import TranslatableString
from services.code_file_service import extract_translatable_strings
from utils.constants import APP_VERSION, APP_NAMESPACE_UUID
from utils.localization import _
import logging
logger = logging.getLogger(__name__)


def po_entry_to_translatable_string(entry, po_file_rel_path, full_code_lines=None):
    # [CRITICAL ARCHITECTURE NOTE]
    # We MUST force the 'occurrences' to point to the PO file itself (e.g., 'source/zh.po'),
    # ignoring the actual occurrences listed inside the PO entry (e.g., '#: main.py:123').
    #
    # Reason:
    # In LexiSync's Project Mode, the "Active File" switching logic relies on exact path matching.
    # It filters the global string list using: ts.source_file_path == active_file_project_path.
    #
    # If we use entry.occurrences, the source_file_path becomes 'main.py', which does NOT match
    # the project file path 'source/zh.po', causing the view to be empty.
    #
    # The original occurrences are preserved in 'po_comment' for reference, but for
    # internal logic, the "source" of this string is the PO file.
    line_num = entry.linenum
    msgctxt = entry.msgctxt or ""
    msgid = entry.msgid
    msgstr = entry.msgstr or ""
    occurrences = [(po_file_rel_path, str(line_num))]

    # 生成 UUID
    stable_name_for_uuid = f"{po_file_rel_path}::{msgctxt}::{msgid}"

    ts = TranslatableString(
        original_raw=msgid,
        original_semantic=msgid,
        line_num=line_num,
        char_pos_start_in_file=0,
        char_pos_end_in_file=0,
        full_code_lines=full_code_lines or [],
        string_type="PO Import",
        source_file_path=po_file_rel_path,
        occurrences=occurrences,
        occurrence_index=0
    )

    ts.id = str(uuid.uuid5(APP_NAMESPACE_UUID, stable_name_for_uuid))
    ts.translation = msgstr

    if msgctxt:
        ts.context = msgctxt

    user_comment_lines = []
    po_meta_comment_lines = []

    # 1. 处理提取注释 (Extracted Comments, #.)
    if entry.tcomment:
        # 优化：避免重复 splitlines，直接在迭代中处理
        for line in entry.tcomment.splitlines():
            po_meta_comment_lines.append(f"#. {line}")

    # 2. 处理翻译注释 (Translator Comments, #)
    if entry.comment:
        for line in entry.comment.splitlines():
            stripped = line.strip()
            # 识别 LexiSync 的特殊标记
            if stripped.startswith('LexiSync:'):
                lower_stripped = stripped.lower()  # 只转换一次
                if 'reviewed' in lower_stripped:
                    ts.is_reviewed = True
                if 'ignored' in lower_stripped:
                    ts.is_ignored = True
            else:
                user_comment_lines.append(line)

    # 3. 处理引用 (References, #:)
    entry_occurrences = getattr(entry, 'occurrences', None)
    if entry_occurrences:
        refs = ' '.join(f"{p}:{l}" if l else p for p, l in entry_occurrences)
        po_meta_comment_lines.append(f"#: {refs}")

    # 4. 处理标志 (Flags, #,)
    flags = getattr(entry, 'flags', [])
    if flags:
        po_meta_comment_lines.append(f"#, {', '.join(flags)}")
        # 优化：在这里检查 fuzzy，避免后面再次检查
        if 'fuzzy' in flags:
            ts.is_fuzzy = True

    # 5. 处理旧翻译 (Previous, #|)
    previous_msgid = getattr(entry, 'previous_msgid', None)
    if previous_msgid:
        po_meta_comment_lines.append(f'#| msgid "{previous_msgid}"')

    ts.comment = "\n".join(user_comment_lines) if user_comment_lines else ""
    ts.po_comment = "\n".join(po_meta_comment_lines) if po_meta_comment_lines else ""

    ts.update_sort_weight()
    return ts


def _find_project_root(po_filepath: str) -> str | None:
    current_path = Path(po_filepath).parent
    while True:
        if (current_path / "project.json").is_file():
            return str(current_path)

        if current_path.parent == current_path:
            return None
        current_path = current_path.parent

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
        'Generated-By': f'LexiSync {app_version_from_app}',
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
    logger.debug(f"[load_from_po] Starting to load PO file: {filepath}")
    po_file = polib.pofile(filepath, encoding='utf-8', wrapwidth=0)
    translatable_objects = []
    project_root = _find_project_root(filepath)
    file_content_cache = {}
    path_exists_cache = {}

    def cached_is_file(path_str):
        if path_str not in path_exists_cache:
            path_exists_cache[path_str] = os.path.isfile(path_str)
        return path_exists_cache[path_str]

    po_file_rel_path = ""
    if project_root:
        try:
            po_file_rel_path = Path(filepath).relative_to(project_root).as_posix()
        except ValueError:
            po_file_rel_path = os.path.basename(filepath)
    else:
        po_file_rel_path = os.path.basename(filepath)
    logger.debug(f"[load_from_po] Determined relative path for this PO file: {po_file_rel_path}")

    for entry in po_file:
        if entry.obsolete or (entry.msgid == "" and not translatable_objects):
            continue

        full_code_lines = []
        if entry.occurrences:
            source_path_to_read = None
            try:
                relative_path = entry.occurrences[0][0]
                normalized_rel_path = os.path.normpath(relative_path)

                if project_root:
                    candidate = os.path.join(project_root, normalized_rel_path)
                    if cached_is_file(candidate):
                        source_path_to_read = candidate
                else:
                    current_search_dir = Path(filepath).parent
                    for _ in range(6):
                        candidate = current_search_dir / normalized_rel_path
                        candidate_str = str(candidate)
                        if cached_is_file(candidate_str):
                            source_path_to_read = candidate_str
                            break
                        if current_search_dir.parent == current_search_dir:
                            break
                        current_search_dir = current_search_dir.parent

                if source_path_to_read:
                    if source_path_to_read in file_content_cache:
                        full_code_lines = file_content_cache[source_path_to_read]
                    else:
                        with open(source_path_to_read, 'r', encoding='utf-8', errors='replace') as f:
                            lines = f.read().splitlines()
                            file_content_cache[source_path_to_read] = lines
                            full_code_lines = lines
            except Exception as e:
                logger.warning(f"Warning: Could not load context file for entry '{entry.msgid[:20]}...': {e}")

        ts = po_entry_to_translatable_string(entry, po_file_rel_path, full_code_lines)

        translatable_objects.append(ts)

    po_lang = po_file.metadata.get('Language', None)
    logger.debug(f"[load_from_po] Finished loading. Found {len(translatable_objects)} entries.")
    return translatable_objects, po_file.metadata, po_lang


def save_to_po(filepath, translatable_objects, metadata=None, original_file_name="source_code", app_instance=None):
    po_file = polib.POFile(wrapwidth=78)
    if metadata:
        po_file.metadata = metadata
    else:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M%z")
        po_file.metadata = {
            'Project-Id-Version': f'LexiSync {APP_VERSION}',
            'Report-Msgid-Bugs-To': '',
            'POT-Creation-Date': now,
            'PO-Revision-Date': now,
            'Last-Translator': 'LexiSync User',
            'Language-Team': '',
            'MIME-Version': '1.0',
            'Content-Type': 'text/plain; charset=UTF-8',
            'Content-Transfer-Encoding': '8bit',
            'X-Generator': f'LexiSync {APP_VERSION}'
        }

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
            existing_flags = [f.strip() for f in flags_str.split(',') if f.strip()]
            for f in existing_flags:
                if f not in entry_flags and f != 'fuzzy':
                    entry_flags.append(f)

        entry_flags = sorted(list(set(entry_flags)))

        entry_occurrences = []
        location_lines = [line for line in po_comment_lines if line.strip().startswith('#:')]
        for line in location_lines:
            content = line.replace('#:', '').strip()
            parts = content.split()
            for part in parts:
                if ':' in part:
                    try:
                        fpath, lineno = part.rsplit(':', 1)
                        entry_occurrences.append((fpath, lineno))
                    except ValueError:
                        pass
        if not entry_occurrences and ts_obj.line_num_in_file > 0 and ts_obj.string_type != "PO Import":
            entry_occurrences = [(original_file_name, str(ts_obj.line_num_in_file))]

        # 提取 extracted comments (#.)
        extracted_comments = []
        for line in po_comment_lines:
            if line.strip().startswith('#.'):
                clean_line = line.strip()[2:].strip()
                extracted_comments.append(clean_line)

        tcomment_str = "\n".join(extracted_comments) if extracted_comments else None

        # 构造 translator comments (#)
        user_comment_lines = ts_obj.comment.splitlines()
        if ts_obj.is_reviewed:
            user_comment_lines.append("#LexiSync:reviewed")
        if ts_obj.is_ignored:
            user_comment_lines.append("#LexiSync:ignored")

        translator_comment = "\n".join(user_comment_lines)

        entry = polib.POEntry(
            msgid=ts_obj.original_semantic,
            msgstr=ts_obj.translation,
            msgctxt=ts_obj.context if ts_obj.context else None,
            tcomment=tcomment_str,
            comment=translator_comment,
            occurrences=entry_occurrences,
            flags=entry_flags
        )
        po_file.append(entry)

    try:
        po_file.save(filepath)
    except Exception as e:
        logger.error(f"Error saving PO file to {filepath}: {e}")
        raise e