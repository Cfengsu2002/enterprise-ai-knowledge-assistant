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
    Upload a file, create a document record, then auto chunk + embed into `chunks`
    (unless AUTO_INDEX_ON_UPLOAD=false). On embedding failure, upload still succeeds;
    response may include `indexing_error`.
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
            content_type=file.content_type,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return document
