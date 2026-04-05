"""Load plain text from a document row (local disk or S3)."""

from __future__ import annotations

import io
from pathlib import Path

import boto3
from botocore.client import BaseClient
from pypdf import PdfReader

from app.config.local_upload_settings import UPLOAD_DIR
from app.config.s3_settings import get_endpoint_url, get_region


def _s3_client() -> BaseClient:
    kwargs: dict = {"region_name": get_region()}
    endpoint = get_endpoint_url()
    if endpoint:
        kwargs["endpoint_url"] = endpoint
    return boto3.client("s3", **kwargs)


def _decode_bytes(data: bytes, content_type: str | None, name: str) -> str:
    suffix = Path(name or "").suffix.lower()
    if suffix == ".pdf" or (content_type or "").lower() == "application/pdf":
        reader = PdfReader(io.BytesIO(data))
        parts = [p.extract_text() or "" for p in reader.pages]
        return "\n\n".join(parts).strip()

    for enc in ("utf-8", "utf-8-sig", "gb18030", "latin-1"):
        try:
            return data.decode(enc).strip()
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace").strip()


def load_document_text(doc: dict) -> str:
    storage = (doc.get("storage_type") or "local").lower()
    name = doc.get("original_filename") or doc.get("title") or ""

    if storage == "s3":
        bucket = doc.get("s3_bucket")
        key = doc.get("s3_key")
        if not bucket or not key:
            raise ValueError("S3 document is missing s3_bucket or s3_key")
        conn = _s3_client()
        obj = conn.get_object(Bucket=bucket, Key=key)
        data = obj["Body"].read()
        ct = doc.get("content_type") or obj.get("ContentType")
        return _decode_bytes(data, ct, name)

    rel = doc.get("file_path")
    if not rel:
        raise ValueError("Local document has no file_path")
    path = UPLOAD_DIR / rel
    if not path.is_file():
        raise FileNotFoundError(f"Upload not found on disk: {path}")
    data = path.read_bytes()
    return _decode_bytes(data, doc.get("content_type"), name)
