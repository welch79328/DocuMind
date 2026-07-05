"""
測試帳單 pipeline:鍵值抽取與缺漏標記(任務 11.1)

- 票證式抽取金額/日期/戶號,每欄位附信心度
- 缺漏關鍵欄位標記需補齊
- 劣化影像以 LLM Vision(few-shot)補齊
- BillProcessor 為 OCR 型,process() 產出結構化欄位

對應需求: 3.1, 3.2, 3.3, 3.4
"""

import io

import numpy as np
import pytest
from unittest.mock import AsyncMock, MagicMock
from PIL import Image

from app.lib.multi_type_ocr.bill_field_extractor import BillFieldExtractor
from app.lib.multi_type_ocr.bill_processor import BillProcessor
from app.lib.multi_type_ocr.processor import OcrDocumentProcessor

CLEAR_BILL = """台灣電力公司 電費通知
戶號: 01-2345-6789
本期應繳: 1,250 元
繳費期限: 2026/03/15
"""


class TestBillFieldExtraction:
    async def test_extracts_key_fields(self):
        result = await BillFieldExtractor().extract(CLEAR_BILL)
        assert result["amount"] == "1,250"
        assert result["account_no"] == "01-2345-6789"
        assert result["date"] == "2026/03/15"

    async def test_each_field_has_confidence(self):
        result = await BillFieldExtractor().extract(CLEAR_BILL)
        for key in ("amount", "date", "account_no"):
            assert key in result["field_confidences"]
        assert result["field_confidences"]["amount"] >= 0.8

    async def test_missing_field_marked_for_confirmation(self):
        # 缺金額 → 需補齊
        text = "戶號: 01-2345-6789\n繳費期限: 2026/03/15"
        result = await BillFieldExtractor().extract(text)
        assert "amount" in result["needs_confirmation"]
        assert "account_no" not in result["needs_confirmation"]


class TestDegradedLLMFallback:
    async def test_llm_fills_missing_with_few_shot(self):
        provider = MagicMock()
        provider.call = AsyncMock(return_value='{"amount": "980"}')
        extractor = BillFieldExtractor(provider=provider)
        few_shot = [{"input_ref": "r", "corrected_fields": {"amount": "x"}}]

        # 劣化件缺金額
        text = "戶號: 01-2345-6789\n繳費期限: 2026/03/15"
        result = await extractor.extract(
            text, image_data="B64", use_llm_fallback=True, few_shot=few_shot)
        assert result["amount"] == "980"
        assert result["llm_used_for_extraction"] is True
        _, kwargs = provider.call.call_args
        assert kwargs["few_shot"] == few_shot


class TestBillProcessor:
    def test_is_ocr_document_processor(self):
        assert isinstance(BillProcessor(), OcrDocumentProcessor)

    async def test_process_returns_bill_fields(self):
        processor = BillProcessor()
        processor.preprocess = AsyncMock(side_effect=lambda image: image)
        processor.extract_text = AsyncMock(return_value=(CLEAR_BILL, 0.7))
        processor.postprocess = AsyncMock(return_value=(CLEAR_BILL, {}))

        img = Image.fromarray(np.zeros((40, 40, 3), dtype=np.uint8))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        result = await processor.process(
            file_contents=buf.getvalue(), filename="bill.png",
            page_number=1, total_pages=1, enable_llm=False,
        )
        sd = result["structured_data"]
        assert sd["amount"] == "1,250"
        assert "field_confidences" in sd
