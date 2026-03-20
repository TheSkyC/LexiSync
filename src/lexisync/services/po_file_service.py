# Copyright (c) 2025-2026, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import datetime
import logging
import os
from pathlib import Path
import re

import polib
import xxhash

from lexisync.models.translatable_string import TranslatableString
from lexisync.services.code_file_service import extract_translatable_strings
from lexisync.utils.constants import APP_VERSION

logger = logging.getLogger(__name__)


def po_entry_to_translatable_string(
    entry,
    po_file_rel_path,
    full_code_lines=None,
    occurrence_index=0,
    nplurals_from_file=None,
    plural_expr_from_file=None,
):
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
    po_line_num = entry.linenum
    source_line_num = 0
    if entry.occurrences:
        try:
            ref_lineno = entry.occurrences[0][1]
            if ref_lineno and str(ref_lineno).strip():
                source_line_num = int(ref_lineno)
        except (ValueError, IndexError, TypeError):
            pass

    context_slice_line_num = source_line_num if source_line_num > 0 else po_line_num

    is_obsolete = getattr(entry, "obsolete", False)
    msgctxt = entry.msgctxt or ""
    msgid = entry.msgid

    # 复数处理
    is_plural = bool(entry.msgid_plural)
    msgid_plural = entry.msgid_plural if is_plural else ""

    plural_translations = {}
    if is_plural:
        if entry.msgstr_plural:
            for key, val in entry.msgstr_plural.items():
                plural_translations[int(key)] = val

        if nplurals_from_file:
            for i in range(nplurals_from_file):
                if i not in plural_translations:
                    plural_translations[i] = ""
    else:
        plural_translations[0] = entry.msgstr or ""

    occurrences = [(po_file_rel_path, str(po_line_num))]

    # 生成 UUID
    context_key = msgctxt if msgctxt else "NO_CTX"
    stable_name_for_uuid = f"{po_file_rel_path}::{context_key}::{msgid}::{occurrence_index}"
    obj_id = xxhash.xxh128(stable_name_for_uuid.encode("utf-8")).hexdigest()

    ts = TranslatableString(
        original_raw=msgid,
        original_semantic=msgid,
        line_num=context_slice_line_num,
        char_pos_start_in_file=0,
        char_pos_end_in_file=0,
        full_code_lines=full_code_lines or [],
        string_type="PO Obsolete" if is_obsolete else "PO Import",
        source_file_path=po_file_rel_path,
        occurrences=occurrences,
        occurrence_index=occurrence_index,
        id=obj_id,
    )

    ts.is_plural = is_plural
    ts.original_plural = msgid_plural
    ts.plural_translations = plural_translations
    ts.plural_expr = plural_expr_from_file
    ts.is_obsolete = is_obsolete
    if is_obsolete:
        ts.is_ignored = True
    ts.update_search_cache()
    ts.update_sort_weight()

    # 默认显示 index 0
    ts.translation = plural_translations.get(0, "")
    ts._display_translation = ts.translation.replace("\n", "↵")

    if msgctxt:
        ts.context = msgctxt

    user_comment_lines = []
    po_meta_comment_lines = []

    # 1. 处理提取注释 (Extracted Comments, #.)
    if entry.tcomment:
        for line in entry.tcomment.splitlines():
            po_meta_comment_lines.append(f"#. {line}")

    # 2. 处理翻译注释 (Translator Comments, #)
    if entry.comment:
        for line in entry.comment.splitlines():
            stripped = line.strip()
            # 识别 LexiSync 的标记
            if stripped.startswith("LexiSync:"):
                lower_stripped = stripped.lower()
                if "reviewed" in lower_stripped:
                    ts.is_reviewed = True
                if "ignored" in lower_stripped:
                    ts.is_ignored = True
            else:
                user_comment_lines.append(line)

    # 3. 处理引用 (References, #:)
    entry_occurrences = getattr(entry, "occurrences", None)
    if entry_occurrences:
        refs = " ".join(f"{p}:{l}" if l else p for p, l in entry_occurrences)
        po_meta_comment_lines.append(f"#: {refs}")

    # 4. 处理标志 (Flags, #,)
    flags = getattr(entry, "flags", [])
    if flags:
        po_meta_comment_lines.append(f"#, {', '.join(flags)}")
        if "fuzzy" in flags:
            ts.is_fuzzy = True

    # 5. 处理旧翻译 (Previous, #|)
    if hasattr(entry, "previous_msgctxt") and entry.previous_msgctxt:
        po_meta_comment_lines.append(f"#|msgctxt: {entry.previous_msgctxt}")

    if hasattr(entry, "previous_msgid") and entry.previous_msgid:
        po_meta_comment_lines.append(f"#|msgid: {entry.previous_msgid}")

    if hasattr(entry, "previous_msgid_plural") and entry.previous_msgid_plural:
        po_meta_comment_lines.append(f"#|msgid_plural: {entry.previous_msgid_plural}")

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


def extract_to_pot(
    code_content,
    extraction_patterns,
    project_name="Untitled Project",
    app_version_from_app=APP_VERSION,
    original_file_name="source_code",
):
    pot_file = polib.POFile(wrapwidth=0)
    pot_file.metadata = {
        "Project-Id-Version": f"{project_name} {app_version_from_app}",
        "Report-Msgid-Bugs-To": "",
        "POT-Creation-Date": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M%z"),
        "MIME-Version": "1.0",
        "Content-Type": "text/plain; charset=utf-8",
        "Content-Transfer-Encoding": "8bit",
        "Generated-By": f"LexiSync {app_version_from_app}",
    }
    translatable_objects = extract_translatable_strings(code_content, extraction_patterns)
    for ts_obj in translatable_objects:
        entry = polib.POEntry(
            msgid=ts_obj.original_semantic,
            msgstr="",
            occurrences=[(original_file_name, str(ts_obj.line_num_in_file))],
            comment=ts_obj.comment,
        )
        pot_file.append(entry)
    return pot_file


def load_from_po(filepath, relative_path=None):
    logger.debug(f"[load_from_po] Starting to load PO file: {filepath}")
    po_file = polib.pofile(filepath, encoding="utf-8", wrapwidth=0)

    # 标记状态
    polib_failed = not po_file.metadata
    header_recovered = False

    # 存储头部注释
    header_comment = po_file.header

    if polib_failed:
        logger.warning("polib failed to parse metadata. Attempting manual recovery...")
        for entry in po_file:
            if entry.msgid == "":
                lines = entry.msgstr.splitlines()
                for line in lines:
                    if ":" in line:
                        key, val = line.split(":", 1)
                        po_file.metadata[key.strip()] = val.strip()
                header_comment = (entry.comment + "\n" + entry.tcomment).strip()
                if po_file.metadata:
                    header_recovered = True
                    po_file.metadata["_header_comment"] = header_comment if header_comment else None
                    logger.info("Manually recovered metadata and header comment.")
                # 移除这个条目
                po_file.remove(entry)
                break
    else:
        # 如果 polib 正常解析，也把 header 存入隐藏键
        po_file.metadata["_header_comment"] = po_file.header

    # "ok": 解析成功
    # "recovered": polib解析失败但自动修复了
    # "corrupt": 无法修复
    metadata_status = "ok"
    if polib_failed:
        metadata_status = "recovered" if header_recovered else "corrupt"

    nplurals = None
    plural_expr = None
    plural_forms_str = None

    for key, value in po_file.metadata.items():
        if key.strip().lower() == "plural-forms":
            plural_forms_str = value
            break

    if plural_forms_str:
        # 提取 nplurals
        nplurals_match = re.search(r"nplurals\s*=\s*(\d+)", plural_forms_str, re.IGNORECASE)
        if nplurals_match:
            nplurals = int(nplurals_match.group(1))

        # 提取 plural 表达式（匹配到分号为止）
        plural_expr_match = re.search(r"plural\s*=\s*([^;]+)", plural_forms_str, re.IGNORECASE)
        if plural_expr_match:
            plural_expr = plural_expr_match.group(1).strip()

    logger.debug(f"[load_from_po] nplurals: {nplurals}, plural_expr: {plural_expr}")

    translatable_objects = []
    project_root = _find_project_root(filepath)
    file_content_cache = {}
    path_exists_cache = {}

    def cached_is_file(path_str):
        if path_str not in path_exists_cache:
            path_exists_cache[path_str] = os.path.isfile(path_str)
        return path_exists_cache[path_str]

    po_file_rel_path = ""
    if relative_path:
        po_file_rel_path = relative_path
    elif project_root:
        try:
            po_file_rel_path = Path(filepath).relative_to(project_root).as_posix()
        except ValueError:
            po_file_rel_path = os.path.basename(filepath)
    else:
        po_file_rel_path = os.path.basename(filepath)

    occurrence_counters = {}
    for entry in po_file:
        if entry.obsolete or (entry.msgid == "" and not translatable_objects):
            continue

        key = (entry.msgid, entry.msgctxt or "")
        current_index = occurrence_counters.get(key, 0)
        occurrence_counters[key] = current_index + 1

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
                        with open(source_path_to_read, encoding="utf-8", errors="replace") as f:
                            lines = f.read().splitlines()
                            file_content_cache[source_path_to_read] = lines
                            full_code_lines = lines
            except Exception as e:
                logger.warning(f"Warning: Could not load context file for entry '{entry.msgid[:20]}...': {e}")

        ts = po_entry_to_translatable_string(
            entry,
            po_file_rel_path,
            full_code_lines,
            occurrence_index=current_index,
            nplurals_from_file=nplurals,
            plural_expr_from_file=plural_expr,
        )
        if ts:
            translatable_objects.append(ts)

    po_lang = po_file.metadata.get("Language", None)
    logger.debug(f"[load_from_po] Finished loading. Found {len(translatable_objects)} entries.")
    return translatable_objects, po_file.metadata, po_lang, metadata_status


def save_to_po(filepath, translatable_objects, metadata=None, original_file_name="source_code", app_instance=None):
    logger.info(f"--- Starting save_to_po for: {os.path.basename(filepath)} ---")

    po_file = polib.POFile(wrapwidth=78)

    # 准备元数据
    final_metadata = {}
    if metadata:
        final_metadata = metadata.copy()

    # 处理头部注释
    raw_header_comment = final_metadata.pop("_header_comment", None)

    po_file.header = str(raw_header_comment).strip() if raw_header_comment else ""

    now = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M%z")

    # 补全逻辑
    current_version = final_metadata.get("Project-Id-Version", "")
    if not current_version or current_version == "PACKAGE VERSION":
        project_name = "LexiSync Project"
        if app_instance and app_instance.is_project_mode:
            project_name = app_instance.project_config.get("name", "LexiSync Project")
        elif original_file_name and original_file_name != "source_code":
            project_name = os.path.splitext(os.path.basename(original_file_name))[0]

        logger.info(f"Setting default Project-Id-Version: {project_name}")
        final_metadata["Project-Id-Version"] = project_name
    else:
        logger.info(f"Preserving existing Project-Id-Version: {current_version}")

    # 强制更新的字段
    final_metadata["PO-Revision-Date"] = now
    final_metadata["X-Generator"] = f"LexiSync {APP_VERSION}"

    # 补全其他缺失的必要字段
    final_metadata.setdefault("Report-Msgid-Bugs-To", "https://github.com/TheSkyC/lexisync/issues")
    final_metadata.setdefault("POT-Creation-Date", now)
    final_metadata.setdefault("MIME-Version", "1.0")
    final_metadata.setdefault("Content-Type", "text/plain; charset=UTF-8")
    final_metadata.setdefault("Content-Transfer-Encoding", "8bit")

    # 复数公式保护
    if "Plural-Forms" not in final_metadata:
        logger.info("Plural-Forms missing in metadata, searching in objects...")
        for ts in translatable_objects:
            if ts.is_plural and getattr(ts, "plural_expr", None):
                nplurals = len(ts.plural_translations)
                expr = ts.plural_expr
                final_metadata["Plural-Forms"] = f"nplurals={nplurals}; plural={expr};"
                break

    po_file.metadata = final_metadata

    for ts_obj in translatable_objects:
        if not ts_obj.original_semantic or ts_obj.id == "##NEW_ENTRY##":
            continue

        prev_msgctxt = None
        prev_msgid = None
        prev_msgid_plural = None
        extracted_comments = []

        if ts_obj.is_reviewed or ts_obj.is_warning_ignored:
            ts_obj.is_fuzzy = False

        entry_flags = []
        if ts_obj.is_fuzzy:
            entry_flags.append("fuzzy")

        po_comment_lines = ts_obj.po_comment.splitlines()

        # 提取注释和 Previous 属性
        for line in po_comment_lines:
            stripped_line = line.strip()
            if stripped_line.startswith("#."):
                clean_line = stripped_line[2:].strip()
                extracted_comments.append(clean_line)
            elif stripped_line.startswith("#|msgctxt:"):
                prev_msgctxt = stripped_line.replace("#|msgctxt:", "").strip()
            elif stripped_line.startswith("#|msgid:"):
                prev_msgid = stripped_line.replace("#|msgid:", "").strip()
            elif stripped_line.startswith("#|msgid_plural:"):
                prev_msgid_plural = stripped_line.replace("#|msgid_plural:", "").strip()

        tcomment_str = "\n".join(extracted_comments) if extracted_comments else None

        # 构造引用位置
        entry_occurrences = []
        location_lines = [line for line in po_comment_lines if line.strip().startswith("#:")]
        for line in location_lines:
            content = line.replace("#:", "").strip()
            for part in content.split():
                if ":" in part:
                    try:
                        fpath, lineno = part.rsplit(":", 1)
                        entry_occurrences.append((fpath, lineno))
                    except ValueError:
                        pass

        if not entry_occurrences and ts_obj.line_num_in_file > 0 and ts_obj.string_type != "PO Import":
            entry_occurrences = [(original_file_name, str(ts_obj.line_num_in_file))]

        # 构造译员注释
        user_comment_lines = ts_obj.comment.splitlines()
        if ts_obj.is_reviewed:
            user_comment_lines.append("LexiSync:reviewed")
        if ts_obj.is_ignored and not getattr(ts_obj, "is_obsolete", False):
            user_comment_lines.append("LexiSync:ignored")
        translator_comment = "\n".join(user_comment_lines)

        # 构造 POEntry
        entry_kwargs = {
            "msgid": ts_obj.original_semantic,
            "msgctxt": ts_obj.context if ts_obj.context else None,
            "tcomment": tcomment_str,
            "comment": translator_comment,
            "occurrences": entry_occurrences,
            "flags": entry_flags,
            "obsolete": getattr(ts_obj, "is_obsolete", False),
        }

        if prev_msgctxt:
            entry_kwargs["previous_msgctxt"] = prev_msgctxt
        if prev_msgid:
            entry_kwargs["previous_msgid"] = prev_msgid
        if prev_msgid_plural:
            entry_kwargs["previous_msgid_plural"] = prev_msgid_plural

        if ts_obj.is_plural:
            entry_kwargs["msgid_plural"] = ts_obj.original_plural
            entry_kwargs["msgstr_plural"] = {str(k): v for k, v in ts_obj.plural_translations.items()}
        else:
            entry_kwargs["msgstr"] = ts_obj.translation

        po_file.append(polib.POEntry(**entry_kwargs))

    try:
        po_content = po_file.__unicode__()

        if not raw_header_comment:
            if po_content.startswith("#\n"):
                po_content = po_content[2:]
            elif po_content.startswith("# \n"):
                po_content = po_content[3:]

        from lexisync.utils.file_utils import atomic_open

        with atomic_open(filepath, "w", encoding="utf-8") as f:
            f.write(po_content)

        logger.info(f"Successfully saved PO file (with header fix) to: {filepath}")
    except Exception as e:
        logger.error(f"Error saving PO file to {filepath}: {e}", exc_info=True)
        raise e
