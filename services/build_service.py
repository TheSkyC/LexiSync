# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtCore import QObject, Signal
from services import project_service
import logging

logger = logging.getLogger(__name__)

class BuildWorker(QObject):
    progress_updated = Signal(int, int, str)
    finished = Signal(bool, str)

    def __init__(self, project_path, app_instance):
        super().__init__()
        self.project_path = project_path
        self.app = app_instance
        self._is_cancelled = False

    def run(self):
        try:
            success, message = project_service.build_project_target_files(
                self.project_path,
                self.app,
                self.update_progress
            )
            self.finished.emit(success, message)
        except Exception as e:
            logger.error(f"Build process failed with an exception: {e}", exc_info=True)
            self.finished.emit(False, str(e))

    def update_progress(self, current, total, message):
        if not self._is_cancelled:
            self.progress_updated.emit(current, total, message)

    def cancel(self):
        self._is_cancelled = True