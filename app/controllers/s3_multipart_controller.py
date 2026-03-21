"""S3 multipart upload API: presigned part URLs + ListParts for resume."""

from botocore.exceptions import ClientError, NoCredentialsError
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.config.s3_settings import get_presign_expires_seconds, s3_configured
from app.services import s3_multipart_service as s3mp

router = APIRouter(prefix="/upload/s3/multipart", tags=["upload-s3-multipart"])


class MultipartInitBody(BaseModel):
    enterprise_id: int = Field(..., ge=1)
    filename: str = Field(..., min_length=1, max_length=500)
    file_size: int = Field(..., ge=1, le=5 * 1024**4)
    content_type: str | None = None
    title: str | None = None
    user_id: int | None = None


class MultipartCompleteBody(BaseModel):
    session_id: str = Field(..., min_length=1)
    parts: list[dict] = Field(
        ...,
        description="S3 parts: [{PartNumber, ETag}, ...] sorted by PartNumber",
    )


class MultipartAbortBody(BaseModel):
    session_id: str = Field(..., min_length=1)


@router.post("/init")
def multipart_init(body: MultipartInitBody):
    if not s3_configured():
        raise HTTPException(
            status_code=503,
            detail="S3 multipart upload is disabled. Set S3_BUCKET and AWS credentials.",
        )
    try:
        return s3mp.initiate_multipart(
            enterprise_id=body.enterprise_id,
            filename=body.filename,
            file_size=body.file_size,
            content_type=body.content_type,
            title=body.title,
            user_id=body.user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except NoCredentialsError as e:
        raise HTTPException(
            status_code=503,
            detail=(
                "AWS 凭证未进入后端容器：在项目根 .env 填写 AWS_ACCESS_KEY_ID / "
                "AWS_SECRET_ACCESS_KEY（勿留空），保存后执行 docker compose up -d --build"
            ),
        ) from e
    except ClientError as e:
        err = e.response.get("Error", {}) if e.response else {}
        raise HTTPException(
            status_code=502,
            detail=f"S3: {err.get('Code', 'ClientError')}: {err.get('Message', str(e))}",
        ) from e
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/part-url")
def multipart_part_url(
    session_id: str = Query(..., description="Session id from /init"),
    part_number: int = Query(..., ge=1, le=s3mp.MAX_PARTS),
):
    if not s3_configured():
        raise HTTPException(status_code=503, detail="S3 is not configured")
    try:
        url = s3mp.presign_upload_part(session_id=session_id, part_number=part_number)
        return {"url": url, "expires_in_seconds": get_presign_expires_seconds()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except NoCredentialsError as e:
        raise HTTPException(status_code=503, detail="AWS 凭证未配置，见 /upload/s3/multipart/init 说明") from e
    except ClientError as e:
        err = e.response.get("Error", {}) if e.response else {}
        raise HTTPException(
            status_code=502,
            detail=f"S3: {err.get('Code', '')}: {err.get('Message', str(e))}",
        ) from e


@router.post("/part")
async def multipart_upload_part(
    request: Request,
    session_id: str = Query(..., description="Session id from /init"),
    part_number: int = Query(..., ge=1, le=s3mp.MAX_PARTS),
):
    """
    Upload raw bytes for one part (server forwards to S3). Bypasses browser CORS to S3.
    Body: application/octet-stream, length must match the part size for this session.
    """
    if not s3_configured():
        raise HTTPException(status_code=503, detail="S3 is not configured")
    body = await request.body()
    try:
        return s3mp.upload_part_bytes(
            session_id=session_id, part_number=part_number, body=body
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except NoCredentialsError as e:
        raise HTTPException(status_code=503, detail="AWS 凭证未配置") from e
    except ClientError as e:
        err = e.response.get("Error", {}) if e.response else {}
        raise HTTPException(
            status_code=502,
            detail=f"S3: {err.get('Code', '')}: {err.get('Message', str(e))}",
        ) from e


@router.get("/parts")
def multipart_list_parts(session_id: str = Query(...)):
    """Return parts already stored in S3 (for resume after disconnect)."""
    if not s3_configured():
        raise HTTPException(status_code=503, detail="S3 is not configured")
    try:
        parts = s3mp.list_uploaded_parts(session_id=session_id)
        return {"parts": parts}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except NoCredentialsError as e:
        raise HTTPException(status_code=503, detail="AWS 凭证未配置") from e
    except ClientError as e:
        err = e.response.get("Error", {}) if e.response else {}
        raise HTTPException(
            status_code=502,
            detail=f"S3: {err.get('Code', '')}: {err.get('Message', str(e))}",
        ) from e


@router.post("/complete")
def multipart_complete(body: MultipartCompleteBody):
    if not s3_configured():
        raise HTTPException(status_code=503, detail="S3 is not configured")
    try:
        return s3mp.complete_multipart(session_id=body.session_id, parts=body.parts)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except NoCredentialsError as e:
        raise HTTPException(status_code=503, detail="AWS 凭证未配置") from e
    except ClientError as e:
        err = e.response.get("Error", {}) if e.response else {}
        raise HTTPException(
            status_code=502,
            detail=f"S3: {err.get('Code', '')}: {err.get('Message', str(e))}",
        ) from e
    except Exception as e:
        # 未单独映射的异常（常见：数据库 schema/约束、ETag 格式、BotoCore 参数错误）
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/abort")
def multipart_abort(body: MultipartAbortBody):
    if not s3_configured():
        raise HTTPException(status_code=503, detail="S3 is not configured")
    try:
        s3mp.abort_multipart(session_id=body.session_id)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except NoCredentialsError as e:
        raise HTTPException(status_code=503, detail="AWS 凭证未配置") from e
    except ClientError as e:
        err = e.response.get("Error", {}) if e.response else {}
        raise HTTPException(
            status_code=502,
            detail=f"S3: {err.get('Code', '')}: {err.get('Message', str(e))}",
        ) from e
