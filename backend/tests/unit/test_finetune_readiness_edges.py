"""
fine-tune 決策門檻邊界測試(任務 15.2)

對應需求: 9.1, 9.2
"""

import pytest

from app.config import settings
from app.services.evaluation_service import EvaluationService
from app.services.correction_sample_service import CorrectionSampleService
from app.models.evaluation_record import EvaluationRecord
from app.lib.document_types import DocumentType


@pytest.fixture
def ctx(feedback_session):
    return EvaluationService(feedback_session), CorrectionSampleService(feedback_session), feedback_session


def _seed_train(samples, dtype, n):
    for i in range(n):
        samples.save(dtype, f"t{i}", {"a": i}, purpose="train")


def _acc(session, dtype, value, version):
    session.add(EvaluationRecord(
        document_type=dtype, metric_type="field_accuracy",
        value=value, labeled_set_version=version))
    session.commit()


class TestThresholdBoundaries:
    def test_exactly_min_samples_proceeds(self, ctx):
        eval_svc, samples, session = ctx
        _seed_train(samples, "transcript", 3)  # 恰達門檻
        _acc(session, "transcript", 0.60, "v1")
        _acc(session, "transcript", 0.61, "v2")  # 停滯
        r = eval_svc.readiness_for_finetune("transcript", min_samples=3, target_accuracy=0.9)
        assert r["ready"] is True

    def test_one_below_min_samples_blocks(self, ctx):
        eval_svc, samples, session = ctx
        _seed_train(samples, "transcript", 2)  # 少一筆
        _acc(session, "transcript", 0.60, "v1")
        _acc(session, "transcript", 0.61, "v2")
        r = eval_svc.readiness_for_finetune("transcript", min_samples=3, target_accuracy=0.9)
        assert r["ready"] is False

    def test_accuracy_exactly_target_keeps_fewshot(self, ctx):
        eval_svc, samples, session = ctx
        _seed_train(samples, "transcript", 3)
        _acc(session, "transcript", 0.90, "v1")  # 恰達目標
        r = eval_svc.readiness_for_finetune("transcript", min_samples=3, target_accuracy=0.9)
        assert r["ready"] is False

    def test_improvement_equal_epsilon_not_stalled(self, ctx):
        eval_svc, samples, session = ctx
        _seed_train(samples, "transcript", 3)
        _acc(session, "transcript", 0.60, "v1")
        _acc(session, "transcript", 0.62, "v2")  # 改善恰 = epsilon(0.02),不算停滯
        r = eval_svc.readiness_for_finetune("transcript", min_samples=3, target_accuracy=0.9)
        assert r["ready"] is False
        assert "提升" in r["reason"]


class TestDefaultsAndInput:
    def test_default_thresholds_from_settings(self, ctx):
        eval_svc, samples, session = ctx
        _seed_train(samples, "transcript", 5)  # 遠低於預設 200
        _acc(session, "transcript", 0.5, "v1")
        r = eval_svc.readiness_for_finetune("transcript")
        assert r["min_samples"] == settings.FINETUNE_MIN_SAMPLES
        assert r["target_accuracy"] == settings.FINETUNE_TARGET_ACCURACY
        assert r["ready"] is False

    def test_enum_document_type_normalized(self, ctx):
        eval_svc, _, _ = ctx
        r = eval_svc.readiness_for_finetune(DocumentType.BILL, min_samples=3)
        assert r["document_type"] == "bill"


class TestApprovalRecord:
    def test_rejected_decision_recorded(self, ctx):
        eval_svc, _, _ = ctx
        eval_svc.record_finetune_decision("transcript", approver="bob", approved=False)
        decisions = [r for r in eval_svc.list_records("transcript")
                     if r["metric_type"] == "finetune_decision"]
        assert decisions[0]["value"] == 0.0
        assert decisions[0]["labeled_set_version"] == "bob"
