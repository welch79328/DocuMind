"""
測試校正樣本查詢與種子範例 API(任務 4.2)

- GET  /api/v1/samples/{document_type}       檢視樣本與累積量(可 purpose / golden 過濾)
- POST /api/v1/samples/{document_type}/seed  種子範例冷啟動
- POST /api/v1/samples/{sample_id}/golden    標記黃金範例

對應需求: 7.4, 8.4
"""

import httpx
import pytest

from app.database import get_db
from app.main import app
from app.services.correction_sample_service import CorrectionSampleService


def _client():
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


@pytest.fixture
def svc(feedback_session):
    app.dependency_overrides[get_db] = lambda: feedback_session
    try:
        yield CorrectionSampleService(feedback_session)
    finally:
        app.dependency_overrides.pop(get_db, None)


class TestViewSamples:
    async def test_empty_returns_zero_count(self, svc):
        async with _client() as c:
            resp = await c.get("/api/v1/samples/transcript")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 0
        assert body["samples"] == []

    async def test_view_after_direct_save(self, svc):
        svc.save("transcript", "doc-a", {"area": "128.45"})
        async with _client() as c:
            resp = await c.get("/api/v1/samples/transcript")
        body = resp.json()
        assert body["count"] == 1
        assert body["samples"][0]["corrected_fields"] == {"area": "128.45"}

    async def test_unknown_type_rejected(self, svc):
        async with _client() as c:
            resp = await c.get("/api/v1/samples/invoice")
        assert resp.status_code == 400
        assert resp.json()["error_code"] == "UNSUPPORTED_DOCUMENT_TYPE"

    async def test_purpose_filter(self, svc):
        svc.save("bill", "x", {"amount": "1"}, purpose="train")
        svc.save("bill", "y", {"amount": "2"}, purpose="holdout")
        async with _client() as c:
            resp = await c.get("/api/v1/samples/bill", params={"purpose": "holdout"})
        assert resp.json()["count"] == 1


class TestSeed:
    async def test_seed_creates_samples(self, svc):
        payload = {"examples": [
            {"input_ref": "std-1", "corrected_fields": {"area": "100"}},
            {"input_ref": "std-2", "corrected_fields": {"area": "200"}, "purpose": "holdout"},
        ]}
        async with _client() as c:
            resp = await c.post("/api/v1/samples/transcript/seed", json=payload)
        assert resp.status_code == 200
        assert resp.json()["created"] == 2
        # 即時可供查詢
        assert svc.count("transcript", purpose="train") == 1
        assert svc.count("transcript", purpose="holdout") == 1

    async def test_seed_unknown_type_rejected(self, svc):
        async with _client() as c:
            resp = await c.post(
                "/api/v1/samples/invoice/seed",
                json={"examples": [{"input_ref": "x", "corrected_fields": {}}]},
            )
        assert resp.status_code == 400

    async def test_seed_legacy_alias_normalized(self, svc):
        # lease → contract
        async with _client() as c:
            resp = await c.post(
                "/api/v1/samples/lease/seed",
                json={"examples": [{"input_ref": "x", "corrected_fields": {"a": 1}}]},
            )
        assert resp.status_code == 200
        assert svc.count("contract") == 1


class TestMarkGolden:
    async def test_mark_golden_endpoint(self, svc):
        sid = svc.save("transcript", "doc", {"a": 1})
        async with _client() as c:
            resp = await c.post(f"/api/v1/samples/{sid}/golden", json={"is_golden": True})
        assert resp.status_code == 200
        assert resp.json()["is_golden"] is True
        assert svc.list_samples("transcript", golden_only=True)[0]["id"] == sid

    async def test_mark_golden_nonexistent_404(self, svc):
        async with _client() as c:
            resp = await c.post(
                "/api/v1/samples/00000000-0000-0000-0000-000000000000/golden",
                json={"is_golden": True},
            )
        assert resp.status_code == 404
