# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import json
import shutil
import uuid
import polib
from pathlib import Path
from services import po_file_service
from services.code_file_service import extract_translatable_strings
from utils.constants import APP_VERSION, DEFAULT_EXTRACTION_PATTERNS
from utils.localization import _
import logging
logger = logging.getLogger(__package__)


PROJECT_CONFIG_FILE = "project.json"
SOURCE_DIR = "source"
TRANSLATION_DIR = "translation"
TM_DIR = "tm"
GLOSSARY_DIR = "glossary"
TARGET_DIR = "target"
METADATA_DIR = "metadata"


def create_project(project_path: str, project_name: str, source_lang: str, target_langs: list, source_files: list,
                   use_global_tm: bool, glossary_files: list = None, tm_files: list = None):
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
            original_path = Path(file_info['path'])
            destination_path = proj_path / SOURCE_DIR / original_path.name
            shutil.copy2(original_path, destination_path)

            relative_path_obj = destination_path.relative_to(proj_path)
            relative_path_posix = relative_path_obj.as_posix()

            processed_file_info = {
                "id": str(uuid.uuid4()),
                "original_path": str(original_path).replace('\\', '/'),
                "project_path": relative_path_posix,
                "type": file_info['type'],
                "linked": False
            }
            processed_source_files.append(processed_file_info)

            with open(destination_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()

            extraction_patterns = file_info.get('patterns', DEFAULT_EXTRACTION_PATTERNS)
            extracted_strings = extract_translatable_strings(content, extraction_patterns, relative_path_posix)
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
            "settings": {
                "use_global_tm": use_global_tm
            },
            "ui_state": {}
        }

        with open(proj_path / PROJECT_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(project_config, f, indent=4, ensure_ascii=False)

        initial_data = [ts.to_dict() for ts in all_translatable_objects]
        for lang in target_langs:
            translation_path = proj_path / TRANSLATION_DIR / f"{lang}.json"
            with open(translation_path, 'w', encoding='utf-8') as f:
                json.dump(initial_data, f, indent=4, ensure_ascii=False)

        return str(proj_path)

    except Exception as e:
        if proj_path.exists():
            shutil.rmtree(proj_path)
        raise IOError(_("Failed to create project: {error}").format(error=str(e)))


def load_project_data(project_path: str, target_language: str, file_id_to_load: str = None, all_files: bool = False):
    proj_path = Path(project_path)
    config_path = proj_path / PROJECT_CONFIG_FILE
    if not config_path.is_file():
        raise FileNotFoundError(_("This is not a valid LexiSync project folder (missing project.json)."))

    with open(config_path, 'r', encoding='utf-8') as f:
        project_config = json.load(f)

    translation_file = proj_path / TRANSLATION_DIR / f"{target_language}.json"
    translation_map = {}
    if translation_file.is_file():
        with open(translation_file, 'r', encoding='utf-8') as f:
            translation_data = json.load(f)
        translation_map = {item['id']: item for item in translation_data}

    loaded_strings = []

    files_to_process = []
    if all_files:
        files_to_process = project_config.get("source_files", [])
    elif file_id_to_load:
        file_info = next((f for f in project_config.get("source_files", []) if f['id'] == file_id_to_load), None)
        if file_info:
            files_to_process.append(file_info)

    for file_info in files_to_process:
        source_file_path_abs = proj_path / file_info["project_path"]
        if not source_file_path_abs.is_file():
            logger.warning(f"Source file not found, skipping: {source_file_path_abs}")
            continue

        extracted_strings = []
        file_type = file_info.get("type", "code")
        relative_path = file_info["project_path"]
        logger.debug(f"[load_project_data] Processing file: {relative_path}, type: {file_type}")
        if file_type == 'po':
            try:
                extracted_strings, __, ___ = po_file_service.load_from_po(str(source_file_path_abs))
                logger.debug(f"[load_project_data] Loaded {len(extracted_strings)} strings from PO file.")
            except Exception as e:
                logger.error(f"Failed to parse PO file {source_file_path_abs}: {e}", exc_info=True)
        else:
            with open(source_file_path_abs, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()

            extraction_patterns = file_info.get("patterns", DEFAULT_EXTRACTION_PATTERNS)
            extracted_strings = extract_translatable_strings(content, extraction_patterns, relative_path)
            logger.debug(f"[load_project_data] Extracted {len(extracted_strings)} strings from code file.")

        for ts_obj in extracted_strings:
            if ts_obj.id in translation_map:
                ts_data = translation_map[ts_obj.id]
                ts_obj.translation = ts_data.get('translation', "").replace("\\n", "\n")
                ts_obj.comment = ts_data.get('comment', "")
                ts_obj.is_reviewed = ts_data.get('is_reviewed', False)
                ts_obj.is_ignored = ts_data.get('is_ignored', False)
                ts_obj.is_fuzzy = ts_data.get('is_fuzzy', False)
                ts_obj.po_comment = ts_data.get('po_comment', "")
                ts_obj.is_warning_ignored = ts_data.get('is_warning_ignored', False)
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
    with open(temp_file, 'w', encoding='utf-8') as f:
        json.dump(translation_data, f, indent=4, ensure_ascii=False)
    shutil.move(temp_file, translation_file)

    project_config_to_save = app_instance.project_config
    project_config_to_save["current_target_language"] = app_instance.current_target_language
    project_config_to_save["ui_state"] = {
        "search_term": app_instance.search_entry.text() if app_instance.search_entry.text() != _(
            "Quick search...") else "",
        "selected_ts_id": app_instance.current_selected_ts_id or ""
    }

    temp_config_file = config_path.with_suffix(".json.tmp")
    with open(temp_config_file, 'w', encoding='utf-8') as f:
        json.dump(project_config_to_save, f, indent=4, ensure_ascii=False)
    shutil.move(temp_config_file, config_path)

    return True


def build_project_target_files(project_path: str, app_instance, progress_callback=None):
    proj_path = Path(project_path)
    config_path = proj_path / PROJECT_CONFIG_FILE

    with open(config_path, 'r', encoding='utf-8') as f:
        project_config = json.load(f)

    target_langs = project_config.get('target_languages', [])
    source_files = project_config.get('source_files', [])

    total_steps = len(target_langs) * len(source_files)
    current_step = 0

    for lang_code in target_langs:
        translation_file = proj_path / TRANSLATION_DIR / f"{lang_code}.json"
        translation_map = {}
        if translation_file.is_file():
            with open(translation_file, 'r', encoding='utf-8') as f:
                translation_data = json.load(f)
            translation_map = {item['id']: item for item in translation_data}

        lang_target_dir = proj_path / TARGET_DIR / lang_code
        lang_target_dir.mkdir(parents=True, exist_ok=True)

        for file_info in source_files:
            current_step += 1
            if progress_callback:
                msg = _("Building '{file}' for language '{lang}'...").format(file=Path(file_info['project_path']).name,
                                                                             lang=lang_code)
                progress_callback(current_step, total_steps, msg)

            source_path_abs = proj_path / file_info['project_path']
            target_path_abs = lang_target_dir / Path(file_info['project_path']).name

            if not source_path_abs.is_file():
                logger.warning(f"Source file not found, skipping: {source_path_abs}")
                continue
            file_type = file_info.get("type", "code")
            if file_type == 'po':
                try:
                    po_file = polib.pofile(str(source_path_abs), encoding='utf-8', wrapwidth=0)
                    temp_ts_objects, __, ___ = po_file_service.load_from_po(str(source_path_abs))
                    id_to_msgid_map = {ts.id: ts.original_semantic for ts in temp_ts_objects}
                    for entry in po_file:
                        entry_id = next((ts_id for ts_id, msgid in id_to_msgid_map.items() if msgid == entry.msgid),
                                        None)
                        if entry_id and entry_id in translation_map:
                            translated_data = translation_map[entry_id]
                            translation_text = translated_data.get('translation', "").replace("\\n", "\n")
                            if not translated_data.get('is_ignored', False):
                                entry.msgstr = translation_text

                    po_file.save(str(target_path_abs))

                except Exception as e:
                    logger.error(f"Failed to build PO file {source_path_abs}: {e}", exc_info=True)

            else:
                with open(source_path_abs, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()

                extraction_patterns = file_info.get("patterns", DEFAULT_EXTRACTION_PATTERNS)
                extracted_strings = extract_translatable_strings(content, extraction_patterns,
                                                                 file_info['project_path'])

                for ts_obj in sorted(extracted_strings, key=lambda x: x.char_pos_start_in_file, reverse=True):
                    if ts_obj.id in translation_map:
                        translated_data = translation_map[ts_obj.id]
                        translation_text = translated_data.get('translation', "").replace("\\n", "\n")
                        if translation_text.strip() and not translated_data.get('is_ignored', False):
                            start = ts_obj.char_pos_start_in_file
                            end = ts_obj.char_pos_end_in_file

                            ts_obj.translation = translation_text
                            replacement = ts_obj.get_raw_translated_for_code()

                            content = content[:start] + replacement + content[end:]

                with open(target_path_abs, 'w', encoding='utf-8') as f:
                    f.write(content)

    total_files_built = len(target_langs) * len(source_files)
    success_message = _("Project build completed successfully.\n\n"
                        "Languages: {num_langs}\n"
                        "Source Files per Language: {num_files}\n"
                        "Total Files Created: {total_files}").format(
        num_langs=len(target_langs),
        num_files=len(source_files),
        total_files=total_files_built
    )
    return True, success_message