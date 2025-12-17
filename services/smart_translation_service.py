# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import re
import random
from collections import Counter
import logging

logger = logging.getLogger(__name__)


class SmartTranslationService:
    @staticmethod
    def intelligent_sampling(translatable_objects, sample_size=100):
        """
        Implements Stratified + Lexical Diversity Greedy Sampling.
        """
        candidates = []
        seen_hashes = set()

        # 1. Preprocessing & Filtering
        for ts in translatable_objects:
            text = ts.original_semantic.strip()
            if not text or text.isdigit() or len(text) < 2:
                continue
            if text in seen_hashes:
                continue
            seen_hashes.add(text)
            tokens = set(re.findall(r'\w+', text.lower()))
            if not tokens:
                continue

            candidates.append({
                'obj': ts,
                'text': text,
                'tokens': tokens,
                'length': len(tokens)  # Word count
            })

        if not candidates:
            return []

        # 2. Stratification (Bucketing)
        buckets = {
            'long': [c for c in candidates if c['length'] > 15],
            'medium': [c for c in candidates if 5 <= c['length'] <= 15],
            'short': [c for c in candidates if c['length'] < 5]
        }
        quotas = {
            'long': int(sample_size * 0.5),
            'medium': int(sample_size * 0.3),
            'short': int(sample_size * 0.2)
        }

        final_samples = []
        global_seen_tokens = set()

        # 3. Greedy Sampling
        for bucket_name in ['long', 'medium', 'short']:
            pool = buckets[bucket_name]
            quota = quotas[bucket_name]

            if len(pool) <= quota:
                for c in pool:
                    final_samples.append(c['obj'])
                    global_seen_tokens.update(c['tokens'])
                continue

            for _ in range(quota):
                if not pool: break

                best_candidate = None
                best_score = -1.0

                for cand in pool:
                    new_tokens = len(cand['tokens'] - global_seen_tokens)
                    score = new_tokens

                    if score > best_score:
                        best_score = score
                        best_candidate = cand

                if best_candidate:
                    final_samples.append(best_candidate['obj'])
                    global_seen_tokens.update(best_candidate['tokens'])
                    pool.remove(best_candidate)
                else:
                    fallback = pool.pop(0)
                    final_samples.append(fallback['obj'])
        return final_samples

    @staticmethod
    def generate_style_guide_prompt(samples, source_lang, target_lang):
        sample_text = "\n".join([f"- {ts.original_semantic}" for ts in samples])
        return (
            f"You are a localization expert. Analyze the following {len(samples)} sample texts from a software/game project.\n"
            f"Source Language: {source_lang}\n"
            f"Target Language: {target_lang}\n\n"
            f"Samples:\n{sample_text}\n\n"
            "Task: Generate a concise 'Translation Style Guide' (max 150 words). \n"
            "Cover: 1. Tone (Formal/Casual) 2. Target Audience 3. Formatting Rules 4. Specific grammatical instructions for the target language.\n"
            "Output ONLY the Style Guide content."
        )

    @staticmethod
    def extract_terms_prompt(samples):
        sample_text = "\n".join([f"- {ts.original_semantic}" for ts in samples])
        return (
            f"Analyze the following text samples:\n{sample_text}\n\n"
            "Task: Extract 15-20 key terms, proper nouns, or UI elements that require consistent translation. \n"
            "Exclude common stop words (the, a, is, etc.). \n"
            "Return ONLY a Python list of strings, e.g., [\"Term1\", \"Term2\"]"
        )

    @staticmethod
    def translate_terms_prompt(terms_list_str, target_lang):
        return (
            f"Translate the following terms into {target_lang}.\n"
            f"Terms: {terms_list_str}\n\n"
            "Output a Markdown table with two columns: 'Source' and 'Target'. \n"
            "Do not add any other text."
        )