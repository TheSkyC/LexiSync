# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import xml.etree.ElementTree as ET
import logging
from typing import List, Dict, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class TBXParser:
    """Parser for TBX (TermBase eXchange) files."""

    # XML namespace constants
    XML_NS = '{http://www.w3.org/XML/1998/namespace}'
    XML_LANG_ATTR = f'{XML_NS}lang'

    def __init__(self):
        self.namespace_map = {}
        self._detected_languages = set()

    def parse_tbx(self, filepath: str, analyze_only: bool = False) -> Dict:
        """
        Parses a TBX file, detects languages, and extracts term entries.

        :param filepath: Path to the TBX file.
        :param analyze_only: If True, only detects languages and returns them.
        :return: A dictionary containing 'detected_languages' and 'term_entries'.
        :raises ValueError: If the file is not a valid TBX file.
        :raises FileNotFoundError: If the file does not exist.
        """
        # Validate file exists
        if not Path(filepath).exists():
            raise FileNotFoundError(f"TBX file not found: {filepath}")

        try:
            # Parse and validate in one pass
            tree, root = self._parse_and_validate(filepath)

            # Detect languages during parsing
            detected_languages = sorted(list(self._detected_languages))

            if analyze_only:
                return {
                    "detected_languages": detected_languages,
                    "term_entries": []
                }

            # Extract term entries
            term_entries_nodes = self._find_term_entries(root)
            if not term_entries_nodes:
                logger.warning(
                    f"No <termEntry> or <conceptEntry> elements found in {filepath}."
                )
                return {
                    "detected_languages": detected_languages,
                    "term_entries": []
                }

            # Parse term entries with validation
            parsed_term_entries = []
            for entry_node in term_entries_nodes:
                lang_map = self._extract_lang_map_from_entry(entry_node)
                # Only include entries with at least 2 languages
                if len(lang_map) >= 2:
                    parsed_term_entries.append(lang_map)

            logger.info(
                f"Parsed {len(parsed_term_entries)} term entries "
                f"from {filepath} with languages: {detected_languages}"
            )

            return {
                "detected_languages": detected_languages,
                "term_entries": parsed_term_entries
            }

        except ET.ParseError as e:
            logger.error(f"Invalid XML in TBX file {filepath}: {e}")
            raise ValueError(f"Invalid XML in TBX file: {e}")
        except Exception as e:
            logger.error(
                f"Unexpected error parsing TBX file {filepath}: {e}",
                exc_info=True
            )
            raise

    def _parse_and_validate(self, filepath: str) -> Tuple[ET.ElementTree, ET.Element]:
        """
        Parse XML file and validate it's a TBX file.
        Also detects namespaces and languages in a single pass.
        """
        self.namespace_map = {}
        self._detected_languages = set()

        # Use iterparse for efficient single-pass parsing
        context = ET.iterparse(filepath, events=('start', 'start-ns'))

        root = None
        for event, elem in context:
            if event == 'start-ns':
                prefix, uri = elem
                self.namespace_map[prefix if prefix else ''] = uri

            elif event == 'start':
                # Capture root element
                if root is None:
                    root = elem
                    # Validate root element
                    root_tag = self._strip_namespace(root.tag)
                    if root_tag not in ('martif', 'tbx'):
                        raise ValueError(
                            f"Invalid TBX root element: {root_tag}. "
                            f"Expected 'martif' or 'tbx'."
                        )

                # Collect language codes
                lang_code = elem.get(self.XML_LANG_ATTR)
                if lang_code:
                    self._detected_languages.add(lang_code)

        if root is None:
            raise ValueError("Empty or invalid XML file")

        # Build full tree from root
        tree = ET.ElementTree(root)

        return tree, root

    @staticmethod
    def _strip_namespace(tag: str) -> str:
        """Remove namespace from tag."""
        if '}' in tag:
            return tag.split('}', 1)[1]
        return tag

    def _find_term_entries(self, root: ET.Element) -> List[ET.Element]:
        """
        Finds all term entry nodes, trying common element names.
        Searches both with and without namespaces.
        """
        entry_names = ['conceptEntry', 'termEntry']
        entries = []

        for name in entry_names:
            # Try with namespace
            found = root.findall(f'.//{name}', self.namespace_map)
            if found:
                entries.extend(found)

            # Try without namespace (for files without proper namespace declarations)
            if not found and self.namespace_map:
                for prefix, uri in self.namespace_map.items():
                    ns_name = f'{{{uri}}}{name}' if uri else name
                    found = root.findall(f'.//{ns_name}')
                    if found:
                        entries.extend(found)
                        break

        return entries

    def _extract_lang_map_from_entry(
            self,
            entry_node: ET.Element
    ) -> Dict[str, List[str]]:
        """
        Extract language-to-terms mapping from a term entry node.

        :param entry_node: The termEntry or conceptEntry element.
        :return: Dictionary mapping language codes to lists of terms.
        """
        lang_map = {}

        # Common TBX structures for language sections
        lang_section_names = ['langSec', 'langSet']
        lang_sections = []

        for name in lang_section_names:
            lang_sections.extend(
                entry_node.findall(f'./{name}', self.namespace_map)
            )

        for sec in lang_sections:
            lang_code = sec.get(self.XML_LANG_ATTR)
            if not lang_code:
                # Try without namespace prefix
                lang_code = sec.get('lang')

            if not lang_code:
                continue

            # Extract all term elements
            terms = self._extract_terms_from_section(sec)

            if terms:
                # Avoid duplicates while preserving order
                if lang_code in lang_map:
                    lang_map[lang_code].extend(
                        t for t in terms if t not in lang_map[lang_code]
                    )
                else:
                    lang_map[lang_code] = terms

        return lang_map

    def _extract_terms_from_section(self, section: ET.Element) -> List[str]:
        """
        Extract term text from a language section.
        Handles various TBX structures (termSec, tig, ntig, term).
        """
        terms = []

        # Find all <term> elements regardless of parent structure
        term_nodes = section.findall('.//term', self.namespace_map)

        for term_node in term_nodes:
            term_text = self._get_element_text(term_node)
            if term_text:
                terms.append(term_text)

        return terms

    @staticmethod
    def _get_element_text(element: ET.Element) -> Optional[str]:
        """
        Extract and clean text from an element.
        """
        if element.text:
            text = element.text.strip()
            if text:
                return text
        return None


# Convenience function for simple usage
def parse_tbx_file(
        filepath: str,
        analyze_only: bool = False
) -> Dict:
    """
    Parse a TBX file.

    :param filepath: Path to the TBX file.
    :param analyze_only: If True, only detect languages.
    :return: Dictionary with 'detected_languages' and 'term_entries'.
    """
    parser = TBXParser()
    return parser.parse_tbx(filepath, analyze_only)