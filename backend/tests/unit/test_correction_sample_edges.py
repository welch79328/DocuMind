"""
校正樣本邊界/防洩漏測試(任務 4.3)

補強 4.1/4.2 的邊界,聚焦 purpose 隔離與 dedupe 邊界:
- 預設 purpose=train;holdout 不被誤計為 train
- dedupe 不跨 document_type
- dedupe 不跨 purpose(避免去重時誤刪 holdout,保護評估集)

對應需求: 7.1, 7.4, 7.5
"""

import pytest

from app.services.correction_sample_service import CorrectionSampleService


@pytest.fixture
def svc(feedback_session):
    return CorrectionSampleService(feedback_session)


class TestPurposeIsolation:
    def test_default_purpose_is_train(self, svc):
        svc.save("transcript", "x", {"a": 1})
        assert svc.count("transcript", purpose="train") == 1
        assert svc.count("transcript", purpose="holdout") == 0

    def test_holdout_not_counted_or_listed_as_train(self, svc):
        svc.save("transcript", "h", {"a": 1}, purpose="holdout")
        assert svc.count("transcript", purpose="train") == 0
        train_list = svc.list_samples("transcript", purpose="train")
        assert train_list == []
        holdout_list = svc.list_samples("transcript", purpose="holdout")
        assert len(holdout_list) == 1


class TestDedupeBoundaries:
    def test_dedupe_no_duplicates_returns_zero(self, svc):
        svc.save("transcript", "a", {"x": 1})
        svc.save("transcript", "b", {"x": 2})
        assert svc.dedupe("transcript") == 0
        assert len(svc.list_samples("transcript")) == 2

    def test_dedupe_does_not_cross_document_type(self, svc):
        svc.save("transcript", "same", {"x": 1})
        svc.save("bill", "same", {"x": 2})  # 同 input_ref 但不同類型
        removed = svc.dedupe("transcript")
        assert removed == 0
        assert svc.count("bill") == 1  # bill 不受影響

    def test_dedupe_does_not_cross_purpose(self, svc):
        # train 與 holdout 即使同 input_ref,也不應互相去重(保護評估集)
        svc.save("transcript", "doc", {"x": 1}, purpose="train")
        svc.save("transcript", "doc", {"x": 2}, purpose="holdout")
        removed = svc.dedupe("transcript")
        assert removed == 0
        assert svc.count("transcript", purpose="train") == 1
        assert svc.count("transcript", purpose="holdout") == 1

    def test_dedupe_within_same_purpose_removes_duplicate(self, svc):
        svc.save("transcript", "doc", {"x": 1}, purpose="train")
        svc.save("transcript", "doc", {"x": 2}, purpose="train")
        assert svc.dedupe("transcript") == 1
        assert svc.count("transcript", purpose="train") == 1


class TestGoldenPreservesPurpose:
    def test_mark_golden_keeps_holdout_purpose(self, svc):
        sid = svc.save("transcript", "h", {"a": 1}, purpose="holdout")
        svc.mark_golden(sid, True)
        holdout = svc.list_samples("transcript", purpose="holdout")
        assert len(holdout) == 1
        assert holdout[0]["is_golden"] is True
