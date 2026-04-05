"""RAG: index chunks + embeddings into PostgreSQL, semantic search."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from app.repositories.chunk_repo import search_by_embedding
from app.services.document_ingestion_service import ingest_document
from app.services.embedding_service import embed_texts, get_embedding_model

router = APIRouter(prefix="/rag", tags=["rag"])

_MAX_TEXTS = 32
_MAX_CHARS = 16000


class EmbedTextsBody(BaseModel):
    texts: list[str] = Field(..., min_length=1, max_length=_MAX_TEXTS)

    @field_validator("texts")
    @classmethod
    def validate_texts(cls, v: list[str]) -> list[str]:
        for i, t in enumerate(v):
            if t is None or not str(t).strip():
                raise ValueError(f"texts[{i}] must be non-empty")
            if len(str(t)) > _MAX_CHARS:
                raise ValueError(f"texts[{i}] too long (max {_MAX_CHARS})")
        return v


class SemanticSearchBody(BaseModel):
    enterprise_id: int = Field(..., ge=1)
    query: str = Field(..., min_length=1, max_length=8000)
    limit: int = Field(8, ge=1, le=50)


@router.post("/embed")
def embed_only(body: EmbedTextsBody):
    """生成向量（不入库）。便于调试或与入库分离。"""
    try:
        vectors = embed_texts(body.texts)
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Embedding failed: {e}",
        ) from e
    dim = len(vectors[0]) if vectors else 0
    return {
        "model": get_embedding_model(),
        "dimensions": dim,
        "count": len(vectors),
        "embeddings": vectors,
    }


@router.post("/documents/{document_id}/index")
def index_document(
    document_id: int,
    enterprise_id: int = Query(..., ge=1),
    chunk_size: int | None = Query(
        None,
        ge=100,
        le=12000,
        description="缺省用环境变量 CHUNK_SIZE，否则默认 500",
    ),
    chunk_overlap: int | None = Query(
        None,
        ge=0,
        le=11999,
        description="缺省用环境变量 CHUNK_OVERLAP，否则默认 50；须小于 chunk_size",
    ),
):
    """
    读取文档正文 → 分块 → embed_texts → 写入 chunks（先删该文档旧 chunks）。
    默认切块：chunk_size=500，overlap=50（可用 CHUNK_SIZE / CHUNK_OVERLAP 或本接口 query 覆盖）。
    """
    try:
        return ingest_document(
            document_id=document_id,
            enterprise_id=enterprise_id,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/search")
def semantic_search(body: SemanticSearchBody):
    """查询向量化后，与库中 chunks.embedding 做余弦相似度排序。"""
    try:
        qvec = embed_texts([body.query])[0]
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Embedding failed: {e}",
        ) from e
    hits = search_by_embedding(
        enterprise_id=body.enterprise_id,
        query_embedding=qvec,
        limit=body.limit,
    )
    return {"results": hits}
