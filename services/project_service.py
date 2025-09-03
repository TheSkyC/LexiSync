# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import json
import shutil
import uuid
from pathlib import Path
from models.translatable_string import TranslatableString
from services.code_file_service import extract_translatable_strings
from utils.constants import APP_VERSION
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


def create_project(project_path: str, project_name: str, source_lang: str, target_langs: list, source_files: list, use_global_tm: bool):
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
            processed_source_files.append({
                "id": str(uuid.uuid4()),
                "original_path": str(original_path),
                "project_path": str(relative_path_obj),
                "type": file_info['type'],
                "linked": False
            })

            if not all_translatable_objects:
                with open(destination_path, 'r', encoding='utf-8') as f:
                    content = f.read().replace('\r\n', '\n').replace('\r', '\n')

                extraction_patterns = file_info['patterns']
                all_translatable_objects = extract_translatable_strings(content, extraction_patterns)

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

        for lang in target_langs:
            translation_path = proj_path / TRANSLATION_DIR / f"{lang}.json"
            initial_data = [ts.to_dict() for ts in all_translatable_objects]
            with open(translation_path, 'w', encoding='utf-8') as f:
                json.dump(initial_data, f, indent=4, ensure_ascii=False)

        return str(proj_path)

    except Exception as e:
        if proj_path.exists():
            shutil.rmtree(proj_path)
        raise IOError(_("Failed to create project: {error}").format(error=str(e)))


def load_project(project_path: str):
    proj_path = Path(project_path)
    config_path = proj_path / PROJECT_CONFIG_FILE
    if not config_path.is_file():
        raise FileNotFoundError(_("This is not a valid LexiSync project folder (missing project.json)."))

    with open(config_path, 'r', encoding='utf-8') as f:
        project_config = json.load(f)

    current_lang = project_config.get("current_target_language")
    if not current_lang:
        raise ValueError(_("Project has no target language selected."))

    translation_file = proj_path / TRANSLATION_DIR / f"{current_lang}.json"
    if not translation_file.is_file():
        raise FileNotFoundError(_("Translation data for language '{lang}' not found.").format(lang=current_lang))
    logger.debug(f"Loading project from: {project_path}")
    logger.debug(f"  - Reading config: {config_path}")
    logger.debug(f"  - Current language: {current_lang}")
    logger.debug(f"  - Loading translation data from: {translation_file}")
    with open(translation_file, 'r', encoding='utf-8') as f:
        translation_data = json.load(f)

    source_code_content = ""
    full_code_lines = []
    if project_config["source_files"]:
        source_file_path = proj_path / project_config["source_files"][0]["project_path"]
        if source_file_path.is_file():
            with open(source_file_path, 'r', encoding='utf-8') as f:
                source_code_content = f.read()
                full_code_lines = source_code_content.splitlines()

    translatable_objects = [TranslatableString.from_dict(data, full_code_lines) for data in translation_data]

    return {
        "project_config": project_config,
        "translatable_objects": translatable_objects,
        "original_raw_code_content": source_code_content
    }


def save_project(project_path: str, app_instance):
    proj_path = Path(project_path)
    config_path = proj_path / PROJECT_CONFIG_FILE

    if not config_path.is_file():
        raise FileNotFoundError(_("Cannot save, project configuration file is missing."))

    current_lang = app_instance.current_target_language
    translation_file = proj_path / TRANSLATION_DIR / f"{current_lang}.json"
    translation_data = [ts.to_dict() for ts in app_instance.translatable_objects]

    temp_file = translation_file.with_suffix(".json.tmp")

    logger.debug(f"[SAVE_PROJECT] Starting save for project at: {project_path}")
    logger.debug(f"[SAVE_PROJECT] Current target language: {current_lang}")

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

    logger.debug(f"[SAVE_PROJECT] Save operation finished.")
    return True