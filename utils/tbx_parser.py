# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import xml.etree.ElementTree as ET
import logging
from typing import List, Dict, Set

logger = logging.getLogger(__name__)


class TBXParser:
    def __init__(self):
        self.namespace_map = {}

    def parse_tbx(self, filepath: str, analyze_only: bool = False) -> Dict:
        """
        Parses a TBX file, detects languages, and extracts term entries.

        :param filepath: Path to the TBX file.
        :param analyze_only: If True, only detects languages and returns them.
        :return: A dictionary containing 'detected_languages' and 'term_entries'.
        """
        try:
            self._detect_namespaces(filepath)

            tree = ET.parse(filepath)
            root = tree.getroot()

            detected_languages = self._detect_languages(root)

            if analyze_only:
                return {"detected_languages": detected_languages, "term_entries": []}

            term_entries_nodes = self._find_term_entries(root)
            if not term_entries_nodes:
                logger.warning(f"No <termEntry> or <conceptEntry> elements found in {filepath}.")
                return {"detected_languages": detected_languages, "term_entries": []}

            parsed_term_entries = []
            for entry_node in term_entries_nodes:
                lang_map = self._extract_lang_map_from_entry(entry_node)
                if len(lang_map) >= 2:
                    parsed_term_entries.append(lang_map)
            return {"detected_languages": detected_languages, "term_entries": parsed_term_entries}

        except ET.ParseError as e:
            logger.error(f"Invalid XML in TBX file: {e}", exc_info=True)
            raise ValueError(f"Invalid XML in TBX file: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during TBX parsing: {e}", exc_info=True)
            return {"detected_languages": [], "term_entries": []}

    def _detect_namespaces(self, filepath: str):
        self.namespace_map = {}
        try:
            for event, elem in ET.iterparse(filepath, events=('start-ns',)):
                prefix, uri = event
                self.namespace_map[prefix] = uri

            if not self.namespace_map:
                for event, elem in ET.iterparse(filepath, events=('start',)):
                    if '}' in elem.tag:
                        ns_uri = elem.tag.split('}')[0][1:]
                        self.namespace_map[''] = ns_uri
                    break
        except Exception:
            pass

    def _find_term_entries(self, root) -> List[ET.Element]:
        """Finds all term entry nodes, trying common names."""
        paths_to_try = ['.//conceptEntry', './/termEntry']
        for path in paths_to_try:
            entries = root.findall(path, self.namespace_map)
            if entries:
                return entries
        return []

    def _detect_languages(self, root) -> List[str]:
        """Detects all unique language codes defined in xml:lang attributes."""
        langs = set()
        xml_lang_attr = '{http://www.w3.org/XML/1998/namespace}lang'
        for elem in root.findall('.//*[@xml:lang]', {'xml': 'http://www.w3.org/XML/1998/namespace'}):
            lang_code = elem.get(xml_lang_attr)
            if lang_code:
                langs.add(lang_code)
        return sorted(list(langs))

    def _extract_lang_map_from_entry(self, entry_node: ET.Element) -> Dict[str, List[str]]:
        lang_map = {}
        xml_lang_attr = '{http://www.w3.org/XML/1998/namespace}lang'

        # Common structure: <langSec xml:lang="en"> or <langSet xml:lang="en">
        lang_sections = entry_node.findall('./langSec', self.namespace_map) + entry_node.findall('./langSet',
                                                                                                 self.namespace_map)

        for sec in lang_sections:
            lang_code = sec.get(xml_lang_attr)
            if not lang_code:
                continue

            terms = []
            # Common structure: <termSec><term>...</term></termSec> or <tig><term>...</term></tig>
            for term_node in sec.findall('.//term', self.namespace_map):
                if term_node.text and term_node.text.strip():
                    terms.append(term_node.text.strip())

            if terms:
                lang_map[lang_code] = terms

        return lang_map