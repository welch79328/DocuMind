"""
基準測試 API 測試(任務 2.2 / 2.3)

- POST /api/v1/evaluation/{document_type}/baseline  以指定引擎組態產出基準

兩條拒絕路徑皆以 409 回應,不得以異常數值或空結果冒充基準:
- INSUFFICIENT_SAMPLES     樣本數低於門檻(需求 1.6)
- UNSUPPORTED_ARCHITECTURE 處理器架構不支援主力引擎(需求 1.10)

對應需求: 1.3, 1.4, 1.5, 1.6, 1.10
"""

import httpx
import pytest

from app.database import get_db
from app.main import app
from app.services import baseline_runner as br
from app.services.correction_sample_service import CorrectionSampleService
from app.services.evaluation_service import EvaluationService


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


@pytest.fixture
def x86_env(monkeypatch):
    monkeypatch.setattr(br.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(br, "_is_engine_installed", lambda engine: True)


class TestBaselineEndpoint:
    async def test_returns_metrics(self, svc, x86_env):
        svc.save("transcript", "d1", {"area": "105"}, purpose="holdout")
        svc.save("transcript", "d2", {"area": "200"}, purpose="holdout")

        async with _client() as c:
            resp = await c.post("/api/v1/evaluation/transcript/baseline", json={
                "engine_profile": "paddleocr+tesseract",
                "min_samples": 1,
                "predictions": {"d1": {"area": "105"}, "d2": {"area": "XXX"}},
                "confidences": {"d1": 0.95, "d2": 0.4},
            })

        assert resp.status_code == 200
        body = resp.json()
        assert body["sample_count"] == 2
        assert body["field_accuracy"] == 0.5
        assert body["review_trigger_rate"] == 0.5
        assert body["environment"]["architecture"] == "x86_64"
        assert body["environment"]["primary_engine_available"] is True
        assert body["per_field_accuracy"]["area"] == 0.5

    async def test_marks_baseline_when_requested(self, svc, x86_env, feedback_session):
        svc.save("transcript", "d1", {"area": "1"}, purpose="holdout")

        async with _client() as c:
            resp = await c.post("/api/v1/evaluation/transcript/baseline", json={
                "engine_profile": "paddleocr",
                "is_baseline": True,
                "min_samples": 1,
                "predictions": {"d1": {"area": "1"}},
                "confidences": {"d1": 0.95},
            })

        assert resp.status_code == 200
        summary = EvaluationService(feedback_session).summary("transcript")
        assert summary["baseline"] is not None
        assert summary["baseline"]["field_accuracy"] == 1.0

    async def test_insufficient_samples_returns_409(self, svc, x86_env):
        svc.save("transcript", "d1", {"area": "1"}, purpose="holdout")

        async with _client() as c:
            resp = await c.post("/api/v1/evaluation/transcript/baseline", json={
                "engine_profile": "paddleocr",
                "is_baseline": True,
                "min_samples": 30,
                "predictions": {"d1": {"area": "1"}},
            })

        assert resp.status_code == 409
        body = resp.json()
        assert body["error_code"] == "INSUFFICIENT_SAMPLES"
        assert "樣本不足" in body["detail"]

    async def test_unsupported_architecture_returns_409(self, svc, monkeypatch):
        monkeypatch.setattr(br.platform, "machine", lambda: "arm64")
        monkeypatch.setattr(br, "_is_engine_installed", lambda engine: True)
        svc.save("transcript", "d1", {"area": "1"}, purpose="holdout")

        async with _client() as c:
            resp = await c.post("/api/v1/evaluation/transcript/baseline", json={
                "engine_profile": "paddleocr+tesseract",
                "min_samples": 1,
                "predictions": {"d1": {"area": "1"}},
            })

        assert resp.status_code == 409
        body = resp.json()
        assert body["error_code"] == "UNSUPPORTED_ARCHITECTURE"
        assert "x86_64" in body["detail"]

    async def test_unsupported_architecture_leaves_no_records(
        self, svc, monkeypatch, feedback_session
    ):
        """拒絕路徑不得留下任何可被誤讀為基準的紀錄"""
        monkeypatch.setattr(br.platform, "machine", lambda: "arm64")
        monkeypatch.setattr(br, "_is_engine_installed", lambda engine: True)
        svc.save("transcript", "d1", {"area": "1"}, purpose="holdout")

        async with _client() as c:
            await c.post("/api/v1/evaluation/transcript/baseline", json={
                "engine_profile": "paddleocr",
                "min_samples": 1,
                "predictions": {"d1": {"area": "1"}},
            })

        assert EvaluationService(feedback_session).list_records("transcript") == []

    async def test_unsupported_document_type_returns_400(self, svc, x86_env):
        async with _client() as c:
            resp = await c.post("/api/v1/evaluation/invoice/baseline", json={
                "engine_profile": "paddleocr", "predictions": {},
            })

        assert resp.status_code == 400
        assert resp.json()["error_code"] == "UNSUPPORTED_DOCUMENT_TYPE"

    async def test_missing_predictions_returns_422(self, svc, x86_env):
        svc.save("transcript", "d1", {"area": "1"}, purpose="holdout")

        async with _client() as c:
            resp = await c.post("/api/v1/evaluation/transcript/baseline", json={
                "engine_profile": "paddleocr", "min_samples": 1,
            })

        assert resp.status_code == 422
        assert resp.json()["error_code"] == "MISSING_PREDICTIONS"

    async def test_below_threshold_without_baseline_flag_warns(self, svc, x86_env):
        svc.save("transcript", "d1", {"area": "1"}, purpose="holdout")

        async with _client() as c:
            resp = await c.post("/api/v1/evaluation/transcript/baseline", json={
                "engine_profile": "paddleocr",
                "is_baseline": False,
                "min_samples": 30,
                "predictions": {"d1": {"area": "1"}},
                "confidences": {"d1": 0.95},
            })

        assert resp.status_code == 200
        body = resp.json()
        assert body["baseline_eligible"] is False
        assert "樣本不足" in body["warnings"][0]
