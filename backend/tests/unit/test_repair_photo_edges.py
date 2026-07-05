"""
修繕照片邊界測試(任務 13.2)

驗證 VLM 回應的健壯處理:信心度字串/缺欄位/畸形 JSON/非數值信心度。

對應需求: 5.1, 5.2, 5.4
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.lib.multi_type_ocr.repair_photo_processor import RepairPhotoProcessor
from app.lib.multi_type_ocr.processor_factory import ProcessorFactory


def _p(json_str):
    p = MagicMock()
    p.call = AsyncMock(return_value=json_str)
    return p


class TestRobustParsing:
    async def test_confidence_as_string(self):
        r = await RepairPhotoProcessor(provider=_p(
            '{"defect_labels": ["漏水"], "description": "x", "confidence": "0.75"}')).understand("B")
        assert r["confidence"] == 0.75

    async def test_missing_defect_labels_defaults_empty(self):
        r = await RepairPhotoProcessor(provider=_p(
            '{"description": "x", "confidence": 0.5}')).understand("B")
        assert r["defect_labels"] == []

    async def test_missing_confidence_defaults_zero(self):
        r = await RepairPhotoProcessor(provider=_p(
            '{"defect_labels": ["龜裂"], "description": "x"}')).understand("B")
        assert r["confidence"] == 0.0

    async def test_malformed_json_degrades(self):
        r = await RepairPhotoProcessor(provider=_p("這不是 JSON")).understand("B")
        assert r["defect_labels"] == []
        assert r["confidence"] == 0.0

    async def test_non_numeric_confidence_safe(self):
        # VLM 回非數值信心度 → 不應拋出,安全降為 0.0
        r = await RepairPhotoProcessor(provider=_p(
            '{"defect_labels": [], "description": "x", "confidence": "高"}')).understand("B")
        assert r["confidence"] == 0.0


class TestRouting:
    def test_route_by_string(self):
        assert isinstance(
            ProcessorFactory.get_processor("repair_photo"), RepairPhotoProcessor)
