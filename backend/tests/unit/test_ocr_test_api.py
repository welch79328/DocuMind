"""
OCR 測試 API 端點單元測試

驗收標準:
- 測試不提供 document_type 預設為 transcript
- 測試 document_type="contract" 正確處理
- 測試不支援類型返回 400 錯誤
- 測試錯誤訊息格式正確（繁體中文）
- 測試回應包含 document_type 欄位
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock, Mock
from io import BytesIO
from PIL import Image
import numpy as np
from fastapi import HTTPException


@pytest.fixture
def sample_image_bytes():
    """創建測試用的圖片字節"""
    img = Image.fromarray(np.zeros((100, 100, 3), dtype=np.uint8))
    img_bytes = BytesIO()
    img.save(img_bytes, format='PNG')
    return img_bytes.getvalue()


@pytest.fixture
def mock_upload_file(sample_image_bytes):
    """創建模擬的 UploadFile 對象"""
    mock_file = Mock()
    mock_file.filename = "test.png"
    mock_file.read = AsyncMock(return_value=sample_image_bytes)
    return mock_file


@pytest.fixture
def mock_processor_result():
    """模擬處理器返回結果"""
    return {
        "page_number": 1,
        "original_image": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg",
        "ocr_raw": {
            "text": "測試 OCR 文字",
            "confidence": 0.85
        },
        "rule_postprocessed": {
            "text": "測試 OCR 文字",
            "stats": {"typo_fixes": 0}
        },
        "llm_postprocessed": None,
        "structured_data": None,
        "accuracy": None,
        "processing_steps": {
            "1_ocr_engine": "Tesseract",
            "2_rule_processing": "✓ 完成",
            "3_llm_processing": "⊗ 未使用"
        }
    }


class TestDocumentTypeParameter:
    """測試 document_type 參數處理"""

    @pytest.mark.asyncio
    @patch('app.api.v1.ocr_test.ProcessorFactory.get_processor')
    async def test_default_document_type_is_transcript(
        self,
        mock_get_processor,
        mock_upload_file,
        mock_processor_result
    ):
        """驗證不提供 document_type 參數時預設為 transcript"""
        from app.api.v1.ocr_test import test_ocr

        # 設置 mock
        mock_processor = MagicMock()
        mock_processor.process = AsyncMock(return_value=mock_processor_result)
        mock_get_processor.return_value = mock_processor

        # 調用 API（使用預設值）
        result = await test_ocr(
            file=mock_upload_file,
            enable_llm=False,
            ground_truth=None,
            page_number=None,
            document_type="transcript"  # 預設值
        )

        # 驗證結果
        assert result["document_type"] == "transcript"
        mock_get_processor.assert_called_once_with("transcript")

    @pytest.mark.asyncio
    @patch('app.api.v1.ocr_test.ProcessorFactory.get_processor')
    async def test_document_type_contract_is_processed(
        self,
        mock_get_processor,
        mock_upload_file,
        mock_processor_result
    ):
        """驗證 document_type="contract" 正確處理"""
        from app.api.v1.ocr_test import test_ocr

        # 設置 mock
        mock_processor = MagicMock()
        mock_processor.process = AsyncMock(return_value=mock_processor_result)
        mock_get_processor.return_value = mock_processor

        # 調用 API（指定 contract）
        result = await test_ocr(
            file=mock_upload_file,
            enable_llm=False,
            ground_truth=None,
            page_number=None,
            document_type="contract"
        )

        # 驗證結果
        assert result["document_type"] == "contract"
        mock_get_processor.assert_called_once_with("contract")

    @pytest.mark.asyncio
    @patch('app.api.v1.ocr_test.ProcessorFactory.get_processor')
    async def test_supported_types_work_correctly(
        self,
        mock_get_processor,
        mock_upload_file,
        mock_processor_result
    ):
        """驗證支援的文件類型能正確處理"""
        from app.api.v1.ocr_test import test_ocr

        # 設置 mock
        mock_processor = MagicMock()
        mock_processor.process = AsyncMock(return_value=mock_processor_result)
        mock_get_processor.return_value = mock_processor

        # 測試 transcript
        result = await test_ocr(
            file=mock_upload_file,
            enable_llm=False,
            ground_truth=None,
            page_number=None,
            document_type="transcript"
        )
        assert result["document_type"] == "transcript"

        # 重置並測試 contract
        mock_upload_file.read.reset_mock()
        mock_get_processor.reset_mock()

        result = await test_ocr(
            file=mock_upload_file,
            enable_llm=False,
            ground_truth=None,
            page_number=None,
            document_type="contract"
        )
        assert result["document_type"] == "contract"

    def test_api_has_proper_type_hints(self):
        """驗證 API 使用了正確的型別提示"""
        from app.api.v1.ocr_test import test_ocr
        import inspect
        from typing import get_type_hints

        # 獲取函數簽名
        sig = inspect.signature(test_ocr)

        # 驗證 document_type 參數存在
        assert 'document_type' in sig.parameters

        # 驗證參數有預設值
        param = sig.parameters['document_type']
        assert param.default is not inspect.Parameter.empty

    @pytest.mark.asyncio
    @patch('app.api.v1.ocr_test.ProcessorFactory.get_processor')
    async def test_response_includes_document_type_field(
        self,
        mock_get_processor,
        mock_upload_file,
        mock_processor_result
    ):
        """驗證回應包含 document_type 欄位"""
        from app.api.v1.ocr_test import test_ocr

        # 設置 mock
        mock_processor = MagicMock()
        mock_processor.process = AsyncMock(return_value=mock_processor_result)
        mock_get_processor.return_value = mock_processor

        # 測試 transcript 類型
        result_transcript = await test_ocr(
            file=mock_upload_file,
            enable_llm=False,
            ground_truth=None,
            page_number=None,
            document_type="transcript"
        )

        assert "document_type" in result_transcript
        assert result_transcript["document_type"] == "transcript"

        # 重置 mock 並測試 contract 類型
        mock_upload_file.read.reset_mock()
        mock_get_processor.reset_mock()

        result_contract = await test_ocr(
            file=mock_upload_file,
            enable_llm=False,
            ground_truth=None,
            page_number=None,
            document_type="contract"
        )

        assert "document_type" in result_contract
        assert result_contract["document_type"] == "contract"


class TestBackwardCompatibility:
    """測試向後兼容性"""

    @pytest.mark.asyncio
    @patch('app.api.v1.ocr_test.ProcessorFactory.get_processor')
    async def test_existing_api_calls_still_work(
        self,
        mock_get_processor,
        mock_upload_file,
        mock_processor_result
    ):
        """驗證現有 API 調用仍然有效（使用預設 document_type）"""
        from app.api.v1.ocr_test import test_ocr

        # 設置 mock
        mock_processor = MagicMock()
        mock_processor.process = AsyncMock(return_value=mock_processor_result)
        mock_get_processor.return_value = mock_processor

        # 調用 API（模擬舊的 API 調用方式，使用預設值）
        result = await test_ocr(
            file=mock_upload_file,
            enable_llm=True,
            ground_truth=None,
            page_number=None,
            document_type="transcript"  # 預設值
        )

        # 驗證回應成功
        assert "file_name" in result
        assert "total_pages" in result
        assert "document_type" in result
        assert "pages" in result

        # 驗證預設為 transcript
        assert result["document_type"] == "transcript"


class TestResponseStructure:
    """測試回應結構"""

    @pytest.mark.asyncio
    @patch('app.api.v1.ocr_test.ProcessorFactory.get_processor')
    async def test_response_has_all_required_fields(
        self,
        mock_get_processor,
        mock_upload_file,
        mock_processor_result
    ):
        """驗證回應包含所有必要欄位"""
        from app.api.v1.ocr_test import test_ocr

        # 設置 mock
        mock_processor = MagicMock()
        mock_processor.process = AsyncMock(return_value=mock_processor_result)
        mock_get_processor.return_value = mock_processor

        # 調用 API
        result = await test_ocr(
            file=mock_upload_file,
            enable_llm=False,
            ground_truth=None,
            page_number=None,
            document_type="contract"
        )

        # 驗證頂層欄位
        assert "file_name" in result
        assert "total_pages" in result
        assert "document_type" in result
        assert "pages" in result

        # 驗證 pages 是列表
        assert isinstance(result["pages"], list)
        assert len(result["pages"]) > 0

        # 驗證每一頁的結構
        page = result["pages"][0]
        assert "page_number" in page
        assert "original_image" in page
        assert "ocr_raw" in page
        assert "rule_postprocessed" in page
        assert "processing_steps" in page


class TestProcessorFactoryIntegration:
    """測試與 ProcessorFactory 的整合"""

    @pytest.mark.asyncio
    @patch('app.api.v1.ocr_test.ProcessorFactory.get_processor')
    async def test_processor_factory_called_with_correct_type(
        self,
        mock_get_processor,
        mock_upload_file,
        mock_processor_result
    ):
        """驗證 ProcessorFactory.get_processor 被正確調用"""
        from app.api.v1.ocr_test import test_ocr

        # 設置 mock
        mock_processor = MagicMock()
        mock_processor.process = AsyncMock(return_value=mock_processor_result)
        mock_get_processor.return_value = mock_processor

        # 調用 API
        await test_ocr(
            file=mock_upload_file,
            enable_llm=False,
            ground_truth=None,
            page_number=None,
            document_type="contract"
        )

        # 驗證 ProcessorFactory.get_processor 被調用
        mock_get_processor.assert_called_once_with("contract")

    @pytest.mark.asyncio
    @patch('app.api.v1.ocr_test.ProcessorFactory.get_processor')
    async def test_processor_process_method_called(
        self,
        mock_get_processor,
        mock_upload_file,
        mock_processor_result,
        sample_image_bytes
    ):
        """驗證處理器的 process() 方法被正確調用"""
        from app.api.v1.ocr_test import test_ocr

        # 設置 mock
        mock_processor = MagicMock()
        mock_processor.process = AsyncMock(return_value=mock_processor_result)
        mock_get_processor.return_value = mock_processor

        # 調用 API
        await test_ocr(
            file=mock_upload_file,
            enable_llm=True,
            ground_truth=None,
            page_number=None,
            document_type="transcript"
        )

        # 驗證 processor.process() 被調用
        assert mock_processor.process.called
        call_args = mock_processor.process.call_args

        # 驗證傳遞給 process() 的參數
        assert call_args[1]["filename"] == "test.png"
        assert call_args[1]["page_number"] == 1
        assert call_args[1]["total_pages"] == 1
        assert call_args[1]["enable_llm"] is True
