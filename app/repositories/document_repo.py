from app.database import get_db_connection


def create_document(enterprise_id: int, title: str, file_path: str, user_id: int | None = None):
    """Insert a new document and return its record."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO documents (enterprise_id, user_id, title, file_path)
                VALUES (%s, %s, %s, %s)
                RETURNING id, enterprise_id, user_id, title, file_path, created_at, updated_at
                """,
                (enterprise_id, user_id, title, file_path),
            )
            row = cur.fetchone()
            return dict(row) if row else None
