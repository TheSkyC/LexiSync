import uuid

APP_NAMESPACE_UUID = uuid.UUID('c2e02333-2f1d-48ba-bc8d-90d49da373af')
APP_VERSION = "0.7"

CONFIG_FILE = "localization_tool_config.json"
PROJECT_FILE_EXTENSION = ".owproj"
TM_FILE_EXCEL = "ow_translator_tm.xlsx"
TB_FILE_EXCEL = "ow_translator_tb.xlsx"

MAX_UNDO_HISTORY = 50

DEFAULT_AI_PROMPT_TEMPLATE = (
    "You are a professional video game translator specializing in 'Overwatch' custom game modes. Your task is to translate UI text and descriptions into [Target Language].\n"
    "Follow these instructions strictly:\n"
    "1.  Translate the following user-provided text into [Target Language].\n"
    "2.  Adhere to these project-specific translation guidelines:\n"
    "    [Custom Translate] (Ignore if not provided by the user)\n"
    "3.  If the source language is the same as the target language, do not make any changes.\n"
    "4.  Preserve all symbols, including '\\n', '\\r', all whitespace, '()', '[]', and '.,?!/\\', etc. Do not translate them. Do not add symbols that were not in the original text.\n"
    "5.  Refer to the following translated context for terminology and style consistency (if relevant):\n"
    "    [Translated Context] (Ignore if not provided by the user)\n"
    "6.  Refer to the following untranslated original context to understand the flow of conversation or description:\n"
    "    [Original Untranslated Context] (Ignore if not provided by the user)\n"
    "7.  You MUST use the following mandatory term translations if they appear in the text:\n"
    "    [Termbase Mappings] (Ignore if not provided)\n"
    "8.  The translation should be accurate, concise, and match the in-game language style of 'Overwatch'.\n"
    "9.  **IMPORTANT: Your response [must only contain the translated text content]. Do not add any extra explanations or notes.**"
)

DEFAULT_API_URL = "https://api.deepseek.com/chat/completions"

DEFAULT_HOTKEYS = {
    "apply_and_next": "<Control-Return>",
    "ai_translate_selected": "<Control-Alt-T>",
    "toggle_reviewed": "<Control-R>",
    "toggle_ignored": "<Control-I>",
    "copy_original": "<Control-Shift-C>",
    "paste_translation": "<Control-Shift-V>",
    "save_project": "<Control-S>",
    "open_project": "<Control-O>",
    "find_replace": "<Control-F>",
}