"""
共識機制接線與端到端驗證(任務 6.2 / 6.3 / 6.5)

單元測試無法偵測「共識靜默失效」——解析邏輯本身正確,失效點在候選來源與接線。
故本測試組驗證的是**整條路徑真的通了**:

- 各候選抽取走純規則路徑,LLM 呼叫次數為 0(成本硬約束:增幅 0%)
- 共識信心度確實寫入既有結果結構,並能觸發既有品質判定與複核入列
- 共識模式關閉時,結果與現行版本一致

對應需求: 4.1, 4.2, 4.3, 4.4, 4.7, 6.2, 6.5
"""

import numpy as np
import pytest
from PIL import Image

from app.lib.multi_type_ocr.processor import OcrDocumentProcessor


def _image():
    return Image.fromarray(np.zeros((8, 8, 3), dtype=np.uint8))


class _FakeEngineManager:
    def __init__(self, engine_results):
        self.engine_results = engine_results
        self.calls = 0

    async def extract_text_multi_engine(self, image_array, page_number: int = 1):
        self.calls += 1
        if not self.engine_results:
            return "", 0.0, []
        best = max(self.engine_results, key=lambda r: r["confidence"])
        return best["text"], best["confidence"], list(self.engine_results)

    def fuse(self, results):
        if not results:
            return "", 0.0
        best = max(results, key=lambda r: r["confidence"])
        return best["text"], best["confidence"]


def _engine(engine, text, confidence):
    return {
        "engine": engine, "text": text,
        "confidence": confidence, "processing_time_ms": 5,
    }


class _SpyProcessor(OcrDocumentProcessor):
    """記錄各步驟呼叫參數的 OCR 型處理器;欄位抽取依文字內容回傳不同結果"""

    def __init__(self, engine_results, extraction_by_text=None):
        self.engine_manager = _FakeEngineManager(engine_results)
        self.extraction_by_text = extraction_by_text or {}
        self.extract_fields_calls = []
        self.llm_calls = 0

    async def preprocess(self, image):
        return image

    async def extract_text(self, image):
        text, confidence, _ = await self.engine_manager.extract_text_multi_engine(
            self._to_bgr_array(image)
        )
        return text, confidence

    async def extract_text_candidates(self, image):
        _t, _c, results = await self.engine_manager.extract_text_multi_engine(
            self._to_bgr_array(image)
        )
        return results

    async def postprocess(self, text, confidence, image_data=None):
        stats = {"typo_fixes": 0}
        if image_data is not None:
            stats.update({"llm_used": True, "llm_cost": 0.02})
        return text, stats

    async def extract_fields(self, text, image_data=None, enable_llm=False, few_shot=None):
        self.extract_fields_calls.append({
            "text": text, "image_data": image_data,
            "enable_llm": enable_llm, "few_shot": few_shot,
        })
        # 既有抽取的 LLM 觸發條件:enable_llm 與 image_data 同時成立
        if enable_llm and image_data:
            self.llm_calls += 1
        default = {"land_number": None, "field_confidences": {"land_number": 0.0}}
        return dict(self.extraction_by_text.get(text, default))


DISAGREEING = [
    _engine("paddleocr", "地號0221-0000", 0.91),
    _engine("tesseract", "地號0221-0001", 0.78),
]
AGREEING = [
    _engine("paddleocr", "地號0221-0000", 0.91),
    _engine("tesseract", "地號0221-0000 ", 0.78),
]
EXTRACTIONS = {
    "地號0221-0000": {
        "land_number": "0221-0000",
        "field_confidences": {"land_number": 0.9},
    },
    "地號0221-0001": {
        "land_number": "0221-0001",
        "field_confidences": {"land_number": 0.88},
    },
    "地號0221-0000 ": {
        "land_number": "0221-0000",
        "field_confidences": {"land_number": 0.88},
    },
}


@pytest.fixture
def consensus_on(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "OCR_CONSENSUS_ENABLED", True)
    monkeypatch.setattr(settings, "OCR_CONSENSUS_DISAGREE_PENALTY", 0.3)


@pytest.fixture
def consensus_off(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "OCR_CONSENSUS_ENABLED", False)
    monkeypatch.setattr(settings, "OCR_FUSION_METHOD", "best")


def _processor(engine_results=DISAGREEING):
    return _SpyProcessor(engine_results, EXTRACTIONS)


# --------------------------------------------------------------------------- #
# 任務 6.2:各候選走純規則路徑,LLM 只跑一次
# --------------------------------------------------------------------------- #
class TestCandidateExtractionCost:
    async def test_candidate_extraction_never_triggers_llm(self, consensus_on):
        processor = _processor()

        await processor.analyze(_image(), image_data="b64", enable_llm=True)

        candidate_calls = [
            c for c in processor.extract_fields_calls
            if c["text"] in ("地號0221-0000", "地號0221-0001")
            and c is not processor.extract_fields_calls[-1]
        ]
        assert candidate_calls, "候選抽取未發生,共識來源不存在"
        assert all(c["enable_llm"] is False for c in candidate_calls)
        assert all(c["image_data"] is None for c in candidate_calls)

    async def test_llm_invoked_exactly_once(self, consensus_on):
        processor = _processor()

        await processor.analyze(_image(), image_data="b64", enable_llm=True)

        assert processor.llm_calls == 1

    async def test_llm_cost_identical_to_single_engine_mode(
        self, monkeypatch, consensus_on
    ):
        """硬約束:共識模式的 LLM 成本增幅為 0%"""
        from app.config import settings

        with_consensus = _processor()
        await with_consensus.analyze(_image(), image_data="b64", enable_llm=True)

        monkeypatch.setattr(settings, "OCR_CONSENSUS_ENABLED", False)
        single = _processor()
        await single.analyze(_image(), image_data="b64", enable_llm=True)

        assert with_consensus.llm_calls == single.llm_calls == 1

    async def test_no_additional_engine_run(self, consensus_on):
        """共識模式不得多跑一次引擎"""
        processor = _processor()

        await processor.analyze(_image(), image_data="b64", enable_llm=True)

        assert processor.engine_manager.calls == 1

    async def test_extra_work_is_bounded_to_regex_extraction(self, consensus_on):
        """
        共識模式的額外開銷僅為「每個候選一次規則式抽取」。

        耗時增幅 < 1.5 倍的目標由此結構保證;實際牆鐘時間於基準測試量測。
        """
        processor = _processor()

        await processor.analyze(_image(), image_data="b64", enable_llm=True)

        # 2 個候選 + 1 次既有抽取
        assert len(processor.extract_fields_calls) == 3

    async def test_llm_disabled_produces_no_llm_call(self, consensus_on):
        processor = _processor()

        await processor.analyze(_image(), image_data="b64", enable_llm=False)

        assert processor.llm_calls == 0


# --------------------------------------------------------------------------- #
# 任務 6.3:共識訊號接入既有結果結構
# --------------------------------------------------------------------------- #
class TestConsensusSignalWiring:
    async def test_page_result_carries_consensus_detail(self, consensus_on):
        processor = _processor()

        page = await processor.analyze(_image(), image_data="b64", enable_llm=True)

        assert page["consensus"]["available"] is True
        agreement = page["consensus"]["agreements"]["land_number"]
        assert agreement["agreed"] is False
        assert agreement["engine_values"] == {
            "paddleocr": "0221-0000", "tesseract": "0221-0001",
        }

    async def test_disagreement_lowers_field_confidence(self, consensus_on):
        processor = _processor()

        page = await processor.analyze(_image(), image_data="b64", enable_llm=True)

        assert page["field_confidences"]["land_number"] == 0.3
        assert page["structured_data"]["field_confidences"]["land_number"] == 0.3

    async def test_agreement_keeps_conservative_confidence(self, consensus_on):
        processor = _SpyProcessor(AGREEING, EXTRACTIONS)

        page = await processor.analyze(_image(), image_data="b64", enable_llm=True)

        assert page["consensus"]["agreements"]["land_number"]["agreed"] is True
        assert page["field_confidences"]["land_number"] == 0.88

    async def test_consensus_never_raises_existing_confidence(self, consensus_on):
        """共識只能收緊攔截,不得放寬——信心度回報不得高於實際可信程度"""
        low = {
            "地號0221-0000": {
                "land_number": "0221-0000",
                "field_confidences": {"land_number": 0.95},
            },
            "地號0221-0000 ": {
                "land_number": "0221-0000",
                "field_confidences": {"land_number": 0.95},
            },
        }
        processor = _SpyProcessor(AGREEING, low)
        # 融合後文字的抽取信心度刻意設低
        low["地號0221-0000"] = {
            "land_number": "0221-0000",
            "field_confidences": {"land_number": 0.40},
        }

        page = await processor.analyze(_image(), image_data="b64", enable_llm=True)

        assert page["field_confidences"]["land_number"] <= 0.40

    async def test_quality_assessor_called_with_unchanged_signature(self, consensus_on):
        """判定權仍在既有 QualityAssessor,呼叫方式零變更"""
        from app.lib.ocr_enhanced.quality_assessor import QualityAssessor

        processor = _processor()
        page = await processor.analyze(_image(), image_data="b64", enable_llm=True)

        decision = QualityAssessor().assess(
            page["overall_confidence"], page["field_confidences"]
        )

        assert decision["needs_review"] is True
        assert "land_number" in decision["low_confidence_fields"]


class TestConsensusDisabled:
    async def test_no_consensus_key_when_disabled(self, consensus_off):
        processor = _processor()

        page = await processor.analyze(_image(), image_data="b64", enable_llm=True)

        assert "consensus" not in page

    async def test_field_confidences_untouched_when_disabled(self, consensus_off):
        processor = _processor()

        page = await processor.analyze(_image(), image_data="b64", enable_llm=True)

        # 沿用既有抽取自評信心度,未被共識壓低
        assert page["field_confidences"]["land_number"] == 0.9

    async def test_only_one_extraction_when_disabled(self, consensus_off):
        processor = _processor()

        await processor.analyze(_image(), image_data="b64", enable_llm=True)

        assert len(processor.extract_fields_calls) == 1

    async def test_existing_page_result_keys_unchanged(self, consensus_off):
        processor = _processor()

        page = await processor.analyze(_image(), image_data="b64", enable_llm=True)

        assert set(page) == {
            "page_number", "original_image", "ocr_raw", "rule_postprocessed",
            "llm_postprocessed", "structured_data", "accuracy",
            "processing_steps", "field_confidences", "overall_confidence",
        }


class TestFusionModeSwitch:
    async def test_cross_check_fusion_method_enables_consensus(self, monkeypatch):
        """融合模式可由設定選擇(需求 4.7)"""
        from app.config import settings
        monkeypatch.setattr(settings, "OCR_CONSENSUS_ENABLED", False)
        monkeypatch.setattr(settings, "OCR_FUSION_METHOD", "cross_check")

        processor = _processor()
        page = await processor.analyze(_image(), image_data="b64", enable_llm=True)

        assert page["consensus"]["available"] is True

    def test_cross_check_is_a_recognised_fusion_method(self):
        from app.lib.ocr_enhanced.types import FusionMethod

        import typing
        assert "cross_check" in typing.get_args(FusionMethod)
        # 既有模式不得消失
        for existing in ("best", "weighted", "vote", "smart"):
            assert existing in typing.get_args(FusionMethod)


class TestDegradation:
    async def test_single_candidate_marks_consensus_unavailable(self, consensus_on):
        processor = _SpyProcessor(
            [_engine("tesseract", "地號0221-0000", 0.78)], EXTRACTIONS
        )

        page = await processor.analyze(_image(), image_data="b64", enable_llm=True)

        assert page["consensus"]["available"] is False
        # 退回單引擎信心度,不偽報高信心度
        assert page["field_confidences"]["land_number"] == 0.9

    async def test_all_engines_failed_does_not_crash(self, consensus_on):
        processor = _SpyProcessor([], EXTRACTIONS)

        page = await processor.analyze(_image(), image_data="b64", enable_llm=True)

        assert page["ocr_raw"]["confidence"] == 0.0
        assert page["consensus"]["available"] is False

    async def test_consensus_failure_degrades_to_single_engine(
        self, consensus_on, monkeypatch
    ):
        """共識解析失敗須降級為單引擎模式,不得使整頁處理失敗"""
        from app.lib.multi_type_ocr import processor as processor_module

        class _Exploding:
            def __init__(self, *args, **kwargs):
                raise RuntimeError("共識爆炸")

        monkeypatch.setattr(processor_module, "FieldConsensusResolver", _Exploding)

        processor = _processor()
        page = await processor.analyze(_image(), image_data="b64", enable_llm=True)

        assert page["structured_data"] is not None
        assert "consensus" not in page


# --------------------------------------------------------------------------- #
# 任務 6.5:端到端(共識 → 品質判定 → 複核入列)
# --------------------------------------------------------------------------- #
class TestEndToEndReviewEnqueue:
    async def test_disagreement_reaches_review_queue(self, consensus_on, feedback_session):
        from app.api.v1.analyze import _apply_confidence_gating
        from app.services.review_queue_service import ReviewQueueService

        processor = _processor()
        page = await processor.analyze(_image(), image_data="b64", enable_llm=True)
        page.pop("original_image", None)

        result = {"document_type": "transcript", "pages": [page]}
        _apply_confidence_gating(result, feedback_session)

        assert result["needs_review"] is True
        assert result["review_item_id"] is not None
        assert result["field_confidences"]["land_number"] == 0.3

        queued = ReviewQueueService(feedback_session).list_queue()
        assert len(queued) == 1

    async def test_agreement_passes_through_without_review(
        self, consensus_on, feedback_session
    ):
        from app.api.v1.analyze import _apply_confidence_gating

        processor = _SpyProcessor(AGREEING, EXTRACTIONS)
        page = await processor.analyze(_image(), image_data="b64", enable_llm=True)
        page.pop("original_image", None)

        result = {"document_type": "transcript", "pages": [page]}
        _apply_confidence_gating(result, feedback_session)

        assert result["needs_review"] is False
        assert result["review_item_id"] is None

    async def test_consensus_detail_survives_response_schema(self, consensus_on):
        """共識明細須通過回應 schema,不得被過濾掉"""
        from app.schemas.analyze import OcrPageResult

        processor = _processor()
        page = await processor.analyze(_image(), image_data="b64", enable_llm=True)
        page.pop("original_image", None)

        model = OcrPageResult(**page)

        assert model.consensus is not None
        assert model.consensus["available"] is True
        assert model.field_confidences["land_number"] == 0.3

    def test_schema_backward_compatible_without_consensus(self):
        """既有欄位語意不變,新增欄位皆為選填"""
        from app.schemas.analyze import OcrPageResult

        model = OcrPageResult(
            page_number=1,
            ocr_raw={"text": "x", "confidence": 0.9},
            rule_postprocessed={"text": "x", "stats": {}},
        )

        assert model.consensus is None
        assert model.field_confidences == {}
