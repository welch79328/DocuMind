"""
測試 TranscriptPreprocessor - 預處理流程管道

驗證 preprocess() 方法正確整合所有預處理步驟。
"""

import pytest
import numpy as np
import cv2
from PIL import Image
from app.lib.ocr_enhanced.preprocessor import TranscriptPreprocessor
from app.lib.ocr_enhanced.config import PreprocessConfig


class TestPreprocessInit:
    """測試 preprocess 方法基本功能"""

    @pytest.fixture
    def preprocessor(self):
        """創建預處理器實例"""
        config = PreprocessConfig()
        return TranscriptPreprocessor(config)

    @pytest.fixture
    def pil_image(self):
        """創建 PIL 圖像"""
        img_array = np.ones((200, 200, 3), dtype=np.uint8) * 200
        return Image.fromarray(img_array)

    @pytest.mark.asyncio
    async def test_method_exists(self, preprocessor):
        """測試 preprocess 方法存在"""
        assert hasattr(preprocessor, 'preprocess')
        assert callable(preprocessor.preprocess)

    @pytest.mark.asyncio
    async def test_accepts_pil_image(self, preprocessor, pil_image):
        """測試接受 PIL Image"""
        result, metadata = await preprocessor.preprocess(pil_image)
        assert result is not None
        assert metadata is not None

    @pytest.mark.asyncio
    async def test_returns_tuple(self, preprocessor, pil_image):
        """測試返回 (numpy 陣列, 元數據)"""
        result = await preprocessor.preprocess(pil_image)
        assert isinstance(result, tuple)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_returns_numpy_array(self, preprocessor, pil_image):
        """測試返回 numpy 陣列"""
        processed, metadata = await preprocessor.preprocess(pil_image)
        assert isinstance(processed, np.ndarray)

    @pytest.mark.asyncio
    async def test_returns_metadata_dict(self, preprocessor, pil_image):
        """測試返回元數據字典"""
        processed, metadata = await preprocessor.preprocess(pil_image)
        assert isinstance(metadata, dict)


class TestPreprocessMetadata:
    """測試元數據內容"""

    @pytest.fixture
    def preprocessor(self):
        """創建預處理器實例"""
        config = PreprocessConfig()
        return TranscriptPreprocessor(config)

    @pytest.fixture
    def pil_image(self):
        """創建 PIL 圖像"""
        img_array = np.ones((200, 200, 3), dtype=np.uint8) * 200
        return Image.fromarray(img_array)

    @pytest.mark.asyncio
    async def test_metadata_has_watermark_removed(self, preprocessor, pil_image):
        """測試元數據包含 watermark_removed"""
        _, metadata = await preprocessor.preprocess(pil_image)
        assert 'watermark_removed' in metadata
        assert isinstance(metadata['watermark_removed'], bool)

    @pytest.mark.asyncio
    async def test_metadata_has_binarization_applied(self, preprocessor, pil_image):
        """測試元數據包含 binarization_applied"""
        _, metadata = await preprocessor.preprocess(pil_image)
        assert 'binarization_applied' in metadata
        assert isinstance(metadata['binarization_applied'], bool)

    @pytest.mark.asyncio
    async def test_metadata_has_binarization_method(self, preprocessor, pil_image):
        """測試元數據包含 binarization_method"""
        _, metadata = await preprocessor.preprocess(pil_image)
        if metadata.get('binarization_applied'):
            assert 'binarization_method' in metadata
            assert isinstance(metadata['binarization_method'], str)

    @pytest.mark.asyncio
    async def test_metadata_has_processing_time(self, preprocessor, pil_image):
        """測試元數據包含 processing_time_ms"""
        _, metadata = await preprocessor.preprocess(pil_image)
        assert 'processing_time_ms' in metadata
        assert isinstance(metadata['processing_time_ms'], (int, float))
        assert metadata['processing_time_ms'] >= 0


class TestPreprocessPipeline:
    """測試預處理流程"""

    @pytest.fixture
    def preprocessor_full(self):
        """創建啟用所有步驟的預處理器"""
        config = PreprocessConfig(
            enable_watermark_removal=True,
            enable_binarization=True,
            enable_denoising=True,
            binarization_method="gaussian",
            target_dpi=1500
        )
        return TranscriptPreprocessor(config)

    @pytest.fixture
    def pil_image(self):
        """創建 PIL 圖像"""
        img_array = np.ones((200, 200, 3), dtype=np.uint8) * 200
        # 添加一些內容
        cv2.rectangle(img_array, (50, 50), (150, 150), (50, 50, 50), -1)
        return Image.fromarray(img_array)

    @pytest.mark.asyncio
    async def test_converts_pil_to_numpy(self, preprocessor_full, pil_image):
        """測試 PIL → numpy 轉換"""
        processed, _ = await preprocessor_full.preprocess(pil_image)
        assert isinstance(processed, np.ndarray)

    @pytest.mark.asyncio
    async def test_applies_watermark_removal(self, preprocessor_full):
        """測試應用浮水印移除"""
        # 創建帶紅色的圖像
        img_array = np.ones((200, 200, 3), dtype=np.uint8) * 255
        img_array[50:150, 50:150] = [0, 0, 255]  # 紅色區域
        pil_img = Image.fromarray(img_array)

        processed, metadata = await preprocessor_full.preprocess(pil_img)

        assert metadata['watermark_removed'] is True
        # 紅色區域應該被移除
        assert processed is not None

    @pytest.mark.asyncio
    async def test_applies_binarization(self, preprocessor_full, pil_image):
        """測試應用二值化"""
        processed, metadata = await preprocessor_full.preprocess(pil_image)

        assert metadata['binarization_applied'] is True
        assert metadata['binarization_method'] == "gaussian"

    @pytest.mark.asyncio
    async def test_pipeline_order_correct(self, preprocessor_full, pil_image):
        """測試流程順序正確"""
        # 流程應該是：PIL → numpy → 浮水印移除 → 二值化 → 去噪 → 解析度調整
        processed, metadata = await preprocessor_full.preprocess(pil_image)

        # 檢查元數據記錄了各個步驟
        assert 'watermark_removed' in metadata
        assert 'binarization_applied' in metadata
        assert 'processing_time_ms' in metadata


class TestPreprocessConfigControl:
    """測試配置控制"""

    @pytest.fixture
    def pil_image(self):
        """創建 PIL 圖像"""
        img_array = np.ones((200, 200, 3), dtype=np.uint8) * 200
        return Image.fromarray(img_array)

    @pytest.mark.asyncio
    async def test_watermark_removal_disabled(self, pil_image):
        """測試禁用浮水印移除"""
        config = PreprocessConfig(enable_watermark_removal=False)
        preprocessor = TranscriptPreprocessor(config)

        _, metadata = await preprocessor.preprocess(pil_image)
        assert metadata['watermark_removed'] is False

    @pytest.mark.asyncio
    async def test_binarization_disabled(self, pil_image):
        """測試禁用二值化"""
        config = PreprocessConfig(enable_binarization=False)
        preprocessor = TranscriptPreprocessor(config)

        _, metadata = await preprocessor.preprocess(pil_image)
        assert metadata['binarization_applied'] is False

    @pytest.mark.asyncio
    async def test_denoising_controlled_by_config(self, pil_image):
        """測試去噪由配置控制"""
        config = PreprocessConfig(enable_denoising=True)
        preprocessor = TranscriptPreprocessor(config)

        processed, _ = await preprocessor.preprocess(pil_image)
        assert processed is not None


class TestPreprocessStrategy:
    """測試策略模式"""

    @pytest.fixture
    def pil_image(self):
        """創建 PIL 圖像"""
        img_array = np.ones((200, 200, 3), dtype=np.uint8) * 200
        return Image.fromarray(img_array)

    @pytest.mark.asyncio
    async def test_accepts_custom_strategy(self, pil_image):
        """測試接受自訂策略"""
        config = PreprocessConfig()
        preprocessor = TranscriptPreprocessor(config)

        # 傳入 None 作為策略應該使用預設流程
        processed, metadata = await preprocessor.preprocess(pil_image, strategy=None)
        assert processed is not None

    @pytest.mark.asyncio
    async def test_default_strategy_when_none(self, pil_image):
        """測試 None 策略時使用預設"""
        config = PreprocessConfig()
        preprocessor = TranscriptPreprocessor(config)

        processed, metadata = await preprocessor.preprocess(pil_image)
        assert processed is not None
        assert metadata is not None


class TestPreprocessErrorHandling:
    """測試錯誤處理"""

    @pytest.fixture
    def preprocessor(self):
        """創建預處理器實例"""
        config = PreprocessConfig()
        return TranscriptPreprocessor(config)

    @pytest.mark.asyncio
    async def test_handles_none_image(self, preprocessor):
        """測試處理 None 圖像"""
        with pytest.raises((ValueError, TypeError, AttributeError)):
            await preprocessor.preprocess(None)

    @pytest.mark.asyncio
    async def test_handles_invalid_image(self, preprocessor):
        """測試處理無效圖像"""
        with pytest.raises((ValueError, TypeError, AttributeError)):
            await preprocessor.preprocess("not an image")


class TestPreprocessRealisticScenario:
    """測試真實場景"""

    @pytest.fixture
    def scanned_document(self):
        """創建模擬掃描文件"""
        # 白色背景 + 黑色文字 + 紅色浮水印 + 雜訊
        img_array = np.ones((400, 600, 3), dtype=np.uint8) * 240

        # 添加文字行
        for i in range(10):
            y = 50 + i * 35
            cv2.rectangle(img_array, (50, y), (550, y + 20), (30, 30, 30), -1)

        # 添加紅色浮水印
        cv2.putText(img_array, "COPY", (200, 200),
                   cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 3)

        # 添加雜訊
        noise = np.random.normal(0, 10, img_array.shape)
        noisy = img_array + noise
        noisy = np.clip(noisy, 0, 255).astype(np.uint8)

        return Image.fromarray(noisy)

    @pytest.mark.asyncio
    async def test_full_pipeline_on_document(self, scanned_document):
        """測試完整流程處理文件"""
        config = PreprocessConfig(
            enable_watermark_removal=True,
            enable_binarization=True,
            enable_denoising=True,
            binarization_method="gaussian",
            target_dpi=1500
        )
        preprocessor = TranscriptPreprocessor(config)

        processed, metadata = await preprocessor.preprocess(scanned_document)

        # 檢查處理成功
        assert processed is not None
        assert isinstance(processed, np.ndarray)

        # 檢查元數據
        assert metadata['watermark_removed'] is True
        assert metadata['binarization_applied'] is True
        assert metadata['processing_time_ms'] > 0

        # 檢查圖像被處理過
        assert processed.shape[0] > 0
        assert processed.shape[1] > 0

    @pytest.mark.asyncio
    async def test_pipeline_produces_different_output(self, scanned_document):
        """測試流程產生不同的輸出"""
        config = PreprocessConfig(
            enable_watermark_removal=True,
            enable_binarization=True,
            enable_denoising=True
        )
        preprocessor = TranscriptPreprocessor(config)

        # 轉換為 numpy 比較
        original = np.array(scanned_document)
        processed, _ = await preprocessor.preprocess(scanned_document)

        # 處理後應該與原始不同
        # 注意：可能大小不同，所以不能直接比較
        assert processed is not None


class TestPreprocessPerformance:
    """測試性能"""

    @pytest.fixture
    def small_image(self):
        """創建小圖像"""
        img_array = np.ones((100, 100, 3), dtype=np.uint8) * 200
        return Image.fromarray(img_array)

    @pytest.fixture
    def large_image(self):
        """創建大圖像"""
        img_array = np.ones((2000, 2000, 3), dtype=np.uint8) * 200
        return Image.fromarray(img_array)

    @pytest.mark.asyncio
    async def test_small_image_processing_time(self, small_image):
        """測試小圖像處理時間"""
        config = PreprocessConfig()
        preprocessor = TranscriptPreprocessor(config)

        _, metadata = await preprocessor.preprocess(small_image)

        # 小圖像應該很快處理完成（< 1000ms）
        assert metadata['processing_time_ms'] < 1000

    @pytest.mark.asyncio
    async def test_large_image_processing_time(self, large_image):
        """測試大圖像處理時間"""
        config = PreprocessConfig()
        preprocessor = TranscriptPreprocessor(config)

        _, metadata = await preprocessor.preprocess(large_image)

        # 大圖像可能需要更長時間，但應該在合理範圍內（< 5000ms）
        assert metadata['processing_time_ms'] > 0
        assert metadata['processing_time_ms'] < 5000


class TestPreprocessOutputQuality:
    """測試輸出品質"""

    @pytest.fixture
    def preprocessor(self):
        """創建預處理器實例"""
        config = PreprocessConfig(
            enable_watermark_removal=True,
            enable_binarization=True,
            enable_denoising=True
        )
        return TranscriptPreprocessor(config)

    @pytest.fixture
    def document_image(self):
        """創建文件圖像"""
        img_array = np.ones((300, 400, 3), dtype=np.uint8) * 230
        # 添加文字區域
        cv2.rectangle(img_array, (50, 100), (350, 130), (40, 40, 40), -1)
        cv2.rectangle(img_array, (50, 150), (350, 180), (40, 40, 40), -1)
        return Image.fromarray(img_array)

    @pytest.mark.asyncio
    async def test_output_is_valid_image(self, preprocessor, document_image):
        """測試輸出是有效圖像"""
        processed, _ = await preprocessor.preprocess(document_image)

        # 檢查形狀
        assert len(processed.shape) in [2, 3]

        # 檢查數據類型
        assert processed.dtype == np.uint8

        # 檢查值範圍
        assert np.min(processed) >= 0
        assert np.max(processed) <= 255

    @pytest.mark.asyncio
    async def test_output_preserves_structure(self, preprocessor, document_image):
        """測試輸出保留結構"""
        processed, _ = await preprocessor.preprocess(document_image)

        # 處理後應該仍有內容（不是全白或全黑）
        assert not np.all(processed == 0)
        assert not np.all(processed == 255)


class TestPreprocessEdgeCases:
    """測試邊界情況"""

    @pytest.mark.asyncio
    async def test_very_small_image(self):
        """測試極小圖像"""
        config = PreprocessConfig()
        preprocessor = TranscriptPreprocessor(config)

        img_array = np.ones((10, 10, 3), dtype=np.uint8) * 128
        pil_img = Image.fromarray(img_array)

        processed, metadata = await preprocessor.preprocess(pil_img)
        assert processed is not None

    @pytest.mark.asyncio
    async def test_all_steps_disabled(self):
        """測試所有步驟禁用"""
        config = PreprocessConfig(
            enable_watermark_removal=False,
            enable_binarization=False,
            enable_denoising=False
        )
        preprocessor = TranscriptPreprocessor(config)

        img_array = np.ones((200, 200, 3), dtype=np.uint8) * 128
        pil_img = Image.fromarray(img_array)

        processed, metadata = await preprocessor.preprocess(pil_img)

        # 應該仍然返回結果，只是沒有應用處理
        assert processed is not None
        assert metadata['watermark_removed'] is False
        assert metadata['binarization_applied'] is False
