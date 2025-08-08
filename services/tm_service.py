# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import json
import logging
import os
import shutil
from datetime import datetime, timezone
from openpyxl import load_workbook, Workbook
from utils.localization import _

def create_tu(source_text, target_text, source_lang, target_lang, created_by="LexiSync", comment=""):
    now = datetime.now(timezone.utc).isoformat()
    return {
        "source_text": source_text,
        "target_text": target_text,
        "source_lang": source_lang,
        "target_lang": target_lang,
        "created_by": created_by,
        "creation_date": now,
        "modified_by": created_by,
        "last_modified_date": now,
        "usage_count": 1,
        "comment": comment
    }

class BaseTMProvider:
    def read(self, filepath: str) -> dict:
        raise NotImplementedError

    def write(self, filepath: str, tm_data: dict):
        raise NotImplementedError

class JsonlTMProvider(BaseTMProvider):
    def read(self, filepath: str) -> dict:
        tm_data = {}
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        tu = json.loads(line)
                        tm_data[tu["source_text"]] = tu
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        return tm_data

    def write(self, filepath: str, tm_data: dict):
        temp_filepath = filepath + ".tmp"
        with open(temp_filepath, 'w', encoding='utf-8') as f:
            for tu in tm_data.values():
                f.write(json.dumps(tu, ensure_ascii=False) + '\n')
        shutil.move(temp_filepath, filepath)

class XlsxTMProvider(BaseTMProvider):
    def read(self, filepath: str) -> dict:
        tm_data = {}
        try:
            workbook = load_workbook(filepath, read_only=True)
            sheet = workbook.active
            for row in sheet.iter_rows(min_row=2, values_only=True):
                if len(row) >= 2 and row[0] is not None:
                    source_text = str(row[0])
                    target_text = str(row[1]) if row[1] is not None else ""
                    tm_data[source_text] = create_tu(source_text, target_text, "unknown", "unknown", "Legacy Import")
        except FileNotFoundError:
            pass
        return tm_data

    def write(self, filepath: str, tm_data: dict):
        raise NotImplementedError(_("Saving to legacy .xlsx TM format is not supported. Please use .jsonl."))

class TMService:
    def __init__(self):
        self.providers = {
            '.jsonl': JsonlTMProvider(),
            '.xlsx': XlsxTMProvider(),
        }

    def get_provider(self, filepath: str) -> BaseTMProvider | None:
        _, ext = os.path.splitext(filepath)
        return self.providers.get(ext.lower())

    def load_tm_from_directory(self, directory_path: str) -> dict:
        merged_tm = {}
        if not os.path.isdir(directory_path):
            return merged_tm

        for filename in os.listdir(directory_path):
            filepath = os.path.join(directory_path, filename)
            if os.path.isfile(filepath):
                tm_data = self.load_tm(filepath)
                if tm_data:
                    merged_tm.update(tm_data)
                else:
                    logging.warning(f"TMService: File '{filename}' was loaded, but it's empty or unsupported.")
        return merged_tm

    def load_tm(self, filepath: str) -> dict:
        provider = self.get_provider(filepath)
        if provider:
            return provider.read(filepath)
        return {}

    def save_tm(self, filepath: str, tm_data: dict):
        jsonl_provider = self.providers['.jsonl']
        base, _ = os.path.splitext(filepath)
        jsonl_filepath = base + ".jsonl"
        jsonl_provider.write(jsonl_filepath, tm_data)
        return jsonl_filepath

    def update_tm_entry(self, tm_data: dict, source_text: str, target_text: str, source_lang: str, target_lang: str):
        if not source_text.strip():
            return

        if source_text in tm_data:
            tu = tm_data[source_text]
            tu["target_text"] = target_text
            tu["last_modified_date"] = datetime.now(timezone.utc).isoformat()
            tu["usage_count"] = tu.get("usage_count", 0) + 1
        else:
            tu = create_tu(source_text, target_text, source_lang, target_lang)
            tm_data[source_text] = tu