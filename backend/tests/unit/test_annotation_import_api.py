"""
標註匯入 API 測試(任務 1.2)

- POST /api/v1/samples/{document_type}/import  將標註檔匯入為保留評估集

對應需求: 1.7, 1.8
"""

import json

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


def _annotation_file(tmp_path, payload) -> str:
    path = tmp_path / "gt.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return str(path)


class TestImportEndpoint:
    async def test_imports_and_reports_counts(self, svc, tmp_path):
        path = _annotation_file(tmp_path, {
            "ok.jpg": {"key_fields": {"land_number": "0231-0000"}},
            "todo.pdf": {"key_fields": {"land_number": None}},
        })
        async with _client() as c:
            resp = await c.post(
                "/api/v1/samples/transcript/import",
                json={"file_path": path, "purpose": "holdout"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["imported"] == 1
        assert body["skipped"] == 1
        assert body["skipped_refs"] == ["todo.pdf"]
        assert body["errors"] == []
        assert svc.count("transcript", purpose="holdout") == 1

    async def test_defaults_to_holdout(self, svc, tmp_path):
        path = _annotation_file(tmp_path, {"ok.jpg": {"key_fields": {"area": 1.0}}})
        async with _client() as c:
            resp = await c.post(
                "/api/v1/samples/transcript/import", json={"file_path": path}
            )

        assert resp.status_code == 200
        assert svc.count("transcript", purpose="holdout") == 1
        assert svc.count("transcript", purpose="train") == 0

    async def test_unsupported_document_type_returns_400(self, svc, tmp_path):
        path = _annotation_file(tmp_path, {"ok.jpg": {"key_fields": {"area": 1.0}}})
        async with _client() as c:
            resp = await c.post(
                "/api/v1/samples/invoice/import", json={"file_path": path}
            )

        assert resp.status_code == 400
        assert resp.json()["error_code"] == "UNSUPPORTED_DOCUMENT_TYPE"

    async def test_missing_file_returns_404(self, svc, tmp_path):
        async with _client() as c:
            resp = await c.post(
                "/api/v1/samples/transcript/import",
                json={"file_path": str(tmp_path / "nope.json")},
            )

        assert resp.status_code == 404
        assert resp.json()["error_code"] == "ANNOTATION_FILE_NOT_FOUND"

    async def test_malformed_json_returns_422(self, svc, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("{ not json ", encoding="utf-8")
        async with _client() as c:
            resp = await c.post(
                "/api/v1/samples/transcript/import", json={"file_path": str(path)}
            )

        assert resp.status_code == 422
        assert resp.json()["error_code"] == "INVALID_ANNOTATION_FORMAT"

    async def test_imported_holdout_not_used_by_fewshot(self, svc, tmp_path):
        svc.save("transcript", "train-1", {"area": 9.0}, purpose="train")
        path = _annotation_file(tmp_path, {"hold.jpg": {"key_fields": {"area": 1.0}}})
        async with _client() as c:
            await c.post(
                "/api/v1/samples/transcript/import", json={"file_path": path}
            )

        refs = {s["input_ref"] for s in svc.list_for_fewshot("transcript")}
        assert refs == {"train-1"}
