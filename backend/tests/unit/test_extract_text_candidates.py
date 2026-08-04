"""
多引擎辨識候選測試(任務 4.1 / 4.2 / 4.3 / 4.4)

現行處理器呼叫多引擎辨識後,將各引擎原始結果以底線變數丟棄,僅回傳融合後的
單一文字。若覆寫未生效,**共識機制不會運作而所有既有測試仍會通過**——本測試
組專為攔截此靜默失效而設,故明確驗證:

- 多引擎組態下候選數 > 1(覆寫確實生效)
- 單引擎組態下候選數 = 1
- 引擎執行次數未因取得候選而增加(成本影響為零)

對應需求: 4.1, 4.4, 6.6
"""

import numpy as np
import pytest
from PIL import Image

from app.lib.multi_type_ocr.bill_processor import BillProcessor
from app.lib.multi_type_ocr.contract_processor import ContractProcessor
from app.lib.multi_type_ocr.processor import (
    ImageUnderstandingProcessor,
    OcrDocumentProcessor,
)
from app.lib.multi_type_ocr.repair_photo_processor import RepairPhotoProcessor
from app.lib.multi_type_ocr.transcript_processor import TranscriptProcessor

OCR_PROCESSORS = [TranscriptProcessor, ContractProcessor, BillProcessor]


def _rgb_image(r=10, g=20, b=30):
    array = np.zeros((8, 8, 3), dtype=np.uint8)
    array[:, :, 0], array[:, :, 1], array[:, :, 2] = r, g, b
    return Image.fromarray(array)


class _FakeEngineManager:
    """記錄呼叫次數的假引擎管理器;不執行真實 OCR"""

    def __init__(self, engine_results):
        self.engine_results = engine_results
        self.calls = 0
        self.last_image = None

    async def extract_text_multi_engine(self, image_array, page_number: int = 1):
        self.calls += 1
        self.last_image = image_array
        if not self.engine_results:
            return "", 0.0, []
        # 融合結果:取信心度最高者(僅供測試,不代表真實融合邏輯)
        best = max(self.engine_results, key=lambda r: r["confidence"])
        return best["text"], best["confidence"], list(self.engine_results)


def _engine_result(engine, text, confidence):
    return {
        "engine": engine,
        "text": text,
        "confidence": confidence,
        "processing_time_ms": 5,
    }


DUAL_ENGINE = [
    _engine_result("paddleocr", "地號 0221-0000", 0.91),
    _engine_result("tesseract", "地號 0221-OOOO", 0.78),
]
SINGLE_ENGINE = [_engine_result("tesseract", "地號 0221-0000", 0.78)]


def _with_fake_engine(processor, engine_results):
    processor.engine_manager = _FakeEngineManager(engine_results)
    return processor


# --------------------------------------------------------------------------- #
# 任務 4.1:影像格式轉換共用邏輯
# --------------------------------------------------------------------------- #
class TestBgrArrayHelper:
    def test_helper_available_on_ocr_base(self):
        assert hasattr(OcrDocumentProcessor, "_to_bgr_array")

    def test_rgb_channels_swapped_to_bgr(self):
        array = OcrDocumentProcessor._to_bgr_array(_rgb_image(r=10, g=20, b=30))
        # RGB(10,20,30) → BGR(30,20,10)
        assert array.shape == (8, 8, 3)
        assert tuple(array[0, 0]) == (30, 20, 10)

    def test_grayscale_left_untouched(self):
        gray = Image.fromarray(np.full((8, 8), 128, dtype=np.uint8))
        array = OcrDocumentProcessor._to_bgr_array(gray)
        assert array.shape == (8, 8)
        assert array[0, 0] == 128

    def test_rgba_left_untouched(self):
        rgba = Image.fromarray(np.zeros((8, 8, 4), dtype=np.uint8))
        array = OcrDocumentProcessor._to_bgr_array(rgba)
        assert array.shape == (8, 8, 4)

    @pytest.mark.parametrize("cls", OCR_PROCESSORS, ids=lambda c: c.__name__)
    async def test_extract_text_behaviour_unchanged(self, cls):
        """抽出共用邏輯後,既有文字提取的回傳與傳入引擎的影像格式皆不變"""
        processor = _with_fake_engine(cls(), DUAL_ENGINE)

        text, confidence = await processor.extract_text(_rgb_image())

        assert text == "地號 0221-0000"
        assert confidence == 0.91
        assert processor.engine_manager.calls == 1
        assert tuple(processor.engine_manager.last_image[0, 0]) == (30, 20, 10)


# --------------------------------------------------------------------------- #
# 任務 4.2:基底預設實作
# --------------------------------------------------------------------------- #
class _NoOverrideProcessor(OcrDocumentProcessor):
    """未覆寫候選提取的既有型子類別"""

    def __init__(self):
        self.extract_text_calls = 0

    async def preprocess(self, image):
        return image

    async def extract_text(self, image):
        self.extract_text_calls += 1
        return ("融合後文字", 0.66)

    async def postprocess(self, text, confidence, image_data=None):
        return (text, {})

    async def extract_fields(self, text, image_data=None, enable_llm=False, few_shot=None):
        return {}


class TestDefaultImplementation:
    async def test_default_returns_single_candidate(self):
        processor = _NoOverrideProcessor()

        candidates = await processor.extract_text_candidates(_rgb_image())

        assert len(candidates) == 1

    async def test_default_candidate_wraps_extract_text(self):
        processor = _NoOverrideProcessor()

        candidate = (await processor.extract_text_candidates(_rgb_image()))[0]

        assert candidate["text"] == "融合後文字"
        assert candidate["confidence"] == 0.66
        assert candidate["engine"] == "default"
        assert candidate["processing_time_ms"] == 0
        assert processor.extract_text_calls == 1

    async def test_existing_subclass_still_works_unmodified(self):
        """既有子類別不修改即可運作,analyze 行為不變"""
        processor = _NoOverrideProcessor()

        result = await processor.analyze(_rgb_image())

        assert result["ocr_raw"] == {"text": "融合後文字", "confidence": 0.66}
        assert result["overall_confidence"] == 0.66


# --------------------------------------------------------------------------- #
# 任務 4.3:各處理器回傳真實多引擎候選
# --------------------------------------------------------------------------- #
class TestProcessorOverrides:
    @pytest.mark.parametrize("cls", OCR_PROCESSORS, ids=lambda c: c.__name__)
    async def test_multi_engine_yields_more_than_one_candidate(self, cls):
        """核心防護:多引擎組態下候選數必須 > 1,否則共識機制靜默失效"""
        processor = _with_fake_engine(cls(), DUAL_ENGINE)

        candidates = await processor.extract_text_candidates(_rgb_image())

        assert len(candidates) > 1
        assert {c["engine"] for c in candidates} == {"paddleocr", "tesseract"}

    @pytest.mark.parametrize("cls", OCR_PROCESSORS, ids=lambda c: c.__name__)
    async def test_candidates_are_raw_not_fused(self, cls):
        """候選須為各引擎原始結果,不得是融合後的單一文字"""
        processor = _with_fake_engine(cls(), DUAL_ENGINE)

        candidates = await processor.extract_text_candidates(_rgb_image())

        texts = {c["text"] for c in candidates}
        assert texts == {"地號 0221-0000", "地號 0221-OOOO"}

    @pytest.mark.parametrize("cls", OCR_PROCESSORS, ids=lambda c: c.__name__)
    async def test_single_engine_yields_one_candidate(self, cls):
        processor = _with_fake_engine(cls(), SINGLE_ENGINE)

        candidates = await processor.extract_text_candidates(_rgb_image())

        assert len(candidates) == 1
        assert candidates[0]["engine"] == "tesseract"

    @pytest.mark.parametrize("cls", OCR_PROCESSORS, ids=lambda c: c.__name__)
    async def test_no_additional_engine_invocation(self, cls):
        """成本影響為零:取得候選只跑一次引擎,與現行相同"""
        processor = _with_fake_engine(cls(), DUAL_ENGINE)

        await processor.extract_text_candidates(_rgb_image())

        assert processor.engine_manager.calls == 1

    @pytest.mark.parametrize("cls", OCR_PROCESSORS, ids=lambda c: c.__name__)
    async def test_candidates_conform_to_engine_result_contract(self, cls):
        processor = _with_fake_engine(cls(), DUAL_ENGINE)

        candidates = await processor.extract_text_candidates(_rgb_image())

        for candidate in candidates:
            assert {"engine", "text", "confidence", "processing_time_ms"} <= set(candidate)
            assert isinstance(candidate["text"], str)
            assert 0.0 <= candidate["confidence"] <= 1.0

    @pytest.mark.parametrize("cls", OCR_PROCESSORS, ids=lambda c: c.__name__)
    async def test_all_engines_failed_yields_no_candidates(self, cls):
        """全部引擎失敗時回傳空候選,不得偽造一個候選充數"""
        processor = _with_fake_engine(cls(), [])

        assert await processor.extract_text_candidates(_rgb_image()) == []

    @pytest.mark.parametrize("cls", OCR_PROCESSORS, ids=lambda c: c.__name__)
    async def test_receives_bgr_converted_image(self, cls):
        processor = _with_fake_engine(cls(), DUAL_ENGINE)

        await processor.extract_text_candidates(_rgb_image(r=10, g=20, b=30))

        assert tuple(processor.engine_manager.last_image[0, 0]) == (30, 20, 10)


# --------------------------------------------------------------------------- #
# 影像理解型不受影響
# --------------------------------------------------------------------------- #
class TestImageUnderstandingUnaffected:
    def test_image_understanding_base_has_no_candidate_extraction(self):
        assert not hasattr(ImageUnderstandingProcessor, "extract_text_candidates")

    def test_repair_photo_is_not_ocr_processor(self):
        assert issubclass(RepairPhotoProcessor, ImageUnderstandingProcessor)
        assert not issubclass(RepairPhotoProcessor, OcrDocumentProcessor)
        assert not hasattr(RepairPhotoProcessor, "extract_text_candidates")
