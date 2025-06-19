# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import gettext
import os

APP_NAME = "overwatch_localizer"
LOCALE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'locales')




class LanguageManager:
    def __init__(self):
        # 默认的翻译函数，只会返回原文
        self.translator = lambda s: s

    def setup_translation(self, lang_code=None):
        APP_NAME = "overwatch_localizer"
        LOCALE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'locales')

        if lang_code is None:
            lang_code = 'en_US'

        try:
            lang = gettext.translation(APP_NAME, localedir=LOCALE_DIR, languages=[lang_code])
            self.translator = lang.gettext
            print(f"Successfully set up translation for '{lang_code}'")
        except FileNotFoundError:
            print(f"Warning: Translation for '{lang_code}' not found. Falling back to default.")
            self.translator = lambda s: s

    def get_translator(self):
        return self.translator

lang_manager = LanguageManager()

_ = lambda s: lang_manager.get_translator()(s)

def setup_translation(lang_code=None):
    if lang_code is None:
        lang_code = 'en_US'

    try:
        lang = gettext.translation(APP_NAME, localedir=LOCALE_DIR, languages=[lang_code])
        return lang.gettext
    except FileNotFoundError:
        print(f"Warning: Translation for '{lang_code}' not found. Falling back to default.")
        return lambda s: s

def get_available_languages():
    APP_NAME = "overwatch_localizer"
    LOCALE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'locales')
    DEFAULT_LANG = 'en_US'
    languages = []
    if os.path.isdir(LOCALE_DIR):
        for name in os.listdir(LOCALE_DIR):
            if os.path.isdir(os.path.join(LOCALE_DIR, name)):
                mo_path = os.path.join(LOCALE_DIR, name, 'LC_MESSAGES', f'{APP_NAME}.mo')
                if os.path.exists(mo_path):
                    languages.append(name)
    if DEFAULT_LANG not in languages:
        languages.insert(0, DEFAULT_LANG)
    return sorted(languages)