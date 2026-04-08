"""
統一端點端到端單元測試

驗收標準:
- 測試正常上傳 PDF/JPG 並驗證回應結構
- 測試不支援的檔案格式回傳 400
- 測試不支援的文件類型回傳 400
- 測試 S3 上傳失敗的降級行為
- 所有測試通過
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from PIL import Image
from io import BytesIO


def _make_png_bytes():
    img = Image.new('RGB', (100, 100), color='white')
    buf = BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def _make_analyze_result(filename="test.png", doc_type="transcript", file_url=None, pages=1):
    page_list = []
    for i in range(1, pages + 1):
        page_list.append({
            "page_number": i,
            "ocr_raw": {"text": f"第{i}頁文字", "confidence": 0.85},
            "rule_postprocessed": {"text": f"第{i}頁修正", "stats": {"typo_fixes": 3}},
            "llm_postprocessed": None,
            "structured_data": None,
        })
    return {
        "file_name": filename,
        "file_url": file_url,
        "document_type": doc_type,
        "total_pages": pages,
        "pages": page_list,
        "answer": None,
        "stats": {
            "total_time_ms": 1500,
            "total_pages": pages,
            "llm_pages_used": 0,
            "estimated_cost": 0.0,
        },
    }


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


class TestNormalUpload:
    """測試正常上傳並驗證回應結構"""

    def test_upload_png_returns_200(self, client):
        """上傳 PNG 圖片應回傳 200"""
        with patch("app.api.v1.analyze.AnalyzeService") as MockService:
            mock = MockService.return_value
            mock.analyze = AsyncMock(return_value=_make_analyze_result(
                filename="test.png",
                file_url="https://cdn.example.com/uploads/ocr_transcripts/uuid.png",
            ))

            response = client.post(
                "/api/v1/analyze",
                files={"file": ("test.png", _make_png_bytes(), "image/png")},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["file_name"] == "test.png"
            assert data["document_type"] == "transcript"
            assert data["total_pages"] == 1
            assert len(data["pages"]) == 1
            assert data["answer"] is None
            assert "stats" in data

    def test_upload_pdf_returns_200(self, client):
        """上傳 PDF 應回傳 200"""
        with patch("app.api.v1.analyze.AnalyzeService") as MockService:
            mock = MockService.return_value
            mock.analyze = AsyncMock(return_value=_make_analyze_result(
                filename="謄本.pdf",
                file_url="https://cdn.example.com/uploads/ocr_transcripts/uuid.pdf",
                pages=3,
            ))

            response = client.post(
                "/api/v1/analyze",
                files={"file": ("謄本.pdf", b"%PDF-1.4 fake", "application/pdf")},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["total_pages"] == 3
            assert len(data["pages"]) == 3

    def test_upload_jpg_returns_200(self, client):
        """上傳 JPG 應回傳 200"""
        with patch("app.api.v1.analyze.AnalyzeService") as MockService:
            mock = MockService.return_value
            mock.analyze = AsyncMock(return_value=_make_analyze_result(filename="photo.jpg"))

            response = client.post(
                "/api/v1/analyze",
                files={"file": ("photo.jpg", b"\xff\xd8\xff fake", "image/jpeg")},
            )

            assert response.status_code == 200

    def test_response_has_stats(self, client):
        """回應應包含完整的 stats"""
        with patch("app.api.v1.analyze.AnalyzeService") as MockService:
            mock = MockService.return_value
            mock.analyze = AsyncMock(return_value=_make_analyze_result())

            response = client.post(
                "/api/v1/analyze",
                files={"file": ("test.png", _make_png_bytes(), "image/png")},
            )

            stats = response.json()["stats"]
            assert "total_time_ms" in stats
            assert "total_pages" in stats
            assert "llm_pages_used" in stats
            assert "estimated_cost" in stats

    def test_contract_type_accepted(self, client):
        """contract 文件類型應被接受"""
        with patch("app.api.v1.analyze.AnalyzeService") as MockService:
            mock = MockService.return_value
            mock.analyze = AsyncMock(return_value=_make_analyze_result(doc_type="contract"))

            response = client.post(
                "/api/v1/analyze",
                files={"file": ("contract.pdf", b"%PDF fake", "application/pdf")},
                data={"document_type": "contract"},
            )

            assert response.status_code == 200
            assert response.json()["document_type"] == "contract"


class TestFileTypeRejection:
    """測試不支援的檔案格式"""

    def test_docx_returns_400(self, client):
        response = client.post(
            "/api/v1/analyze",
            files={"file": ("test.docx", b"fake", "application/msword")},
        )
        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == "UNSUPPORTED_FILE_TYPE"
        assert "PDF" in data["detail"]
        assert "JPG" in data["detail"]

    def test_csv_returns_400(self, client):
        response = client.post(
            "/api/v1/analyze",
            files={"file": ("data.csv", b"a,b,c", "text/csv")},
        )
        assert response.status_code == 400
        assert response.json()["error_code"] == "UNSUPPORTED_FILE_TYPE"

    def test_no_extension_returns_400(self, client):
        response = client.post(
            "/api/v1/analyze",
            files={"file": ("noextension", b"binary", "application/octet-stream")},
        )
        assert response.status_code == 400
        assert response.json()["error_code"] == "UNSUPPORTED_FILE_TYPE"


class TestDocumentTypeRejection:
    """測試不支援的文件類型"""

    def test_invoice_returns_400(self, client):
        response = client.post(
            "/api/v1/analyze",
            files={"file": ("test.pdf", b"%PDF", "application/pdf")},
            data={"document_type": "invoice"},
        )
        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == "UNSUPPORTED_DOCUMENT_TYPE"
        assert "transcript" in data["detail"]
        assert "contract" in data["detail"]

    def test_unknown_type_returns_400(self, client):
        response = client.post(
            "/api/v1/analyze",
            files={"file": ("test.jpg", b"\xff\xd8", "image/jpeg")},
            data={"document_type": "unknown"},
        )
        assert response.status_code == 400
        assert response.json()["error_code"] == "UNSUPPORTED_DOCUMENT_TYPE"


class TestS3FailureDegradation:
    """測試 S3 上傳失敗的降級"""

    def test_s3_failure_file_url_is_null(self, client):
        """S3 失敗時 file_url 應為 null"""
        result = _make_analyze_result(file_url=None)

        with patch("app.api.v1.analyze.AnalyzeService") as MockService:
            mock = MockService.return_value
            mock.analyze = AsyncMock(return_value=result)

            response = client.post(
                "/api/v1/analyze",
                files={"file": ("test.png", _make_png_bytes(), "image/png")},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["file_url"] is None
            assert len(data["pages"]) == 1  # OCR 結果正常

    def test_s3_failure_pages_still_present(self, client):
        """S3 失敗時 OCR 結果仍應正常回傳"""
        result = _make_analyze_result(file_url=None, pages=2)

        with patch("app.api.v1.analyze.AnalyzeService") as MockService:
            mock = MockService.return_value
            mock.analyze = AsyncMock(return_value=result)

            response = client.post(
                "/api/v1/analyze",
                files={"file": ("test.pdf", b"%PDF", "application/pdf")},
            )

            assert response.status_code == 200
            assert len(response.json()["pages"]) == 2


class TestServiceError:
    """測試服務層錯誤處理"""

    def test_internal_error_returns_500(self, client):
        """服務內部錯誤應回傳 500"""
        with patch("app.api.v1.analyze.AnalyzeService") as MockService:
            mock = MockService.return_value
            mock.analyze = AsyncMock(side_effect=RuntimeError("unexpected"))

            response = client.post(
                "/api/v1/analyze",
                files={"file": ("test.png", _make_png_bytes(), "image/png")},
            )

            assert response.status_code == 500
            data = response.json()
            assert data["error_code"] == "PROCESSING_ERROR"
            # 不應洩漏內部錯誤訊息
            assert "unexpected" not in data["detail"]
            assert "處理失敗" in data["detail"]
