"""
OCR Service - AWS Textract / pytesseract
"""

import boto3
from PIL import Image
import io
from app.config import settings
from app.lib.s3_service import download_file_from_s3


async def extract_text_from_document(file_url: str) -> str:
    """
    Extract text from document using configured OCR service
    """
    if settings.OCR_SERVICE == "textract":
        return await extract_text_with_textract(file_url)
    elif settings.OCR_SERVICE == "pytesseract":
        return await extract_text_with_tesseract(file_url)
    else:
        raise ValueError(f"Unknown OCR service: {settings.OCR_SERVICE}")


async def extract_text_with_textract(file_url: str) -> str:
    """
    Extract text using AWS Textract
    """
    # Download file from S3
    file_bytes = await download_file_from_s3(file_url)

    # Create Textract client
    textract_client = boto3.client(
        "textract",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION
    )

    # Call Textract
    response = textract_client.detect_document_text(
        Document={"Bytes": file_bytes}
    )

    # Extract text from response
    text_lines = []
    for block in response["Blocks"]:
        if block["BlockType"] == "LINE":
            text_lines.append(block["Text"])

    return "\n".join(text_lines)


async def extract_text_with_tesseract(file_url: str) -> str:
    """
    Extract text using pytesseract (free alternative)
    """
    try:
        import pytesseract
    except ImportError:
        raise ImportError("pytesseract not installed. Run: pip install pytesseract")

    # Download file from S3
    file_bytes = await download_file_from_s3(file_url)

    # Open image
    image = Image.open(io.BytesIO(file_bytes))

    # OCR with pytesseract (Traditional Chinese)
    text = pytesseract.image_to_string(image, lang="chi_tra")

    return text
