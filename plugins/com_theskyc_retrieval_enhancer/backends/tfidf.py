# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from .base import RetrievalBackend
import logging

logger = logging.getLogger(__name__)

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

class TfidfBackend(RetrievalBackend):
    def __init__(self):
        self.vectorizer = None
        self.tfidf_matrix = None
        self.indexed_data = []

    def name(self) -> str:
        return "TF-IDF (Statistical)"

    def is_available(self) -> bool:
        return SKLEARN_AVAILABLE

    def build_index(self, data_list: list, progress_callback=None) -> bool:
        if not self.is_available() or not data_list:
            return False
        try:
            if progress_callback: progress_callback(10)

            self.indexed_data = data_list
            corpus = [item['source'] for item in data_list]
            self.vectorizer = TfidfVectorizer(analyzer='char_wb', ngram_range=(2, 4))
            self.tfidf_matrix = self.vectorizer.fit_transform(corpus)

            if progress_callback: progress_callback(100)
            return True
        except Exception as e:
            logger.error(f"TF-IDF build failed: {e}")
            return False

    def retrieve(self, query: str, limit: int = 5, threshold: float = 0.0) -> list:
        if self.vectorizer is None or self.tfidf_matrix is None:
            return []
        try:
            query_vec = self.vectorizer.transform([query])
            cosine_similarities = cosine_similarity(query_vec, self.tfidf_matrix).flatten()
            related_docs_indices = cosine_similarities.argsort()[:-limit - 1:-1]

            results = []
            for idx in related_docs_indices:
                score = float(cosine_similarities[idx])
                if score >= threshold:
                    item = self.indexed_data[idx].copy()
                    item['score'] = score
                    results.append(item)
            return results
        except Exception as e:
            logger.error(f"TF-IDF retrieve failed: {e}")
            return []

    def clear(self):
        self.vectorizer = None
        self.tfidf_matrix = None
        self.indexed_data = []