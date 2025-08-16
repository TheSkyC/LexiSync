# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from plugins.plugin_base import PluginBase
import logging
from typing import Dict, List, Optional, Tuple

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    import numpy as np

    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

class TMEnhancerPlugin(PluginBase):
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.vectorizer = None
        self.tfidf_matrix = None
        self.tm_originals = []
        self.tm_data = {}
        self.is_ready = SKLEARN_AVAILABLE
        if not self.is_ready:
            self.logger.warning("scikit-learn or numpy not found. TM Enhancer plugin will be disabled.")

    def plugin_id(self) -> str:
        return "com_theskyc_tm_enhancer"

    def name(self) -> str:
        return self._("TM Enhancer (TF-IDF)")

    def description(self) -> str:
        if SKLEARN_AVAILABLE:
            return self._("Enhances TM matching performance using TF-IDF")
        else:
            return self._(
                "Enhances TM matching performance using TF-IDF. Requires 'scikit-learn' and 'numpy'. Please run: pip install scikit-learn numpy")

    def version(self) -> str:
        return "1.1.0"

    def author(self) -> str:
        return "TheSkyC"

    def url(self) -> str:
        return "https://github.com/TheSkyC/lexisync/tree/master/plugins/com_theskyc_tm_enhancer"

    def compatible_app_version(self) -> str:
        return "1.2"

    def external_dependencies(self) -> Dict[str, str]:
        return {
            'scikit-learn': '>=1.0',
            'numpy': '',
        }

    def query_tm_suggestions(self, original_text: str) -> Optional[List[Tuple[float, str, str]]]:
        if not self.is_ready or not self.main_window:
            return None

        try:
            source_lang = self.main_window.source_language
            target_lang = self.main_window.current_target_language if self.main_window.is_project_mode else self.main_window.target_language

            candidates = self.main_window.tm_service.get_fuzzy_matches(
                source_text=original_text,
                source_lang=source_lang,
                target_lang=target_lang,
                limit=50,
                threshold=0.5
            )

            if not candidates or len(candidates) < 1:
                return None

            candidate_sources = [c['source_text'] for c in candidates]
            all_texts_for_model = [original_text] + candidate_sources

            vectorizer = TfidfVectorizer(analyzer='char_wb', ngram_range=(2, 4))
            tfidf_matrix = vectorizer.fit_transform(all_texts_for_model)

            cosine_similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()

            suggestions = []
            final_threshold = 0.7

            for i, score in enumerate(cosine_similarities):
                if score >= final_threshold:
                    candidate = candidates[i]
                    suggestions.append((
                        float(score),
                        candidate['source_text'],
                        candidate['target_text']
                    ))

            suggestions.sort(key=lambda x: x[0], reverse=True)
            return suggestions[:5]

        except Exception as e:
            self.logger.error(f"Error during TF-IDF TM query: {e}", exc_info=True)
            return None