# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import re
import regex
import random
import logging
logger = logging.getLogger(__name__)


class ObfuscatorLogic:
    def __init__(self, code_content, options, element_count=32768):
        self.logger = logging.getLogger(__name__)
        self.code = code_content
        self.options = options
        self.max_elements = 30000
        self.available_elements = self.max_elements - element_count

        self.header_blocks = ""
        self.rules_block = ""
        self.variables_block_content = ""
        self.subroutines_block_content = ""

        self.strings = []
        self.dynamic_list = {'subroutines': [], 'global_vars': [], 'player_vars': []}
        self.obfuscated_names = self._get_obfuscated_names(1024)

    @staticmethod
    def estimate_element_count(code_content: str) -> int:
        byte_count = len(code_content.encode('utf-8'))
        line_count = code_content.count('\n') + 1
        estimated = (0.071 * byte_count) + (0.15 * line_count) - 500
        if estimated < 0:
            estimated = 100
        return estimated

    def run(self):
        processed_code = self.code
        if self.options.get('remove_comments', True):
            processed_code = self._remove_comments(processed_code)
        self._parse_and_separate_blocks(processed_code)
        self._parse_dynamic_list()
        processed_rules = self.rules_block
        if self.options.get('remove_rule_names', True):
            processed_rules = self._remove_rule_names(processed_rules)
        if self.options.get('obfuscate_strings', True):
            processed_rules = self._obfuscate_strings(processed_rules)
        new_header_blocks = self.header_blocks
        if self.options.get('obfuscate_variables'):
            processed_rules, new_vars_block, new_subs_block = self._obfuscate_names(processed_rules)
            new_header_blocks = new_header_blocks.replace(self.variables_block_content, new_vars_block)
            new_header_blocks = new_header_blocks.replace(self.subroutines_block_content, new_subs_block)
        if self.options.get('obfuscate_indices') or self.options.get('obfuscate_local_indices'):
            processed_rules = self._obfuscate_indices(processed_rules)
        if self.options.get('obfuscate_rules'):
            processed_rules = self._pad_rules(processed_rules)
        return f"{new_header_blocks}\n\n{processed_rules}"

    def _get_obfuscated_names(self, count):
        chars = "Il"
        names = set()
        max_attempts = count * 100
        attempts = 0
        while len(names) < count and attempts < max_attempts:
            length = random.randint(8, 12)
            names.add(''.join(random.choice(chars) for _ in range(length)))
            attempts += 1
        if len(names) < count:
            self.logger.warning(f"Could only generate {len(names)} unique names out of {count} requested.")
        name_list = list(names)
        random.shuffle(name_list)
        return name_list

    def _parse_and_separate_blocks(self, content):
        self.header_blocks = content
        self.rules_block = ""
        rule_start_match = regex.search(r"^\s*(?:禁用\s*|disabled\s*)?规则|rule", content,
                                        regex.MULTILINE | regex.IGNORECASE)
        if rule_start_match:
            rule_start_pos = rule_start_match.start()
            self.header_blocks = content[:rule_start_pos]
            self.rules_block = content[rule_start_pos:]
        var_pattern = regex.compile(r"(?i)(变量|variables)\s*(\{ (?: [^{}]* | (?2) )* \})", regex.VERBOSE)
        sub_pattern = regex.compile(r"(?i)(子程序|subroutines)\s*(\{ (?: [^{}]* | (?2) )* \})", regex.VERBOSE)

        variables_match = var_pattern.search(self.header_blocks)
        if variables_match:
            self.variables_block_content = variables_match.group(0)
        else:
            self.variables_block_content = "变量 {\n\t全局:\n\t玩家:\n}"

        subroutines_match = sub_pattern.search(self.header_blocks)
        if subroutines_match:
            self.subroutines_block_content = subroutines_match.group(0)
        else:
            self.subroutines_block_content = "子程序 {\n}"
    def _parse_dynamic_list(self):
        self.dynamic_list = {'subroutines': [], 'global_vars': [], 'player_vars': []}

        # 解析全局变量
        global_vars_match = regex.search(r"(?i)全局:\s*([\s\S]*?)(?=\s*玩家:|\})", self.variables_block_content)
        if global_vars_match:
            for line in global_vars_match.group(1).splitlines():
                if ':' in line:
                    parts = line.split(':', 1)
                    name = parts[1].strip()
                    if name: self.dynamic_list['global_vars'].append(name)

        # 解析玩家变量
        player_vars_match = regex.search(r"(?i)玩家:\s*([\s\S]*?)\}", self.variables_block_content)
        if player_vars_match:
            for line in player_vars_match.group(1).splitlines():
                if ':' in line:
                    parts = line.split(':', 1)
                    name = parts[1].strip()
                    if name: self.dynamic_list['player_vars'].append(name)

        # 解析子程序
        subroutines_match = regex.search(r"(?i)(子程序|subroutines)\s*\{([\s\S]*?)\}", self.subroutines_block_content)
        if subroutines_match:
            for line in subroutines_match.group(2).splitlines():
                if ':' in line:
                    parts = line.split(':', 1)
                    name = parts[1].strip()
                    if name: self.dynamic_list['subroutines'].append(name)

    def _remove_comments(self, text):
        text = regex.sub(r"/\*.*?\*/", "", text, flags=regex.DOTALL)
        text = regex.sub(r"//.*", "", text)
        return text

    def _remove_rule_names(self, text):
        return regex.sub(
            r'((?:禁用\s*|disabled\s*)?规则|rule)\s*\(".*?"\)',
            r'\1("")',
            text,
            flags=regex.IGNORECASE | regex.MULTILINE
        )

    def _obfuscate_strings(self, text):
        pattern = regex.compile(
            r'(自定义字符串\s*\(\s*")'
            r'((?:\\"|[^"])*)'
            r'((?:[^()]*|\((?R)\))*?)'
            r'(\))',
            regex.IGNORECASE
        )
        return pattern.sub(self._string_replacer, text)

    def _string_replacer(self, match):
        prefix = match.group(1)
        string_content = match.group(2)
        other_args = match.group(3)
        suffix = match.group(4)

        parts = regex.split(r'(\{\d+\}|\\r|\\n)', string_content)
        obfuscated_parts = []
        for i, part in enumerate(parts):
            if i % 2 == 1:
                obfuscated_parts.append(part)
            else:
                obfuscated_part = ''.join(
                    chr(ord(c) + 0xE0000) if ' ' <= c <= '~' and c != '\\' else c
                    for c in part
                )
                obfuscated_parts.append(obfuscated_part)

        obfuscated_content = "".join(obfuscated_parts)

        return f'{prefix}{obfuscated_content}{other_args}{suffix}'

    def _pad_rules(self, text):
        complexity_factor = self.options.get('complexity', 50) / 100.0
        padding_budget = int(self.available_elements * (2 / 3) * complexity_factor)

        if padding_budget <= 0:
            self.logger.info("No available element budget for rule padding.")
            return text

        num_padding_total = padding_budget # 每条空规则占用1点元素
        if num_padding_total <= 0:
            return text
        rule_pattern = re.compile(r"^\s*(?:禁用\s*|disabled\s*)?规则|rule", re.IGNORECASE | re.MULTILINE)
        insertion_points = [match.start() for match in rule_pattern.finditer(text)]
        if not insertion_points:
            padding_rule = '规则("")\n{\n\t事件\n\t{\n\t\t持续 - 全局;\n\t}\n\t动作\n\t{\n\t}\n}\n'
            return text + ('\n' * 2) + (padding_rule * num_padding_total)
        num_gaps = len(insertion_points)
        padding_per_gap = num_padding_total // num_gaps
        remaining_padding = num_padding_total % num_gaps

        self.logger.info(
            f"Complexity: {complexity_factor * 100}%. Padding budget: {padding_budget}. "
            f"Total fake rules: {num_padding_total}. Original rules: {num_gaps}. "
            f"Padding per gap: ~{padding_per_gap}."
        )

        padding_rule = '规则("")\n{\n\t事件\n\t{\n\t\t持续 - 全局;\n\t}\n\t动作\n\t{\n\t}\n}\n'
        processed_text = text
        for i in range(len(insertion_points) - 1, -1, -1):
            insert_pos = insertion_points[i]
            num_to_add = padding_per_gap
            if i < remaining_padding:
                num_to_add += 1
            if num_to_add > 0:
                padding_str = padding_rule * num_to_add
                processed_text = processed_text[:insert_pos] + padding_str + processed_text[insert_pos:]

        return processed_text

    def _obfuscate_names(self, rules_text):
        name_counter = 0
        keywords = {'for', 'if', 'else', 'while', 'end', 'true', 'false', 'null', '全局', '玩家', '事件'}
        sub_map, global_map, player_map = {}, {}, {}
        for name in self.dynamic_list['subroutines']:
            if name.lower() not in keywords:
                sub_map[name] = self.obfuscated_names[name_counter]
                name_counter += 1
        for name in self.dynamic_list['global_vars']:
            if name.lower() not in keywords:
                global_map[name] = self.obfuscated_names[name_counter]
                name_counter += 1
        for name in self.dynamic_list['player_vars']:
            if name.lower() not in keywords:
                player_map[name] = self.obfuscated_names[name_counter]
                name_counter += 1
        # 阶段 A: 替换所有带前缀的变量
        # 匹配 `事件玩家.Var` 或 `全局.Var`
        all_var_names = sorted(list(global_map.keys()) + list(player_map.keys()), key=len, reverse=True)
        if all_var_names:
            prefix_pattern = regex.compile(
                r'((?:[\w\u4e00-\u9fa5]+|\))\.)('
                + '|'.join(regex.escape(n) for n in all_var_names) + r')\b',
                regex.IGNORECASE
            )
            def prefix_replacer(match):
                prefix, name = match.group(1), match.group(2)
                if prefix.lower() in ['全局.', 'global.']:
                    return prefix + global_map.get(name, name)
                else:
                    return prefix + player_map.get(name, name)
            rules_text = prefix_pattern.sub(prefix_replacer, rules_text)

        # 阶段 B: 替换特定函数调用中的无前缀变量
        # B-1: 全局变量
        if global_map:
            global_names = sorted(global_map.keys(), key=len, reverse=True)
            # 匹配 Func(GlobalVar, ...) 或 Func(GlobalVar)
            global_func_pattern = regex.compile(
                r'((?:修改全局变量|设置全局变量|在索引处设置全局变量|在索引处修改全局变量|持续追踪全局变量|追踪全局变量频率|停止追踪全局变量|For\s+全局变量)\s*\()(' + '|'.join(
                    regex.escape(n) for n in global_names) + r')([,\)])', regex.IGNORECASE)
            rules_text = global_func_pattern.sub(
                lambda m: m.group(1) + global_map.get(m.group(2), m.group(2)) + m.group(3), rules_text)

        # B-2: 玩家变量
        if player_map:
            player_names = sorted(player_map.keys(), key=len, reverse=True)
            # 匹配 Func(..., PlayerVar, ...)
            player_func_pattern = regex.compile(
                r'((?:修改玩家变量|设置玩家变量|在索引处设置玩家变量|在索引处修改玩家变量|持续追踪玩家变量|追踪玩家变量频率|停止追踪玩家变量|For\s+玩家变量)\s*\((?:[^,)]+,)*\s*)(' + '|'.join(
                    regex.escape(n) for n in player_names) + r')([,\)])', regex.IGNORECASE)
            rules_text = player_func_pattern.sub(
                lambda m: m.group(1) + player_map.get(m.group(2), m.group(2)) + m.group(3), rules_text)

        # 阶段 C: 替换子程序
        if sub_map:
            sub_names = sorted(sub_map.keys(), key=len, reverse=True)
            # C-1: 事件块中的 `子程序; SubName;`
            event_pattern = regex.compile(
                r'(子程序\s*;\s*)(' + '|'.join(regex.escape(n) for n in sub_names) + r')(\s*;)', regex.IGNORECASE)
            rules_text = event_pattern.sub(lambda m: m.group(1) + sub_map.get(m.group(2), m.group(2)) + m.group(3),
                                           rules_text)
            # C-2: `调用子程序(SubName)`
            call_pattern = regex.compile(
                r'(调用子程序\s*\()(' + '|'.join(regex.escape(n) for n in sub_names) + r')(\s*\))', regex.IGNORECASE)
            rules_text = call_pattern.sub(lambda m: m.group(1) + sub_map.get(m.group(2), m.group(2)) + m.group(3),
                                          rules_text)
            # C-3: `开始规则(SubName, ...)`
            start_rule_pattern = regex.compile(
                r'(开始规则\s*\()(' + '|'.join(regex.escape(n) for n in sub_names) + r')(\s*,)', regex.IGNORECASE)
            rules_text = start_rule_pattern.sub(lambda m: m.group(1) + sub_map.get(m.group(2), m.group(2)) + m.group(3),
                                                rules_text)

        # 重建代码块
        new_vars_block = "变量\n{\n\t全局:\n"
        for i, name in enumerate(self.dynamic_list['global_vars']):
            obf_name = global_map.get(name, name)
            new_vars_block += f"\t\t{i}: {obf_name}\n"
        new_vars_block += "\t玩家:\n"
        for i, name in enumerate(self.dynamic_list['player_vars']):
            obf_name = player_map.get(name, name)
            new_vars_block += f"\t\t{i}: {obf_name}\n"
        new_vars_block += "}"
        new_subs_block = "子程序\n{\n"
        for i, name in enumerate(self.dynamic_list['subroutines']):
            obf_name = sub_map.get(name, name)
            new_subs_block += f"\t\t{i}: {obf_name}\n"
        new_subs_block += "}"

        return rules_text, new_vars_block, new_subs_block