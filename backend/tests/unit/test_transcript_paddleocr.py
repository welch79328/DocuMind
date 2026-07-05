"""
測試謄本啟用 PaddleOCR 與浮水印前處理(任務 10.1)

- EngineManager 惰性載入 PaddleOCR(未安裝時建構不 crash)
- TranscriptProcessor 依設定啟用 PaddleOCR(取代硬編碼 tesseract)
- 保留浮水印移除前處理與原始 OCR 文字

對應需求: 2.1, 2.2, 2.5
"""

import io

import numpy as np
import pytest
from unittest.mock import AsyncMock
from PIL import Image

from app.lib.ocr_enhanced.engine_manager import EngineManager
from app.lib.multi_type_ocr.transcript_processor import TranscriptProcessor


class TestEngineManagerLazy:
    def test_construct_with_paddleocr_does_not_crash(self):
        # 惰性:含 paddleocr 的建構不應在未安裝時失敗
        em = EngineManager(engines=["paddleocr", "tesseract"])
        assert "paddleocr" in em.engines

    def test_paddleocr_lang_configurable(self):
        em = EngineManager(engines=["paddleocr"], paddleocr_lang="chinese_cht")
        assert em.paddleocr_lang == "chinese_cht"


class TestTranscriptEngine:
    def test_transcript_uses_paddleocr(self):
        processor = TranscriptProcessor()
        assert "paddleocr" in processor.engine_manager.engines

    def test_watermark_preprocessing_preserved(self):
        processor = TranscriptProcessor()
        assert processor.preprocessor.config.enable_watermark_removal is True


class TestOriginalTextPreserved:
    async def test_ocr_raw_text_preserved_in_result(self):
        processor = TranscriptProcessor()
        # mock 四步驟,聚焦驗證原始 OCR 文字保留於 ocr_raw
        processor.preprocess = AsyncMock(side_effect=lambda image: image)
        processor.extract_text = AsyncMock(return_value=("原始謄本文字", 0.7))
        processor.postprocess = AsyncMock(return_value=("修正後文字", {}))
        processor.extract_fields = AsyncMock(return_value={})

        img = Image.fromarray(np.zeros((40, 40, 3), dtype=np.uint8))
        buf = io.BytesIO()
        img.save(buf, format="PNG")

        result = await processor.process(
            file_contents=buf.getvalue(), filename="t.png",
            page_number=1, total_pages=1, enable_llm=False,
        )
        # 保留原始 OCR 文字供對照
        assert result["ocr_raw"]["text"] == "原始謄本文字"
