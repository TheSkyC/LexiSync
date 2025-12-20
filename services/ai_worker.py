# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtCore import QRunnable, QObject, Signal
import weakref
import re
import logging
from utils.enums import AIOperationType
from utils.localization import _
from services.prompt_service import generate_prompt_from_structure
from utils.constants import DEFAULT_PROMPT_STRUCTURE, SUPPORTED_LANGUAGES

logger = logging.getLogger(__name__)


class AIWorkerSignals(QObject):
    # ts_id, translated_text, error_message, op_type
    result = Signal(str, str, str, object)
    finished = Signal()


class AIWorker(QRunnable):
    def __init__(self, app_instance, ts_id, operation_type: AIOperationType, **kwargs):
        super().__init__()
        self.app_ref = weakref.ref(app_instance)
        self.ts_id = ts_id
        self.op_type = operation_type
        self.signals = AIWorkerSignals()

        # Common args
        self.original_text = kwargs.get('original_text', "")
        self.target_lang = kwargs.get('target_lang', "")

        # Translation specific args
        self.context_dict = kwargs.get('context_dict', {})
        self.plugin_placeholders = kwargs.get('plugin_placeholders', {})

        # Args
        self.system_prompt = kwargs.get('system_prompt', None)
        self.temperature = kwargs.get('temperature', None)

    def run(self):
        app = self.app_ref()
        if not app: return

        try:
            final_prompt = ""

            # --- Logic Branch 1: Translation (Single or Batch) ---
            if self.op_type in (AIOperationType.TRANSLATION, AIOperationType.BATCH_TRANSLATION):
                if self.system_prompt:
                    final_prompt = self.system_prompt
                else:
                    # 1. Glossary Lookup
                    glossary_prompt_part = self._build_glossary_context(app)

                    # 2. Build Prompt
                    placeholders = {
                        '[Target Language]': self.target_lang,
                        '[Untranslated Context]': self.context_dict.get("original_context", ""),
                        '[Translated Context]': self.context_dict.get("translation_context", ""),
                        '[Glossary]': glossary_prompt_part
                    }
                    if self.plugin_placeholders:
                        placeholders.update(self.plugin_placeholders)

                    prompt_structure = app.config.get("ai_prompt_structure", DEFAULT_PROMPT_STRUCTURE)
                    final_prompt = generate_prompt_from_structure(prompt_structure, placeholders)

            # --- Logic Branch 2: Fix ---
            elif self.op_type == AIOperationType.FIX:
                final_prompt = self.system_prompt

            # --- Execute API Call ---
            logger.debug(f"[AIWorker] Type: {self.op_type.name}, ID: {self.ts_id}")
            translated_text = app.ai_translator.translate(
                self.original_text, final_prompt, temperature=self.temperature
            )

            # Emit Success
            self.signals.result.emit(
                self.ts_id, translated_text, None, self.op_type
            )

        except Exception as e:
            # Emit Error
            self.signals.result.emit(
                self.ts_id, None, str(e), self.op_type
            )

        finally:
            self.signals.finished.emit()

    def _build_glossary_context(self, app):
        """Helper to extract glossary terms relevant to the text."""
        original_words = set(re.findall(r'\b\w+\b', self.original_text.lower()))
        if not original_words: return ""

        source_lang = app.source_language
        target_lang_code = app.current_target_language if app.is_project_mode else app.target_language

        potential_terms = app.glossary_service.get_translations_batch(
            words=list(original_words),
            source_lang=source_lang,
            target_lang=target_lang_code,
            include_reverse=False
        )

        if not potential_terms: return ""

        # Filter terms that actually appear in text
        placeholder_spans = [m.span() for m in app.placeholder_regex.finditer(self.original_text)]
        valid_terms = {}

        for word, term_info in potential_terms.items():
            try:
                for match in re.finditer(r'\b' + re.escape(word) + r'\b', self.original_text, re.IGNORECASE):
                    if not any(start <= match.start() < end for start, end in placeholder_spans):
                        valid_terms[word] = term_info
                        break
            except re.error:
                continue

        if not valid_terms: return ""

        header = f"| {_('Source Term')} | {_('Should be Translated As')} |\n|---|---|\n"
        rows = []
        for word, term_info in valid_terms.items():
            targets = " or ".join(f"'{t['target']}'" for t in term_info['translations'])
            rows.append(f"| {word} | {targets} |")

        return header + "\n".join(rows)