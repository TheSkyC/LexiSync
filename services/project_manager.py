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
        file_type = 'po' if source_file.suffix.lower() in ['.po', '.pot'] else 'code'

        new_file_entry = {
            "id": str(uuid.uuid4()),
            "original_path": str(source_file),
            "project_path": relative_path,
            "type": file_type,
            "linked": False
        }
        self.project_config['source_files'].append(new_file_entry)
        is_first_file = len(self.project_config['source_files']) == 1
        if is_first_file:
            try:
                with open(destination_path, 'r', encoding='utf-8') as f:
                    content = f.read().replace('\r\n', '\n').replace('\r', '\n')

                patterns = self.app.config.get("extraction_patterns", [])
                initial_objects = extract_translatable_strings(content, patterns)
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