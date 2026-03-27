"""
測試 TranscriptProcessor 謄本處理器

驗收標準:
- TranscriptProcessor 繼承 DocumentProcessor
- preprocess() 委派給 TranscriptPreprocessor
- extract_text() 委派給 EngineManager
- postprocess() 委派給 TranscriptPostprocessor
- extract_fields() 返回空字典(未來擴展)
- 保持現有謄本處理邏輯 100% 不變
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from PIL import Image
import numpy as np
from app.lib.multi_type_ocr.transcript_processor import TranscriptProcessor
from app.lib.multi_type_ocr.processor import DocumentProcessor


class TestTranscriptProcessorStructure:
    """測試 TranscriptProcessor 基本結構"""

    def test_transcript_processor_inherits_document_processor(self):
        """驗證 TranscriptProcessor 繼承 DocumentProcessor"""
        processor = TranscriptProcessor()
        assert isinstance(processor, DocumentProcessor)

    def test_transcript_processor_has_preprocessor(self):
        """驗證 TranscriptProcessor 有 preprocessor 屬性"""
        processor = TranscriptProcessor()
        assert hasattr(processor, 'preprocessor')
        assert processor.preprocessor is not None

    def test_transcript_processor_has_engine_manager(self):
        """驗證 TranscriptProcessor 有 engine_manager 屬性"""
        processor = TranscriptProcessor()
        assert hasattr(processor, 'engine_manager')
        assert processor.engine_manager is not None

    def test_transcript_processor_has_postprocessor(self):
        """驗證 TranscriptProcessor 有 postprocessor 屬性"""
        processor = TranscriptProcessor()
        assert hasattr(processor, 'postprocessor')
        assert processor.postprocessor is not None


class TestPreprocessMethod:
    """測試 preprocess 方法"""

    @pytest.mark.asyncio
    async def test_preprocess_calls_transcript_preprocessor(self):
        """驗證 preprocess 調用 TranscriptPreprocessor"""
        processor = TranscriptProcessor()

        # 創建測試圖像
        test_image = Image.new('RGB', (100, 100), color='white')

        # Mock preprocessor
        mock_array = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_metadata = {"watermark_removed": True}
        processor.preprocessor.preprocess = AsyncMock(
            return_value=(mock_array, mock_metadata)
        )

        # 執行
        result = await processor.preprocess(test_image)

        # 驗證調用
        processor.preprocessor.preprocess.assert_called_once()
        # 驗證傳入的參數是 PIL Image
        call_args = processor.preprocessor.preprocess.call_args[0]
        assert isinstance(call_args[0], Image.Image)

    @pytest.mark.asyncio
    async def test_preprocess_returns_pil_image(self):
        """驗證 preprocess 返回 PIL Image"""
        processor = TranscriptProcessor()

        test_image = Image.new('RGB', (100, 100), color='white')

        # Mock preprocessor 返回 numpy array
        mock_array = np.zeros((100, 100, 3), dtype=np.uint8)
        processor.preprocessor.preprocess = AsyncMock(
            return_value=(mock_array, {})
        )

        result = await processor.preprocess(test_image)

        # 驗證返回類型
        assert isinstance(result, Image.Image)

    @pytest.mark.asyncio
    async def test_preprocess_converts_bgr_to_rgb(self):
        """驗證 preprocess 正確轉換 BGR 到 RGB"""
        processor = TranscriptProcessor()

        test_image = Image.new('RGB', (100, 100), color=(255, 0, 0))  # 紅色

        # Mock preprocessor 返回 BGR 格式 numpy array
        # OpenCV uses BGR, so blue channel should have the red value
        mock_array = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_array[:, :, 2] = 255  # BGR 格式的紅色（B=0, G=0, R=255）
        processor.preprocessor.preprocess = AsyncMock(
            return_value=(mock_array, {})
        )

        result = await processor.preprocess(test_image)

        # 驗證轉換正確（RGB 格式應該是 R=255）
        result_array = np.array(result)
        assert result_array[0, 0, 0] == 255  # R channel


class TestExtractTextMethod:
    """測試 extract_text 方法"""

    @pytest.mark.asyncio
    async def test_extract_text_calls_engine_manager(self):
        """驗證 extract_text 調用 EngineManager"""
        processor = TranscriptProcessor()

        test_image = Image.new('RGB', (100, 100), color='white')

        # Mock engine_manager
        processor.engine_manager.extract_text_multi_engine = AsyncMock(
            return_value=("測試文字", 0.95, [])
        )

        # 執行
        text, confidence = await processor.extract_text(test_image)

        # 驗證調用
        processor.engine_manager.extract_text_multi_engine.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_text_returns_text_and_confidence(self):
        """驗證 extract_text 返回文字和信心度"""
        processor = TranscriptProcessor()

        test_image = Image.new('RGB', (100, 100), color='white')

        # Mock engine_manager
        expected_text = "謄本測試文字"
        expected_confidence = 0.87
        processor.engine_manager.extract_text_multi_engine = AsyncMock(
            return_value=(expected_text, expected_confidence, [])
        )

        # 執行
        text, confidence = await processor.extract_text(test_image)

        # 驗證返回值
        assert text == expected_text
        assert confidence == expected_confidence
        assert isinstance(text, str)
        assert isinstance(confidence, float)

    @pytest.mark.asyncio
    async def test_extract_text_accepts_pil_image(self):
        """驗證 extract_text 接受 PIL Image 並轉換為 numpy array"""
        processor = TranscriptProcessor()

        test_image = Image.new('RGB', (100, 100), color='white')

        processor.engine_manager.extract_text_multi_engine = AsyncMock(
            return_value=("text", 0.9, [])
        )

        await processor.extract_text(test_image)

        # 驗證傳入的是 numpy array
        call_args = processor.engine_manager.extract_text_multi_engine.call_args[0]
        assert isinstance(call_args[0], np.ndarray)


class TestPostprocessMethod:
    """測試 postprocess 方法"""

    @pytest.mark.asyncio
    async def test_postprocess_calls_transcript_postprocessor(self):
        """驗證 postprocess 調用 TranscriptPostprocessor"""
        processor = TranscriptProcessor()

        test_text = "測試文字"
        test_confidence = 0.85

        # Mock postprocessor
        processor.postprocessor.postprocess = AsyncMock(
            return_value=("修正後文字", {"typo_fixes": 5})
        )

        # 執行
        result_text, stats = await processor.postprocess(test_text, test_confidence)

        # 驗證調用（接受關鍵字參數）
        processor.postprocessor.postprocess.assert_called_once()
        call_args, call_kwargs = processor.postprocessor.postprocess.call_args

        # 驗證參數值
        assert call_args[0] == test_text
        assert call_kwargs.get('ocr_confidence') == test_confidence
        assert call_kwargs.get('image_data') is None

    @pytest.mark.asyncio
    async def test_postprocess_returns_text_and_stats(self):
        """驗證 postprocess 返回文字和統計資訊"""
        processor = TranscriptProcessor()

        expected_text = "修正後的謄本文字"
        expected_stats = {"typo_fixes": 3, "format_corrections": 2}

        processor.postprocessor.postprocess = AsyncMock(
            return_value=(expected_text, expected_stats)
        )

        result_text, stats = await processor.postprocess("原始文字", 0.9)

        assert result_text == expected_text
        assert stats == expected_stats

    @pytest.mark.asyncio
    async def test_postprocess_passes_image_data(self):
        """驗證 postprocess 正確傳遞 image_data 參數"""
        processor = TranscriptProcessor()

        test_image_data = "data:image/png;base64,iVBORw0KGgoAAAANS..."

        processor.postprocessor.postprocess = AsyncMock(
            return_value=("text", {})
        )

        await processor.postprocess("text", 0.9, test_image_data)

        # 驗證 image_data 被傳遞
        call_args = processor.postprocessor.postprocess.call_args[0]
        call_kwargs = processor.postprocessor.postprocess.call_args[1]
        # image_data 可能作為位置參數或關鍵字參數傳遞
        if len(call_args) > 2:
            assert call_args[2] == test_image_data
        else:
            assert call_kwargs.get('image_data') == test_image_data


class TestExtractFieldsMethod:
    """測試 extract_fields 方法"""

    @pytest.mark.asyncio
    async def test_extract_fields_returns_empty_dict(self):
        """驗證 extract_fields 返回空字典（未來實作）"""
        processor = TranscriptProcessor()

        result = await processor.extract_fields("謄本文字內容")

        assert isinstance(result, dict)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_extract_fields_accepts_text_parameter(self):
        """驗證 extract_fields 接受文字參數"""
        processor = TranscriptProcessor()

        # 不應拋出異常
        test_text = "建物謄本\n地號：1234\n面積：100平方公尺"
        result = await processor.extract_fields(test_text)

        # 目前應返回空字典
        assert result == {}


class TestProcessorConfiguration:
    """測試處理器配置"""

    def test_preprocessor_uses_default_config(self):
        """驗證 preprocessor 使用預設配置"""
        processor = TranscriptProcessor()

        # 驗證 preprocessor 有正確的配置
        assert processor.preprocessor.config is not None
        assert processor.preprocessor.config.enable_watermark_removal is True

    def test_engine_manager_uses_correct_engines(self):
        """驗證 engine_manager 使用正確的引擎"""
        processor = TranscriptProcessor()

        # 驗證引擎配置
        assert processor.engine_manager.engines is not None
        assert isinstance(processor.engine_manager.engines, list)

    def test_postprocessor_has_correct_settings(self):
        """驗證 postprocessor 有正確的設定"""
        processor = TranscriptProcessor()

        # 驗證後處理器設定
        assert processor.postprocessor.enable_typo_fix is True
        assert processor.postprocessor.enable_format_correction is True


class TestProcessTemplateMethod:
    """測試 process() 模板方法的完整流程（驗收標準 4.2）"""

    @pytest.mark.asyncio
    async def test_process_method_full_pipeline(self):
        """驗證 process() 模板方法執行完整處理流程"""
        import io

        processor = TranscriptProcessor()

        # 準備真實的圖像資料（創建一個小的測試圖像）
        test_image = Image.new('RGB', (100, 100), color='white')
        img_byte_arr = io.BytesIO()
        test_image.save(img_byte_arr, format='PNG')
        test_file_contents = img_byte_arr.getvalue()

        test_filename = "test.jpg"
        test_page_number = 1
        test_total_pages = 1

        # Mock 各個階段
        mock_preprocessed_image = Image.new('RGB', (100, 100), color='white')
        mock_ocr_text = "測試謄本文字"
        mock_ocr_confidence = 0.85
        mock_postprocessed_text = "修正後的謄本文字"
        mock_postprocess_stats = {"typo_fixes": 3}
        # 空字典會被轉換為 None（參考 processor.py:233）
        mock_structured_data = {}

        processor.preprocess = AsyncMock(return_value=mock_preprocessed_image)
        processor.extract_text = AsyncMock(return_value=(mock_ocr_text, mock_ocr_confidence))
        processor.postprocess = AsyncMock(return_value=(mock_postprocessed_text, mock_postprocess_stats))
        processor.extract_fields = AsyncMock(return_value=mock_structured_data)

        # 執行完整流程
        result = await processor.process(
            file_contents=test_file_contents,
            filename=test_filename,
            page_number=test_page_number,
            total_pages=test_total_pages,
            enable_llm=False
        )

        # 驗證每個步驟都被調用
        processor.preprocess.assert_called_once()
        processor.extract_text.assert_called_once_with(mock_preprocessed_image)
        processor.postprocess.assert_called_once()
        processor.extract_fields.assert_called_once_with(
            mock_postprocessed_text,
            image_data=None,
            enable_llm=False
        )

        # 驗證返回結果結構
        assert "page_number" in result
        assert "ocr_raw" in result
        assert "rule_postprocessed" in result
        assert "structured_data" in result

        # 驗證各階段資料正確組合
        assert result["page_number"] == test_page_number
        assert result["ocr_raw"]["text"] == mock_ocr_text
        assert result["ocr_raw"]["confidence"] == mock_ocr_confidence
        assert result["rule_postprocessed"]["text"] == mock_postprocessed_text
        assert result["rule_postprocessed"]["stats"] == mock_postprocess_stats
        # 空 dict 會被轉換為 None（processor.py:233）
        assert result["structured_data"] is None

    @pytest.mark.asyncio
    async def test_process_method_handles_enable_llm_parameter(self):
        """驗證 process() 方法正確處理 enable_llm 參數"""
        import io

        processor = TranscriptProcessor()

        # 準備真實的圖像資料
        test_image = Image.new('RGB', (100, 100), color='white')
        img_byte_arr = io.BytesIO()
        test_image.save(img_byte_arr, format='PNG')
        test_file_contents = img_byte_arr.getvalue()

        # Mock 所有方法
        processor.preprocess = AsyncMock(return_value=Image.new('RGB', (100, 100)))
        processor.extract_text = AsyncMock(return_value=("text", 0.9))
        processor.postprocess = AsyncMock(return_value=("text", {}))
        processor.extract_fields = AsyncMock(return_value={})

        # 測試 enable_llm=True
        await processor.process(
            file_contents=test_file_contents,
            filename="test.jpg",
            page_number=1,
            total_pages=1,
            enable_llm=True
        )

        # 測試 enable_llm=False
        await processor.process(
            file_contents=test_file_contents,
            filename="test.jpg",
            page_number=1,
            total_pages=1,
            enable_llm=False
        )

        # 確保兩種情況都正常執行
        assert processor.preprocess.call_count == 2
        assert processor.extract_text.call_count == 2
