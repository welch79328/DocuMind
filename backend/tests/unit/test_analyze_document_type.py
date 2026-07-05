"""
測試統一分析 API 的文件類型收斂與驗證(任務 1.1)

以 httpx.ASGITransport(相容 httpx 0.28)進行 ASGI 測試,mock AnalyzeService 避免真實處理。

驗收標準:
- API 白名單由工廠支援型別動態產生,不再寫死
- 舊型別(lease)正規化為權威型別(contract)後傳入服務
- 未知型別回傳繁中錯誤 UNSUPPORTED_DOCUMENT_TYPE
- 型別-檔案格式不相容回傳繁中錯誤
"""

import httpx
import pytest
from unittest.mock import AsyncMock, patch

from app.main import app
from app.database import get_db


@pytest.fixture(autouse=True)
def _override_db(feedback_session):
    # 端點於 few-shot 選取時需 db session;測試以 in-memory SQLite 提供
    app.dependency_overrides[get_db] = lambda: feedback_session
    yield
    app.dependency_overrides.pop(get_db, None)


def _client():
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


def _mock_service_result(document_type="transcript"):
    return {
        "file_name": "test.pdf", "file_url": None,
        "document_type": document_type, "total_pages": 1,
        "pages": [], "answer": None,
        "stats": {"total_time_ms": 100, "total_pages": 1,
                  "llm_pages_used": 0, "estimated_cost": 0.0},
    }


class TestDynamicWhitelist:
    async def test_unknown_type_rejected_with_chinese_error(self):
        async with _client() as c:
            resp = await c.post(
                "/api/v1/analyze",
                files={"file": ("test.pdf", b"%PDF-1.4 fake", "application/pdf")},
                data={"document_type": "invoice"},
            )
        assert resp.status_code == 400
        body = resp.json()
        assert body["error_code"] == "UNSUPPORTED_DOCUMENT_TYPE"
        assert "不支援的文件類型" in body["detail"]
        assert "transcript" in body["detail"]

    async def test_registered_types_reflect_factory(self):
        with patch("app.api.v1.analyze.AnalyzeService") as MockService:
            MockService.return_value.analyze = AsyncMock(
                return_value=_mock_service_result("contract"))
            async with _client() as c:
                resp = await c.post(
                    "/api/v1/analyze",
                    files={"file": ("test.pdf", b"%PDF-1.4 fake", "application/pdf")},
                    data={"document_type": "contract"},
                )
        assert resp.status_code == 200


class TestLegacyNormalization:
    async def test_lease_normalized_to_contract(self):
        with patch("app.api.v1.analyze.AnalyzeService") as MockService:
            mock_analyze = AsyncMock(return_value=_mock_service_result("contract"))
            MockService.return_value.analyze = mock_analyze
            async with _client() as c:
                resp = await c.post(
                    "/api/v1/analyze",
                    files={"file": ("test.pdf", b"%PDF-1.4 fake", "application/pdf")},
                    data={"document_type": "lease"},
                )
        assert resp.status_code == 200
        _, kwargs = mock_analyze.call_args
        assert kwargs.get("document_type") == "contract"


class TestTypeFileCompatibility:
    async def test_repair_photo_rejects_pdf(self):
        # repair_photo 已註冊(任務 13.1),但只接受影像 → PDF 不相容(需求 1.5)
        async with _client() as c:
            resp = await c.post(
                "/api/v1/analyze",
                files={"file": ("test.pdf", b"%PDF-1.4 fake", "application/pdf")},
                data={"document_type": "repair_photo"},
            )
        assert resp.status_code == 400
        assert resp.json()["error_code"] == "INCOMPATIBLE_FILE_TYPE"
