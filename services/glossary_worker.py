# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtCore import QRunnable, Signal, QObject
import weakref
import re
from utils.text_utils import generate_ngrams

class GlossarySignals(QObject):
    finished = Signal(str, list, bool)

class GlossaryAnalysisWorker(QRunnable):
    def __init__(self, app_instance, ts_id: str, text_to_analyze: str, is_manual: bool = False):
        super().__init__()
        self.app_ref = weakref.ref(app_instance)
        self.ts_id = ts_id
        self.text = text_to_analyze
        self.is_manual = is_manual
        self.signals = GlossarySignals()

    def run(self):
        app = self.app_ref()
        if not app or not self.text:
            self.signals.finished.emit(self.ts_id, [], self.is_manual)
            return

        # 生成 N-gram 候选项
        candidates = generate_ngrams(self.text.lower(), min_n=1, max_n=5)

        if not candidates:
            self.signals.finished.emit(self.ts_id, [], self.is_manual)
            return

        source_lang = app.source_language
        target_lang = app.current_target_language if app.is_project_mode else app.target_language

        # 批量查询数据库
        term_results_map = app.glossary_service.get_translations_batch(
            words=candidates,
            source_lang=source_lang,
            target_lang=target_lang,
            include_reverse=False
        )

        matches = []

        # 过滤
        sorted_terms = sorted(term_results_map.keys(), key=len, reverse=True)

        text_len = len(self.text)
        covered_mask = [False] * text_len

        for term in sorted_terms:
            term_info = term_results_map[term]
            is_valid_occurrence = False

            try:
                pattern = re.compile(r'\b' + re.escape(term) + r'\b', re.IGNORECASE)

                for match in pattern.finditer(self.text):
                    start, end = match.span()
                    if any(covered_mask[i] for i in range(start, end)):
                        continue

                    for i in range(start, end):
                        covered_mask[i] = True

                    is_valid_occurrence = True
            except re.error:
                continue

            if is_valid_occurrence:
                ui_translations = [{"target": t["target"], "comment": t["comment"]} for t in term_info['translations']]
                matches.append({
                    "source": term,
                    "translations": ui_translations
                })

        self.signals.finished.emit(self.ts_id, matches, self.is_manual)