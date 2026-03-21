from uuid import UUID

from app.database import get_db_connection


def create_session(
    *,
    s3_upload_id: str,
    s3_key: str,
    bucket: str,
    enterprise_id: int,
    original_filename: str,
    file_size: int,
    part_size_bytes: int,
    title: str | None,
    user_id: int | None,
    content_type: str | None,
) -> dict | None:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO multipart_upload_sessions (
                    s3_upload_id, s3_key, bucket, enterprise_id, user_id,
                    original_filename, title, file_size, content_type,
                    part_size_bytes, status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'in_progress')
                RETURNING id, s3_upload_id, s3_key, bucket, enterprise_id, user_id,
                          original_filename, title, file_size, content_type,
                          part_size_bytes, status, created_at
                """,
                (
                    s3_upload_id,
                    s3_key,
                    bucket,
                    enterprise_id,
                    user_id,
                    original_filename,
                    title,
                    file_size,
                    content_type,
                    part_size_bytes,
                ),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def get_session(session_id: UUID) -> dict | None:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, s3_upload_id, s3_key, bucket, enterprise_id, user_id,
                       original_filename, title, file_size, content_type,
                       part_size_bytes, status, created_at, updated_at
                FROM multipart_upload_sessions
                WHERE id = %s
                """,
                (str(session_id),),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def update_session_status(session_id: UUID, status: str) -> None:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE multipart_upload_sessions
                SET status = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (status, str(session_id)),
            )
