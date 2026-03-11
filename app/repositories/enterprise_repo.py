from app.database import get_db_connection


def get_enterprise_by_id(enterprise_id: int):
    """Fetch an enterprise by ID from PostgreSQL."""
    print("Querying database for enterprise ID:", enterprise_id)  

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, created_at, updated_at FROM enterprises WHERE id = %s",
                (enterprise_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None

