"""
測試 /api/v1/analyze 的信心度攔截整合(任務 3.3)

mock AnalyzeService 回傳受控信心度,驗證:
- 低信心 → needs_review=True、review_item_id 有值、自動入複核佇列
- 高信心 → needs_review=False、不入列、行為與現行一致

對應需求: 6.2
"""

import httpx
import pytest
from unittest.mock import AsyncMock, patch

from app.database import get_db
from app.main import app
from app.services.review_queue_service import ReviewQueueService


def _client():
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


@pytest.fixture
def gating_ctx(feedback_session):
    app.dependency_overrides[get_db] = lambda: feedback_session
    try:
        yield ReviewQueueService(feedback_session)
    finally:
        app.dependency_overrides.pop(get_db, None)


def _mock_result(confidence, structured=None):
    return {
        "file_name": "t.pdf", "file_url": None, "document_type": "transcript",
        "total_pages": 1,
        "pages": [{
            "page_number": 1,
            "ocr_raw": {"text": "土地登記", "confidence": confidence},
            "rule_postprocessed": {"text": "土地登記", "stats": {}},
            "llm_postprocessed": None,
            "structured_data": structured,
        }],
        "answer": None,
        "stats": {"total_time_ms": 10, "total_pages": 1,
                  "llm_pages_used": 0, "estimated_cost": 0.0},
    }


async def _post_analyze():
    async with _client() as c:
        return await c.post(
            "/api/v1/analyze",
            files={"file": ("t.pdf", b"%PDF-1.4 fake", "application/pdf")},
            data={"document_type": "transcript", "enable_llm": "false"},
        )


class TestLowConfidenceGating:
    async def test_low_ocr_confidence_needs_review_and_enqueued(self, gating_ctx):
        svc = gating_ctx
        with patch("app.api.v1.analyze.AnalyzeService") as MockService:
            MockService.return_value.analyze = AsyncMock(return_value=_mock_result(0.6))
            resp = await _post_analyze()
        assert resp.status_code == 200
        body = resp.json()
        assert body["needs_review"] is True
        assert body["review_item_id"] is not None
        # 已自動入複核佇列
        queue = svc.list_queue(status="pending")
        assert len(queue) == 1
        assert queue[0]["document_type"] == "transcript"

    async def test_low_field_confidence_triggers_review(self, gating_ctx):
        with patch("app.api.v1.analyze.AnalyzeService") as MockService:
            MockService.return_value.analyze = AsyncMock(
                return_value=_mock_result(
                    0.95, structured={"field_confidences": {"area": 0.6}}))
            resp = await _post_analyze()
        body = resp.json()
        assert body["needs_review"] is True
        assert body["field_confidences"].get("area") == 0.6


class TestHighConfidencePassthrough:
    async def test_high_confidence_no_review_not_enqueued(self, gating_ctx):
        svc = gating_ctx
        with patch("app.api.v1.analyze.AnalyzeService") as MockService:
            MockService.return_value.analyze = AsyncMock(return_value=_mock_result(0.95))
            resp = await _post_analyze()
        assert resp.status_code == 200
        body = resp.json()
        assert body["needs_review"] is False
        assert body["review_item_id"] is None
        # 未入列
        assert svc.list_queue() == []

    async def test_response_preserves_existing_fields(self, gating_ctx):
        with patch("app.api.v1.analyze.AnalyzeService") as MockService:
            MockService.return_value.analyze = AsyncMock(return_value=_mock_result(0.95))
            resp = await _post_analyze()
        body = resp.json()
        # 現行欄位不受影響(向後相容)
        assert body["file_name"] == "t.pdf"
        assert body["document_type"] == "transcript"
        assert body["total_pages"] == 1
        assert len(body["pages"]) == 1
