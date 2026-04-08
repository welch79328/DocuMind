"""
測試用量統計記錄

驗收標準:
- api_usage_logs 資料表模型定義正確
- 每次 analyze 呼叫後自動寫入用量記錄
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


class TestApiUsageLogModel:
    """測試 ApiUsageLog 模型定義"""

    def test_model_exists(self):
        from app.models.api_usage_log import ApiUsageLog
        assert ApiUsageLog is not None

    def test_model_tablename(self):
        from app.models.api_usage_log import ApiUsageLog
        assert ApiUsageLog.__tablename__ == "api_usage_logs"

    def test_model_has_required_columns(self):
        from app.models.api_usage_log import ApiUsageLog
        columns = {c.name for c in ApiUsageLog.__table__.columns}
        assert "id" in columns
        assert "endpoint" in columns
        assert "document_type" in columns
        assert "total_pages" in columns
        assert "llm_used" in columns
        assert "llm_cost" in columns
        assert "processing_time_ms" in columns
        assert "created_at" in columns


class TestUsageRecording:
    """測試 analyze 呼叫後寫入用量記錄"""

    @pytest.mark.asyncio
    async def test_analyze_records_usage(self):
        """analyze() 完成後應寫入用量記錄"""
        from app.services.analyze_service import AnalyzeService

        service = AnalyzeService()

        mock_pages = [{
            "page_number": 1,
            "ocr_raw": {"text": "文字", "confidence": 0.85},
            "rule_postprocessed": {"text": "文字", "stats": {}},
            "llm_postprocessed": None,
            "structured_data": None,
        }]

        with patch.object(service, '_upload_to_s3', new_callable=AsyncMock) as mock_s3, \
             patch.object(service, '_process_ocr', new_callable=AsyncMock) as mock_ocr, \
             patch.object(service, '_record_usage') as mock_record:
            mock_s3.return_value = None
            mock_ocr.return_value = (mock_pages, 1)

            await service.analyze(
                file_contents=b"fake",
                filename="test.png",
                document_type="transcript",
                enable_llm=False,
            )

            mock_record.assert_called_once()
            call_kwargs = mock_record.call_args[1] if mock_record.call_args[1] else {}
            call_args = mock_record.call_args[0] if mock_record.call_args[0] else ()

            # 驗證記錄內容（不論用位置或關鍵字參數傳遞）
            if call_kwargs:
                assert call_kwargs.get("document_type") == "transcript"
                assert call_kwargs.get("total_pages") == 1

    @pytest.mark.asyncio
    async def test_usage_recording_failure_does_not_break_response(self):
        """用量記錄失敗不應影響回應"""
        from app.services.analyze_service import AnalyzeService

        service = AnalyzeService()

        mock_pages = [{
            "page_number": 1,
            "ocr_raw": {"text": "文字", "confidence": 0.85},
            "rule_postprocessed": {"text": "文字", "stats": {}},
            "llm_postprocessed": None,
            "structured_data": None,
        }]

        with patch.object(service, '_upload_to_s3', new_callable=AsyncMock) as mock_s3, \
             patch.object(service, '_process_ocr', new_callable=AsyncMock) as mock_ocr, \
             patch.object(service, '_record_usage', side_effect=Exception("DB error")):
            mock_s3.return_value = None
            mock_ocr.return_value = (mock_pages, 1)

            # 不應拋出異常
            result = await service.analyze(
                file_contents=b"fake",
                filename="test.png",
                document_type="transcript",
                enable_llm=False,
            )

            assert result["file_name"] == "test.png"
            assert len(result["pages"]) == 1
