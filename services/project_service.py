import json
import os
import shutil
import datetime
from models.translatable_string import TranslatableString
from utils import constants


class ProjectService:
    @staticmethod
    def open_project(project_filepath):
        with open(project_filepath, 'r', encoding='utf-8') as f:
            project_data = json.load(f)

        if not all(k in project_data for k in ["version", "original_code_file_path", "translatable_objects_data"]):
            raise ValueError("Project file is invalid or missing required fields.")

        code_path = project_data["original_code_file_path"]
        raw_code = ""
        code_lines = []
        code_load_warning = None

        if code_path and os.path.exists(code_path):
            try:
                with open(code_path, 'r', encoding='utf-8', errors='replace') as cf:
                    raw_code = cf.read()
                code_lines = raw_code.splitlines()
            except Exception as e:
                code_load_warning = f"Could not load associated code file '{code_path}': {e}"
        elif code_path:
            code_load_warning = f"Associated code file '{code_path}' not found."

        translatable_objects = [
            TranslatableString.from_dict(ts_data, code_lines)
            for ts_data in project_data["translatable_objects_data"]
        ]

        project_data['translatable_objects'] = translatable_objects
        project_data['original_raw_code_content'] = raw_code
        project_data['code_load_warning'] = code_load_warning

        return project_data

    @staticmethod
    def save_project(project_filepath, project_data):
        try:
            with open(project_filepath, 'w', encoding='utf-8') as f:
                json.dump(project_data, f, indent=4, ensure_ascii=False,
                          default=lambda o: o.to_dict() if isinstance(o, TranslatableString) else o.__dict__)
            return True
        except Exception as e:
            raise IOError(f"Failed to save project file: {e}")

    @staticmethod
    def save_code_file(filepath_to_save, original_code, translatable_objects):
        from .code_file_service import CodeFileService
        final_content = CodeFileService.generate_translated_code(original_code, translatable_objects)

        if os.path.exists(filepath_to_save):
            backup_path = filepath_to_save + ".bak." + datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            try:
                shutil.copy2(filepath_to_save, backup_path)
            except Exception as e_backup:
                print(f"Warning: Could not create backup: {e_backup}")

        with open(filepath_to_save, 'w', encoding='utf-8') as f:
            f.write(final_content)