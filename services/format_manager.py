# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import os
import xml.etree.ElementTree as ET
from pathlib import Path
import xxhash
import logging
from models.translatable_string import TranslatableString
from services import po_file_service
from services import code_file_service
from utils.localization import _

logger = logging.getLogger(__name__)


class BaseFormatHandler:
    """格式处理器的基类"""
    format_id = "unknown"
    extensions = []
    format_type = "translation"  # 'translation' (结构化翻译文件) 或 'source' (需要正则提取的源码)

    display_name = "Unknown File"
    badge_text = "UNK"
    badge_bg_color = "#E0E0E0"
    badge_text_color = "#444444"

    def load(self, filepath, **kwargs):
        """返回: (translatable_objects, metadata, language_code)"""
        raise NotImplementedError

    def save(self, filepath, translatable_objects, metadata, **kwargs):
        """保存文件"""
        raise NotImplementedError


class PoFormatHandler(BaseFormatHandler):
    format_id = "po"
    extensions = ['.po', '.pot']
    format_type = "translation"
    display_name = _("PO Translation File")
    badge_text = "PO"
    badge_bg_color = "#F3E5F5"
    badge_text_color = "#7B1FA2"

    def load(self, filepath, **kwargs):
        relative_path = kwargs.get('relative_path')
        return po_file_service.load_from_po(filepath, relative_path=relative_path)

    def save(self, filepath, translatable_objects, metadata, **kwargs):
        original_file_name = kwargs.get('original_file_name', "source_code")
        app_instance = kwargs.get('app_instance', None)
        po_file_service.save_to_po(filepath, translatable_objects, metadata, original_file_name, app_instance)


class TsFormatHandler(BaseFormatHandler):
    format_id = "ts"
    extensions = ['.ts']
    format_type = "translation"
    display_name = _("Qt TS Translation File")
    badge_text = "TS"
    badge_bg_color = "#E8F5E9"
    badge_text_color = "#2E7D32"

    def load(self, filepath, **kwargs):
        logger.debug(f"[TsFormatHandler] Loading TS file: {filepath}")
        tree = ET.parse(filepath)
        root = tree.getroot()
        language = root.get('language', '')

        translatable_objects = []
        occurrence_counters = {}
        file_content_cache = {}

        relative_path = kwargs.get('relative_path')
        if relative_path:
            ts_file_rel_path = relative_path
        else:
            current_path = Path(filepath).parent
            project_root = None
            while True:
                if (current_path / "project.json").is_file():
                    project_root = str(current_path)
                    break
                if current_path.parent == current_path:
                    break
                current_path = current_path.parent

            if project_root:
                try:
                    ts_file_rel_path = Path(filepath).relative_to(project_root).as_posix()
                except ValueError:
                    ts_file_rel_path = os.path.basename(filepath)
            else:
                ts_file_rel_path = os.path.basename(filepath)

        for context in root.findall('context'):
            context_name = context.findtext('name', '')
            for message in context.findall('message'):
                source = message.findtext('source', '')
                if not source: continue

                translation_node = message.find('translation')
                translation = translation_node.text if translation_node is not None and translation_node.text else ''
                is_unfinished = translation_node.get('type') == 'unfinished' if translation_node is not None else False
                is_obsolete = translation_node.get('type') == 'obsolete' if translation_node is not None else False

                if is_obsolete: continue

                locations = []
                for loc in message.findall('location'):
                    locations.append((loc.get('filename', ''), loc.get('line', '0')))

                full_code_lines = []
                if locations:
                    src_rel_path = locations[0][0]
                    src_abs_path = os.path.normpath(os.path.join(os.path.dirname(filepath), src_rel_path))

                    if src_abs_path in file_content_cache:
                        full_code_lines = file_content_cache[src_abs_path]
                    elif os.path.isfile(src_abs_path):
                        try:
                            with open(src_abs_path, 'r', encoding='utf-8', errors='replace') as f:
                                lines = f.read().splitlines()
                                file_content_cache[src_abs_path] = lines
                                full_code_lines = lines
                        except Exception as e:
                            logger.warning(f"Failed to read source file for context: {src_abs_path}, error: {e}")

                line_num = int(locations[0][1]) if locations else 0
                forced_occurrences = [(ts_file_rel_path, str(line_num))]

                extracomment = message.findtext('extracomment', '')
                translatorcomment = message.findtext('translatorcomment', '')

                if locations:
                    refs = ' '.join(f"{p}:{l}" for p, l in locations)
                    if extracomment:
                        extracomment = f"#: {refs}\n{extracomment}"
                    else:
                        extracomment = f"#: {refs}"

                key = (source, context_name)
                current_index = occurrence_counters.get(key, 0)
                occurrence_counters[key] = current_index + 1

                stable_name_for_uuid = f"{ts_file_rel_path}::{context_name}::{source}::{current_index}"
                import xxhash
                obj_id = xxhash.xxh128(stable_name_for_uuid.encode('utf-8')).hexdigest()

                ts = TranslatableString(
                    original_raw=source, original_semantic=source,
                    line_num=line_num,
                    char_pos_start_in_file=0, char_pos_end_in_file=0,
                    full_code_lines=full_code_lines,
                    string_type="TS Import",
                    source_file_path=ts_file_rel_path,
                    occurrences=forced_occurrences,
                    occurrence_index=current_index, id=obj_id
                )
                ts.translation = translation
                ts.context = context_name
                ts.po_comment = extracomment
                ts.comment = translatorcomment
                ts.is_reviewed = not is_unfinished
                ts.update_sort_weight()
                translatable_objects.append(ts)

        return translatable_objects, {'language': language}, language

    def save(self, filepath, translatable_objects, metadata, **kwargs):
        root = ET.Element('TS', version="2.1")
        app_instance = kwargs.get('app_instance', None)

        lang_code = 'en'
        if app_instance:
            lang_code = app_instance.current_target_language if app_instance.is_project_mode else app_instance.target_language
        elif metadata and 'language' in metadata:
            lang_code = metadata['language']

        root.set('language', lang_code)
        contexts = {}
        for ts in translatable_objects:
            if not ts.original_semantic or ts.id == "##NEW_ENTRY##": continue
            ctx = ts.context or "Default"
            if ctx not in contexts: contexts[ctx] = []
            contexts[ctx].append(ts)

        for ctx_name, items in contexts.items():
            context_node = ET.SubElement(root, 'context')
            name_node = ET.SubElement(context_node, 'name')
            name_node.text = ctx_name

            for ts in items:
                msg_node = ET.SubElement(context_node, 'message')

                entry_occurrences = []
                clean_extracomment_lines = []
                if ts.po_comment:
                    for line in ts.po_comment.splitlines():
                        if line.strip().startswith('#:'):
                            content = line.replace('#:', '').strip()
                            for part in content.split():
                                if ':' in part:
                                    try:
                                        fpath, lineno = part.rsplit(':', 1)
                                        entry_occurrences.append((fpath, lineno))
                                    except ValueError:
                                        pass
                        else:
                            clean_extracomment_lines.append(line)

                if not entry_occurrences:
                    entry_occurrences = [("unknown", "0")]

                for loc_file, loc_line in entry_occurrences:
                    loc_node = ET.SubElement(msg_node, 'location')
                    loc_node.set('filename', loc_file)
                    loc_node.set('line', str(loc_line))

                source_node = ET.SubElement(msg_node, 'source')
                source_node.text = ts.original_semantic

                clean_extracomment = "\n".join(clean_extracomment_lines).strip()
                if clean_extracomment:
                    extracomment_node = ET.SubElement(msg_node, 'extracomment')
                    extracomment_node.text = clean_extracomment

                if ts.comment:
                    translatorcomment_node = ET.SubElement(msg_node, 'translatorcomment')
                    translatorcomment_node.text = ts.comment

                trans_node = ET.SubElement(msg_node, 'translation')
                trans_node.text = ts.translation

                if not ts.is_reviewed:
                    trans_node.set('type', 'unfinished')

        tree = ET.ElementTree(root)
        if hasattr(ET, 'indent'): ET.indent(tree, space="    ", level=0)
        xml_str = ET.tostring(root, encoding='utf-8', xml_declaration=True).decode('utf-8')
        xml_str = xml_str.replace('?>', '?>\n<!DOCTYPE TS>')
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(xml_str)


class OwCodeFormatHandler(BaseFormatHandler):
    format_id = "ow_code"
    extensions = ['.ow', '.txt']
    format_type = "source"
    display_name = _("Overwatch Workshop Code")
    badge_text = "Code"
    badge_bg_color = "#E3F2FD"
    badge_text_color = "#0277BD"

    def load(self, filepath, **kwargs):
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        extraction_patterns = kwargs.get('extraction_patterns', [])
        relative_path = kwargs.get('relative_path', os.path.basename(filepath))
        strings = code_file_service.extract_translatable_strings(content, extraction_patterns, relative_path)
        return strings, {'raw_content': content}, 'en'

    def save(self, filepath, translatable_objects, metadata, **kwargs):
        app_instance = kwargs.get('app_instance', None)
        raw_content = metadata.get('raw_content', '')
        code_file_service.save_translated_code(filepath, raw_content, translatable_objects, app_instance)


class FormatManager:
    _handlers = {}

    @classmethod
    def register_handler(cls, handler_class):
        handler = handler_class()
        cls._handlers[handler.format_id] = handler
        logger.info(f"Registered format handler: {handler.format_id}")

    @classmethod
    def get_handler(cls, format_id) -> BaseFormatHandler:
        return cls._handlers.get(format_id)

    @classmethod
    def get_handler_by_extension(cls, filepath) -> BaseFormatHandler:
        ext = os.path.splitext(filepath)[1].lower()
        for handler in cls._handlers.values():
            if ext in handler.extensions:
                return handler
        return None

    @classmethod
    def get_file_dialog_filters(cls, format_type=None):
        """生成文件选择器的过滤器字符串"""
        filters = []
        all_exts = []

        for handler in cls._handlers.values():
            if format_type and handler.format_type != format_type:
                continue
            ext_str = " ".join(f"*{ext}" for ext in handler.extensions)
            filters.append(f"{handler.display_name} ({ext_str})")
            all_exts.extend(handler.extensions)

        all_ext_str = " ".join(f"*{ext}" for ext in set(all_exts))

        if format_type == "translation":
            prefix = _("All Translation Files")
        elif format_type == "source":
            prefix = _("All Source Files")
        else:
            prefix = _("All Supported Files")

        filter_string = f"{prefix} ({all_ext_str});;" + ";;".join(filters) + f";;{_('All Files')} (*.*)"
        return filter_string


# 注册内置处理器
FormatManager.register_handler(PoFormatHandler)
FormatManager.register_handler(TsFormatHandler)
FormatManager.register_handler(OwCodeFormatHandler)