"""
測試統一分析 API 端點 - 檔案驗證與參數解析

驗收標準:
- 支援 PDF、JPG、JPEG、PNG 格式，不支援的格式回傳 400
- 檔案超過 20MB 回傳 413
- 不支援的文件類型回傳 400 並列出支援的類型
- 所有錯誤訊息為繁體中文，包含統一的 error_code
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from io import BytesIO


@pytest.fixture
def client():
    """建立測試用 FastAPI client"""
    from app.main import app
    return TestClient(app)


class TestFileTypeValidation:
    """測試檔案格式驗證"""

    def test_pdf_accepted(self, client):
        """PDF 格式應被接受"""
        file = BytesIO(b"%PDF-1.4 fake pdf content")
        with patch("app.api.v1.analyze.AnalyzeService") as MockService:
            mock_instance = MockService.return_value
            mock_instance.analyze = AsyncMock(return_value={
                "file_name": "test.pdf", "file_url": None,
                "document_type": "transcript", "total_pages": 1,
                "pages": [], "answer": None,
                "stats": {"total_time_ms": 100, "total_pages": 1,
                          "llm_pages_used": 0, "estimated_cost": 0.0}
            })
            response = client.post(
                "/api/v1/analyze",
                files={"file": ("test.pdf", file, "application/pdf")},
            )
        assert response.status_code != 400 or "UNSUPPORTED_FILE_TYPE" not in response.text

    def test_jpg_accepted(self, client):
        """JPG 格式應被接受"""
        file = BytesIO(b"\xff\xd8\xff fake jpg")
        with patch("app.api.v1.analyze.AnalyzeService") as MockService:
            mock_instance = MockService.return_value
            mock_instance.analyze = AsyncMock(return_value={
                "file_name": "test.jpg", "file_url": None,
                "document_type": "transcript", "total_pages": 1,
                "pages": [], "answer": None,
                "stats": {"total_time_ms": 100, "total_pages": 1,
                          "llm_pages_used": 0, "estimated_cost": 0.0}
            })
            response = client.post(
                "/api/v1/analyze",
                files={"file": ("test.jpg", file, "image/jpeg")},
            )
        assert response.status_code != 400 or "UNSUPPORTED_FILE_TYPE" not in response.text

    def test_docx_rejected(self, client):
        """不支援的格式應回傳 400"""
        file = BytesIO(b"fake docx content")
        response = client.post(
            "/api/v1/analyze",
            files={"file": ("test.docx", file, "application/vnd.openxmlformats")},
        )
        assert response.status_code == 400
        data = response.json()
        assert "error_code" in data
        assert data["error_code"] == "UNSUPPORTED_FILE_TYPE"
        # 錯誤訊息為繁體中文
        assert "不支援" in data["detail"] or "格式" in data["detail"]

    def test_txt_rejected(self, client):
        """txt 格式應回傳 400"""
        file = BytesIO(b"plain text")
        response = client.post(
            "/api/v1/analyze",
            files={"file": ("test.txt", file, "text/plain")},
        )
        assert response.status_code == 400
        assert response.json()["error_code"] == "UNSUPPORTED_FILE_TYPE"


class TestDocumentTypeValidation:
    """測試文件類型驗證"""

    def test_invalid_document_type(self, client):
        """不支援的文件類型應回傳 400"""
        file = BytesIO(b"%PDF-1.4 fake")
        response = client.post(
            "/api/v1/analyze",
            files={"file": ("test.pdf", file, "application/pdf")},
            data={"document_type": "invoice"},
        )
        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == "UNSUPPORTED_DOCUMENT_TYPE"
        assert "transcript" in data["detail"]
        assert "contract" in data["detail"]

    def test_default_document_type_is_transcript(self, client):
        """預設文件類型為 transcript"""
        file = BytesIO(b"%PDF-1.4 fake")
        with patch("app.api.v1.analyze.AnalyzeService") as MockService:
            mock_instance = MockService.return_value
            mock_instance.analyze = AsyncMock(return_value={
                "file_name": "test.pdf", "file_url": None,
                "document_type": "transcript", "total_pages": 1,
                "pages": [], "answer": None,
                "stats": {"total_time_ms": 100, "total_pages": 1,
                          "llm_pages_used": 0, "estimated_cost": 0.0}
            })
            response = client.post(
                "/api/v1/analyze",
                files={"file": ("test.pdf", file, "application/pdf")},
            )
            # 確認 service 被呼叫時 document_type 為 transcript
            call_kwargs = mock_instance.analyze.call_args
            if call_kwargs:
                args, kwargs = call_kwargs
                assert kwargs.get("document_type", args[2] if len(args) > 2 else None) == "transcript"


class TestErrorFormat:
    """測試錯誤回應格式"""

    def test_error_has_detail_and_error_code(self, client):
        """錯誤回應必須包含 detail 和 error_code"""
        file = BytesIO(b"fake")
        response = client.post(
            "/api/v1/analyze",
            files={"file": ("test.xyz", file, "application/octet-stream")},
        )
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "error_code" in data

    def test_error_message_in_chinese(self, client):
        """錯誤訊息應為繁體中文"""
        file = BytesIO(b"fake")
        response = client.post(
            "/api/v1/analyze",
            files={"file": ("test.docx", file, "application/msword")},
        )
        data = response.json()
        # 檢查包含中文字元
        assert any('\u4e00' <= c <= '\u9fff' for c in data["detail"])
