# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import os
import json
from .backends.tfidf import TfidfBackend
from .backends.onnx_backend import OnnxBackend
from .utils.cache_manager import CacheManager
from .utils.model_manager import ModelManager
from .utils.constants import DEFAULT_CONFIG, SUPPORTED_MODELS
from utils.path_utils import get_app_data_path
import logging
logger = logging.getLogger(__name__)

class RetrievalCore:
    def __init__(self, plugin_dir):
        self.plugin_dir = plugin_dir

        # 数据目录: AppData/Local/LexiSync/plugins_data/com_theskyc_retrieval_enhancer/
        self.data_dir = os.path.join(get_app_data_path(), "plugins_data", "com_theskyc_retrieval_enhancer")
        os.makedirs(self.data_dir, exist_ok=True)

        self.models_dir = os.path.join(self.data_dir, "models")
        self.config_path = os.path.join(self.data_dir, "config.json")
        self.cache_db_path = os.path.join(self.data_dir, "cache.db")

        self.config = self._load_config()

        # Managers
        self.cache_manager = CacheManager(self.cache_db_path)
        self.model_manager = ModelManager(self.models_dir)

        # Backends
        self.tfidf_backend = TfidfBackend()
        self.onnx_backend = OnnxBackend(self.cache_manager)

        self.active_backend = None
        self._apply_config()

    def _load_config(self):
        # 优先读取 AppData 下的配置
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    # 合并默认配置，防止缺字段
                    config = DEFAULT_CONFIG.copy()
                    config.update(user_config)
                    return config
            except:
                pass

        # 首次运行，保存默认配置
        self._save_config_to_disk(DEFAULT_CONFIG)
        return DEFAULT_CONFIG

    def _save_config_to_disk(self, config):
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)

    def save_config(self):
        self._save_config_to_disk(self.config)
        self._apply_config()

    def _apply_config(self):
        """应用配置，加载对应的模型"""
        active_id = self.config.get("active_model", "minilm-l12-v2")

        # 确定模型路径
        if active_id in SUPPORTED_MODELS:
            # 内置模型
            model_path = self.model_manager.get_model_dir(active_id)
        elif active_id in self.config.get("custom_models", {}):
            # 自定义模型
            model_path = self.model_manager.get_model_dir(active_id, is_custom=True)
        else:
            model_path = None

        if model_path:
            self.onnx_backend.load_model(model_path, active_id)

    def clear_all_backends(self):
        """Clears in-memory indexes of all backends."""
        self.tfidf_backend.clear()
        self.onnx_backend.clear()
        self.active_backend = None
        logger.info("[RetrievalCore] All backend indexes have been cleared.")

    def build_index(self, data_list):
        # 优先尝试 ONNX
        if self.onnx_backend.is_available():
            if self.onnx_backend.build_index(data_list):
                self.active_backend = self.onnx_backend
                return True

        # 降级到 TF-IDF
        if self.tfidf_backend.is_available():
            if self.tfidf_backend.build_index(data_list):
                self.active_backend = self.tfidf_backend
                return True

        return False

    def retrieve(self, query, limit=5, mode="auto"):
        import logging
        logger = logging.getLogger(__name__)

        backend = None

        if mode == "onnx":
            if self.onnx_backend.is_available():
                backend = self.onnx_backend
        elif mode == "tfidf":
            if self.tfidf_backend.is_available():
                backend = self.tfidf_backend
        else:  # Auto
            if self.onnx_backend.is_available():
                backend = self.onnx_backend
            elif self.tfidf_backend.is_available():
                backend = self.tfidf_backend

        target_backend = backend if backend else self.active_backend

        if not target_backend:
            logger.error(
                f"[RetrievalCore] CRITICAL: No backend available! ONNX Available: {self.onnx_backend.is_available()}, TF-IDF Available: {self.tfidf_backend.is_available()}")
            return []

        data_count = len(target_backend.indexed_data) if hasattr(target_backend, 'indexed_data') else 0
        if data_count == 0:
            logger.warning(
                f"[RetrievalCore] Backend '{target_backend.name()}' has EMPTY index (0 items). build_index() was likely not called yet.")
            return []

        logger.info(f"[RetrievalCore] Using backend '{target_backend.name()}' to search in {data_count} items.")

        # 执行检索
        return target_backend.retrieve(query, limit)