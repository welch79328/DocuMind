"""
測試謄本關鍵欄位抽取與低信心標記(任務 10.2)

- 規則抽取:地號/建號、面積、權利範圍、所有權人,每欄位附信心度
- 低信心欄位標記需人工確認
- LLM Vision fallback 支援 few-shot 注入

對應需求: 2.3, 2.4
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.lib.multi_type_ocr.transcript_field_extractor import TranscriptFieldExtractor

SAMPLE = """土地登記第一類謄本
地號: 0123-0045
面積: 128.45 平方公尺
權利範圍: 全部
所有權人: 陳大明
"""


class TestRegexExtraction:
    async def test_extracts_key_fields(self):
        result = await TranscriptFieldExtractor().extract(SAMPLE)
        assert result["land_number"] == "0123-0045"
        assert result["area"] == "128.45"
        assert result["rights_scope"] == "全部"
        assert result["owner"] == "陳大明"

    async def test_every_field_has_confidence(self):
        result = await TranscriptFieldExtractor().extract(SAMPLE)
        fc = result["field_confidences"]
        for key in ("land_number", "building_number", "area", "rights_scope", "owner"):
            assert key in fc
        # 有抽到的欄位信心度高
        assert fc["land_number"] >= 0.8
        # 未出現的建號 → 低信心
        assert fc["building_number"] == 0.0

    async def test_missing_fields_marked_for_confirmation(self):
        result = await TranscriptFieldExtractor().extract(SAMPLE)
        # 建號未出現 → 需人工確認
        assert "building_number" in result["needs_confirmation"]
        assert "land_number" not in result["needs_confirmation"]

    async def test_empty_text_all_need_confirmation(self):
        result = await TranscriptFieldExtractor().extract("")
        assert set(result["needs_confirmation"]) == {
            "land_number", "building_number", "area", "rights_scope", "owner"
        }
        assert result["llm_used_for_extraction"] is False


class TestLLMFallback:
    async def test_llm_fills_missing_and_injects_few_shot(self):
        provider = MagicMock()
        provider.call = AsyncMock(return_value='{"building_number": "9988-0001"}')
        extractor = TranscriptFieldExtractor(provider=provider)
        few_shot = [{"input_ref": "r", "corrected_fields": {"building_number": "x"}}]

        result = await extractor.extract(
            SAMPLE, image_data="BASE64", use_llm_fallback=True, few_shot=few_shot,
        )
        assert result["building_number"] == "9988-0001"
        assert result["llm_used_for_extraction"] is True
        # few-shot 注入至 provider
        _, kwargs = provider.call.call_args
        assert kwargs["few_shot"] == few_shot
        # 影像傳入
        assert kwargs.get("image_data") == "BASE64"

    async def test_no_llm_when_no_image(self):
        provider = MagicMock()
        provider.call = AsyncMock(return_value="{}")
        extractor = TranscriptFieldExtractor(provider=provider)
        result = await extractor.extract(SAMPLE, image_data=None, use_llm_fallback=True)
        assert result["llm_used_for_extraction"] is False
        provider.call.assert_not_called()


class TestProcessorIntegration:
    async def test_transcript_processor_extract_fields_returns_confidences(self):
        from app.lib.multi_type_ocr.transcript_processor import TranscriptProcessor
        processor = TranscriptProcessor()
        result = await processor.extract_fields(SAMPLE)
        assert "field_confidences" in result
        assert result["field_confidences"]["owner"] >= 0.8
