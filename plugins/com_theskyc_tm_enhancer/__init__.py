# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from plugins.plugin_base import PluginBase
import logging
from typing import Dict

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
        self.is_ready = False

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

    def author(self) -> str:
        return "TheSkyC"

    def url(self) -> str:
        return "https://github.com/TheSkyC/lexisync/tree/master/plugins/com_theskyc_tm_enhancer"

    def compatible_app_version(self) -> str:
        return "1.1"

    def external_dependencies(self) -> Dict[str, str]:
        return {
            'scikit-learn': '>=1.0',
            'numpy': '',
        }

    def setup(self, main_window, plugin_manager):
        super().setup(main_window, plugin_manager)
        if not SKLEARN_AVAILABLE:
            self.logger.warning("scikit-learn or numpy not found. TM Enhancer plugin will be disabled.")
        self.on_tm_loaded(self.main_window.translation_memory)

    def on_tm_loaded(self, translation_memory: dict):
        if not SKLEARN_AVAILABLE or not translation_memory:
            self.is_ready = False
            return

        self.logger.info("TM has been updated. Rebuilding TF-IDF index...")
        try:
            self.tm_data = translation_memory
            self.tm_originals = list(self.tm_data.keys())
            self.vectorizer = TfidfVectorizer(analyzer='char_wb', ngram_range=(2, 4))
            self.tfidf_matrix = self.vectorizer.fit_transform(self.tm_originals)
            self.is_ready = True
            self.logger.info(f"TF-IDF index rebuilt successfully for {len(self.tm_originals)} TM entries.")
        except Exception as e:
            self.is_ready = False
            self.logger.error(f"Failed to build TF-IDF index: {e}", exc_info=True)

    def query_tm_suggestions(self, original_text: str) -> list[tuple[float, str, str]] | None:
        if not self.is_ready or not SKLEARN_AVAILABLE:
            return None
        try:
            query_vec = self.vectorizer.transform([original_text])
            cosine_similarities = cosine_similarity(query_vec, self.tfidf_matrix).flatten()
            top_n_indices = cosine_similarities.argsort()[-10:][::-1]
            suggestions = []
            for i in top_n_indices:
                score = cosine_similarities[i]
                if score > 0.5:
                    tm_original = self.tm_originals[i]
                    tm_translation = self.tm_data[tm_original]
                    suggestions.append((score, tm_original, tm_translation))
            return suggestions
        except Exception as e:
            self.logger.error(f"Error during TM query: {e}", exc_info=True)
            return None