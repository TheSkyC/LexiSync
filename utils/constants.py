# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import uuid
from utils.localization import _

APP_NAMESPACE_UUID = uuid.UUID('c2e02333-2f1d-48ba-bc8d-90d49da373af')
CONFIG_FILE = "config.json"
EXPANSION_DATA_DIR = "expansion_data"
MAX_UNDO_HISTORY = 30
DEFAULT_API_URL = "https://api.deepseek.com/chat/completions"
APP_VERSION = "1.2.1"
PROMPT_PRESET_EXTENSION = ".prompt"
EXTRACTION_PATTERN_PRESET_EXTENSION = ".extract"

STRUCTURAL = "Structural Content"
STATIC = "Static Instruction"
DYNAMIC = "Dynamic Instruction"

DEFAULT_VALIDATION_RULES = {
    # --- 代码安全 ---
    "printf": {"enabled": True, "level": "error", "label": "Printf Format (%s, %d)"},
    "python_brace": {"enabled": True, "level": "error", "label": "Python Brace ({}, {name})"},
    "html_tags": {"enabled": True, "level": "error", "label": "HTML/XML Tags"},
    "url_email": {"enabled": True, "level": "warning", "label": "URL & Email"},

    # --- 内容一致性 ---
    "numbers": {
        "enabled": True,
        "level": "error",
        "label": "Numbers Consistency",
        "modes": {
            "strict": {
                "name": "Strict",
                "description": "Arabic numerals must match exactly (e.g. '1' must be '1')."
            },
            "loose": {
                "name": "Loose",
                "description": "Allows numerals to be translated into words (e.g. '1' -> 'One', '一', 'First')."
            }
        },
        "default_mode": "loose"
    },
    "glossary": {"enabled": True, "level": "warning", "label": "Glossary Terms"},
    "fuzzy": {"enabled": True, "level": "warning", "label": "Fuzzy State"},

    # --- 格式与标点 ---
    "punctuation": {"enabled": True, "level": "warning", "label": "Ending Punctuation"},
    "brackets": {"enabled": True, "level": "warning", "label": "Paired Brackets () [] {}"},
    "whitespace": {"enabled": True, "level": "warning", "label": "Leading/Trailing Whitespace"},
    "double_space": {"enabled": True, "level": "warning", "label": "Double Spaces"},
    "capitalization": {"enabled": False, "level": "warning", "label": "Initial Capitalization"},
    "repeated_word": {"enabled": True, "level": "info", "label": "Repeated Words"},
    "newline_count": {"enabled": True, "level": "warning", "label": "Newline Count Mismatch"},
    "quotes": {
        "enabled": True,
        "level": "info",
        "label": "Mismatched Quotes",
        "modes": {
            "strict": {
                "name": "Strict",
                "description": "Single and double quotes must match their types exactly."
            },
            "flexible": {
                "name": "Flexible",
                "description": "Allows converting single quotes to double quotes (e.g., '...' -> “...”) and vice versa."
            }
        },
        "default_mode": "flexible"
    },
    "accelerator": {"enabled": True, "level": "error", "label": "Accelerator Mismatch"},
}

DEFAULT_CORRECTION_PROMPT_STRUCTURE = [
    {
        "id": str(uuid.uuid4()),
        "type": "Structural Content",
        "enabled": True,
        "content": "你是一位专业的本地化QA专家。你的任务是修复以下译文中的错误，使其符合目标语言的语法习惯和项目规则。"
    },
    {
        "id": str(uuid.uuid4()),
        "type": "Static Instruction",
        "enabled": True,
        "content": "请参考以下错误报告（Errors），针对性地修正译文。"
    },
    {
        "id": str(uuid.uuid4()),
        "type": "Dynamic Instruction",
        "enabled": True,
        "content": "错误报告：\n[Error List]"
    },
    {
        "id": str(uuid.uuid4()),
        "type": "Dynamic Instruction",
        "enabled": True,
        "content": "原文：\n[Source Text]"
    },
    {
        "id": str(uuid.uuid4()),
        "type": "Dynamic Instruction",
        "enabled": True,
        "content": "当前有问题的译文：\n[Current Translation]"
    },
    {
        "id": str(uuid.uuid4()),
        "type": "Static Instruction",
        "enabled": True,
        "content": "请直接返回修正后的完整译文内容，不要包含任何解释、前缀或后缀。不要使用Markdown代码块。"
    }
]

DEFAULT_PROMPT_STRUCTURE = [
    {
        "id": str(uuid.uuid4()),
        "type": STRUCTURAL,
        "enabled": True,
        "content": "你是一位专业的本地化专家，负责将软件或游戏中的UI文本翻译成[Target Language]。这些文本来自标准的 PO/POT 本地化文件。\n请严格遵循以下要求："
    },
    {
        "id": str(uuid.uuid4()),
        "type": STATIC,
        "enabled": True,
        "content": "你的唯一任务是将文本翻译成[Target Language]。"
    },
    {
        "id": str(uuid.uuid4()),
        "type": DYNAMIC,
        "enabled": True,
        "content": "请遵循以下针对此项目的特定翻译指示：\n[Global Instructions]\n[Project Instructions]"
    },
    {
        "id": str(uuid.uuid4()),
        "type": STATIC,
        "enabled": True,
        "content": "如果原文已经是目标语言，则无需改动，直接返回原文。"
    },
    {
        "id": str(uuid.uuid4()),
        "type": STATIC,
        "enabled": True,
        "content": "必须完整保留所有的占位符，例如 `%s`, `%d`, `%{count}`, `{variable}` 等，占位符本身无需翻译。确保占位符的数量和名称在译文中与原文完全一致。"
    },
    {
        "id": str(uuid.uuid4()),
        "type": STATIC,
        "enabled": True,
        "content": "必须保留所有的格式化标记和控制字符，例如换行符 `\\n`、制表符 `\\t` 以及其他特殊转义字符。"
    },
    {
        "id": str(uuid.uuid4()),
        "type": STATIC,
        "enabled": True,
        "content": "除了翻译本身，不得增加或删除任何原文中没有的字符、符号或空格。除非是为了匹配当地的符号使用习惯"
    },
    {
        "id": str(uuid.uuid4()),
        "type": DYNAMIC,
        "enabled": True,
        "content": "请参考以下术语库信息：\n[Glossary]"
    },
    {
        "id": str(uuid.uuid4()),
        "type": DYNAMIC,
        "enabled": True,
        "content": "请参考以下未翻译的原文上下文信息，以确保术语和风格的一致性（如果上下文与当前文本相关）：\n[Untranslated Context]"
    },
    {
        "id": str(uuid.uuid4()),
        "type": DYNAMIC,
        "enabled": True,
        "content": "请参考以下已翻译的译文上下文信息，以确保术语和风格的一致性（如果上下文与当前文本相关）：\n[Translated Context]"
    },
    {
        "id": str(uuid.uuid4()),
        "type": STATIC,
        "enabled": True,
        "content": "翻译结果应准确、地道，并符合目标语言用户的阅读习惯。"
    },
    {
        "id": str(uuid.uuid4()),
        "type": STRUCTURAL,
        "enabled": True,
        "content": "重要：你的回答[必须且仅能包含翻译后的内容]，不要添加任何额外的解释、说明或引用标记。"
    }
]

DEFAULT_EXTRACTION_PATTERNS = [
    {
        "id": str(uuid.uuid4()), "name": "Custom String (EN/CN)", "enabled": True,
        "left_delimiter": r'(?:自定义字符串|Custom String)\s*\(\s*"',
        "right_delimiter": r'(?<!\\)"',
        "string_type": "Custom String"
    },
    {
        "id": str(uuid.uuid4()), "name": "Description (EN/CN)", "enabled": True,
        "left_delimiter": r'(?:Description|描述)\s*:\s*"',
        "right_delimiter": r'(?<!\\)"',
        "string_type": "Description"
    },
    {
        "id": str(uuid.uuid4()), "name": "Mode Name (EN/CN)", "enabled": True,
        "left_delimiter": r'(?:Mode Name|模式名称)\s*:\s*"',
        "right_delimiter": r'(?<!\\)"',
        "string_type": "Mode Name"
    }
]

DEFAULT_KEYBINDINGS = {
    'open_code_file': 'Ctrl+O',
    'new_project': 'Ctrl+Shift+N',
    'open_project': 'Ctrl+Shift+O',
    'build_project': 'Ctrl+B',
    'save_current_file': 'Ctrl+S',
    'save_code_file': 'Ctrl+Shift+S',
    'undo': 'Ctrl+Z',
    'redo': 'Ctrl+Y',
    'find_replace': 'Ctrl+Shift+F',
    'copy_original': 'Ctrl+Shift+C',
    'paste_translation': 'Ctrl+Shift+V',
    'ai_translate_selected': 'Ctrl+T',
    'toggle_reviewed': 'Ctrl+R',
    'toggle_ignored': 'Ctrl+I',
    'apply_and_next': 'Ctrl+Return',
    'refresh_sort': 'F5',
}

SUPPORTED_LANGUAGES = {
    "Afrikaans": "af",
    "Amharic": "am",
    "Aragonese": "an",
    "Arabic": "ar",
    "Assamese": "as",
    "Azerbaijani": "az",
    "Belarusian": "be",
    "Bulgarian": "bg",
    "Bengali": "bn",
    "Breton": "br",
    "Catalan": "ca",
    "Czech": "cs",
    "Welsh": "cy",
    "Danish": "da",
    "Deutsch": "de",
    "Dzongkha": "dz",
    "Greek": "el",
    "English": "en",
    "Esperanto": "eo",
    "Español": "es",
    "Estonian": "et",
    "Basque": "eu",
    "Persian": "fa",
    "Finnish": "fi",
    "Français": "fr",
    "Western Frisian": "fy",
    "Irish": "ga",
    "Scottish Gaelic": "gd",
    "Galician": "gl",
    "Gujarati": "gu",
    "Hausa": "ha",
    "Hebrew": "he",
    "Hindi": "hi",
    "Croatian": "hr",
    "Hungarian": "hu",
    "Armenian": "hy",
    "Indonesian": "id",
    "Igbo": "ig",
    "Icelandic": "is",
    "Italiano": "it",
    "日本語": "ja",
    "Georgian": "ka",
    "Kazakh": "kk",
    "Khmer": "km",
    "Kannada": "kn",
    "한국어": "ko",
    "Kurdish": "ku",
    "Kyrgyz": "ky",
    "Limburgish": "li",
    "Lithuanian": "lt",
    "Latvian": "lv",
    "Malagasy": "mg",
    "Macedonian": "mk",
    "Malayalam": "ml",
    "Mongolian": "mn",
    "Marathi": "mr",
    "Malay": "ms",
    "Maltese": "mt",
    "Burmese": "my",
    "Norwegian Bokmål": "nb",
    "Nepali": "ne",
    "Dutch": "nl",
    "Norwegian Nynorsk": "nn",
    "Norwegian": "no",
    "Occitan": "oc",
    "Oriya": "or",
    "Punjabi": "pa",
    "Polish": "pl",
    "Pashto": "ps",
    "Portuguese": "pt",
    "Romanian": "ro",
    "Русский": "ru",
    "Kinyarwanda": "rw",
    "Northern Sami": "se",
    "Serbo-Croatian": "sh",
    "Sinhala": "si",
    "Slovak": "sk",
    "Slovenian": "sl",
    "Albanian": "sq",
    "Serbian": "sr",
    "Swedish": "sv",
    "Tamil": "ta",
    "Telugu": "te",
    "Tajik": "tg",
    "Thai": "th",
    "Turkmen": "tk",
    "Turkish": "tr",
    "Tatar": "tt",
    "Uyghur": "ug",
    "Ukrainian": "uk",
    "Urdu": "ur",
    "Uzbek": "uz",
    "Vietnamese": "vi",
    "Walloon": "wa",
    "Xhosa": "xh",
    "Yiddish": "yi",
    "Yoruba": "yo",
    "简体中文": "zh",
    "繁體中文": "zh_TW",
    "Zulu": "zu",
}