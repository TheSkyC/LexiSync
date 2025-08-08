import xml.etree.ElementTree as ET
import logging
from typing import List, Dict, Optional, Tuple
import re

logger = logging.getLogger(__name__)


class TBXParser:
    def __init__(self):
        self.namespace_map = {}
        self.structure_stats = {
            'total_entries': 0,
            'successful_extractions': 0,
            'strategy_usage': {}
        }

    def parse_tbx(self, filepath: str) -> List[Dict]:
        try:
            tree = ET.parse(filepath)
            root = tree.getroot()
            self._extract_namespaces(root)
            term_entries = self._find_term_entries(root)

            if not term_entries:
                logger.warning("No <termEntry> elements found")
                return []
            self.structure_stats['total_entries'] = len(term_entries)
            structure_info = self._analyze_structure(term_entries[:5])
            logger.info(f"TBX structure analysis: {structure_info}")
            terms = []
            for i, term_entry in enumerate(term_entries):
                extracted_terms = self._extract_terms_universal(term_entry, i)
                if extracted_terms:
                    terms.extend(extracted_terms)
                    self.structure_stats['successful_extractions'] += 1
            success_rate = (self.structure_stats['successful_extractions'] /
                            self.structure_stats['total_entries'] * 100)
            logger.info(f"Extraction success rate: {success_rate:.1f}%")
            logger.info(f"Strategy usage: {self.structure_stats['strategy_usage']}")
            logger.info(f"Successfully extracted {len(terms)} unique terms from TBX")

            return terms

        except ET.ParseError as e:
            logger.error(f"Invalid XML in TBX file: {e}", exc_info=True)
            raise ValueError(f"Invalid XML in TBX file: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during TBX parsing: {e}", exc_info=True)
            return []

    def _extract_namespaces(self, root):
        """提取XML命名空间信息"""
        for prefix, uri in root.nsmap.items() if hasattr(root, 'nsmap') else {}:
            if prefix:
                self.namespace_map[prefix] = uri
        root_tag = root.tag
        if '}' in root_tag:
            namespace = root_tag.split('}')[0][1:]
            self.namespace_map['default'] = namespace

    def _find_term_entries(self, root):
        term_entries = []
        # 1. 直接查找
        term_entries = root.findall('.//termEntry')
        if term_entries:
            return term_entries

        # 2. 使用命名空间查找
        for ns_prefix, ns_uri in self.namespace_map.items():
            try:
                if ns_prefix == 'default':
                    term_entries = root.findall('.//{' + ns_uri + '}termEntry')
                else:
                    term_entries = root.findall(f'.//{{{ns_uri}}}termEntry')
                if term_entries:
                    return term_entries
            except:
                continue

        # 3. 查找包含"term"和"entry"的元素
        for elem in root.iter():
            if 'termentry' in elem.tag.lower() or 'term-entry' in elem.tag.lower():
                term_entries.append(elem)

        return term_entries

    def _analyze_structure(self, sample_entries: List) -> Dict:
        """分析TBX文件结构"""
        analysis = {
            'has_langset': False,
            'has_ntig': False,
            'has_tig': False,
            'has_termgrp': False,
            'has_descrip': False,
            'language_pattern': [],
            'nesting_depth': 0,
            'common_paths': []
        }

        for entry in sample_entries:
            # 检查各种结构元素
            if entry.find('.//langSet') is not None:
                analysis['has_langset'] = True
            if entry.find('.//ntig') is not None:
                analysis['has_ntig'] = True
            if entry.find('.//tig') is not None:
                analysis['has_tig'] = True
            if entry.find('.//termGrp') is not None:
                analysis['has_termgrp'] = True
            if entry.find('.//descripGrp') is not None:
                analysis['has_descrip'] = True

            # 分析语言模式
            lang_sets = entry.findall('.//langSet')
            for ls in lang_sets:
                lang_attr = ls.get('lang') or ls.get('{http://www.w3.org/XML/1998/namespace}lang')
                if lang_attr and lang_attr not in analysis['language_pattern']:
                    analysis['language_pattern'].append(lang_attr)

            # 计算嵌套深度
            depth = self._calculate_depth(entry)
            analysis['nesting_depth'] = max(analysis['nesting_depth'], depth)

            # 查找term元素的路径
            term_paths = self._find_term_paths(entry)
            analysis['common_paths'].extend(term_paths)

        return analysis

    def _calculate_depth(self, element, depth=0):
        """计算XML元素的最大嵌套深度"""
        if not list(element):
            return depth
        return max(self._calculate_depth(child, depth + 1) for child in element)

    def _find_term_paths(self, entry):
        """查找term元素的所有路径"""
        paths = []
        for term in entry.findall('.//term'):
            path = []
            current = term
            while current != entry and current is not None:
                path.insert(0, self._clean_tag_name(current.tag))
                current = current.getparent() if hasattr(current, 'getparent') else None
            if path:
                paths.append('/'.join(path))
        return paths

    def _clean_tag_name(self, tag):
        """清理标签名，去除命名空间"""
        if '}' in tag:
            return tag.split('}')[1]
        return tag

    def _extract_terms_universal(self, term_entry, entry_index: int) -> List[Dict]:
        """
        使用多种策略提取术语，按优先级顺序尝试
        """
        strategies = [
            ('microsoft_ntig', self._strategy_microsoft_ntig),
            ('standard_tig', self._strategy_standard_tig),
            ('termgrp_direct', self._strategy_termgrp_direct),
            ('nested_termgrp', self._strategy_nested_termgrp),
            ('descrip_group', self._strategy_descrip_group),
            ('all_terms_simple', self._strategy_all_terms_simple),
            ('xml_lang_based', self._strategy_xml_lang_based),
            ('SDL_trados', self._strategy_sdl_trados),
            ('memoq_style', self._strategy_memoq_style),
            ('generic_fallback', self._strategy_generic_fallback)
        ]

        for strategy_name, strategy_func in strategies:
            try:
                result = strategy_func(term_entry)
                if result:
                    # 记录成功的策略
                    if strategy_name not in self.structure_stats['strategy_usage']:
                        self.structure_stats['strategy_usage'][strategy_name] = 0
                    self.structure_stats['strategy_usage'][strategy_name] += 1

                    return result
            except Exception as e:
                # 策略失败，尝试下一个
                continue

        return []

    def _strategy_microsoft_ntig(self, term_entry) -> List[Dict]:
        """Microsoft TBX格式: langSet -> ntig -> termGrp -> term"""
        lang_sets = term_entry.findall('langSet')
        if len(lang_sets) < 2:
            return []

        source_ntig = lang_sets[0].find('ntig')
        if source_ntig is None:
            return []

        source_term_grp = source_ntig.find('termGrp')
        if source_term_grp is None:
            return []

        source_term_node = source_term_grp.find('term')
        if source_term_node is None or not source_term_node.text:
            return []

        source_term = source_term_node.text.strip()
        target_terms = []

        for target_lang_set in lang_sets[1:]:
            target_ntig = target_lang_set.find('ntig')
            if target_ntig is not None:
                target_term_grp = target_ntig.find('termGrp')
                if target_term_grp is not None:
                    target_term_node = target_term_grp.find('term')
                    if target_term_node is not None and target_term_node.text:
                        target_terms.append({
                            "target": target_term_node.text.strip(),
                            "comment": ""
                        })

        if source_term and target_terms:
            return [{
                "source": source_term,
                "translations": target_terms,
                "case_sensitive": False,
                "comment": ""
            }]
        return []

    def _strategy_standard_tig(self, term_entry) -> List[Dict]:
        """标准TBX格式: langSet -> tig -> term"""
        lang_sets = term_entry.findall('langSet')
        if len(lang_sets) < 2:
            return []

        source_tig = lang_sets[0].find('tig')
        if source_tig is None:
            return []

        source_term_node = source_tig.find('term')
        if source_term_node is None or not source_term_node.text:
            return []

        source_term = source_term_node.text.strip()
        target_terms = []

        for target_lang_set in lang_sets[1:]:
            target_tig = target_lang_set.find('tig')
            if target_tig is not None:
                target_term_node = target_tig.find('term')
                if target_term_node is not None and target_term_node.text:
                    target_terms.append({
                        "target": target_term_node.text.strip(),
                        "comment": ""
                    })

        if source_term and target_terms:
            return [{
                "source": source_term,
                "translations": target_terms,
                "case_sensitive": False,
                "comment": ""
            }]
        return []

    def _strategy_termgrp_direct(self, term_entry) -> List[Dict]:
        """直接termGrp结构: termGrp -> term"""
        term_grps = term_entry.findall('.//termGrp')
        if len(term_grps) < 2:
            return []

        source_term_node = term_grps[0].find('term')
        if source_term_node is None or not source_term_node.text:
            return []

        source_term = source_term_node.text.strip()
        target_terms = []

        for term_grp in term_grps[1:]:
            term_node = term_grp.find('term')
            if term_node is not None and term_node.text:
                target_terms.append({
                    "target": term_node.text.strip(),
                    "comment": ""
                })

        if source_term and target_terms:
            return [{
                "source": source_term,
                "translations": target_terms,
                "case_sensitive": False,
                "comment": ""
            }]
        return []

    def _strategy_nested_termgrp(self, term_entry) -> List[Dict]:
        """嵌套termGrp结构"""
        # 查找所有可能的嵌套路径
        nested_paths = [
            './/langSet//termGrp',
            './/descripGrp//termGrp',
            './/termEntry//termGrp'
        ]

        for path in nested_paths:
            term_grps = term_entry.findall(path)
            if len(term_grps) >= 2:
                result = self._extract_from_termgrps(term_grps)
                if result:
                    return result
        return []

    def _strategy_descrip_group(self, term_entry) -> List[Dict]:
        """descripGrp结构"""
        descrip_grps = term_entry.findall('.//descripGrp')
        terms_found = []

        for dg in descrip_grps:
            for term_node in dg.findall('.//term'):
                if term_node.text and term_node.text.strip():
                    terms_found.append(term_node.text.strip())

        if len(terms_found) >= 2:
            return [{
                "source": terms_found[0],
                "translations": [{"target": t, "comment": ""} for t in terms_found[1:]],
                "case_sensitive": False,
                "comment": ""
            }]
        return []

    def _strategy_all_terms_simple(self, term_entry) -> List[Dict]:
        """简单策略：查找所有term元素"""
        all_terms = term_entry.findall('.//term')
        if len(all_terms) >= 2:
            valid_terms = []
            for term_node in all_terms:
                if term_node.text and term_node.text.strip():
                    valid_terms.append(term_node.text.strip())

            if len(valid_terms) >= 2:
                return [{
                    "source": valid_terms[0],
                    "translations": [{"target": t, "comment": ""} for t in valid_terms[1:]],
                    "case_sensitive": False,
                    "comment": ""
                }]
        return []

    def _strategy_xml_lang_based(self, term_entry) -> List[Dict]:
        """基于xml:lang属性的策略"""
        lang_elements = []

        # 查找所有带有语言属性的元素
        for elem in term_entry.iter():
            lang_attr = elem.get('lang') or elem.get('{http://www.w3.org/XML/1998/namespace}lang')
            if lang_attr:
                terms_in_elem = elem.findall('.//term')
                for term in terms_in_elem:
                    if term.text and term.text.strip():
                        lang_elements.append((lang_attr, term.text.strip()))

        if len(lang_elements) >= 2:
            # 按语言分组
            lang_groups = {}
            for lang, term in lang_elements:
                if lang not in lang_groups:
                    lang_groups[lang] = []
                lang_groups[lang].append(term)

            if len(lang_groups) >= 2:
                langs = list(lang_groups.keys())
                source_terms = lang_groups[langs[0]]
                target_terms = []

                for lang in langs[1:]:
                    target_terms.extend([{"target": t, "comment": ""} for t in lang_groups[lang]])

                if source_terms and target_terms:
                    return [{
                        "source": source_terms[0],
                        "translations": target_terms,
                        "case_sensitive": False,
                        "comment": ""
                    }]
        return []

    def _strategy_sdl_trados(self, term_entry) -> List[Dict]:
        """SDL Trados风格的TBX"""
        # SDL Trados通常使用特定的属性和结构
        concepts = term_entry.findall('.//conceptGrp')
        if not concepts:
            concepts = [term_entry]  # 如果没有conceptGrp，使用termEntry本身

        for concept in concepts:
            lang_grps = concept.findall('.//languageGrp')
            if len(lang_grps) >= 2:
                source_term = None
                target_terms = []

                for lang_grp in lang_grps:
                    term_grps = lang_grp.findall('.//termGrp')
                    for term_grp in term_grps:
                        term_node = term_grp.find('term')
                        if term_node is not None and term_node.text:
                            if source_term is None:
                                source_term = term_node.text.strip()
                            else:
                                target_terms.append({"target": term_node.text.strip(), "comment": ""})

                if source_term and target_terms:
                    return [{
                        "source": source_term,
                        "translations": target_terms,
                        "case_sensitive": False,
                        "comment": ""
                    }]
        return []

    def _strategy_memoq_style(self, term_entry) -> List[Dict]:
        """MemoQ风格的TBX"""
        # MemoQ可能使用不同的元素结构
        entries = term_entry.findall('.//entry')
        if not entries:
            entries = [term_entry]

        for entry in entries:
            terms = []

            # 查找各种可能的term容器
            containers = entry.findall('.//translation') + entry.findall('.//term-note')
            if not containers:
                containers = [entry]

            for container in containers:
                term_nodes = container.findall('.//term')
                for term_node in term_nodes:
                    if term_node.text and term_node.text.strip():
                        terms.append(term_node.text.strip())

            if len(terms) >= 2:
                return [{
                    "source": terms[0],
                    "translations": [{"target": t, "comment": ""} for t in terms[1:]],
                    "case_sensitive": False,
                    "comment": ""
                }]
        return []

    def _strategy_generic_fallback(self, term_entry) -> List[Dict]:
        """通用回退策略 - 最后的尝试"""
        # 查找所有可能包含术语的元素
        potential_terms = []

        # 检查各种可能的元素名称
        term_like_elements = ['term', 'translation', 'source', 'target', 'text', 'value']

        for elem_name in term_like_elements:
            elements = term_entry.findall(f'.//{elem_name}')
            for elem in elements:
                if elem.text and elem.text.strip():
                    potential_terms.append(elem.text.strip())

        # 去重
        unique_terms = list(dict.fromkeys(potential_terms))

        if len(unique_terms) >= 2:
            return [{
                "source": unique_terms[0],
                "translations": [{"target": t, "comment": ""} for t in unique_terms[1:]],
                "case_sensitive": False,
                "comment": "Extracted using fallback strategy"
            }]
        return []

    def _extract_from_termgrps(self, term_grps):
        """从termGrp列表中提取术语"""
        terms_found = []

        for term_grp in term_grps:
            term_node = term_grp.find('term')
            if term_node is not None and term_node.text:
                terms_found.append(term_node.text.strip())

        if len(terms_found) >= 2:
            return [{
                "source": terms_found[0],
                "translations": [{"target": t, "comment": ""} for t in terms_found[1:]],
                "case_sensitive": False,
                "comment": ""
            }]
        return []

def parse_tbx(filepath: str) -> List[Dict]:
    """
    简化的接口函数
    """
    parser = TBXParser()
    return parser.parse_tbx(filepath)