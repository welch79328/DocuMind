"""
測試 fine-tune 就緒判斷與核准紀錄(任務 15.1)

依「訓練池樣本量達門檻」且「holdout 準確率停滯於目標下」標示可評估 fine-tune;
未達門檻維持 few-shot;決策附核准紀錄。僅決策,不執行訓練。

對應需求: 9.1, 9.2, 9.3, 9.4
"""

import pytest

from app.services.evaluation_service import EvaluationService
from app.services.correction_sample_service import CorrectionSampleService
from app.models.evaluation_record import EvaluationRecord


@pytest.fixture
def ctx(feedback_session):
    return EvaluationService(feedback_session), CorrectionSampleService(feedback_session), feedback_session


def _seed_train(samples, dtype, n):
    for i in range(n):
        samples.save(dtype, f"t{i}", {"a": i}, purpose="train")


def _add_accuracy(session, dtype, value, version):
    session.add(EvaluationRecord(
        document_type=dtype, metric_type="field_accuracy",
        value=value, labeled_set_version=version))
    session.commit()


class TestReadiness:
    def test_not_enough_samples_keeps_fewshot(self, ctx):
        eval_svc, samples, session = ctx
        _seed_train(samples, "transcript", 2)
        _add_accuracy(session, "transcript", 0.5, "v1")
        r = eval_svc.readiness_for_finetune("transcript", min_samples=3, target_accuracy=0.9)
        assert r["ready"] is False
        assert "樣本" in r["reason"]

    def test_no_evaluation_keeps_fewshot(self, ctx):
        eval_svc, samples, _ = ctx
        _seed_train(samples, "transcript", 3)
        r = eval_svc.readiness_for_finetune("transcript", min_samples=3)
        assert r["ready"] is False

    def test_accuracy_above_target_keeps_fewshot(self, ctx):
        eval_svc, samples, session = ctx
        _seed_train(samples, "transcript", 3)
        _add_accuracy(session, "transcript", 0.95, "v1")
        r = eval_svc.readiness_for_finetune("transcript", min_samples=3, target_accuracy=0.9)
        assert r["ready"] is False

    def test_improving_keeps_fewshot(self, ctx):
        eval_svc, samples, session = ctx
        _seed_train(samples, "transcript", 3)
        _add_accuracy(session, "transcript", 0.30, "v1")
        _add_accuracy(session, "transcript", 0.60, "v2")  # 仍在提升
        r = eval_svc.readiness_for_finetune("transcript", min_samples=3, target_accuracy=0.9)
        assert r["ready"] is False
        assert "提升" in r["reason"]

    def test_stalled_below_target_is_ready(self, ctx):
        eval_svc, samples, session = ctx
        _seed_train(samples, "transcript", 3)
        _add_accuracy(session, "transcript", 0.62, "v1")
        _add_accuracy(session, "transcript", 0.63, "v2")  # 停滯(改善 < epsilon)
        r = eval_svc.readiness_for_finetune("transcript", min_samples=3, target_accuracy=0.9)
        assert r["ready"] is True
        assert r["comparison"] is not None
        assert r["train_sample_count"] == 3
        assert r["latest_field_accuracy"] == 0.63


class TestApprovalRecord:
    def test_record_finetune_decision(self, ctx):
        eval_svc, _, _ = ctx
        eval_svc.record_finetune_decision("transcript", approver="alice", approved=True)
        records = eval_svc.list_records("transcript")
        decisions = [r for r in records if r["metric_type"] == "finetune_decision"]
        assert len(decisions) == 1
        assert decisions[0]["value"] == 1.0
        assert decisions[0]["labeled_set_version"] == "alice"
