"""
S3 multipart upload helpers (init, presigned part PUT, list parts, complete, abort).
"""

from __future__ import annotations

import uuid
from pathlib import Path

import boto3
from botocore.client import BaseClient
from botocore.exceptions import ClientError

from app.config.s3_settings import (
    get_bucket,
    get_endpoint_url,
    get_presign_expires_seconds,
    get_region,
)
from app.repositories.document_repo import create_document
from app.repositories.multipart_session_repo import (
    create_session,
    get_session,
    update_session_status,
)
from app.services.upload_service import ALLOWED_EXTENSIONS

FIVE_MIB = 5 * 1024 * 1024
EIGHT_MIB = 8 * 1024 * 1024
MAX_PARTS = 10_000


def _norm_etag(etag: str) -> str:
    """
    S3 CompleteMultipart expects ETag like \"d41d8cd98f00b204e9800998ecf8427e\" (quotes included).
    Browser/JSON may send extra outer quotes — peel them, then wrap once.
    """
    e = str(etag).strip()
    for _ in range(8):
        if len(e) >= 2 and e[0] == '"' and e[-1] == '"':
            e = e[1:-1].strip()
        else:
            break
    return f'"{e}"'


def _s3_client() -> BaseClient:
    kwargs: dict = {"region_name": get_region()}
    endpoint = get_endpoint_url()
    if endpoint:
        kwargs["endpoint_url"] = endpoint
    return boto3.client("s3", **kwargs)


def recommended_part_size(file_size: int) -> int:
    """Pick part size: single small file = one part; else >= 5 MiB parts, max 10k parts."""
    if file_size <= FIVE_MIB:
        return max(file_size, 1)
    part_size = EIGHT_MIB
    while (file_size + part_size - 1) // part_size > MAX_PARTS:
        part_size *= 2
    return part_size


def _safe_s3_filename(original_filename: str) -> str:
    name = Path(original_filename).name.strip()
    if not name:
        raise ValueError("Filename is required")
    ext = Path(name).suffix.lower().lstrip(".")
    if ALLOWED_EXTENSIONS and ext and ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"File type not allowed: {ext}")
    return name


def build_object_key(enterprise_id: int, original_filename: str) -> str:
    safe = _safe_s3_filename(original_filename)
    uid = uuid.uuid4().hex[:16]
    return f"enterprises/{enterprise_id}/uploads/{uid}_{safe}"


def initiate_multipart(
    *,
    enterprise_id: int,
    filename: str,
    file_size: int,
    content_type: str | None,
    title: str | None,
    user_id: int | None,
) -> dict:
    bucket = get_bucket()
    if not bucket:
        raise RuntimeError("S3 is not configured (set S3_BUCKET)")

    if file_size < 1:
        raise ValueError("file_size must be positive")

    key = build_object_key(enterprise_id, filename)
    part_size = recommended_part_size(file_size)
    client = _s3_client()

    create_kw: dict = {"Bucket": bucket, "Key": key}
    if content_type:
        create_kw["ContentType"] = content_type

    resp = client.create_multipart_upload(**create_kw)
    upload_id = resp["UploadId"]

    row = create_session(
        s3_upload_id=upload_id,
        s3_key=key,
        bucket=bucket,
        enterprise_id=enterprise_id,
        original_filename=Path(filename).name,
        file_size=file_size,
        part_size_bytes=part_size,
        title=title,
        user_id=user_id,
        content_type=content_type,
    )
    if not row:
        try:
            client.abort_multipart_upload(Bucket=bucket, Key=key, UploadId=upload_id)
        except Exception:
            pass
        raise RuntimeError("Failed to persist multipart session")

    return {
        "session_id": str(row["id"]),
        "upload_id": upload_id,
        "key": key,
        "bucket": bucket,
        "part_size_bytes": part_size,
        "file_size": file_size,
    }


def presign_upload_part(*, session_id, part_number: int) -> str:
    from uuid import UUID

    sid = UUID(str(session_id))
    row = get_session(sid)
    if not row or row["status"] != "in_progress":
        raise ValueError("Invalid or closed upload session")

    if part_number < 1 or part_number > MAX_PARTS:
        raise ValueError(f"part_number must be 1..{MAX_PARTS}")

    client = _s3_client()
    expires = get_presign_expires_seconds()
    url = client.generate_presigned_url(
        ClientMethod="upload_part",
        Params={
            "Bucket": row["bucket"],
            "Key": row["s3_key"],
            "UploadId": row["s3_upload_id"],
            "PartNumber": part_number,
        },
        ExpiresIn=expires,
        HttpMethod="PUT",
    )
    return url


def upload_part_bytes(*, session_id, part_number: int, body: bytes) -> dict:
    """
    Upload one part using boto3 on the server (same UploadId as presigned flow).
    Use when the browser cannot PUT to S3 (CORS / network / policy) — traffic is browser → API → S3.
    """
    from uuid import UUID

    if not body:
        raise ValueError("empty part body")

    sid = UUID(str(session_id))
    row = get_session(sid)
    if not row or row["status"] != "in_progress":
        raise ValueError("Invalid or closed upload session")

    if part_number < 1 or part_number > MAX_PARTS:
        raise ValueError(f"part_number must be 1..{MAX_PARTS}")

    part_size = int(row["part_size_bytes"])
    file_size = int(row["file_size"])
    start = (part_number - 1) * part_size
    expected_len = min(part_size, max(0, file_size - start))
    if expected_len < 1:
        raise ValueError("invalid part_number for this upload")
    if len(body) != expected_len:
        raise ValueError(
            f"Part body length {len(body)} does not match expected {expected_len} bytes for part {part_number}"
        )

    client = _s3_client()
    resp = client.upload_part(
        Bucket=row["bucket"],
        Key=row["s3_key"],
        PartNumber=part_number,
        UploadId=row["s3_upload_id"],
        Body=body,
    )
    return {"PartNumber": part_number, "ETag": resp["ETag"]}


def list_uploaded_parts(*, session_id) -> list[dict]:
    from uuid import UUID

    sid = UUID(str(session_id))
    row = get_session(sid)
    if not row or row["status"] != "in_progress":
        raise ValueError("Invalid or closed upload session")

    client = _s3_client()
    parts: list[dict] = []
    kwargs = {
        "Bucket": row["bucket"],
        "Key": row["s3_key"],
        "UploadId": row["s3_upload_id"],
    }
    while True:
        resp = client.list_parts(**kwargs)
        for p in resp.get("Parts", []):
            parts.append(
                {
                    "PartNumber": p["PartNumber"],
                    "ETag": p["ETag"],
                    "Size": p.get("Size"),
                }
            )
        token = resp.get("NextPartNumberMarker")
        if resp.get("IsTruncated") and token is not None:
            kwargs["PartNumberMarker"] = token
        else:
            break

    parts.sort(key=lambda x: x["PartNumber"])
    return parts


def complete_multipart(*, session_id, parts: list[dict]) -> dict:
    from uuid import UUID

    sid = UUID(str(session_id))
    row = get_session(sid)
    if not row or row["status"] != "in_progress":
        raise ValueError("Invalid or closed upload session")

    if not parts:
        raise ValueError("parts must not be empty")

    normalized = []
    for p in parts:
        pn = p.get("PartNumber") or p.get("part_number")
        etag = p.get("ETag") or p.get("etag")
        if pn is None or etag is None:
            raise ValueError("Each part needs PartNumber and ETag")
        etag_str = _norm_etag(str(etag).strip())
        normalized.append({"PartNumber": int(pn), "ETag": etag_str})

    normalized.sort(key=lambda x: x["PartNumber"])

    client = _s3_client()
    client.complete_multipart_upload(
        Bucket=row["bucket"],
        Key=row["s3_key"],
        UploadId=row["s3_upload_id"],
        MultipartUpload={"Parts": normalized},
    )

    s3_uri = f"s3://{row['bucket']}/{row['s3_key']}"
    doc_title = (row.get("title") or row["original_filename"] or "upload").strip()
    record = create_document(
        enterprise_id=row["enterprise_id"],
        title=doc_title,
        file_path=s3_uri,
        user_id=row.get("user_id"),
        storage_type="s3",
        original_filename=row["original_filename"],
        content_type=row.get("content_type"),
        byte_size=int(row["file_size"]),
        s3_bucket=row["bucket"],
        s3_key=row["s3_key"],
        file_metadata={
            "aws_region": get_region(),
            "storage": "s3_multipart",
            "source_uri": s3_uri,
            **({"s3_endpoint_url": get_endpoint_url()} if get_endpoint_url() else {}),
        },
    )
    if not record:
        raise RuntimeError("Failed to create document after S3 complete")

    update_session_status(sid, "completed")

    from app.services.auto_index_upload import merge_indexing_into_document

    record_out = merge_indexing_into_document(dict(record))
    return {"document": record_out, "s3_uri": s3_uri}


def abort_multipart(*, session_id) -> None:
    from uuid import UUID

    sid = UUID(str(session_id))
    row = get_session(sid)
    if not row:
        raise ValueError("Unknown session")
    if row["status"] != "in_progress":
        return

    client = _s3_client()
    try:
        client.abort_multipart_upload(
            Bucket=row["bucket"],
            Key=row["s3_key"],
            UploadId=row["s3_upload_id"],
        )
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code not in ("NoSuchUpload", "404"):
            raise
    update_session_status(sid, "aborted")
