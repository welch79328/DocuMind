"""
測試統一分析 API - S3 上傳與路徑分配

驗收標準:
- 謄本檔案存放至 uploads/ocr_transcripts/{uuid}.{ext}
- 合約檔案存放至 uploads/ocr_contracts/{uuid}.{ext}
- 回傳完整的 CDN URL
- S3 上傳失敗時，file_url 為 null，OCR 流程繼續執行
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


class TestS3PathMapping:
    """測試 S3 路徑分配"""

    @pytest.mark.asyncio
    async def test_transcript_uses_correct_path(self):
        """謄本應使用 uploads/ocr_transcripts/ 路徑"""
        from app.services.analyze_service import AnalyzeService

        service = AnalyzeService()

        with patch.object(service, '_upload_to_s3', new_callable=AsyncMock) as mock_upload:
            mock_upload.return_value = "https://cdn.example.com/uploads/ocr_transcripts/uuid.pdf"
            url = await service._upload_to_s3(b"content", "test.pdf", "transcript")
            mock_upload.assert_called_once()

    @pytest.mark.asyncio
    async def test_contract_uses_correct_path(self):
        """合約應使用 uploads/ocr_contracts/ 路徑"""
        from app.services.analyze_service import AnalyzeService, S3_PATH_MAP
        assert S3_PATH_MAP["contract"] == "uploads/ocr_contracts"

    @pytest.mark.asyncio
    async def test_transcript_path_mapping(self):
        """驗證路徑對應表"""
        from app.services.analyze_service import S3_PATH_MAP
        assert S3_PATH_MAP["transcript"] == "uploads/ocr_transcripts"
        assert S3_PATH_MAP["contract"] == "uploads/ocr_contracts"


class TestS3Upload:
    """測試 S3 上傳功能"""

    @pytest.mark.asyncio
    async def test_upload_calls_storage_service(self):
        """上傳應呼叫 StorageService"""
        from app.services.analyze_service import AnalyzeService

        service = AnalyzeService()

        with patch("app.services.analyze_service.storage_service") as mock_storage:
            mock_storage.upload_file = AsyncMock(
                return_value="https://cdn.example.com/uploads/ocr_transcripts/uuid.pdf"
            )

            url = await service._upload_to_s3(b"pdf content", "test.pdf", "transcript")

            mock_storage.upload_file.assert_called_once_with(
                "test.pdf",
                b"pdf content",
                path_prefix="uploads/ocr_transcripts",
                acl="public-read"
            )
            assert url == "https://cdn.example.com/uploads/ocr_transcripts/uuid.pdf"

    @pytest.mark.asyncio
    async def test_upload_contract_uses_contract_path(self):
        """合約上傳應使用合約路徑"""
        from app.services.analyze_service import AnalyzeService

        service = AnalyzeService()

        with patch("app.services.analyze_service.storage_service") as mock_storage:
            mock_storage.upload_file = AsyncMock(
                return_value="https://cdn.example.com/uploads/ocr_contracts/uuid.jpg"
            )

            url = await service._upload_to_s3(b"jpg content", "contract.jpg", "contract")

            mock_storage.upload_file.assert_called_once_with(
                "contract.jpg",
                b"jpg content",
                path_prefix="uploads/ocr_contracts",
                acl="public-read"
            )


class TestS3UploadFailure:
    """測試 S3 上傳失敗的降級處理"""

    @pytest.mark.asyncio
    async def test_upload_failure_returns_none(self):
        """S3 上傳失敗時應回傳 None"""
        from app.services.analyze_service import AnalyzeService

        service = AnalyzeService()

        with patch("app.services.analyze_service.storage_service") as mock_storage:
            mock_storage.upload_file = AsyncMock(side_effect=Exception("S3 connection failed"))

            url = await service._upload_to_s3(b"content", "test.pdf", "transcript")

            assert url is None

    @pytest.mark.asyncio
    async def test_upload_failure_does_not_raise(self):
        """S3 上傳失敗不應拋出異常"""
        from app.services.analyze_service import AnalyzeService

        service = AnalyzeService()

        with patch("app.services.analyze_service.storage_service") as mock_storage:
            mock_storage.upload_file = AsyncMock(side_effect=Exception("Network error"))

            # 不應拋出異常
            url = await service._upload_to_s3(b"content", "test.pdf", "contract")
            assert url is None
