# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import sqlite3
import numpy as np
import hashlib
import time
import os
import gc
import threading
import logging

logger = logging.getLogger(__name__)

class CacheManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        try:
            with self._lock, sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS embeddings (
                        hash TEXT NOT NULL,
                        model_name TEXT NOT NULL,
                        vector BLOB NOT NULL,
                        last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (hash, model_name)
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_model ON embeddings (model_name)")
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to init cache db: {e}")

    def get_vectors(self, texts: list, model_name: str) -> dict:
        if not texts: return {}
        hashes = {self._hash_text(t): t for t in texts}
        result = {}
        try:
            with self._lock, sqlite3.connect(self.db_path) as conn: # [ADD] lock
                hash_keys = list(hashes.keys())
                batch_size = 900
                for i in range(0, len(hash_keys), batch_size):
                    batch = hash_keys[i:i+batch_size]
                    placeholders = ','.join('?' for _ in batch)
                    query = f"SELECT hash, vector FROM embeddings WHERE model_name = ? AND hash IN ({placeholders})"
                    cursor = conn.execute(query, [model_name] + batch)
                    for row in cursor:
                        h, blob = row
                        if h in hashes:
                            text = hashes[h]
                            vector = np.frombuffer(blob, dtype=np.float32)
                            result[text] = vector
        except Exception as e:
            logger.error(f"Cache read error: {e}")
        return result

    def save_vectors(self, text_vector_map: dict, model_name: str):
        if not text_vector_map: return
        data_to_insert = []
        for text, vector in text_vector_map.items():
            h = self._hash_text(text)
            blob = vector.tobytes()
            data_to_insert.append((h, model_name, blob))
        try:
            with self._lock, sqlite3.connect(self.db_path) as conn:
                conn.executemany(
                    "INSERT OR IGNORE INTO embeddings (hash, model_name, vector) VALUES (?, ?, ?)",
                    data_to_insert
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Cache write error: {e}")

    def clear_all_cache(self):
        try:
            with self._lock:
                gc.collect()
                max_retries = 5
                for i in range(max_retries):
                    try:
                        if os.path.exists(self.db_path):
                            os.remove(self.db_path)
                        wal_path = self.db_path + "-wal"
                        shm_path = self.db_path + "-shm"
                        if os.path.exists(wal_path): os.remove(wal_path)
                        if os.path.exists(shm_path): os.remove(shm_path)
                        logger.info("Cache database file removed successfully.")
                        break
                    except PermissionError as e:
                        if i < max_retries - 1:
                            logger.warning(f"Attempt {i + 1} to remove cache failed, retrying in 100ms...")
                            time.sleep(0.1)
                        else:
                            logger.error("Failed to remove cache file after multiple retries.")
                            raise e
                self._init_db()
                logger.info("Cache database re-initialized.")
            return True, ""
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}", exc_info=True)
            return False, str(e)

    def clear_model_cache(self, model_name: str):
        try:
            with self._lock, sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM embeddings WHERE model_name = ?", (model_name,))
                conn.execute("VACUUM")
                conn.commit()
        except Exception as e:
            logger.error(f"Cache clear error: {e}")

    @staticmethod
    def _hash_text(text: str) -> str:
        return hashlib.md5(text.encode('utf-8')).hexdigest()