# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import uuid
def _(message): return message


APP_NAMESPACE_UUID = uuid.UUID('c2e02333-2f1d-48ba-bc8d-90d49da373af')
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
    "printf": {
        "enabled": True,
        "level": "error",
        "label": _("Printf Format (%s, %d)"),
        "modes": {
            "strict": {
                "name": _("Strict"),
                "description": _("Format specifiers must match exactly (e.g. %s != %1$s).")
            },
            "loose": {
                "name": _("Loose"),
                "description": _("Allows positional arguments and width changes (e.g. %s == %1$s).")
            }
        },
        "default_mode": "loose"
    },
    "python_brace": {"enabled": True, "level": "error", "label": _("Python Brace ({}, {name})")},
    "html_tags": {"enabled": True, "level": "error", "label": _("HTML/XML Tags")},
    "url_email": {"enabled": True, "level": "warning", "label": _("URL & Email")},

    # --- 内容一致性 ---
    "numbers": {
        "enabled": True,
        "level": "error",
        "label": _("Numbers Consistency"),
        "modes": {
            "strict": {
                "name": _("Strict"),
                "description": _("Arabic numerals must match exactly (e.g. '1' must be '1').")
            },
            "loose": {
                "name": _("Loose"),
                "description": _("Allows numerals to be translated into words (e.g. '1' -> 'One', '一', 'First').")
            }
        },
        "default_mode": "loose"
    },
    "glossary": {"enabled": True, "level": "warning", "label": _("Glossary Terms")},
    "fuzzy": {"enabled": True, "level": "warning", "label": _("Fuzzy State")},

    # --- 格式与标点 ---
    "punctuation": {"enabled": True, "level": "warning", "label": _("Ending Punctuation")},
    "brackets": {"enabled": True, "level": "warning", "label": _("Paired Brackets () [] {}")},
    "whitespace": {"enabled": True, "level": "warning", "label": _("Leading/Trailing Whitespace")},
    "double_space": {"enabled": True, "level": "warning", "label": _("Double Spaces")},
    "capitalization": {"enabled": False, "level": "warning", "label": _("Initial Capitalization")},
    "repeated_word": {"enabled": True, "level": "info", "label": _("Repeated Words")},
    "newline_count": {"enabled": True, "level": "warning", "label": _("Newline Count Mismatch")},
    "quotes": {
        "enabled": True,
        "level": "info",
        "label": _("Mismatched Quotes"),
        "modes": {
            "strict": {
                "name": _("Strict"),
                "description": _("Single and double quotes must match their types exactly.")
            },
            "flexible": {
                "name": _("Flexible"),
                "description": _("Allows converting single quotes to double quotes (e.g., '...' -> “...”) and vice versa.")
            }
        },
        "default_mode": "flexible"
    },
    "accelerator": {"enabled": True, "level": "error", "label": _("Accelerator Mismatch")},
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
        "content": "目标语言：[Target Language]"
    },
    {
        "id": str(uuid.uuid4()),
        "type": "Dynamic Instruction",
        "enabled": True,
        "content": "参考术语表：\n[Glossary]"
    },
    {
        "id": str(uuid.uuid4()),
        "type": "Dynamic Instruction",
        "enabled": True,
        "content": "检测到的错误：\n[Error List]"
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
        "content": "当前有问题的译文：\n<translate_input>\n[Current Translation]\n</translate_input>"
    },
    {
        "id": str(uuid.uuid4()),
        "type": "Static Instruction",
        "enabled": True,
        "content": "重要：必须严格保留原文中的所有格式，包括：\n- XML/HTML 标签 (例如 <br>, <b>, <![CDATA[...]]>)\n- 转义字符 (\\n, \\t, \\r, \\\")\n- 占位符 (%s, {var})\n不要移除或解释包裹内容的标签。"
    },
    {
        "id": str(uuid.uuid4()),
        "type": "Static Instruction",
        "enabled": True,
        "content": "请根据原文和错误列表修复 <translate_input> 中的内容。仅输出修复后的译文，不要包含 <translate_input> 标签，不要包含任何解释。"
    }
]

DEFAULT_PROMPT_STRUCTURE = [
    {
        "id": str(uuid.uuid4()),
        "type": STRUCTURAL,
        "enabled": True,
        "content": "You are a professional localization expert. Your task is to translate the text enclosed within <translate_input> tags from [Source Language] to [Target Language]."
    },
    {
        "id": str(uuid.uuid4()),
        "type": STATIC,
        "enabled": True,
        "content": "CRITICAL: Preserve ALL placeholders exactly as-is:\n- Format specifiers: %s, %d, %f, %.2f, etc.\n- Named placeholders: {variable}, %{count}, {{name}}\n- Template syntax: ${var}, [[key]], <placeholder>\nThe quantity, order, and names must match the original perfectly."
    },
    {
        "id": str(uuid.uuid4()),
        "type": STATIC,
        "enabled": True,
        "content": "CRITICAL: Preserve ALL formatting exactly:\n- Escape sequences: \\n, \\t, \\r, \\\"\n- HTML tags: <br>, <b>, <i>, <span>, <a>, etc.\n- Do NOT convert between \\n and <br>\n- Match the original format character-by-character"
    },
    {
        "id": str(uuid.uuid4()),
        "type": STATIC,
        "enabled": True,
        "content": "Do not add or remove any characters, symbols, or spaces not present in the original text, unless required by the target language's punctuation conventions."
    },
    {
        "id": str(uuid.uuid4()),
        "type": DYNAMIC,
        "enabled": True,
        "content": "### Project Instructions\n[Global Instructions]\n[Project Instructions]"
    },
    {
        "id": str(uuid.uuid4()),
        "type": DYNAMIC,
        "enabled": True,
        "content": "### Translation Style Guide\n[Style Guide]"
    },
    {
        "id": str(uuid.uuid4()),
        "type": DYNAMIC,
        "enabled": True,
        "content": "### Terminology Glossary\n[Glossary]"
    },
    {
        "id": str(uuid.uuid4()),
        "type": DYNAMIC,
        "enabled": True,
        "content": "### Reference Context\n[Semantic Context]\n[Untranslated Context]\n[Translated Context]"
    },
    {
        "id": str(uuid.uuid4()),
        "type": STATIC,
        "enabled": True,
        "content": "Output ONLY the final translation. No explanations, no notes."
    }
]

COT_INJECTION_PROMPT = """
================================================================================
CRITICAL INSTRUCTION: CHAIN OF THOUGHT ENFORCEMENT
================================================================================
Do NOT output the translation immediately. You must engage in a deep analysis first.

1. **Analyze**: Identify the core meaning, tone, placeholders (%s, {var}), and formatting tags.
2. **Consult**: Check the Glossary and Context provided above. Ensure consistency.
3. **Reason**: Explain your translation choices for ambiguous terms or complex structures.

**OUTPUT FORMAT (MANDATORY)**:
You must strictly follow this XML-style format. Do not output anything else outside these tags.

<thinking>
[Write your step-by-step analysis, glossary checks, and reasoning here]
</thinking>
<translation>
[Write ONLY the final translation result here, preserving all formatting exactly]
</translation>
"""

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

AI_PROVIDER_PRESETS = {
    "DeepSeek": {
        "api_base_url": "https://api.deepseek.com",
        "model_name": "deepseek-chat",
        "concurrency": 8
    },
    "SiliconFlow": {
        "api_base_url": "https://api.siliconflow.cn/v1",
        "model_name": "deepseek-ai/DeepSeek-V3",
        "concurrency": 5
    },
    "OpenAI": {
        "api_base_url": "https://api.openai.com/v1",
        "model_name": "gpt-4o",
        "concurrency": 5
    },
    "火山引擎": {
        "api_base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "model_name": "ep-",
        "concurrency": 16
    },
    "Moonshot (Kimi)": {
        "api_base_url": "https://api.moonshot.cn/v1",
        "model_name": "moonshot-v1-8k",
        "concurrency": 3
    },
    "Ollama (Local)": {
        "api_base_url": "http://localhost:11434/v1",
        "model_name": "qwen2.5:7b",
        "concurrency": 1
    },
    "LM Studio (Local)": {
        "api_base_url": "http://localhost:1234/v1",
        "model_name": "local-model",
        "concurrency": 1
    },
    "vLLM (Local)": {
        "api_base_url": "http://localhost:8000/v1",
        "model_name": "default",
        "concurrency": 4
    },
    "OpenRouter": {
        "api_base_url": "https://openrouter.ai/api/v1",
        "model_name": "deepseek/deepseek-chat",
        "concurrency": 5
    },
    "Groq": {
        "api_base_url": "https://api.groq.com/openai/v1",
        "model_name": "llama3-70b-8192",
        "concurrency": 5
    },
    "Zhipu AI": {
        "api_base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model_name": "glm-4-flash",
        "concurrency": 5
    },
    "AiHubMix": {
        "api_base_url": "https://aihubmix.com/v1",
        "model_name": "gpt-4o",
        "concurrency": 5
    },
    "Custom": {
        "api_base_url": "",
        "model_name": "",
        "concurrency": 1
    }
}