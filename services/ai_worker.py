# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtCore import QRunnable, QObject, Signal
import weakref
import re
import logging
from utils.enums import AIOperationType
from utils.text_utils import generate_ngrams
from utils.localization import _
from services.prompt_service import generate_prompt_from_structure
from services.validation_service import validate_string
from models.translatable_string import TranslatableString
from utils.constants import DEFAULT_PROMPT_STRUCTURE, SUPPORTED_LANGUAGES, DEFAULT_CORRECTION_PROMPT_STRUCTURE, COT_INJECTION_PROMPT

logger = logging.getLogger(__name__)


class AIWorkerSignals(QObject):
    # ts_id, translated_text, error_message, op_type
    result = Signal(str, str, str, object)
    # message, level
    log_message = Signal(str, str)
    finished = Signal()
    stream_chunk = Signal(str)
    final_prompt_ready = Signal(str)


class AIWorker(QRunnable):
    def __init__(self, app_instance, ts_id, operation_type: AIOperationType, **kwargs):
        super().__init__()
        self.app_ref = weakref.ref(app_instance)
        self.ts_id = ts_id
        self.op_type = operation_type
        self.signals = AIWorkerSignals()

        # Args
        self.original_text = kwargs.get('original_text', "")
        self.target_lang = kwargs.get('target_lang', "")

        self.context_provider = kwargs.get('context_provider', None)
        self.context_dict = kwargs.get('context_dict', {})

        self.plugin_placeholders = kwargs.get('plugin_placeholders', {})
        self.system_prompt = kwargs.get('system_prompt', None)
        self.temperature = kwargs.get('temperature', None)
        self.self_repair_limit = kwargs.get('self_repair_limit', 1)
        self.api_timeout = kwargs.get('api_timeout', 60)
        self.stream = kwargs.get('stream', False)
        self.current_translation = kwargs.get('current_translation', "")

    def run(self):
        app = self.app_ref()
        if not app: return

        try:
            # Whitespace Preservation
            original_full = self.original_text
            match_leading = re.match(r'^(\s*)', original_full)
            match_trailing = re.search(r'(\s*)$', original_full)
            leading_ws = match_leading.group(1) if match_leading else ""
            trailing_ws = match_trailing.group(1) if match_trailing else ""
            if len(leading_ws) + len(trailing_ws) < len(original_full):
                text_to_translate_core = original_full.strip()
            else:
                text_to_translate_core = original_full

            if self.context_provider and callable(self.context_provider):
                try:
                    generated_context = self.context_provider(self.ts_id)
                    if generated_context:
                        self.context_dict.update(generated_context)
                except Exception as e:
                    logger.error(f"Error generating context for {self.ts_id}: {e}", exc_info=True)


            active_model_id = app.config.get("active_ai_model_id")
            models = app.config.get("ai_models", [])
            current_model_config = next((m for m in models if m["id"] == active_model_id), {})

            enhancements = current_model_config.get("enhancements", [])
            use_cot = "cot_injection" in enhancements

            # --- 1. 准备 Prompt ---
            final_prompt = ""
            text_to_send = ""

            if self.system_prompt:
                final_prompt = self.system_prompt
                text_to_send = f"Original: {text_to_translate_core}\nTarget: {self.target_lang}"
            else:
                is_fix_mode = self.op_type in [AIOperationType.FIX, AIOperationType.BATCH_FIX]

                if is_fix_mode:
                    # --- 修复模式 ---
                    prompts = app.config.get("ai_prompts", [])
                    active_id = app.config.get("active_correction_prompt_id")
                    prompt_data = next((p for p in prompts if p["id"] == active_id), None)
                    prompt_structure = prompt_data["structure"] if prompt_data else DEFAULT_CORRECTION_PROMPT_STRUCTURE

                    # 构建 User Input
                    text_to_send = (
                        f"Original Text:\n{text_to_translate_core}\n\n"
                        f"Current Translation:\n{self.current_translation}\n\n"
                        f"Errors Detected:\n{self.context_dict.get('[Error List]', 'None')}\n\n"
                        f"Glossary/Context:\n{self.context_dict.get('[Glossary]', '')}\n\n"
                        f"Please provide the corrected translation in {self.target_lang}."
                    )
                else:
                    # --- 翻译模式 ---
                    prompt_structure = app.config.get("ai_prompt_structure", DEFAULT_PROMPT_STRUCTURE)
                    text_to_send = (
                        f"<translate_input>\n{text_to_translate_core}\n</translate_input>\n\n"
                        f"Translate the above text enclosed with <translate_input> into {self.target_lang} without <translate_input>. "
                    )

                # 占位符填充
                glossary_prompt_part = self._build_glossary_context(app)
                placeholders = {
                    '[Source Language]': app.source_language,
                    '[Target Language]': self.target_lang,
                    '[Untranslated Context]': self.context_dict.get("original_context", ""),
                    '[Translated Context]': self.context_dict.get("translation_context", ""),
                    '[Glossary]': glossary_prompt_part,
                    '[Semantic Context]': self.context_dict.get("[Semantic Context]", ""),
                    '[Source Text]': text_to_translate_core,
                    '[Current Translation]': self.current_translation,
                    '[Error List]': self.context_dict.get("[Error List]", "")
                }

                # 插件占位符
                for k, v in self.context_dict.items():
                    if k.startswith('[') and k.endswith(']'):
                        placeholders[k] = v
                if self.plugin_placeholders:
                    placeholders.update(self.plugin_placeholders)

                final_prompt = generate_prompt_from_structure(prompt_structure, placeholders)

            if use_cot:
                final_prompt += "\n\n" + COT_INJECTION_PROMPT

            self.signals.final_prompt_ready.emit(final_prompt)

            # ============================================================
            logger.info(f"========== AI WORKER DEBUG ({self.ts_id}) ==========")
            logger.info(f"OP TYPE: {self.op_type}")
            logger.info(f"CoT ENABLED: {use_cot}")
            logger.info(f"[SYSTEM PROMPT]:\n{final_prompt}")
            logger.info(f"[USER INPUT]:\n{text_to_send}")
            logger.info("====================================================")
            # ============================================================

            # --- 2. 执行翻译循环---
            current_attempt = 1
            max_attempts = 1 + self.self_repair_limit

            while current_attempt <= max_attempts:
                final_translated_text = ""

                if self.stream:
                    full_text_buffer = ""
                    cot_state = "WAITING"  # WAITING -> THINKING -> TRANSLATING

                    cot_emitted_len = 0

                    is_first_translation_chunk = True

                    CLOSE_TAG = "</translation>"

                    if use_cot:
                        self.signals.stream_chunk.emit("Thinking...")

                    for chunk in app.ai_translator.translate_stream(
                            text_to_send, final_prompt,
                            temperature=self.temperature,
                            timeout=self.api_timeout
                    ):
                        if not use_cot:
                            # Standard streaming
                            final_translated_text += chunk
                            self.signals.stream_chunk.emit(chunk)
                        else:
                            # CoT Streaming Logic
                            full_text_buffer += chunk

                            if cot_state == "WAITING":
                                if "<thinking>" in full_text_buffer:
                                    cot_state = "THINKING"
                                    pass
                                elif "<translation>" in full_text_buffer:
                                    cot_state = "TRANSLATING"
                                    self.signals.stream_chunk.emit("")  # Clear "Thinking..."

                                    # 提取标签后的内容
                                    parts = full_text_buffer.split("<translation>", 1)
                                    # 重置 buffer 为翻译内容，方便后续基于索引处理
                                    full_text_buffer = parts[1] if len(parts) > 1 else ""
                                    cot_emitted_len = 0

                            elif cot_state == "THINKING":
                                if "<translation>" in full_text_buffer:
                                    cot_state = "TRANSLATING"
                                    self.signals.stream_chunk.emit("")  # Clear "Thinking..."

                                    parts = full_text_buffer.split("<translation>", 1)
                                    full_text_buffer = parts[1] if len(parts) > 1 else ""
                                    cot_emitted_len = 0

                            if cot_state == "TRANSLATING":
                                tag_index = full_text_buffer.find(CLOSE_TAG)

                                if tag_index != -1:
                                    valid_content = full_text_buffer[:tag_index]

                                    to_emit = valid_content[cot_emitted_len:]

                                    if is_first_translation_chunk:
                                        to_emit = to_emit.lstrip()  # 去除开头的 \n
                                        is_first_translation_chunk = False

                                    if to_emit:
                                        final_translated_text += to_emit
                                        self.signals.stream_chunk.emit(to_emit)

                                    break

                                current_len = len(full_text_buffer)
                                safe_end_index = current_len

                                # 检查末尾是否匹配 </translation> 的前缀
                                for i in range(1, len(CLOSE_TAG)):
                                    suffix = full_text_buffer[-i:]
                                    if CLOSE_TAG.startswith(suffix):
                                        safe_end_index = current_len - i
                                        break

                                if safe_end_index > cot_emitted_len:
                                    to_emit = full_text_buffer[cot_emitted_len:safe_end_index]

                                    if is_first_translation_chunk:
                                        original_len = len(to_emit)
                                        to_emit = to_emit.lstrip()
                                        if len(to_emit) < original_len:
                                            is_first_translation_chunk = False
                                        if not to_emit and original_len > 0:
                                            is_first_translation_chunk = True

                                    if to_emit:
                                        final_translated_text += to_emit
                                        self.signals.stream_chunk.emit(to_emit)
                                        cot_emitted_len = safe_end_index

                    # Post-processing for CoT (Stream finished)
                    if use_cot:
                        if not final_translated_text:
                            match = re.search(r'<translation>(.*?)</translation>', full_text_buffer, re.DOTALL)
                            if match:
                                final_translated_text = match.group(1).strip()
                            else:
                                parts = full_text_buffer.split("</thinking>")
                                if len(parts) > 1:
                                    temp = parts[1].replace("<translation>", "")
                                    final_translated_text = temp.strip()
                                else:
                                    final_translated_text = full_text_buffer.replace("<translation>", "").strip()

                else:
                    # Non-streaming logic
                    raw_response = app.ai_translator.translate(
                        text_to_send, final_prompt,
                        temperature=self.temperature,
                        timeout=self.api_timeout
                    )

                    if use_cot:
                        match = re.search(r'<translation>(.*?)</translation>', raw_response, re.DOTALL)
                        if match:
                            final_translated_text = match.group(1).strip()
                        else:
                            # Fallback logic
                            parts = raw_response.split("</thinking>")
                            if len(parts) > 1:
                                final_translated_text = parts[1].strip()
                            else:
                                final_translated_text = raw_response.strip()
                    else:
                        final_translated_text = raw_response

                # 修复首尾空格
                last_translated_text = final_translated_text
                final_translated_text = leading_ws + last_translated_text.strip() + trailing_ws

                # 如果是修复模式或非翻译任务，不触发自修复
                if self.op_type in [AIOperationType.FIX, AIOperationType.BATCH_FIX]:
                    break

                # --- 3. 自修复检查 (仅翻译模式) ---
                if current_attempt < max_attempts:
                    temp_ts = TranslatableString("", self.original_text, 0, 0, 0, [])
                    temp_ts.translation = final_translated_text
                    validate_string(temp_ts, app.config, app)

                    # 如果有错误
                    if temp_ts.warnings:
                        error_details = "\n".join([f"- {msg}" for __, msg in temp_ts.warnings])

                        log_msg = _(
                            "Self-Repair: '{text}...' failed validation. Issues:\n{errors}\nRetrying with user correction template...").format(
                            text=self.original_text[:20], errors=error_details
                        )
                        self.signals.log_message.emit(log_msg, "WARNING")

                        # 构建自修复 Prompt
                        final_prompt = self._build_self_repair_prompt(app, last_translated_text, error_details)
                        text_to_send = (
                            f"Original: {text_to_translate_core}\n"
                            f"Previous Attempt: {last_translated_text}\n"
                            f"Errors: {error_details}\n"
                            "Please fix the errors and output only the translation."
                        )
                        current_attempt += 1
                        continue

                break

            self.signals.result.emit(self.ts_id, final_translated_text, None, self.op_type)

        except Exception as e:
            self.signals.result.emit(self.ts_id, None, str(e), self.op_type)
        finally:
            self.signals.finished.emit()

    def _build_self_repair_prompt(self, app, failed_translation, error_details):
        prompts = app.config.get("ai_prompts", [])
        active_fix_id = app.config.get("active_correction_prompt_id")
        prompt_data = next((p for p in prompts if p["id"] == active_fix_id), None)

        if prompt_data:
            structure = prompt_data["structure"]
        else:
            structure = DEFAULT_CORRECTION_PROMPT_STRUCTURE

        placeholders = {
            '[Target Language]': self.target_lang,
            '[Source Text]': self.original_text,
            '[Current Translation]': failed_translation,
            '[Error List]': error_details,
            '[Glossary]': self._build_glossary_context(app)
        }

        base_prompt = generate_prompt_from_structure(structure, placeholders)

        strict_suffix = (
            "\n\n"
            "### CRITICAL AUTOMATION RULES:\n"
            "1. Your previous output failed technical validation. You MUST fix the errors listed above.\n"
            "2. Ensure all placeholders, HTML tags, and escape sequences match the source EXACTLY.\n"
            "3. Output ONLY the raw corrected text. NO explanations, NO notes, NO markdown code blocks."
        )

        return base_prompt + strict_suffix

    def _build_glossary_context(self, app):
        candidates = generate_ngrams(self.original_text, min_n=1, max_n=5)
        if not candidates: return ""

        source_lang = app.source_language
        target_lang_code = app.current_target_language if app.is_project_mode else app.target_language

        # 批量查询数据库
        potential_terms = app.glossary_service.get_translations_batch(
            words=candidates,
            source_lang=source_lang,
            target_lang=target_lang_code,
            include_reverse=False
        )

        if not potential_terms: return ""

        placeholder_spans = [m.span() for m in app.placeholder_regex.finditer(self.original_text)]
        valid_terms = {}
        sorted_terms = sorted(potential_terms.keys(), key=len, reverse=True)
        matched_mask = [False] * len(self.original_text)

        for word in sorted_terms:
            term_info = potential_terms[word]
            try:
                for match in re.finditer(r'\b' + re.escape(word) + r'\b', self.original_text, re.IGNORECASE):
                    start, end = match.start(), match.end()

                    if any(p_start <= start < p_end for p_start, p_end in placeholder_spans):
                        continue

                    if any(matched_mask[i] for i in range(start, end)):
                        continue

                    for i in range(start, end):
                        matched_mask[i] = True

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