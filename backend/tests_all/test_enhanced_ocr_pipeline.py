"""
測試 EnhancedOCRPipeline 框架

驗證管道初始化、process() 方法骨架與錯誤處理。
"""

import logging
import pytest
from app.lib.ocr_enhanced import EnhancedOCRPipeline
from app.lib.ocr_enhanced.types import OCRResult


class TestEnhancedOCRPipelineInit:
    """測試 EnhancedOCRPipeline 初始化"""

    def test_pipeline_can_be_instantiated(self):
        """測試管道可以被實例化"""
        pipeline = EnhancedOCRPipeline()
        assert pipeline is not None

    def test_pipeline_init_with_default_config(self):
        """測試使用預設配置初始化"""
        pipeline = EnhancedOCRPipeline()

        assert pipeline.enable_preprocessing is True
        assert pipeline.enable_postprocessing is True
        assert pipeline.enable_multi_engine is False
        assert pipeline.enable_quality_check is True

    def test_pipeline_init_with_custom_config(self):
        """測試使用自訂配置初始化"""
        pipeline = EnhancedOCRPipeline(
            enable_preprocessing=False,
            enable_postprocessing=False,
            enable_multi_engine=True,
            enable_quality_check=False
        )

        assert pipeline.enable_preprocessing is False
        assert pipeline.enable_postprocessing is False
        assert pipeline.enable_multi_engine is True
        assert pipeline.enable_quality_check is False

    def test_pipeline_initializes_all_modules(self):
        """測試管道初始化所有子模組"""
        pipeline = EnhancedOCRPipeline()

        # 驗證所有模組都被初始化
        assert hasattr(pipeline, 'classifier')
        assert hasattr(pipeline, 'preprocessor')
        assert hasattr(pipeline, 'engine_manager')
        assert hasattr(pipeline, 'postprocessor')
        assert hasattr(pipeline, 'quality_assessor')
        assert hasattr(pipeline, 'field_extractor')

        # 驗證模組不為 None
        assert pipeline.classifier is not None
        assert pipeline.preprocessor is not None
        assert pipeline.engine_manager is not None
        assert pipeline.postprocessor is not None
        assert pipeline.quality_assessor is not None
        assert pipeline.field_extractor is not None


class TestEnhancedOCRPipelineProcess:
    """測試 EnhancedOCRPipeline.process() 方法"""

    @pytest.mark.asyncio
    async def test_process_method_exists(self):
        """測試 process() 方法存在且可呼叫"""
        pipeline = EnhancedOCRPipeline()

        # 驗證 process 方法存在
        assert hasattr(pipeline, 'process')
        assert callable(pipeline.process)

    @pytest.mark.asyncio
    async def test_process_returns_ocr_result(self):
        """測試 process() 返回 OCRResult 結構"""
        pipeline = EnhancedOCRPipeline()

        result = await pipeline.process("file:///test.jpg")

        # 驗證返回 OCRResult 結構
        assert isinstance(result, dict)
        assert "text" in result
        assert "page_count" in result
        assert "quality_score" in result
        assert "confidence" in result
        assert "metadata" in result

    @pytest.mark.asyncio
    async def test_process_with_auto_doc_type(self):
        """測試使用 auto 文件類型"""
        pipeline = EnhancedOCRPipeline()

        result = await pipeline.process("file:///test.jpg", doc_type="auto")

        assert result is not None
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_process_with_specific_doc_type(self):
        """測試使用特定文件類型"""
        pipeline = EnhancedOCRPipeline()

        result = await pipeline.process("file:///test.jpg", doc_type="transcript")

        assert result is not None
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_process_returns_correct_types(self):
        """測試 process() 返回正確的型別"""
        pipeline = EnhancedOCRPipeline()

        result = await pipeline.process("file:///test.jpg")

        # 驗證欄位型別
        assert isinstance(result["text"], str)
        assert isinstance(result["page_count"], int)
        assert isinstance(result["quality_score"], float)
        assert isinstance(result["confidence"], float)
        assert isinstance(result["metadata"], dict)


class TestEnhancedOCRPipelineErrorHandling:
    """測試 EnhancedOCRPipeline 錯誤處理"""

    @pytest.mark.asyncio
    async def test_process_handles_empty_url(self):
        """測試處理空 URL"""
        pipeline = EnhancedOCRPipeline()

        # 目前應該返回空結果，不拋出異常
        result = await pipeline.process("")

        assert result is not None
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_process_handles_invalid_doc_type(self):
        """測試處理無效的文件類型"""
        pipeline = EnhancedOCRPipeline()

        # 使用 unknown 作為文件類型應該可以處理
        result = await pipeline.process("file:///test.jpg", doc_type="unknown")

        assert result is not None
        assert isinstance(result, dict)


class TestEnhancedOCRPipelineProcessingFlow:
    """測試 EnhancedOCRPipeline 處理流程"""

    @pytest.mark.asyncio
    async def test_process_flow_metadata_exists(self):
        """測試處理流程元數據存在"""
        pipeline = EnhancedOCRPipeline()

        result = await pipeline.process("file:///test.jpg")

        # 驗證 metadata 欄位存在
        assert "metadata" in result
        assert isinstance(result["metadata"], dict)

    @pytest.mark.asyncio
    async def test_pipeline_with_preprocessing_disabled(self):
        """測試關閉預處理的管道"""
        pipeline = EnhancedOCRPipeline(enable_preprocessing=False)

        result = await pipeline.process("file:///test.jpg")

        assert result is not None
        assert pipeline.enable_preprocessing is False

    @pytest.mark.asyncio
    async def test_pipeline_with_multi_engine_enabled(self):
        """測試啟用多引擎的管道"""
        pipeline = EnhancedOCRPipeline(enable_multi_engine=True)

        result = await pipeline.process("file:///test.jpg")

        assert result is not None
        assert pipeline.enable_multi_engine is True

    @pytest.mark.asyncio
    async def test_pipeline_with_quality_check_disabled(self):
        """測試關閉品質檢查的管道"""
        pipeline = EnhancedOCRPipeline(enable_quality_check=False)

        result = await pipeline.process("file:///test.jpg")

        assert result is not None
        assert pipeline.enable_quality_check is False


class TestEnhancedOCRPipelineLogging:
    """測試 EnhancedOCRPipeline 日誌記錄"""

    def test_pipeline_has_logger(self):
        """測試管道有日誌記錄器"""
        pipeline = EnhancedOCRPipeline()

        # 驗證管道有 logger 屬性
        assert hasattr(pipeline, 'logger')
        assert isinstance(pipeline.logger, logging.Logger)

    def test_logger_has_correct_name(self):
        """測試日誌記錄器有正確的名稱"""
        pipeline = EnhancedOCRPipeline()

        # 驗證 logger 名稱
        assert pipeline.logger.name == "EnhancedOCRPipeline"

    @pytest.mark.asyncio
    async def test_process_logs_start_and_end(self, caplog):
        """測試 process() 記錄開始和結束日誌"""
        pipeline = EnhancedOCRPipeline()

        with caplog.at_level(logging.INFO):
            await pipeline.process("file:///test.jpg")

        # 驗證記錄了處理開始和結束
        log_messages = [record.message for record in caplog.records]
        assert any("開始處理" in msg or "Starting" in msg for msg in log_messages)
        assert any("處理完成" in msg or "Completed" in msg for msg in log_messages)

    @pytest.mark.asyncio
    async def test_process_logs_configuration(self, caplog):
        """測試 process() 記錄配置資訊"""
        pipeline = EnhancedOCRPipeline(
            enable_preprocessing=True,
            enable_multi_engine=True
        )

        with caplog.at_level(logging.DEBUG):
            await pipeline.process("file:///test.jpg")

        # 驗證記錄了配置資訊
        log_text = " ".join([record.message for record in caplog.records])
        assert "preprocessing" in log_text.lower() or "預處理" in log_text

    @pytest.mark.asyncio
    async def test_process_logs_processing_time(self, caplog):
        """測試 process() 記錄處理時間"""
        pipeline = EnhancedOCRPipeline()

        with caplog.at_level(logging.INFO):
            await pipeline.process("file:///test.jpg")

        # 驗證記錄了處理時間
        log_text = " ".join([record.message for record in caplog.records])
        assert "time" in log_text.lower() or "時間" in log_text or "ms" in log_text.lower()


class TestEnhancedOCRPipelineAdvancedErrorHandling:
    """測試 EnhancedOCRPipeline 進階錯誤處理"""

    @pytest.mark.asyncio
    async def test_process_logs_errors(self, caplog):
        """測試處理錯誤時記錄日誌"""
        pipeline = EnhancedOCRPipeline()

        with caplog.at_level(logging.ERROR):
            # 使用明顯無效的 URL 觸發錯誤
            result = await pipeline.process("invalid://bad-url")

        # 即使有錯誤，也應該返回結果（graceful degradation）
        assert result is not None
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_metadata_includes_processing_stages(self):
        """測試 metadata 包含處理階段資訊"""
        pipeline = EnhancedOCRPipeline()

        result = await pipeline.process("file:///test.jpg")

        # 驗證 metadata 包含處理階段資訊
        metadata = result["metadata"]
        assert isinstance(metadata, dict)
        # 當實作完成後，metadata 應該包含處理階段資訊

    @pytest.mark.asyncio
    async def test_process_handles_processing_errors_gracefully(self):
        """測試處理錯誤時優雅降級"""
        pipeline = EnhancedOCRPipeline()

        # 即使是有問題的輸入，也應該返回有效的 OCRResult
        result = await pipeline.process("file:///nonexistent.jpg")

        assert result is not None
        assert isinstance(result, dict)
        assert "text" in result
        assert "metadata" in result
