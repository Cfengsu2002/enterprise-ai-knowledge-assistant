"""
Text embeddings: OpenAI API or 本地小模型（FastEmbed + ONNX，无需 GPU）。

默认策略（EMBEDDING_BACKEND=auto）：
- 若设置了 OPENAI_API_KEY → 使用 OpenAI
- 否则 → 使用本地模型（推荐：`paraphrase-multilingual-MiniLM-L12-v2`，384 维，中英文）

仅走 local / auto+无 Key 时**不导入 openai**，避免本机 venv 里 pydantic_core 损坏导致无法跑本地嵌入。
"""

from __future__ import annotations

import os
from typing import Literal

# 本地默认：多语言 MiniLM（比 bge-small-en 略大，但支持中文作业演示）
DEFAULT_LOCAL_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

_backend: Literal["openai", "local"] | None = None
_local_embedder = None
_local_model_name: str | None = None


def get_embedding_backend() -> Literal["openai", "local"]:
    global _backend
    if _backend is None:
        raw = (os.getenv("EMBEDDING_BACKEND") or "auto").strip().lower()
        if raw == "openai":
            _backend = "openai"
        elif raw == "local":
            _backend = "local"
        else:
            _backend = (
                "openai" if os.getenv("OPENAI_API_KEY", "").strip() else "local"
            )
    return _backend


def get_embedding_model() -> str:
    if get_embedding_backend() == "openai":
        return os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    return os.getenv("LOCAL_EMBEDDING_MODEL", DEFAULT_LOCAL_MODEL)


def openai_client():
    """仅在 OpenAI 分支调用；延迟 import 以免本地模式依赖 pydantic_core。"""
    from openai import OpenAI

    kwargs: dict = {}
    base = (os.getenv("OPENAI_BASE_URL") or "").strip()
    if base:
        kwargs["base_url"] = base
    return OpenAI(**kwargs)


def _get_local_embedder():
    """FastEmbed：小体积 ONNX 推理，首次运行会从 Hugging Face 拉取模型文件。"""
    global _local_embedder, _local_model_name
    name = get_embedding_model()
    if _local_embedder is None or _local_model_name != name:
        from fastembed import TextEmbedding

        _local_embedder = TextEmbedding(model_name=name)
        _local_model_name = name
    return _local_embedder


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    if get_embedding_backend() == "local":
        model = _get_local_embedder()
        out: list[list[float]] = []
        for row in model.embed(texts):
            out.append([float(x) for x in row.tolist()])
        return out

    if not os.getenv("OPENAI_API_KEY", "").strip():
        raise RuntimeError(
            "OPENAI_API_KEY is not set (or use EMBEDDING_BACKEND=local for FastEmbed)"
        )
    model = get_embedding_model()
    client = openai_client()
    resp = client.embeddings.create(model=model, input=texts)
    ordered = sorted(resp.data, key=lambda d: d.index)
    return [item.embedding for item in ordered]
