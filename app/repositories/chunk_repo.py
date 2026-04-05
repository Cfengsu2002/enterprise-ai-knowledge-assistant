import math

from psycopg2.extras import Json

from app.database import get_db_connection


def delete_chunks_for_document(document_id: int) -> None:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM chunks WHERE document_id = %s", (document_id,))


def insert_chunk(
    *,
    document_id: int,
    content: str,
    chunk_index: int,
    embedding: list[float],
    embedding_model: str,
) -> int:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chunks (
                    document_id, content, chunk_index, embedding_model, embedding
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    document_id,
                    content,
                    chunk_index,
                    embedding_model,
                    Json(embedding),
                ),
            )
            row = cur.fetchone()
            return int(row["id"]) if row else 0


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def search_by_embedding(
    *,
    enterprise_id: int,
    query_embedding: list[float],
    limit: int = 8,
) -> list[dict]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.id, c.document_id, c.content, c.chunk_index,
                       c.embedding, c.embedding_model,
                       d.title AS document_title
                FROM chunks c
                INNER JOIN documents d ON d.id = c.document_id
                WHERE d.enterprise_id = %s AND c.embedding IS NOT NULL
                """,
                (enterprise_id,),
            )
            rows = cur.fetchall() or []

    scored: list[tuple[float, dict]] = []
    for row in rows:
        emb = row["embedding"]
        if emb is None:
            continue
        if not isinstance(emb, list):
            continue
        try:
            vec = [float(x) for x in emb]
        except (TypeError, ValueError):
            continue
        if len(vec) != len(query_embedding):
            continue
        sim = _cosine_similarity(query_embedding, vec)
        item = {
            "id": row["id"],
            "document_id": row["document_id"],
            "content": row["content"],
            "chunk_index": row["chunk_index"],
            "document_title": row["document_title"],
            "embedding_model": row["embedding_model"],
            "score": sim,
        }
        scored.append((sim, item))

    scored.sort(key=lambda x: -x[0])
    return [item for _, item in scored[: int(limit)]]
