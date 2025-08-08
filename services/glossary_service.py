# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import sqlite3
import re
import os
import json
import hashlib
import logging
from datetime import datetime
from xml.etree import ElementTree as ET
from typing import List, Dict, Tuple, Optional
from utils.tbx_parser import TBXParser
from utils.localization import _

logger = logging.getLogger(__name__)

MANIFEST_FILE = "manifest.json"
DB_FILE = "glossary.db"


class GlossaryService:
    def __init__(self):
        self.project_db_path: Optional[str] = None
        self.global_db_path: Optional[str] = None

    def connect_databases(self, global_glossary_path: str, project_glossary_path: Optional[str] = None):
        self.disconnect_databases()

        os.makedirs(global_glossary_path, exist_ok=True)
        self.global_db_path = os.path.join(global_glossary_path, DB_FILE)
        with self._get_db_connection(self.global_db_path) as conn:
            self._create_schema(conn)

        if project_glossary_path:
            os.makedirs(project_glossary_path, exist_ok=True)
            self.project_db_path = os.path.join(project_glossary_path, DB_FILE)
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
            CREATE TABLE IF NOT EXISTS terms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_term TEXT NOT NULL UNIQUE,
                source_term_lower TEXT NOT NULL,
                case_sensitive INTEGER NOT NULL DEFAULT 0,
                comment TEXT, 
                source_manifest_key TEXT NOT NULL
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS translations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                term_id INTEGER NOT NULL,
                target_term TEXT NOT NULL,
                comment TEXT,
                FOREIGN KEY (term_id) REFERENCES terms (id) ON DELETE CASCADE
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_source_term_lower ON terms (source_term_lower);")
        conn.commit()

    def get_term(self, source_text: str, case_sensitive: bool = False) -> Optional[List[Dict]]:
        if self.project_db_path:
            with self._get_db_connection(self.project_db_path) as conn:
                result = self._query_term_in_db(conn, source_text, case_sensitive)
                if result:
                    return result

        if self.global_db_path:
            with self._get_db_connection(self.global_db_path) as conn:
                return self._query_term_in_db(conn, source_text, case_sensitive)
        return None

    def _query_term_in_db(self, conn: sqlite3.Connection, source_text: str, case_sensitive: bool) -> Optional[List[Dict]]:
        cursor = conn.cursor()
        if case_sensitive:
            cursor.execute("SELECT id FROM terms WHERE source_term = ?", (source_text,))
        else:
            cursor.execute("SELECT id FROM terms WHERE source_term_lower = ?", (source_text.lower(),))

        term_row = cursor.fetchone()
        if not term_row:
            return None

        term_id = term_row['id']
        cursor.execute("SELECT target_term, comment FROM translations WHERE term_id = ?", (term_id,))
        translations = [{"target": row["target_term"], "comment": row["comment"]} for row in cursor.fetchall()]
        return translations

    def import_from_tbx(self, tbx_filepath: str, glossary_dir_path: str, progress_callback=None) -> Tuple[bool, str]:
        db_path = os.path.join(glossary_dir_path, DB_FILE)
        manifest_path = os.path.join(glossary_dir_path, MANIFEST_FILE)
        manifest = self._read_manifest(manifest_path)
        file_stats = self._get_file_stats(tbx_filepath)
        filename = os.path.basename(tbx_filepath)

        if filename in manifest.get("imported_sources", {}):
            existing_stats = manifest["imported_sources"][filename]
            if all(existing_stats.get(k) == file_stats.get(k) for k in ["filesize", "last_modified", "checksum"]):
                return True, _("This file has already been imported and has not changed.")

        try:
            if progress_callback: progress_callback(_("Parsing TBX file..."))
            terms_to_import = self._parse_tbx(tbx_filepath)
            term_count = len(terms_to_import)
            if progress_callback: progress_callback(_("Connecting to database..."))
            with self._get_db_connection(db_path) as conn:
                self._merge_terms_into_db(conn, terms_to_import, filename, progress_callback)
            file_stats['import_date'] = datetime.now().isoformat() + "Z"
            file_stats['term_count'] = term_count
            manifest.setdefault("imported_sources", {})[filename] = file_stats
            self._write_manifest(manifest_path, manifest)
            return True, _("Successfully imported {count} terms.").format(count=len(terms_to_import))
        except Exception as e:
            logger.error(f"Failed to import TBX file '{tbx_filepath}': {e}", exc_info=True)
            return False, str(e)
        finally:
            if 'conn' in locals() and conn:
                conn.close()

    def _parse_tbx(self, filepath: str) -> List[Dict]:
        try:
            parser = TBXParser()
            terms = parser.parse_tbx(filepath)
            return terms
        except Exception as e:
            logger.error(f"UniversalTBXParser failed for file '{filepath}': {e}", exc_info=True)
            raise e

    def _merge_terms_into_db(self, conn: sqlite3.Connection, terms: List[Dict], source_key: str, progress_callback=None):
        cursor = conn.cursor()
        total = len(terms)
        try:
            if progress_callback: progress_callback(_("Preparing data for database..."))

            cursor.execute("SELECT source_term_lower, id FROM terms")
            existing_terms_map = {row['source_term_lower']: row['id'] for row in cursor.fetchall()}

            new_terms_to_insert = []
            new_translations_to_insert = []
            seen_in_this_batch = set()

            if progress_callback: progress_callback(_("Analyzing new and existing terms..."))

            for i, term_data in enumerate(terms):
                source = term_data["source"]
                source_lower = source.lower()

                if source_lower in existing_terms_map:
                    term_id = existing_terms_map[source_lower]
                    cursor.execute("SELECT target_term FROM translations WHERE term_id = ?", (term_id,))
                    existing_targets = {row['target_term'] for row in cursor.fetchall()}

                    for trans in term_data["translations"]:
                        if trans["target"] not in existing_targets:
                            new_translations_to_insert.append(
                                (term_id, trans["target"], trans["comment"])
                            )
                elif source_lower not in seen_in_this_batch:
                    new_terms_to_insert.append(
                        (source, source_lower, term_data["case_sensitive"], term_data["comment"], source_key)
                    )
                    seen_in_this_batch.add(source_lower)

            cursor.execute("BEGIN TRANSACTION;")

            if new_terms_to_insert:
                if progress_callback: progress_callback(
                    _("Inserting {count} new source terms...").format(count=len(new_terms_to_insert)))
                cursor.executemany(
                    "INSERT INTO terms (source_term, source_term_lower, case_sensitive, comment, source_manifest_key) VALUES (?, ?, ?, ?, ?)",
                    new_terms_to_insert
                )

            if progress_callback: progress_callback(_("Fetching new term IDs..."))
            cursor.execute("SELECT source_term_lower, id FROM terms")
            all_terms_map = {row['source_term_lower']: row['id'] for row in cursor.fetchall()}
            for term_data in terms:
                source_lower = term_data["source"].lower()
                if source_lower in seen_in_this_batch:
                    term_id = all_terms_map.get(source_lower)
                    if term_id:
                        for trans in term_data["translations"]:
                            new_translations_to_insert.append(
                                (term_id, trans["target"], trans["comment"])
                            )

            if new_translations_to_insert:
                if progress_callback: progress_callback(
                    _("Inserting {count} new translations...").format(count=len(new_translations_to_insert)))
                cursor.executemany(
                    "INSERT INTO translations (term_id, target_term, comment) VALUES (?, ?, ?)",
                    new_translations_to_insert
                )

            conn.commit()
            if progress_callback: progress_callback(_("Database update complete!"))

        except Exception as e:
            conn.rollback()
            raise IOError(f"Database operation failed: {e}")

    def remove_source(self, source_key: str, glossary_dir_path: str) -> Tuple[bool, str]:
        db_path = os.path.join(glossary_dir_path, DB_FILE)
        manifest_path = os.path.join(glossary_dir_path, MANIFEST_FILE)

        with self._get_db_connection(db_path) as conn:
            try:
                cursor = conn.cursor()
                cursor.execute("BEGIN TRANSACTION;")
                cursor.execute("DELETE FROM terms WHERE source_manifest_key = ?", (source_key,))
                rows_deleted = cursor.rowcount
                cursor.execute("""
                    DELETE FROM translations 
                    WHERE term_id NOT IN (SELECT id FROM terms)
                """)

                conn.commit()
                manifest = self._read_manifest(manifest_path)
                if "imported_sources" in manifest and source_key in manifest["imported_sources"]:
                    del manifest["imported_sources"][source_key]
                    self._write_manifest(manifest_path, manifest)

                return True, _("Successfully removed {count} terms from source '{source}'.").format(count=rows_deleted,
                                                                                                    source=source_key)

            except Exception as e:
                conn.rollback()
                logger.error(f"Failed to remove source '{source_key}': {e}", exc_info=True)
                return False, str(e)
            finally:
                if conn:
                    conn.close()

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
        return {
            "filepath": filepath,
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

    def get_terms_batch(self, words: List[str]) -> Dict:
        """Efficiently gets all terms for a list of words."""
        if not words:
            return {}

        all_matches = {}

        if self.project_db_path:
            with self._get_db_connection(self.project_db_path) as conn:
                matches = self._query_terms_batch_in_db(conn, words)
                all_matches.update(matches)

        if self.global_db_path:
            remaining_words = [w for w in words if w not in all_matches]
            if remaining_words:
                with self._get_db_connection(self.global_db_path) as conn:
                    matches = self._query_terms_batch_in_db(conn, remaining_words)
                    all_matches.update(matches)
        return all_matches

    def _query_terms_batch_in_db(self, conn: sqlite3.Connection, words: List[str]) -> Dict:
        if not words:
            return {}
        placeholders = ','.join('?' for _ in words)
        query = f"""
            SELECT t.source_term_lower, tr.target_term, tr.comment
            FROM terms t
            JOIN translations tr ON t.id = tr.term_id
            WHERE t.source_term_lower IN ({placeholders})
        """
        cursor = conn.cursor()
        cursor.execute(query, words)
        results = {}
        for row in cursor.fetchall():
            source_lower = row['source_term_lower']
            if source_lower not in results:
                results[source_lower] = {"translations": []}
            results[source_lower]["translations"].append({
                "target": row["target_term"],
                "comment": row["comment"]
            })
        logger.debug(f"  -> Found {len(results)} matches.")
        return results