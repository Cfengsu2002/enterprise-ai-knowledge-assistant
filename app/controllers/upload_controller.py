from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.services.upload_service import upload_file

router = APIRouter()


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    enterprise_id: int = Form(...),
    title: str | None = Form(None),
    user_id: int | None = Form(None),
):
    """
    Upload a file and create a document record.
    Required: file, enterprise_id.
    Optional: title (defaults to filename), user_id.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")
    try:
        content = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {e}") from e
    try:
        document = upload_file(
            file_content=content,
            filename=file.filename,
            enterprise_id=enterprise_id,
            title=title,
            user_id=user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return document
