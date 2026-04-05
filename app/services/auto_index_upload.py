"""Upload 成功后自动 chunked + embedding 写入 chunks（可关闭）。"""

from __future__ import annotations

import logging
import os

from app.services.document_ingestion_service import ingest_document

logger = logging.getLogger(__name__)


def is_auto_index_enabled() -> bool:
    v = (os.getenv("AUTO_INDEX_ON_UPLOAD") or "true").strip().lower()
    return v not in ("0", "false", "no", "off")


def merge_indexing_into_document(document: dict) -> dict:
    """
    在已有 document 行上跑 ingest；失败不抛错，写入 indexing_error。
    返回新 dict（不修改入参）。
    """
    doc = dict(document)
    if not is_auto_index_enabled():
        doc["indexing"] = None
        doc["auto_index_skipped"] = True
        return doc
    try:
        meta = ingest_document(
            document_id=int(doc["id"]),
            enterprise_id=int(doc["enterprise_id"]),
        )
        doc["indexing"] = meta
    except Exception as e:
        logger.warning(
            "Auto-index failed document_id=%s: %s",
            doc.get("id"),
            e,
        )
        doc["indexing"] = None
        doc["indexing_error"] = str(e)
    return doc
