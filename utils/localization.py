# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import json
import os

class LocalizationService:
    def __init__(self, lang_dir='lang', language='en_us'):
        self.lang_dir = lang_dir
        self.languages = {}
        self.current_lang_data = {}
        self.current_lang = None
        self._load_available_languages()
        self.set_language(language)

    def _load_available_languages(self):
        self.available_languages = {
            "en_us": "English",
            "zh_cn": "简体中文"
        }

    def get_available_languages(self):
        return self.available_languages

    def load_language(self, lang_code):
        if lang_code in self.languages:
            return self.languages[lang_code]

        filepath = os.path.join(self.lang_dir, f"{lang_code}.json")
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                self.languages[lang_code] = json.load(f)
                return self.languages[lang_code]
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Warning: Could not load language file for '{lang_code}': {e}")
            return None

    def set_language(self, lang_code):
        data = self.load_language(lang_code)
        if data:
            self.current_lang_data = data
            self.current_lang = lang_code
        else:
            print(f"Warning: Language '{lang_code}' not found. Falling back to 'en_us'.")
            self.current_lang_data = self.load_language('en_us')
            self.current_lang = 'en_us'

    def get(self, key, *args, **kwargs):
        keys = key.split('.')
        try:
            value = self.current_lang_data
            for k in keys:
                value = value[k]

            if args or kwargs:
                return value.format(*args, **kwargs)
            return value
        except KeyError:
            print(f"Warning: Translation key not found: '{key}'")
            return key