# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import os
import shutil
import json
import uuid
from pathlib import Path
from typing import Tuple, List, Dict
from . import project_service
from utils.localization import _
from services.code_file_service import extract_translatable_strings
from services.format_manager import FormatManager


class ProjectManager:
    def __init__(self, app_instance):
        self.app = app_instance
        self.current_project_path = None
        self.project_config = {}

    def is_project_open(self) -> bool:
        return self.current_project_path is not None

    def load_project(self, project_path: str):
        loaded_data = project_service.load_project(project_path)
        self.current_project_path = project_path
        self.project_config = loaded_data["project_config"]
        self.app.current_project_path = self.current_project_path
        self.app.project_config = self.project_config
        self.app.translatable_objects = loaded_data["translatable_objects"]
        self.app.original_raw_code_content = loaded_data["original_raw_code_content"]
        return loaded_data

    def close_project(self):
        self.current_project_path = None
        self.project_config = {}

    def add_source_file(self, file_to_add_path: str) -> Tuple[bool, str]:
        if not self.is_project_open():
            return False, _("No project is currently open.")

        source_file = Path(file_to_add_path)
        if not source_file.is_file():
            return False, _("Source file does not exist.")
        proj_path = Path(self.current_project_path)
        config_path = proj_path / project_service.PROJECT_CONFIG_FILE

        if any(Path(p['original_path']).name == source_file.name for p in self.project_config['source_files']):
            return False, _("A file with this name already exists in the project.")

        destination_path = proj_path / project_service.SOURCE_DIR / source_file.name
        shutil.copy2(source_file, destination_path)

        relative_path = destination_path.relative_to(proj_path).as_posix()
        handler = FormatManager.get_handler_by_extension(file_to_add_path)
        if not handler:
            return False, _("Unsupported file format.")

        new_file_entry = {
            "id": str(uuid.uuid4()),
            "original_path": str(source_file),
            "project_path": relative_path,
            "format_id": handler.format_id,
            "linked": False
        }
        self.project_config['source_files'].append(new_file_entry)
        is_first_file = len(self.project_config['source_files']) == 1
        if is_first_file:
            try:
                if handler.format_type == "translation":
                    initial_objects, __, ___ = handler.load(str(destination_path))
                else:
                    patterns = self.app.config.get("extraction_patterns", [])
                    initial_objects, __, ___ = handler.load(str(destination_path),
                                                         extraction_patterns=patterns,
                                                         relative_path=relative_path)

                initial_data = [ts.to_dict() for ts in initial_objects]

                for lang in self.project_config['target_languages']:
                    translation_path = proj_path / project_service.TRANSLATION_DIR / f"{lang}.json"
                    with open(translation_path, 'w', encoding='utf-8') as f:
                        json.dump(initial_data, f, indent=4, ensure_ascii=False)
            except Exception as e:
                self.project_config['source_files'].pop()
                return False, _("Failed to create initial translation data: {error}").format(error=e)

        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.project_config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            return False, _("Failed to save project configuration: {error}").format(error=e)

        return True, _("File '{filename}' added to the project successfully.").format(filename=source_file.name)

    # TODO: remove_source_file, add_target_language 等