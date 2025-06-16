import json
import os

class LocalizationService:
    def __init__(self, language='en_us'):
        self.language = language
        self.translations = {}
        self.load_language(self.language)

    def load_language(self, language):
        self.language = language
        lang_file = os.path.join('lang', f'{language}.json')
        try:
            with open(lang_file, 'r', encoding='utf-8') as f:
                self.translations = json.load(f)
        except FileNotFoundError:
            print(f"Language file not found: {lang_file}. Falling back to empty dict.")
            self.translations = {}
        except json.JSONDecodeError:
            print(f"Error decoding language file: {lang_file}.")
            self.translations = {}

    def get(self, key, *args):
        translation = self.translations.get(key, key)
        if args:
            try:
                return translation.format(*args)
            except (IndexError, KeyError):
                return translation
        return translation

    def __call__(self, key, *args):
        return self.get(key, *args)