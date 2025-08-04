# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import logging
import os
import json
from utils.path_utils import get_resource_path

class ExpansionRatioService:
    _instance = None

    @staticmethod
    def initialize():
        if ExpansionRatioService._instance is None:
            ExpansionRatioService._instance = ExpansionRatioService()

    @staticmethod
    def get_instance():
        if ExpansionRatioService._instance is None:
            ExpansionRatioService.initialize()
        return ExpansionRatioService._instance

    def __init__(self):
        self.ratios = {}
        self._load_data()

    def _load_data(self):
        data_file_path = get_resource_path(os.path.join('expansion_data', 'Helsinki-NLP_opus-100.json'))
        if not os.path.exists(data_file_path):
            logging.warning(
                f"Warning: Expansion ratio data file not found at '{data_file_path}'. Service will use default values.")
            return
        try:
            with open(data_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.ratios = data.get("ratios", {})
            logging.info(f"Expansion ratio service loaded {len(self.ratios)} ratio entries.")
        except Exception as e:
            logging.info(f"Error loading expansion ratio data: {e}")

    def get_expected_ratio(self, source_lang, target_lang, original_text=None, placeholder_density=None, visited=None):
        if not self.ratios:
            return 1.0
        if visited is None:
            visited = set()
        query_source_lang = 'zh' if source_lang == 'zh_TW' else source_lang
        query_target_lang = 'zh' if target_lang == 'zh_TW' else target_lang
        if query_source_lang == query_target_lang:
            return 1.0
        lang_pair = f"{query_source_lang}-{query_target_lang}"
        if lang_pair in visited:
            return None
        visited.add(lang_pair)
        if lang_pair in self.ratios:
            return self.ratios[lang_pair]
        reverse_lang_pair = f"{query_target_lang}-{query_source_lang}"
        if reverse_lang_pair in self.ratios:
            reverse_ratio = self.ratios[reverse_lang_pair]
            return 1.0 / reverse_ratio if reverse_ratio != 0 else 1.0
        if query_source_lang != 'en' and query_target_lang != 'en':
            ratio_source_to_en = self.get_expected_ratio(query_source_lang, 'en', visited=visited)
            ratio_en_to_target = self.get_expected_ratio('en', query_target_lang, visited=visited)

            if ratio_source_to_en is not None and ratio_en_to_target is not None:
                return ratio_source_to_en * ratio_en_to_target
        return None