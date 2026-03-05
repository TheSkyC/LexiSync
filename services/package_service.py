# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import os
import json
import logging
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import QObject, Signal, QThread

logger = logging.getLogger(__name__)

try:
    import pyzipper

    HAS_PYZIPPER = True
except ImportError:
    import zipfile as pyzipper

    HAS_PYZIPPER = False
    logger.warning("pyzipper not installed. Password protection for .lexipack is disabled.")


class PackageWorker(QObject):
    progress = Signal(int, str)
    finished = Signal(bool, str)

    def __init__(self, project_path, export_path, options):
        super().__init__()
        self.project_path = Path(project_path)
        self.export_path = export_path
        self.options = options  # dict: langs, include_tm, include_glossary, password
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            self.progress.emit(5, "Collecting files...")
            files_to_pack = self._collect_files()

            self.progress.emit(10, "Calculating project statistics...")
            pack_info = self._generate_pack_info(files_to_pack)

            if self._is_cancelled: return

            self.progress.emit(15, "Initializing archive...")

            # Setup ZipFile
            if HAS_PYZIPPER and self.options.get('password'):
                zf = pyzipper.AESZipFile(self.export_path, 'w', compression=pyzipper.ZIP_DEFLATED)
            else:
                zf = pyzipper.ZipFile(self.export_path, 'w', compression=pyzipper.ZIP_DEFLATED)

            with zf:
                # 1. Write pack_info.json (UNENCRYPTED for preview)
                zf.writestr('pack_info.json', json.dumps(pack_info, indent=4, ensure_ascii=False))

                # 2. Enable encryption for the rest of the files
                if HAS_PYZIPPER and self.options.get('password'):
                    zf.setpassword(self.options['password'].encode('utf-8'))
                    zf.setencryption(pyzipper.WZ_AES, nbits=256)

                # 3. Collect files to pack
                total_files = len(files_to_pack)
                for i, file_path in enumerate(files_to_pack):
                    if self._is_cancelled:
                        raise InterruptedError("Packaging cancelled by user.")

                    arcname = file_path.relative_to(self.project_path)
                    zf.write(file_path, arcname)

                    prog = 15 + int((i / total_files) * 80)
                    self.progress.emit(prog, f"Packing: {arcname.name}")

            self.progress.emit(100, "Packaging complete.")
            self.finished.emit(True, self.export_path)

        except Exception as e:
            logger.error(f"Packaging failed: {e}", exc_info=True)
            # Cleanup partial file
            if os.path.exists(self.export_path):
                try:
                    os.remove(self.export_path)
                except:
                    pass
            self.finished.emit(False, str(e))

    def _generate_pack_info(self, files_to_pack):
        """
        Generates rich metadata for the package.
        files_to_pack: List of Path objects that will be included in the zip.
        """
        with open(self.project_path / "project.json", 'r', encoding='utf-8') as f:
            proj_config = json.load(f)

        # 1. Calculate Languages Stats
        langs_stats = {}
        for lang in self.options['langs']:
            trans_file = self.project_path / "translation" / f"{lang}.json"

            stats = {
                "total_strings": 0,
                "translated_strings": 0,
                "source_char_count": 0,
                "translation_char_count": 0,
                "progress_percent": 0.0
            }

            if trans_file.exists():
                try:
                    with open(trans_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        stats["total_strings"] = len(data)

                        for item in data:
                            src_len = len(item.get('original_semantic', ''))
                            trans_len = len(item.get('translation', ''))
                            is_trans = bool(item.get('translation', '').strip()) and not item.get('is_ignored', False)

                            stats["source_char_count"] += src_len
                            if is_trans:
                                stats["translated_strings"] += 1
                                stats["translation_char_count"] += trans_len

                        if stats["total_strings"] > 0:
                            stats["progress_percent"] = round(
                                (stats["translated_strings"] / stats["total_strings"]) * 100, 1)
                except Exception as e:
                    logger.error(f"Error calculating stats for {lang}: {e}")

            langs_stats[lang] = stats

        # 2. Calculate File Stats
        total_size = 0
        file_manifest = {
            "source": [],
            "tm": [],
            "glossary": []
        }

        for p in files_to_pack:
            try:
                size = p.stat().st_size
                total_size += size

                # Categorize for manifest
                rel = p.relative_to(self.project_path)
                if str(rel).startswith('source'):
                    file_manifest['source'].append(p.name)
                elif str(rel).startswith('tm'):
                    file_manifest['tm'].append(p.name)
                elif str(rel).startswith('glossary'):
                    file_manifest['glossary'].append(p.name)
            except:
                pass

        return {
            "version": "1.1",
            "project_name": proj_config.get('name', 'Unknown Project'),
            "created_at": datetime.now().isoformat(),
            "source_lang": proj_config.get('source_language', 'en'),
            "overview": {
                "total_files": len(files_to_pack),
                "total_size_bytes": total_size,
                "includes_tm": self.options['include_tm'],
                "includes_glossary": self.options['include_glossary'],
                "is_encrypted": bool(self.options.get('password'))
            },
            "languages": langs_stats,
            "manifest": file_manifest
        }

    def _collect_files(self):
        files = []
        # 基础文件
        files.append(self.project_path / "project.json")

        # 垃圾文件黑名单
        EXCLUDE_NAMES = {'pack_info.json', '.DS_Store', 'thumbs.db', 'desktop.ini', '.gitignore'}
        EXCLUDE_EXTS = {'.tmp', '.bak', '.log', '.swp'}

        def is_junk(path):
            return (
                    path.name in EXCLUDE_NAMES or
                    path.suffix.lower() in EXCLUDE_EXTS or
                    path.name.startswith('~$')
            )

        def scan_dir(directory):
            if directory.exists():
                for p in directory.rglob('*'):
                    if p.is_file() and not is_junk(p):
                        files.append(p)

        # Source 目录
        scan_dir(self.project_path / "source")

        # Translation dir
        trans_dir = self.project_path / "translation"
        if trans_dir.exists():
            for lang in self.options['langs']:
                f = trans_dir / f"{lang}.json"
                if f.exists() and not is_junk(f):
                    files.append(f)

        # TM
        if self.options['include_tm']:
            scan_dir(self.project_path / "tm")

        # Glossary
        if self.options.get('include_glossary'):
            scan_dir(self.project_path / "glossary")

        return files


class ExtractWorker(QObject):
    progress = Signal(int, str)
    finished = Signal(bool, str)

    def __init__(self, package_path, target_dir, password=None):
        super().__init__()
        self.package_path = package_path
        self.target_dir = target_dir
        self.password = password

    def run(self):
        try:
            self.progress.emit(10, "Opening package...")

            if HAS_PYZIPPER:
                zf = pyzipper.AESZipFile(self.package_path, 'r')
                if self.password:
                    zf.setpassword(self.password.encode('utf-8'))
            else:
                zf = pyzipper.ZipFile(self.package_path, 'r')
                if self.password:
                    zf.setpassword(self.password.encode('utf-8'))

            with zf:
                members = zf.infolist()
                total = len(members)

                for i, member in enumerate(members):
                    zf.extract(member, self.target_dir)
                    prog = 10 + int((i / total) * 90)
                    self.progress.emit(prog, f"Extracting: {member.filename}")

            info_path = os.path.join(self.target_dir, 'pack_info.json')
            if os.path.exists(info_path):
                try:
                    os.remove(info_path)
                except Exception as e:
                    logger.warning(f"Failed to remove pack_info.json: {e}")

            self.progress.emit(100, "Extraction complete.")
            self.finished.emit(True, self.target_dir)

        except RuntimeError as e:
            if 'Bad password' in str(e) or 'password required' in str(e):
                self.finished.emit(False, "INVALID_PASSWORD")
            else:
                self.finished.emit(False, str(e))
        except Exception as e:
            logger.error(f"Extraction failed: {e}", exc_info=True)
            self.finished.emit(False, str(e))

    @staticmethod
    def verify_password(package_path, password):
        """
        在不解压的情况下，通过尝试读取一个加密文件来校验密码。
        """
        try:
            if HAS_PYZIPPER:
                zf = pyzipper.AESZipFile(package_path, 'r')
            else:
                zf = pyzipper.ZipFile(package_path, 'r')

            if password:
                zf.setpassword(password.encode('utf-8'))

            with zf:
                try:
                    zf.read('project.json')
                except KeyError:
                    files = zf.namelist()
                    target_file = None
                    for f in files:
                        if f != 'pack_info.json':
                            target_file = f
                            break

                    if target_file:
                        zf.read(target_file)
                    else:
                        # 包里只有 pack_info.json？那密码其实无所谓了
                        return True, None

            return True, None
        except Exception as e:
            return False, str(e)


def read_package_info(package_path):
    """Reads pack_info.json without extracting the whole archive or needing a password."""
    try:
        # Standard zipfile is enough to read unencrypted members even in an encrypted zip
        import zipfile
        with zipfile.ZipFile(package_path, 'r') as zf:
            if 'pack_info.json' in zf.namelist():
                with zf.open('pack_info.json') as f:
                    return json.load(f)
    except Exception as e:
        logger.error(f"Failed to read pack_info.json: {e}")
    return None