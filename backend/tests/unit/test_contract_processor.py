"""
測試 ContractProcessor 合約處理器

驗收標準:
- ContractProcessor 繼承 DocumentProcessor
- preprocess() 使用 TranscriptPreprocessor,禁用浮水印移除
- extract_text() 使用 EngineManager
- postprocess() 使用 TranscriptPostprocessor
- extract_fields() 返回符合 ContractStructuredData 結構的空欄位
- 能完成端到端的合約 OCR 處理
"""

import pytest
from unittest.mock import Mock, AsyncMock
from PIL import Image
import numpy as np
from app.lib.multi_type_ocr.contract_processor import ContractProcessor
from app.lib.multi_type_ocr.processor import DocumentProcessor
from app.lib.multi_type_ocr.types import ContractStructuredData


class TestContractProcessorStructure:
    """測試 ContractProcessor 基本結構"""

    def test_contract_processor_inherits_document_processor(self):
        """驗證 ContractProcessor 繼承 DocumentProcessor"""
        processor = ContractProcessor()
        assert isinstance(processor, DocumentProcessor)

    def test_contract_processor_has_preprocessor(self):
        """驗證 ContractProcessor 有 preprocessor 屬性"""
        processor = ContractProcessor()
        assert hasattr(processor, 'preprocessor')
        assert processor.preprocessor is not None

    def test_contract_processor_has_engine_manager(self):
        """驗證 ContractProcessor 有 engine_manager 屬性"""
        processor = ContractProcessor()
        assert hasattr(processor, 'engine_manager')
        assert processor.engine_manager is not None

    def test_contract_processor_has_postprocessor(self):
        """驗證 ContractProcessor 有 postprocessor 屬性"""
        processor = ContractProcessor()
        assert hasattr(processor, 'postprocessor')
        assert processor.postprocessor is not None


class TestPreprocessorConfiguration:
    """測試預處理器配置"""

    def test_preprocessor_watermark_removal_disabled(self):
        """驗證預處理器禁用浮水印移除（合約通常無浮水印）"""
        processor = ContractProcessor()

        # 驗證配置正確
        assert processor.preprocessor.config.enable_watermark_removal is False

    def test_preprocessor_denoising_enabled(self):
        """驗證預處理器啟用去噪（合約可能需要更強的去噪）"""
        processor = ContractProcessor()

        # 驗證去噪啟用
        assert processor.preprocessor.config.enable_denoising is True

    def test_preprocessor_configuration_different_from_transcript(self):
        """驗證合約處理器配置與謄本處理器不同"""
        from app.lib.multi_type_ocr.transcript_processor import TranscriptProcessor

        contract_processor = ContractProcessor()
        transcript_processor = TranscriptProcessor()

        # 合約不移除浮水印，謄本移除
        assert (contract_processor.preprocessor.config.enable_watermark_removal !=
                transcript_processor.preprocessor.config.enable_watermark_removal)


class TestPreprocessMethod:
    """測試 preprocess 方法"""

    @pytest.mark.asyncio
    async def test_preprocess_calls_preprocessor(self):
        """驗證 preprocess 調用 TranscriptPreprocessor"""
        processor = ContractProcessor()

        test_image = Image.new('RGB', (100, 100), color='white')

        # Mock preprocessor
        mock_array = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_metadata = {"watermark_removed": False}
        processor.preprocessor.preprocess = AsyncMock(
            return_value=(mock_array, mock_metadata)
        )

        result = await processor.preprocess(test_image)

        # 驗證調用
        processor.preprocessor.preprocess.assert_called_once()
        assert isinstance(result, Image.Image)

    @pytest.mark.asyncio
    async def test_preprocess_returns_pil_image(self):
        """驗證 preprocess 返回 PIL Image"""
        processor = ContractProcessor()

        test_image = Image.new('RGB', (100, 100), color='white')

        mock_array = np.zeros((100, 100, 3), dtype=np.uint8)
        processor.preprocessor.preprocess = AsyncMock(
            return_value=(mock_array, {})
        )

        result = await processor.preprocess(test_image)

        assert isinstance(result, Image.Image)


class TestExtractTextMethod:
    """測試 extract_text 方法"""

    @pytest.mark.asyncio
    async def test_extract_text_calls_engine_manager(self):
        """驗證 extract_text 調用 EngineManager"""
        processor = ContractProcessor()

        test_image = Image.new('RGB', (100, 100), color='white')

        processor.engine_manager.extract_text_multi_engine = AsyncMock(
            return_value=("合約測試文字", 0.92, [])
        )

        text, confidence = await processor.extract_text(test_image)

        processor.engine_manager.extract_text_multi_engine.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_text_returns_text_and_confidence(self):
        """驗證 extract_text 返回文字和信心度"""
        processor = ContractProcessor()

        test_image = Image.new('RGB', (100, 100), color='white')

        expected_text = "合約書\n甲方：公司A\n乙方：公司B"
        expected_confidence = 0.88

        processor.engine_manager.extract_text_multi_engine = AsyncMock(
            return_value=(expected_text, expected_confidence, [])
        )

        text, confidence = await processor.extract_text(test_image)

        assert text == expected_text
        assert confidence == expected_confidence
        assert isinstance(text, str)
        assert isinstance(confidence, float)


class TestPostprocessMethod:
    """測試 postprocess 方法"""

    @pytest.mark.asyncio
    async def test_postprocess_calls_postprocessor(self):
        """驗證 postprocess 調用 TranscriptPostprocessor"""
        processor = ContractProcessor()

        test_text = "合約測試文字"
        test_confidence = 0.85

        processor.postprocessor.postprocess = AsyncMock(
            return_value=("修正後文字", {"typo_fixes": 2})
        )

        result_text, stats = await processor.postprocess(test_text, test_confidence)

        processor.postprocessor.postprocess.assert_called_once()

    @pytest.mark.asyncio
    async def test_postprocess_returns_text_and_stats(self):
        """驗證 postprocess 返回文字和統計資訊"""
        processor = ContractProcessor()

        expected_text = "修正後的合約文字"
        expected_stats = {"typo_fixes": 1, "format_corrections": 0}

        processor.postprocessor.postprocess = AsyncMock(
            return_value=(expected_text, expected_stats)
        )

        result_text, stats = await processor.postprocess("原始文字", 0.9)

        assert result_text == expected_text
        assert stats == expected_stats


class TestExtractFieldsMethod:
    """測試 extract_fields 方法"""

    @pytest.mark.asyncio
    async def test_extract_fields_returns_contract_structured_data(self):
        """驗證 extract_fields 返回符合 ContractStructuredData 結構"""
        processor = ContractProcessor()

        result = await processor.extract_fields("合約文字內容")

        # 驗證返回的是字典
        assert isinstance(result, dict)

        # 驗證包含必要的頂層鍵
        assert "contract_metadata" in result
        assert "parties" in result
        assert "financial_terms" in result
        assert "extraction_confidence" in result

    @pytest.mark.asyncio
    async def test_extract_fields_returns_empty_metadata(self):
        """驗證 extract_fields 返回空的元資訊（Phase 2 實作）"""
        processor = ContractProcessor()

        result = await processor.extract_fields("合約內容")

        metadata = result["contract_metadata"]
        assert metadata["contract_number"] is None
        assert metadata["signing_date"] is None
        assert metadata["effective_date"] is None

    @pytest.mark.asyncio
    async def test_extract_fields_returns_empty_parties(self):
        """驗證 extract_fields 返回空的雙方資訊"""
        processor = ContractProcessor()

        result = await processor.extract_fields("合約內容")

        parties = result["parties"]
        assert parties["party_a"] is None
        assert parties["party_b"] is None
        assert parties["party_a_address"] is None
        assert parties["party_b_address"] is None

    @pytest.mark.asyncio
    async def test_extract_fields_returns_empty_financial_terms(self):
        """驗證 extract_fields 返回空的財務條款"""
        processor = ContractProcessor()

        result = await processor.extract_fields("合約內容")

        financial = result["financial_terms"]
        assert financial["contract_amount"] is None
        assert financial["currency"] is None
        assert financial["payment_method"] is None
        assert financial["payment_deadline"] is None

    @pytest.mark.asyncio
    async def test_extract_fields_confidence_is_zero(self):
        """驗證 extract_fields 返回的信心度為 0.0（基礎版未實作提取）"""
        processor = ContractProcessor()

        result = await processor.extract_fields("合約內容")

        assert result["extraction_confidence"] == 0.0


class TestProcessorConfiguration:
    """測試處理器配置"""

    def test_engine_manager_uses_correct_engines(self):
        """驗證 engine_manager 使用正確的引擎"""
        processor = ContractProcessor()

        assert processor.engine_manager.engines is not None
        assert isinstance(processor.engine_manager.engines, list)

    def test_postprocessor_has_correct_settings(self):
        """驗證 postprocessor 有正確的設定"""
        processor = ContractProcessor()

        assert processor.postprocessor.enable_typo_fix is True
        assert processor.postprocessor.enable_format_correction is True
