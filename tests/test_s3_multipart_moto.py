"""
S3 分片上传 + ListParts（断点续传依据）+ Complete —— 使用 moto 模拟 S3，不访问真实 AWS。
DB 层用内存 stub，只测 s3_multipart_service 与 boto3/moto 的协作。
"""

from __future__ import annotations

import os
import uuid
from unittest.mock import patch

import pytest
import requests

# 必须在 import app 前设置，以便 s3_settings / boto3 读到
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_SECURITY_TOKEN", "testing")
os.environ.setdefault("AWS_SESSION_TOKEN", "testing")
os.environ["S3_BUCKET"] = "test-multipart-bucket"
os.environ["AWS_REGION"] = "us-east-1"
os.environ.pop("S3_ENDPOINT_URL", None)

pytest.importorskip("moto")
from moto import mock_aws  # noqa: E402

import boto3  # noqa: E402

from app.services import s3_multipart_service as s3mp  # noqa: E402


@pytest.fixture
def memory_db():
    """内存中的 multipart session + 假 document。"""
    sessions: dict[str, dict] = {}
    doc_counter = [0]

    def create_session(**kw):
        sid = uuid.uuid4()
        row = {
            "id": sid,
            "s3_upload_id": kw["s3_upload_id"],
            "s3_key": kw["s3_key"],
            "bucket": kw["bucket"],
            "enterprise_id": kw["enterprise_id"],
            "user_id": kw["user_id"],
            "original_filename": kw["original_filename"],
            "title": kw["title"],
            "file_size": kw["file_size"],
            "content_type": kw["content_type"],
            "part_size_bytes": kw["part_size_bytes"],
            "status": "in_progress",
            "created_at": None,
            "updated_at": None,
        }
        sessions[str(sid)] = row
        return row

    def get_session(session_id):
        return sessions.get(str(session_id))

    def update_session_status(session_id, status):
        key = str(session_id)
        if key in sessions:
            sessions[key]["status"] = status

    def create_document(**kw):
        doc_counter[0] += 1
        return {
            "id": doc_counter[0],
            "enterprise_id": kw["enterprise_id"],
            "title": kw["title"],
            "file_path": kw["file_path"],
            "storage_type": kw.get("storage_type"),
            "original_filename": kw.get("original_filename"),
            "byte_size": kw.get("byte_size"),
            "s3_bucket": kw.get("s3_bucket"),
            "s3_key": kw.get("s3_key"),
        }

    return sessions, create_session, get_session, update_session_status, create_document


@mock_aws
def test_multipart_single_part_and_list_parts_resume(memory_db):
    _, fake_create, fake_get, fake_update, fake_doc = memory_db

    conn = boto3.client("s3", region_name="us-east-1")
    conn.create_bucket(Bucket=os.environ["S3_BUCKET"])

    file_size = 2048
    part_body = b"a" * file_size

    with (
        patch.object(s3mp, "create_session", side_effect=fake_create),
        patch.object(s3mp, "get_session", side_effect=fake_get),
        patch.object(s3mp, "update_session_status", side_effect=fake_update),
        patch.object(s3mp, "create_document", side_effect=fake_doc),
    ):
        init = s3mp.initiate_multipart(
            enterprise_id=1,
            filename="note.txt",
            file_size=file_size,
            content_type="text/plain",
            title="note",
            user_id=None,
        )
        session_id = init["session_id"]

        # 尚未上传 —— ListParts 为空（续传起点）
        assert s3mp.list_uploaded_parts(session_id=session_id) == []

        url = s3mp.presign_upload_part(session_id=session_id, part_number=1)
        put = requests.put(url, data=part_body, timeout=30)
        assert put.status_code == 200, put.text
        etag = put.headers.get("ETag", "").strip('"')

        # 服务端直传分片（与预签名二选一，用于绕过浏览器 CORS）
        init2 = s3mp.initiate_multipart(
            enterprise_id=1,
            filename="server-part.txt",
            file_size=file_size,
            content_type=None,
            title="srv",
            user_id=None,
        )
        sid2 = init2["session_id"]
        srv = s3mp.upload_part_bytes(session_id=sid2, part_number=1, body=part_body)
        assert srv["ETag"]
        assert s3mp.list_uploaded_parts(session_id=sid2)
        s3mp.abort_multipart(session_id=sid2)

        parts = s3mp.list_uploaded_parts(session_id=session_id)
        assert len(parts) == 1
        assert parts[0]["PartNumber"] == 1
        assert parts[0]["ETag"]

        # 模拟断点续传：已有一份 Part，再 list 仍一致
        parts2 = s3mp.list_uploaded_parts(session_id=session_id)
        assert parts2 == parts

        out = s3mp.complete_multipart(
            session_id=session_id,
            parts=[{"PartNumber": 1, "ETag": parts[0]["ETag"]}],
        )
        assert "document" in out
        assert out["document"]["file_path"].startswith("s3://")
        head = conn.head_object(Bucket=init["bucket"], Key=init["key"])
        assert int(head["ContentLength"]) == file_size


@mock_aws
def test_multipart_two_parts_merge(memory_db):
    _, fake_create, fake_get, fake_update, fake_doc = memory_db
    conn = boto3.client("s3", region_name="us-east-1")
    conn.create_bucket(Bucket=os.environ["S3_BUCKET"])

    # 两片：按服务推荐的 part_size（默认 8MiB）切分
    part_size = s3mp.EIGHT_MIB
    tail = 512 * 1024
    file_size = part_size + tail
    body1 = b"b" * part_size
    body2 = b"c" * tail

    with (
        patch.object(s3mp, "create_session", side_effect=fake_create),
        patch.object(s3mp, "get_session", side_effect=fake_get),
        patch.object(s3mp, "update_session_status", side_effect=fake_update),
        patch.object(s3mp, "create_document", side_effect=fake_doc),
    ):
        init = s3mp.initiate_multipart(
            enterprise_id=2,
            filename="big.csv",
            file_size=file_size,
            content_type="text/csv",
            title="big",
            user_id=None,
        )
        session_id = init["session_id"]
        assert init["part_size_bytes"] == part_size

        for pn, chunk in ((1, body1), (2, body2)):
            url = s3mp.presign_upload_part(session_id=session_id, part_number=pn)
            r = requests.put(url, data=chunk, timeout=60)
            assert r.status_code == 200, r.text

        listed = s3mp.list_uploaded_parts(session_id=session_id)
        assert len(listed) == 2

        out = s3mp.complete_multipart(
            session_id=session_id,
            parts=[{"PartNumber": p["PartNumber"], "ETag": p["ETag"]} for p in listed],
        )
        assert out["document"]["byte_size"] == file_size
        obj = conn.get_object(Bucket=init["bucket"], Key=init["key"])
        assert len(obj["Body"].read()) == file_size
