# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from .base import RetrievalBackend
import logging
import os
import gc
import numpy as np

logger = logging.getLogger(__name__)

try:
    import onnxruntime as ort
    from tokenizers import Tokenizer

    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False


class OnnxBackend(RetrievalBackend):
    def __init__(self, cache_manager):
        self.cache_manager = cache_manager
        self.model_path = None
        self.model_id = "unknown"
        self.expected_dim = None
        self.tokenizer = None
        self.session = None
        self.index_embeddings = None
        self.indexed_data = []
        self._is_ready = False
        self._use_token_type_ids = None

    def name(self) -> str:
        return "Local LLM (ONNX)"

    def is_available(self) -> bool:
        if not ONNX_AVAILABLE: return False
        if not self.model_path: return False
        has_model = os.path.exists(os.path.join(self.model_path, "model.onnx")) or \
                    os.path.exists(os.path.join(self.model_path, "model_quantized.onnx"))
        has_tok = os.path.exists(os.path.join(self.model_path, "tokenizer.json"))
        return has_model and has_tok

    def load_model(self, model_path, model_id, expected_dim=None):
        if self.session:
            del self.session
            self.session = None
            gc.collect()

        if self.model_id != model_id:
            self.clear()

        self.model_path = model_path
        self.model_id = model_id
        self.expected_dim = expected_dim
        self._is_ready = False
        self.tokenizer = None
        self._use_token_type_ids = None

    def _ensure_loaded(self):
        if self._is_ready: return True
        if not self.is_available(): return False

        try:
            tok_file = os.path.join(self.model_path, "tokenizer.json")
            onnx_file = os.path.join(self.model_path, "model_quantized.onnx")
            if not os.path.exists(onnx_file):
                onnx_file = os.path.join(self.model_path, "model.onnx")

            temp_tokenizer = Tokenizer.from_file(tok_file)
            temp_tokenizer.enable_padding(pad_id=0, pad_token="[PAD]", length=512)
            temp_tokenizer.enable_truncation(max_length=512)

            sess_options = ort.SessionOptions()

            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            sess_options.execution_mode = ort.ExecutionMode.ORT_PARALLEL
            try:
                num_threads = os.cpu_count()
                if num_threads:
                    sess_options.intra_op_num_threads = num_threads
                    sess_options.inter_op_num_threads = num_threads
                    logger.info(f"[OnnxBackend] Set ONNX threads to {num_threads}.")
            except Exception as e:
                logger.warning(f"[OnnxBackend] Could not set thread count: {e}")
            available_providers = ort.get_available_providers()
            providers_to_use = []
            if 'DmlExecutionProvider' in available_providers:
                providers_to_use.append('DmlExecutionProvider')
            providers_to_use.append('CPUExecutionProvider')
            logger.info(f"[OnnxBackend] Using ONNX providers: {providers_to_use}")
            temp_session = ort.InferenceSession(onnx_file, sess_options, providers=providers_to_use)

            if self._use_token_type_ids is None:
                encoded = temp_tokenizer.encode_batch(["test"])
                input_ids = np.array([e.ids for e in encoded], dtype=np.int64)
                attention_mask = np.array([e.attention_mask for e in encoded], dtype=np.int64)
                token_type_ids = np.array([e.type_ids for e in encoded], dtype=np.int64)

                try:
                    temp_session.run(None, {'input_ids': input_ids, 'attention_mask': attention_mask,
                                            'token_type_ids': token_type_ids})
                    self._use_token_type_ids = True
                except:
                    self._use_token_type_ids = False
                logger.info(f"[OnnxBackend] Model requires token_type_ids: {self._use_token_type_ids}")

            if self.expected_dim:
                dummy_emb = self._compute_embeddings_internal(temp_tokenizer, temp_session, ["test"])
                actual_dim = dummy_emb.shape[1] if dummy_emb is not None else -1

                if actual_dim != self.expected_dim:
                    logger.critical(
                        f"CRITICAL MODEL MISMATCH! Model ID '{self.model_id}' expects dimension {self.expected_dim}, "
                        f"but files at '{self.model_path}' produce dimension {actual_dim}. "
                        f"Aborting load."
                    )
                    return False

            self.tokenizer = temp_tokenizer
            self.session = temp_session
            self._is_ready = True
            return True
        except Exception as e:
            logger.error(f"Failed to load ONNX model from {self.model_path}: {e}", exc_info=True)
            return False

    def _mean_pooling(self, model_output, attention_mask):
        token_embeddings = model_output[0]
        input_mask_expanded = np.expand_dims(attention_mask, -1)
        masked_embeddings = token_embeddings * input_mask_expanded
        sum_embeddings = np.sum(masked_embeddings, axis=1)
        sum_mask = np.sum(attention_mask, axis=1, keepdims=True)
        clipped_sum_mask = np.maximum(sum_mask, 1e-9)
        pooled_embeddings = sum_embeddings / clipped_sum_mask
        return pooled_embeddings.astype(np.float32)

    def _compute_embeddings_internal(self, tokenizer, session, texts: list):
        """Internal compute function for self-check, avoids recursion."""
        encoded = tokenizer.encode_batch(texts)
        input_ids = np.array([e.ids for e in encoded], dtype=np.int64)
        attention_mask = np.array([e.attention_mask for e in encoded], dtype=np.int64)

        inputs = {'input_ids': input_ids, 'attention_mask': attention_mask}
        if self._use_token_type_ids:
            inputs['token_type_ids'] = np.array([e.type_ids for e in encoded], dtype=np.int64)

        outputs = session.run(None, inputs)
        return self._mean_pooling(outputs, attention_mask)

    def _compute_embeddings(self, texts: list):
        if not self._ensure_loaded(): return None
        embeddings = self._compute_embeddings_internal(self.tokenizer, self.session, texts)
        norm = np.linalg.norm(embeddings, axis=1, keepdims=True)
        return embeddings / np.clip(norm, a_min=1e-9, a_max=None)

    def build_index(self, data_list: list) -> bool:
        if not self.is_available(): return False
        try:
            self.indexed_data = data_list
            corpus = [item['source'] for item in data_list]
            cached_vectors = self.cache_manager.get_vectors(corpus, self.model_id)
            missing_texts = [t for t in corpus if t not in cached_vectors]
            logger.info(
                f"[OnnxBackend] Cache Stats - Total: {len(corpus)}, Hits: {len(cached_vectors)}, Misses: {len(missing_texts)}")

            if missing_texts:
                logger.info(f"Computing embeddings for {len(missing_texts)} new items...")
                batch_size = 32
                new_vectors_map = {}
                for i in range(0, len(missing_texts), batch_size):
                    batch = missing_texts[i:i + batch_size]
                    embeddings = self._compute_embeddings(batch)
                    if embeddings is not None:
                        for j, text in enumerate(batch):
                            new_vectors_map[text] = embeddings[j]
                self.cache_manager.save_vectors(new_vectors_map, self.model_id)
                cached_vectors.update(new_vectors_map)

            final_list, valid_indices = [], []
            for i, text in enumerate(corpus):
                if text in cached_vectors:
                    final_list.append(cached_vectors[text])
                    valid_indices.append(i)

            if final_list:
                self.index_embeddings = np.vstack(final_list)
                self.indexed_data = [data_list[i] for i in valid_indices]
                return True
            return False
        except Exception as e:
            logger.error(f"ONNX build failed: {e}", exc_info=True)
            return False

    def retrieve(self, query: str, limit: int = 5, threshold: float = 0.0) -> list:
        if self.index_embeddings is None: return []
        try:
            query_emb = self._compute_embeddings([query])
            if query_emb is None: return []
            scores = np.dot(self.index_embeddings, query_emb.T).flatten()
            related_indices = scores.argsort()[:-limit - 1:-1]
            results = []
            for idx in related_indices:
                score = float(scores[idx])
                if score >= threshold:
                    item = self.indexed_data[idx].copy()
                    item['score'] = score
                    results.append(item)
            return results
        except Exception as e:
            logger.error(f"ONNX retrieve failed: {e}", exc_info=True)
            return []

    def clear(self):
        self.index_embeddings = None
        self.indexed_data = []
        logger.info(f"[OnnxBackend] In-memory index cleared for model '{self.model_id}'.")