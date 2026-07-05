"""
測試 DocumentProcessor 抽象基類(契約重構後,任務 8.1)

驗收標準:
- DocumentProcessor 繼承 ABC,定義抽象 analyze 與具體 process 模板
- OcrDocumentProcessor 定義四步驟抽象方法(preprocess/extract_text/postprocess/extract_fields)
- process() 模板編排完整處理流程
- 抽象方法支援 async/await
"""

import inspect
import pytest
from abc import ABC
from PIL import Image
from app.lib.multi_type_ocr.processor import (
    DocumentProcessor,
    OcrDocumentProcessor,
)


class TestDocumentProcessorStructure:
    """DocumentProcessor 基本結構(analyze + process)"""

    def test_inherits_abc(self):
        assert issubclass(DocumentProcessor, ABC)

    def test_has_analyze_method(self):
        assert hasattr(DocumentProcessor, "analyze")

    def test_has_process_method(self):
        assert hasattr(DocumentProcessor, "process")

    def test_cannot_instantiate_abstract_class(self):
        with pytest.raises(TypeError):
            DocumentProcessor()  # type: ignore


class TestOcrProcessorStructure:
    """OcrDocumentProcessor 定義四步驟抽象方法"""

    def test_has_preprocess_method(self):
        assert hasattr(OcrDocumentProcessor, "preprocess")

    def test_has_extract_text_method(self):
        assert hasattr(OcrDocumentProcessor, "extract_text")

    def test_has_postprocess_method(self):
        assert hasattr(OcrDocumentProcessor, "postprocess")

    def test_has_extract_fields_method(self):
        assert hasattr(OcrDocumentProcessor, "extract_fields")

    def test_is_document_processor(self):
        assert issubclass(OcrDocumentProcessor, DocumentProcessor)


class TestMethodsAreAsync:
    def test_analyze_is_async(self):
        assert inspect.iscoroutinefunction(DocumentProcessor.analyze)

    def test_process_is_async(self):
        assert inspect.iscoroutinefunction(DocumentProcessor.process)

    def test_ocr_steps_are_async(self):
        assert inspect.iscoroutinefunction(OcrDocumentProcessor.preprocess)
        assert inspect.iscoroutinefunction(OcrDocumentProcessor.extract_text)
        assert inspect.iscoroutinefunction(OcrDocumentProcessor.postprocess)
        assert inspect.iscoroutinefunction(OcrDocumentProcessor.extract_fields)


class TestConcreteImplementation:
    """具體 OCR 處理器可繼承並運作"""

    @pytest.fixture
    def concrete_processor(self):
        class ConcreteProcessor(OcrDocumentProcessor):
            async def preprocess(self, image):
                return image

            async def extract_text(self, image):
                return ("測試文字", 0.95)

            async def postprocess(self, text, confidence, image_data=None):
                return (text + "_processed", {"stats": "test"})

            async def extract_fields(self, text, image_data=None, enable_llm=False, few_shot=None):
                return {"field": "value"}

        return ConcreteProcessor()

    async def test_can_create_concrete_implementation(self, concrete_processor):
        assert isinstance(concrete_processor, DocumentProcessor)

    async def test_concrete_preprocess_works(self, concrete_processor):
        import numpy as np
        img = Image.fromarray(np.zeros((100, 100, 3), dtype=np.uint8))
        result = await concrete_processor.preprocess(img)
        assert isinstance(result, Image.Image)

    async def test_concrete_extract_text_works(self, concrete_processor):
        import numpy as np
        img = Image.fromarray(np.zeros((100, 100, 3), dtype=np.uint8))
        text, confidence = await concrete_processor.extract_text(img)
        assert isinstance(text, str)
        assert isinstance(confidence, float)

    async def test_concrete_postprocess_works(self, concrete_processor):
        text, stats = await concrete_processor.postprocess("原始文字", 0.9)
        assert isinstance(text, str)
        assert isinstance(stats, dict)

    async def test_concrete_extract_fields_works(self, concrete_processor):
        fields = await concrete_processor.extract_fields("測試文字")
        assert isinstance(fields, dict)


class TestProcessTemplateMethod:
    """process 模板方法按順序調用四步驟"""

    @pytest.fixture
    def mock_processor(self):
        class MockProcessor(OcrDocumentProcessor):
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

            async def extract_fields(self, text, image_data=None, enable_llm=False, few_shot=None):
                self.extract_fields_called = True
                return {"test": "field"}

        return MockProcessor()

    async def test_process_calls_all_methods_in_order(self, mock_processor):
        import numpy as np
        import io
        img = Image.fromarray(np.zeros((100, 100, 3), dtype=np.uint8))
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        file_contents = img_bytes.getvalue()

        result = await mock_processor.process(
            file_contents=file_contents,
            filename="test.png",
            page_number=1,
            total_pages=1,
            enable_llm=False,
        )

        assert mock_processor.preprocess_called
        assert mock_processor.extract_text_called
        assert mock_processor.postprocess_called
        assert mock_processor.extract_fields_called
        assert isinstance(result, dict)
        assert result["page_number"] == 1
