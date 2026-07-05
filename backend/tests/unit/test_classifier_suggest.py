"""
測試分類器建議接入路由(任務 14.1)

- DocumentClassifier.suggest:分類結果對映權威型別 + 信心度
- /api/v1/classify 端點:回傳建議型別供使用者確認
- 使用者指定永遠優先(analyze 使用使用者型別,不受分類器影響)

對應需求: 1.3
"""

import io

import httpx
import numpy as np
import pytest
from unittest.mock import AsyncMock, patch
from PIL import Image

from app.lib.ocr_enhanced.document_classifier import DocumentClassifier
from app.lib.document_types import DocumentType
from app.database import get_db
from app.main import app


def _png():
    img = Image.fromarray(np.zeros((30, 30, 3), dtype=np.uint8))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _client():
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


class TestSuggest:
    @pytest.mark.parametrize("raw,expected", [
        ("transcript", DocumentType.TRANSCRIPT),
        ("lease", DocumentType.CONTRACT),   # 舊型別正規化
    ])
    async def test_maps_to_canonical(self, raw, expected):
        clf = DocumentClassifier()
        with patch.object(clf, "classify", AsyncMock(return_value=raw)):
            dt, conf = await clf.suggest(Image.new("RGB", (10, 10)))
        assert dt == expected
        assert conf > 0

    @pytest.mark.parametrize("raw", ["id_card", "unknown"])
    async def test_no_canonical_mapping(self, raw):
        clf = DocumentClassifier()
        with patch.object(clf, "classify", AsyncMock(return_value=raw)):
            dt, conf = await clf.suggest(Image.new("RGB", (10, 10)))
        assert dt is None
        assert conf == 0.0


class TestClassifyEndpoint:
    async def test_returns_suggestion(self):
        with patch("app.api.v1.classify.DocumentClassifier") as MockClf:
            MockClf.return_value.suggest = AsyncMock(
                return_value=(DocumentType.CONTRACT, 0.7))
            async with _client() as c:
                resp = await c.post(
                    "/api/v1/classify",
                    files={"file": ("x.png", _png(), "image/png")},
                )
        assert resp.status_code == 200
        body = resp.json()
        assert body["suggested_document_type"] == "contract"
        assert body["confidence"] == 0.7

    async def test_unknown_suggestion_null(self):
        with patch("app.api.v1.classify.DocumentClassifier") as MockClf:
            MockClf.return_value.suggest = AsyncMock(return_value=(None, 0.0))
            async with _client() as c:
                resp = await c.post(
                    "/api/v1/classify",
                    files={"file": ("x.png", _png(), "image/png")},
                )
        assert resp.json()["suggested_document_type"] is None


class TestUserSpecifiedWins:
    @pytest.fixture(autouse=True)
    def _db(self, feedback_session):
        app.dependency_overrides[get_db] = lambda: feedback_session
        yield
        app.dependency_overrides.pop(get_db, None)

    async def test_analyze_uses_user_type_not_classifier(self):
        captured = {}

        async def fake_analyze(**kwargs):
            captured["document_type"] = kwargs.get("document_type")
            return {
                "file_name": "x.pdf", "file_url": None, "document_type": "contract",
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
                    data={"document_type": "contract", "enable_llm": "false"},
                )
        assert resp.status_code == 200
        # 使用者指定 contract 為準,不被分類器覆寫
        assert captured["document_type"] == "contract"
