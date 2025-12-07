# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import sqlite3
import re
import os
import json
import hashlib
import logging
from rapidfuzz import fuzz
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from openpyxl import load_workbook
from utils.localization import _

logger = logging.getLogger(__name__)

MANIFEST_FILE = "manifest.json"
DB_FILE = "tm.db"


class TMService:
    def __init__(self):
        self.project_db_path: Optional[str] = None
        self.global_db_path: Optional[str] = None

    def connect_databases(self, global_tm_path: Optional[str], project_tm_path: Optional[str] = None):
        self.disconnect_databases()

        if global_tm_path:
            os.makedirs(global_tm_path, exist_ok=True)
            self.global_db_path = os.path.join(global_tm_path, DB_FILE)
            with self._get_db_connection(self.global_db_path) as conn:
                self._create_schema(conn)

        if project_tm_path:
            os.makedirs(project_tm_path, exist_ok=True)
            self.project_db_path = os.path.join(project_tm_path, DB_FILE)
            with self._get_db_connection(self.project_db_path) as conn:
                self._create_schema(conn)

    def disconnect_databases(self):
        self.project_db_path = None
        self.global_db_path = None

    def _get_db_connection(self, db_path: str) -> sqlite3.Connection:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _create_schema(self, conn: sqlite3.Connection):
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS translation_units (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_lang TEXT NOT NULL,
                target_lang TEXT NOT NULL,
                source_text TEXT NOT NULL,
                target_text TEXT NOT NULL,
                source_manifest_key TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(source_lang, target_lang, source_text)
            );
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_tm_source ON translation_units (source_lang, target_lang, source_text);")
        conn.commit()

    def delete_tm_entry(self, db_path: str, source_text: str, source_lang: str, target_lang: str) -> bool:
        if not source_text.strip() or not db_path:
            return False

        try:
            with self._get_db_connection(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM translation_units
                    WHERE source_text = ? AND source_lang = ? AND target_lang = ?
                """, (source_text, source_lang, target_lang))
                conn.commit()
                if cursor.rowcount > 0:
                    logger.info(
                        f"Deleted TM entry for '{source_text}' ({source_lang}->{target_lang}) from {os.path.basename(db_path)}")
                    return True
                else:
                    logger.warning(f"Attempted to delete TM entry for '{source_text}', but it was not found.")
                    return False
        except Exception as e:
            logger.error(f"Failed to delete TM entry: {e}", exc_info=True)
            return False

    def get_translation(self, source_text: str, source_lang: str, target_lang: str, db_to_check: str = 'all') -> \
    Optional[str]:
        if db_to_check in ('all', 'project') and self.project_db_path:
            with self._get_db_connection(self.project_db_path) as conn:
                result = self._query_translation_in_db(conn, source_text, source_lang, target_lang)
                if result is not None:
                    return result
        if db_to_check in ('all', 'global') and self.global_db_path:
            with self._get_db_connection(self.global_db_path) as conn:
                return self._query_translation_in_db(conn, source_text, source_lang, target_lang)
        return None

    def get_entry_count_by_source(self, dir_path: str, source_key: str) -> int:
        """获取指定来源的条目数量"""
        if not dir_path or not os.path.exists(dir_path):
            return 0

        db_path = os.path.join(dir_path, DB_FILE)

        if not os.path.exists(db_path):
            return 0

        try:
            with self._get_db_connection(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT COUNT(*) FROM translation_units WHERE source_manifest_key = ?",
                    (source_key,)
                )
                result = cursor.fetchone()
                return result[0] if result else 0
        except Exception as e:
            logger.error(f"Failed to get entry count for source '{source_key}': {e}")
            return 0

    def _query_translation_in_db(self, conn: sqlite3.Connection, source_text: str, source_lang: str,
                                 target_lang: str) -> Optional[str]:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT target_text FROM translation_units WHERE source_text = ? AND source_lang = ? AND target_lang = ?",
            (source_text, source_lang, target_lang)
        )
        row = cursor.fetchone()
        return row['target_text'] if row else None

    def update_tm_entry(self, db_path: str, source_text: str, target_text: str, source_lang: str, target_lang: str,
                        source_key: str = "manual"):
        if not source_text.strip() or not db_path:
            return

        with self._get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO translation_units 
                (source_lang, target_lang, source_text, target_text, source_manifest_key)
                VALUES (?, ?, ?, ?, ?)
            """, (source_lang, target_lang, source_text, target_text, source_key))
            conn.commit()

    def import_from_file(self, source_filepath: str, tm_dir_path: str, source_lang: str, target_lang: str,
                         progress_callback=None) -> Tuple[bool, str]:
        db_path = os.path.join(tm_dir_path, DB_FILE)
        manifest_path = os.path.join(tm_dir_path, MANIFEST_FILE)
        manifest = self._read_manifest(manifest_path)
        file_stats = self._get_file_stats(source_filepath)
        filename = os.path.basename(source_filepath)

        if filename in manifest.get("imported_sources", {}):
            existing_stats = manifest["imported_sources"][filename]
            if all(existing_stats.get(k) == file_stats.get(k) for k in ["filesize", "last_modified", "checksum"]):
                return True, _("This TM file has already been imported and has not changed.")
        try:
            if progress_callback: progress_callback(_("Parsing TM file..."))
            tus_to_import = self._parse_tm_file(source_filepath, source_lang, target_lang)

            if progress_callback: progress_callback(_("Connecting to database..."))
            with self._get_db_connection(db_path) as conn:
                self._merge_tus_into_db(conn, tus_to_import, filename, progress_callback)
            file_stats['import_date'] = datetime.now().isoformat() + "Z"
            file_stats['tu_count'] = len(tus_to_import)
            file_stats['source_lang'] = source_lang
            file_stats['target_lang'] = target_lang
            manifest.setdefault("imported_sources", {})[filename] = file_stats
            self._write_manifest(manifest_path, manifest)

            return True, _("Successfully imported {count} TM entries.").format(count=len(tus_to_import))
        except Exception as e:
            logger.error(f"Failed to import TM file '{source_filepath}': {e}", exc_info=True)
            return False, str(e)

    def get_fuzzy_matches(self, source_text: str, source_lang: str, target_lang: str, limit: int = 5,
                          threshold: float = 0.7) -> List[Dict]:
        all_matches = []
        if self.project_db_path:
            with self._get_db_connection(self.project_db_path) as conn:
                matches = self._query_fuzzy_in_db(conn, source_text, source_lang, target_lang, limit)
                all_matches.extend(matches)
        if self.global_db_path:
            with self._get_db_connection(self.global_db_path) as conn:
                matches = self._query_fuzzy_in_db(conn, source_text, source_lang, target_lang, limit)
                all_matches.extend(matches)
        if not all_matches:
            return []
        unique_matches = {(m['source_text'], m['target_text']): m for m in all_matches}.values()
        scored_matches = []
        for match in unique_matches:
            score = fuzz.ratio(source_text, match['source_text']) / 100.0
            if score >= threshold:
                scored_matches.append({
                    "score": score,
                    "source_text": match['source_text'],
                    "target_text": match['target_text']
                })
        scored_matches.sort(key=lambda x: x['score'], reverse=True)

        return scored_matches[:limit]

    def _query_fuzzy_in_db(self, conn: sqlite3.Connection, source_text: str, source_lang: str, target_lang: str,
                           limit: int) -> List[Dict]:
        cursor = conn.cursor()
        keywords = [word for word in re.findall(r'\b\w+\b', source_text) if len(word) > 3]
        if not keywords:
            keywords = [source_text[:10]]
        like_clauses = " OR ".join(["source_text LIKE ?"] * len(keywords))
        like_params = [f"%{kw}%" for kw in keywords]
        query = f"""
            SELECT source_text, target_text
            FROM translation_units
            WHERE source_lang = ? AND target_lang = ? AND ({like_clauses})
            LIMIT ?
        """
        params = [source_lang, target_lang] + like_params + [limit * 5]
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def _parse_tm_file(self, filepath: str, source_lang: str, target_lang: str) -> List[Dict]:
        _, ext = os.path.splitext(filepath)
        ext = ext.lower()

        if ext == '.xlsx':
            return self._parse_xlsx(filepath, source_lang, target_lang)
        else:
            raise ValueError(_("Unsupported TM file format: {ext}").format(ext=ext))

    def _parse_xlsx(self, filepath: str, source_lang: str, target_lang: str) -> List[Dict]:
        tus = []
        wb = load_workbook(filepath, read_only=True)
        ws = wb.active
        for row in ws.iter_rows(min_row=2, values_only=True):
            if len(row) >= 2 and row[0] is not None and row[1] is not None:
                source_text = str(row[0])
                target_text = str(row[1])
                tus.append({
                    "source_lang": source_lang,
                    "target_lang": target_lang,
                    "source_text": source_text,
                    "target_text": target_text
                })
        return tus

    def _merge_tus_into_db(self, conn: sqlite3.Connection, tus: List[Dict], source_key: str, progress_callback=None):
        cursor = conn.cursor()
        data_to_insert = [
            (
                tu['source_lang'], tu['target_lang'], tu['source_text'],
                tu['target_text'], source_key
            )
            for tu in tus if tu.get('source_text') and tu.get('target_text')
        ]

        if not data_to_insert:
            return

        try:
            cursor.execute("BEGIN TRANSACTION;")
            if progress_callback: progress_callback(
                _("Inserting {count} TM entries...").format(count=len(data_to_insert)))

            cursor.executemany("""
                INSERT OR REPLACE INTO translation_units 
                (source_lang, target_lang, source_text, target_text, source_manifest_key)
                VALUES (?, ?, ?, ?, ?)
            """, data_to_insert)

            conn.commit()
        except Exception as e:
            conn.rollback()
            raise IOError(f"Database operation failed: {e}")

    def remove_source(self, source_key: str, tm_dir_path: str) -> Tuple[bool, str]:
        db_path = os.path.join(tm_dir_path, DB_FILE)
        manifest_path = os.path.join(tm_dir_path, MANIFEST_FILE)

        with self._get_db_connection(db_path) as conn:
            try:
                cursor = conn.cursor()
                cursor.execute("BEGIN TRANSACTION;")

                cursor.execute("DELETE FROM translation_units WHERE source_manifest_key = ?", (source_key,))
                rows_deleted = cursor.rowcount

                conn.commit()

                manifest = self._read_manifest(manifest_path)
                if "imported_sources" in manifest and source_key in manifest["imported_sources"]:
                    del manifest["imported_sources"][source_key]
                    self._write_manifest(manifest_path, manifest)

                return True, _("Successfully removed {count} TM entries from source '{source}'.").format(
                    count=rows_deleted, source=source_key)
            except Exception as e:
                conn.rollback()
                logger.error(f"Failed to remove TM source '{source_key}': {e}", exc_info=True)
                return False, str(e)
    def _read_manifest(self, manifest_path: str) -> Dict:
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"version": 1, "imported_sources": {}}

    def _write_manifest(self, manifest_path: str, manifest_data: Dict):
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest_data, f, indent=4, ensure_ascii=False)

    def _get_file_stats(self, filepath: str) -> Dict:
        stat = os.stat(filepath)
        normalized_filepath = filepath.replace('\\', '/')
        return {
            "filepath": normalized_filepath,
            "filesize": stat.st_size,
            "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat() + "Z",
            "checksum": self._calculate_checksum(filepath)
        }

    def _calculate_checksum(self, filepath: str, hash_algo="sha256") -> str:
        h = hashlib.new(hash_algo)
        with open(filepath, 'rb') as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()