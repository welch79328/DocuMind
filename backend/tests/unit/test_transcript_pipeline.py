"""
謄本 pipeline 整合測試(任務 10.4)

以 mock OCR 步驟(離線)驗證完整謄本流程:
process() → 欄位抽取 → 低信心標記 → few-shot 貫穿 → PageResult 信心度。

對應需求: 2.1, 2.2, 2.3, 2.4
"""

import io

import numpy as np
import pytest
from unittest.mock import AsyncMock, patch
from PIL import Image

from app.lib.multi_type_ocr.transcript_processor import TranscriptProcessor
from app.lib.multi_type_ocr.transcript_field_extractor import TranscriptFieldExtractor

# 密集謄本樣本(多欄位;缺建號)
DENSE_TRANSCRIPT = """土地登記第一類謄本  （浮水印）
　　　　　　　　　　地　號: 0123-0045
面　積: 256.80 平方公尺
權利範圍: 1000分之100
所有權人: 林大同
登記日期: 民國112年3月
"""


def _png():
    img = Image.fromarray(np.zeros((60, 60, 3), dtype=np.uint8))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _mock_ocr(processor, text=DENSE_TRANSCRIPT, confidence=0.72):
    processor.preprocess = AsyncMock(side_effect=lambda image: image)
    processor.extract_text = AsyncMock(return_value=(text, confidence))
    processor.postprocess = AsyncMock(return_value=(text, {}))
    return processor


async def _run(processor, **kwargs):
    return await processor.process(
        file_contents=_png(), filename="t.png",
        page_number=1, total_pages=1,
        enable_llm=kwargs.get("enable_llm", False),
        few_shot=kwargs.get("few_shot"),
    )


class TestFullPipeline:
    async def test_extracts_fields_with_confidences(self):
        result = await _run(_mock_ocr(TranscriptProcessor()))
        sd = result["structured_data"]
        assert sd["land_number"] == "0123-0045"
        assert sd["area"] == "256.80"
        assert sd["owner"] == "林大同"
        assert sd["rights_scope"] == "1000分之100"
        assert "field_confidences" in sd

    async def test_page_result_confidence_flows(self):
        result = await _run(_mock_ocr(TranscriptProcessor(), confidence=0.72))
        # 整體信心度 = OCR 信心度;欄位信心度由抽取結果彙整至 PageResult
        assert result["overall_confidence"] == 0.72
        assert result["field_confidences"]["owner"] >= 0.8
        assert result["field_confidences"]["building_number"] == 0.0

    async def test_low_confidence_field_marked(self):
        result = await _run(_mock_ocr(TranscriptProcessor()))
        # 缺建號 → 標記需人工確認
        assert "building_number" in result["structured_data"]["needs_confirmation"]
        assert "land_number" not in result["structured_data"]["needs_confirmation"]


class TestFewShotThreading:
    async def test_few_shot_reaches_field_extractor(self):
        processor = _mock_ocr(TranscriptProcessor())
        few_shot = [{"input_ref": "r", "corrected_fields": {"area": "1"}}]
        captured = {}

        real_extract = TranscriptFieldExtractor.extract

        async def spy(self, text, image_data=None, use_llm_fallback=False, few_shot=None):
            captured["few_shot"] = few_shot
            return await real_extract(
                self, text, image_data=image_data,
                use_llm_fallback=use_llm_fallback, few_shot=few_shot,
            )

        with patch.object(TranscriptFieldExtractor, "extract", spy):
            await _run(processor, few_shot=few_shot)

        assert captured["few_shot"] == few_shot


class TestDenseTable:
    async def test_dense_transcript_multiple_fields(self):
        result = await _run(_mock_ocr(TranscriptProcessor()))
        sd = result["structured_data"]
        # 密集多欄位皆抽取(建號除外)
        extracted = [k for k in ("land_number", "area", "rights_scope", "owner")
                     if sd.get(k)]
        assert len(extracted) == 4
