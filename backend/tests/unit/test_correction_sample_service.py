"""
測試校正樣本服務 CorrectionSampleService(任務 4.1)

以 in-memory SQLite 驗證:
- save:依類型入庫,預設 purpose=train、is_golden=False
- mark_golden:標記 / 取消黃金範例
- dedupe:同類型同來源重複去重,保留黃金 / 最新
- 僅人工校正(submit_correction)會觸發入庫;analyze 攔截(enqueue)不入庫

對應需求: 7.1, 7.2, 7.4, 7.5
"""

import pytest

from app.lib.document_types import DocumentType
from app.services.correction_sample_service import CorrectionSampleService
from app.services.review_queue_service import ReviewQueueService


@pytest.fixture
def sample_svc(feedback_session):
    return CorrectionSampleService(feedback_session)


class TestSave:
    def test_save_creates_sample_with_defaults(self, sample_svc):
        sid = sample_svc.save(
            document_type=DocumentType.TRANSCRIPT,
            input_ref="土地登記 12B.45",
            corrected_fields={"area": "128.45"},
        )
        assert sid is not None
        samples = sample_svc.list_samples(DocumentType.TRANSCRIPT)
        assert len(samples) == 1
        s = samples[0]
        assert s["document_type"] == "transcript"
        assert s["purpose"] == "train"
        assert s["is_golden"] is False
        assert s["corrected_fields"] == {"area": "128.45"}

    def test_save_stores_source_review_id(self, sample_svc):
        sid = sample_svc.save(
            document_type="contract", input_ref="x",
            corrected_fields={"a": 1},
            source_review_id="99999999-9999-9999-9999-999999999999",
        )
        s = [x for x in sample_svc.list_samples("contract") if x["id"] == sid][0]
        assert s["source_review_id"] == "99999999-9999-9999-9999-999999999999"

    def test_save_respects_purpose_holdout(self, sample_svc):
        sample_svc.save("bill", "x", {"amount": "100"}, purpose="holdout")
        assert len(sample_svc.list_samples("bill", purpose="holdout")) == 1
        assert len(sample_svc.list_samples("bill", purpose="train")) == 0


class TestMarkGolden:
    def test_mark_and_unmark_golden(self, sample_svc):
        sid = sample_svc.save("transcript", "x", {"a": 1})
        sample_svc.mark_golden(sid, True)
        assert sample_svc.list_samples("transcript")[0]["is_golden"] is True
        sample_svc.mark_golden(sid, False)
        assert sample_svc.list_samples("transcript")[0]["is_golden"] is False

    def test_mark_nonexistent_raises(self, sample_svc):
        with pytest.raises(ValueError):
            sample_svc.mark_golden("00000000-0000-0000-0000-000000000000", True)


class TestDedupe:
    def test_dedupe_removes_duplicates_same_input(self, sample_svc):
        # 同類型、同 input_ref 視為重複
        sample_svc.save("transcript", "same-doc", {"area": "1"})
        sample_svc.save("transcript", "same-doc", {"area": "2"})
        sample_svc.save("transcript", "other-doc", {"area": "3"})
        removed = sample_svc.dedupe("transcript")
        assert removed == 1
        remaining = sample_svc.list_samples("transcript")
        assert len(remaining) == 2
        input_refs = sorted(s["input_ref"] for s in remaining)
        assert input_refs == ["other-doc", "same-doc"]

    def test_dedupe_keeps_golden(self, sample_svc):
        s1 = sample_svc.save("transcript", "doc", {"area": "1"})
        sample_svc.save("transcript", "doc", {"area": "2"})
        sample_svc.mark_golden(s1, True)
        sample_svc.dedupe("transcript")
        remaining = sample_svc.list_samples("transcript")
        assert len(remaining) == 1
        assert remaining[0]["id"] == s1  # 保留黃金範例


class TestAntiReinforcementBias:
    def test_submit_correction_creates_sample(self, feedback_session):
        # 人工校正 → 自動入對應類型樣本庫
        sample_svc = CorrectionSampleService(feedback_session)
        review_svc = ReviewQueueService(feedback_session, sample_service=sample_svc)
        item_id = review_svc.enqueue(
            document_id=None, document_type=DocumentType.TRANSCRIPT,
            overall_confidence=0.6,
            result={"pages": [{"ocr_raw": {"text": "12B.45"}}]},
        )
        review_svc.claim(item_id, "alice")
        review_svc.submit_correction(item_id, "alice", {"area": "128.45"})

        samples = sample_svc.list_samples("transcript")
        assert len(samples) == 1
        assert samples[0]["corrected_fields"] == {"area": "128.45"}
        assert samples[0]["source_review_id"] == item_id

    def test_enqueue_alone_creates_no_sample(self, feedback_session):
        # analyze 攔截(僅入列)不應產生校正樣本(防自我增強偏誤)
        sample_svc = CorrectionSampleService(feedback_session)
        review_svc = ReviewQueueService(feedback_session, sample_service=sample_svc)
        review_svc.enqueue(
            document_id=None, document_type=DocumentType.TRANSCRIPT,
            overall_confidence=0.6, result={"pages": []},
        )
        assert sample_svc.list_samples("transcript") == []
