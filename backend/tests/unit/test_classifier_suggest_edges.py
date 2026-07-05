"""
分類器建議邊界與「使用者指定優先」契約(任務 14.2)

對應需求: 1.3
"""

import httpx
import pytest
from unittest.mock import AsyncMock, patch
from PIL import Image

from app.lib.ocr_enhanced.document_classifier import DocumentClassifier
from app.lib.document_types import DocumentType
from app.database import get_db
from app.main import app


def _client():
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


class TestSuggestEdges:
    async def test_confidence_value_for_mapped(self):
        clf = DocumentClassifier()
        with patch.object(clf, "classify", AsyncMock(return_value="transcript")):
            _, conf = await clf.suggest(Image.new("RGB", (5, 5)))
        assert conf == 0.7

    async def test_lease_contract_alias_maps_to_contract(self):
        clf = DocumentClassifier()
        with patch.object(clf, "classify", AsyncMock(return_value="lease_contract")):
            dt, _ = await clf.suggest(Image.new("RGB", (5, 5)))
        assert dt == DocumentType.CONTRACT


class TestEndpointDegrade:
    async def test_classifier_failure_returns_null(self):
        with patch("app.api.v1.classify.DocumentClassifier") as MockClf:
            MockClf.return_value.suggest = AsyncMock(side_effect=RuntimeError("OCR down"))
            async with _client() as c:
                resp = await c.post(
                    "/api/v1/classify",
                    files={"file": ("x.png", b"\x89PNG\r\n", "image/png")},
                )
        assert resp.status_code == 200
        assert resp.json()["suggested_document_type"] is None


class TestUserSpecifiedPriority:
    @pytest.fixture(autouse=True)
    def _db(self, feedback_session):
        app.dependency_overrides[get_db] = lambda: feedback_session
        yield
        app.dependency_overrides.pop(get_db, None)

    async def test_user_type_used_even_if_differs_from_suggestion(self):
        # 使用者指定 transcript,即使分類器可能建議別的,analyze 仍用使用者指定
        captured = {}

        async def fake_analyze(**kwargs):
            captured["document_type"] = kwargs.get("document_type")
            return {
                "file_name": "x.pdf", "file_url": None, "document_type": "transcript",
                "total_pages": 1,
                "pages": [{"page_number": 1, "ocr_raw": {"text": "x", "confidence": 0.95},
                           "rule_postprocessed": {"text": "x", "stats": {}},
                           "llm_postprocessed": None, "structured_data": None}],
                "answer": None,
                "stats": {"total_time_ms": 1, "total_pages": 1,
                          "llm_pages_used": 0, "estimated_cost": 0.0},
            }

        with patch("app.api.v1.analyze.AnalyzeService") as MockService:
            MockService.return_value.analyze = AsyncMock(side_effect=fake_analyze)
            async with _client() as c:
                resp = await c.post(
                    "/api/v1/analyze",
                    files={"file": ("x.pdf", b"%PDF-1.4", "application/pdf")},
                    data={"document_type": "transcript", "enable_llm": "false"},
                )
        assert resp.status_code == 200
        assert captured["document_type"] == "transcript"
