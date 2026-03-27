"""
測試 multi_type_ocr 型別定義

驗收標準:
- DocumentTypeEnum 定義 "transcript" 和 "contract"
- PageResult TypedDict 包含所有必要欄位
- OcrRawResult, RulePostprocessedResult, LlmPostprocessedResult 正確定義
- 所有型別定義通過 mypy 靜態檢查
"""

import pytest
from typing import get_type_hints, get_args
from app.lib.multi_type_ocr.types import (
    DocumentTypeEnum,
    OcrRawResult,
    RulePostprocessedResult,
    LlmPostprocessedResult,
    PageResult,
)


class TestDocumentTypeEnum:
    """測試文件類型列舉"""

    def test_document_type_enum_has_transcript(self):
        """驗證包含 transcript 類型"""
        args = get_args(DocumentTypeEnum)
        assert "transcript" in args

    def test_document_type_enum_has_contract(self):
        """驗證包含 contract 類型"""
        args = get_args(DocumentTypeEnum)
        assert "contract" in args

    def test_document_type_enum_only_two_types(self):
        """驗證只有兩種類型"""
        args = get_args(DocumentTypeEnum)
        assert len(args) == 2


class TestOcrRawResult:
    """測試 OCR 原始結果型別"""

    def test_ocr_raw_result_has_text_field(self):
        """驗證包含 text 欄位"""
        hints = get_type_hints(OcrRawResult)
        assert "text" in hints

    def test_ocr_raw_result_has_confidence_field(self):
        """驗證包含 confidence 欄位"""
        hints = get_type_hints(OcrRawResult)
        assert "confidence" in hints

    def test_ocr_raw_result_text_is_string(self):
        """驗證 text 欄位為字串類型"""
        hints = get_type_hints(OcrRawResult)
        assert hints["text"] == str

    def test_ocr_raw_result_confidence_is_float(self):
        """驗證 confidence 欄位為浮點數類型"""
        hints = get_type_hints(OcrRawResult)
        assert hints["confidence"] == float


class TestRulePostprocessedResult:
    """測試規則後處理結果型別"""

    def test_rule_postprocessed_has_text_field(self):
        """驗證包含 text 欄位"""
        hints = get_type_hints(RulePostprocessedResult)
        assert "text" in hints

    def test_rule_postprocessed_has_stats_field(self):
        """驗證包含 stats 欄位"""
        hints = get_type_hints(RulePostprocessedResult)
        assert "stats" in hints


class TestLlmPostprocessedResult:
    """測試 LLM 後處理結果型別"""

    def test_llm_postprocessed_has_text_field(self):
        """驗證包含 text 欄位"""
        hints = get_type_hints(LlmPostprocessedResult)
        assert "text" in hints

    def test_llm_postprocessed_has_stats_field(self):
        """驗證包含 stats 欄位"""
        hints = get_type_hints(LlmPostprocessedResult)
        assert "stats" in hints

    def test_llm_postprocessed_has_used_field(self):
        """驗證包含 used 欄位"""
        hints = get_type_hints(LlmPostprocessedResult)
        assert "used" in hints


class TestPageResult:
    """測試頁面結果型別"""

    def test_page_result_has_page_number(self):
        """驗證包含 page_number 欄位"""
        hints = get_type_hints(PageResult)
        assert "page_number" in hints

    def test_page_result_has_original_image(self):
        """驗證包含 original_image 欄位"""
        hints = get_type_hints(PageResult)
        assert "original_image" in hints

    def test_page_result_has_ocr_raw(self):
        """驗證包含 ocr_raw 欄位"""
        hints = get_type_hints(PageResult)
        assert "ocr_raw" in hints

    def test_page_result_has_rule_postprocessed(self):
        """驗證包含 rule_postprocessed 欄位"""
        hints = get_type_hints(PageResult)
        assert "rule_postprocessed" in hints

    def test_page_result_has_llm_postprocessed(self):
        """驗證包含 llm_postprocessed 欄位（可選）"""
        hints = get_type_hints(PageResult)
        assert "llm_postprocessed" in hints

    def test_page_result_has_structured_data(self):
        """驗證包含 structured_data 欄位（可選）"""
        hints = get_type_hints(PageResult)
        assert "structured_data" in hints

    def test_page_result_has_accuracy(self):
        """驗證包含 accuracy 欄位（可選）"""
        hints = get_type_hints(PageResult)
        assert "accuracy" in hints

    def test_page_result_has_processing_steps(self):
        """驗證包含 processing_steps 欄位"""
        hints = get_type_hints(PageResult)
        assert "processing_steps" in hints


class TestTypeInstantiation:
    """測試型別實例化"""

    def test_can_create_ocr_raw_result(self):
        """驗證可以創建 OcrRawResult 實例"""
        result: OcrRawResult = {
            "text": "測試文字",
            "confidence": 0.95
        }
        assert result["text"] == "測試文字"
        assert result["confidence"] == 0.95

    def test_can_create_rule_postprocessed_result(self):
        """驗證可以創建 RulePostprocessedResult 實例"""
        result: RulePostprocessedResult = {
            "text": "修正後文字",
            "stats": {"typo_fixes": 5}
        }
        assert result["text"] == "修正後文字"
        assert result["stats"]["typo_fixes"] == 5

    def test_can_create_llm_postprocessed_result(self):
        """驗證可以創建 LlmPostprocessedResult 實例"""
        result: LlmPostprocessedResult = {
            "text": "LLM 修正後文字",
            "stats": {"llm_cost": 0.02},
            "used": True
        }
        assert result["text"] == "LLM 修正後文字"
        assert result["used"] is True

    def test_can_create_page_result(self):
        """驗證可以創建 PageResult 實例"""
        result: PageResult = {
            "page_number": 1,
            "original_image": "base64...",
            "ocr_raw": {"text": "原始", "confidence": 0.9},
            "rule_postprocessed": {"text": "修正", "stats": {}},
            "llm_postprocessed": None,
            "structured_data": None,
            "accuracy": None,
            "processing_steps": {"step1": "完成"}
        }
        assert result["page_number"] == 1
        assert result["ocr_raw"]["text"] == "原始"
