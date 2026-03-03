# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import os
import xml.etree.ElementTree as ET
from pathlib import Path
import xxhash
import logging
import json
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

            # [FIX] 查找 trans-unit 也要带前缀
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


# 注册内置处理器
FormatManager.register_handler(PoFormatHandler)
FormatManager.register_handler(TsFormatHandler)
FormatManager.register_handler(OwCodeFormatHandler)
FormatManager.register_handler(JsonI18nFormatHandler)
FormatManager.register_handler(XliffFormatHandler)
FormatManager.register_handler(AndroidStringsFormatHandler)