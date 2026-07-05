"""
測試合約 PDF 文字層接入分析流程(任務 12.1)

- 合約 PDF 含文字層 → 略過 OCR,直接以文字層分段
- 純掃描合約 PDF → 觸發 OCR

對應需求: 4.1, 4.2, 4.3
"""

import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.analyze_service import AnalyzeService
from app.lib.multi_type_ocr.processor_factory import ProcessorFactory


def _text_layer_pages():
    return [
        {"page_number": 1, "ocr_raw": {"text": "第一頁條款", "confidence": 1.0},
         "rule_postprocessed": {"text": "第一頁條款", "stats": {}},
         "llm_postprocessed": None, "structured_data": None,
         "field_confidences": {}, "overall_confidence": 1.0, "text_layer": True},
        {"page_number": 2, "ocr_raw": {"text": "第二頁條款", "confidence": 1.0},
         "rule_postprocessed": {"text": "第二頁條款", "stats": {}},
         "llm_postprocessed": None, "structured_data": None,
         "field_confidences": {}, "overall_confidence": 1.0, "text_layer": True},
    ]


class TestTextLayerWiring:
    async def test_contract_with_text_layer_skips_ocr(self):
        svc = AnalyzeService()
        mock_proc = MagicMock()
        mock_proc.process = AsyncMock()

        with patch("app.services.analyze_service.has_text_layer", return_value=True), \
             patch("app.services.analyze_service.extract_text_layer_pages",
                   return_value=_text_layer_pages()), \
             patch.object(ProcessorFactory, "get_processor", return_value=mock_proc):
            pages, total = await svc._process_ocr(b"pdfbytes", "contract.pdf", "contract", False)

        # 略過 OCR:processor.process 未被呼叫
        mock_proc.process.assert_not_called()
        assert total == 2
        assert pages[0]["text_layer"] is True
        assert pages[0]["ocr_raw"]["text"] == "第一頁條款"

    async def test_scanned_contract_triggers_ocr(self):
        svc = AnalyzeService()
        mock_proc = MagicMock()
        mock_proc.process = AsyncMock(return_value={
            "page_number": 1, "ocr_raw": {"text": "掃描文字", "confidence": 0.8},
            "rule_postprocessed": {"text": "掃描文字", "stats": {}},
            "llm_postprocessed": None, "structured_data": None, "original_image": "x",
        })

        # 惰性 import fitz:以 sys.modules 注入假 fitz 提供頁數
        fake_fitz = MagicMock()
        fake_doc = MagicMock()
        fake_doc.__len__ = lambda self: 1
        fake_fitz.open.return_value = fake_doc

        with patch("app.services.analyze_service.has_text_layer", return_value=False), \
             patch.dict(sys.modules, {"fitz": fake_fitz}), \
             patch.object(ProcessorFactory, "get_processor", return_value=mock_proc):
            await svc._process_ocr(b"pdfbytes", "contract.pdf", "contract", False)

        # 觸發 OCR:processor.process 被呼叫
        mock_proc.process.assert_called()
