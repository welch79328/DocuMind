"""
謄本/合約處理器契約重構回歸測試(任務 8.2)

驗證 TranscriptProcessor / ContractProcessor 在重構後,process() 組裝的
PageResult 結構與行為與重構前一致(mock 四步驟內部,聚焦輸出契約)。

對應需求: 2.1
"""

import io

import numpy as np
import pytest
from unittest.mock import AsyncMock
from PIL import Image

from app.lib.multi_type_ocr.transcript_processor import TranscriptProcessor
from app.lib.multi_type_ocr.contract_processor import ContractProcessor

LEGACY_KEYS = {
    "page_number", "original_image", "ocr_raw", "rule_postprocessed",
    "llm_postprocessed", "structured_data", "accuracy", "processing_steps",
}


def _png_bytes():
    img = Image.fromarray(np.zeros((50, 50, 3), dtype=np.uint8))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _patch_steps(processor, *, llm_used=False, structured=None):
    """mock 四步驟,聚焦驗證 process/analyze 的組裝行為"""
    processor.preprocess = AsyncMock(side_effect=lambda image: image)
    processor.extract_text = AsyncMock(return_value=("辨識文字", 0.83))
    stats = {"typo_fixes": 3}
    if llm_used:
        stats.update({"llm_used": True, "llm_cost": 0.02})
    processor.postprocess = AsyncMock(return_value=("修正後文字", stats))
    processor.extract_fields = AsyncMock(return_value=(structured or {}))
    return processor


async def _run(processor, **kwargs):
    return await processor.process(
        file_contents=_png_bytes(), filename="doc.png",
        page_number=2, total_pages=4, enable_llm=kwargs.get("enable_llm", False),
    )


class TestTranscriptRegression:
    async def test_output_has_all_legacy_keys(self):
        result = await _run(_patch_steps(TranscriptProcessor()))
        assert LEGACY_KEYS.issubset(result.keys())

    async def test_ocr_and_rule_structure_unchanged(self):
        result = await _run(_patch_steps(TranscriptProcessor()))
        assert result["ocr_raw"] == {"text": "辨識文字", "confidence": 0.83}
        assert result["rule_postprocessed"]["text"] == "修正後文字"
        assert result["rule_postprocessed"]["stats"]["typo_fixes"] == 3
        assert result["page_number"] == 2
        assert result["original_image"].startswith("data:image/png;base64,")
        assert result["accuracy"] is None

    async def test_processing_steps_present(self):
        result = await _run(_patch_steps(TranscriptProcessor()))
        steps = result["processing_steps"]
        assert steps["1_preprocess"] == "完成"
        assert steps["2_ocr"] == "完成"

    async def test_llm_postprocessed_none_when_not_used(self):
        result = await _run(_patch_steps(TranscriptProcessor(), llm_used=False))
        assert result["llm_postprocessed"] is None

    async def test_llm_postprocessed_populated_when_used(self):
        result = await _run(
            _patch_steps(TranscriptProcessor(), llm_used=True), enable_llm=True)
        llm = result["llm_postprocessed"]
        assert llm is not None
        assert llm["used"] is True
        assert llm["stats"]["llm_cost"] == 0.02

    async def test_overall_confidence_matches_ocr(self):
        result = await _run(_patch_steps(TranscriptProcessor()))
        assert result["overall_confidence"] == 0.83


class TestContractRegression:
    async def test_output_has_all_legacy_keys(self):
        result = await _run(_patch_steps(ContractProcessor()))
        assert LEGACY_KEYS.issubset(result.keys())

    async def test_structured_data_carried_through(self):
        structured = {"contract_metadata": {"contract_number": "A-001"}}
        result = await _run(_patch_steps(ContractProcessor(), structured=structured))
        assert result["structured_data"] == structured

    async def test_empty_structured_becomes_none(self):
        result = await _run(_patch_steps(ContractProcessor(), structured={}))
        assert result["structured_data"] is None

    async def test_overall_confidence_matches_ocr(self):
        result = await _run(_patch_steps(ContractProcessor()))
        assert result["overall_confidence"] == 0.83
