# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import sqlite3
import os
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class CacheViewerService:
    def __init__(self, db_path):
        self.global_db_path = db_path
        self.project_db_path = None  # Cache is always global

    def connect_databases(self, global_path, project_path=None):
        pass  # No-op, path is fixed

    def disconnect_databases(self):
        pass

    @contextmanager
    def _get_db_connection(self):
        conn = None
        try:
            conn = sqlite3.connect(self.global_db_path, timeout=10.0)
            conn.row_factory = sqlite3.Row
            yield conn
        except Exception as e:
            logger.error(f"Cache viewer db error: {e}")
            raise
        finally:
            if conn: conn.close()

    def get_distinct_languages(self, db_path):
        # Cache doesn't have languages, return dummy
        return ["Text"], ["Vector"]

    def get_entry_count_by_source(self, dir_path, source_key):
        # source_key here is model_name
        try:
            with self._get_db_connection() as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM embeddings WHERE model_name = ?", (source_key,))
                return cursor.fetchone()[0]
        except:
            return 0

    def count_entries(self, db_path, source_key=None, src_lang=None, tgt_lang=None, search_term=None):
        query = "SELECT COUNT(*) FROM embeddings WHERE 1=1"
        params = []

        if source_key and source_key != "All":
            query += " AND model_name = ?"
            params.append(source_key)

        if search_term:
            query += " AND (text LIKE ? OR hash LIKE ?)"
            wildcard = f"%{search_term}%"
            params.extend([wildcard, wildcard])

        try:
            with self._get_db_connection() as conn:
                cursor = conn.execute(query, params)
                return cursor.fetchone()[0]
        except:
            return 0

    def query_entries(self, db_path, page=1, page_size=50, source_key=None, src_lang=None, tgt_lang=None,
                      search_term=None):
        offset = (page - 1) * page_size
        query = "SELECT hash, model_name, text, length(vector) as vec_len FROM embeddings WHERE 1=1"
        params = []

        if source_key and source_key != "All":
            query += " AND model_name = ?"
            params.append(source_key)

        if search_term:
            query += " AND (text LIKE ? OR hash LIKE ?)"
            wildcard = f"%{search_term}%"
            params.extend([wildcard, wildcard])

        query += " LIMIT ? OFFSET ?"
        params.extend([page_size, offset])

        results = []
        try:
            with self._get_db_connection() as conn:
                cursor = conn.execute(query, params)
                for row in cursor:
                    # Map to ResourceViewerDialog columns
                    # source_text -> text (or hash if text is null)
                    # target_text -> Vector info
                    # source_manifest_key -> model_name
                    # source_lang -> "Text"
                    # target_lang -> "Vector"

                    display_text = row['text'] if row['text'] else f"Hash: {row['hash']}"
                    vec_info = f"Blob ({row['vec_len']} bytes)"

                    results.append({
                        'id': row['hash'][:8],
                        'source_text': display_text,
                        'target_text': vec_info,
                        'source_lang': "Text",
                        'target_lang': "Vector",
                        'source_manifest_key': row['model_name']
                    })
        except Exception as e:
            logger.error(f"Cache query failed: {e}")

        return results

    def _read_manifest(self, path):
        models = {}
        try:
            if os.path.exists(self.global_db_path):
                with self._get_db_connection() as conn:
                    cursor = conn.execute("SELECT DISTINCT model_name FROM embeddings")
                    for row in cursor:
                        models[row[0]] = {}
        except:
            pass
        return {"imported_sources": models}