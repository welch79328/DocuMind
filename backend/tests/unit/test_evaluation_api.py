"""
測試評估 API 端點(任務 5.2)

- GET  /api/v1/evaluation/{document_type}       最新/基準線指標 + 樣本量
- POST /api/v1/evaluation/{document_type}/run   重新評估(可產出前後對照)

對應需求: 8.3, 8.4
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
def samples(feedback_session):
    app.dependency_overrides[get_db] = lambda: feedback_session
    try:
        yield CorrectionSampleService(feedback_session)
    finally:
        app.dependency_overrides.pop(get_db, None)


class TestGetEvaluation:
    async def test_empty(self, samples):
        async with _client() as c:
            resp = await c.get("/api/v1/evaluation/transcript")
        assert resp.status_code == 200
        body = resp.json()
        assert body["latest"] is None
        assert body["baseline"] is None
        assert body["sample_counts"] == {"holdout": 0, "train": 0}

    async def test_reports_counts_and_metrics(self, samples):
        samples.save("transcript", "d1", {"area": "1"}, purpose="holdout")
        samples.save("transcript", "d2", {"area": "2"}, purpose="train")
        async with _client() as c:
            # 先跑一次基準線評估
            await c.post("/api/v1/evaluation/transcript/run", json={
                "predictions": {"d1": {"area": "1"}},
                "holdout_version": "baseline", "is_baseline": True,
            })
            resp = await c.get("/api/v1/evaluation/transcript")
        body = resp.json()
        assert body["sample_counts"] == {"holdout": 1, "train": 1}
        assert body["baseline"]["field_accuracy"] == 1.0
        assert body["latest"]["field_accuracy"] == 1.0

    async def test_unknown_type_rejected(self, samples):
        async with _client() as c:
            resp = await c.get("/api/v1/evaluation/invoice")
        assert resp.status_code == 400


class TestRunEvaluation:
    async def test_run_returns_metrics(self, samples):
        samples.save("transcript", "d1", {"area": "1"}, purpose="holdout")
        async with _client() as c:
            resp = await c.post("/api/v1/evaluation/transcript/run", json={
                "predictions": {"d1": {"area": "X"}},
                "holdout_version": "v1",
            })
        assert resp.status_code == 200
        body = resp.json()
        assert body["metrics"]["sample_count"] == 1
        assert body["metrics"]["field_accuracy"] == 0.0

    async def test_run_with_comparison(self, samples):
        samples.save("transcript", "d1", {"area": "1"}, purpose="holdout")
        async with _client() as c:
            # 基準線:全錯
            await c.post("/api/v1/evaluation/transcript/run", json={
                "predictions": {"d1": {"area": "9"}},
                "holdout_version": "baseline", "is_baseline": True,
            })
            # 改進後 + 對照基準線
            resp = await c.post("/api/v1/evaluation/transcript/run", json={
                "predictions": {"d1": {"area": "1"}},
                "holdout_version": "after", "compare_to": "baseline",
            })
        body = resp.json()
        assert body["metrics"]["field_accuracy"] == 1.0
        assert body["comparison"]["field_accuracy"]["delta"] == 1.0
