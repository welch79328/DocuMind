"""
測試 ProcessorFactory 工廠類別

驗收標準:
- 實作 get_processor(document_type: str) 類別方法
- 實作 register_processor() 方法支援動態註冊
- 實作 supported_types() 方法返回支援的類型列表
- 不支援的類型拋出 ValueError,錯誤訊息使用繁體中文並列出支援類型
- 錯誤訊息格式: "不支援的文件類型: {type}。支援的類型: {supported}"
"""

import pytest
from app.lib.multi_type_ocr.processor_factory import ProcessorFactory
from app.lib.multi_type_ocr.processor import DocumentProcessor
from PIL import Image
from typing import Dict, Any, Optional


class TestProcessorFactoryStructure:
    """測試 ProcessorFactory 基本結構"""

    def test_processor_factory_has_get_processor(self):
        """驗證有 get_processor 類別方法"""
        assert hasattr(ProcessorFactory, 'get_processor')
        assert callable(ProcessorFactory.get_processor)

    def test_processor_factory_has_register_processor(self):
        """驗證有 register_processor 類別方法"""
        assert hasattr(ProcessorFactory, 'register_processor')
        assert callable(ProcessorFactory.register_processor)

    def test_processor_factory_has_supported_types(self):
        """驗證有 supported_types 類別方法"""
        assert hasattr(ProcessorFactory, 'supported_types')
        assert callable(ProcessorFactory.supported_types)

    def test_processor_factory_has_processors_dict(self):
        """驗證有 _processors 類別屬性"""
        assert hasattr(ProcessorFactory, '_processors')
        assert isinstance(ProcessorFactory._processors, dict)


class TestGetProcessor:
    """測試 get_processor 方法"""

    @pytest.fixture(autouse=True)
    def setup_test_processors(self):
        """每個測試前設置測試用處理器"""
        # 創建測試用處理器類別
        class TestProcessor(DocumentProcessor):
            async def preprocess(self, image):
                return image

            async def extract_text(self, image):
                return ("test", 0.9)

            async def postprocess(self, text, confidence, image_data=None):
                return (text, {})

            async def extract_fields(self, text):
                return {}

        # 保存原始 _processors 字典
        self.original_processors = ProcessorFactory._processors.copy()

        # 註冊測試處理器
        ProcessorFactory._processors = {
            "test_type": TestProcessor,
        }

        yield

        # 恢復原始 _processors
        ProcessorFactory._processors = self.original_processors

    def test_get_processor_returns_correct_instance(self):
        """驗證 get_processor 返回正確的處理器實例"""
        processor = ProcessorFactory.get_processor("test_type")
        assert isinstance(processor, DocumentProcessor)

    def test_get_processor_returns_different_instances(self):
        """驗證每次調用返回新的實例"""
        processor1 = ProcessorFactory.get_processor("test_type")
        processor2 = ProcessorFactory.get_processor("test_type")
        assert processor1 is not processor2

    def test_get_processor_unsupported_type_raises_value_error(self):
        """驗證不支援的類型拋出 ValueError"""
        with pytest.raises(ValueError):
            ProcessorFactory.get_processor("unsupported_type")

    def test_get_processor_error_message_format(self):
        """驗證錯誤訊息格式正確"""
        with pytest.raises(ValueError) as exc_info:
            ProcessorFactory.get_processor("invoice")

        error_message = str(exc_info.value)
        assert "不支援的文件類型: invoice" in error_message
        assert "支援的類型:" in error_message

    def test_get_processor_error_message_lists_supported_types(self):
        """驗證錯誤訊息列出所有支援的類型"""
        with pytest.raises(ValueError) as exc_info:
            ProcessorFactory.get_processor("invoice")

        error_message = str(exc_info.value)
        assert "test_type" in error_message


class TestRegisterProcessor:
    """測試 register_processor 方法"""

    @pytest.fixture(autouse=True)
    def setup_clean_factory(self):
        """每個測試前清理工廠狀態"""
        # 保存原始 _processors 字典
        self.original_processors = ProcessorFactory._processors.copy()

        yield

        # 恢復原始 _processors
        ProcessorFactory._processors = self.original_processors

    def test_register_processor_adds_new_type(self):
        """驗證 register_processor 能註冊新類型"""
        class NewProcessor(DocumentProcessor):
            async def preprocess(self, image):
                return image

            async def extract_text(self, image):
                return ("", 0.0)

            async def postprocess(self, text, confidence, image_data=None):
                return (text, {})

            async def extract_fields(self, text):
                return {}

        ProcessorFactory.register_processor("new_type", NewProcessor)
        assert "new_type" in ProcessorFactory._processors
        assert ProcessorFactory._processors["new_type"] == NewProcessor

    def test_register_processor_allows_retrieval(self):
        """驗證註冊後可以通過 get_processor 取得"""
        class CustomProcessor(DocumentProcessor):
            async def preprocess(self, image):
                return image

            async def extract_text(self, image):
                return ("custom", 0.85)

            async def postprocess(self, text, confidence, image_data=None):
                return (text, {})

            async def extract_fields(self, text):
                return {}

        ProcessorFactory.register_processor("custom", CustomProcessor)
        processor = ProcessorFactory.get_processor("custom")
        assert isinstance(processor, CustomProcessor)

    def test_register_processor_overwrites_existing(self):
        """驗證 register_processor 可以覆蓋既有類型"""
        class OriginalProcessor(DocumentProcessor):
            async def preprocess(self, image):
                return image

            async def extract_text(self, image):
                return ("original", 0.9)

            async def postprocess(self, text, confidence, image_data=None):
                return (text, {})

            async def extract_fields(self, text):
                return {}

        class ReplacementProcessor(DocumentProcessor):
            async def preprocess(self, image):
                return image

            async def extract_text(self, image):
                return ("replacement", 0.95)

            async def postprocess(self, text, confidence, image_data=None):
                return (text, {})

            async def extract_fields(self, text):
                return {}

        ProcessorFactory.register_processor("test", OriginalProcessor)
        ProcessorFactory.register_processor("test", ReplacementProcessor)

        processor = ProcessorFactory.get_processor("test")
        assert isinstance(processor, ReplacementProcessor)


class TestSupportedTypes:
    """測試 supported_types 方法"""

    @pytest.fixture(autouse=True)
    def setup_known_processors(self):
        """設置已知的處理器集合"""
        class ProcessorA(DocumentProcessor):
            async def preprocess(self, image):
                return image

            async def extract_text(self, image):
                return ("", 0.0)

            async def postprocess(self, text, confidence, image_data=None):
                return (text, {})

            async def extract_fields(self, text):
                return {}

        class ProcessorB(DocumentProcessor):
            async def preprocess(self, image):
                return image

            async def extract_text(self, image):
                return ("", 0.0)

            async def postprocess(self, text, confidence, image_data=None):
                return (text, {})

            async def extract_fields(self, text):
                return {}

        # 保存原始 _processors 字典
        self.original_processors = ProcessorFactory._processors.copy()

        ProcessorFactory._processors = {
            "type_a": ProcessorA,
            "type_b": ProcessorB,
        }

        yield

        # 恢復原始 _processors
        ProcessorFactory._processors = self.original_processors

    def test_supported_types_returns_list(self):
        """驗證 supported_types 返回列表"""
        types = ProcessorFactory.supported_types()
        assert isinstance(types, list)

    def test_supported_types_contains_registered_types(self):
        """驗證 supported_types 包含所有註冊的類型"""
        types = ProcessorFactory.supported_types()
        assert "type_a" in types
        assert "type_b" in types

    def test_supported_types_count(self):
        """驗證 supported_types 返回正確數量"""
        types = ProcessorFactory.supported_types()
        assert len(types) == 2

    def test_supported_types_updates_after_registration(self):
        """驗證註冊新類型後 supported_types 更新"""
        class NewProcessor(DocumentProcessor):
            async def preprocess(self, image):
                return image

            async def extract_text(self, image):
                return ("", 0.0)

            async def postprocess(self, text, confidence, image_data=None):
                return (text, {})

            async def extract_fields(self, text):
                return {}

        initial_types = ProcessorFactory.supported_types()
        assert "new_type" not in initial_types

        ProcessorFactory.register_processor("new_type", NewProcessor)

        updated_types = ProcessorFactory.supported_types()
        assert "new_type" in updated_types
        assert len(updated_types) == len(initial_types) + 1


class TestRealProcessors:
    """測試真實的處理器類型（驗收標準 3.2）"""

    def test_get_processor_transcript_returns_transcript_processor(self):
        """驗證 get_processor("transcript") 返回 TranscriptProcessor"""
        from app.lib.multi_type_ocr.transcript_processor import TranscriptProcessor

        processor = ProcessorFactory.get_processor("transcript")
        assert isinstance(processor, TranscriptProcessor)

    def test_get_processor_contract_returns_contract_processor(self):
        """驗證 get_processor("contract") 返回 ContractProcessor"""
        from app.lib.multi_type_ocr.contract_processor import ContractProcessor

        processor = ProcessorFactory.get_processor("contract")
        assert isinstance(processor, ContractProcessor)

    def test_supported_types_includes_transcript_and_contract(self):
        """驗證 supported_types() 包含 transcript 和 contract"""
        types = ProcessorFactory.supported_types()

        assert "transcript" in types
        assert "contract" in types
        assert len(types) >= 2
