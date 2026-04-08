"""
測試統一端點 - 問答功能與錯誤格式

驗收標準:
- 測試帶 question 參數回傳 AI 回答
- 測試不帶 question 時 answer 為 null
- 測試錯誤回應格式正確
- 所有測試通過
"""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from PIL import Image
from io import BytesIO


def _make_png_bytes():
    img = Image.new('RGB', (100, 100), color='white')
    buf = BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def _make_result(answer=None):
    return {
        "file_name": "test.png",
        "file_url": None,
        "document_type": "transcript",
        "total_pages": 1,
        "pages": [{
            "page_number": 1,
            "ocr_raw": {"text": "所有權人：黃水木", "confidence": 0.85},
            "rule_postprocessed": {"text": "所有權人：黃水木", "stats": {}},
            "llm_postprocessed": None,
            "structured_data": None,
        }],
        "answer": answer,
        "stats": {
            "total_time_ms": 1000,
            "total_pages": 1,
            "llm_pages_used": 0,
            "estimated_cost": 0.0,
        },
    }


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


class TestQuestionEndpoint:
    """測試端點層的問答功能"""

    def test_with_question_returns_answer(self, client):
        """帶 question 參數時回應應包含 AI 回答"""
        with patch("app.api.v1.analyze.AnalyzeService") as MockService:
            mock = MockService.return_value
            mock.analyze = AsyncMock(return_value=_make_result(answer="所有權人是黃水木"))

            response = client.post(
                "/api/v1/analyze",
                files={"file": ("test.png", _make_png_bytes(), "image/png")},
                data={"question": "所有權人是誰？"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["answer"] == "所有權人是黃水木"

    def test_without_question_answer_is_null(self, client):
        """不帶 question 時 answer 應為 null"""
        with patch("app.api.v1.analyze.AnalyzeService") as MockService:
            mock = MockService.return_value
            mock.analyze = AsyncMock(return_value=_make_result(answer=None))

            response = client.post(
                "/api/v1/analyze",
                files={"file": ("test.png", _make_png_bytes(), "image/png")},
            )

            assert response.status_code == 200
            assert response.json()["answer"] is None

    def test_question_passes_to_service(self, client):
        """question 參數應正確傳遞到 service"""
        with patch("app.api.v1.analyze.AnalyzeService") as MockService:
            mock = MockService.return_value
            mock.analyze = AsyncMock(return_value=_make_result())

            client.post(
                "/api/v1/analyze",
                files={"file": ("test.png", _make_png_bytes(), "image/png")},
                data={"question": "金額多少？"},
            )

            call_kwargs = mock.analyze.call_args[1]
            assert call_kwargs["question"] == "金額多少？"


class TestAllErrorFormats:
    """測試所有錯誤回應格式一致性"""

    def test_unsupported_file_format(self, client):
        """不支援的檔案格式"""
        response = client.post(
            "/api/v1/analyze",
            files={"file": ("test.docx", b"fake", "application/msword")},
        )
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "error_code" in data
        assert data["error_code"] == "UNSUPPORTED_FILE_TYPE"
        # 繁體中文
        assert any('\u4e00' <= c <= '\u9fff' for c in data["detail"])

    def test_unsupported_document_type(self, client):
        """不支援的文件類型"""
        response = client.post(
            "/api/v1/analyze",
            files={"file": ("test.pdf", b"%PDF", "application/pdf")},
            data={"document_type": "invoice"},
        )
        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == "UNSUPPORTED_DOCUMENT_TYPE"
        assert any('\u4e00' <= c <= '\u9fff' for c in data["detail"])

    def test_processing_error_format(self, client):
        """處理錯誤"""
        with patch("app.api.v1.analyze.AnalyzeService") as MockService:
            mock = MockService.return_value
            mock.analyze = AsyncMock(side_effect=RuntimeError("boom"))

            response = client.post(
                "/api/v1/analyze",
                files={"file": ("test.png", _make_png_bytes(), "image/png")},
            )

            assert response.status_code == 500
            data = response.json()
            assert data["error_code"] == "PROCESSING_ERROR"
            assert any('\u4e00' <= c <= '\u9fff' for c in data["detail"])
            # 不洩漏內部錯誤
            assert "boom" not in data["detail"]

    def test_all_errors_have_consistent_keys(self, client):
        """所有錯誤回應都應有 detail 和 error_code 兩個 key"""
        # 測試多種錯誤，確認格式一致
        error_cases = [
            # (filename, content_type, data, expected_code)
            ("test.xlsx", "application/vnd.ms-excel", {}, "UNSUPPORTED_FILE_TYPE"),
            ("test.pdf", "application/pdf", {"document_type": "receipt"}, "UNSUPPORTED_DOCUMENT_TYPE"),
        ]

        for filename, content_type, data, expected_code in error_cases:
            response = client.post(
                "/api/v1/analyze",
                files={"file": (filename, b"fake", content_type)},
                data=data,
            )
            resp_data = response.json()
            assert set(resp_data.keys()) == {"detail", "error_code"}, \
                f"錯誤回應 key 不一致: {resp_data.keys()} for {expected_code}"
            assert resp_data["error_code"] == expected_code


class TestSwaggerDocs:
    """測試 Swagger 文檔可用性"""

    def test_openapi_json_accessible(self, client):
        """OpenAPI JSON 應可存取"""
        response = client.get("/api/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "paths" in data

    def test_analyze_endpoint_in_openapi(self, client):
        """analyze 端點應出現在 OpenAPI 文檔中"""
        response = client.get("/api/openapi.json")
        paths = response.json()["paths"]
        assert "/api/v1/analyze" in paths
        assert "post" in paths["/api/v1/analyze"]

    def test_analyze_has_description(self, client):
        """analyze 端點應有繁體中文說明"""
        response = client.get("/api/openapi.json")
        endpoint = response.json()["paths"]["/api/v1/analyze"]["post"]
        assert "summary" in endpoint or "description" in endpoint
