# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import os
import json
import pandas as pd
import numpy as np
from utils.constants import EXPANSION_DATA_DIR
from utils.text_utils  import get_linguistic_length
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
        self.df = None
        self._load_and_process_data()

    def _load_and_process_data(self):
        data_dir_path = get_resource_path(EXPANSION_DATA_DIR)
        if not os.path.isdir(data_dir_path):
            print(f"Warning: Expansion data directory '{data_dir_path}' not found.")
            return
        all_data = []
        for filename in os.listdir(data_dir_path):
            if filename.endswith(".json"):
                filepath = os.path.join(data_dir_path, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    models = data.get("models", {})
                    for lang_pair, model_data in models.items():
                        for bucket in model_data.get("buckets", []):
                            min_len, max_len = bucket.get("range", [0, 0])
                            for density, stats in bucket.get("stats", {}).items():
                                all_data.append({
                                    "lang_pair": lang_pair,
                                    "density": density,
                                    "min_len": min_len,
                                    "max_len": max_len,
                                    "mean": stats.get("mean"),
                                    "std": stats.get("std"),
                                    "median": stats.get("median"),
                                    "count": stats.get("count"),
                                })

        if not all_data:
            return

        temp_df = pd.DataFrame(all_data)
        def weighted_agg(group):
            weights = group['count']
            if weights.sum() == 0:
                return pd.Series({
                    'mean': 0, 'std': 0, 'median': 0, 'count': 0
                })
            return pd.Series({
                'mean': np.average(group['mean'], weights=weights),
                'std': np.average(group['std'], weights=weights),  # 简化为加权平均
                'median': np.average(group['median'], weights=weights),  # 简化为加权平均
                'count': weights.sum()
            })

        cols_to_agg = ['mean', 'std', 'median', 'count']
        self.df = temp_df.groupby(['lang_pair', 'density', 'min_len', 'max_len'])[cols_to_agg].apply(weighted_agg).reset_index()
        print(f"Expansion ratio service loaded and processed {len(self.df)} statistical entries.")

    def get_expected_ratio(self, source_lang, target_lang, original_text, placeholder_density="none", visited=None):
        if self.df is None:
            return None
        if visited is None:
            visited = set()

        lang_pair = f"{source_lang}-{target_lang}"
        if lang_pair in visited:
            return None
        visited.add(lang_pair)
        length = get_linguistic_length(original_text)
        query = self.df[
            (self.df['lang_pair'] == lang_pair) &
            (self.df['density'] == placeholder_density) &
            (self.df['min_len'] <= length) &
            (self.df['max_len'] > length)
            ]
        if not query.empty:
            return query.iloc[0]['median']
        reverse_lang_pair = f"{target_lang}-{source_lang}"
        reverse_query = self.df[
            (self.df['lang_pair'] == reverse_lang_pair) &
            (self.df['density'] == placeholder_density) &
            (self.df['min_len'] <= length) &
            (self.df['max_len'] > length)
            ]
        if not reverse_query.empty:
            reverse_ratio = reverse_query.iloc[0]['median']
            return 1 / reverse_ratio if reverse_ratio != 0 else None
        if source_lang != 'en' and target_lang != 'en':
            ratio_source_to_en = self.get_expected_ratio(source_lang, 'en', original_text, placeholder_density, visited)
            if ratio_source_to_en:
                estimated_en_len = length * ratio_source_to_en
                en_text_placeholder = "a" * int(estimated_en_len)
                ratio_en_to_target = self.get_expected_ratio('en', target_lang, en_text_placeholder,
                                                             placeholder_density, visited)
                if ratio_en_to_target:
                    return ratio_source_to_en * ratio_en_to_target

        return None