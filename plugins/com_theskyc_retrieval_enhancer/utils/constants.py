# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

DEFAULT_CONFIG = {
    "active_model": "minilm-l12-v2",
    "mirror": "https://hf-mirror.com",
    "custom_models": {}  # 存储导入的模型信息: { "id": { "name": "...", "path": "relative/path" } }
}

# 内置支持的模型注册表
SUPPORTED_MODELS = {
    "minilm-l12-v2": {
        "name": "MiniLM L12 v2 (Balanced)",
        "description": "Small (120MB), fast, good for general purpose.",
        "repo_id": "Xenova/paraphrase-multilingual-MiniLM-L12-v2",
        "files": ["onnx/model_quantized.onnx", "tokenizer.json", "config.json"],
        "dim": 384
    },
    "multilingual-e5-small": {
        "name": "Multilingual E5 Small (Quality)",
        "description": "Small (160MB), better semantic understanding.",
        "repo_id": "Xenova/multilingual-e5-small",
        "files": ["onnx/model_quantized.onnx", "tokenizer.json", "config.json"],
        "dim": 384
    },
    "labse": {
        "name": "LaBSE (High Accuracy)",
        "description": "Large (~500MB), excellent for bitext alignment, slower.",
        "repo_id": "Xenova/LaBSE",
        "files": ["onnx/model_quantized.onnx", "tokenizer.json", "config.json"],
        "dim": 768
    }
}