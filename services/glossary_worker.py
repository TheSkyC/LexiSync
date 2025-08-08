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
        for word in words:
            term_results = app.glossary_service.get_term(word, case_sensitive=False)
            if term_results:
                matches.append({
                    "source": word,
                    "translations": term_results
                })
        self.signals.finished.emit(self.ts_id, matches)