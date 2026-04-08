"""
S3 / Cloudflare R2 Service
"""

import boto3
from botocore.config import Config
from app.config import settings
import uuid


def get_s3_client():
    """Get S3/R2 client"""
    client_config = {
        "service_name": "s3",
        "aws_access_key_id": settings.S3_ACCESS_KEY,
        "aws_secret_access_key": settings.S3_SECRET_KEY,
        "region_name": settings.S3_REGION,
        "config": Config(signature_version="s3v4")
    }

    # Use custom endpoint for Cloudflare R2
    if settings.S3_ENDPOINT_URL:
        client_config["endpoint_url"] = settings.S3_ENDPOINT_URL

    return boto3.client(**client_config)


async def upload_file_to_s3(
    filename: str,
    file_content: bytes,
    path_prefix: str = "uploads",
    acl: str = "public-read"
) -> str:
    """
    上傳檔案至 S3 並回傳 URL

    Args:
        filename: 原始檔名
        file_content: 檔案內容
        path_prefix: S3 路徑前綴（例如 uploads/ocr_transcripts）
        acl: 存取權限（public-read 或 private）

    Returns:
        檔案的 CDN URL 或 S3 URL
    """
    s3_client = get_s3_client()

    # 產生唯一檔名
    file_extension = filename.rsplit(".", 1)[-1] if "." in filename else ""
    unique_filename = f"{uuid.uuid4()}.{file_extension}" if file_extension else str(uuid.uuid4())

    # 組合完整 S3 key
    s3_key = f"{path_prefix}/{unique_filename}"

    # 上傳
    put_params = {
        "Bucket": settings.S3_BUCKET,
        "Key": s3_key,
        "Body": file_content,
    }
    if acl:
        put_params["ACL"] = acl

    s3_client.put_object(**put_params)

    # 回傳 URL
    if settings.S3_CDN_URL:
        return f"{settings.S3_CDN_URL.rstrip('/')}/{s3_key}"
    elif settings.S3_ENDPOINT_URL:
        return f"{settings.S3_ENDPOINT_URL}/{settings.S3_BUCKET}/{s3_key}"
    else:
        return f"https://{settings.S3_BUCKET}.s3.{settings.S3_REGION}.amazonaws.com/{s3_key}"


async def download_file_from_s3(file_url: str) -> bytes:
    """
    從 S3 下載檔案
    """
    s3_client = get_s3_client()

    # 從 URL 提取 key
    # 支援 CDN URL 和 S3 URL
    if settings.S3_CDN_URL and file_url.startswith(settings.S3_CDN_URL):
        key = file_url.replace(settings.S3_CDN_URL.rstrip('/') + '/', '')
    else:
        key = file_url.split("/", 3)[-1] if "/" in file_url else file_url

    response = s3_client.get_object(
        Bucket=settings.S3_BUCKET,
        Key=key
    )

    return response["Body"].read()
