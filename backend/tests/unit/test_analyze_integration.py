"""
測試統一分析服務 - 完整流程整合

驗收標準:
- POST /api/v1/analyze 可正常存取
- 回應包含完整的 ProcessingStats
- analyze() 整合 S3 上傳 + OCR 處理並回傳 AnalyzeResponse 格式
"""

import pytest
import time
from unittest.mock import AsyncMock, patch, MagicMock
from PIL import Image
from io import BytesIO


def _make_test_image_bytes():
    img = Image.new('RGB', (100, 100), color='white')
    buf = BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def _make_mock_page_result(page_number=1, llm_used=False):
    result = {
        "page_number": page_number,
        "ocr_raw": {"text": f"第{page_number}頁", "confidence": 0.85},
        "rule_postprocessed": {
            "text": f"第{page_number}頁修正",
            "stats": {"typo_fixes": 3, "format_corrections": 1}
        },
        "llm_postprocessed": None,
        "structured_data": None,
    }
    if llm_used:
        result["llm_postprocessed"] = {
            "text": f"第{page_number}頁LLM",
            "stats": {"llm_used": True, "llm_cost": 0.02},
            "used": True,
        }
    return result


class TestAnalyzeServiceIntegration:
    """測試 AnalyzeService.analyze() 完整流程"""

    @pytest.mark.asyncio
    async def test_analyze_returns_correct_structure(self):
        """analyze() 回傳應包含所有必要欄位"""
        from app.services.analyze_service import AnalyzeService

        service = AnalyzeService()
        img_bytes = _make_test_image_bytes()

        with patch.object(service, '_upload_to_s3', new_callable=AsyncMock) as mock_s3, \
             patch.object(service, '_process_ocr', new_callable=AsyncMock) as mock_ocr:
            mock_s3.return_value = "https://cdn.example.com/uploads/ocr_transcripts/uuid.png"
            mock_ocr.return_value = ([_make_mock_page_result(1)], 1)

            result = await service.analyze(
                file_contents=img_bytes,
                filename="test.png",
                document_type="transcript",
                enable_llm=False,
            )

            assert result["file_name"] == "test.png"
            assert result["file_url"] == "https://cdn.example.com/uploads/ocr_transcripts/uuid.png"
            assert result["document_type"] == "transcript"
            assert result["total_pages"] == 1
            assert len(result["pages"]) == 1
            assert result["answer"] is None

    @pytest.mark.asyncio
    async def test_analyze_includes_processing_stats(self):
        """回應應包含完整的 ProcessingStats"""
        from app.services.analyze_service import AnalyzeService

        service = AnalyzeService()

        with patch.object(service, '_upload_to_s3', new_callable=AsyncMock) as mock_s3, \
             patch.object(service, '_process_ocr', new_callable=AsyncMock) as mock_ocr:
            mock_s3.return_value = None
            mock_ocr.return_value = ([_make_mock_page_result(1)], 1)

            result = await service.analyze(
                file_contents=_make_test_image_bytes(),
                filename="test.jpg",
                document_type="transcript",
                enable_llm=False,
            )

            stats = result["stats"]
            assert "total_time_ms" in stats
            assert "total_pages" in stats
            assert "llm_pages_used" in stats
            assert "estimated_cost" in stats
            assert stats["total_pages"] == 1
            assert isinstance(stats["total_time_ms"], int)
            assert stats["total_time_ms"] >= 0

    @pytest.mark.asyncio
    async def test_analyze_counts_llm_usage(self):
        """應正確計算 LLM 使用頁數與成本"""
        from app.services.analyze_service import AnalyzeService

        service = AnalyzeService()

        pages = [
            _make_mock_page_result(1, llm_used=True),
            _make_mock_page_result(2, llm_used=False),
            _make_mock_page_result(3, llm_used=True),
        ]

        with patch.object(service, '_upload_to_s3', new_callable=AsyncMock) as mock_s3, \
             patch.object(service, '_process_ocr', new_callable=AsyncMock) as mock_ocr:
            mock_s3.return_value = None
            mock_ocr.return_value = (pages, 3)

            result = await service.analyze(
                file_contents=b"fake",
                filename="test.pdf",
                document_type="transcript",
                enable_llm=True,
            )

            assert result["stats"]["llm_pages_used"] == 2
            assert result["stats"]["estimated_cost"] == pytest.approx(0.04)

    @pytest.mark.asyncio
    async def test_analyze_s3_failure_still_returns_result(self):
        """S3 上傳失敗時仍回傳 OCR 結果"""
        from app.services.analyze_service import AnalyzeService

        service = AnalyzeService()

        with patch.object(service, '_upload_to_s3', new_callable=AsyncMock) as mock_s3, \
             patch.object(service, '_process_ocr', new_callable=AsyncMock) as mock_ocr:
            mock_s3.return_value = None  # S3 失敗
            mock_ocr.return_value = ([_make_mock_page_result(1)], 1)

            result = await service.analyze(
                file_contents=_make_test_image_bytes(),
                filename="test.png",
                document_type="transcript",
                enable_llm=False,
            )

            assert result["file_url"] is None
            assert len(result["pages"]) == 1


class TestAnalyzeEndpointIntegration:
    """測試端點完整呼叫"""

    def test_endpoint_returns_analyze_response(self):
        """端點應回傳 AnalyzeResponse 格式"""
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)

        mock_result = {
            "file_name": "test.png",
            "file_url": "https://cdn.example.com/test.png",
            "document_type": "transcript",
            "total_pages": 1,
            "pages": [{
                "page_number": 1,
                "ocr_raw": {"text": "文字", "confidence": 0.85},
                "rule_postprocessed": {"text": "修正", "stats": {}},
                "llm_postprocessed": None,
                "structured_data": None,
            }],
            "answer": None,
            "stats": {
                "total_time_ms": 500,
                "total_pages": 1,
                "llm_pages_used": 0,
                "estimated_cost": 0.0,
            },
        }

        with patch("app.api.v1.analyze.AnalyzeService") as MockService:
            mock_instance = MockService.return_value
            mock_instance.analyze = AsyncMock(return_value=mock_result)

            response = client.post(
                "/api/v1/analyze",
                files={"file": ("test.png", _make_test_image_bytes(), "image/png")},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["file_name"] == "test.png"
            assert "stats" in data
            assert data["stats"]["total_pages"] == 1
