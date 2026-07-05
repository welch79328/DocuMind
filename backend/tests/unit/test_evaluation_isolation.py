"""
評估指標與資料隔離測試(任務 5.3)

- 指標計算正確性(多欄位、多樣本、忽略多餘預測欄位)
- 雙向資料隔離(防洩漏):
  - train 不被評估讀取(EvaluationService 僅讀 holdout)
  - holdout 不被 few-shot 取用(CorrectionSampleService.list_for_fewshot 僅回 train)

對應需求: 8.1, 8.2
"""

import pytest

from app.services.evaluation_service import (
    EvaluationService,
    character_error_rate,
    field_accuracy,
)
from app.services.correction_sample_service import CorrectionSampleService


@pytest.fixture
def ctx(feedback_session):
    return (
        EvaluationService(feedback_session),
        CorrectionSampleService(feedback_session),
    )


class TestMetricCorrectness:
    def test_field_accuracy_ignores_extra_predicted_fields(self):
        # 預測多出的欄位不影響準確率(以真值欄位為分母)
        acc = field_accuracy({"a": "1", "extra": "9"}, {"a": "1"})
        assert acc == 1.0

    def test_cer_multi_field_text(self):
        # 完全正確 → 0
        assert character_error_rate("a=1\nb=2", "a=1\nb=2") == 0.0
        # 一個字元錯
        assert character_error_rate("a=1\nb=3", "a=1\nb=2") == pytest.approx(1 / 7)

    def test_evaluate_aggregates_multiple_samples(self, ctx):
        eval_svc, samples = ctx
        samples.save("transcript", "d1", {"area": "1"}, purpose="holdout")
        samples.save("transcript", "d2", {"area": "2"}, purpose="holdout")
        # d1 對、d2 錯 → 平均欄位準確率 0.5
        metrics = eval_svc.evaluate(
            "transcript", {"d1": {"area": "1"}, "d2": {"area": "X"}}, "v1")
        assert metrics["sample_count"] == 2
        assert metrics["field_accuracy"] == 0.5


class TestDataIsolation:
    def test_train_not_read_by_evaluation(self, ctx):
        eval_svc, samples = ctx
        samples.save("transcript", "h", {"area": "1"}, purpose="holdout")
        samples.save("transcript", "t1", {"area": "1"}, purpose="train")
        samples.save("transcript", "t2", {"area": "1"}, purpose="train")
        # 評估只看 1 筆 holdout,不因 train 增加樣本數
        metrics = eval_svc.evaluate("transcript", {"h": {"area": "1"}}, "v1")
        assert metrics["sample_count"] == 1

    def test_holdout_not_taken_by_fewshot(self, ctx):
        _, samples = ctx
        samples.save("transcript", "train-1", {"area": "1"}, purpose="train")
        samples.save("transcript", "hold-1", {"area": "2"}, purpose="holdout")
        fewshot = samples.list_for_fewshot("transcript")
        input_refs = {s["input_ref"] for s in fewshot}
        assert input_refs == {"train-1"}  # 絕不含 holdout

    def test_list_for_fewshot_cannot_return_holdout_even_if_all_holdout(self, ctx):
        _, samples = ctx
        samples.save("transcript", "h1", {"a": 1}, purpose="holdout")
        samples.save("transcript", "h2", {"a": 2}, purpose="holdout")
        assert samples.list_for_fewshot("transcript") == []

    def test_round_trip_no_overlap(self, ctx):
        eval_svc, samples = ctx
        samples.save("bill", "x", {"amount": "100"}, purpose="train")
        samples.save("bill", "y", {"amount": "200"}, purpose="holdout")
        # few-shot 只拿 train
        assert {s["input_ref"] for s in samples.list_for_fewshot("bill")} == {"x"}
        # 評估只拿 holdout
        m = eval_svc.evaluate("bill", {"y": {"amount": "200"}}, "v1")
        assert m["sample_count"] == 1
        assert m["field_accuracy"] == 1.0
