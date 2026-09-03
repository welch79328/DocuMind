"""
合約文字層邊界測試(任務 12.2)

- 分支閘控:文字層優化僅套用合約(非合約 PDF 不略過 OCR)
- 多頁分段:保留連續頁碼與逐頁文字
- 偵測門檻邊界

對應需求: 4.1, 4.2, 4.3, 4.4
"""

import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.analyze_service import AnalyzeService
from app.lib.multi_type_ocr.processor_factory import ProcessorFactory
from app.lib import pdf_text_layer


class _FakePage:
    def __init__(self, text):
        self._text = text

    def get_text(self):
        return self._text


class _FakeDoc:
    def __init__(self, texts):
        self._pages = [_FakePage(t) for t in texts]

    def __iter__(self):
        return iter(self._pages)

    def __len__(self):
        return len(self._pages)

    def close(self):
        pass


class TestBranchGating:
    async def test_non_contract_pdf_also_uses_text_layer(self):
        """謄本 PDF 含文字層時同樣略過 OCR。

        原本這條斷言的是相反行為(「閘控為合約」)。2026-09-03 查證後改寫:

          原始 commit 5b62994 把文字層列為「合約 pipeline」的特性,
          謄本那段只寫「PaddleOCR + 浮水印前處理」,**完全沒提文字層**。
          該處沒有排除謄本的理由——是設計合約那條路時的遺漏,不是決策。

          實測(4 頁電子謄本):走 OCR 85s / CER 14.5%,走文字層 <1s / 逐字精確。
          謄本的 OCR 錯誤率高於合約,受益更大。

        純掃描件不含文字層,has_text_layer 回 False 自動走 OCR,行為不變。
        """
        svc = AnalyzeService()
        mock_proc = MagicMock()
        mock_proc.process = AsyncMock(return_value={
            "page_number": 1, "ocr_raw": {"text": "x", "confidence": 0.8},
            "rule_postprocessed": {"text": "x", "stats": {}},
            "llm_postprocessed": None, "structured_data": None, "original_image": "x",
        })
        fake_fitz = MagicMock()
        fake_doc = MagicMock()
        fake_doc.__len__ = lambda self: 1
        fake_fitz.open.return_value = fake_doc

        with patch("app.services.analyze_service.has_text_layer") as mock_has, \
             patch.dict(sys.modules, {"fitz": fake_fitz}), \
             patch.object(ProcessorFactory, "get_processor", return_value=mock_proc):
            await svc._process_ocr(b"pdf", "transcript.pdf", "transcript", False)

        # 現在所有 PDF 都會先問一次文字層
        mock_has.assert_called_once()
        # mock_has 預設回傳 MagicMock(truthy),故走文字層分支、不進 OCR
        mock_proc.process.assert_not_called()


class TestMultiPageChunking:
    def test_preserves_sequential_page_numbers(self):
        texts = [f"第{i}頁條款內容" for i in range(1, 6)]
        with patch.object(pdf_text_layer, "_open_pdf", return_value=_FakeDoc(texts)):
            pages = pdf_text_layer.extract_text_layer_pages(b"pdf")
        assert [p["page_number"] for p in pages] == [1, 2, 3, 4, 5]
        assert pages[2]["ocr_raw"]["text"] == "第3頁條款內容"

    def test_empty_page_still_chunked(self):
        with patch.object(pdf_text_layer, "_open_pdf",
                          return_value=_FakeDoc(["有內容的一頁", ""])):
            pages = pdf_text_layer.extract_text_layer_pages(b"pdf")
        assert len(pages) == 2
        assert pages[1]["ocr_raw"]["text"] == ""


class TestThresholdBoundary:
    def test_exactly_min_chars_is_text_layer(self):
        text = "字" * 20  # 恰好 20 字元
        with patch.object(pdf_text_layer, "_open_pdf", return_value=_FakeDoc([text])):
            assert pdf_text_layer.has_text_layer(b"pdf") is True

    def test_below_min_chars_is_scanned(self):
        text = "字" * 19
        with patch.object(pdf_text_layer, "_open_pdf", return_value=_FakeDoc([text])):
            assert pdf_text_layer.has_text_layer(b"pdf") is False
