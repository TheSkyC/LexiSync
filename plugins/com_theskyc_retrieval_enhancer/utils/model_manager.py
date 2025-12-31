# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import os
import requests
import shutil
import logging
from .constants import SUPPORTED_MODELS

logger = logging.getLogger(__name__)


class ModelManager:
    def __init__(self, base_dir):
        self.base_dir = base_dir  # plugins_data/.../models/

    def get_model_dir(self, model_id, is_custom=False):
        return os.path.join(self.base_dir, model_id)

    def is_model_installed(self, model_id, is_custom=False):
        target_dir = self.get_model_dir(model_id, is_custom)
        if not os.path.exists(target_dir):
            return False
        # 简单检查关键文件
        required = ["model.onnx", "model_quantized.onnx"]  # 至少有一个
        has_model = any(os.path.exists(os.path.join(target_dir, f)) for f in required)
        has_tokenizer = os.path.exists(os.path.join(target_dir, "tokenizer.json"))
        return has_model and has_tokenizer

    def download_model(self, model_id, mirror_url, progress_callback):
        if model_id not in SUPPORTED_MODELS:
            raise ValueError(f"Unknown model ID: {model_id}")

        info = SUPPORTED_MODELS[model_id]
        repo_id = info["repo_id"]
        files = info["files"]

        target_dir = self.get_model_dir(model_id)
        os.makedirs(target_dir, exist_ok=True)

        total_files = len(files)

        for i, remote_path in enumerate(files):
            filename = os.path.basename(remote_path)
            url = f"{mirror_url}/{repo_id}/resolve/main/{remote_path}"
            save_path = os.path.join(target_dir, filename)

            progress_callback(int((i / total_files) * 100), f"Downloading {filename}...")

            try:
                self._download_file(url, save_path)
            except Exception as e:
                raise Exception(f"Failed to download {filename}: {e}")

        progress_callback(100, "Download Complete")

    def _download_file(self, url, save_path):
        with requests.get(url, stream=True, timeout=30) as r:
            r.raise_for_status()
            with open(save_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

    def import_local_model(self, src_path, custom_id):
        """
        复制本地文件夹到模型目录
        """
        # 验证
        if not (os.path.exists(os.path.join(src_path, "model.onnx")) or
                os.path.exists(os.path.join(src_path, "model_quantized.onnx"))):
            raise ValueError("Source folder must contain 'model.onnx' or 'model_quantized.onnx'")

        if not os.path.exists(os.path.join(src_path, "tokenizer.json")):
            raise ValueError("Source folder must contain 'tokenizer.json'")

        target_dir = self.get_model_dir(custom_id)
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir)

        shutil.copytree(src_path, target_dir)
        return True

    def delete_model(self, model_id):
        target_dir = self.get_model_dir(model_id)
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir)