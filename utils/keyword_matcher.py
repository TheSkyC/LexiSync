# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

class TrieNode:
    __slots__ = ('children', 'is_end', 'data')

    def __init__(self):
        self.children = {}
        self.is_end = False
        self.data = None


class KeywordMatcher:
    """
    基于 Trie 树的高效关键词匹配器。
    用于在长文本中快速查找已知的术语。
    """
    def __init__(self, case_sensitive=False):
        self.root = TrieNode()
        self.case_sensitive = case_sensitive

    def add_keywords(self, keywords_dict):
        """
        批量添加关键词。
        :param keywords_dict: { 'term': 'translation' } 或 { 'term': data }
        """
        for term, data in keywords_dict.items():
            self.add_keyword(term, data)

    def add_keyword(self, term, data=None):
        if not term:
            return

        node = self.root
        processing_term = term if self.case_sensitive else term.lower()

        for char in processing_term:
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]

        node.is_end = True
        node.data = data

    def extract_keywords(self, text):
        """
        在文本中查找所有匹配的关键词。
        采用最长匹配原则 (Longest Match Preference)。
        :return: list of {'term': str, 'data': any, 'start': int, 'end': int}
        """
        if not text:
            return []

        processing_text = text if self.case_sensitive else text.lower()
        n = len(processing_text)
        results = []
        i = 0

        while i < n:
            node = self.root
            j = i
            last_match_end = -1
            last_match_data = None

            # 尝试匹配尽可能长的词
            while j < n and processing_text[j] in node.children:
                node = node.children[processing_text[j]]
                j += 1
                if node.is_end:
                    last_match_end = j
                    last_match_data = node.data

            if last_match_end != -1:
                # 找到了匹配
                # 简单的单词边界检查 (可选，防止匹配到单词内部，如 "he" 匹配 "hello")
                # 这里做一个简单的边界检查：如果匹配结束位置后面是字母数字，则视为单词内部匹配，忽略
                is_valid_word = True
                if last_match_end < n:
                    next_char = processing_text[last_match_end]
                    if next_char.isalnum() or next_char == '_':
                        is_valid_word = False

                if is_valid_word:
                    original_term = text[i:last_match_end]
                    results.append({
                        'term': original_term,
                        'data': last_match_data,
                        'start': i,
                        'end': last_match_end
                    })
                    i = last_match_end
                    continue

            i += 1

        return results