# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import os
import regex as re
from rapidfuzz import fuzz
import xxhash
import plistlib
import xml.etree.ElementTree as ET
from pathlib import Path
import logging
import json
import csv
import copy
from typing import List, Dict, Any, Tuple, Optional
from models.translatable_string import TranslatableString
from services import po_file_service
from services import code_file_service
from utils.localization import _

logger = logging.getLogger(__name__)


class BaseFormatHandler:
    """格式处理器的基类"""
    format_id = "unknown"
    extensions = []
    format_type = "translation"

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

    def _detect_language_from_filename(self, filename: str) -> str:
        """从文件名（如 data_zh_CN.csv）中尝试提取 BCP-47 语言代码"""
        import regex as re
        stem = os.path.splitext(filename)[0]
        # 匹配常见的语言后缀，如 _zh, -en, .jp 等
        m = re.search(r'[._-]([a-z]{2,3}(?:[_-][A-Za-z]{2,4})?)$', stem)
        if m:
            return m.group(1).replace('-', '_')
        return 'en'

class PoFormatHandler(BaseFormatHandler):
    """
    GNU Gettext PO/POT 格式处理器
    支持的特性:
    1. 标准元数据: 读写文件头信息 (Project-Id, Language, POT-Creation-Date 等)
    2. 注释处理: 支持翻译者注释 (#) 和提取出的开发者注释 (#.)
    3. 状态同步: 完美支持模糊标记 (fuzzy) 以及 LexiSync 特有的已审阅标记
    4. 源码引用: 自动记录并还原条目在原始代码中的位置信息 (#:)
    """
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
    """
    Qt Linguist TS 格式处理器
    支持的特性:
    1. 上下文分组: 严格遵循 XML 结构，按 <context> 元素组织翻译条目
    2. 源码关联: 自动寻址并加载 <location> 标签指向的本地源码片段作为上下文
    3. 状态映射: 将 type="unfinished" 状态与 LexiSync 的“审阅”流程深度绑定
    4. 扩展注释: 支持 extracomment (开发者) 和 translatorcomment (译员) 的读写
    """
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


class XliffFormatHandler(BaseFormatHandler):
    """
    XLIFF (XML Localization Interchange File Format) 处理器
    支持版本:
    - XLIFF 1.2
    - XLIFF 2.0
    """
    format_id = "xliff"
    extensions = ['.xlf', '.xliff']
    format_type = "translation"
    display_name = _("XLIFF Translation File")
    badge_text = "XLIFF"
    badge_bg_color = "#E1F5FE"
    badge_text_color = "#01579B"

    def load(self, filepath, **kwargs):
        logger.debug(f"[XliffFormatHandler] Loading XLIFF file: {filepath}")
        tree = ET.parse(filepath)
        root = tree.getroot()

        namespace = ""
        if root.tag.startswith("{"):
            namespace = root.tag[1:].split("}")[0]

        # 定义命名空间映射，用于 findall
        ns = {"x": namespace} if namespace else {}
        prefix = "x:" if namespace else ""

        version = root.get('version', '1.2')
        rel_path = kwargs.get('relative_path') or os.path.basename(filepath)
        translatable_objects = []
        occurrence_counters = {}

        files = root.findall(f'.//{prefix}file', ns)
        if not files and (self._strip_ns(root.tag) == 'file'):
            files = [root]

        for file_elem in files:
            source_lang = file_elem.get('source-language', 'en')
            target_lang = file_elem.get('target-language', '')
            original_file = file_elem.get('original', '')

            trans_units = file_elem.findall(f'.//{prefix}trans-unit', ns)
            for trans_unit in trans_units:
                self._process_trans_unit(
                    trans_unit, translatable_objects, occurrence_counters,
                    rel_path, original_file, ns, prefix
                )

        metadata = {
            'version': version,
            'source_language': source_lang if 'source_lang' in locals() else 'en',
            'target_language': target_lang if target_lang else 'en',
            'namespace_uri': namespace
        }
        return translatable_objects, metadata, metadata['target_language']

    def _strip_ns(self, tag):
        return tag.split('}', 1)[1] if '}' in tag else tag

    def _process_trans_unit(self, trans_unit, results, occurrence_counters, file_rel_path, original_file, ns, prefix):
        unit_id = trans_unit.get('id', 'unknown')

        source_elem = trans_unit.find(f'{prefix}source', ns)
        target_elem = trans_unit.find(f'{prefix}target', ns)

        if source_elem is None or source_elem.text is None:
            return

        source_text = source_elem.text
        target_text = target_elem.text if target_elem is not None and target_elem.text else ''

        state = target_elem.get('state', 'needs-translation') if target_elem is not None else 'needs-translation'
        # 映射状态：translated 和 final 视为已审阅
        is_reviewed = state in ['translated', 'final', 'signed-off']

        note_elems = trans_unit.findall(f'{prefix}note', ns)
        notes = [note.text for note in note_elems if note.text]

        counter_key = (source_text, unit_id)
        idx = occurrence_counters.get(counter_key, 0)
        occurrence_counters[counter_key] = idx + 1

        stable_name = f"{file_rel_path}::{unit_id}::{source_text}::{idx}"
        obj_id = xxhash.xxh128(stable_name.encode('utf-8')).hexdigest()

        ts = TranslatableString(
            source_text, source_text, 0, 0, 0, [], "XLIFF Import",
            file_rel_path, [(file_rel_path, unit_id)], idx, obj_id
        )
        ts.translation = target_text
        ts.context = unit_id
        ts.comment = "\n".join(notes) if notes else ""
        ts.po_comment = f"#: XLIFF ID: {unit_id}"
        ts.is_reviewed = is_reviewed
        ts.update_sort_weight()
        results.append(ts)

    def save(self, filepath, translatable_objects, metadata, **kwargs):
        uri = metadata.get('namespace_uri', 'urn:oasis:names:tc:xliff:document:1.2')
        ET.register_namespace('', uri)  # 注册为默认命名空间

        root = ET.Element(f'{{{uri}}}xliff', version=metadata.get('version', '1.2'))
        file_elem = ET.SubElement(root, f'{{{uri}}}file')
        file_elem.set('source-language', metadata.get('source_language', 'en'))

        app = kwargs.get('app_instance')
        target_lang = app.current_target_language if app else metadata.get('target_language', 'en')
        file_elem.set('target-language', target_lang)
        file_elem.set('datatype', 'plaintext')

        body_elem = ET.SubElement(file_elem, f'{{{uri}}}body')

        for ts in translatable_objects:
            if not ts.original_semantic or ts.id == "##NEW_ENTRY##": continue
            unit = ET.SubElement(body_elem, f'{{{uri}}}trans-unit', id=ts.context or f"u{ts.id[:8]}")
            ET.SubElement(unit, f'{{{uri}}}source').text = ts.original_semantic
            target = ET.SubElement(unit, f'{{{uri}}}target')
            target.text = ts.translation
            if ts.is_reviewed:
                target.set('state', 'translated')
            else:
                target.set('state', 'needs-translation')

            if ts.comment:
                ET.SubElement(unit, f'{{{uri}}}note').text = ts.comment

        tree = ET.ElementTree(root)
        if hasattr(ET, 'indent'): ET.indent(tree, space="  ")
        tree.write(filepath, encoding='utf-8', xml_declaration=True)


class AndroidStringsFormatHandler(BaseFormatHandler):
    """
    Android Strings XML 处理器

    支持的元素:
    - <string name="key">value</string>
    - <string name="key" translatable="false">value</string>
    - <plurals name="key">...</plurals>
    - <string-array name="key">...</string-array>
    """
    format_id = "android_strings"
    extensions = ['.xml']
    format_type = "translation"
    display_name = _("Android Strings XML")
    badge_text = "Android"
    badge_bg_color = "#E8F5E9"
    badge_text_color = "#1B5E20"

    def load(self, filepath, **kwargs):
        logger.debug(f"[AndroidStringsFormatHandler] Loading Android strings.xml: {filepath}")

        tree = ET.parse(filepath)
        root = tree.getroot()

        if root.tag != 'resources':
            raise ValueError("Not a valid Android strings.xml file (root element must be <resources>)")

        relative_path = kwargs.get('relative_path')
        if relative_path:
            xml_file_rel_path = relative_path
        else:
            xml_file_rel_path = self._get_relative_path(filepath)

        translatable_objects = []
        occurrence_counters = {}

        # 处理 <string> 元素
        for string_elem in root.findall('string'):
            self._process_string_element(
                string_elem, translatable_objects, occurrence_counters, xml_file_rel_path
            )

        # 处理 <plurals> 元素
        for plurals_elem in root.findall('plurals'):
            self._process_plurals_element(
                plurals_elem, translatable_objects, occurrence_counters, xml_file_rel_path
            )

        # 处理 <string-array> 元素
        for array_elem in root.findall('string-array'):
            self._process_array_element(
                array_elem, translatable_objects, occurrence_counters, xml_file_rel_path
            )

        # 尝试从文件名检测语言
        language_code = self._detect_language_from_path(filepath)

        metadata = {
            'xml_declaration': True,
            'indent': '    '  # Android 标准使用 4 空格
        }

        logger.info(f"[AndroidStringsFormatHandler] Loaded {len(translatable_objects)} strings from {filepath}")
        return translatable_objects, metadata, language_code

    def _get_relative_path(self, filepath: str) -> str:
        """获取文件相对路径"""
        current_path = Path(filepath).parent
        while True:
            if (current_path / "project.json").is_file():
                try:
                    return Path(filepath).relative_to(current_path).as_posix()
                except ValueError:
                    break
            if current_path.parent == current_path:
                break
            current_path = current_path.parent
        return os.path.basename(filepath)

    def _detect_language_from_path(self, filepath: str) -> str:
        """从文件路径检测语言 (例如: values-zh/strings.xml -> zh)"""
        path_parts = Path(filepath).parts
        for part in reversed(path_parts):
            if part.startswith('values-'):
                lang_code = part.replace('values-', '')
                # 处理 values-zh-rCN -> zh-CN
                lang_code = lang_code.replace('-r', '-')
                return lang_code
        return 'en'  # 默认 values/ 目录是英语

    def _process_string_element(
            self, elem: ET.Element, results: List[TranslatableString],
            occurrence_counters: Dict, file_rel_path: str
    ):
        """处理 <string> 元素"""

        name = elem.get('name')
        if not name:
            return

        # 检查 translatable 属性
        translatable = elem.get('translatable', 'true').lower() == 'true'
        if not translatable:
            return  # 跳过不可翻译的字符串

        # 提取文本（可能包含 CDATA）
        text = self._extract_text(elem)
        if not text or not text.strip():
            return

        # 生成唯一标识
        counter_key = (text, name)
        current_index = occurrence_counters.get(counter_key, 0)
        occurrence_counters[counter_key] = current_index + 1

        stable_name = f"{file_rel_path}::{name}::{text}::{current_index}"
        obj_id = xxhash.xxh128(stable_name.encode('utf-8')).hexdigest()

        # 检测格式化占位符
        placeholders = self._detect_android_placeholders(text)
        comment_parts = []
        if placeholders:
            comment_parts.append(f"Format arguments: {', '.join(placeholders)}")

        ts = TranslatableString(
            original_raw=text,
            original_semantic=text,
            line_num=0,
            char_pos_start_in_file=0,
            char_pos_end_in_file=0,
            full_code_lines=[],
            string_type="Android String",
            source_file_path=file_rel_path,
            occurrences=[(file_rel_path, name)],
            occurrence_index=current_index,
            id=obj_id
        )

        ts.context = name
        ts.comment = "\n".join(comment_parts) if comment_parts else ""
        ts.po_comment = f"#: Android string name: {name}"
        ts.is_reviewed = False
        ts.update_sort_weight()

        results.append(ts)

    def _process_plurals_element(
            self, elem: ET.Element, results: List[TranslatableString],
            occurrence_counters: Dict, file_rel_path: str
    ):
        """处理 <plurals> 元素"""

        name = elem.get('name')
        if not name:
            return

        # 处理每个 <item quantity="...">
        for item in elem.findall('item'):
            quantity = item.get('quantity', 'other')
            text = self._extract_text(item)

            if not text or not text.strip():
                continue

            # 使用 name:quantity 作为唯一标识
            full_name = f"{name}:{quantity}"

            counter_key = (text, full_name)
            current_index = occurrence_counters.get(counter_key, 0)
            occurrence_counters[counter_key] = current_index + 1

            stable_name = f"{file_rel_path}::{full_name}::{text}::{current_index}"
            obj_id = xxhash.xxh128(stable_name.encode('utf-8')).hexdigest()

            placeholders = self._detect_android_placeholders(text)
            comment_parts = [f"Plural form: {quantity}"]
            if placeholders:
                comment_parts.append(f"Format arguments: {', '.join(placeholders)}")

            ts = TranslatableString(
                original_raw=text,
                original_semantic=text,
                line_num=0,
                char_pos_start_in_file=0,
                char_pos_end_in_file=0,
                full_code_lines=[],
                string_type="Android Plural",
                source_file_path=file_rel_path,
                occurrences=[(file_rel_path, full_name)],
                occurrence_index=current_index,
                id=obj_id
            )

            ts.context = full_name
            ts.comment = "\n".join(comment_parts)
            ts.po_comment = f"#: Android plurals name: {name}, quantity: {quantity}"
            ts.is_reviewed = False
            ts.update_sort_weight()

            results.append(ts)

    def _process_array_element(
            self, elem: ET.Element, results: List[TranslatableString],
            occurrence_counters: Dict, file_rel_path: str
    ):
        """处理 <string-array> 元素"""

        name = elem.get('name')
        if not name:
            return

        # 处理每个 <item>
        for idx, item in enumerate(elem.findall('item')):
            text = self._extract_text(item)

            if not text or not text.strip():
                continue

            # 使用 name[index] 作为唯一标识
            full_name = f"{name}[{idx}]"

            counter_key = (text, full_name)
            current_index = occurrence_counters.get(counter_key, 0)
            occurrence_counters[counter_key] = current_index + 1

            stable_name = f"{file_rel_path}::{full_name}::{text}::{current_index}"
            obj_id = xxhash.xxh128(stable_name.encode('utf-8')).hexdigest()

            ts = TranslatableString(
                original_raw=text,
                original_semantic=text,
                line_num=0,
                char_pos_start_in_file=0,
                char_pos_end_in_file=0,
                full_code_lines=[],
                string_type="Android Array",
                source_file_path=file_rel_path,
                occurrences=[(file_rel_path, full_name)],
                occurrence_index=current_index,
                id=obj_id
            )

            ts.context = full_name
            ts.comment = f"Array item index: {idx}"
            ts.po_comment = f"#: Android string-array name: {name}, index: {idx}"
            ts.is_reviewed = False
            ts.update_sort_weight()

            results.append(ts)

    def _extract_text(self, elem: ET.Element) -> str:
        """提取元素的文本内容（处理 CDATA 和转义字符）"""
        if elem.text:
            # 解码 XML 转义
            return self._unescape_android_xml(elem.text)
        return ''

    def _unescape_android_xml(self, text: str) -> str:
        """解码 Android XML 转义字符"""
        # Android 特殊转义
        text = text.replace(r'\'', "'")
        text = text.replace(r'\"', '"')
        text = text.replace(r'\n', '\n')
        text = text.replace(r'\t', '\t')
        text = text.replace(r'\\', '\\')
        return text

    def _escape_android_xml(self, text: str) -> str:
        """编码 Android XML 转义字符"""
        text = text.replace('\\', r'\\')
        text = text.replace("'", r"\'")
        text = text.replace('"', r'\"')
        text = text.replace('\n', r'\n')
        text = text.replace('\t', r'\t')
        return text

    def _detect_android_placeholders(self, text: str) -> List[str]:
        """检测 Android 格式化占位符"""
        import re
        # 匹配 %1$s, %d, %2$f, %s 等
        pattern = r'%(\d+\$)?[diouxXeEfFgGaAcspn]'
        matches = re.findall(pattern, text)
        return [f"%{m}" if m else "%" for m in matches]

    def save(self, filepath, translatable_objects, metadata, **kwargs):
        """保存 Android strings.xml 文件"""
        logger.debug(f"[AndroidStringsFormatHandler] Saving Android strings.xml: {filepath}")

        # 创建根元素
        root = ET.Element('resources')

        # 按类型分组
        strings_by_type = {
            'string': [],
            'plurals': {},
            'array': {}
        }

        for ts in translatable_objects:
            if not ts.original_semantic or ts.id == "##NEW_ENTRY##":
                continue

            if ts.string_type == "Android String":
                strings_by_type['string'].append(ts)
            elif ts.string_type == "Android Plural":
                # 解析 name:quantity
                if ':' in ts.context:
                    name, quantity = ts.context.rsplit(':', 1)
                    if name not in strings_by_type['plurals']:
                        strings_by_type['plurals'][name] = []
                    strings_by_type['plurals'][name].append((quantity, ts))
            elif ts.string_type == "Android Array":
                # 解析 name[index]
                if '[' in ts.context:
                    name = ts.context[:ts.context.index('[')]
                    if name not in strings_by_type['array']:
                        strings_by_type['array'][name] = []
                    strings_by_type['array'][name].append(ts)

        # 添加 <string> 元素
        for ts in strings_by_type['string']:
            string_elem = ET.SubElement(root, 'string')
            string_elem.set('name', ts.context)
            translation = ts.translation if ts.translation else ts.original_semantic
            string_elem.text = self._escape_android_xml(translation)

        # 添加 <plurals> 元素
        for name, items in strings_by_type['plurals'].items():
            plurals_elem = ET.SubElement(root, 'plurals')
            plurals_elem.set('name', name)

            for quantity, ts in sorted(items, key=lambda x: x[0]):
                item_elem = ET.SubElement(plurals_elem, 'item')
                item_elem.set('quantity', quantity)
                translation = ts.translation if ts.translation else ts.original_semantic
                item_elem.text = self._escape_android_xml(translation)

        # 添加 <string-array> 元素
        for name, items in strings_by_type['array'].items():
            array_elem = ET.SubElement(root, 'string-array')
            array_elem.set('name', name)

            # 按索引排序
            sorted_items = sorted(items,
                                  key=lambda ts: int(ts.context[ts.context.index('[') + 1:ts.context.index(']')]))

            for ts in sorted_items:
                item_elem = ET.SubElement(array_elem, 'item')
                translation = ts.translation if ts.translation else ts.original_semantic
                item_elem.text = self._escape_android_xml(translation)

        # 格式化并保存
        tree = ET.ElementTree(root)
        if hasattr(ET, 'indent'):
            ET.indent(tree, space="    ", level=0)

        tree.write(filepath, encoding='utf-8', xml_declaration=True)

        logger.info(f"[AndroidStringsFormatHandler] Saved {len(translatable_objects)} strings to {filepath}")


class IosStringsFormatHandler(BaseFormatHandler):
    """
    Apple iOS / macOS 本地化文件处理器

    支持的格式与特性:
    1. .strings 文件: 标准 "key" = "value"; 格式，完整保留行内注释和块注释
    2. .stringsdict 文件: XML Plist 复数规则，支持 NSStringLocalizedFormatKey
       以及所有 CLDR 复数类别 (zero/one/two/few/many/other)
    3. 注释提取: 块注释 /* ... */ 和行注释 // 均可作为 translator comment 保留
    4. 转义处理: 正确处理 \\n \\t \\\\ \\\" 等 Apple 转义序列的双向转换
    5. 状态检测: 自动将 value == key 或 value 为空的条目标记为待审阅
    6. 路径语言检测: 从 xx.lproj/Localizable.strings 路径自动解析语言代码
    """
    format_id = "ios_strings"
    extensions = ['.strings', '.stringsdict']
    format_type = "translation"
    display_name = _("Apple .strings / .stringsdict")
    badge_text = "iOS"
    badge_bg_color = "#F9FBE7"
    badge_text_color = "#558B2F"

    def load(self, filepath, **kwargs):
        ext = os.path.splitext(filepath)[1].lower()
        relative_path = kwargs.get('relative_path') or self._get_relative_path(filepath)
        language_code = self._detect_language_from_path(filepath)

        if ext == '.stringsdict':
            objects, meta = self._load_stringsdict(filepath, relative_path)
        else:
            objects, meta = self._load_strings(filepath, relative_path)

        return objects, meta, language_code

    def _load_strings(self, filepath, rel_path):
        with open(filepath, 'r', encoding='utf-8-sig', errors='replace') as f:
            content = f.read()

        translatable_objects = []
        occurrence_counters = {}

        # 解析所有条目（带前置注释）
        # 语法: (可选注释块/行) "key" = "value";
        token_re = re.compile(
            r'(?:(?P<block_comment>/\*.*?\*/)|(?P<line_comment>//[^\n]*\n))'
            r'|"(?P<key>(?:[^"\\]|\\.)*)"\s*=\s*"(?P<value>(?:[^"\\]|\\.)*)"\s*;',
            re.DOTALL
        )

        pending_comment = []
        for m in token_re.finditer(content):
            if m.group('block_comment'):
                text = m.group('block_comment')[2:-2].strip()
                pending_comment.append(text)
            elif m.group('line_comment'):
                text = m.group('line_comment')[2:].strip()
                pending_comment.append(text)
            else:
                key = self._unescape(m.group('key'))
                value = self._unescape(m.group('value'))
                comment = '\n'.join(pending_comment).strip()
                pending_comment.clear()

                if not key:
                    continue

                counter_key = (key, rel_path)
                idx = occurrence_counters.get(counter_key, 0)
                occurrence_counters[counter_key] = idx + 1

                stable = f"{rel_path}::{key}::{idx}"
                obj_id = xxhash.xxh128(stable.encode()).hexdigest()

                ts = TranslatableString(
                    original_raw=key, original_semantic=key,
                    line_num=0,
                    char_pos_start_in_file=0, char_pos_end_in_file=0,
                    full_code_lines=[],
                    string_type="iOS String",
                    source_file_path=rel_path,
                    occurrences=[(rel_path, key)],
                    occurrence_index=idx,
                    id=obj_id
                )
                ts.translation = value
                ts.context = key
                ts.comment = comment
                ts.po_comment = f"#: Apple strings key: {key}"
                # value == key 通常意味着尚未翻译（源语言文件）
                ts.is_reviewed = bool(value and value != key)
                ts.update_sort_weight()
                translatable_objects.append(ts)

        meta = {'format': 'strings', 'raw_content': content}
        logger.info(f"[IosStringsFormatHandler] Loaded {len(translatable_objects)} entries from {filepath}")
        return translatable_objects, meta

    def _load_stringsdict(self, filepath, rel_path):
        """
        解析 .stringsdict (Binary / XML Plist)。
        顶层结构:
          {
            "<key>": {
              "NSStringLocalizedFormatKey": "%#@value@",
              "value": {
                "NSStringFormatSpecTypeKey": "NSStringPluralRuleType",
                "NSStringFormatValueTypeKey": "d",
                "zero": "...", "one": "...", "two": "...",
                "few": "...", "many": "...", "other": "..."
              }
            }
          }
        """
        with open(filepath, 'rb') as f:
            try:
                data = plistlib.load(f)
            except Exception as e:
                logger.error(f"Failed to parse stringsdict plist: {e}")
                return [], {'format': 'stringsdict', 'original_data': {}}

        translatable_objects = []
        occurrence_counters = {}
        plural_categories = ['zero', 'one', 'two', 'few', 'many', 'other']

        for top_key, top_value in data.items():
            if not isinstance(top_value, dict):
                continue

            format_key = top_value.get('NSStringLocalizedFormatKey', '')

            # 遍历所有变量规则块
            for var_name, var_dict in top_value.items():
                if var_name == 'NSStringLocalizedFormatKey':
                    continue
                if not isinstance(var_dict, dict):
                    continue
                if var_dict.get('NSStringFormatSpecTypeKey') != 'NSStringPluralRuleType':
                    continue

                value_type = var_dict.get('NSStringFormatValueTypeKey', 'd')

                for category in plural_categories:
                    text = var_dict.get(category)
                    if text is None:
                        continue

                    full_context = f"{top_key}.{var_name}.{category}"
                    counter_key = (text, full_context)
                    idx = occurrence_counters.get(counter_key, 0)
                    occurrence_counters[counter_key] = idx + 1

                    stable = f"{rel_path}::{full_context}::{text}::{idx}"
                    obj_id = xxhash.xxh128(stable.encode()).hexdigest()

                    ts = TranslatableString(
                        original_raw=text, original_semantic=text,
                        line_num=0,
                        char_pos_start_in_file=0, char_pos_end_in_file=0,
                        full_code_lines=[],
                        string_type="iOS Plural",
                        source_file_path=rel_path,
                        occurrences=[(rel_path, full_context)],
                        occurrence_index=idx,
                        id=obj_id
                    )
                    ts.translation = text
                    ts.context = full_context
                    ts.comment = (
                        f"Plural category: {category}\n"
                        f"Format variable: {var_name} (type: %{value_type})\n"
                        f"Format key: {format_key}"
                    )
                    ts.po_comment = (
                        f"#: stringsdict key: {top_key}, "
                        f"variable: {var_name}, category: {category}"
                    )
                    ts.is_reviewed = False
                    ts.update_sort_weight()
                    translatable_objects.append(ts)

        meta = {'format': 'stringsdict', 'original_data': data}
        logger.info(f"[IosStringsFormatHandler] Loaded {len(translatable_objects)} plural entries from {filepath}")
        return translatable_objects, meta

    def save(self, filepath, translatable_objects, metadata, **kwargs):
        fmt = metadata.get('format', 'strings')
        if fmt == 'stringsdict':
            self._save_stringsdict(filepath, translatable_objects, metadata)
        else:
            self._save_strings(filepath, translatable_objects, metadata)

    def _save_strings(self, filepath, translatable_objects, metadata):
        lines = []
        for ts in translatable_objects:
            if not ts.original_semantic or ts.id == "##NEW_ENTRY##":
                continue
            if ts.comment:
                # 多行注释写成块注释
                lines.append(f"/* {ts.comment} */")
            translation = ts.translation if ts.translation else ts.original_semantic
            escaped_key = self._escape(ts.context or ts.original_semantic)
            escaped_val = self._escape(translation)
            lines.append(f'"{escaped_key}" = "{escaped_val}";')
            lines.append('')

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        logger.info(f"[IosStringsFormatHandler] Saved {len(translatable_objects)} strings to {filepath}")

    def _save_stringsdict(self, filepath, translatable_objects, metadata):
        """重建 plist 数据结构并写出。"""
        original_data = metadata.get('original_data', {})

        # 将翻译回填进原始结构的副本
        import copy
        new_data = copy.deepcopy(original_data)

        # 建立 context -> translation 映射
        trans_map = {
            ts.context: ts.translation
            for ts in translatable_objects
            if ts.translation and not ts.is_ignored and ts.context
        }

        for top_key, top_value in new_data.items():
            if not isinstance(top_value, dict):
                continue
            for var_name, var_dict in top_value.items():
                if var_name == 'NSStringLocalizedFormatKey':
                    continue
                if not isinstance(var_dict, dict):
                    continue
                for category in ['zero', 'one', 'two', 'few', 'many', 'other']:
                    if category not in var_dict:
                        continue
                    ctx = f"{top_key}.{var_name}.{category}"
                    if ctx in trans_map:
                        var_dict[category] = trans_map[ctx]

        with open(filepath, 'wb') as f:
            plistlib.dump(new_data, f, fmt=plistlib.FMT_XML)
        logger.info(f"[IosStringsFormatHandler] Saved stringsdict to {filepath}")

    def _unescape(self, s: str) -> str:
        """将 .strings 转义序列还原为真实字符。"""
        return (s
                .replace('\\"', '"')
                .replace("\\'", "'")
                .replace('\\n', '\n')
                .replace('\\r', '\r')
                .replace('\\t', '\t')
                .replace('\\\\', '\\'))

    def _escape(self, s: str) -> str:
        """将真实字符编码为 .strings 转义序列。"""
        return (s
                .replace('\\', '\\\\')
                .replace('"', '\\"')
                .replace('\n', '\\n')
                .replace('\r', '\\r')
                .replace('\t', '\\t'))

    def _detect_language_from_path(self, filepath: str) -> str:
        """
        从 Xcode 项目的 lproj 路径提取语言代码。
        例: en.lproj/Localizable.strings  →  'en'
            zh-Hans.lproj/...             →  'zh-Hans'
        """
        for part in Path(filepath).parts:
            if part.endswith('.lproj'):
                return part[:-len('.lproj')]
        return 'en'

    def _get_relative_path(self, filepath: str) -> str:
        current = Path(filepath).parent
        while True:
            if (current / 'project.json').is_file():
                try:
                    return Path(filepath).relative_to(current).as_posix()
                except ValueError:
                    break
            if current.parent == current:
                break
            current = current.parent
        return os.path.basename(filepath)


class ArbFormatHandler(BaseFormatHandler):
    """
    Flutter / Dart ARB (Application Resource Bundle) 格式处理器

    支持的特性:
    1. 元数据保留: 完整读写 @@locale、@@last_modified 等文件级元数据
    2. 条目描述符: 支持 @key 块中的 description、placeholders、plural 字段
    3. 占位符解析: 自动识别 {name}、{count} 形式的插值占位符并记录到注释
    4. 复数/性别: 识别 ICU MessageFormat 语法 (plural/select/gender) 并保留原样
    5. 非翻译键过滤: 自动跳过以 @@ 开头的全局元数据键
    6. 语言检测: 优先读取 @@locale 字段，其次从文件名 (app_en.arb) 推断
    """
    format_id = "arb"
    extensions = ['.arb']
    format_type = "translation"
    display_name = _("Flutter ARB File")
    badge_text = "ARB"
    badge_bg_color = "#E8EAF6"
    badge_text_color = "#283593"

    def load(self, filepath, **kwargs):
        logger.debug(f"[ArbFormatHandler] Loading ARB file: {filepath}")

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            data = json.loads(content)

        relative_path = kwargs.get('relative_path') or self._get_relative_path(filepath)
        language_code = self._detect_language(data, os.path.basename(filepath))
        indent = self._detect_indent(content)

        translatable_objects = []
        occurrence_counters = {}

        # 全局元数据 (@@locale, @@last_modified …) — 保留但不翻译
        global_metadata = {k: v for k, v in data.items() if k.startswith('@@')}

        # 遍历所有翻译键
        for key, value in data.items():
            if key.startswith('@'):          # @key 描述符或 @@ 全局元数据 — 跳过
                continue
            if not isinstance(value, str):   # ARB 规范: 翻译值必须为字符串
                continue
            if not value.strip():
                continue

            # 获取对应的 @key 描述符
            descriptor = data.get(f'@{key}', {})
            description = descriptor.get('description', '') if isinstance(descriptor, dict) else ''
            placeholders = descriptor.get('placeholders', {}) if isinstance(descriptor, dict) else {}

            # 构建人类可读的占位符说明
            ph_notes = []
            for ph_name, ph_info in placeholders.items():
                ph_type = ph_info.get('type', 'String') if isinstance(ph_info, dict) else 'String'
                ph_example = ph_info.get('example', '') if isinstance(ph_info, dict) else ''
                note = f"{{{ph_name}}}: {ph_type}"
                if ph_example:
                    note += f" (e.g. {ph_example})"
                ph_notes.append(note)

            counter_key = (value, key)
            idx = occurrence_counters.get(counter_key, 0)
            occurrence_counters[counter_key] = idx + 1

            stable = f"{relative_path}::{key}::{value}::{idx}"
            obj_id = xxhash.xxh128(stable.encode()).hexdigest()

            ts = TranslatableString(
                original_raw=value, original_semantic=value,
                line_num=0,
                char_pos_start_in_file=0, char_pos_end_in_file=0,
                full_code_lines=[],
                string_type="ARB String",
                source_file_path=relative_path,
                occurrences=[(relative_path, key)],
                occurrence_index=idx,
                id=obj_id
            )
            ts.translation = value
            ts.context = key
            ts.comment = description
            ts.po_comment = (
                f"#: ARB key: {key}"
                + (f"\n#. Placeholders: {', '.join(ph_notes)}" if ph_notes else "")
            )
            ts.is_reviewed = False
            ts.update_sort_weight()
            translatable_objects.append(ts)

        metadata = {
            'indent': indent,
            'global_metadata': global_metadata,
            'descriptors': {k[1:]: v for k, v in data.items()
                            if k.startswith('@') and not k.startswith('@@')},
        }

        logger.info(f"[ArbFormatHandler] Loaded {len(translatable_objects)} strings from {filepath}")
        return translatable_objects, metadata, language_code

    def save(self, filepath, translatable_objects, metadata, **kwargs):
        logger.debug(f"[ArbFormatHandler] Saving ARB file: {filepath}")

        indent = metadata.get('indent', 4)
        global_metadata = metadata.get('global_metadata', {})
        descriptors = metadata.get('descriptors', {})

        app = kwargs.get('app_instance')
        target_lang = None
        if app:
            target_lang = (app.current_target_language
                           if app.is_project_mode else app.target_language)

        output = {}

        # 写入 @@locale
        locale = target_lang or global_metadata.get('@@locale', 'en')
        output['@@locale'] = locale

        # 写入其他 @@ 全局元数据（排除 @@locale，已单独写）
        for k, v in global_metadata.items():
            if k != '@@locale':
                output[k] = v

        # 写入翻译条目 + 对应描述符
        for ts in translatable_objects:
            if not ts.original_semantic or ts.id == '##NEW_ENTRY##':
                continue
            key = ts.context or ts.original_semantic
            translation = ts.translation if ts.translation else ts.original_semantic
            output[key] = translation

            # 还原 @key 描述符（保留原有占位符、描述等）
            if key in descriptors:
                output[f'@{key}'] = descriptors[key]
            elif ts.comment:
                # 若原本没有描述符但有 description，生成一个最简描述符
                output[f'@{key}'] = {'description': ts.comment}

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=indent, ensure_ascii=False)
            f.write('\n')  # ARB 文件惯例以换行结尾

        logger.info(f"[ArbFormatHandler] Saved {len(translatable_objects)} strings to {filepath}")

    def _detect_indent(self, content: str) -> int:
        for line in content.split('\n')[1:]:
            stripped = line.lstrip()
            if stripped and line != stripped:
                indent = len(line) - len(stripped)
                if indent > 0:
                    return indent
        return 4  # Flutter 官方工具默认 4 空格

    def _detect_language(self, data: dict, filename: str) -> str:
        # 优先读取 @@locale
        if '@@locale' in data:
            return data['@@locale']
        # 从文件名推断: intl_en.arb / app_zh_CN.arb / en.arb
        name = filename.lower().replace('.arb', '')
        parts = re.split(r'[_\-]', name)
        common = {'en', 'zh', 'ja', 'ko', 'fr', 'de', 'es', 'it', 'ru', 'pt', 'ar',
                  'tr', 'pl', 'nl', 'sv', 'da', 'fi', 'nb', 'cs', 'sk', 'hu', 'ro'}
        for part in reversed(parts):
            if part in common:
                return part
        return 'en'

    def _get_relative_path(self, filepath: str) -> str:
        current = Path(filepath).parent
        while True:
            if (current / 'project.json').is_file():
                try:
                    return Path(filepath).relative_to(current).as_posix()
                except ValueError:
                    break
            if current.parent == current:
                break
            current = current.parent
        return os.path.basename(filepath)


class JsonI18nFormatHandler(BaseFormatHandler):
    """
    JSON 国际化文件处理器
    支持的格式:
    1. 扁平结构: {"key1": "value1", "key2": "value2"}
    2. 嵌套结构: {"menu": {"home": "Home", "about": "About"}}
    3. 数组: {"items": ["Item 1", "Item 2"]}
    4. 混合: {"user": {"messages": ["Welcome", "Goodbye"]}}
    """
    format_id = "json_i18n"
    extensions = ['.json']
    format_type = "translation"
    display_name = _("JSON i18n File")
    badge_text = "JSON"
    badge_bg_color = "#FFF3E0"
    badge_text_color = "#E65100"

    def load(self, filepath, **kwargs):
        logger.debug(f"[JsonI18nFormatHandler] Loading JSON file: {filepath}")

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            data = json.loads(content)

        # 检测 JSON 缩进
        indent = self._detect_indent(content)

        relative_path = kwargs.get('relative_path')
        if relative_path:
            json_file_rel_path = relative_path
        else:
            json_file_rel_path = self._get_relative_path(filepath)

        translatable_objects = []
        occurrence_counters = {}

        # 递归提取所有可翻译字符串
        self._extract_recursive(
            data, [], translatable_objects, occurrence_counters,
            json_file_rel_path, line_num=1
        )

        metadata = {
            'original_structure': data,
            'indent': indent,
            'ensure_ascii': False  # 保留 Unicode 字符
        }

        # 尝试检测语言代码
        language_code = self._detect_language(data, os.path.basename(filepath))

        logger.info(f"[JsonI18nFormatHandler] Loaded {len(translatable_objects)} strings from {filepath}")
        return translatable_objects, metadata, language_code

    def _detect_indent(self, json_content: str) -> int:
        """检测 JSON 文件的缩进空格数"""
        lines = json_content.split('\n')
        for line in lines[1:]:  # 跳过第一行
            stripped = line.lstrip()
            if stripped and line != stripped:
                indent = len(line) - len(stripped)
                if indent > 0:
                    return indent
        return 2  # 默认 2 空格

    def _get_relative_path(self, filepath: str) -> str:
        """获取文件相对于项目根目录的路径"""
        current_path = Path(filepath).parent
        while True:
            if (current_path / "project.json").is_file():
                try:
                    return Path(filepath).relative_to(current_path).as_posix()
                except ValueError:
                    break
            if current_path.parent == current_path:
                break
            current_path = current_path.parent
        return os.path.basename(filepath)

    def _detect_language(self, data: Dict, filename: str) -> str:
        # 从文件名检测: en.json, zh-CN.json, messages_fr.json
        name_lower = filename.lower().replace('.json', '')
        common_langs = ['en', 'zh', 'ja', 'ko', 'fr', 'de', 'es', 'it', 'ru', 'pt', 'ar']
        for lang in common_langs:
            if lang in name_lower:
                return lang

        # 从数据结构检测: {"locale": "en", ...} 或 {"en": {...}}
        if isinstance(data, dict):
            if 'locale' in data or 'language' in data or 'lang' in data:
                lang_value = data.get('locale') or data.get('language') or data.get('lang')
                if isinstance(lang_value, str):
                    return lang_value

            # 检查顶层键是否为语言代码
            top_keys = list(data.keys())
            if len(top_keys) == 1 and top_keys[0] in common_langs:
                return top_keys[0]

        return 'en'  # 默认英语

    def _extract_recursive(
            self, obj: Any, key_path: List[str], results: List[TranslatableString],
            occurrence_counters: Dict, file_rel_path: str, line_num: int
    ):
        """递归提取 JSON 中的所有可翻译字符串"""

        if isinstance(obj, dict):
            for key, value in obj.items():
                self._extract_recursive(
                    value, key_path + [key], results, occurrence_counters,
                    file_rel_path, line_num
                )

        elif isinstance(obj, list):
            for idx, item in enumerate(obj):
                # 数组索引也作为路径的一部分
                self._extract_recursive(
                    item, key_path + [f"[{idx}]"], results, occurrence_counters,
                    file_rel_path, line_num
                )

        elif isinstance(obj, str):
            # 只提取非空字符串
            if obj.strip():
                self._create_translatable_string(
                    obj, key_path, results, occurrence_counters,
                    file_rel_path, line_num
                )

    def _create_translatable_string(self, text, key_path, results, occurrence_counters, file_rel_path, line_num):
        """创建 TranslatableString 对象"""

        # 生成完整键路径作为 context
        full_key = ".".join(key_path)

        # 生成唯一计数器键
        counter_key = (text, full_key)
        current_index = occurrence_counters.get(counter_key, 0)
        occurrence_counters[counter_key] = current_index + 1

        # 生成稳定的 UUID
        stable_name = f"{file_rel_path}::{full_key}::{text}::{current_index}"
        obj_id = xxhash.xxh128(stable_name.encode('utf-8')).hexdigest()

        ts = TranslatableString(
            original_raw=text,
            original_semantic=text,
            line_num=line_num,
            char_pos_start_in_file=0,
            char_pos_end_in_file=0,
            full_code_lines=[],
            string_type="JSON i18n",
            source_file_path=file_rel_path,
            occurrences=[(file_rel_path, str(line_num))],
            occurrence_index=current_index,
            id=obj_id
        )

        ts.context = full_key
        ts.comment = ""
        ts.po_comment = f"#: JSON key path: {full_key}"
        ts.is_reviewed = False
        ts.update_sort_weight()

        results.append(ts)

    def save(self, filepath, translatable_objects, metadata, **kwargs):
        """保存翻译后的 JSON 文件"""
        logger.debug(f"[JsonI18nFormatHandler] Saving JSON file: {filepath}")

        # 获取原始结构
        original_structure = metadata.get('original_structure', {})
        indent = metadata.get('indent', 2)
        ensure_ascii = metadata.get('ensure_ascii', False)

        # 创建翻译映射: key_path -> translation
        translation_map = {}
        for ts in translatable_objects:
            if ts.translation and not ts.is_ignored and ts.context:
                translation_map[ts.context] = ts.translation

        # 重建 JSON 结构
        translated_structure = self._rebuild_structure(
            original_structure, translation_map
        )

        # 保存文件
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(
                translated_structure,
                f,
                indent=indent,
                ensure_ascii=ensure_ascii,
                sort_keys=False
            )

        logger.info(f"[JsonI18nFormatHandler] Saved {len(translation_map)} translations to {filepath}")

    def _rebuild_structure(self, obj: Any, translation_map: Dict[str, str], key_path: List[str] = None) -> Any:
        """递归重建 JSON 结构，应用翻译"""
        if key_path is None:
            key_path = []

        if isinstance(obj, dict):
            result = {}
            for key, value in obj.items():
                result[key] = self._rebuild_structure(value, translation_map, key_path + [key])
            return result

        elif isinstance(obj, list):
            result = []
            for idx, item in enumerate(obj):
                result.append(
                    self._rebuild_structure(item, translation_map, key_path + [f"[{idx}]"])
                )
            return result

        elif isinstance(obj, str):
            # 查找翻译
            full_key = ".".join(key_path)
            return translation_map.get(full_key, obj)

        else:
            return obj


class YamlI18nFormatHandler(BaseFormatHandler):
    """
    YAML 国际化文件处理器

    支持的框架与格式:
    1. Ruby on Rails i18n: en:\n  key: value  (顶层语言键包装结构)
    2. Vue i18n / react-i18next: 扁平或嵌套 YAML，无顶层语言键
    3. 通用嵌套: 任意深度嵌套映射，键路径以 . 连接作为 context
    4. 多行字面量块 (|) 与折叠块 (>): 正确提取完整文本，保存时
       自动选择最合适的块标量风格

    关键技术决策:
    - 使用 ruamel.yaml 而非 PyYAML，以确保注释、键顺序、缩进风格
      在加载/保存过程中完整保留（PyYAML 会丢失注释和 key 顺序）
    - 若 ruamel.yaml 不可用则自动回退到 PyYAML（功能降级：注释丢失）
    - Rails 顶层语言键 (如 `en:`) 自动识别并在保存时还原，不作为翻译条目
    - 跳过非字符串叶节点（数字、布尔、null），防止误提取配置值
    - 数组中的字符串元素以 key[0], key[1] 形式纳入翻译管理
    """
    format_id = "yaml_i18n"
    extensions = ['.yml', '.yaml']
    format_type = "translation"
    display_name = _("YAML i18n File")
    badge_text = "YAML"
    badge_bg_color = "#F1F8E9"
    badge_text_color = "#33691E"

    # Rails 风格顶层语言键检测：单个符合 BCP-47 的顶层键
    _LANG_CODE_RE = re.compile(
        r'^[a-z]{2,3}(?:[_-][A-Za-z]{2,4})?$'
    )

    def load(self, filepath, **kwargs):
        logger.debug(f"[YamlI18nFormatHandler] Loading YAML: {filepath}")

        with open(filepath, 'r', encoding='utf-8') as f:
            raw_content = f.read()

        data, yaml_backend = self._yaml_load(raw_content)
        if not isinstance(data, dict):
            logger.warning(f"[YamlI18nFormatHandler] Root is not a mapping: {filepath}")
            return [], {}, 'en'

        rel_path = kwargs.get('relative_path') or self._get_relative_path(filepath)
        language_code = self._detect_language(data, os.path.basename(filepath))

        # Rails 顶层语言键解包
        rails_lang_key, data_root = self._unwrap_rails_root(data)

        translatable_objects = []
        occurrence_counters = {}
        self._extract_recursive(
            data_root, [], translatable_objects, occurrence_counters, rel_path
        )

        metadata = {
            'raw_content': raw_content,
            'rails_lang_key': rails_lang_key,
            'yaml_backend': yaml_backend,
        }

        logger.info(f"[YamlI18nFormatHandler] Loaded {len(translatable_objects)} strings from {filepath}")
        return translatable_objects, metadata, language_code

    def _yaml_load(self, content: str) -> Tuple[Any, str]:
        """加载 YAML，返回 (data, backend_name)"""
        try:
            from ruamel.yaml import YAML
            yaml = YAML()
            yaml.preserve_quotes = True
            import io
            data = yaml.load(io.StringIO(content))
            return data, 'ruamel'
        except ImportError:
            pass

        try:
            import yaml as pyyaml
            data = pyyaml.safe_load(content)
            return data, 'pyyaml'
        except Exception as e:
            logger.error(f"[YamlI18nFormatHandler] YAML parse error: {e}")
            return {}, 'pyyaml'

    def _yaml_dump(self, data: Any, backend: str, indent: int = 2) -> str:
        """序列化 YAML，尽量保持原格式"""
        if backend == 'ruamel':
            try:
                from ruamel.yaml import YAML
                import io
                yaml = YAML()
                yaml.default_flow_style = False
                yaml.allow_unicode = True
                yaml.indent(mapping=indent, sequence=indent, offset=indent)
                buf = io.StringIO()
                yaml.dump(data, buf)
                return buf.getvalue()
            except ImportError:
                pass

        import yaml as pyyaml
        return pyyaml.dump(
            data, allow_unicode=True, default_flow_style=False,
            indent=indent, sort_keys=False
        )

    def _unwrap_rails_root(self, data: Dict) -> Tuple[Optional[str], Any]:
        """
        如果数据只有一个顶层键且符合语言码格式，视为 Rails 风格并解包。
        返回 (lang_key_or_None, inner_data)
        """
        keys = list(data.keys()) if isinstance(data, dict) else []
        if len(keys) == 1:
            key = str(keys[0])
            if self._LANG_CODE_RE.match(key):
                return key, data[key] if isinstance(data[key], dict) else data
        return None, data

    def _wrap_rails_root(self, data: Any, lang_key: Optional[str]) -> Any:
        """将数据重新包装到 Rails 顶层语言键下"""
        if lang_key:
            return {lang_key: data}
        return data

    def _extract_recursive(
        self, obj: Any, key_path: List[str],
        results: List[TranslatableString], counters: Dict, rel_path: str
    ):
        if isinstance(obj, dict):
            for k, v in obj.items():
                self._extract_recursive(v, key_path + [str(k)], results, counters, rel_path)

        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                self._extract_recursive(item, key_path + [f"[{i}]"], results, counters, rel_path)

        elif isinstance(obj, str) and obj.strip():
            self._make_ts(obj, key_path, results, counters, rel_path)

    def _make_ts(
        self, text: str, key_path: List[str],
        results: List[TranslatableString], counters: Dict, rel_path: str
    ):
        full_key = '.'.join(
            p if not p.startswith('[') else p
            for p in key_path
        )
        # 美化：去掉 .[0] -> [0] 多余的点
        full_key = re.sub(r'\.\[', '[', full_key)

        counter_key = (text, full_key)
        idx = counters.get(counter_key, 0)
        counters[counter_key] = idx + 1

        stable = f"{rel_path}::{full_key}::{text}::{idx}"
        obj_id = xxhash.xxh128(stable.encode('utf-8')).hexdigest()

        ts = TranslatableString(
            original_raw=text, original_semantic=text,
            line_num=0,
            char_pos_start_in_file=0, char_pos_end_in_file=0,
            full_code_lines=[],
            string_type="YAML i18n",
            source_file_path=rel_path,
            occurrences=[(rel_path, full_key)],
            occurrence_index=idx,
            id=obj_id
        )
        ts.translation = text
        ts.context = full_key
        ts.comment = ""
        ts.po_comment = f"#: YAML key: {full_key}"
        ts.is_reviewed = False
        ts.update_sort_weight()
        results.append(ts)

    def _rebuild_recursive(
        self, obj: Any, key_path: List[str], translation_map: Dict[str, str]
    ) -> Any:
        """递归将原始 YAML 结构中的字符串替换为译文"""
        if isinstance(obj, dict):
            # ruamel.yaml CommentedMap 需要逐键更新而非整体替换
            result = obj.__class__() if hasattr(obj, '__class__') and hasattr(obj, 'ca') else {}
            for k, v in obj.items():
                result[k] = self._rebuild_recursive(v, key_path + [str(k)], translation_map)
            return result

        elif isinstance(obj, list):
            cls = obj.__class__ if hasattr(obj, 'ca') else list
            result = cls()
            for i, item in enumerate(obj):
                rebuilt = self._rebuild_recursive(item, key_path + [f"[{i}]"], translation_map)
                result.append(rebuilt)
            return result

        elif isinstance(obj, str):
            full_key = re.sub(r'\.\[', '[', '.'.join(
                p if not p.startswith('[') else p for p in key_path
            ))
            return translation_map.get(full_key, obj)

        return obj

    def _detect_language(self, data: Dict, filename: str) -> str:
        # 优先从 Rails 顶层键检测
        keys = list(data.keys()) if isinstance(data, dict) else []
        if len(keys) == 1:
            key = str(keys[0])
            if self._LANG_CODE_RE.match(key):
                return key

        # 从文件名检测: zh-CN.yml / messages.fr.yml / i18n_de.yaml
        stem = os.path.splitext(filename)[0]
        m = re.search(r'(?:^|[_.-])([a-z]{2,3}(?:[_-][A-Za-z]{2,4})?)(?:[_.-]|$)', stem)
        if m:
            candidate = m.group(1)
            if self._LANG_CODE_RE.match(candidate):
                return candidate

        return 'en'

    def _get_relative_path(self, filepath: str) -> str:
        current = Path(filepath).parent
        while True:
            if (current / 'project.json').is_file():
                try:
                    return Path(filepath).relative_to(current).as_posix()
                except ValueError:
                    break
            if current.parent == current:
                break
            current = current.parent
        return os.path.basename(filepath)

    def save(self, filepath, translatable_objects, metadata, **kwargs):
        logger.debug(f"[YamlI18nFormatHandler] Saving YAML: {filepath}")

        translation_map = {
            ts.context: (ts.translation or ts.original_semantic)
            for ts in translatable_objects
            if ts.original_semantic and ts.id != "##NEW_ENTRY##"
                and not ts.is_ignored and ts.context
        }

        raw_content = metadata.get('raw_content', '')
        rails_lang_key = metadata.get('rails_lang_key')
        backend = metadata.get('yaml_backend', 'pyyaml')

        # 重新加载原始结构（保留注释，如果使用 ruamel）
        original_data, _ = self._yaml_load(raw_content)
        _, data_root = self._unwrap_rails_root(original_data)

        # 递归替换
        translated_root = self._rebuild_recursive(data_root, [], translation_map)

        # 还原 Rails 顶层键包装
        output_data = self._wrap_rails_root(translated_root, rails_lang_key)

        yaml_str = self._yaml_dump(output_data, backend)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(yaml_str)

        logger.info(f"[YamlI18nFormatHandler] Saved {len(translation_map)} strings to {filepath}")


class TomlFormatHandler(BaseFormatHandler):
    """
    TOML 配置文件处理器
    使用 tomlkit 库以确保在保存时完美还原注释、空行和结构顺序。
    """
    format_id = "toml"
    extensions = ['.toml']
    format_type = "translation"
    display_name = _("TOML Config File")
    badge_text = "TOML"
    badge_bg_color = "#FCE4EC"
    badge_text_color = "#3F51B5"

    def load(self, filepath, **kwargs):
        try:
            import tomlkit
        except ImportError:
            raise ImportError(
                _("The 'tomlkit' library is required to read TOML files. Please install it via 'pip install tomlkit'."))

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            doc = tomlkit.parse(content)

        rel_path = kwargs.get('relative_path') or os.path.basename(filepath)
        translatable_objects = []
        occurrence_counters = {}

        self._extract_recursive(doc, [], translatable_objects, occurrence_counters, rel_path)

        metadata = {'raw_content': content}
        return translatable_objects, metadata, 'en'

    def _extract_recursive(self, obj, key_path, results, counters, rel_path):
        if isinstance(obj, dict):
            for k, v in obj.items():
                self._extract_recursive(v, key_path + [str(k)], results, counters, rel_path)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                self._extract_recursive(item, key_path + [f"[{i}]"], results, counters, rel_path)
        elif isinstance(obj, str) and obj.strip():
            # 过滤掉看起来像颜色、路径或纯数字的字符串
            if re.match(r'^#[0-9a-fA-F]{3,8}$', obj): return
            if re.match(r'^(?:https?://|/|\./)', obj): return

            full_key = '.'.join(p if not p.startswith('[') else p for p in key_path)
            full_key = re.sub(r'\.\[', '[', full_key)

            counter_key = (obj, full_key)
            idx = counters.get(counter_key, 0)
            counters[counter_key] = idx + 1

            stable = f"{rel_path}::{full_key}::{obj}::{idx}"
            obj_id = xxhash.xxh128(stable.encode()).hexdigest()

            ts = TranslatableString(
                original_raw=obj, original_semantic=obj,
                line_num=0, char_pos_start_in_file=0, char_pos_end_in_file=0,
                full_code_lines=[], string_type="TOML String",
                source_file_path=rel_path, occurrences=[(rel_path, full_key)],
                occurrence_index=idx, id=obj_id
            )
            ts.translation = obj
            ts.context = full_key
            ts.po_comment = f"#: TOML key: {full_key}"
            ts.is_reviewed = False
            ts.update_sort_weight()
            results.append(ts)

    def save(self, filepath, translatable_objects, metadata, **kwargs):
        import tomlkit
        raw_content = metadata.get('raw_content', '')
        doc = tomlkit.parse(raw_content)

        translation_map = {
            ts.context: (ts.translation or ts.original_semantic)
            for ts in translatable_objects
            if ts.original_semantic and ts.id != "##NEW_ENTRY##" and ts.context
        }

        self._rebuild_recursive(doc, [], translation_map)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(tomlkit.dumps(doc))

    def _rebuild_recursive(self, obj, key_path, translation_map):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, str):
                    full_key = re.sub(r'\.\[', '[', '.'.join(key_path + [str(k)]))
                    if full_key in translation_map:
                        obj[k] = translation_map[full_key]
                else:
                    self._rebuild_recursive(v, key_path + [str(k)], translation_map)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                if isinstance(item, str):
                    full_key = re.sub(r'\.\[', '[', '.'.join(key_path + [f"[{i}]"]))
                    if full_key in translation_map:
                        obj[i] = translation_map[full_key]
                else:
                    self._rebuild_recursive(item, key_path + [f"[{i}]"], translation_map)


class ResxFormatHandler(BaseFormatHandler):
    """
    .NET / C# RESX (XML Resource File) 格式处理器

    支持的特性:
    1. 数据类型过滤: 仅提取 type 属性缺失或为 System.String 的 <data> 节点，
       自动跳过图片、图标、二进制嵌入资源等非文本条目，防止误翻译
    2. 注释双通道: <comment> 子节点保存为 po_comment 供内部追踪；
       xml:space="preserve" 属性被正确识别并在保存时还原
    3. Designer 文件跳过: 自动检测 .Designer.resx 文件并拒绝加载，
       避免将自动生成的资源键混入翻译工作流
    4. ResX 头部保留: 加载时完整记录 <resheader> / <assembly> / <metadata>
       节点，保存时原样写回，确保 Visual Studio 可正常打开并编译
    5. 语言检测: 从 App.zh-CN.resx / Strings.fr.resx 等命名约定中
       自动提取 BCP-47 语言代码
    """
    format_id = "resx"
    extensions = ['.resx']
    format_type = "translation"
    display_name = _("RESX Resource File (.NET)")
    badge_text = "RESX"
    badge_bg_color = "#E8EAF6"
    badge_text_color = "#283593"

    # 需要跳过的已知非字符串类型前缀
    _SKIP_TYPE_PREFIXES = (
        'System.Drawing', 'System.Windows.Forms', 'System.Byte[]',
        'System.Resources', 'Microsoft.',
    )

    def load(self, filepath, **kwargs):
        logger.debug(f"[ResxFormatHandler] Loading RESX: {filepath}")

        # 拒绝处理 .Designer.resx（自动生成文件）
        if filepath.endswith('.Designer.resx'):
            logger.info(f"[ResxFormatHandler] Skipping designer file: {filepath}")
            return [], {}, 'en'

        tree = ET.parse(filepath)
        root = tree.getroot()

        rel_path = kwargs.get('relative_path') or self._get_relative_path(filepath)
        translatable_objects = []
        occurrence_counters = {}

        # 收集所有 <data> 节点
        for data_elem in root.findall('data'):
            name = data_elem.get('name', '')
            if not name:
                continue

            # 跳过非字符串资源（图片、二进制等）
            res_type = data_elem.get('type', '')
            if res_type and not res_type.startswith('System.String'):
                if any(res_type.startswith(p) for p in self._SKIP_TYPE_PREFIXES):
                    continue

            # 跳过 mimetype 属性（base64 嵌入数据）
            if data_elem.get('mimetype'):
                continue

            value_elem = data_elem.find('value')
            if value_elem is None or not (value_elem.text or '').strip():
                continue

            value = value_elem.text.strip()

            comment_elem = data_elem.find('comment')
            comment_text = comment_elem.text.strip() if comment_elem is not None and comment_elem.text else ''

            counter_key = (value, name)
            idx = occurrence_counters.get(counter_key, 0)
            occurrence_counters[counter_key] = idx + 1

            stable = f"{rel_path}::{name}::{idx}"
            obj_id = xxhash.xxh128(stable.encode('utf-8')).hexdigest()

            ts = TranslatableString(
                original_raw=value, original_semantic=value,
                line_num=0,
                char_pos_start_in_file=0, char_pos_end_in_file=0,
                full_code_lines=[],
                string_type="RESX String",
                source_file_path=rel_path,
                occurrences=[(rel_path, name)],
                occurrence_index=idx,
                id=obj_id
            )
            ts.translation = value
            ts.context = name
            ts.comment = comment_text
            ts.po_comment = f"#: RESX name: {name}"
            ts.is_reviewed = False
            ts.update_sort_weight()
            translatable_objects.append(ts)

        # 保存头部节点用于回写
        header_nodes = self._collect_header_nodes(root)
        language_code = self._detect_language(os.path.basename(filepath))

        metadata = {
            'header_nodes': header_nodes,
            'xml_version': '1.0',
            'encoding': 'utf-8',
        }

        logger.info(f"[ResxFormatHandler] Loaded {len(translatable_objects)} strings from {filepath}")
        return translatable_objects, metadata, language_code

    def _collect_header_nodes(self, root: ET.Element) -> List[Dict]:
        """收集 resheader / assembly / metadata 节点，保存时原样还原"""
        preserved = []
        for tag in ('resheader', 'assembly', 'metadata'):
            for elem in root.findall(tag):
                preserved.append({
                    'tag': tag,
                    'attrib': dict(elem.attrib),
                    'children': [
                        {'tag': c.tag, 'text': c.text, 'attrib': dict(c.attrib)}
                        for c in elem
                    ]
                })
        return preserved

    def _detect_language(self, filename: str) -> str:
        """
        从 Resource.zh-CN.resx / Strings.fr.resx / App.de.resx 中提取语言码。
        中性区域文件 (Resource.resx) 视为源语言 (en)。
        """
        stem = os.path.splitext(filename)[0]  # 去掉 .resx
        # BCP-47 语言标签: xx 或 xx-YY
        m = re.search(r'\.([a-z]{2,3}(?:-[A-Za-z]{2,4})?)$', stem, re.IGNORECASE)
        if m:
            return m.group(1)
        return 'en'

    def _get_relative_path(self, filepath: str) -> str:
        current = Path(filepath).parent
        while True:
            if (current / 'project.json').is_file():
                try:
                    return Path(filepath).relative_to(current).as_posix()
                except ValueError:
                    break
            if current.parent == current:
                break
            current = current.parent
        return os.path.basename(filepath)

    def save(self, filepath, translatable_objects, metadata, **kwargs):
        logger.debug(f"[ResxFormatHandler] Saving RESX: {filepath}")

        # 注册 .NET 标准命名空间
        import xml.etree.ElementTree as ET
        ET.register_namespace('xsd', 'http://www.w3.org/2001/XMLSchema')
        ET.register_namespace('msdata', 'urn:schemas-microsoft-com:xml-msdata')

        root = ET.Element('root')

        # 写入架构声明
        schema_elem = ET.SubElement(root, '{http://www.w3.org/2001/XMLSchema}schema')
        schema_elem.set('id', 'root')

        # 还原头部节点 (resheader, assembly 等)
        for node_info in metadata.get('header_nodes', []):
            elem = ET.SubElement(root, node_info['tag'], **node_info['attrib'])
            for child in node_info['children']:
                c = ET.SubElement(elem, child['tag'], **child.get('attrib', {}))
                c.text = child.get('text', '')

        # 写入翻译条目并计数
        saved_count = 0
        for ts in translatable_objects:
            if not ts.original_semantic or ts.id == "##NEW_ENTRY##":
                continue

            data_elem = ET.SubElement(root, 'data')
            data_elem.set('name', ts.context)
            # 处理空格保留
            data_elem.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')

            value_elem = ET.SubElement(data_elem, 'value')
            # 如果有翻译则用翻译，否则回退到原文
            value_elem.text = ts.translation if ts.translation else ts.original_semantic

            if ts.comment:
                comment_elem = ET.SubElement(data_elem, 'comment')
                comment_elem.text = ts.comment

            saved_count += 1

        tree = ET.ElementTree(root)
        if hasattr(ET, 'indent'):
            ET.indent(tree, space='  ', level=0)

        tree.write(filepath, encoding='utf-8', xml_declaration=True)
        logger.info(f"[ResxFormatHandler] Saved {saved_count} strings to {filepath}")


# 表格类辅助函数
def _guess_column_mapping(headers, config):
    mapping = {}
    is_fuzzy = False
    if not headers: return mapping

    # 关键词
    default_pool = {
        'source': [
            'source', 'original', '原文', 'text', 'string', 'msgid',
            'src', 'source_text', 'default', 'base', 'reference', 'master'
        ],
        'target': [
            'target', 'translation', '译文', 'msgstr', 'value',
            'tgt', 'translated_text', 'loc', 'localized', 'localization', 'result', 'dest',
            'destination'
        ],
        'key': [
            'key', 'id', 'name', '键', '标识',
            'identifier', 'code', 'string_id', 'text_id', 'label', 'path', 'var', 'variable'
        ],
        'comment': [
            'comment', 'note', 'description', '备注', 'context',
            'desc', 'notes', 'instruction', 'info', 'information', '说明', 'reference_url'
        ]
    }

    user_pool = config.get('column_keywords', {})

    def normalize(s):
        return re.sub(r'[^a-z0-9\u4e00-\u9fa5]', '', str(s).lower())

    processed_pools = {}
    for role, words in default_pool.items():
        combined = set(words + user_pool.get(role, []))
        processed_pools[role] = [normalize(w) for w in combined if w]

    assigned_indices = set()

    # --- 第一阶段：精确匹配 ---
    for role in ['source', 'target', 'key', 'comment']:
        for idx, h in enumerate(headers):
            if idx in assigned_indices: continue
            if normalize(h) in processed_pools[role]:
                mapping[role] = idx
                assigned_indices.add(idx)
                break

    # --- 第二阶段：包含匹配 ---
    for role in ['source', 'target']:
        if role in mapping: continue
        for idx, h in enumerate(headers):
            if idx in assigned_indices: continue
            h_norm = normalize(h)
            if any(word in h_norm for word in processed_pools[role] if len(word) > 3):
                mapping[role] = idx
                assigned_indices.add(idx)
                break

    # --- 第三阶段：Fuzzy 模糊匹配 ---
    for role in ['source', 'target']:
        if role in mapping: continue
        best_score = 0
        best_idx = -1
        for idx, h in enumerate(headers):
            if idx in assigned_indices: continue
            h_norm = normalize(h)
            for word in processed_pools[role]:
                score = fuzz.ratio(h_norm, word)
                if score > 85 and score > best_score:
                    best_score = score
                    best_idx = idx

        if best_idx != -1:
            mapping[role] = best_idx
            assigned_indices.add(best_idx)
            is_fuzzy = True

    return mapping, is_fuzzy


def _learn_column_mapping(headers, mapping, config):
    """将用户手动选择的表头加入关键词池"""
    if 'column_keywords' not in config:
        config['column_keywords'] = {}

    pool = config['column_keywords']
    changed = False

    for role, col_idx in mapping.items():
        if col_idx >= len(headers): continue
        header_val = str(headers[col_idx]).strip().lower()
        if not header_val: continue

        if role not in pool: pool[role] = []
        if header_val not in pool[role]:
            pool[role].append(header_val)
            changed = True

    return changed

class CsvFormatHandler(BaseFormatHandler):
    format_id = "csv"
    extensions = ['.csv']
    format_type = "translation"
    display_name = _("CSV Table File")
    badge_text = "CSV"
    badge_bg_color = "#E8F5E9"
    badge_text_color = "#2E7D32"

    def load(self, filepath, **kwargs):
        app = kwargs.get('app_instance')
        force_dialog = kwargs.get('force_dialog', False)
        if not app: raise ValueError("App instance required for CSV mapping.")

        with open(filepath, 'r', encoding='utf-8-sig', newline='') as f:
            sample = f.read(4096)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample)
            except:
                dialect = csv.excel

            reader = csv.reader(f, dialect)
            rows = list(reader)

        if not rows: return [], {}, 'en'

        headers = rows[0]
        data_rows = rows[1:]

        # 1. 尝试猜测映射
        mapping, is_guessed_fuzzy = _guess_column_mapping(headers, app.config)

        # 2. 如果缺少原文列，或者强制交互，弹出对话框
        if force_dialog or is_guessed_fuzzy or 'source' not in mapping:
            from dialogs.column_mapper_dialog import ColumnMapperDialog
            dialog = ColumnMapperDialog(app.main_window if hasattr(app, 'main_window') else app, headers, data_rows[:5], mapping)
            if dialog.exec():
                mapping = dialog.result_mapping
                if dialog.remember_choices:
                    if _learn_column_mapping(headers, mapping, app.config):
                        app.save_config()
            else:
                return [], {}, 'en'

        rel_path = kwargs.get('relative_path') or os.path.basename(filepath)
        translatable_objects = []
        occurrence_counters = {}

        src_idx = mapping.get('source')
        tgt_idx = mapping.get('target')
        key_idx = mapping.get('key')
        cmt_idx = mapping.get('comment')

        for row_num, row in enumerate(data_rows, start=2):
            if src_idx >= len(row): continue
            source_text = row[src_idx]
            if not source_text.strip(): continue

            target_text = row[tgt_idx] if tgt_idx is not None and tgt_idx < len(row) else ""
            key_text = row[key_idx] if key_idx is not None and key_idx < len(row) else ""
            comment_text = row[cmt_idx] if cmt_idx is not None and cmt_idx < len(row) else ""

            context = key_text or f"row_{row_num}"
            counter_key = (source_text, context)
            idx = occurrence_counters.get(counter_key, 0)
            occurrence_counters[counter_key] = idx + 1

            stable = f"{rel_path}::{context}::{source_text}::{idx}"
            obj_id = xxhash.xxh128(stable.encode()).hexdigest()

            ts = TranslatableString(
                original_raw=source_text, original_semantic=source_text,
                line_num=row_num, char_pos_start_in_file=0, char_pos_end_in_file=0,
                full_code_lines=[], string_type="CSV Row",
                source_file_path=rel_path, occurrences=[(rel_path, str(row_num))],
                occurrence_index=idx, id=obj_id
            )
            ts.translation = target_text
            ts.context = context
            ts.comment = comment_text
            ts.po_comment = f"#: Row {row_num}"
            ts.is_reviewed = False
            ts.update_sort_weight()
            translatable_objects.append(ts)

        language_code = self._detect_language_from_filename(os.path.basename(filepath))
        metadata = {
            'mapping': mapping,
            'dialect': {
                'delimiter': dialect.delimiter,
                'quotechar': dialect.quotechar,
                'lineterminator': dialect.lineterminator
            }
        }
        return translatable_objects, metadata, language_code

    def save(self, filepath, translatable_objects, metadata, **kwargs):
        mapping = metadata.get('mapping', {})
        tgt_idx = mapping.get('target')
        cmt_idx = mapping.get('comment')

        # 如果没有目标列，我们需要在末尾追加一列
        append_target = False
        if tgt_idx is None:
            append_target = True

        dialect_info = metadata.get('dialect', {})

        # 读取原始数据
        with open(filepath, 'r', encoding='utf-8-sig', newline='') as f:
            reader = csv.reader(f, delimiter=dialect_info.get('delimiter', ','),
                                quotechar=dialect_info.get('quotechar', '"'))
            rows = list(reader)

        if not rows: return

        if append_target:
            tgt_idx = len(rows[0])
            rows[0].append("Translation")  # 追加表头

        # 建立行号映射
        ts_map = {ts.line_num_in_file: ts for ts in translatable_objects if ts.id != "##NEW_ENTRY##"}

        for row_num, row in enumerate(rows[1:], start=2):
            ts = ts_map.get(row_num)
            if ts:
                # 1. 回填译文
                trans_text = ts.translation if ts.translation else ts.original_semantic
                if append_target:
                    row.append(trans_text)
                elif tgt_idx < len(row):
                    row[tgt_idx] = trans_text
                else:
                    # 补齐长度
                    row.extend([""] * (tgt_idx - len(row) + 1))
                    row[tgt_idx] = trans_text
                # 2. 回填注释
                if cmt_idx is not None and cmt_idx < len(row):
                    row[cmt_idx] = ts.comment

        # 写回
        with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f, delimiter=dialect_info.get('delimiter', ','),
                                quotechar=dialect_info.get('quotechar', '"'),
                                lineterminator=dialect_info.get('lineterminator', '\r\n'))
            writer.writerows(rows)


class XlsxFormatHandler(BaseFormatHandler):
    format_id = "xlsx"
    extensions = ['.xlsx']
    format_type = "translation"
    display_name = _("Excel Workbook")
    badge_text = "XLSX"
    badge_bg_color = "#E8F5E9"
    badge_text_color = "#1B5E20"

    def load(self, filepath, **kwargs):
        try:
            import openpyxl
        except ImportError:
            raise ImportError(
                _("The 'openpyxl' library is required to read Excel files. Please install it via 'pip install openpyxl'."))

        app = kwargs.get('app_instance')
        force_dialog = kwargs.get('force_dialog', False)
        if not app: raise ValueError("App instance required.")

        wb = openpyxl.load_workbook(filepath, data_only=True)
        ws = wb.active

        rows = list(ws.iter_rows(values_only=True))
        if not rows: return [], {}, 'en'

        headers = [str(c) if c is not None else "" for c in rows[0]]
        data_rows = rows[1:]

        mapping, is_guessed_fuzzy = _guess_column_mapping(headers, app.config)

        if force_dialog or is_guessed_fuzzy or 'source' not in mapping:
            from dialogs.column_mapper_dialog import ColumnMapperDialog
            dialog = ColumnMapperDialog(
                app.main_window if hasattr(app, 'main_window') else app,
                headers,
                data_rows[:5],
                mapping
            )

            if dialog.exec():
                mapping = dialog.result_mapping
                if dialog.remember_choices:
                    if _learn_column_mapping(headers, mapping, app.config):
                        app.save_config()
            else:
                return [], {}, 'en'

        rel_path = kwargs.get('relative_path') or os.path.basename(filepath)
        translatable_objects = []
        occurrence_counters = {}

        src_idx = mapping.get('source')
        tgt_idx = mapping.get('target')
        key_idx = mapping.get('key')
        cmt_idx = mapping.get('comment')

        for row_num, row in enumerate(data_rows, start=2):
            if src_idx >= len(row) or row[src_idx] is None: continue
            source_text = str(row[src_idx])
            if not source_text.strip(): continue

            target_text = str(row[tgt_idx]) if tgt_idx is not None and tgt_idx < len(row) and row[tgt_idx] is not None else ""
            key_text = str(row[key_idx]) if key_idx is not None and key_idx < len(row) and row[key_idx] is not None else ""
            comment_text = str(row[cmt_idx]) if cmt_idx is not None and cmt_idx < len(row) and row[cmt_idx] is not None else ""

            context = key_text or f"row_{row_num}"
            counter_key = (source_text, context)
            idx = occurrence_counters.get(counter_key, 0)
            occurrence_counters[counter_key] = idx + 1

            stable = f"{rel_path}::{context}::{source_text}::{idx}"
            obj_id = xxhash.xxh128(stable.encode()).hexdigest()

            ts = TranslatableString(
                original_raw=source_text, original_semantic=source_text,
                line_num=row_num, char_pos_start_in_file=0, char_pos_end_in_file=0,
                full_code_lines=[], string_type="Excel Row",
                source_file_path=rel_path, occurrences=[(rel_path, str(row_num))],
                occurrence_index=idx, id=obj_id
            )
            ts.translation = target_text
            ts.context = context
            ts.comment = comment_text
            ts.po_comment = f"#: Row {row_num}"
            ts.is_reviewed = False
            ts.update_sort_weight()
            translatable_objects.append(ts)

        language_code = self._detect_language_from_filename(os.path.basename(filepath))
        metadata = {'mapping': mapping, 'sheet_name': ws.title}
        return translatable_objects, metadata, language_code

    def save(self, filepath, translatable_objects, metadata, **kwargs):
        import openpyxl
        mapping = metadata.get('mapping', {})
        tgt_idx = mapping.get('target')
        cmt_idx = mapping.get('comment')

        wb = openpyxl.load_workbook(filepath)
        ws = wb[metadata.get('sheet_name', wb.active.title)]

        append_target = False
        if tgt_idx is None:
            append_target = True
            tgt_idx = ws.max_column
            ws.cell(row=1, column=tgt_idx + 1, value="Translation")

        ts_map = {ts.line_num_in_file: ts for ts in translatable_objects if ts.id != "##NEW_ENTRY##"}

        for row_num in range(2, ws.max_row + 1):
            ts = ts_map.get(row_num)
            if ts:
                # 1. 回填译文 (openpyxl 是 1-based)
                trans_text = ts.translation if ts.translation else ts.original_semantic
                ws.cell(row=row_num, column=tgt_idx + 1, value=trans_text)

                # 2. 回填注释
                if cmt_idx is not None:
                    ws.cell(row=row_num, column=cmt_idx + 1, value=ts.comment)
        wb.save(filepath)


class JavaPropertiesFormatHandler(BaseFormatHandler):
    """
    Java / Kotlin .properties 资源文件处理器

    支持的特性:
    1. 多种分隔符: 正确解析 key=value、key: value、key value 三种赋值形式
    2. 多行续行: 支持行尾反斜杠 \\ 的跨行字符串
    3. Unicode 转义: 双向处理 \\uXXXX 编码，保留非 ASCII 可读性
    4. 注释提取: # 和 ! 开头的行内注释均作为 translator comment 关联到下一条目
    5. 顺序保留: 保存时严格按原始键顺序输出，保证 diff 友好
    6. 语言检测: 从标准命名规范 messages_zh_CN.properties 自动推断语言代码
    7. 空行保护: 保存时在每个条目间保留适当空行，贴近手写习惯
    """
    format_id = "java_properties"
    extensions = ['.properties']
    format_type = "translation"
    display_name = _("Java .properties File")
    badge_text = "Props"
    badge_bg_color = "#FFF8E1"
    badge_text_color = "#F57F17"

    def load(self, filepath, **kwargs):
        logger.debug(f"[JavaPropertiesFormatHandler] Loading .properties: {filepath}")

        # Java .properties 官方编码为 ISO-8859-1，但现代项目多用 UTF-8
        encoding = self._detect_encoding(filepath)
        with open(filepath, 'r', encoding=encoding, errors='replace') as f:
            lines = f.readlines()

        relative_path = kwargs.get('relative_path') or self._get_relative_path(filepath)
        language_code = self._detect_language(os.path.basename(filepath))

        translatable_objects = []
        occurrence_counters = {}

        # --- 解析器状态 ---
        pending_comments: List[str] = []
        line_idx = 0

        while line_idx < len(lines):
            raw = lines[line_idx]
            stripped = raw.strip()
            line_idx += 1

            # 空行 → 清空待关联注释（注释只关联紧随其后的条目）
            if not stripped:
                pending_comments.clear()
                continue

            # 注释行
            if stripped.startswith('#') or stripped.startswith('!'):
                pending_comments.append(stripped[1:].strip())
                continue

            # 键值行（可能带续行）
            logical_line = raw.rstrip('\r\n')
            while logical_line.endswith('\\'):
                logical_line = logical_line[:-1]  # 去掉续行符
                if line_idx < len(lines):
                    logical_line += lines[line_idx].strip()
                    line_idx += 1

            key, value = self._split_key_value(logical_line.strip())
            if key is None:
                pending_comments.clear()
                continue

            # 解码 Unicode 转义
            key = self._decode_unicode_escapes(key)
            value = self._decode_unicode_escapes(value)

            if not value.strip():
                pending_comments.clear()
                continue

            comment = '\n'.join(pending_comments).strip()
            pending_comments.clear()

            counter_key = (value, key)
            idx = occurrence_counters.get(counter_key, 0)
            occurrence_counters[counter_key] = idx + 1

            stable = f"{relative_path}::{key}::{value}::{idx}"
            obj_id = xxhash.xxh128(stable.encode()).hexdigest()

            ts = TranslatableString(
                original_raw=value, original_semantic=value,
                line_num=0,
                char_pos_start_in_file=0, char_pos_end_in_file=0,
                full_code_lines=[],
                string_type="Java Properties",
                source_file_path=relative_path,
                occurrences=[(relative_path, key)],
                occurrence_index=idx,
                id=obj_id
            )
            ts.translation = value
            ts.context = key
            ts.comment = comment
            ts.po_comment = f"#: Properties key: {key}"
            ts.is_reviewed = False
            ts.update_sort_weight()
            translatable_objects.append(ts)

        metadata = {
            'encoding': encoding,
            'key_order': [ts.context for ts in translatable_objects],
        }

        logger.info(
            f"[JavaPropertiesFormatHandler] Loaded {len(translatable_objects)} "
            f"entries from {filepath} (encoding: {encoding})"
        )
        return translatable_objects, metadata, language_code

    def save(self, filepath, translatable_objects, metadata, **kwargs):
        logger.debug(f"[JavaPropertiesFormatHandler] Saving .properties: {filepath}")

        encoding = metadata.get('encoding', 'utf-8')
        key_order = metadata.get('key_order', [])

        # 建立 context -> ts 映射
        ts_map = {ts.context: ts for ts in translatable_objects
                  if ts.original_semantic and ts.id != '##NEW_ENTRY##'}

        # 按原始顺序输出，末尾追加新增条目
        ordered_keys = key_order + [k for k in ts_map if k not in key_order]

        lines = []
        for key in ordered_keys:
            ts = ts_map.get(key)
            if not ts:
                continue

            # 写注释
            if ts.comment:
                for comment_line in ts.comment.splitlines():
                    lines.append(f'# {comment_line}')

            translation = ts.translation if ts.translation else ts.original_semantic

            # 决定是否需要 Unicode 转义 (仅在 latin-1 编码时必须转义非 ASCII)
            needs_escape = encoding.lower() in ('iso-8859-1', 'latin-1', 'latin1')
            escaped_key = self._encode_key(key, needs_escape)
            escaped_val = self._encode_value(translation, needs_escape)

            lines.append(f'{escaped_key}={escaped_val}')
            lines.append('')  # 条目间空行

        with open(filepath, 'w', encoding=encoding) as f:
            f.write('\n'.join(lines))

        logger.info(f"[JavaPropertiesFormatHandler] Saved {len(ts_map)} entries to {filepath}")

    def _detect_encoding(self, filepath: str) -> str:
        """
        检测文件编码。
        Java 规范是 ISO-8859-1，但 Spring Boot 等现代框架默认 UTF-8。
        检查 BOM 或尝试 UTF-8 解码来区分。
        """
        with open(filepath, 'rb') as f:
            raw = f.read(4)
        if raw.startswith(b'\xef\xbb\xbf'):
            return 'utf-8-sig'
        # 尝试 UTF-8 解码前 4KB
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                f.read(4096)
            return 'utf-8'
        except UnicodeDecodeError:
            return 'iso-8859-1'

    def _split_key_value(self, line: str) -> Tuple[Optional[str], str]:
        """
        解析 key=value / key: value / key value 三种形式。
        返回 (key, value)，解析失败返回 (None, '')。
        """
        # 跳过注释和空行（已在上层处理，这里做保险）
        if not line or line[0] in ('#', '!'):
            return None, ''

        # 找到未转义的分隔符 (=, :, 或首个空格)
        i = 0
        while i < len(line):
            ch = line[i]
            if ch == '\\':
                i += 2  # 跳过转义字符
                continue
            if ch in ('=', ':'):
                return line[:i].strip(), line[i + 1:].lstrip()
            if ch in (' ', '\t'):
                key = line[:i].strip()
                rest = line[i:].lstrip()
                # 如果空格后面紧跟 = 或 :，那才是真正的分隔符
                if rest and rest[0] in ('=', ':'):
                    return key, rest[1:].lstrip()
                return key, rest
            i += 1

        # 只有键没有值（空值）
        return line.strip(), ''

    def _decode_unicode_escapes(self, s: str) -> str:
        """将 \\uXXXX 转义序列解码为 Unicode 字符。"""
        return re.sub(
            r'\\u([0-9a-fA-F]{4})',
            lambda m: chr(int(m.group(1), 16)),
            s
        )

    def _encode_unicode_escapes(self, s: str) -> str:
        """将非 ASCII 字符编码为 \\uXXXX（仅用于 latin-1 编码文件）。"""
        result = []
        for ch in s:
            if ord(ch) > 127:
                result.append(f'\\u{ord(ch):04X}')
            else:
                result.append(ch)
        return ''.join(result)

    def _encode_key(self, key: str, unicode_escape: bool) -> str:
        """对键中的特殊字符进行转义。"""
        key = key.replace('\\', '\\\\')
        key = key.replace(' ', '\\ ')
        key = key.replace('=', '\\=')
        key = key.replace(':', '\\:')
        key = key.replace('#', '\\#')
        key = key.replace('!', '\\!')
        if unicode_escape:
            key = self._encode_unicode_escapes(key)
        return key

    def _encode_value(self, value: str, unicode_escape: bool) -> str:
        """对值进行转义，换行符转为 \\n 续行形式。"""
        value = value.replace('\\', '\\\\')
        value = value.replace('\n', '\\n\\\n    ')
        value = value.replace('\t', '\\t')
        if unicode_escape:
            value = self._encode_unicode_escapes(value)
        return value

    def _detect_language(self, filename: str) -> str:
        """
        从标准 Java ResourceBundle 命名规范中提取语言代码。
        例: messages_zh_CN.properties → zh_CN
            strings_en.properties    → en
            MyApp_fr_FR.properties   → fr_FR
        """
        name = filename.replace('.properties', '')
        # 尝试匹配末尾的 _lang 或 _lang_COUNTRY
        m = re.search(
            r'_([a-z]{2,3})(?:_([A-Z]{2,3}))?$',
            name
        )
        if m:
            lang = m.group(1)
            country = m.group(2)
            return f"{lang}_{country}" if country else lang
        return 'en'

    def _get_relative_path(self, filepath: str) -> str:
        current = Path(filepath).parent
        while True:
            if (current / 'project.json').is_file():
                try:
                    return Path(filepath).relative_to(current).as_posix()
                except ValueError:
                    break
            if current.parent == current:
                break
            current = current.parent
        return os.path.basename(filepath)


class MarkdownFormatHandler(BaseFormatHandler):
    """
    Markdown / MDX 文档本地化处理器

    支持的提取单元（按语义粒度从细到粗）:
    1. Frontmatter 字段: 解析 YAML frontmatter (--- ... ---) 中的字符串字段，
       如 title / description / keywords，跳过日期、布尔、数字等非文本字段
    2. 标题 (ATX/Setext): 提取 # / ## / ### 等 ATX 风格标题；
       同时支持 Setext 风格（下划线 === / ---）标题
    3. 段落块: 将连续非空行合并为一个段落单元提取，保留行内 Markdown 标记
       (**bold**, *italic*, `code`, [link](url), ![alt](src))，
       仅替换文本内容，不破坏标记结构
    4. 列表项: 有序列表 (1. 2. 3.) 和无序列表 (- * +) 的每个条目单独提取；
       支持嵌套列表，子项以缩进层级区分
    5. 表格单元: 解析 GFM (GitHub Flavored Markdown) 表格，提取表头和数据单元，
       跳过分隔行 (| --- | --- |)
    6. 块引用: 提取 > 引用块中的文字内容，多行引用合并为一个单元
    7. 自定义 MDX 组件属性: 提取 JSX 风格属性中的字符串字面量，
       如 <Button label="Click me"> 中的 "Click me"

    刻意跳过的内容（保证代码结构不受损）:
    - 围栏代码块 (``` 或 ~~~)
    - 行内代码 (`code`)
    - HTML 注释 (<!-- -->)
    - import / export 语句 (MDX 专用)
    - 纯 URL / 路径
    - 数学公式 ($ ... $ 和 $$ ... $$)

    保存策略:
    - 基于 char_pos_start_in_file / char_pos_end_in_file 精准定位并替换，
      文档其余部分（格式、空行、代码块）完全原样保留
    - 若无 char 偏移信息则回退到行号替换
    """
    format_id = "markdown"
    extensions = ['.md', '.mdx', '.markdown']
    format_type = "translation"
    display_name = _("Markdown / MDX Document")
    badge_text = "MD"
    badge_bg_color = "#ECEFF1"
    badge_text_color = "#37474F"

    # 跳过的 frontmatter 字段（通常是日期、布尔、路径等）
    _FRONTMATTER_SKIP_KEYS = {
        'date', 'updated', 'created', 'draft', 'published',
        'order', 'weight', 'slug', 'permalink', 'url',
        'layout', 'template', 'type', 'id', 'uuid',
    }

    # 纯 URL / 路径正则（不值得翻译）
    _URL_RE = re.compile(
        r'^(?:https?://|ftp://|/|\.{0,2}/)[\w./?=&%#@:+\-]*$'
    )

    def load(self, filepath, **kwargs):
        logger.debug(f"[MarkdownFormatHandler] Loading Markdown: {filepath}")
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        rel_path = kwargs.get('relative_path') or self._get_relative_path(filepath)

        full_lines = content.splitlines()

        translatable_objects = []
        occurrence_counters = {}
        skip_ranges = self._find_skip_ranges(content)

        fm_end = 0
        _, fm_end = self._extract_frontmatter(
            content, rel_path, translatable_objects, occurrence_counters, full_lines
        )

        self._extract_body(
            content, fm_end, skip_ranges, rel_path,
            translatable_objects, occurrence_counters, full_lines
        )

        language_code = self._detect_language(os.path.basename(filepath))
        metadata = {
            'original_content': content,
            'skip_ranges': skip_ranges,
        }

        logger.info(f"[MarkdownFormatHandler] Loaded {len(translatable_objects)} segments from {filepath}")
        return translatable_objects, metadata, language_code

    def _find_skip_ranges(self, content: str) -> List[Tuple[int, int]]:
        """
        返回不应被提取或替换的字符区间列表 [(start, end), ...]。
        涵盖: 围栏代码块、行内代码、HTML注释、数学公式、import/export
        """
        ranges = []

        # 围栏代码块: ```...``` 或 ~~~...~~~
        for m in re.finditer(r'(?m)^(```+|~~~+)[^\n]*\n.*?\n\1[ \t]*$', content, re.DOTALL):
            ranges.append((m.start(), m.end()))

        # HTML 注释
        for m in re.finditer(r'<!--.*?-->', content, re.DOTALL):
            ranges.append((m.start(), m.end()))

        # 数学公式块 $$ ... $$
        for m in re.finditer(r'\$\$.*?\$\$', content, re.DOTALL):
            ranges.append((m.start(), m.end()))

        # 行内数学 $ ... $（单行）
        for m in re.finditer(r'\$[^\n$]+\$', content):
            ranges.append((m.start(), m.end()))

        # MDX import / export 语句
        for m in re.finditer(r'(?m)^(?:import|export)\s+.+$', content):
            ranges.append((m.start(), m.end()))

        return sorted(ranges)

    def _in_skip_range(self, pos: int, skip_ranges: List[Tuple[int, int]]) -> bool:
        for s, e in skip_ranges:
            if s <= pos < e:
                return True
            if s > pos:
                break
        return False

    def _extract_frontmatter(
        self, content: str, rel_path: str,
        results: List, counters: Dict, full_lines: List[str]
    ) -> Tuple[Dict, int]:
        """提取 YAML frontmatter 中的可翻译字段，返回 (字段dict, frontmatter结束位置)"""
        fm_end = 0
        extracted = {}

        m = re.match(r'^---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n', content, re.DOTALL)
        if not m:
            return extracted, fm_end

        fm_text = m.group(1)
        fm_end = m.end()

        for fm_m in re.finditer(
            r'^([ \t]*)(\w[\w-]*)[ \t]*:[ \t]*(["\']?)(.+?)\3[ \t]*$',
            fm_text, re.MULTILINE
        ):
            indent_str, key, quote, value = fm_m.groups()
            if key.lower() in self._FRONTMATTER_SKIP_KEYS:
                continue
            if self._URL_RE.match(value.strip()):
                continue
            if re.match(r'^(?:true|false|null|\d[\d.,]*)$', value.strip(), re.I):
                continue
            if value.strip():
                self._make_ts(
                    value.strip(), f"frontmatter.{key}", rel_path,
                    results, counters,
                    full_lines,
                    line_num=content[:m.start() + fm_m.start()].count('\n') + 1,
                    char_start=m.start(1) + fm_m.start(4),
                    char_end=m.start(1) + fm_m.end(4),
                    string_type="MD Frontmatter",
                )

        return extracted, fm_end

    def _extract_body(
            self, content: str, body_start: int,
            skip_ranges: List[Tuple[int, int]],
            rel_path: str, results: List, counters: Dict,
            full_lines: List[str]
    ):
        """逐行扫描文档正文，按语义单元提取"""
        lines = content[body_start:].split('\n')
        abs_offset = body_start

        i = 0
        while i < len(lines):
            line = lines[i]
            line_abs_start = abs_offset
            line_num = content[:abs_offset].count('\n') + 1

            # 如果整行在禁区内，跳过
            if self._in_skip_range(line_abs_start, skip_ranges):
                abs_offset += len(line) + 1
                i += 1
                continue

            stripped = line.strip()
            if not stripped:
                abs_offset += len(line) + 1
                i += 1
                continue

            # --- 1. ATX 标题 ---
            atx_m = re.match(r'^(#{1,6})\s+(.*?)(?:\s+#+\s*)?$', stripped)
            if atx_m:
                heading_text = atx_m.group(2).strip()
                if heading_text:
                    level = len(atx_m.group(1))
                    # 计算文本在文件中的精确起始位置
                    hash_prefix = atx_m.group(1)
                    # 找到第一个非空字符的位置
                    text_rel_start = re.search(re.escape(heading_text), line).start()
                    text_abs_start = line_abs_start + text_rel_start
                    self._make_ts(
                        heading_text, f"heading.h{level}", rel_path, results, counters,
                        full_lines,
                        line_num=line_num,
                        char_start=text_abs_start,
                        char_end=text_abs_start + len(heading_text),
                        string_type="MD Heading",
                    )
                abs_offset += len(line) + 1
                i += 1
                continue

            # --- 2. Setext 标题 ---
            if i + 1 < len(lines):
                next_stripped = lines[i + 1].strip()
                if re.match(r'^=+$', next_stripped) or re.match(r'^-+$', next_stripped):
                    level = 1 if next_stripped.startswith('=') else 2
                    if stripped:
                        self._make_ts(
                            stripped, f"heading.h{level}", rel_path, results, counters,
                            full_lines,
                            line_num=line_num,
                            char_start=line_abs_start + line.find(stripped),
                            char_end=line_abs_start + line.find(stripped) + len(stripped),
                            string_type="MD Heading",
                        )
                    abs_offset += len(line) + 1 + len(lines[i + 1]) + 1
                    i += 2
                    continue

            # --- 3. 列表项 ---
            list_m = re.match(r'^([ \t]*)(?:[-*+]|\d+\.)\s+(.*)', line)
            if list_m:
                item_text = list_m.group(2).strip()
                item_text_clean = self._strip_inline_code(item_text)
                if item_text_clean and not self._URL_RE.match(item_text_clean):
                    text_rel_start = line.find(list_m.group(2))
                    text_abs_start = line_abs_start + text_rel_start
                    self._make_ts(
                        item_text, "list.item", rel_path, results, counters,
                        full_lines,
                        line_num=line_num,
                        char_start=text_abs_start,
                        char_end=text_abs_start + len(item_text),
                        string_type="MD List Item",
                    )
                abs_offset += len(line) + 1
                i += 1
                continue

            # --- 4. 块引用 ---
            if stripped.startswith('>'):
                quote_lines = []
                quote_start_offset = abs_offset
                start_i = i
                while i < len(lines) and lines[i].strip().startswith('>'):
                    # 移除开头的 > 符号
                    content_part = re.sub(r'^[ \t]*>+[ \t]?', '', lines[i])
                    quote_lines.append(content_part)
                    abs_offset += len(lines[i]) + 1
                    i += 1

                quote_text = '\n'.join(quote_lines).strip()
                if quote_text and not self._URL_RE.match(self._strip_inline_code(quote_text)):
                    self._make_ts(
                        quote_text, "blockquote", rel_path, results, counters,
                        full_lines,
                        line_num=line_num,
                        char_start=quote_start_offset,
                        char_end=abs_offset - 1,
                        string_type="MD Blockquote",
                    )
                continue

            # --- 5. GFM 表格行 ---
            if '|' in stripped and not re.match(r'^\|?[ \t:|-]+\|', stripped):
                # 简单的表格单元提取
                cells = [c.strip() for c in stripped.strip('|').split('|')]
                for cell in cells:
                    if not cell: continue
                    cell_clean = self._strip_inline_code(cell)
                    if cell_clean and not self._URL_RE.match(cell_clean) and len(cell_clean) > 1:
                        # 定位单元格在行中的位置
                        cell_rel_start = line.find(cell)
                        self._make_ts(
                            cell, "table.cell", rel_path, results, counters,
                            full_lines,
                            line_num=line_num,
                            char_start=line_abs_start + cell_rel_start,
                            char_end=line_abs_start + cell_rel_start + len(cell),
                            string_type="MD Table",
                        )
                abs_offset += len(line) + 1
                i += 1
                continue

            # --- 6. 段落（连续非空行）---
            # 只有不满足上述所有条件的非空行才进入段落解析
            para_lines = []
            para_start_offset = abs_offset
            para_start_line = line_num
            while i < len(lines):
                cur_line = lines[i]
                cur_stripped = cur_line.strip()
                # 检查是否遇到其他块的起始标识
                if (not cur_stripped
                        or cur_stripped.startswith('#')
                        or cur_stripped.startswith('```')
                        or cur_stripped.startswith('~~~')
                        or re.match(r'^(?:[-*_]){3,}$', cur_stripped)
                        or re.match(r'^(?:[-*+]|\d+\.)\s', cur_stripped)
                        or cur_stripped.startswith('>')
                        or self._in_skip_range(abs_offset, skip_ranges)):
                    break
                para_lines.append(cur_line)
                abs_offset += len(cur_line) + 1
                i += 1

            if para_lines:
                # 合并多行段落为单行文本（Markdown 渲染特性）
                para_text = ' '.join(l.strip() for l in para_lines).strip()
                para_text_clean = self._strip_inline_code(para_text)

                if (para_text_clean and len(para_text_clean) > 2
                        and not self._URL_RE.match(para_text_clean)):
                    self._make_ts(
                        para_text, "paragraph", rel_path, results, counters,
                        full_lines,
                        line_num=para_start_line,
                        char_start=para_start_offset,
                        char_end=abs_offset - 1,
                        string_type="MD Paragraph",
                    )
                continue

            abs_offset += len(line) + 1
            i += 1

    def _strip_inline_code(self, text: str) -> str:
        """去除行内反引号代码后返回纯文本，用于判断是否值得翻译"""
        return re.sub(r'`[^`]*`', '', text).strip()

    def _make_ts(self, text, context_hint, rel_path, results, counters,
                 full_lines, line_num=0, char_start=0, char_end=0, string_type="MD Text"):
        """统一创建 TranslatableString 对象"""
        # 过滤过短或无意义的文本
        clean = self._strip_inline_code(text)
        if len(clean.strip()) < 2:
            return

        # context = hint::顺序计数，防止同文件同类型条目冲突
        counter_key = (text, context_hint)
        idx = counters.get(counter_key, 0)
        counters[counter_key] = idx + 1

        context = f"{context_hint}[{idx}]" if idx > 0 else context_hint

        ts = TranslatableString(
            original_raw=text, original_semantic=text,
            line_num=line_num,
            char_pos_start_in_file=char_start,
            char_pos_end_in_file=char_end,
            full_code_lines=full_lines,
            string_type=string_type,
            source_file_path=rel_path,
            occurrences=[(rel_path, str(line_num))],
            occurrence_index=counters.get((text, context_hint), 0),
            id=xxhash.xxh128(f"{rel_path}::{context_hint}::{text}".encode()).hexdigest()
        )
        ts.translation = text
        ts.context = context
        ts.comment = f"Type: {string_type}"
        ts.po_comment = f"#: {rel_path}:{line_num} ({string_type})"
        ts.is_reviewed = False
        ts.update_sort_weight()
        results.append(ts)

    def _detect_language(self, filename: str) -> str:
        stem = os.path.splitext(filename)[0]
        # docs.zh-CN.md / index.fr.mdx
        m = re.search(r'\.([a-z]{2,3}(?:-[A-Za-z]{2,4})?)$', stem, re.IGNORECASE)
        if m:
            return m.group(1)
        return 'en'

    def _get_relative_path(self, filepath: str) -> str:
        current = Path(filepath).parent
        while True:
            if (current / 'project.json').is_file():
                try:
                    return Path(filepath).relative_to(current).as_posix()
                except ValueError:
                    break
            if current.parent == current:
                break
            current = current.parent
        return os.path.basename(filepath)

    def save(self, filepath, translatable_objects, metadata, **kwargs):
        logger.debug(f"[MarkdownFormatHandler] Saving Markdown: {filepath}")

        original_content = metadata.get('original_content', '')

        # 按 char_pos_start_in_file 降序排列，从后往前替换，避免偏移漂移
        replace_ops = []
        for ts in translatable_objects:
            if not ts.original_semantic or ts.id == "##NEW_ENTRY##":
                continue
            translation = ts.translation or ts.original_semantic
            if translation == ts.original_semantic:
                continue  # 未翻译，跳过
            if (ts.char_pos_start_in_file > 0 or ts.char_pos_end_in_file > 0):
                replace_ops.append((
                    ts.char_pos_start_in_file,
                    ts.char_pos_end_in_file,
                    ts.original_semantic,
                    translation
                ))

        # 去重 + 降序
        replace_ops.sort(key=lambda x: x[0], reverse=True)

        content = original_content
        for start, end, original, translation in replace_ops:
            # 安全校验：确认位置内容与原文匹配
            if content[start:end] == original:
                content = content[:start] + translation + content[end:]
            else:
                # 偏移可能已漂移，回退到全文替换（只替换第一次出现）
                content = content.replace(original, translation, 1)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        logger.info(f"[MarkdownFormatHandler] Saved translated document to {filepath}")


class OwCodeFormatHandler(BaseFormatHandler):
    """
    守望先锋工坊代码格式处理器
    支持的特性:
    1. 智能提取: 基于正则表达式从 .ow 或 .txt 源码中精准抠取待翻译文本
    2. 结构回填: 保存时将译文精准替换回原始位置，确保代码逻辑和格式不受损
    3. 多维识别: 支持提取自定义字符串 (Custom String)、模式名称及模式描述
    4. 自动过滤: 智能跳过数字、纯占位符及已知的工坊技术关键字
    """
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


# ============================================================================
# FORMAT MANAGER
# ============================================================================

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

FormatManager.register_handler(PoFormatHandler)
FormatManager.register_handler(TsFormatHandler)
FormatManager.register_handler(XliffFormatHandler)

FormatManager.register_handler(AndroidStringsFormatHandler)
FormatManager.register_handler(IosStringsFormatHandler)
FormatManager.register_handler(ArbFormatHandler)

FormatManager.register_handler(JsonI18nFormatHandler)
FormatManager.register_handler(YamlI18nFormatHandler)
FormatManager.register_handler(TomlFormatHandler)

FormatManager.register_handler(JavaPropertiesFormatHandler)
FormatManager.register_handler(ResxFormatHandler)

FormatManager.register_handler(CsvFormatHandler)
FormatManager.register_handler(XlsxFormatHandler)

FormatManager.register_handler(OwCodeFormatHandler)
FormatManager.register_handler(MarkdownFormatHandler)