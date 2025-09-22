# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import sqlite3
import os
import json
import hashlib
import logging
import threading
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from contextlib import contextmanager
from utils.tbx_parser import TBXParser
from utils.localization import _

logger = logging.getLogger(__name__)

MANIFEST_FILE = "manifest.json"
DB_FILE = "glossary.db"


class GlossaryService:
    def __init__(self):
        self.project_db_path: Optional[str] = None
        self.global_db_path: Optional[str] = None
        self._lock = threading.RLock()  # 线程安全锁

    def connect_databases(self, global_glossary_path: str, project_glossary_path: Optional[str] = None):
        with self._lock:
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
        with self._lock:
            self.project_db_path = None
            self.global_db_path = None

    @contextmanager
    def _get_db_connection(self, db_path: str):
        """线程安全的数据库连接上下文管理器"""
        conn = None
        try:
            conn = sqlite3.connect(
                db_path,
                timeout=30.0,
                check_same_thread=False,
                isolation_level=None
            )
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=10000")
            conn.execute("PRAGMA temp_store=memory")
            conn.row_factory = sqlite3.Row
            yield conn

        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            logger.error(f"Database connection error for {db_path}: {e}")
            raise
        finally:
            if conn:
                try:
                    conn.close()
                except Exception as e:
                    logger.warning(f"Error closing database connection: {e}")

    def _create_schema(self, conn: sqlite3.Connection):
        """创建数据库结构"""
        try:
            cursor = conn.cursor()

            # 开始事务
            cursor.execute("BEGIN IMMEDIATE TRANSACTION")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS terms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    term_text TEXT NOT NULL,
                    term_text_lower TEXT NOT NULL,
                    language_code TEXT NOT NULL,
                    case_sensitive INTEGER NOT NULL DEFAULT 0,
                    comment TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(term_text, language_code)
                );
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS term_translations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_term_id INTEGER NOT NULL,
                    target_term_id INTEGER NOT NULL,
                    is_bidirectional INTEGER NOT NULL DEFAULT 0,
                    relationship_type TEXT DEFAULT 'translation',
                    confidence_score REAL DEFAULT 1.0,
                    comment TEXT,
                    source_manifest_key TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (source_term_id) REFERENCES terms (id) ON DELETE CASCADE,
                    FOREIGN KEY (target_term_id) REFERENCES terms (id) ON DELETE CASCADE,
                    UNIQUE(source_term_id, target_term_id)
                );
            """)

            # 创建索引
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_terms_text_lower_lang ON terms (term_text_lower, language_code);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_translations_source ON term_translations (source_term_id);")
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_translations_target_bidirectional ON term_translations (target_term_id, is_bidirectional);")
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_translations_source_manifest ON term_translations (source_manifest_key);")

            cursor.execute("COMMIT")

        except Exception as e:
            cursor.execute("ROLLBACK")
            logger.error(f"Schema creation failed: {e}")
            raise

    def get_translations(self, term_text: str, source_lang: str, target_lang: str = None,
                         include_reverse: bool = True) -> Optional[List[Dict]]:
        with self._lock:
            if self.project_db_path:
                try:
                    with self._get_db_connection(self.project_db_path) as conn:
                        result = self._query_translations_in_db(conn, term_text, source_lang, target_lang,
                                                                include_reverse)
                        if result:
                            return result
                except Exception as e:
                    logger.warning(f"Project database query failed: {e}")

            if self.global_db_path:
                try:
                    with self._get_db_connection(self.global_db_path) as conn:
                        return self._query_translations_in_db(conn, term_text, source_lang, target_lang,
                                                              include_reverse)
                except Exception as e:
                    logger.warning(f"Global database query failed: {e}")

            return None

    def _query_translations_in_db(self, conn: sqlite3.Connection, term_text: str, source_lang: str,
                                  target_lang: str = None, include_reverse: bool = True) -> Optional[List[Dict]]:
        try:
            cursor = conn.cursor()

            base_query = """
            SELECT DISTINCT
                t_target.term_text as target_term,
                t_target.language_code as target_lang,
                tt.comment,
                tt.confidence_score,
                'forward' as direction
            FROM terms t_source
            JOIN term_translations tt ON t_source.id = tt.source_term_id
            JOIN terms t_target ON tt.target_term_id = t_target.id
            WHERE t_source.term_text_lower = ? 
            AND t_source.language_code = ?
            """

            params = [term_text.lower(), source_lang]

            if target_lang:
                base_query += " AND t_target.language_code = ?"
                params.append(target_lang)

            if include_reverse:
                reverse_query = """
                UNION
                SELECT DISTINCT
                    t_source.term_text as target_term,
                    t_source.language_code as target_lang,
                    tt.comment,
                    tt.confidence_score,
                    'reverse' as direction
                FROM terms t_target
                JOIN term_translations tt ON t_target.id = tt.target_term_id
                JOIN terms t_source ON tt.source_term_id = t_source.id
                WHERE t_target.term_text_lower = ? 
                AND t_target.language_code = ?
                AND tt.is_bidirectional = 1
                """

                base_query += reverse_query
                params.extend([term_text.lower(), source_lang])

                if target_lang:
                    base_query += " AND t_source.language_code = ?"
                    params.append(target_lang)

            cursor.execute(base_query, params)
            results = [dict(row) for row in cursor.fetchall()]
            return results if results else None

        except Exception as e:
            logger.error(f"Query translations failed: {e}")
            return None

    def import_from_tbx(self, tbx_filepath: str, glossary_dir_path: str,
                        source_lang: str, target_langs: List[str], is_bidirectional: bool,
                        lang_mapping: Dict[str, str], progress_callback=None) -> Tuple[bool, str]:
        """导入TBX文件"""
        try:
            with self._lock:
                db_path = os.path.join(glossary_dir_path, DB_FILE)
                manifest_path = os.path.join(glossary_dir_path, MANIFEST_FILE)

                # 确保目录存在
                os.makedirs(glossary_dir_path, exist_ok=True)

                manifest = self._read_manifest(manifest_path)
                file_stats = self._get_file_stats(tbx_filepath)
                filename = os.path.basename(tbx_filepath)

                # 检查文件是否已导入
                if filename in manifest.get("imported_sources", {}):
                    existing_stats = manifest["imported_sources"][filename]
                    if all(existing_stats.get(k) == file_stats.get(k) for k in
                           ["filesize", "last_modified", "checksum"]):
                        return True, _("This file has already been imported and has not changed.")

                # 解析TBX文件
                if progress_callback:
                    progress_callback(_("Parsing TBX file..."))

                terms_to_import = self._parse_tbx(tbx_filepath)
                term_count = len(terms_to_import)

                if term_count == 0:
                    return False, _("No valid terms found in the TBX file.")

                # 导入到数据库
                with self._get_db_connection(db_path) as conn:
                    self._create_schema(conn)

                    self._merge_terms_into_db(
                        conn, terms_to_import, filename, source_lang,
                        target_langs, is_bidirectional, lang_mapping, progress_callback
                    )

                # 更新manifest
                file_stats['import_date'] = datetime.now().isoformat() + "Z"
                file_stats['term_count'] = term_count
                file_stats['source_lang'] = source_lang
                file_stats['target_langs'] = target_langs
                file_stats['is_bidirectional'] = is_bidirectional
                manifest.setdefault("imported_sources", {})[filename] = file_stats
                self._write_manifest(manifest_path, manifest)

                return True, _("Successfully imported relationships for {count} entries.").format(count=term_count)

        except Exception as e:
            logger.error(f"Failed to import TBX file '{tbx_filepath}': {e}", exc_info=True)
            return False, f"Import failed: {str(e)}"

    def _parse_tbx(self, filepath: str) -> List[Dict]:
        """解析TBX文件"""
        try:
            parser = TBXParser()
            parse_result = parser.parse_tbx(filepath)
            return parse_result.get("term_entries", [])
        except Exception as e:
            logger.error(f"TBXParser failed for file '{filepath}': {e}", exc_info=True)
            raise

    def _merge_terms_into_db(self, conn: sqlite3.Connection, term_entries: List[Dict], source_key: str,
                             source_lang_code: str, target_lang_codes: List[str], is_bidirectional: bool,
                             lang_mapping: Dict[str, str], progress_callback=None):
        """合并术语到数据库"""
        try:
            cursor = conn.cursor()

            if progress_callback:
                progress_callback(_("Preparing data for database..."))

            # 开始事务
            cursor.execute("BEGIN IMMEDIATE TRANSACTION")

            try:
                # 收集所有需要插入的术语
                new_terms_to_insert = []
                seen_terms_in_batch = set()

                for lang_map in term_entries:
                    for lang_in_file, terms in lang_map.items():
                        lexisync_lang = lang_mapping.get(lang_in_file)
                        if not lexisync_lang:
                            continue

                        for term_text in terms:
                            if not term_text or not term_text.strip():
                                continue

                            key = (term_text.lower(), lexisync_lang)
                            if key not in seen_terms_in_batch:
                                new_terms_to_insert.append((
                                    term_text.strip(),
                                    term_text.strip().lower(),
                                    lexisync_lang,
                                    0,
                                    ""
                                ))
                                seen_terms_in_batch.add(key)

                # 批量插入术语
                if new_terms_to_insert:
                    if progress_callback:
                        progress_callback(_("Inserting new terms..."))

                    cursor.executemany(
                        "INSERT OR IGNORE INTO terms (term_text, term_text_lower, language_code, case_sensitive, comment) VALUES (?, ?, ?, ?, ?)",
                        new_terms_to_insert
                    )

                # 获取所有术语ID映射
                cursor.execute("SELECT term_text_lower, language_code, id FROM terms")
                all_terms_map = {
                    (row['term_text_lower'], row['language_code']): row['id']
                    for row in cursor.fetchall()
                }

                # 准备翻译关系
                new_translations_to_insert = []
                seen_translations_in_batch = set()

                for lang_map in term_entries:
                    # 获取源语言术语
                    source_terms_in_file = []
                    for lang_in_file, terms in lang_map.items():
                        if lang_mapping.get(lang_in_file) == source_lang_code:
                            source_terms_in_file.extend([t.strip() for t in terms if t and t.strip()])

                    if not source_terms_in_file:
                        continue

                    # 为每个目标语言创建翻译关系
                    for target_lang_code in target_lang_codes:
                        target_terms_in_file = []
                        for lang_in_file, terms in lang_map.items():
                            if lang_mapping.get(lang_in_file) == target_lang_code:
                                target_terms_in_file.extend([t.strip() for t in terms if t and t.strip()])

                        if not target_terms_in_file:
                            continue

                        # 创建术语对
                        for s_term in source_terms_in_file:
                            for t_term in target_terms_in_file:
                                s_id = all_terms_map.get((s_term.lower(), source_lang_code))
                                t_id = all_terms_map.get((t_term.lower(), target_lang_code))

                                if s_id and t_id and s_id != t_id:
                                    # 使用排序后的ID对作为唯一标识
                                    pair = tuple(sorted((s_id, t_id)))
                                    if pair not in seen_translations_in_batch:
                                        new_translations_to_insert.append((
                                            s_id, t_id, int(is_bidirectional), source_key
                                        ))
                                        seen_translations_in_batch.add(pair)

                # 批量插入翻译关系
                if new_translations_to_insert:
                    if progress_callback:
                        progress_callback(_("Inserting translations..."))

                    cursor.executemany(
                        "INSERT OR IGNORE INTO term_translations (source_term_id, target_term_id, is_bidirectional, source_manifest_key) VALUES (?, ?, ?, ?)",
                        new_translations_to_insert
                    )
                cursor.execute("COMMIT")

                if progress_callback:
                    progress_callback(_("Database update complete!"))

            except Exception as e:
                cursor.execute("ROLLBACK")
                raise

        except Exception as e:
            logger.error(f"Database merge failed: {e}", exc_info=True)
            raise IOError(f"Database operation failed: {e}")

    def remove_source(self, source_key: str, glossary_dir_path: str) -> Tuple[bool, str]:
        """删除指定源的所有术语"""
        try:
            with self._lock:
                db_path = os.path.join(glossary_dir_path, DB_FILE)
                manifest_path = os.path.join(glossary_dir_path, MANIFEST_FILE)

                with self._get_db_connection(db_path) as conn:
                    cursor = conn.cursor()

                    # 开始事务
                    cursor.execute("BEGIN IMMEDIATE TRANSACTION")

                    try:
                        logger.info(f"Starting transaction to remove source: {source_key}")

                        # 删除翻译关系
                        cursor.execute(
                            "DELETE FROM term_translations WHERE source_manifest_key = ?",
                            (source_key,)
                        )
                        rows_deleted = cursor.rowcount
                        logger.info(f"Deleted {rows_deleted} translation relationships from source: {source_key}")

                        # 清理孤立的术语
                        cursor.execute("""
                            DELETE FROM terms 
                            WHERE id NOT IN (
                                SELECT DISTINCT source_term_id FROM term_translations
                                UNION
                                SELECT DISTINCT target_term_id FROM term_translations
                            )
                        """)
                        orphaned_terms_cleaned = cursor.rowcount
                        if orphaned_terms_cleaned > 0:
                            logger.info(f"Cleaned up {orphaned_terms_cleaned} orphaned terms.")

                        cursor.execute("COMMIT")

                        manifest = self._read_manifest(manifest_path)
                        if "imported_sources" in manifest and source_key in manifest["imported_sources"]:
                            del manifest["imported_sources"][source_key]
                            self._write_manifest(manifest_path, manifest)

                        return True, _("Successfully removed {count} translations from source '{source}'.").format(
                            count=rows_deleted, source=source_key)

                    except Exception as e:
                        cursor.execute("ROLLBACK")
                        raise

        except Exception as e:
            logger.error(f"Failed to remove source '{source_key}': {e}", exc_info=True)
            return False, f"Removal failed: {str(e)}"

    def get_translations_batch(self, words: List[str], source_lang: str = "auto", target_lang: str = None,
                               include_reverse: bool = True) -> Dict:
        if not words:
            return {}

        with self._lock:
            all_matches = {}

            # 分块查询项目数据库
            chunk_size = 5000
            word_chunks = [words[i:i + chunk_size] for i in range(0, len(words), chunk_size)]

            for chunk in word_chunks:
                if self.project_db_path:
                    try:
                        with self._get_db_connection(self.project_db_path) as conn:
                            matches = self._query_translations_batch_in_db(conn, chunk, source_lang, target_lang,
                                                                           include_reverse)
                            all_matches.update(matches)
                    except Exception as e:
                        logger.warning(f"Project database batch query failed for a chunk: {e}")

                if self.global_db_path:
                    remaining_words_in_chunk = [w for w in chunk if w not in all_matches]
                    if remaining_words_in_chunk:
                        try:
                            with self._get_db_connection(self.global_db_path) as conn:
                                matches = self._query_translations_batch_in_db(conn, remaining_words_in_chunk, source_lang,
                                                                               target_lang, include_reverse)
                                all_matches.update(matches)
                        except Exception as e:
                            logger.warning(f"Global database batch query failed for a chunk: {e}")
            return all_matches

    def _query_translations_batch_in_db(self, conn: sqlite3.Connection, words: List[str],
                                        source_lang: str = "auto", target_lang: str = None,
                                        include_reverse: bool = True) -> Dict:
        """在指定数据库中批量查询翻译"""
        if not words:
            return {}

        try:
            words_lower = [w.lower() for w in words]
            placeholders = ','.join('?' for _ in words_lower)

            base_query = f"""
            SELECT 
                t_source.term_text_lower as source_key,
                t_target.term_text as target_term,
                t_target.language_code as target_lang,
                tt.comment,
                tt.confidence_score,
                'forward' as direction
            FROM terms t_source
            JOIN term_translations tt ON t_source.id = tt.source_term_id
            JOIN terms t_target ON tt.target_term_id = t_target.id
            WHERE t_source.term_text_lower IN ({placeholders})
            """

            params = words_lower[:]

            if source_lang != "auto":
                base_query += " AND t_source.language_code = ?"
                params.append(source_lang)

            if target_lang:
                base_query += " AND t_target.language_code = ?"
                params.append(target_lang)

            if include_reverse:
                reverse_query = f"""
                UNION
                SELECT 
                    t_target.term_text_lower as source_key,
                    t_source.term_text as target_term,
                    t_source.language_code as target_lang,
                    tt.comment,
                    tt.confidence_score,
                    'reverse' as direction
                FROM terms t_target
                JOIN term_translations tt ON t_target.id = tt.target_term_id
                JOIN terms t_source ON tt.source_term_id = t_source.id
                WHERE t_target.term_text_lower IN ({placeholders})
                AND tt.is_bidirectional = 1
                """

                base_query += reverse_query
                params.extend(words_lower)

                if source_lang != "auto":
                    base_query += " AND t_target.language_code = ?"
                    params.append(source_lang)

                if target_lang:
                    base_query += " AND t_source.language_code = ?"
                    params.append(target_lang)

            cursor = conn.cursor()
            cursor.execute(base_query, params)

            results = {}
            for row in cursor.fetchall():
                source_key = row['source_key']
                if source_key not in results:
                    results[source_key] = {"translations": []}
                results[source_key]["translations"].append({
                    "target": row["target_term"],
                    "target_lang": row["target_lang"],
                    "comment": row["comment"],
                    "confidence_score": row["confidence_score"],
                    "direction": row["direction"]
                })

            logger.debug(f"Found {len(results)} matches in batch query.")
            return results

        except Exception as e:
            logger.error(f"Batch query failed: {e}")
            return {}

    def _read_manifest(self, manifest_path: str) -> Dict:
        """读取manifest文件"""
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.debug(f"Manifest file not found or invalid, creating new: {e}")
            return {"version": 2, "imported_sources": {}}

    def _write_manifest(self, manifest_path: str, manifest_data: Dict):
        """写入manifest文件"""
        try:
            os.makedirs(os.path.dirname(manifest_path), exist_ok=True)

            with open(manifest_path, 'w', encoding='utf-8') as f:
                json.dump(manifest_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to write manifest: {e}")
            raise

    def _get_file_stats(self, filepath: str) -> Dict:
        """获取文件统计信息"""
        try:
            stat = os.stat(filepath)
            normalized_filepath = filepath.replace('\\', '/')
            return {
                "filepath": normalized_filepath,
                "filesize": stat.st_size,
                "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat() + "Z",
                "checksum": self._calculate_checksum(filepath)
            }
        except Exception as e:
            logger.error(f"Failed to get file stats for {filepath}: {e}")
            raise

    def _calculate_checksum(self, filepath: str, hash_algo="sha256") -> str:
        """计算文件校验和"""
        try:
            h = hashlib.new(hash_algo)
            with open(filepath, 'rb') as f:
                while chunk := f.read(8192):
                    h.update(chunk)
            return h.hexdigest()
        except Exception as e:
            logger.error(f"Failed to calculate checksum for {filepath}: {e}")
            raise