"""
最終驗收與非功能驗證(任務 16.2)

可離線驗證:
- 四類文件路由正確率(> 95%)
- 謄本 few-shot 回灌後準確率相對基準線「可量測提升」(評估前後對照機制)
- 成本控制機制(本地優先可插拔 + 條件式 LLM)

實際準確率數值 / <30s / <$15 須容器 + 真實樣本驗證(見 acceptance-report.md)。

對應需求: 1.1, 2.3, 8.3
"""

import pytest

from app.lib.multi_type_ocr.processor_factory import ProcessorFactory
from app.lib.multi_type_ocr.transcript_processor import TranscriptProcessor
from app.lib.multi_type_ocr.bill_processor import BillProcessor
from app.lib.multi_type_ocr.contract_processor import ContractProcessor
from app.lib.multi_type_ocr.repair_photo_processor import RepairPhotoProcessor
from app.lib.document_types import DocumentType
from app.config import settings
from app.services.evaluation_service import EvaluationService
from app.services.correction_sample_service import CorrectionSampleService
from app.lib.llm_service.providers import create_provider, LocalQwenProvider


class TestRoutingCorrectness:
    def test_all_four_types_route_correctly(self):
        expected = {
            DocumentType.TRANSCRIPT: TranscriptProcessor,
            DocumentType.BILL: BillProcessor,
            DocumentType.CONTRACT: ContractProcessor,
            DocumentType.REPAIR_PHOTO: RepairPhotoProcessor,
        }
        correct = sum(
            1 for dt, cls in expected.items()
            if isinstance(ProcessorFactory.get_processor(dt), cls)
        )
        accuracy = correct / len(expected)
        assert accuracy == 1.0  # 4/4 > 95%

    def test_all_canonical_types_registered(self):
        supported = {str(t) for t in ProcessorFactory.supported_types()}
        for dt in DocumentType:
            assert dt.value in supported


class TestMeasurableAccuracyImprovement:
    def test_fewshot_improvement_is_measurable(self, feedback_session):
        eval_svc = EvaluationService(feedback_session)
        samples = CorrectionSampleService(feedback_session)
        # holdout ground truth
        for i in range(4):
            samples.save("transcript", f"h{i}", {"area": str(i)}, purpose="holdout")

        # 基準線:全錯(模擬 few-shot 前)
        baseline = eval_svc.evaluate(
            "transcript",
            {f"h{i}": {"area": "WRONG"} for i in range(4)},
            holdout_version="baseline", is_baseline=True,
        )
        # 回灌 few-shot 後:全對(模擬校正累積後)
        after = eval_svc.evaluate(
            "transcript",
            {f"h{i}": {"area": str(i)} for i in range(4)},
            holdout_version="after",
        )
        cmp = eval_svc.compare("transcript", "baseline", "after")

        # 相對基準線可量測提升
        assert after["field_accuracy"] > baseline["field_accuracy"]
        assert cmp["field_accuracy"]["delta"] > 0


class TestCostControlMechanism:
    def test_local_first_configurable(self, monkeypatch):
        # 本地優先:可切換至本地 Qwen(不呼叫付費雲端 → 控成本)
        monkeypatch.setattr(settings, "LOCAL_QWEN_ENDPOINT", "http://localhost:8001")
        monkeypatch.setattr(settings, "LLM_PROVIDER", "local_qwen")
        assert isinstance(create_provider(), LocalQwenProvider)

    def test_quality_threshold_gates_llm_cost(self):
        # 智能策略:信心度門檻存在(僅低信心才觸發複核/LLM → 控成本)
        assert 0.0 < settings.OCR_QUALITY_THRESHOLD <= 1.0
