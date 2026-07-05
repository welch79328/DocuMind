"""
測試評估服務 EvaluationService(任務 5.1)

- 純指標函數:Levenshtein、CER、欄位準確率
- evaluate:以 purpose='holdout' 為 ground truth,計算 CER / 欄位準確率並持久化
- 資料隔離:僅讀 holdout,train 樣本絕不納入評估(防洩漏)
- record_baseline / compare:記錄基準線與前後對照

對應需求: 8.1, 8.2, 8.3
"""

import pytest

from app.services.evaluation_service import (
    EvaluationService,
    levenshtein,
    character_error_rate,
    field_accuracy,
)
from app.services.correction_sample_service import CorrectionSampleService


@pytest.fixture
def eval_ctx(feedback_session):
    return (
        EvaluationService(feedback_session),
        CorrectionSampleService(feedback_session),
    )


# --------------------------------------------------------------------------- #
class TestPureMetrics:
    def test_levenshtein(self):
        assert levenshtein("", "") == 0
        assert levenshtein("abc", "abc") == 0
        assert levenshtein("abc", "abd") == 1
        assert levenshtein("12B45", "12845") == 1

    def test_cer_perfect(self):
        assert character_error_rate("128.45", "128.45") == 0.0

    def test_cer_one_char(self):
        # 6 字元中錯 1 → 1/6
        assert character_error_rate("12B.45", "128.45") == pytest.approx(1 / 6)

    def test_field_accuracy_all_correct(self):
        assert field_accuracy({"a": "1", "b": "2"}, {"a": "1", "b": "2"}) == 1.0

    def test_field_accuracy_half(self):
        assert field_accuracy({"a": "1", "b": "X"}, {"a": "1", "b": "2"}) == 0.5

    def test_field_accuracy_missing_prediction(self):
        assert field_accuracy({}, {"a": "1", "b": "2"}) == 0.0

    def test_field_accuracy_empty_truth_is_one(self):
        assert field_accuracy({}, {}) == 1.0


# --------------------------------------------------------------------------- #
class TestEvaluate:
    def test_evaluate_computes_and_persists(self, eval_ctx):
        eval_svc, samples = eval_ctx
        samples.save("transcript", "doc1", {"area": "128.45"}, purpose="holdout")
        samples.save("transcript", "doc2", {"area": "256.80"}, purpose="holdout")

        predictions = {
            "doc1": {"area": "128.45"},   # 完全正確
            "doc2": {"area": "256.8O"},   # 一字錯(0 vs O)
        }
        metrics = eval_svc.evaluate("transcript", predictions, holdout_version="v1")

        assert metrics["sample_count"] == 2
        assert 0.0 <= metrics["field_accuracy"] <= 1.0
        assert metrics["field_accuracy"] == 0.5  # doc1 對、doc2 欄位不符
        assert metrics["cer"] > 0.0

        # 已持久化(cer + field_accuracy 兩筆)
        records = eval_svc.list_records("transcript")
        metric_types = sorted(r["metric_type"] for r in records)
        assert metric_types == ["cer", "field_accuracy"]

    def test_evaluate_only_reads_holdout_not_train(self, eval_ctx):
        eval_svc, samples = eval_ctx
        samples.save("transcript", "h", {"area": "1"}, purpose="holdout")
        samples.save("transcript", "t", {"area": "1"}, purpose="train")  # 不應被評估
        metrics = eval_svc.evaluate("transcript", {"h": {"area": "1"}}, "v1")
        assert metrics["sample_count"] == 1  # 僅 holdout

    def test_evaluate_empty_holdout(self, eval_ctx):
        eval_svc, _ = eval_ctx
        metrics = eval_svc.evaluate("transcript", {}, "v1")
        assert metrics["sample_count"] == 0


# --------------------------------------------------------------------------- #
class TestBaselineAndCompare:
    def test_record_baseline_and_compare(self, eval_ctx):
        eval_svc, samples = eval_ctx
        samples.save("transcript", "d", {"area": "1"}, purpose="holdout")

        # 基準線:全錯
        eval_svc.evaluate("transcript", {"d": {"area": "9"}}, holdout_version="baseline",
                          is_baseline=True)
        # 改進後:全對
        eval_svc.evaluate("transcript", {"d": {"area": "1"}}, holdout_version="after")

        cmp = eval_svc.compare("transcript", "baseline", "after")
        assert cmp["field_accuracy"]["before"] == 0.0
        assert cmp["field_accuracy"]["after"] == 1.0
        assert cmp["field_accuracy"]["delta"] == 1.0
