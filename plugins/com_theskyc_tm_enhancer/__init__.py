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


class RetrievalEnhancerPlugin(PluginBase):
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.vectorizer = None
        self.tfidf_matrix = None
        self.indexed_data = []  # List of dicts: {'source': str, 'target': str, ...}
        self.is_ready = SKLEARN_AVAILABLE
        if not self.is_ready:
            self.logger.warning("scikit-learn or numpy not found. Retrieval Enhancer will be disabled.")

    def plugin_id(self) -> str:
        return "com_theskyc_retrieval_enhancer"  # [CHANGED] ID Updated

    def name(self) -> str:
        return self._("Retrieval Enhancer (TF-IDF)")  # [CHANGED] Name Updated

    def description(self) -> str:
        if SKLEARN_AVAILABLE:
            return self._(
                "Provides advanced semantic retrieval capabilities using TF-IDF for TM matching and AI context.")
        else:
            return self._("Requires 'scikit-learn' and 'numpy'.")

    def version(self) -> str:
        return "2.0.0"

    def author(self) -> str:
        return "TheSkyC"

    def external_dependencies(self) -> Dict[str, str]:
        return {
            'scikit-learn': '>=1.0',
            'numpy': '',
        }

    # --- Hook for TM Panel (Legacy Support) ---
    def query_tm_suggestions(self, original_text: str) -> Optional[List[Tuple[float, str, str]]]:
        return None

        # --- New Hooks for Intelligent Batch Translation ---

    def build_retrieval_index(self, data_list: List[Dict[str, str]]):
        """
        Builds a TF-IDF index from a list of data.
        data_list: [{'source': '...', 'target': '...'}, ...]
        """
        if not self.is_ready or not data_list:
            return False

        try:
            self.indexed_data = data_list
            corpus = [item['source'] for item in data_list]

            # char_wb + ngram (2,4) is good for short text similarity
            self.vectorizer = TfidfVectorizer(analyzer='char_wb', ngram_range=(2, 4))
            self.tfidf_matrix = self.vectorizer.fit_transform(corpus)
            self.logger.info(f"Built TF-IDF index for {len(corpus)} items.")
            return True
        except Exception as e:
            self.logger.error(f"Failed to build index: {e}", exc_info=True)
            return False

    def retrieve_context(self, query_text: str, limit: int = 3, threshold: float = 0.6) -> List[Dict]:
        """
        Retrieves similar items from the built index.
        """
        if not self.is_ready or self.vectorizer is None or self.tfidf_matrix is None:
            return []

        try:
            query_vec = self.vectorizer.transform([query_text])
            cosine_similarities = cosine_similarity(query_vec, self.tfidf_matrix).flatten()

            related_docs_indices = cosine_similarities.argsort()[:-limit - 1:-1]

            results = []
            for idx in related_docs_indices:
                score = cosine_similarities[idx]
                if score >= threshold:
                    item = self.indexed_data[idx].copy()
                    item['score'] = float(score)
                    results.append(item)

            return results
        except Exception as e:
            self.logger.error(f"Error during retrieval: {e}", exc_info=True)
            return []