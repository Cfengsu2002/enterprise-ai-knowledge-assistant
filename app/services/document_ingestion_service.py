"""Chunk documents, embed, persist vectors to PostgreSQL chunks.embedding (JSONB)."""

from __future__ import annotations

import os

from app.repositories.chunk_repo import delete_chunks_for_document, insert_chunk
from app.repositories.document_repo import get_document_by_id
from app.services.document_text_loader import load_document_text
from app.services.embedding_service import embed_texts, get_embedding_model

_DEFAULT_CHUNK = 500
_DEFAULT_OVERLAP = 50


def default_chunk_size() -> int:
    raw = os.getenv("CHUNK_SIZE", str(_DEFAULT_CHUNK)).strip()
    try:
        v = int(raw)
    except ValueError:
        return _DEFAULT_CHUNK
    return max(100, min(v, 12000))


def default_chunk_overlap() -> int:
    raw = os.getenv("CHUNK_OVERLAP", str(_DEFAULT_OVERLAP)).strip()
    try:
        v = int(raw)
    except ValueError:
        return _DEFAULT_OVERLAP
    return max(0, min(v, default_chunk_size() - 1))


def chunk_text(
    text: str, *, chunk_size: int = _DEFAULT_CHUNK, overlap: int = _DEFAULT_OVERLAP
) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    pieces: list[str] = []
    if overlap >= chunk_size:
        overlap = max(0, chunk_size - 1)
    step = max(1, chunk_size - overlap)
    i = 0
    while i < len(text):
        pieces.append(text[i : i + chunk_size])
        i += step
    return pieces


def ingest_document(
    *,
    document_id: int,
    enterprise_id: int,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> dict:
    doc = get_document_by_id(document_id)
    if not doc:
        raise ValueError("Document not found")
    if int(doc["enterprise_id"]) != int(enterprise_id):
        raise ValueError("Document does not belong to this enterprise")

    cs = chunk_size if chunk_size is not None else default_chunk_size()
    ov = chunk_overlap if chunk_overlap is not None else default_chunk_overlap()
    if ov >= cs:
        raise ValueError("chunk_overlap must be less than chunk_size")

    raw = load_document_text(doc)
    parts = chunk_text(raw, chunk_size=cs, overlap=ov)
    if not parts:
        raise ValueError("No extractable text for embedding")

    model = get_embedding_model()
    vectors = embed_texts(parts)
    if len(vectors) != len(parts):
        raise RuntimeError("Embedding provider returned unexpected count")

    delete_chunks_for_document(document_id)
    for idx, (piece, vec) in enumerate(zip(parts, vectors, strict=True)):
        insert_chunk(
            document_id=document_id,
            content=piece,
            chunk_index=idx,
            embedding=vec,
            embedding_model=model,
        )

    return {
        "document_id": document_id,
        "chunks": len(parts),
        "chunk_size": cs,
        "chunk_overlap": ov,
        "embedding_model": model,
        "embedding_dims": len(vectors[0]) if vectors else 0,
    }
