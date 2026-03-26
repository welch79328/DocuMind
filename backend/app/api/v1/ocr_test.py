"""
OCR Testing and Validation API Routes
用於測試和驗證 OCR 效果的專用 API
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from PIL import Image
import fitz
from io import BytesIO
import os
from typing import Optional, List

from app.lib.ocr_enhanced.preprocessor import TranscriptPreprocessor
from app.lib.ocr_enhanced.config import PreprocessConfig
from app.lib.ocr_enhanced.engine_manager import EngineManager
from app.lib.ocr_enhanced.postprocessor import TranscriptPostprocessor

router = APIRouter()


@router.post("/test")
async def test_ocr(
    file: UploadFile = File(...),
    enable_llm: bool = True,
    ground_truth: Optional[str] = None,
    page_number: Optional[int] = None  # None = 處理所有頁面
):
    """
    測試 OCR 效果並返回對比結果

    Args:
        file: PDF 或圖片檔案
        enable_llm: 是否啟用 LLM 後處理
        ground_truth: 可選的標準答案（用於計算準確率）
        page_number: 頁碼（None = 處理所有頁，預設）

    Returns:
        {
            "file_name": "檔案名稱",
            "total_pages": 3,
            "pages": [頁面結果列表]
        }
    """
    try:
        # 讀取檔案內容
        contents = await file.read()

        # 判斷檔案類型
        is_pdf = file.filename.lower().endswith('.pdf')

        if is_pdf:
            # 取得 PDF 總頁數
            doc = fitz.open(stream=contents, filetype="pdf")
            total_pages = len(doc)
            doc.close()

            # 決定要處理哪些頁面
            if page_number is not None:
                # 處理單頁
                pages_to_process = [page_number]
            else:
                # 處理所有頁
                pages_to_process = list(range(1, total_pages + 1))
        else:
            # 圖片只有一頁
            total_pages = 1
            pages_to_process = [1]

        # 處理每一頁
        results = []
        for page_num in pages_to_process:
            page_result = await _process_single_page(
                contents,
                file.filename,
                page_num,
                total_pages,
                enable_llm,
                ground_truth,
                is_pdf
            )
            results.append(page_result)

        # 返回結果
        return {
            "file_name": file.filename,
            "total_pages": total_pages,
            "pages": results
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR 測試失敗: {str(e)}")


async def _process_single_page(
    file_contents: bytes,
    filename: str,
    page_number: int,
    total_pages: int,
    enable_llm: bool,
    ground_truth: Optional[str],
    is_pdf: bool
) -> dict:
    """處理單一頁面的 OCR"""
    import base64
    import difflib

    # 提取圖片
    if is_pdf:
        pil_image, _ = await _extract_pdf_page(file_contents, page_number)
    else:
        pil_image = Image.open(BytesIO(file_contents))

    # 步驟 1: 預處理
    config = PreprocessConfig()
    preprocessor = TranscriptPreprocessor(config)
    processed, _ = await preprocessor.preprocess(pil_image)

    # 步驟 2: OCR 辨識
    engine_manager = EngineManager(engines=["tesseract"], parallel=False)
    raw_text, confidence, _ = await engine_manager.extract_text_multi_engine(processed)

    # 步驟 3: 規則後處理
    rule_postprocessor = TranscriptPostprocessor(
        enable_typo_fix=True,
        enable_format_correction=True,
        enable_llm=False
    )
    rule_text, rule_stats = await rule_postprocessor.postprocess(raw_text, confidence)

    # 步驟 4: LLM 後處理（可選，支援視覺修正）
    llm_text = None
    llm_stats = None
    llm_used = False

    if enable_llm:
        openai_key = os.getenv("OPENAI_API_KEY")
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")

        if openai_key or anthropic_key:
            llm_provider = "openai" if openai_key else "anthropic"
            llm_postprocessor = TranscriptPostprocessor(
                enable_typo_fix=True,
                enable_format_correction=True,
                enable_llm=True,
                llm_provider=llm_provider,
                llm_strategy="auto"
            )

            # 將圖片轉換為 base64（供 LLM 視覺修正使用）
            buffered_for_llm = BytesIO()
            pil_image.save(buffered_for_llm, format="PNG")
            img_base64_for_llm = base64.b64encode(buffered_for_llm.getvalue()).decode()

            # 調用 LLM 修正（傳入圖片）
            llm_text, llm_stats = await llm_postprocessor.postprocess(
                raw_text,
                confidence,
                image_data=img_base64_for_llm
            )
            llm_used = llm_stats.get("llm_used", False)

    # 步驟 5: 計算準確率
    accuracy = None
    if ground_truth:
        def calc_accuracy(gt: str, text: str) -> float:
            gt_clean = ''.join(gt.split())
            text_clean = ''.join(text.split())
            matcher = difflib.SequenceMatcher(None, gt_clean, text_clean)
            return matcher.ratio() * 100

        raw_portion = raw_text[:len(raw_text)//3]
        rule_portion = rule_text[:len(rule_text)//3]
        llm_portion = llm_text[:len(llm_text)//3] if llm_text else None

        accuracy = {
            "raw": round(calc_accuracy(ground_truth, raw_portion), 2),
            "rule": round(calc_accuracy(ground_truth, rule_portion), 2),
            "llm": round(calc_accuracy(ground_truth, llm_portion), 2) if llm_portion else None
        }

    # 步驟 6: 轉換圖片為 base64
    buffered = BytesIO()
    pil_image.save(buffered, format="PNG")
    img_base64 = base64.b64encode(buffered.getvalue()).decode()

    # 返回結果
    return {
        "page_number": page_number,
        "original_image": f"data:image/png;base64,{img_base64}",
        "ocr_raw": {
            "text": raw_text,
            "confidence": round(confidence, 4)
        },
        "rule_postprocessed": {
            "text": rule_text,
            "stats": rule_stats
        },
        "llm_postprocessed": {
            "text": llm_text,
            "stats": llm_stats,
            "used": llm_used
        } if enable_llm and llm_text else None,
        "accuracy": accuracy,
        "processing_steps": {
            "1_ocr_engine": "Tesseract",
            "2_rule_processing": "✓ 完成",
            "3_llm_processing": "✓ 完成" if (enable_llm and llm_used) else "⊗ 未使用"
        }
    }


async def _extract_pdf_page(pdf_bytes: bytes, page_number: int = 1) -> tuple[Image.Image, int]:
    """從 PDF 提取指定頁為圖片

    Args:
        pdf_bytes: PDF 檔案的 bytes
        page_number: 頁碼（從 1 開始）

    Returns:
        (PIL Image, 總頁數)
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_pages = len(doc)

    # 驗證頁碼
    if page_number < 1 or page_number > total_pages:
        doc.close()
        raise HTTPException(
            status_code=400,
            detail=f"無效的頁碼。PDF 共有 {total_pages} 頁，請選擇 1-{total_pages} 之間的頁碼"
        )

    page = doc[page_number - 1]  # 轉換為 0-based index
    mat = fitz.Matrix(300/72, 300/72)  # 300 DPI
    pix = page.get_pixmap(matrix=mat)
    img_data = pix.tobytes("png")
    pil_image = Image.open(BytesIO(img_data))
    doc.close()
    return pil_image, total_pages
