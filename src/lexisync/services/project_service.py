# Copyright (c) 2025-2026, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from copy import deepcopy
import json
import logging
from pathlib import Path
import shutil
import uuid

from rapidfuzz import fuzz

from lexisync.services.code_file_service import extract_translatable_strings
from lexisync.services.format_manager import FormatManager
from lexisync.utils.constants import APP_VERSION, DEFAULT_EXTRACTION_PATTERNS
from lexisync.utils.localization import _

logger = logging.getLogger(__package__)


PROJECT_CONFIG_FILE = "project.json"
SOURCE_DIR = "source"
TRANSLATION_DIR = "translation"
TM_DIR = "tm"
GLOSSARY_DIR = "glossary"
TARGET_DIR = "target"
METADATA_DIR = "metadata"


def create_project(
    project_path: str,
    project_name: str,
    source_lang: str,
    target_langs: list,
    source_files: list,
    use_global_tm: bool,
    app_instance,
    glossary_files: list | None = None,
    tm_files: list | None = None,
):
    proj_path = Path(project_path)
    if proj_path.exists():
        raise FileExistsError(_("A file or directory with this name already exists."))

    try:
        proj_path.mkdir(parents=True)
        (proj_path / SOURCE_DIR).mkdir()
        (proj_path / TRANSLATION_DIR).mkdir()
        (proj_path / TM_DIR).mkdir()
        (proj_path / GLOSSARY_DIR).mkdir()
        (proj_path / TARGET_DIR).mkdir()
        (proj_path / METADATA_DIR).mkdir()

        processed_source_files = []
        all_translatable_objects = []

        for file_info in source_files:
            original_path = Path(file_info["path"])
            destination_path = proj_path / SOURCE_DIR / original_path.name
            shutil.copy2(original_path, destination_path)

            relative_path_obj = destination_path.relative_to(proj_path)
            relative_path_posix = relative_path_obj.as_posix()

            f_id = file_info["format_id"]

            processed_file_info = {
                "id": str(uuid.uuid4()),
                "original_path": str(original_path).replace("\\", "/"),
                "project_path": relative_path_posix,
                "format_id": f_id,
                "linked": False,
            }
            processed_source_files.append(processed_file_info)
            handler = FormatManager.get_handler(f_id)
            if handler:
                if handler.format_type == "translation":
                    extracted_strings, __, ___ = handler.load(
                        str(destination_path), relative_path=relative_path_posix, app_instance=app_instance
                    )
                else:
                    patterns = file_info.get("patterns", DEFAULT_EXTRACTION_PATTERNS)
                    extracted_strings, __, ___ = handler.load(
                        str(destination_path),
                        extraction_patterns=patterns,
                        relative_path=relative_path_posix,
                        app_instance=app_instance,
                    )
                all_translatable_objects.extend(extracted_strings)

        if glossary_files:
            for g_file in glossary_files:
                shutil.copy2(g_file, proj_path / GLOSSARY_DIR)

        if tm_files:
            for t_file in tm_files:
                shutil.copy2(t_file, proj_path / TM_DIR)

        project_config = {
            "lexisync_version": APP_VERSION,
            "name": project_name,
            "source_language": source_lang,
            "target_languages": target_langs,
            "current_target_language": target_langs[0] if target_langs else "",
            "source_files": processed_source_files,
            "settings": {"use_global_tm": use_global_tm},
            "ui_state": {},
        }

        with open(proj_path / PROJECT_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(project_config, f, indent=4, ensure_ascii=False)

        initial_data = [ts.to_dict() for ts in all_translatable_objects]
        for lang in target_langs:
            translation_path = proj_path / TRANSLATION_DIR / f"{lang}.json"
            with open(translation_path, "w", encoding="utf-8") as f:
                json.dump(initial_data, f, indent=4, ensure_ascii=False)

        return str(proj_path)

    except Exception as e:
        if proj_path.exists():
            shutil.rmtree(proj_path)
        raise OSError(_("Failed to create project: {error}").format(error=str(e))) from e


def load_project_data(
    project_path: str, target_language: str, app_instance, file_id_to_load: str | None = None, all_files: bool = False
):
    proj_path = Path(project_path)
    config_path = proj_path / PROJECT_CONFIG_FILE
    if not config_path.is_file():
        raise FileNotFoundError(_("This is not a valid LexiSync project folder (missing project.json)."))

    with open(config_path, encoding="utf-8") as f:
        project_config = json.load(f)

    translation_file = proj_path / TRANSLATION_DIR / f"{target_language}.json"
    translation_map = {}
    if translation_file.is_file():
        with open(translation_file, encoding="utf-8") as f:
            translation_data = json.load(f)
        translation_map = {item["id"]: item for item in translation_data}

    loaded_strings = []

    files_to_process = []
    if all_files:
        files_to_process = project_config.get("source_files", [])
    elif file_id_to_load:
        file_info = next((f for f in project_config.get("source_files", []) if f["id"] == file_id_to_load), None)
        if file_info:
            files_to_process.append(file_info)

    for file_info in files_to_process:
        source_file_path_abs = proj_path / file_info["project_path"]
        if not source_file_path_abs.is_file():
            logger.warning(f"Source file not found, skipping: {source_file_path_abs}")
            continue

        extracted_strings = []

        format_id = file_info.get("format_id")
        from lexisync.services.format_manager import FormatManager

        handler = FormatManager.get_handler(format_id)

        if not handler:
            logger.error(f"No handler found for format_id: {format_id}")
            continue

        logger.debug(f"[load_project_data] Processing file: {file_info['project_path']}, format: {format_id}")

        try:
            if handler.format_type == "translation":
                extracted_strings, __, ___ = handler.load(
                    str(source_file_path_abs), relative_path=file_info["project_path"], app_instance=app_instance
                )
                logger.debug(
                    f"[load_project_data] Loaded {len(extracted_strings)} strings from {handler.display_name}."
                )
            elif handler.format_type == "source":
                extraction_patterns = file_info.get("patterns", DEFAULT_EXTRACTION_PATTERNS)
                extracted_strings, __, ___ = handler.load(
                    str(source_file_path_abs),
                    extraction_patterns=extraction_patterns,
                    relative_path=file_info["project_path"],
                    app_instance=app_instance,
                )
                logger.debug(
                    f"[load_project_data] Extracted {len(extracted_strings)} strings from {handler.display_name}."
                )
        except Exception as e:
            logger.error(f"Failed to parse file {source_file_path_abs}: {e}", exc_info=True)

        for ts_obj in extracted_strings:
            if ts_obj.id in translation_map:
                ts_data = translation_map[ts_obj.id]
                val = ts_data.get("translation", "").replace("\\n", "\n")
                ts_obj.set_translation_internal(val)
                ts_obj._translation_edit_history = [ts_obj.translation]
                ts_obj._translation_history_pointer = 0
                ts_obj.comment = ts_data.get("comment", "")
                ts_obj.is_reviewed = ts_data.get("is_reviewed", False)
                ts_obj.is_ignored = ts_data.get("is_ignored", False)
                ts_obj.is_fuzzy = ts_data.get("is_fuzzy", False)
                ts_obj.po_comment = ts_data.get("po_comment", "")
                ts_obj.is_warning_ignored = ts_data.get("is_warning_ignored", False)
                ts_obj.sync_cached_text_fields()
            loaded_strings.append(ts_obj)

    logger.debug(f"[load_project_data] Total strings loaded in this call: {len(loaded_strings)}")
    return project_config, loaded_strings


def save_project(project_path: str, app_instance):
    proj_path = Path(project_path)
    config_path = proj_path / PROJECT_CONFIG_FILE

    if not config_path.is_file():
        raise FileNotFoundError(_("Cannot save, project configuration file is missing."))

    current_lang = app_instance.current_target_language
    translation_file = proj_path / TRANSLATION_DIR / f"{current_lang}.json"

    translation_data = [ts.to_dict() for ts in app_instance.all_project_strings]

    temp_file = translation_file.with_suffix(".json.tmp")
    with app_instance.file_monitor.ignore_changes():
        temp_file = translation_file.with_suffix(".json.tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(translation_data, f, indent=4, ensure_ascii=False)
        shutil.move(temp_file, translation_file)
    shutil.move(temp_file, translation_file)

    project_config_to_save = app_instance.project_config
    project_config_to_save["current_target_language"] = app_instance.current_target_language
    project_config_to_save["ui_state"] = {
        "search_term": app_instance.search_entry.text()
        if app_instance.search_entry.text() != _("Quick search...")
        else "",
        "selected_ts_id": app_instance.current_selected_ts_id or "",
    }

    temp_config_file = config_path.with_suffix(".json.tmp")
    with open(temp_config_file, "w", encoding="utf-8") as f:
        json.dump(project_config_to_save, f, indent=4, ensure_ascii=False)
    shutil.move(temp_config_file, config_path)

    return True


def build_project_target_files(project_path: str, app_instance, progress_callback=None):
    proj_path = Path(project_path)
    config_path = proj_path / PROJECT_CONFIG_FILE

    with open(config_path, encoding="utf-8") as f:
        project_config = json.load(f)

    target_langs = project_config.get("target_languages", [])
    source_files = project_config.get("source_files", [])

    total_steps = len(target_langs) * len(source_files)
    current_step = 0

    for lang_code in target_langs:
        translation_file = proj_path / TRANSLATION_DIR / f"{lang_code}.json"
        translation_map = {}
        if translation_file.is_file():
            with open(translation_file, encoding="utf-8") as f:
                translation_data = json.load(f)
            translation_map = {item["id"]: item for item in translation_data}

        lang_target_dir = proj_path / TARGET_DIR / lang_code
        lang_target_dir.mkdir(parents=True, exist_ok=True)

        for file_info in source_files:
            current_step += 1
            if progress_callback:
                msg = _("Building '{file}' for language '{lang}'...").format(
                    file=Path(file_info["project_path"]).name, lang=lang_code
                )
                progress_callback(current_step, total_steps, msg)

            source_path_abs = proj_path / file_info["project_path"]
            target_path_abs = lang_target_dir / Path(file_info["project_path"]).name

            if not source_path_abs.is_file():
                logger.warning(f"Source file not found, skipping: {source_path_abs}")
                continue
            format_id = file_info.get("format_id")
            if not format_id:
                format_id = "po" if file_info.get("type") == "po" else "ow_code"

            handler = FormatManager.get_handler(format_id)
            if not handler:
                continue

            try:
                if handler.format_type == "translation":
                    temp_ts_objects, metadata, __ = handler.load(str(source_path_abs))
                    for ts in temp_ts_objects:
                        if ts.id in translation_map:
                            translated_data = translation_map[ts.id]
                            translation_text = translated_data.get("translation", "").replace("\\n", "\n")
                            if not translated_data.get("is_ignored", False):
                                ts.set_translation_internal(translation_text)
                                ts.is_reviewed = translated_data.get("is_reviewed", False)
                                ts.is_fuzzy = translated_data.get("is_fuzzy", False)
                    handler.save(str(target_path_abs), temp_ts_objects, metadata, app_instance=app_instance)

                elif handler.format_type == "source":
                    with open(source_path_abs, encoding="utf-8", errors="replace") as f:
                        content = f.read()
                    extraction_patterns = file_info.get("patterns", DEFAULT_EXTRACTION_PATTERNS)
                    extracted_strings, __, ___ = handler.load(
                        str(source_path_abs),
                        extraction_patterns=extraction_patterns,
                        relative_path=file_info["project_path"],
                    )

                    for ts_obj in sorted(extracted_strings, key=lambda x: x.char_pos_start_in_file, reverse=True):
                        if ts_obj.id in translation_map:
                            translated_data = translation_map[ts_obj.id]
                            translation_text = translated_data.get("translation", "").replace("\\n", "\n")
                            if translation_text.strip() and not translated_data.get("is_ignored", False):
                                start = ts_obj.char_pos_start_in_file
                                end = ts_obj.char_pos_end_in_file
                                ts_obj.set_translation_internal(translation_text)
                                replacement = ts_obj.get_raw_translated_for_code()
                                content = content[:start] + replacement + content[end:]

                    with open(target_path_abs, "w", encoding="utf-8") as f:
                        f.write(content)
            except Exception as e:
                logger.error(f"Failed to build file {source_path_abs}: {e}", exc_info=True)
            else:
                with open(source_path_abs, encoding="utf-8", errors="replace") as f:
                    content = f.read()

                extraction_patterns = file_info.get("patterns", DEFAULT_EXTRACTION_PATTERNS)
                extracted_strings = extract_translatable_strings(
                    content, extraction_patterns, file_info["project_path"]
                )

                for ts_obj in sorted(extracted_strings, key=lambda x: x.char_pos_start_in_file, reverse=True):
                    if ts_obj.id in translation_map:
                        translated_data = translation_map[ts_obj.id]
                        translation_text = translated_data.get("translation", "").replace("\\n", "\n")
                        if translation_text.strip() and not translated_data.get("is_ignored", False):
                            start = ts_obj.char_pos_start_in_file
                            end = ts_obj.char_pos_end_in_file

                            ts_obj.translation = translation_text
                            replacement = ts_obj.get_raw_translated_for_code()

                            content = content[:start] + replacement + content[end:]

                with open(target_path_abs, "w", encoding="utf-8") as f:
                    f.write(content)

    total_files_built = len(target_langs) * len(source_files)
    success_message = _(
        "Project build completed successfully.\n\n"
        "Languages: {num_langs}\n"
        "Source Files per Language: {num_files}\n"
        "Total Files Created: {total_files}"
    ).format(num_langs=len(target_langs), num_files=len(source_files), total_files=total_files_built)
    return True, success_message


def rebuild_project_structure(project_path: str, target_langs: list, new_patterns: list, app_instance):
    """
    重新构建项目结构：通过 FormatManager 重新加载所有源文件并合并现有翻译。
    """
    proj_path = Path(project_path)
    config_path = proj_path / PROJECT_CONFIG_FILE

    with open(config_path, encoding="utf-8") as f:
        project_config = json.load(f)

    source_files = project_config.get("source_files", [])
    all_new_strings = []

    # 统一使用 FormatManager 加载所有源文件
    from lexisync.services.format_manager import FormatManager

    for file_info in source_files:
        file_abs_path = proj_path / file_info["project_path"]
        if not file_abs_path.is_file():
            logger.warning(f"Source file missing during rebuild: {file_abs_path}")
            continue

        handler = FormatManager.get_handler(file_info.get("format_id"))
        if not handler:
            logger.error(f"No handler found for format_id: {file_info.get('format_id')}")
            continue

        try:
            extracted, __, ___ = handler.load(
                str(file_abs_path),
                extraction_patterns=new_patterns,
                relative_path=file_info["project_path"],
                app_instance=app_instance,
            )
            all_new_strings.extend(extracted)
        except Exception as e:
            logger.error(f"Failed to load file during rebuild: {file_abs_path}, error: {e}")

    # 针对每个目标语言进行数据合并
    rebuild_results = {}  # {lang: [new_objects]}

    for lang in target_langs:
        trans_file = proj_path / TRANSLATION_DIR / f"{lang}.json"
        old_data_map = {}
        if trans_file.is_file():
            with open(trans_file, encoding="utf-8") as f:
                old_data_list = json.load(f)
                # 以原文语义为 Key 建立映射，方便找回翻译
                for item in old_data_list:
                    old_data_map[item["id"]] = item

        final_lang_strings = []
        current_new_strings = deepcopy(all_new_strings)

        # 建立一个基于原文的旧池子，用于模糊匹配
        old_pool_by_text = {v["original_semantic"]: v for v in old_data_map.values()}
        used_old_ids = set()

        for ts in current_new_strings:
            # 策略 A: ID 精确匹配
            if ts.id in old_data_map:
                old_item = old_data_map[ts.id]
                if old_item.get("is_plural"):
                    ts.is_plural = True
                    ts.original_plural = old_item.get("original_plural", "")
                    ts.plural_translations = {
                        int(k): v
                        for k, v in old_item.get("plural_translations", {0: old_item.get("translation", "")}).items()
                    }
                    ts.translation = old_item.get("translation", "")
                else:
                    ts.set_translation_internal(old_item.get("translation", ""))
                ts.comment = old_item.get("comment", "")
                ts.is_reviewed = old_item.get("is_reviewed", False)
                ts.is_ignored = old_item.get("is_ignored", False)
                ts.is_fuzzy = old_item.get("is_fuzzy", False)
                ts.sync_cached_text_fields()
                used_old_ids.add(ts.id)

            # 策略 B: 原文内容匹配
            elif ts.original_semantic in old_pool_by_text:
                old_item = old_pool_by_text[ts.original_semantic]
                if old_item.get("is_plural"):
                    ts.is_plural = True
                    ts.original_plural = old_item.get("original_plural", "")
                    ts.plural_translations = {
                        int(k): v
                        for k, v in old_item.get("plural_translations", {0: old_item.get("translation", "")}).items()
                    }
                    ts.translation = old_item.get("translation", "")
                else:
                    ts.set_translation_internal(old_item.get("translation", ""))
                ts.comment = old_item.get("comment", "")
                ts.is_fuzzy = True  # 标记为模糊，因为位置变了
                ts.sync_cached_text_fields()
                used_old_ids.add(old_item["id"])

            # 策略 C: 模糊匹配
            else:
                best_score = 0
                best_match = None
                for old_id, old_item in old_data_map.items():
                    if old_id in used_old_ids:
                        continue
                    score = fuzz.ratio(ts.original_semantic, old_item["original_semantic"]) / 100.0
                    if score > best_score:
                        best_score = score
                        best_match = old_item

                if best_score >= 0.85:
                    if best_match.get("is_plural"):
                        ts.is_plural = True
                        ts.original_plural = best_match.get("original_plural", "")
                        ts.plural_translations = {
                            int(k): v
                            for k, v in best_match.get(
                                "plural_translations", {0: best_match.get("translation", "")}
                            ).items()
                        }
                        ts.translation = best_match.get("translation", "")
                    else:
                        ts.set_translation_internal(best_match.get("translation", ""))
                    ts.is_fuzzy = True
                    ts.sync_cached_text_fields()
                    used_old_ids.add(best_match["id"])

            final_lang_strings.append(ts)

        rebuild_results[lang] = final_lang_strings

    return rebuild_results
