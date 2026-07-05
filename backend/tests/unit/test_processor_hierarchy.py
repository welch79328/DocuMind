"""
測試處理器契約重構:統一 analyze 模板 + OCR型/影像理解型(任務 8.1)

- DocumentProcessor:抽象 analyze + 具體 process 模板
- OcrDocumentProcessor:4 步驟抽象方法 + 具體 analyze(輸出保留既有 PageResult 欄位 + field_confidences/overall_confidence)
- ImageUnderstandingProcessor:抽象 understand + analyze(承載非 OCR 結果)

對應需求: 2.1, 5.1
"""

import io
from abc import ABC

import numpy as np
import pytest
from PIL import Image

from app.lib.multi_type_ocr.processor import (
    DocumentProcessor,
    OcrDocumentProcessor,
    ImageUnderstandingProcessor,
)


def _png_bytes():
    img = Image.fromarray(np.zeros((60, 60, 3), dtype=np.uint8))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# --- OCR 型測試替身 ------------------------------------------------------- #
class _OcrDouble(OcrDocumentProcessor):
    async def preprocess(self, image):
        return image

    async def extract_text(self, image):
        return ("OCR文字", 0.72)

    async def postprocess(self, text, confidence, image_data=None):
        return (text + "_fixed", {"typo_fixes": 1})

    async def extract_fields(self, text, image_data=None, enable_llm=False, few_shot=None):
        return {"area": "128.45", "field_confidences": {"area": 0.6}}


# --- 影像理解型測試替身 --------------------------------------------------- #
class _ImageDouble(ImageUnderstandingProcessor):
    async def understand(self, image_data, few_shot=None):
        return {
            "defect_labels": ["漏水"],
            "description": "牆面滲水",
            "confidence": 0.83,
        }


class TestHierarchy:
    def test_document_processor_is_abstract_with_analyze(self):
        assert issubclass(DocumentProcessor, ABC)
        assert hasattr(DocumentProcessor, "analyze")
        assert hasattr(DocumentProcessor, "process")
        with pytest.raises(TypeError):
            DocumentProcessor()  # type: ignore

    def test_ocr_processor_defines_four_steps(self):
        for m in ("preprocess", "extract_text", "postprocess", "extract_fields"):
            assert hasattr(OcrDocumentProcessor, m)

    def test_image_processor_defines_understand(self):
        assert hasattr(ImageUnderstandingProcessor, "understand")

    def test_both_are_document_processor(self):
        assert issubclass(OcrDocumentProcessor, DocumentProcessor)
        assert issubclass(ImageUnderstandingProcessor, DocumentProcessor)


class TestOcrAnalyze:
    async def test_process_produces_backward_compatible_result(self):
        result = await _OcrDouble().process(
            file_contents=_png_bytes(), filename="t.png",
            page_number=3, total_pages=5, enable_llm=False,
        )
        # 既有欄位保留
        for key in (
            "page_number", "original_image", "ocr_raw", "rule_postprocessed",
            "llm_postprocessed", "structured_data", "accuracy", "processing_steps",
        ):
            assert key in result
        assert result["page_number"] == 3
        assert result["ocr_raw"]["text"] == "OCR文字"
        assert result["ocr_raw"]["confidence"] == 0.72

    async def test_result_has_confidence_fields(self):
        result = await _OcrDouble().process(
            file_contents=_png_bytes(), filename="t.png",
            page_number=1, total_pages=1, enable_llm=False,
        )
        # 新增:整體信心度與欄位信心度
        assert result["overall_confidence"] == 0.72
        assert result["field_confidences"] == {"area": 0.6}


class TestImageAnalyze:
    async def test_image_understanding_carries_non_ocr_result(self):
        result = await _ImageDouble().process(
            file_contents=_png_bytes(), filename="photo.jpg",
            page_number=1, total_pages=1, enable_llm=True,
        )
        # 承載影像理解結果於 structured_data,非 OCR
        assert result["structured_data"]["defect_labels"] == ["漏水"]
        assert result["structured_data"]["description"] == "牆面滲水"
        assert result["overall_confidence"] == 0.83
        assert result["ocr_raw"] is None
        assert result["page_number"] == 1
