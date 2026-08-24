"""
OCR Service - AWS Textract / PaddleOCR / pytesseract
"""

from PIL import Image
import io
from app.config import settings
from app.lib.storage_service import storage_service


async def extract_text_from_document(file_url: str) -> tuple[str, int]:
    """
    Extract text from document using configured OCR service

    Returns:
        tuple[str, int]: (extracted_text, page_count)
    """
    if settings.OCR_SERVICE == "textract":
        return await extract_text_with_textract(file_url)
    elif settings.OCR_SERVICE == "paddleocr":
        return await extract_text_with_paddleocr(file_url)
    elif settings.OCR_SERVICE == "pytesseract":
        return await extract_text_with_tesseract(file_url)
    else:
        raise ValueError(f"Unknown OCR service: {settings.OCR_SERVICE}")


async def extract_text_with_textract(file_url: str) -> tuple[str, int]:
    """
    Extract text using AWS Textract

    Returns:
        tuple[str, int]: (extracted_text, page_count)
    """
    # Download file from storage
    file_bytes = await storage_service.download_file(file_url)

    # 惰性匯入 boto3(僅 Textract 需要),與 pytesseract/paddleocr 一致,
    # 避免在未安裝 boto3 的環境匯入整個 services 套件時失敗
    import boto3

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
    page_count = 0
    for block in response["Blocks"]:
        if block["BlockType"] == "PAGE":
            page_count += 1
        elif block["BlockType"] == "LINE":
            text_lines.append(block["Text"])

    return "\n".join(text_lines), max(page_count, 1)


async def extract_text_with_tesseract(file_url: str) -> tuple[str, int]:
    """
    Extract text using pytesseract (free alternative)

    Returns:
        tuple[str, int]: (extracted_text, page_count)
    """
    try:
        import pytesseract
        from pdf2image import convert_from_bytes
    except ImportError:
        raise ImportError("pytesseract or pdf2image not installed")

    # Download file from storage
    file_bytes = await storage_service.download_file(file_url)

    # Check if PDF
    if file_url.lower().endswith('.pdf'):
        # Convert PDF to images
        images = convert_from_bytes(file_bytes)
        page_count = len(images)

        # OCR each page
        text_parts = []
        for i, image in enumerate(images, 1):
            text = pytesseract.image_to_string(image, lang="chi_tra")
            text_parts.append(f"--- Page {i}/{page_count} ---\n{text}")

        return "\n\n".join(text_parts), page_count
    else:
        # Direct image OCR with gentle preprocessing
        from PIL import ImageEnhance

        image = Image.open(io.BytesIO(file_bytes))

        # Image preprocessing for better OCR (gentle approach - tested best for ID cards)
        # 1. Convert to grayscale
        image = image.convert('L')

        # 2. Resize to higher resolution FIRST (before any enhancement)
        # Higher resolution helps OCR recognize small text
        width, height = image.size
        if width < 2000 or height < 2000:
            scale = max(2000 / width, 2000 / height)
            new_size = (int(width * scale), int(height * scale))
            image = image.resize(new_size, Image.Resampling.LANCZOS)

        # 3. Very gentle contrast enhancement (1.3x)
        # Helps with faded text without over-processing
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.3)

        # 4. Slight sharpness boost (1.5x)
        # Helps with slightly blurry images
        sharpener = ImageEnhance.Sharpness(image)
        image = sharpener.enhance(1.5)

        # OCR with optimized Tesseract configuration
        # --psm 6: Assume a single uniform block of text
        # --oem 1: Use LSTM OCR engine only (better for Chinese)
        custom_config = r'--oem 1 --psm 6'
        text = pytesseract.image_to_string(image, lang="chi_tra", config=custom_config)

        return text, 1


async def extract_text_with_paddleocr(file_url: str) -> tuple[str, int]:
    """
    Extract text using PaddleOCR (optimized for Chinese)

    Returns:
        tuple[str, int]: (extracted_text, page_count)
    """
    try:
        from paddleocr import PaddleOCR
        from pdf2image import convert_from_bytes
    except ImportError:
        raise ImportError("PaddleOCR or pdf2image not installed")

    # Initialize PaddleOCR
    # paddleocr 3.x API:use_angle_cls / use_gpu / show_log 已移除。
    # enable_mkldnn=False 為必要——paddle 3.x 的 PIR 執行器與 oneDNN 有功能缺口,
    # 開啟時推論會拋 NotImplementedError(詳見 EngineManager._ensure_paddleocr 註解)。
    ocr = PaddleOCR(
        lang=settings.OCR_PADDLEOCR_LANG,
        enable_mkldnn=False,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=True,
    )

    # Download file from storage
    file_bytes = await storage_service.download_file(file_url)

    # Check if PDF
    if file_url.lower().endswith('.pdf'):
        # Convert PDF to images
        images = convert_from_bytes(file_bytes)
        page_count = len(images)

        # OCR each page
        text_parts = []
        for i, image in enumerate(images, 1):
            # PaddleOCR requires numpy array or image path
            import numpy as np
            img_array = np.array(image)

            # Run OCR(3.x 為 predict();回傳 list[dict] 而非巢狀 bbox 陣列)
            result = ocr.predict(img_array)

            # Extract text from result
            page_text = []
            for page in (result or []):
                page_text.extend(page.get("rec_texts") or [])

            text_parts.append(f"--- Page {i}/{page_count} ---\n" + "\n".join(page_text))

        return "\n\n".join(text_parts), page_count
    else:
        # Direct image OCR with preprocessing
        from PIL import ImageEnhance
        import numpy as np

        image = Image.open(io.BytesIO(file_bytes))

        # Image preprocessing (same as Tesseract for consistency)
        # 1. Convert to RGB (PaddleOCR works better with RGB)
        if image.mode != 'RGB':
            image = image.convert('RGB')

        # 2. Resize if too small
        width, height = image.size
        if width < 1000 or height < 1000:
            scale = max(1000 / width, 1000 / height)
            new_size = (int(width * scale), int(height * scale))
            image = image.resize(new_size, Image.Resampling.LANCZOS)

        # Convert to numpy array for PaddleOCR
        img_array = np.array(image)

        # Run OCR(3.x 為 predict())
        result = ocr.predict(img_array)

        # Extract text from result
        text_lines = []
        for page in (result or []):
            text_lines.extend(page.get("rec_texts") or [])

        return "\n".join(text_lines), 1
