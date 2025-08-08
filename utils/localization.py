# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import gettext
import os
import locale
from PySide6.QtCore import QObject, Signal
from .path_utils import get_resource_path
import logging
logger = logging.getLogger(__name__)

class LanguageManager(QObject):
    language_changed = Signal()

    def __init__(self):
        super().__init__()
        self.translator = lambda s: s
        self.app_name = "lexisync"
        self.locale_dir = get_resource_path('locales')
        self.supported_languages = self._get_supported_languages()
        self.default_lang = 'en_US'
        self.current_lang_code = self.default_lang

    def _get_supported_languages(self):
        languages = []
        if os.path.isdir(self.locale_dir):
            for name in os.listdir(self.locale_dir):
                if os.path.isdir(os.path.join(self.locale_dir, name)):
                    mo_path = os.path.join(self.locale_dir, name, 'LC_MESSAGES', f'{self.app_name}.mo')
                    if os.path.exists(mo_path):
                        languages.append(name)
        return languages

    def get_system_language(self):
        try:
            system_lang, encoding = locale.getdefaultlocale()
            if system_lang:
                return system_lang
        except Exception:
            pass

        env_lang = os.getenv('LANG')
        if env_lang:
            return env_lang.split('.')[0]

        return None

    def get_best_match_language(self):
        system_lang = self.get_system_language()
        if not system_lang:
            return self.default_lang

        system_lang_lower = system_lang.lower().replace('-', '_')

        if system_lang_lower in self.supported_languages:
            return system_lang

        base_lang = system_lang_lower.split('_')[0]
        for lang in self.supported_languages:
            if lang.lower().startswith(base_lang):
                return lang

        return self.default_lang

    def setup_translation(self, lang_code=None):
        if lang_code is None:
            lang_code = self.get_best_match_language()
        self.current_lang_code = lang_code

        try:
            lang = gettext.translation(self.app_name, localedir=self.locale_dir, languages=[lang_code], fallback=True)
            lang.install()
            self.translator = lang.gettext
            logger.info(f"Successfully set up translation for '{lang_code}'")
        except Exception as e:
            logger.warning(f"Warning: Translation for '{lang_code}' not found or failed to load: {e}. Falling back to default.")
            self.translator = lambda s: s

    def get_translator(self):
        return self.translator

    def get_current_language(self):
        return self.current_lang_code

    def get_available_languages(self):
        available = list(self.supported_languages)
        if self.default_lang not in available:
            available.insert(0, self.default_lang)
        return sorted(available)

    def get_language_name(self, lang_code):
        full_name_map = {
            'en_US': 'English',
            'zh_CN': '简体中文',
            'zh_TW': '繁體中文',
            'ja_JP': '日本語',
            'ko_KR': '한국어',
            'fr_FR': 'Français',
            'de_DE': 'Deutsch',
            'ru_RU': 'Русский',
            'es_ES': 'Español (España)',
            'es_MX': 'Español (Latinoamérica)',
            'pt_BR': 'Português (Brasil)',
            'pt_PT': 'Português (Portugal)',
            'it_IT': 'Italiano',
            'pl_PL': 'Polski',
            'tr_TR': 'Türkçe',
            'ar_SA': 'العربية',
        }
        return full_name_map.get(lang_code, lang_code)

    def get_available_languages_map(self):
        return {code: self.get_language_name(code) for code in self.get_available_languages()}

lang_manager = LanguageManager()
_ = lambda s: lang_manager.get_translator()(s)