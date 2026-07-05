"""
測試複核佇列 API 端點(任務 3.2)

以真實 app + in-memory SQLite(覆寫 get_db)驗證四端點與錯誤碼。
使用 httpx.ASGITransport(相容 httpx 0.28,取代不相容的 TestClient)進行 ASGI 測試。

對應需求: 6.2, 6.3, 6.4, 6.5, 6.7
"""

import httpx
import pytest

from app.database import get_db
from app.main import app
from app.services.review_queue_service import ReviewQueueService
from app.lib.document_types import DocumentType


def _client():
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


@pytest.fixture
def svc(feedback_session):
    app.dependency_overrides[get_db] = lambda: feedback_session
    try:
        yield ReviewQueueService(feedback_session)
    finally:
        app.dependency_overrides.pop(get_db, None)


def _seed(svc, confidence=0.62):
    return svc.enqueue(
        document_id="11111111-1111-1111-1111-111111111111",
        document_type=DocumentType.TRANSCRIPT,
        overall_confidence=confidence,
        result={"area": "12B.45"},
    )


class TestQueueList:
    async def test_list_returns_items(self, svc):
        _seed(svc)
        async with _client() as c:
            resp = await c.get("/api/v1/review/queue")
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 1

    async def test_list_filter_by_status(self, svc):
        item_id = _seed(svc)
        _seed(svc)
        svc.claim(item_id, "alice")
        async with _client() as c:
            resp = await c.get("/api/v1/review/queue", params={"status": "pending"})
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 1


class TestGetSingleItem:
    async def test_get_existing_item(self, svc):
        item_id = _seed(svc)
        async with _client() as c:
            resp = await c.get(f"/api/v1/review/{item_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == item_id
        assert body["document_type"] == "transcript"
        assert body["original_result"] == {"area": "12B.45"}

    async def test_get_nonexistent_returns_404(self, svc):
        async with _client() as c:
            resp = await c.get("/api/v1/review/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404
        assert resp.json()["error_code"] == "NOT_FOUND"

    async def test_queue_route_not_shadowed_by_item_route(self, svc):
        # /queue 為字面路徑,不應被 /{item_id} 誤匹配
        _seed(svc)
        async with _client() as c:
            resp = await c.get("/api/v1/review/queue")
        assert resp.status_code == 200
        assert "items" in resp.json()


class TestClaim:
    async def test_claim_success(self, svc):
        item_id = _seed(svc)
        async with _client() as c:
            resp = await c.post(f"/api/v1/review/{item_id}/claim", json={"reviewer": "alice"})
        assert resp.status_code == 200
        assert resp.json()["claimed"] is True

    async def test_claim_conflict_returns_409(self, svc):
        item_id = _seed(svc)
        svc.claim(item_id, "alice")
        async with _client() as c:
            resp = await c.post(f"/api/v1/review/{item_id}/claim", json={"reviewer": "bob"})
        assert resp.status_code == 409
        assert resp.json()["error_code"] == "ALREADY_CLAIMED"
        assert "已被" in resp.json()["detail"]


class TestSubmit:
    async def test_submit_success_returns_diff(self, svc):
        item_id = _seed(svc)
        svc.claim(item_id, "alice")
        async with _client() as c:
            resp = await c.post(
                f"/api/v1/review/{item_id}/submit",
                json={"reviewer": "alice", "corrected_fields": {"area": "128.45"}},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "completed"
        assert body["diff"]["area"] == {"before": "12B.45", "after": "128.45"}

    async def test_submit_non_owner_returns_403(self, svc):
        item_id = _seed(svc)
        svc.claim(item_id, "alice")
        async with _client() as c:
            resp = await c.post(
                f"/api/v1/review/{item_id}/submit",
                json={"reviewer": "bob", "corrected_fields": {"area": "x"}},
            )
        assert resp.status_code == 403
        assert resp.json()["error_code"] == "FORBIDDEN"

    async def test_submit_nonexistent_returns_404(self, svc):
        async with _client() as c:
            resp = await c.post(
                "/api/v1/review/00000000-0000-0000-0000-000000000000/submit",
                json={"reviewer": "alice", "corrected_fields": {}},
            )
        assert resp.status_code == 404
        assert resp.json()["error_code"] == "NOT_FOUND"

    async def test_submit_missing_field_returns_422(self, svc):
        item_id = _seed(svc)
        svc.claim(item_id, "alice")
        async with _client() as c:
            resp = await c.post(f"/api/v1/review/{item_id}/submit", json={"reviewer": "alice"})
        assert resp.status_code == 422


class TestRelease:
    async def test_release_returns_to_pending(self, svc):
        item_id = _seed(svc)
        svc.claim(item_id, "alice")
        async with _client() as c:
            resp = await c.post(f"/api/v1/review/{item_id}/release", json={"reviewer": "alice"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "pending"

    async def test_release_non_owner_returns_403(self, svc):
        item_id = _seed(svc)
        svc.claim(item_id, "alice")
        async with _client() as c:
            resp = await c.post(f"/api/v1/review/{item_id}/release", json={"reviewer": "bob"})
        assert resp.status_code == 403
