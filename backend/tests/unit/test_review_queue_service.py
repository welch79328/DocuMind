"""
測試人工複核佇列服務 ReviewQueueService(任務 3.1)

以 in-memory SQLite 進行真實資料庫測試,驗證認領式狀態機:
- enqueue → pending
- claim → in_review(認領鎖定);併發第二次認領失敗
- submit_correction → completed,記錄前後差異;僅認領者可提交
- release → 回 pending

對應需求: 6.3, 6.4, 6.5, 6.7
"""

import pytest

from app.lib.document_types import DocumentType
from app.services.review_queue_service import ReviewQueueService


def _enqueue(svc, confidence=0.62, result=None):
    return svc.enqueue(
        document_id="11111111-1111-1111-1111-111111111111",
        document_type=DocumentType.TRANSCRIPT,
        overall_confidence=confidence,
        result=result or {"area": "12B.45", "owner": "陳○明"},
    )


@pytest.fixture
def svc(feedback_session):
    return ReviewQueueService(feedback_session)


class TestEnqueue:
    def test_enqueue_creates_pending_item(self, svc):
        item_id = _enqueue(svc)
        assert item_id is not None
        queue = svc.list_queue()
        assert len(queue) == 1
        assert queue[0]["status"] == "pending"
        assert queue[0]["document_type"] == "transcript"

    def test_enqueue_stores_original_result(self, svc):
        _enqueue(svc, result={"area": "12B.45"})
        item = svc.list_queue()[0]
        assert item["original_result"] == {"area": "12B.45"}


class TestClaimLocking:
    def test_claim_pending_succeeds_and_locks(self, svc):
        item_id = _enqueue(svc)
        assert svc.claim(item_id, reviewer="alice") is True
        item = svc.list_queue()[0]
        assert item["status"] == "in_review"
        assert item["reviewer"] == "alice"

    def test_second_claim_fails_when_already_claimed(self, svc):
        item_id = _enqueue(svc)
        assert svc.claim(item_id, reviewer="alice") is True
        # 需求 6.7:已被認領者,其他人再認領應失敗
        assert svc.claim(item_id, reviewer="bob") is False
        item = svc.list_queue()[0]
        assert item["reviewer"] == "alice"

    def test_claim_nonexistent_returns_false(self, svc):
        assert svc.claim("00000000-0000-0000-0000-000000000000", "alice") is False


class TestSubmitCorrection:
    def test_owner_submits_records_diff_and_completes(self, svc):
        item_id = _enqueue(svc, result={"area": "12B.45", "owner": "陳○明"})
        svc.claim(item_id, reviewer="alice")
        diff = svc.submit_correction(
            item_id, reviewer="alice",
            corrected_fields={"area": "128.45", "owner": "陳○明"},
        )
        # 記錄前後差異:僅 area 變動
        assert "area" in diff
        assert diff["area"] == {"before": "12B.45", "after": "128.45"}
        assert "owner" not in diff
        item = svc.list_queue()[0]
        assert item["status"] == "completed"
        assert item["corrected_result"] == {"area": "128.45", "owner": "陳○明"}
        # 校正前結果仍保留
        assert item["original_result"] == {"area": "12B.45", "owner": "陳○明"}

    def test_non_owner_cannot_submit(self, svc):
        item_id = _enqueue(svc)
        svc.claim(item_id, reviewer="alice")
        # 需求 6.4:僅擁有者可編輯
        with pytest.raises(PermissionError):
            svc.submit_correction(item_id, reviewer="bob", corrected_fields={"area": "x"})

    def test_cannot_submit_unclaimed(self, svc):
        item_id = _enqueue(svc)  # 尚未認領(pending)
        with pytest.raises(PermissionError):
            svc.submit_correction(item_id, reviewer="alice", corrected_fields={"area": "x"})

    def test_submit_nonexistent_raises(self, svc):
        with pytest.raises(ValueError):
            svc.submit_correction("00000000-0000-0000-0000-000000000000", "alice", {})


class TestRelease:
    def test_owner_release_returns_to_pending(self, svc):
        item_id = _enqueue(svc)
        svc.claim(item_id, reviewer="alice")
        svc.release(item_id, reviewer="alice")
        item = svc.list_queue()[0]
        assert item["status"] == "pending"
        assert item["reviewer"] is None
        # 釋出後可被他人重新認領
        assert svc.claim(item_id, reviewer="bob") is True

    def test_non_owner_cannot_release(self, svc):
        item_id = _enqueue(svc)
        svc.claim(item_id, reviewer="alice")
        with pytest.raises(PermissionError):
            svc.release(item_id, reviewer="bob")


class TestListQueue:
    def test_filter_by_status(self, svc):
        id1 = _enqueue(svc)
        _enqueue(svc)
        svc.claim(id1, reviewer="alice")
        assert len(svc.list_queue(status="pending")) == 1
        assert len(svc.list_queue(status="in_review")) == 1
        assert len(svc.list_queue()) == 2
