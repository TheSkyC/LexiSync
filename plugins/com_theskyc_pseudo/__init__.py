# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from PySide6.QtGui import QAction
from plugins.plugin_base import PluginBase
from plugins.com_theskyc_pseudo.settings_dialog import SettingsDialog
from plugins.com_theskyc_pseudo.preview_dialog import PreviewDialog
import re
import logging

class EnhancedPseudoLocalizationPlugin(PluginBase):
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)

    def get_default_config(self) -> dict:
        return {
            'auto_pseudo_on_apply': False,
            'mode': 'comprehensive',
            'length_expansion': True,
            'expansion_factor': 1.1,
            'unicode_replacement': True,
            'preserve_placeholders': True,
            'preserve_html': True,
            'preserve_urls': True,
        }

    def plugin_id(self) -> str:
        return "com_theskyc_pseudo"

    def name(self) -> str:
        return self._("Pseudo-Localization")

    def description(self) -> str:
        return self._("An advanced pseudo-localization plugin with multiple modes and extensive customization.")

    def author(self) -> str:
        return "TheSkyC"

    def compatible_app_version(self) -> str:
        return "1.2"

    def add_menu_items(self) -> list[tuple[str, callable]]:
        pseudo_menu = self.main_window.plugin_menu.addMenu(self.name())

        apply_action = pseudo_menu.addAction(self._("Apply to Selected"))
        apply_action.triggered.connect(self.apply_to_selected)

        copy_original_action = pseudo_menu.addAction(self._("Copy Original to Translation"))
        copy_original_action.triggered.connect(self.copy_original_to_translation)

        preview_action = pseudo_menu.addAction(self._("Preview on Selected"))
        preview_action.triggered.connect(self.preview_selected)

        clear_action = pseudo_menu.addAction(self._("Clear Translation for Selected"))
        clear_action.triggered.connect(self.clear_selected_translation)

        pseudo_menu.addSeparator()

        settings_action = pseudo_menu.addAction(self._("Settings..."))
        settings_action.triggered.connect(self.show_settings_dialog)

        return []

    def apply_to_selected(self):
        selected_objs = self.main_window._get_selected_ts_objects_from_sheet()
        if not selected_objs:
            self.main_window.update_statusbar(self._("No items selected."))
            return

        for ts_obj in selected_objs:
            if ts_obj.original_semantic and ts_obj.original_semantic.strip():
                processed_text = self._do_pseudo_localization(ts_obj.original_semantic)
                self.main_window._apply_translation_to_model(ts_obj, processed_text, source="plugin_pseudo_manual")
        self.main_window.update_statusbar(
            self._("Applied pseudo-localization to {count} items.").format(count=len(selected_objs))
        )

    def copy_original_to_translation(self):
        selected_objs = self.main_window._get_selected_ts_objects_from_sheet()
        if not selected_objs:
            self.main_window.update_statusbar(self._("No items selected."))
            return

        for ts_obj in selected_objs:
            self.main_window._apply_translation_to_model(
                ts_obj,
                ts_obj.original_semantic,
                source="plugin_copy_original"
            )

        self.main_window.update_statusbar(
            self._("Copied original text to translation for {count} items.").format(count=len(selected_objs))
        )

    def preview_selected(self):
        selected_objs = self.main_window._get_selected_ts_objects_from_sheet()
        if not selected_objs or len(selected_objs) > 1:
            self.main_window.update_statusbar(self._("Please select a single item to preview."))
            return

        ts_obj = selected_objs[0]
        original = ts_obj.original_semantic
        preview = self._do_pseudo_localization(original)

        dialog = PreviewDialog(self.main_window, original, preview)
        dialog.exec()

    def clear_selected_translation(self):
        selected_objs = self.main_window._get_selected_ts_objects_from_sheet()
        if not selected_objs:
            self.main_window.update_statusbar(self._("No items selected."))
            return

        for ts_obj in selected_objs:
            self.main_window._apply_translation_to_model(ts_obj, "", source="plugin_clear")

        self.main_window.update_statusbar(
            self._("Cleared translation for {count} items.").format(count=len(selected_objs))
        )

    def show_settings_dialog(self):
        dialog = SettingsDialog(self.main_window, self.config)
        if dialog.exec():
            self.config = dialog.get_settings()
            self.save_config()
            self.main_window.update_statusbar(self._("Pseudo-localization settings updated."))

    def process_string_for_save(self, text: str, ts_object, column: str) -> str:
        # --- 这是核心修改：钩子现在会检查开关状态 ---
        if not self.config.get('auto_pseudo_on_apply', False):
            # 如果自动伪本地化功能被关闭，钩子直接返回原文，什么都不做
            return text

        # 如果功能开启，则执行伪本地化
        return self._do_pseudo_localization(text)
        # --- 结束修改 ---

    def _do_pseudo_localization(self, text: str) -> str:
        """
        The actual processing logic, extracted into a separate method.
        This can be called directly by menu actions or by the hook.
        """
        if not text or not text.strip():
            return text

        try:
            patterns = []
            if self.config['preserve_placeholders']:
                patterns.append(r'\{[^{}]+\}')
            if self.config['preserve_html']:
                patterns.append(r'<[^>]+>|&[a-zA-Z]+;|&#\d+;')
            if self.config['preserve_urls']:
                patterns.append(r'https?://[^\s]+|www\.[^\s]+|[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')

            if not patterns:
                processed_text = self._process_normal_text(text)
            else:
                combined_pattern = re.compile('|'.join(patterns))
                result_parts = []
                last_end = 0
                for match in combined_pattern.finditer(text):
                    start, end = match.span()
                    normal_text_part = text[last_end:start]
                    result_parts.append(self._process_normal_text(normal_text_part))
                    preserved_part = text[start:end]
                    result_parts.append(preserved_part)
                    last_end = end
                remaining_text = text[last_end:]
                result_parts.append(self._process_normal_text(remaining_text))
                processed_text = "".join(result_parts)

            return self._add_brackets(processed_text)
        except Exception as e:
            self.logger.error(f"Pseudo-localization failed for text '{text[:30]}...': {e}", exc_info=True)
            return text

    def _process_normal_text(self, text: str) -> str:
        if not text:
            return ""

        if self.config['unicode_replacement']:
            text = self._apply_unicode_replacement(text)

        if self.config['length_expansion']:
            text = self._apply_length_expansion(text)

        return text

    def _apply_unicode_replacement(self, text: str) -> str:
        mode = self.config['mode']
        if mode == 'basic':
            char_map = {'a': 'ä', 'e': 'ë', 'i': 'ï', 'o': 'ö', 'u': 'ü', 'y': 'ÿ', 'A': 'Ä', 'E': 'Ë', 'I': 'Ï',
                        'O': 'Ö', 'U': 'Ü', 'Y': 'Ÿ'}
        elif mode == 'comprehensive':
            char_map = {'a': 'ä', 'b': 'ḅ', 'c': 'ç', 'd': 'ḍ', 'e': 'ë', 'f': 'ḟ', 'g': 'ğ', 'h': 'ḥ', 'i': 'ï',
                        'j': 'ĵ', 'k': 'ķ', 'l': 'ł', 'm': 'ṁ', 'n': 'ñ', 'o': 'ö', 'p': 'ṗ', 'q': 'ǫ', 'r': 'ř',
                        's': 'ş', 't': 'ţ', 'u': 'ü', 'v': 'ṿ', 'w': 'ẅ', 'x': 'ẋ', 'y': 'ÿ', 'z': 'ẓ', 'A': 'Ä',
                        'B': 'Ḅ', 'C': 'Ç', 'D': 'Ḍ', 'E': 'Ë', 'F': 'Ḟ', 'G': 'Ğ', 'H': 'Ḥ', 'I': 'Ï', 'J': 'Ĵ',
                        'K': 'Ķ', 'L': 'Ł', 'M': 'Ṁ', 'N': 'Ñ', 'O': 'Ö', 'P': 'Ṗ', 'Q': 'Ǫ', 'R': 'Ř', 'S': 'Ş',
                        'T': 'Ţ', 'U': 'Ü', 'V': 'Ṿ', 'W': 'Ẅ', 'X': 'Ẋ', 'Y': 'Ÿ', 'Z': 'Ẓ'}
        else:
            char_map = {'a': 'ä́', 'b': 'ḅ̌', 'c': 'ç̂', 'd': 'ḍ̃', 'e': 'ë́', 'f': 'ḟ̌', 'g': 'ğ̂', 'h': 'ḥ̃',
                        'i': 'ḯ', 'j': 'ĵ̌', 'k': 'ķ̂', 'l': 'ł̃', 'm': 'ṁ́', 'n': 'ñ̌', 'o': 'ö̂', 'p': 'ṗ̃',
                        'q': 'ǫ́', 'r': 'ř̌', 's': 'ş̂', 't': 'ţ̃', 'u': 'ǘ', 'v': 'ṿ̌', 'w': 'ẅ̂', 'x': 'ẋ̃',
                        'y': 'ÿ́', 'z': 'ẓ̌', 'A': 'Ä́', 'B': 'Ḅ̌', 'C': 'Ç̂', 'D': 'Ḍ̃', 'E': 'Ë́', 'F': 'Ḟ̌',
                        'G': 'Ğ̂', 'H': 'Ḥ̃', 'I': 'Ḯ', 'J': 'Ĵ̌', 'K': 'Ķ̂', 'L': 'Ł̃', 'M': 'Ṁ́', 'N': 'Ñ̌',
                        'O': 'Ö̂', 'P': 'Ṗ̃', 'Q': 'Ǫ́', 'R': 'Ř̌', 'S': 'Ş̂', 'T': 'Ţ̃', 'U': 'Ǘ', 'V': 'Ṿ̌',
                        'W': 'Ẅ̂', 'X': 'Ẋ̃', 'Y': 'Ÿ́', 'Z': 'Ẓ̌'}
        return "".join(char_map.get(char, char) for char in text)

    def _apply_length_expansion(self, text: str) -> str:
        expansion_factor = self.config['expansion_factor']
        target_length = int(len(text) * expansion_factor)
        if target_length <= len(text):
            return text

        padding = " " * (target_length - len(text))
        return text + padding

    _add_brackets = lambda self, text: f"[{text}]"