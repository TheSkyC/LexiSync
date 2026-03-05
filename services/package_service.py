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
            self.progress.emit(5, "Calculating project statistics...")
            pack_info = self._generate_pack_info()

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
                files_to_pack = self._collect_files()
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

    def _generate_pack_info(self):
        with open(self.project_path / "project.json", 'r', encoding='utf-8') as f:
            proj_config = json.load(f)

        langs_stats = {}
        for lang in self.options['langs']:
            trans_file = self.project_path / "translation" / f"{lang}.json"
            total, translated = 0, 0
            if trans_file.exists():
                with open(trans_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    total = len(data)
                    translated = sum(
                        1 for item in data if item.get('translation', '').strip() and not item.get('is_ignored', False))
            langs_stats[lang] = {"total": total, "translated": translated}

        return {
            "version": "1.0",
            "project_name": proj_config.get('name', 'Unknown Project'),
            "created_at": datetime.now().isoformat(),
            "source_lang": proj_config.get('source_language', 'en'),
            "languages": langs_stats,
            "includes_tm": self.options['include_tm'],
            "includes_glossary": self.options['include_glossary'],
            "is_encrypted": bool(self.options.get('password'))
        }

    def _collect_files(self):
        files = []
        # Base files
        files.append(self.project_path / "project.json")

        # Source dir
        src_dir = self.project_path / "source"
        if src_dir.exists():
            files.extend([p for p in src_dir.rglob('*') if p.is_file()])

        # Translation dir (only selected langs)
        trans_dir = self.project_path / "translation"
        if trans_dir.exists():
            for lang in self.options['langs']:
                f = trans_dir / f"{lang}.json"
                if f.exists(): files.append(f)

        # TM
        if self.options['include_tm']:
            tm_dir = self.project_path / "tm"
            if tm_dir.exists():
                files.extend([p for p in tm_dir.rglob('*') if p.is_file()])

        # Glossary
        if self.options['include_glossary']:
            glos_dir = self.project_path / "glossary"
            if glos_dir.exists():
                files.extend([p for p in glos_dir.rglob('*') if p.is_file()])

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