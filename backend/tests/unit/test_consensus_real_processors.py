"""
真實處理器的共識端到端驗證(任務 6.5)

前一組測試以處理器替身驗證接線邏輯,但**替身正確不代表產線正確**——共識靜默
失效的失效點正是在真實子類別的覆寫與欄位抽取器的實際輸出形狀上。故本組一律
使用產線類別(`TranscriptProcessor` / `ContractProcessor` / `BillProcessor`),
僅把引擎替換為不執行真實 OCR 的假引擎。

對應需求: 4.1, 4.2, 4.3, 4.4
"""

import numpy as np
import pytest
from PIL import Image

from app.lib.multi_type_ocr.bill_processor import BillProcessor
from app.lib.multi_type_ocr.contract_processor import ContractProcessor
from app.lib.multi_type_ocr.transcript_processor import TranscriptProcessor


def _image():
    return Image.fromarray(np.full((40, 200, 3), 255, dtype=np.uint8))


class _FakeEngineManager:
    """回傳預設文字的假引擎;記錄執行次數以驗證成本"""

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


def _engine(name, text, confidence):
    return {
        "engine": name, "text": text,
        "confidence": confidence, "processing_time_ms": 5,
    }


# 兩引擎對「地號」讀出不同結果:0221-0000 vs 0221-0001(真實差異,非格式差異)
TRANSCRIPT_DISAGREE = [
    _engine("paddleocr", "地號: 0221-0000\n面積: 153.00平方公尺\n所有權人: 王小明", 0.91),
    _engine("tesseract", "地號: 0221-0001\n面積: 153.00平方公尺\n所有權人: 王小明", 0.85),
]
TRANSCRIPT_AGREE = [
    _engine("paddleocr", "地號: 0221-0000\n面積: 153.00平方公尺\n所有權人: 王小明", 0.91),
    _engine("tesseract", "地號: 0221-0000\n面積: 153.00 平方公尺\n所有權人: 王小明", 0.85),
]


@pytest.fixture
def consensus_on(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "OCR_CONSENSUS_ENABLED", True)
    monkeypatch.setattr(settings, "OCR_CONSENSUS_DISAGREE_PENALTY", 0.3)


@pytest.fixture(autouse=True)
def no_preprocessing(monkeypatch):
    """略過影像預處理(需 OpenCV 實作),本組只驗共識路徑"""
    async def passthrough(self, image):
        return image

    for cls in (TranscriptProcessor, ContractProcessor, BillProcessor):
        monkeypatch.setattr(cls, "preprocess", passthrough)


def _with_engines(processor, engine_results):
    processor.engine_manager = _FakeEngineManager(engine_results)
    return processor


class TestTranscriptConsensusActuallyRuns:
    async def test_consensus_available_in_real_pipeline(self, consensus_on):
        """核心防護:產線處理器跑完後共識必須真的可用"""
        processor = _with_engines(TranscriptProcessor(), TRANSCRIPT_DISAGREE)

        page = await processor.analyze(_image(), image_data=None, enable_llm=False)

        assert "consensus" in page, "共識未啟動——候選來源或覆寫失效"
        assert page["consensus"]["available"] is True

    async def test_disagreed_field_confidence_lowered(self, consensus_on):
        processor = _with_engines(TranscriptProcessor(), TRANSCRIPT_DISAGREE)

        page = await processor.analyze(_image(), image_data=None, enable_llm=False)

        agreements = page["consensus"]["agreements"]
        assert agreements["land_number"]["agreed"] is False
        assert agreements["land_number"]["engine_values"] == {
            "paddleocr": "0221-0000", "tesseract": "0221-0001",
        }
        assert page["field_confidences"]["land_number"] <= 0.3

    async def test_disagreement_triggers_review_decision(self, consensus_on):
        from app.lib.ocr_enhanced.quality_assessor import QualityAssessor

        processor = _with_engines(TranscriptProcessor(), TRANSCRIPT_DISAGREE)
        page = await processor.analyze(_image(), image_data=None, enable_llm=False)

        decision = QualityAssessor().assess(
            page["overall_confidence"], page["field_confidences"]
        )

        assert decision["needs_review"] is True
        assert "land_number" in decision["low_confidence_fields"]

    async def test_format_only_difference_stays_agreed(self, consensus_on):
        """`153.00平方公尺` 與 `153.00 平方公尺` 僅為格式差異,不得誤判為不一致"""
        processor = _with_engines(TranscriptProcessor(), TRANSCRIPT_AGREE)

        page = await processor.analyze(_image(), image_data=None, enable_llm=False)

        agreements = page["consensus"]["agreements"]
        assert agreements["land_number"]["agreed"] is True
        assert agreements["area"]["agreed"] is True

    async def test_engine_runs_exactly_once(self, consensus_on):
        processor = _with_engines(TranscriptProcessor(), TRANSCRIPT_DISAGREE)

        await processor.analyze(_image(), image_data=None, enable_llm=False)

        assert processor.engine_manager.calls == 1

    async def test_disabled_mode_leaves_no_consensus_key(self, monkeypatch):
        from app.config import settings
        monkeypatch.setattr(settings, "OCR_CONSENSUS_ENABLED", False)
        monkeypatch.setattr(settings, "OCR_FUSION_METHOD", "best")

        processor = _with_engines(TranscriptProcessor(), TRANSCRIPT_DISAGREE)
        page = await processor.analyze(_image(), image_data=None, enable_llm=False)

        assert "consensus" not in page


class TestBillConsensusActuallyRuns:
    async def test_consensus_available(self, consensus_on):
        processor = _with_engines(BillProcessor(), [
            _engine("paddleocr", "應繳金額: 1,530 元\n繳費期限: 民國114年09月26日", 0.9),
            _engine("tesseract", "應繳金額: 1,538 元\n繳費期限: 民國114年09月26日", 0.8),
        ])

        page = await processor.analyze(_image(), image_data=None, enable_llm=False)

        assert page["consensus"]["available"] is True


class TestContractConsensusActuallyRuns:
    async def test_nested_extraction_shape_supported(self, consensus_on):
        """合約抽取輸出為巢狀且無逐欄位信心度,共識仍須能運作"""
        processor = _with_engines(ContractProcessor(), [
            _engine("paddleocr", "合約編號: A-001\n甲方: 甲公司\n乙方: 乙公司", 0.9),
            _engine("tesseract", "合約編號: A-002\n甲方: 甲公司\n乙方: 乙公司", 0.8),
        ])

        page = await processor.analyze(_image(), image_data=None, enable_llm=False)

        assert page["consensus"]["available"] is True
        assert page["consensus"]["agreements"], "巢狀輸出未被攤平為可比對欄位"


class TestLlmCostUnchanged:
    @staticmethod
    def _spy_llm(monkeypatch):
        """監看欄位抽取器的 LLM 進入點,回傳呼叫記錄"""
        from app.lib.multi_type_ocr.field_extraction_base import RegexFieldExtractor

        calls = []

        async def spy(self, text, image_data, needs, few_shot):
            calls.append(text)
            return {}

        monkeypatch.setattr(RegexFieldExtractor, "_extract_with_llm", spy)
        return calls

    async def test_llm_precondition_holds(self, consensus_on, monkeypatch):
        """
        前提檢查:此測試資料確實會觸發 LLM 補全。

        若此處為 0,下方的成本測試將**空洞通過**——那正是共識成本失控時
        最不會被發現的路徑。
        """
        calls = self._spy_llm(monkeypatch)

        processor = _with_engines(TranscriptProcessor(), TRANSCRIPT_DISAGREE)
        await processor.analyze(_image(), image_data="fake-b64", enable_llm=True)

        assert len(calls) >= 1, "測試資料未觸發 LLM,成本測試失去意義"

    async def test_llm_called_once_and_only_on_fused_text(
        self, consensus_on, monkeypatch
    ):
        """硬約束:LLM 成本增幅 0%——候選階段一次都不得呼叫"""
        calls = self._spy_llm(monkeypatch)

        processor = _with_engines(TranscriptProcessor(), TRANSCRIPT_DISAGREE)
        await processor.analyze(_image(), image_data="fake-b64", enable_llm=True)

        assert len(calls) == 1
        # 僅對融合後文字呼叫;任一候選原文出現即代表成本隨候選數倍增
        fused = max(TRANSCRIPT_DISAGREE, key=lambda r: r["confidence"])["text"]
        assert calls[0] == fused

    async def test_consensus_mode_llm_cost_equals_single_engine(
        self, consensus_on, monkeypatch
    ):
        from app.config import settings

        with_consensus = self._spy_llm(monkeypatch)
        processor = _with_engines(TranscriptProcessor(), TRANSCRIPT_DISAGREE)
        await processor.analyze(_image(), image_data="fake-b64", enable_llm=True)
        consensus_count = len(with_consensus)

        monkeypatch.setattr(settings, "OCR_CONSENSUS_ENABLED", False)
        monkeypatch.setattr(settings, "OCR_FUSION_METHOD", "best")
        single = self._spy_llm(monkeypatch)
        baseline = _with_engines(TranscriptProcessor(), TRANSCRIPT_DISAGREE)
        await baseline.analyze(_image(), image_data="fake-b64", enable_llm=True)

        assert consensus_count == len(single) == 1
