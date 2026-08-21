"""
使用者當場確認回灌測試(ocr-vlm-consensus 任務 9.2)

驗收標準:
- 使用者修正可寫回為訓練用途樣本
- 回灌後可被 few-shot 選取
- 既有複核佇列流程不受影響,保留為稍後處理的備援路徑

對應需求: 6.3, 6.4
"""

import httpx
import pytest

from app.database import get_db
from app.main import app
from app.services.correction_sample_service import CorrectionSampleService
from app.services.few_shot_selector import FewShotSelector, compute_layout_signature
from app.services.field_confirmation_service import FieldConfirmationService
from app.services.review_queue_service import ReviewQueueService

PAGE_TEXT = (
    "土地登記第三類謄本(所有權個人全部)\n"
    "中正區中正段三小段 0221-0000 地號\n"
    "所有權人:黃水木\n"
    "面積:153.00平方公尺\n"
)

DECISIONS = [
    {"field": "land_number", "action": "corrected",
     "before": "O221-OOOO", "after": "0221-0000"},
    {"field": "owner", "action": "confirmed",
     "before": "黃水木", "after": "黃水木"},
]


def _client():
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


@pytest.fixture
def samples(feedback_session):
    return CorrectionSampleService(feedback_session)


@pytest.fixture
def api(feedback_session):
    app.dependency_overrides[get_db] = lambda: feedback_session
    try:
        yield CorrectionSampleService(feedback_session)
    finally:
        app.dependency_overrides.pop(get_db, None)


class TestWriteBackAsTrainingSample:
    def test_decisions_become_a_train_sample(self, samples):
        report = FieldConfirmationService(samples).record(
            "transcript", PAGE_TEXT, DECISIONS
        )

        assert report["created"] is True
        assert report["fields_written"] == 2
        assert samples.count("transcript", purpose="train") == 1

    def test_written_values_are_the_user_final_values(self, samples):
        FieldConfirmationService(samples).record("transcript", PAGE_TEXT, DECISIONS)
        stored = samples.list_samples("transcript", purpose="train")[0]

        assert stored["corrected_fields"] == {
            "land_number": "0221-0000",   # 修正後的值,不是 OCR 原值
            "owner": "黃水木",
        }

    def test_never_written_to_holdout(self, samples):
        """當場確認絕不可寫進保留評估集,否則訓練資料污染基準"""
        FieldConfirmationService(samples).record("transcript", PAGE_TEXT, DECISIONS)
        assert samples.count("transcript", purpose="holdout") == 0

    def test_layout_signature_uses_shared_computation(self, samples):
        """版型指紋沿用既有計算,當場確認的樣本才吃得到同版型優先選取"""
        FieldConfirmationService(samples).record("transcript", PAGE_TEXT, DECISIONS)
        stored = samples.list_samples("transcript", purpose="train")[0]

        expected = compute_layout_signature({"ocr_raw": {"text": PAGE_TEXT}})
        assert stored["layout_signature"] == expected
        assert stored["layout_signature"] != ""

    def test_input_ref_comes_from_page_text(self, samples):
        FieldConfirmationService(samples).record("transcript", PAGE_TEXT, DECISIONS)
        stored = samples.list_samples("transcript", purpose="train")[0]
        assert "0221-0000" in stored["input_ref"]

    def test_long_page_text_is_truncated(self, samples):
        FieldConfirmationService(samples).record("transcript", "字" * 5000, DECISIONS)
        stored = samples.list_samples("transcript", purpose="train")[0]
        assert len(stored["input_ref"]) == 2000


class TestNoSampleWithoutRealDecisions:
    def test_empty_decisions_write_nothing(self, samples):
        report = FieldConfirmationService(samples).record("transcript", PAGE_TEXT, [])

        assert report["created"] is False
        assert report["sample_id"] is None
        assert samples.count("transcript", purpose="train") == 0

    def test_unknown_action_is_skipped_not_written(self, samples):
        """未知處置不得被當成使用者確認過——那等於偽造人工驗證"""
        report = FieldConfirmationService(samples).record(
            "transcript", PAGE_TEXT,
            [{"field": "land_number", "action": "guessed", "after": "0221-0000"}],
        )

        assert report["created"] is False
        assert report["skipped"] == ["land_number"]
        assert samples.count("transcript", purpose="train") == 0

    def test_blank_field_name_is_skipped(self, samples):
        report = FieldConfirmationService(samples).record(
            "transcript", PAGE_TEXT,
            [{"field": "  ", "action": "confirmed", "after": "x"}],
        )
        assert report["created"] is False

    def test_corrected_without_final_value_is_skipped(self, samples):
        """缺最終值的決定不成立——寫進去會讓 null 混入 few-shot 範例"""
        report = FieldConfirmationService(samples).record(
            "transcript", PAGE_TEXT,
            [{"field": "owner", "action": "corrected", "before": "黃水木"}],
        )

        assert report["created"] is False
        assert report["skipped"] == ["owner"]
        assert samples.count("transcript", purpose="train") == 0

    def test_explicit_none_after_is_skipped(self, samples):
        report = FieldConfirmationService(samples).record(
            "transcript", PAGE_TEXT,
            [{"field": "owner", "action": "confirmed", "after": None}],
        )
        assert report["created"] is False
        assert report["skipped"] == ["owner"]

    def test_empty_string_is_a_valid_answer(self, samples):
        """使用者清空欄位代表「此欄無值」,是有效答案,不可與缺值混為一談"""
        report = FieldConfirmationService(samples).record(
            "transcript", PAGE_TEXT,
            [{"field": "owner", "action": "corrected", "before": "雜訊", "after": ""}],
        )

        assert report["created"] is True
        stored = samples.list_samples("transcript", purpose="train")[0]
        assert stored["corrected_fields"] == {"owner": ""}

    def test_valid_and_invalid_mixed_writes_only_valid(self, samples):
        report = FieldConfirmationService(samples).record(
            "transcript", PAGE_TEXT,
            [
                {"field": "owner", "action": "confirmed", "after": "黃水木"},
                {"field": "area", "action": "bogus", "after": "153.00"},
            ],
        )

        assert report["created"] is True
        assert report["fields_written"] == 1
        assert report["skipped"] == ["area"]
        stored = samples.list_samples("transcript", purpose="train")[0]
        assert stored["corrected_fields"] == {"owner": "黃水木"}


class TestFewShotPickup:
    def test_confirmed_sample_is_selectable_for_fewshot(self, samples):
        """驗收標準:回灌後可被 few-shot 選取"""
        FieldConfirmationService(samples).record("transcript", PAGE_TEXT, DECISIONS)

        picked = samples.list_for_fewshot("transcript")
        assert len(picked) == 1
        assert picked[0]["corrected_fields"]["land_number"] == "0221-0000"

    def test_selector_injects_the_confirmed_sample(self, samples):
        FieldConfirmationService(samples).record("transcript", PAGE_TEXT, DECISIONS)

        selector = FewShotSelector(samples)
        examples = selector.select(
            document_type="transcript",
            layout_signature=compute_layout_signature({"ocr_raw": {"text": PAGE_TEXT}}),
        )
        assert any(
            e["corrected_fields"].get("land_number") == "0221-0000" for e in examples
        )

    def test_holdout_samples_are_not_reachable_via_fewshot(self, samples):
        """既有防洩漏不變:當場確認寫入 train,不影響 holdout 隔離"""
        samples.save(
            document_type="transcript",
            input_ref="評估用",
            corrected_fields={"land_number": "9999-9999"},
            purpose="holdout",
        )
        FieldConfirmationService(samples).record("transcript", PAGE_TEXT, DECISIONS)

        picked = samples.list_for_fewshot("transcript")
        assert all(p["purpose"] == "train" for p in picked)
        assert len(picked) == 1


class TestReviewQueueUnaffected:
    """驗收標準:既有複核佇列流程不受影響,保留為稍後處理的備援路徑"""

    def _queued_item(self, session):
        service = ReviewQueueService(session)
        return service.enqueue(
            document_id=None,
            document_type="transcript",
            overall_confidence=0.4,
            result={"pages": [{"ocr_raw": {"text": PAGE_TEXT}}]},
        )

    def test_confirmation_does_not_touch_the_queue(self, feedback_session, samples):
        item_id = self._queued_item(feedback_session)
        FieldConfirmationService(samples).record("transcript", PAGE_TEXT, DECISIONS)

        queue = ReviewQueueService(feedback_session).list_queue()
        assert len(queue) == 1
        assert queue[0]["id"] == item_id
        assert queue[0]["status"] == "pending"

    def test_claim_submit_release_still_work_after_confirmation(
        self, feedback_session, samples
    ):
        item_id = self._queued_item(feedback_session)
        FieldConfirmationService(samples).record("transcript", PAGE_TEXT, DECISIONS)

        service = ReviewQueueService(feedback_session, sample_service=samples)
        assert service.claim(item_id, "reviewer-a") is True

        service.release(item_id, "reviewer-a")
        assert service.get_item(item_id)["status"] == "pending"

        assert service.claim(item_id, "reviewer-b") is True
        diff = service.submit_correction(
            item_id, "reviewer-b", {"land_number": "0221-0000"}
        )
        assert service.get_item(item_id)["status"] == "completed"
        assert "land_number" in diff

    def test_both_paths_produce_independent_samples(self, feedback_session, samples):
        """兩條路徑並存:各自沉澱樣本,互不覆蓋"""
        item_id = self._queued_item(feedback_session)
        FieldConfirmationService(samples).record("transcript", PAGE_TEXT, DECISIONS)

        service = ReviewQueueService(feedback_session, sample_service=samples)
        service.claim(item_id, "reviewer-a")
        service.submit_correction(item_id, "reviewer-a", {"owner": "黃水木"})

        stored = samples.list_samples("transcript", purpose="train")
        assert len(stored) == 2
        sources = [s["source_review_id"] for s in stored]
        assert None in sources              # 當場確認:無來源複核項目
        assert str(item_id) in [str(s) for s in sources if s]


class TestConfirmEndpoint:
    async def test_endpoint_writes_sample(self, api):
        async with _client() as c:
            resp = await c.post(
                "/api/v1/samples/transcript/confirm",
                json={"page_text": PAGE_TEXT, "decisions": DECISIONS},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["created"] is True
        assert body["fields_written"] == 2
        assert body["document_type"] == "transcript"
        assert api.count("transcript", purpose="train") == 1

    async def test_endpoint_rejects_unknown_document_type(self, api):
        async with _client() as c:
            resp = await c.post(
                "/api/v1/samples/invoice/confirm",
                json={"page_text": PAGE_TEXT, "decisions": DECISIONS},
            )

        assert resp.status_code == 400
        assert resp.json()["error_code"] == "UNSUPPORTED_DOCUMENT_TYPE"
        assert api.count("transcript", purpose="train") == 0

    async def test_endpoint_with_no_decisions_writes_nothing(self, api):
        async with _client() as c:
            resp = await c.post(
                "/api/v1/samples/transcript/confirm",
                json={"page_text": PAGE_TEXT, "decisions": []},
            )

        assert resp.status_code == 200
        assert resp.json()["created"] is False
        assert api.count("transcript", purpose="train") == 0
