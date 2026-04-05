from psycopg2.extras import Json

from app.database import get_db_connection


def get_document_by_id(document_id: int) -> dict | None:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, enterprise_id, user_id, title, file_path,
                       storage_type, original_filename, content_type, byte_size,
                       s3_bucket, s3_key, file_metadata,
                       created_at, updated_at
                FROM documents
                WHERE id = %s
                """,
                (document_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def create_document(
    enterprise_id: int,
    title: str,
    file_path: str,
    user_id: int | None = None,
    *,
    storage_type: str = "local",
    original_filename: str | None = None,
    content_type: str | None = None,
    byte_size: int | None = None,
    s3_bucket: str | None = None,
    s3_key: str | None = None,
    file_metadata: dict | None = None,
):
    """
    Insert a new document. file_path is the canonical link (local relative path or s3://bucket/key).
    """
    meta = file_metadata if file_metadata is not None else {}
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO documents (
                    enterprise_id, user_id, title, file_path,
                    storage_type, original_filename, content_type, byte_size,
                    s3_bucket, s3_key, file_metadata
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, enterprise_id, user_id, title, file_path,
                          storage_type, original_filename, content_type, byte_size,
                          s3_bucket, s3_key, file_metadata,
                          created_at, updated_at
                """,
                (
                    enterprise_id,
                    user_id,
                    title,
                    file_path,
                    storage_type,
                    original_filename,
                    content_type,
                    byte_size,
                    s3_bucket,
                    s3_key,
                    Json(meta),
                ),
            )
            row = cur.fetchone()
            return dict(row) if row else None
