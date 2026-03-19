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


async def upload_file_to_s3(filename: str, file_content: bytes) -> str:
    """
    Upload file to S3/R2 and return URL
    """
    s3_client = get_s3_client()

    # Generate unique filename
    file_extension = filename.split(".")[-1]
    unique_filename = f"{uuid.uuid4()}.{file_extension}"

    # Upload file
    s3_client.put_object(
        Bucket=settings.S3_BUCKET,
        Key=unique_filename,
        Body=file_content
    )

    # Generate URL
    if settings.S3_ENDPOINT_URL:
        # Cloudflare R2 URL
        file_url = f"{settings.S3_ENDPOINT_URL}/{settings.S3_BUCKET}/{unique_filename}"
    else:
        # AWS S3 URL
        file_url = f"https://{settings.S3_BUCKET}.s3.{settings.S3_REGION}.amazonaws.com/{unique_filename}"

    return file_url


async def download_file_from_s3(file_url: str) -> bytes:
    """
    Download file from S3/R2
    """
    s3_client = get_s3_client()

    # Extract key from URL
    key = file_url.split("/")[-1]

    # Download file
    response = s3_client.get_object(
        Bucket=settings.S3_BUCKET,
        Key=key
    )

    return response["Body"].read()
