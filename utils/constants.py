# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import uuid

APP_NAMESPACE_UUID = uuid.UUID('c2e02333-2f1d-48ba-bc8d-90d49da373af')
CONFIG_FILE = "localization_tool_config.json"
PROJECT_FILE_EXTENSION = ".owproj"
TM_FILE_EXCEL = "ow_translator_tm.xlsx"
MAX_UNDO_HISTORY = 30
DEFAULT_API_URL = "https://api.deepseek.com/chat/completions"
APP_VERSION = "1.0.3"
PROMPT_PRESET_EXTENSION = ".owprompt"
EXTRACTION_PATTERN_PRESET_EXTENSION = ".owextract"

STRUCTURAL = "结构化内容"
STATIC = "静态指令"
DYNAMIC = "动态指令"
DEFAULT_PROMPT_STRUCTURE = [
    {
        "id": str(uuid.uuid4()), "type": STRUCTURAL, "enabled": True,
        "content": "你是一个专业的游戏文本翻译器，负责将《守望先锋》自定义模式的界面UI文本和描述翻译成[Target Language]。\n请严格遵循以下要求："
    },
    {
        "id": str(uuid.uuid4()), "type": STATIC, "enabled": True,
        "content": "将以下文本翻译成[Target Language]语言。"
    },
    {
        "id": str(uuid.uuid4()), "type": DYNAMIC, "enabled": True,
        "content": "请遵循以下针对此项目的特定翻译指示：\n[Custom Translate]"
    },
    {
        "id": str(uuid.uuid4()), "type": STATIC, "enabled": True,
        "content": "如果原来的语言与目标语言一样，则不需要作改动。"
    },
    {
        "id": str(uuid.uuid4()), "type": STATIC, "enabled": True,
        "content": "所有符号必须保留。比如'\\n'，'\\r'，'任何空格'，'()'，'[]'，以及'.。?/\\'等等必须保留原样，无需翻译。同时，原来没有的符号也不要乱添加。"
    },
    {
        "id": str(uuid.uuid4()), "type": DYNAMIC, "enabled": True,
        "content": "请参考以下未翻译的原文上下文信息，以确保术语和风格的一致性（如果上下文与当前文本相关）：\n[Untranslated Context]"
    },
    {
        "id": str(uuid.uuid4()), "type": DYNAMIC, "enabled": True,
        "content": "请参考以下已翻译的译文上下文信息，以确保术语和风格的一致性（如果上下文与当前文本相关）：\n[Translated Context]"
    },
    {
        "id": str(uuid.uuid4()), "type": STATIC, "enabled": True,
        "content": "翻译结果应准确、简洁，并符合《守望先锋》的游戏内语言风格。"
    },
    {
        "id": str(uuid.uuid4()), "type": STRUCTURAL, "enabled": True,
        "content": "重要：你的回答[必须且仅能包含翻译后的文本内容]，不要添加任何额外的解释、说明。"
    }
]

DEFAULT_EXTRACTION_PATTERNS = [
    {
        "id": str(uuid.uuid4()), "name": "Custom String (EN/CN)", "enabled": True,
        "regex_pattern_str": r'(?:自定义字符串|Custom String)\s*\(\s*\"', # Note: The regex should end just BEFORE the opening quote of the content
        "string_type": "Custom String"
    },
    {
        "id": str(uuid.uuid4()), "name": "Description (EN/CN)", "enabled": True,
        "regex_pattern_str": r'(?:Description|描述)\s*:\s*\"',
        "string_type": "Description"
    },
    {
        "id": str(uuid.uuid4()), "name": "Mode Name (EN/CN)", "enabled": True,
        "regex_pattern_str": r'(?:Mode Name|模式名称)\s*:\s*\"',
        "string_type": "Mode Name"
    }
]

DEFAULT_KEYBINDINGS = {
    'open_code_file': '<Control-o>',
    'open_project': '<Control-Shift-O>',
    'save_project': '<Control-p>',
    'save_code_file': '<Control-s>',
    'undo': '<Control-z>',
    'redo': '<Control-y>',
    'find_replace': '<Control-Shift-F>',
    'copy_original': '<Control-Shift-C>',
    'paste_translation': '<Control-Shift-V>',
    'ai_translate_selected': '<Control-t>',
    'toggle_reviewed': '<Control-r>',
    'toggle_ignored': '<Control-i>',
    'apply_and_next': '<Control-Return>',
}