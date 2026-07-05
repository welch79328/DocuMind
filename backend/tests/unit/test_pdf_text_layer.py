"""
測試 PDF 文字層偵測與分段(任務 12.1)

- has_text_layer:含文字層 → True;純掃描/無文字 → False;fitz 不可用 → 降級 False
- extract_text_layer_pages:逐頁抽取並分段(保留頁碼、標記 text_layer)

對應需求: 4.1, 4.2, 4.3
"""

import pytest
from unittest.mock import patch

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


class TestHasTextLayer:
    def test_true_when_text_present(self):
        long_text = "第一條 本租賃契約由出租人與承租人雙方訂立,租賃期間自簽約日起計算,雙方同意遵守下列各項條款。"
        with patch.object(pdf_text_layer, "_open_pdf", return_value=_FakeDoc([long_text])):
            assert pdf_text_layer.has_text_layer(b"pdf") is True

    def test_false_when_empty(self):
        with patch.object(pdf_text_layer, "_open_pdf", return_value=_FakeDoc(["", "  "])):
            assert pdf_text_layer.has_text_layer(b"pdf") is False

    def test_false_when_fitz_unavailable(self):
        with patch.object(pdf_text_layer, "_open_pdf", side_effect=ImportError("no fitz")):
            assert pdf_text_layer.has_text_layer(b"pdf") is False


class TestExtractPages:
    def test_extracts_page_chunks_with_page_numbers(self):
        with patch.object(pdf_text_layer, "_open_pdf",
                          return_value=_FakeDoc(["第一頁條款", "第二頁條款"])):
            pages = pdf_text_layer.extract_text_layer_pages(b"pdf")
        assert len(pages) == 2
        assert pages[0]["page_number"] == 1
        assert pages[0]["ocr_raw"]["text"] == "第一頁條款"
        assert pages[1]["page_number"] == 2
        # 文字層為精確文字,信心度高、標記 text_layer(略過 OCR)
        assert pages[0]["ocr_raw"]["confidence"] == 1.0
        assert pages[0]["text_layer"] is True
        assert pages[0]["overall_confidence"] == 1.0
