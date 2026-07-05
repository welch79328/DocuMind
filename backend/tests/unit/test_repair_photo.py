"""
測試修繕照片影像理解與型別註冊(任務 13.1)

- RepairPhotoProcessor 為影像理解型(非 OCR)
- VLM 產出瑕疵分類、繁中描述與信心度;模糊照片低信心
- few-shot 注入;LLM 失敗降級
- repair_photo 可被路由

對應需求: 5.1, 5.2, 5.3, 5.4, 1.1
"""

import io

import numpy as np
import pytest
from unittest.mock import AsyncMock, MagicMock
from PIL import Image

from app.lib.multi_type_ocr.repair_photo_processor import RepairPhotoProcessor
from app.lib.multi_type_ocr.processor import ImageUnderstandingProcessor
from app.lib.multi_type_ocr.processor_factory import ProcessorFactory
from app.lib.document_types import DocumentType


def _png():
    img = Image.fromarray(np.zeros((40, 40, 3), dtype=np.uint8))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _provider(json_str):
    p = MagicMock()
    p.call = AsyncMock(return_value=json_str)
    return p


class TestType:
    def test_is_image_understanding_processor(self):
        assert isinstance(RepairPhotoProcessor(), ImageUnderstandingProcessor)


class TestUnderstand:
    async def test_returns_defects_description_confidence(self):
        p = _provider('{"defect_labels": ["漏水", "壁癌"], "description": "牆面滲水並有壁癌", "confidence": 0.88}')
        result = await RepairPhotoProcessor(provider=p).understand("B64")
        assert result["defect_labels"] == ["漏水", "壁癌"]
        assert result["description"] == "牆面滲水並有壁癌"
        assert result["confidence"] == 0.88

    async def test_few_shot_injected(self):
        p = _provider('{"defect_labels": [], "description": "", "confidence": 0.5}')
        few_shot = [{"input_ref": "r", "corrected_fields": {"x": 1}}]
        await RepairPhotoProcessor(provider=p).understand("B64", few_shot=few_shot)
        _, kwargs = p.call.call_args
        assert kwargs["few_shot"] == few_shot
        assert kwargs["image_data"] == "B64"

    async def test_llm_failure_degrades(self):
        p = MagicMock()
        p.call = AsyncMock(side_effect=RuntimeError("VLM down"))
        result = await RepairPhotoProcessor(provider=p).understand("B64")
        assert result["defect_labels"] == []
        assert result["confidence"] == 0.0


class TestProcess:
    async def test_process_carries_understanding(self):
        p = _provider('{"defect_labels": ["龜裂"], "description": "地面龜裂", "confidence": 0.9}')
        result = await RepairPhotoProcessor(provider=p).process(
            file_contents=_png(), filename="photo.jpg",
            page_number=1, total_pages=1, enable_llm=True,
        )
        assert result["structured_data"]["defect_labels"] == ["龜裂"]
        assert result["overall_confidence"] == 0.9
        assert result["ocr_raw"] is None  # 非 OCR

    async def test_blurry_photo_low_confidence(self):
        # 模糊照片 → VLM 回低信心 → overall_confidence 低(進複核由 gating 處理)
        p = _provider('{"defect_labels": [], "description": "影像模糊無法辨識", "confidence": 0.3}')
        result = await RepairPhotoProcessor(provider=p).process(
            file_contents=_png(), filename="blurry.jpg",
            page_number=1, total_pages=1, enable_llm=True,
        )
        assert result["overall_confidence"] == 0.3
        assert result["overall_confidence"] < 0.8


class TestRouting:
    def test_repair_photo_routable(self):
        assert isinstance(
            ProcessorFactory.get_processor(DocumentType.REPAIR_PHOTO), RepairPhotoProcessor)

    def test_in_supported_types(self):
        assert "repair_photo" in [str(t) for t in ProcessorFactory.supported_types()]
