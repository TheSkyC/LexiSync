import re
from models.translatable_string import TranslatableString, unescape_overwatch_string

class CodeFileService:
    @staticmethod
    def extract_translatable_strings(code_content):
        strings = []
        full_code_lines = code_content.splitlines()

        patterns = [
            ("Custom String", re.compile(r'(?:自定义字符串|Custom String)\s*\(\s*\"', re.IGNORECASE)),
            ("Description", re.compile(r'(?:Description|描述)\s*:\s*\"', re.IGNORECASE)),
            ("Mode Name", re.compile(r'(?:Mode Name|模式名称)\s*:\s*\"', re.IGNORECASE)),
        ]

        regex_all_digits = re.compile(r'^\d+$')
        regex_ow_placeholder = re.compile(r'^\{\d+\}$')
        allowed_symbols = r".,?!|:;\-_+=*/%&#@$^~`<>(){}\[\]\s"
        regex_only_symbols = re.compile(f"^[{re.escape(allowed_symbols)}]+$")
        regex_placeholder_like = re.compile(r'\{\d+\}')
        regex_repeating_char = re.compile(r"^(.)\1{1,}$")
        regex_progress_bar = re.compile(r"^[\[\(\|\-=<>#\s]*[\]\s]*$")
        known_untranslatable = {"ID", "HP", "MP", "XP", "LV", "CD", "UI", "OK", "X", "Y", "Z", "A", "B", "C", "N/A"}

        for string_type, pattern in patterns:
            for match in pattern.finditer(code_content):
                start_idx = match.end()
                content_chars = []
                ptr = start_idx
                escaped = False
                closed = False
                end_idx = -1

                while ptr < len(code_content):
                    char = code_content[ptr]
                    if escaped:
                        content_chars.append(char)
                        escaped = False
                    elif char == '\\':
                        content_chars.append(char)
                        escaped = True
                    elif char == '"':
                        closed = True
                        end_idx = ptr
                        break
                    elif char == '\n' and string_type == "Custom String":
                        break
                    else:
                        content_chars.append(char)
                    ptr += 1

                if closed:
                    raw_content = "".join(content_chars)
                    semantic_content = unescape_overwatch_string(raw_content)
                    line_num = code_content.count('\n', 0, start_idx) + 1

                    ts = TranslatableString(
                        original_raw=raw_content,
                        original_semantic=semantic_content,
                        line_num=line_num,
                        char_pos_start_in_file=start_idx,
                        char_pos_end_in_file=end_idx,
                        full_code_lines=full_code_lines,
                        string_type=string_type
                    )

                    if string_type in ["Description", "Mode Name"]:
                        ts.comment = string_type

                    s_stripped = semantic_content.strip()
                    s_len = len(s_stripped)

                    auto_ignore = (
                        not s_stripped or
                        regex_all_digits.fullmatch(s_stripped) or
                        regex_ow_placeholder.fullmatch(s_stripped) or
                        (s_len == 1 and 'a' <= s_stripped.lower() <= 'z' and s_stripped.isascii()) or
                        regex_only_symbols.fullmatch(semantic_content) or
                        (s_len >= 2 and regex_repeating_char.fullmatch(s_stripped)) or
                        s_stripped.upper() in known_untranslatable or
                        (s_len > 2 and regex_progress_bar.fullmatch(s_stripped))
                    )

                    if not auto_ignore and regex_placeholder_like.search(s_stripped):
                        content_no_placeholders = regex_placeholder_like.sub('', s_stripped)
                        content_text_only = re.sub(f"[{re.escape(allowed_symbols)}]", '', content_no_placeholders).strip()
                        if len(content_text_only) < 2:
                            auto_ignore = True

                    if auto_ignore:
                        ts.was_auto_ignored = True
                        ts.is_ignored = True

                    strings.append(ts)

        strings.sort(key=lambda s: s.char_pos_start_in_file)
        return strings

    @staticmethod
    def generate_translated_code(original_code, translatable_objects):
        content_chars = list(original_code)
        sorted_ts = sorted(translatable_objects, key=lambda ts: ts.char_pos_start_in_file, reverse=True)

        for ts_obj in sorted_ts:
            if ts_obj.translation and not ts_obj.is_ignored:
                start = ts_obj.char_pos_start_in_file
                end = ts_obj.char_pos_end_in_file
                raw_translated = ts_obj.get_raw_translated_for_code()
                content_chars[start:end] = list(raw_translated)

        return "".join(content_chars)