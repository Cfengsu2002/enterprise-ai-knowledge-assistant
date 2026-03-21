"""S3 / S3-compatible (MinIO) configuration from environment."""

import os

from dotenv import load_dotenv

load_dotenv()


def s3_configured() -> bool:
    return bool(os.getenv("S3_BUCKET", "").strip())


def get_bucket() -> str:
    return os.getenv("S3_BUCKET", "").strip()


def get_region() -> str:
    return os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))


def get_endpoint_url() -> str | None:
    url = os.getenv("S3_ENDPOINT_URL", "").strip()
    return url or None


def get_presign_expires_seconds() -> int:
    raw = os.getenv("S3_PRESIGN_EXPIRES_SECONDS", "3600")
    try:
        return max(300, min(int(raw), 86400 * 7))
    except ValueError:
        return 3600
