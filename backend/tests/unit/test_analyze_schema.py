"""
測試 AnalyzeResponse 統一分析回應 schema

驗收標準:
- AnalyzeResponse 包含：file_name, file_url, document_type, total_pages, pages, answer, stats
- 每頁結果包含：ocr_raw（文字+信心度）、rule_postprocessed、llm_postprocessed（可選）、structured_data（可選）
- ProcessingStats 包含：total_time_ms, total_pages, llm_pages_used, estimated_cost
- 所有型別使用 Pydantic BaseModel，無 Any 型別
"""

import pytest
from pydantic import BaseModel, ValidationError


class TestOcrRawOutput:
    """測試 OCR 原始輸出型別"""

    def test_valid_ocr_raw(self):
        from app.schemas.analyze import OcrRawOutput
        result = OcrRawOutput(text="測試文字", confidence=0.85)
        assert result.text == "測試文字"
        assert result.confidence == 0.85

    def test_ocr_raw_is_pydantic_model(self):
        from app.schemas.analyze import OcrRawOutput
        assert issubclass(OcrRawOutput, BaseModel)

    def test_ocr_raw_requires_text(self):
        from app.schemas.analyze import OcrRawOutput
        with pytest.raises(ValidationError):
            OcrRawOutput(confidence=0.85)

    def test_ocr_raw_requires_confidence(self):
        from app.schemas.analyze import OcrRawOutput
        with pytest.raises(ValidationError):
            OcrRawOutput(text="文字")


class TestRulePostprocessedOutput:
    """測試規則後處理輸出型別"""

    def test_valid_rule_postprocessed(self):
        from app.schemas.analyze import RulePostprocessedOutput
        result = RulePostprocessedOutput(
            text="修正後文字",
            stats={"typo_fixes": 5, "format_corrections": 2}
        )
        assert result.text == "修正後文字"
        assert result.stats["typo_fixes"] == 5

    def test_rule_postprocessed_is_pydantic_model(self):
        from app.schemas.analyze import RulePostprocessedOutput
        assert issubclass(RulePostprocessedOutput, BaseModel)


class TestLlmPostprocessedOutput:
    """測試 LLM 後處理輸出型別"""

    def test_valid_llm_postprocessed(self):
        from app.schemas.analyze import LlmPostprocessedOutput
        result = LlmPostprocessedOutput(
            text="LLM 修正文字",
            stats={"llm_used": True, "llm_cost": 0.02},
            used=True
        )
        assert result.text == "LLM 修正文字"
        assert result.used is True

    def test_llm_postprocessed_requires_used_field(self):
        from app.schemas.analyze import LlmPostprocessedOutput
        with pytest.raises(ValidationError):
            LlmPostprocessedOutput(text="文字", stats={})


class TestOcrPageResult:
    """測試單頁 OCR 結果型別"""

    def test_valid_page_result(self):
        from app.schemas.analyze import OcrPageResult, OcrRawOutput, RulePostprocessedOutput
        result = OcrPageResult(
            page_number=1,
            ocr_raw=OcrRawOutput(text="原始文字", confidence=0.82),
            rule_postprocessed=RulePostprocessedOutput(
                text="修正文字", stats={"typo_fixes": 3}
            )
        )
        assert result.page_number == 1
        assert result.llm_postprocessed is None
        assert result.structured_data is None

    def test_page_result_with_llm(self):
        from app.schemas.analyze import (
            OcrPageResult, OcrRawOutput, RulePostprocessedOutput, LlmPostprocessedOutput
        )
        result = OcrPageResult(
            page_number=1,
            ocr_raw=OcrRawOutput(text="原始", confidence=0.7),
            rule_postprocessed=RulePostprocessedOutput(text="規則", stats={}),
            llm_postprocessed=LlmPostprocessedOutput(text="LLM", stats={}, used=True),
            structured_data={"contract_number": "ABC-001"}
        )
        assert result.llm_postprocessed.used is True
        assert result.structured_data["contract_number"] == "ABC-001"


class TestProcessingStats:
    """測試處理統計型別"""

    def test_valid_stats(self):
        from app.schemas.analyze import ProcessingStats
        stats = ProcessingStats(
            total_time_ms=12500,
            total_pages=3,
            llm_pages_used=2,
            estimated_cost=0.04
        )
        assert stats.total_time_ms == 12500
        assert stats.total_pages == 3
        assert stats.llm_pages_used == 2
        assert stats.estimated_cost == 0.04

    def test_stats_is_pydantic_model(self):
        from app.schemas.analyze import ProcessingStats
        assert issubclass(ProcessingStats, BaseModel)

    def test_stats_requires_all_fields(self):
        from app.schemas.analyze import ProcessingStats
        with pytest.raises(ValidationError):
            ProcessingStats(total_time_ms=100)


class TestAnalyzeResponse:
    """測試統一分析回應型別"""

    def test_valid_response(self):
        from app.schemas.analyze import (
            AnalyzeResponse, OcrPageResult, OcrRawOutput,
            RulePostprocessedOutput, ProcessingStats
        )
        response = AnalyzeResponse(
            file_name="謄本.pdf",
            file_url="https://cdn.example.com/uploads/ocr_transcripts/uuid.pdf",
            document_type="transcript",
            total_pages=1,
            pages=[
                OcrPageResult(
                    page_number=1,
                    ocr_raw=OcrRawOutput(text="土地登記", confidence=0.85),
                    rule_postprocessed=RulePostprocessedOutput(text="土地登記", stats={})
                )
            ],
            stats=ProcessingStats(
                total_time_ms=5000,
                total_pages=1,
                llm_pages_used=0,
                estimated_cost=0.0
            )
        )
        assert response.file_name == "謄本.pdf"
        assert response.document_type == "transcript"
        assert response.answer is None
        assert len(response.pages) == 1

    def test_response_file_url_optional(self):
        from app.schemas.analyze import (
            AnalyzeResponse, OcrPageResult, OcrRawOutput,
            RulePostprocessedOutput, ProcessingStats
        )
        response = AnalyzeResponse(
            file_name="test.jpg",
            document_type="contract",
            total_pages=1,
            pages=[
                OcrPageResult(
                    page_number=1,
                    ocr_raw=OcrRawOutput(text="合約", confidence=0.9),
                    rule_postprocessed=RulePostprocessedOutput(text="合約", stats={})
                )
            ],
            stats=ProcessingStats(
                total_time_ms=3000, total_pages=1,
                llm_pages_used=0, estimated_cost=0.0
            )
        )
        assert response.file_url is None

    def test_response_with_answer(self):
        from app.schemas.analyze import (
            AnalyzeResponse, OcrPageResult, OcrRawOutput,
            RulePostprocessedOutput, ProcessingStats
        )
        response = AnalyzeResponse(
            file_name="test.pdf",
            document_type="transcript",
            total_pages=1,
            pages=[
                OcrPageResult(
                    page_number=1,
                    ocr_raw=OcrRawOutput(text="文字", confidence=0.8),
                    rule_postprocessed=RulePostprocessedOutput(text="文字", stats={})
                )
            ],
            answer="所有權人是黃水木",
            stats=ProcessingStats(
                total_time_ms=8000, total_pages=1,
                llm_pages_used=1, estimated_cost=0.02
            )
        )
        assert response.answer == "所有權人是黃水木"

    def test_response_is_pydantic_model(self):
        from app.schemas.analyze import AnalyzeResponse
        assert issubclass(AnalyzeResponse, BaseModel)

    def test_response_serialization(self):
        from app.schemas.analyze import (
            AnalyzeResponse, OcrPageResult, OcrRawOutput,
            RulePostprocessedOutput, ProcessingStats
        )
        response = AnalyzeResponse(
            file_name="test.pdf",
            document_type="transcript",
            total_pages=1,
            pages=[
                OcrPageResult(
                    page_number=1,
                    ocr_raw=OcrRawOutput(text="文字", confidence=0.8),
                    rule_postprocessed=RulePostprocessedOutput(text="文字", stats={})
                )
            ],
            stats=ProcessingStats(
                total_time_ms=5000, total_pages=1,
                llm_pages_used=0, estimated_cost=0.0
            )
        )
        data = response.model_dump()
        assert "file_name" in data
        assert "pages" in data
        assert "stats" in data
        assert data["answer"] is None
        assert data["file_url"] is None
