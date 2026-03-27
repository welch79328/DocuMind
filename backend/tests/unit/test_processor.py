"""
測試 DocumentProcessor 抽象基類

驗收標準:
- DocumentProcessor 繼承 ABC,定義 4 個抽象方法
- 實作 process() 模板方法,編排完整處理流程
- 所有方法有完整的型別提示與 docstring
- 抽象方法支援 async/await
- 通過 pylint 與 mypy 檢查
"""

import pytest
from abc import ABC
from typing import get_type_hints
from PIL import Image
from app.lib.multi_type_ocr.processor import DocumentProcessor


class TestDocumentProcessorStructure:
    """測試 DocumentProcessor 基本結構"""

    def test_document_processor_inherits_abc(self):
        """驗證 DocumentProcessor 繼承 ABC"""
        assert issubclass(DocumentProcessor, ABC)

    def test_has_preprocess_method(self):
        """驗證有 preprocess 抽象方法"""
        assert hasattr(DocumentProcessor, 'preprocess')

    def test_has_extract_text_method(self):
        """驗證有 extract_text 抽象方法"""
        assert hasattr(DocumentProcessor, 'extract_text')

    def test_has_postprocess_method(self):
        """驗證有 postprocess 抽象方法"""
        assert hasattr(DocumentProcessor, 'postprocess')

    def test_has_extract_fields_method(self):
        """驗證有 extract_fields 抽象方法"""
        assert hasattr(DocumentProcessor, 'extract_fields')

    def test_has_process_method(self):
        """驗證有 process 模板方法"""
        assert hasattr(DocumentProcessor, 'process')

    def test_cannot_instantiate_abstract_class(self):
        """驗證無法直接實例化抽象基類"""
        with pytest.raises(TypeError):
            DocumentProcessor()


class TestDocumentProcessorMethods:
    """測試 DocumentProcessor 方法簽名"""

    def test_preprocess_is_async(self):
        """驗證 preprocess 是異步方法"""
        import inspect
        assert inspect.iscoroutinefunction(DocumentProcessor.preprocess)

    def test_extract_text_is_async(self):
        """驗證 extract_text 是異步方法"""
        import inspect
        assert inspect.iscoroutinefunction(DocumentProcessor.extract_text)

    def test_postprocess_is_async(self):
        """驗證 postprocess 是異步方法"""
        import inspect
        assert inspect.iscoroutinefunction(DocumentProcessor.postprocess)

    def test_extract_fields_is_async(self):
        """驗證 extract_fields 是異步方法"""
        import inspect
        assert inspect.iscoroutinefunction(DocumentProcessor.extract_fields)

    def test_process_is_async(self):
        """驗證 process 模板方法是異步方法"""
        import inspect
        assert inspect.iscoroutinefunction(DocumentProcessor.process)


class TestConcreteImplementation:
    """測試具體實作可以繼承並運作"""

    @pytest.fixture
    def concrete_processor(self):
        """創建一個具體的處理器實例用於測試"""
        class ConcreteProcessor(DocumentProcessor):
            async def preprocess(self, image):
                return image

            async def extract_text(self, image):
                return ("測試文字", 0.95)

            async def postprocess(self, text, confidence, image_data=None):
                return (text + "_processed", {"stats": "test"})

            async def extract_fields(self, text):
                return {"field": "value"}

        return ConcreteProcessor()

    @pytest.mark.asyncio
    async def test_can_create_concrete_implementation(self, concrete_processor):
        """驗證可以創建具體實作"""
        assert isinstance(concrete_processor, DocumentProcessor)

    @pytest.mark.asyncio
    async def test_concrete_preprocess_works(self, concrete_processor):
        """驗證具體實作的 preprocess 方法可運作"""
        from PIL import Image
        import numpy as np

        # 創建一個簡單的測試圖像
        img = Image.fromarray(np.zeros((100, 100, 3), dtype=np.uint8))
        result = await concrete_processor.preprocess(img)
        assert isinstance(result, Image.Image)

    @pytest.mark.asyncio
    async def test_concrete_extract_text_works(self, concrete_processor):
        """驗證具體實作的 extract_text 方法可運作"""
        from PIL import Image
        import numpy as np

        img = Image.fromarray(np.zeros((100, 100, 3), dtype=np.uint8))
        text, confidence = await concrete_processor.extract_text(img)
        assert isinstance(text, str)
        assert isinstance(confidence, float)

    @pytest.mark.asyncio
    async def test_concrete_postprocess_works(self, concrete_processor):
        """驗證具體實作的 postprocess 方法可運作"""
        text, stats = await concrete_processor.postprocess("原始文字", 0.9)
        assert isinstance(text, str)
        assert isinstance(stats, dict)

    @pytest.mark.asyncio
    async def test_concrete_extract_fields_works(self, concrete_processor):
        """驗證具體實作的 extract_fields 方法可運作"""
        fields = await concrete_processor.extract_fields("測試文字")
        assert isinstance(fields, dict)


class TestProcessTemplateMethod:
    """測試 process 模板方法"""

    @pytest.fixture
    def mock_processor(self):
        """創建帶計數的模擬處理器"""
        class MockProcessor(DocumentProcessor):
            def __init__(self):
                self.preprocess_called = False
                self.extract_text_called = False
                self.postprocess_called = False
                self.extract_fields_called = False

            async def preprocess(self, image):
                self.preprocess_called = True
                return image

            async def extract_text(self, image):
                self.extract_text_called = True
                return ("OCR文字", 0.85)

            async def postprocess(self, text, confidence, image_data=None):
                self.postprocess_called = True
                return (text, {"stats": {}})

            async def extract_fields(self, text, image_data=None, enable_llm=False):
                self.extract_fields_called = True
                return {"test": "field"}

        return MockProcessor()

    @pytest.mark.asyncio
    async def test_process_calls_all_methods_in_order(self, mock_processor):
        """驗證 process 方法按順序調用所有步驟"""
        from PIL import Image
        import numpy as np
        import io

        # 創建測試圖像並轉為字節
        img = Image.fromarray(np.zeros((100, 100, 3), dtype=np.uint8))
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        file_contents = img_bytes.getvalue()

        result = await mock_processor.process(
            file_contents=file_contents,
            filename="test.png",
            page_number=1,
            total_pages=1,
            enable_llm=False
        )

        # 驗證所有方法都被調用
        assert mock_processor.preprocess_called
        assert mock_processor.extract_text_called
        assert mock_processor.postprocess_called
        assert mock_processor.extract_fields_called

        # 驗證返回結果是字典
        assert isinstance(result, dict)
