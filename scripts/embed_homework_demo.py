#!/usr/bin/env python3
"""
演示 embed_texts：默认无 OPENAI_API_KEY 时使用本地小模型（FastEmbed，首次会下载 ONNX 权重）。

  PYTHONPATH=. ./venv312/bin/python scripts/embed_homework_demo.py

仅假向量（不下载模型）：

  PYTHONPATH=. ./venv312/bin/python scripts/embed_homework_demo.py --mock

强制 OpenAI：

  EMBEDDING_BACKEND=openai OPENAI_API_KEY=sk-... PYTHONPATH=. ./venv312/bin/python scripts/embed_homework_demo.py

若出现 ModuleNotFoundError: pydantic_core._pydantic_core，在 project 根目录执行：

  ./venv312/bin/pip install --force-reinstall "pydantic-core>=2.41,<3" "pydantic>=2.12,<3"
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from app.services.embedding_service import (  # noqa: E402
    embed_texts,
    get_embedding_backend,
    get_embedding_model,
)


def _mock_embeddings(texts: list[str], dim: int = 384) -> list[list[float]]:
    """本地演示用假向量（维度与默认本地 MiniLM 一致）。"""
    import hashlib
    import struct

    out: list[list[float]] = []
    for t in texts:
        seed = hashlib.sha256(t.encode("utf-8")).digest()
        vec: list[float] = []
        block = seed
        while len(vec) < dim:
            block = hashlib.sha256(block + seed).digest()
            for j in range(0, 28, 4):
                if len(vec) >= dim:
                    break
                x = struct.unpack("<f", block[j : j + 4])[0]
                vec.append(max(-1.0, min(1.0, x)))
        out.append(vec)
    return out


def main() -> None:
    use_mock = "--mock" in sys.argv or os.getenv("EMBED_DEMO_MOCK", "").strip() == "1"
    samples = [
        "企业知识助手使用 RAG 从向量库检索相关段落。",
        "Embeddings map text to vectors for semantic search.",
    ]
    if use_mock:
        print("(mock) 确定性假向量，未使用 FastEmbed / OpenAI\n")
        vectors = _mock_embeddings(samples)
        print("backend=mock dim=384")
    else:
        vectors = embed_texts(samples)
        print(f"backend={get_embedding_backend()} model={get_embedding_model()}")
    for i, vec in enumerate(vectors):
        print(f"text[{i}] dim={len(vec)} head={vec[:5]}")


if __name__ == "__main__":
    main()
