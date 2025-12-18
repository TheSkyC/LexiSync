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
            f"Role: You are a Senior Localization Lead. Analyze the following {len(samples)} sample texts from a software/game project to create a Style Guide.\n"
            f"Source Language: {source_lang}\n"
            f"Target Language: {target_lang}\n\n"
            f"Samples:\n{sample_text}\n\n"
            "Constraints for the Guide:\n"
            "1. DO NOT mention technical formatting (placeholders, line breaks, HTML, variables). These are strictly handled by a separate system logic.\n"
            "2. Focus PURELY on linguistic style, cultural nuance, and terminology strategy.\n\n"
            "Task: Generate a dense, high-impact 'Translation Style Guide' (max 150 words) covering:\n"
            "- **Vibe & Domain**: The specific sub-genre (e.g., 'Cyberpunk UI', 'Corporate SaaS', 'High-Fantasy') and emotional tone.\n"
            "- **Lexical Choice**: Rules for specific nouns/verbs (e.g., 'Use intuitive verbs over formal nouns', 'Keep proper names in English').\n"
            "- **Syntactical Constraints**: Instructions on sentence length (e.g., 'Prioritize brevity for buttons', 'Avoid passive voice').\n"
            "- **Addressing the User**: How to refer to the user (e.g., 'You/您' vs 'Player/玩家' vs impersonal).\n\n"
            "Output ONLY the Style Guide content as a bulleted list."
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