import os
import uuid
from pathlib import Path

from app.repositories.document_repo import create_document

# Directory where uploaded files are stored (relative to project root)
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads"))

# Allowed extensions (optional safety). Empty = allow all.
ALLOWED_EXTENSIONS = {"pdf", "txt", "md", "doc", "docx", "csv", "json"}


def _ensure_upload_dir(enterprise_id: int) -> Path:
    """Ensure per-enterprise upload directory exists."""
    dir_path = UPLOAD_DIR / str(enterprise_id)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def _safe_filename(original_filename: str) -> str:
    """Generate a unique filename while keeping extension."""
    ext = Path(original_filename).suffix.lower().lstrip(".")
    if ALLOWED_EXTENSIONS and ext and ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"File type not allowed: {ext}")
    unique = uuid.uuid4().hex[:12]
    return f"{unique}_{original_filename}" if original_filename else f"{unique}"


def upload_file(
    file_content: bytes,
    filename: str,
    enterprise_id: int,
    title: str | None = None,
    user_id: int | None = None,
    content_type: str | None = None,
) -> dict:
    """
    Save file to disk and create a document record.
    Returns the created document as a dict.
    """
    if not filename or not filename.strip():
        raise ValueError("Filename is required")

    safe_name = _safe_filename(filename.strip())
    dir_path = _ensure_upload_dir(enterprise_id)
    file_path = dir_path / safe_name

    file_path.write_bytes(file_content)
    # Store path relative to UPLOAD_DIR for portability
    relative_path = str(Path(str(enterprise_id)) / safe_name)

    doc_title = (title or filename).strip() or safe_name
    record = create_document(
        enterprise_id=enterprise_id,
        title=doc_title,
        file_path=relative_path,
        user_id=user_id,
        storage_type="local",
        original_filename=filename.strip(),
        content_type=content_type,
        byte_size=len(file_content),
        file_metadata={"storage": "local_disk"},
    )
    if not record:
        file_path.unlink(missing_ok=True)
        raise RuntimeError("Failed to create document record")
    return record
