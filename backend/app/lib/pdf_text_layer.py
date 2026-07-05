"""
PDF 文字層偵測與分段

合約 PDF 可能含文字層(數位產生)或為純掃描。含文字層時直接抽取文字並分段
(保留頁碼),可略過 OCR、大幅省成本;純掃描則維持 OCR 流程。

PyMuPDF(fitz)惰性載入;未安裝或失敗時 has_text_layer 回 False(降級為 OCR)。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# 判定含文字層的最低字元數(避免掃描 PDF 夾帶少量浮水印文字誤判)
_MIN_TEXT_CHARS = 20


def _open_pdf(file_contents: bytes):
    """開啟 PDF(惰性載入 fitz)"""
    import fitz
    return fitz.open(stream=file_contents, filetype="pdf")


def has_text_layer(file_contents: bytes, min_chars: int = _MIN_TEXT_CHARS) -> bool:
    """
    偵測 PDF 是否含可抽取的文字層。

    Returns:
        True 表示含足量文字層(可略過 OCR);False 表示純掃描或不可用(走 OCR)。
    """
    try:
        doc = _open_pdf(file_contents)
    except Exception as e:  # 未安裝 fitz / 開檔失敗 → 降級為 OCR
        logger.warning(f"PDF 文字層偵測不可用,降級為 OCR: {e}")
        return False

    try:
        total = sum(len((page.get_text() or "").strip()) for page in doc)
        return total >= min_chars
    except Exception as e:  # pragma: no cover
        logger.warning(f"PDF 文字層偵測失敗,降級為 OCR: {e}")
        return False
    finally:
        doc.close()


def extract_text_layer_pages(file_contents: bytes) -> List[Dict[str, Any]]:
    """
    逐頁抽取文字層並分段(保留頁碼),回傳 PageResult 相容的頁面清單。

    每頁標記 text_layer=True(表示略過 OCR)、信心度 1.0(文字層為精確文字)。
    """
    doc = _open_pdf(file_contents)
    try:
        pages: List[Dict[str, Any]] = []
        for index, page in enumerate(doc):
            text = page.get_text() or ""
            pages.append({
                "page_number": index + 1,
                "ocr_raw": {"text": text, "confidence": 1.0},
                "rule_postprocessed": {"text": text, "stats": {}},
                "llm_postprocessed": None,
                "structured_data": None,
                "field_confidences": {},
                "overall_confidence": 1.0,
                "text_layer": True,
            })
        return pages
    finally:
        doc.close()
