# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtCore import QRunnable, Signal, QObject
import weakref
import re

class GlossarySignals(QObject):
    finished = Signal(str, list)


class GlossaryAnalysisWorker(QRunnable):
    def __init__(self, app_instance, ts_id: str, text_to_analyze: str):
        super().__init__()
        self.app_ref = weakref.ref(app_instance)
        self.ts_id = ts_id
        self.text = text_to_analyze
        self.signals = GlossarySignals()

    def run(self):
        app = self.app_ref()
        if not app or not self.text:
            self.signals.finished.emit(self.ts_id, [])
            return

        words = set(re.findall(r'\b\w+\b', self.text.lower()))
        if not words:
            self.signals.finished.emit(self.ts_id, [])
            return

        matches = []
        source_lang = app.source_language
        target_lang = app.current_target_language if app.is_project_mode else app.target_language

        term_results_map = app.glossary_service.get_translations_batch(
            words=list(words),
            source_lang=source_lang,
            target_lang=target_lang,
            include_reverse=False
        )

        for word, term_info in term_results_map.items():
            ui_translations = [{"target": t["target"], "comment": t["comment"]} for t in term_info['translations']]
            matches.append({
                "source": word,
                "translations": ui_translations
            })

        self.signals.finished.emit(self.ts_id, matches)