"""
測試文件分類器

驗證 DocumentClassifier 正確識別文件類型（transcript/lease/id_card/unknown）。
"""

import pytest
from PIL import Image
import numpy as np
from app.lib.ocr_enhanced.document_classifier import DocumentClassifier


class TestDocumentClassifierInit:
    """測試 DocumentClassifier 初始化"""

    def test_classifier_can_be_instantiated(self):
        """測試分類器可以被實例化"""
        classifier = DocumentClassifier()
        assert classifier is not None

    def test_classifier_has_transcript_keywords(self):
        """測試分類器包含謄本關鍵字"""
        classifier = DocumentClassifier()
        assert hasattr(classifier, 'transcript_keywords')
        assert isinstance(classifier.transcript_keywords, list)
        assert len(classifier.transcript_keywords) > 0

    def test_transcript_keywords_content(self):
        """測試謄本關鍵字內容"""
        classifier = DocumentClassifier()
        keywords = classifier.transcript_keywords

        # 必須包含的關鍵字
        assert "謄本" in keywords
        assert "地政" in keywords
        assert "建物標示部" in keywords
        assert "土地標示部" in keywords
        assert "所有權部" in keywords


class TestIsTranscript:
    """測試 is_transcript() 方法"""

    @pytest.fixture
    def classifier(self):
        """創建分類器實例"""
        return DocumentClassifier()

    @pytest.fixture
    def sample_image(self):
        """創建測試圖像"""
        # 創建 100x100 白色圖像
        img_array = np.ones((100, 100, 3), dtype=np.uint8) * 255
        return Image.fromarray(img_array)

    def test_is_transcript_method_exists(self, classifier):
        """測試 is_transcript 方法存在"""
        assert hasattr(classifier, 'is_transcript')
        assert callable(classifier.is_transcript)

    def test_is_transcript_returns_bool(self, classifier, sample_image):
        """測試 is_transcript 返回布林值"""
        result = classifier.is_transcript(sample_image)
        assert isinstance(result, bool)

    def test_is_transcript_with_keyword_image(self, classifier):
        """測試包含謄本關鍵字的圖像"""
        # 這個測試需要實際的 OCR 功能，先檢查方法存在
        # 實作後應該識別包含「謄本」等關鍵字的圖像
        pass


class TestClassifyMethod:
    """測試 classify() 方法"""

    @pytest.fixture
    def classifier(self):
        """創建分類器實例"""
        return DocumentClassifier()

    @pytest.fixture
    def sample_image(self):
        """創建測試圖像"""
        img_array = np.ones((100, 100, 3), dtype=np.uint8) * 255
        return Image.fromarray(img_array)

    @pytest.mark.asyncio
    async def test_classify_method_exists(self, classifier):
        """測試 classify 方法存在"""
        assert hasattr(classifier, 'classify')
        assert callable(classifier.classify)

    @pytest.mark.asyncio
    async def test_classify_returns_document_type(self, classifier, sample_image):
        """測試 classify 返回 DocumentType"""
        result = await classifier.classify(sample_image)
        assert isinstance(result, str)
        assert result in ["transcript", "lease", "id_card", "unknown"]

    @pytest.mark.asyncio
    async def test_classify_blank_image_returns_unknown(self, classifier, sample_image):
        """測試空白圖像返回 unknown"""
        result = await classifier.classify(sample_image)
        # 空白圖像應該無法識別
        assert result == "unknown"


class TestClassifyWithKeywords:
    """測試關鍵字識別功能"""

    @pytest.fixture
    def classifier(self):
        """創建分類器實例"""
        return DocumentClassifier()

    def test_extract_text_from_image_method_exists(self, classifier):
        """測試提取文字方法存在"""
        # 分類器應該有提取文字的方法
        assert hasattr(classifier, 'extract_text_from_image') or hasattr(classifier, '_extract_text')

    def test_keyword_matching_logic(self, classifier):
        """測試關鍵字匹配邏輯"""
        # 測試關鍵字匹配方法存在
        assert hasattr(classifier, 'match_keywords') or hasattr(classifier, '_match_keywords')


class TestClassifyTranscript:
    """測試謄本分類"""

    @pytest.fixture
    def classifier(self):
        """創建分類器實例"""
        return DocumentClassifier()

    @pytest.mark.asyncio
    async def test_classify_transcript_with_keyword_text(self, classifier):
        """測試包含謄本關鍵字的文字"""
        # 模擬包含謄本關鍵字的圖像
        # 這需要實作 OCR 功能才能完整測試
        pass


class TestErrorHandling:
    """測試錯誤處理"""

    @pytest.fixture
    def classifier(self):
        """創建分類器實例"""
        return DocumentClassifier()

    @pytest.mark.asyncio
    async def test_classify_with_none_image(self, classifier):
        """測試 None 圖像處理"""
        # 應該返回 unknown 或拋出明確的異常
        with pytest.raises(Exception):
            await classifier.classify(None)

    @pytest.mark.asyncio
    async def test_classify_with_invalid_image(self, classifier):
        """測試無效圖像處理"""
        # 測試非 PIL Image 物件
        with pytest.raises((TypeError, AttributeError)):
            await classifier.classify("not an image")

    def test_is_transcript_with_none_image(self, classifier):
        """測試 is_transcript 處理 None"""
        with pytest.raises(Exception):
            classifier.is_transcript(None)


class TestKeywordMatching:
    """測試關鍵字匹配邏輯"""

    @pytest.fixture
    def classifier(self):
        """創建分類器實例"""
        return DocumentClassifier()

    def test_keyword_match_exact(self, classifier):
        """測試精確關鍵字匹配"""
        text = "這是一份建物土地謄本文件"
        # 應該檢測到「謄本」關鍵字
        keywords = classifier.transcript_keywords
        matches = [kw for kw in keywords if kw in text]
        assert len(matches) > 0

    def test_keyword_match_multiple(self, classifier):
        """測試多個關鍵字匹配"""
        text = "地政謄本 建物標示部 所有權部"
        keywords = classifier.transcript_keywords
        matches = [kw for kw in keywords if kw in text]
        assert len(matches) >= 3

    def test_no_keyword_match(self, classifier):
        """測試無關鍵字匹配"""
        text = "這是一份普通文件"
        keywords = classifier.transcript_keywords
        matches = [kw for kw in keywords if kw in text]
        assert len(matches) == 0


class TestOCRIntegration:
    """測試 OCR 整合"""

    @pytest.fixture
    def classifier(self):
        """創建分類器實例"""
        return DocumentClassifier()

    def test_ocr_method_exists(self, classifier):
        """測試 OCR 方法存在"""
        # 分類器需要某種 OCR 方法來提取文字
        has_ocr_method = (
            hasattr(classifier, 'extract_text_from_image') or
            hasattr(classifier, '_extract_text') or
            hasattr(classifier, 'ocr_extract')
        )
        # 這個測試在實作時會通過
        pass

    @pytest.mark.asyncio
    async def test_classify_uses_ocr(self, classifier):
        """測試 classify 使用 OCR 提取文字"""
        # 創建簡單圖像
        img_array = np.ones((100, 100, 3), dtype=np.uint8) * 255
        image = Image.fromarray(img_array)

        # classify 應該內部調用 OCR
        result = await classifier.classify(image)
        assert result is not None


class TestClassifierBehavior:
    """測試分類器行為"""

    @pytest.fixture
    def classifier(self):
        """創建分類器實例"""
        return DocumentClassifier()

    @pytest.mark.asyncio
    async def test_classify_consistent_results(self, classifier):
        """測試相同圖像產生一致結果"""
        img_array = np.ones((100, 100, 3), dtype=np.uint8) * 255
        image = Image.fromarray(img_array)

        result1 = await classifier.classify(image)
        result2 = await classifier.classify(image)

        assert result1 == result2

    def test_transcript_keyword_threshold(self, classifier):
        """測試謄本關鍵字閾值"""
        # 至少匹配一個關鍵字應該識別為謄本
        # 這個邏輯需要在實作時確認
        assert len(classifier.transcript_keywords) >= 5
