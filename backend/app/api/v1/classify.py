"""
文件類型建議 API(輔助)

使用者未指定型別時,提供建議型別供確認;最終仍以使用者指定為準(需求 1.3)。
"""

import io
import logging

from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse
from PIL import Image

from app.lib.ocr_enhanced.document_classifier import DocumentClassifier

logger = logging.getLogger(__name__)

router = APIRouter()


def _load_first_image(contents: bytes, filename: str) -> Image.Image:
    """載入影像(PDF 取第一頁);供分類器使用"""
    if filename.lower().endswith(".pdf"):
        import fitz
        doc = fitz.open(stream=contents, filetype="pdf")
        try:
            page = doc[0]
            pix = page.get_pixmap()
            return Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        finally:
            doc.close()
    return Image.open(io.BytesIO(contents)).convert("RGB")


@router.post("", summary="建議文件類型")
async def classify_document(file: UploadFile = File(..., description="PDF 或圖片")):
    """
    依上傳文件建議類型(供使用者確認)。回傳 suggested_document_type 與 confidence;
    無法判定時 suggested_document_type 為 null。
    """
    try:
        contents = await file.read()
        image = _load_first_image(contents, file.filename or "")
        suggested, confidence = await DocumentClassifier().suggest(image)
        return {
            "suggested_document_type": suggested.value if suggested is not None else None,
            "confidence": confidence,
        }
    except Exception as e:
        logger.warning(f"文件類型建議失敗: {e}")
        return JSONResponse(
            status_code=200,
            content={"suggested_document_type": None, "confidence": 0.0},
        )
