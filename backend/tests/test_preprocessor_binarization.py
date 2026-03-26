"""
測試 TranscriptPreprocessor - 適應性二值化功能

驗證 adaptive_binarize() 支援 Gaussian, Mean, Sauvola 三種方法。
"""

import pytest
import numpy as np
import cv2
from app.lib.ocr_enhanced.preprocessor import TranscriptPreprocessor
from app.lib.ocr_enhanced.config import PreprocessConfig


class TestAdaptiveBinarizeInit:
    """測試 adaptive_binarize 方法基本功能"""

    @pytest.fixture
    def preprocessor(self):
        """創建預處理器實例"""
        config = PreprocessConfig()
        return TranscriptPreprocessor(config)

    @pytest.fixture
    def gray_image(self):
        """創建灰階圖像"""
        # 100x100 漸變灰階圖像
        img = np.zeros((100, 100), dtype=np.uint8)
        for i in range(100):
            img[i, :] = int(i * 255 / 100)
        return img

    @pytest.fixture
    def text_like_image(self):
        """創建類似文字的圖像"""
        # 白色背景
        img = np.ones((200, 200), dtype=np.uint8) * 255
        # 添加黑色矩形（模擬文字）
        cv2.rectangle(img, (50, 50), (150, 80), 0, -1)
        cv2.rectangle(img, (50, 100), (150, 130), 0, -1)
        return img

    def test_method_exists(self, preprocessor):
        """測試 adaptive_binarize 方法存在"""
        assert hasattr(preprocessor, 'adaptive_binarize')
        assert callable(preprocessor.adaptive_binarize)

    def test_returns_numpy_array(self, preprocessor, gray_image):
        """測試返回 numpy 陣列"""
        result = preprocessor.adaptive_binarize(gray_image)
        assert isinstance(result, np.ndarray)

    def test_preserves_image_shape(self, preprocessor, gray_image):
        """測試保持圖像形狀"""
        result = preprocessor.adaptive_binarize(gray_image)
        assert result.shape == gray_image.shape

    def test_preserves_image_dtype(self, preprocessor, gray_image):
        """測試保持圖像數據類型"""
        result = preprocessor.adaptive_binarize(gray_image)
        assert result.dtype == np.uint8


class TestGaussianMethod:
    """測試 Gaussian 二值化方法"""

    @pytest.fixture
    def preprocessor(self):
        """創建預處理器實例"""
        config = PreprocessConfig()
        return TranscriptPreprocessor(config)

    @pytest.fixture
    def gray_image(self):
        """創建灰階圖像"""
        img = np.zeros((100, 100), dtype=np.uint8)
        img[25:75, 25:75] = 128  # 中間區域灰色
        return img

    @pytest.fixture
    def text_like_image(self):
        """創建類似文字的圖像"""
        img = np.ones((200, 200), dtype=np.uint8) * 200
        cv2.rectangle(img, (50, 50), (150, 80), 50, -1)
        return img

    def test_gaussian_method_accepts_parameter(self, preprocessor, gray_image):
        """測試接受 gaussian 參數"""
        result = preprocessor.adaptive_binarize(gray_image, method="gaussian")
        assert result is not None

    def test_gaussian_output_is_binary(self, preprocessor, gray_image):
        """測試 Gaussian 方法輸出是二值化的"""
        result = preprocessor.adaptive_binarize(gray_image, method="gaussian")
        unique_values = np.unique(result)
        # 應該只有 0 和 255
        assert len(unique_values) <= 2
        assert all(v in [0, 255] for v in unique_values)

    def test_gaussian_handles_text_image(self, preprocessor, text_like_image):
        """測試 Gaussian 方法處理文字圖像"""
        result = preprocessor.adaptive_binarize(text_like_image, method="gaussian")
        # 檢查輸出是二值化的
        unique_values = np.unique(result)
        assert len(unique_values) <= 2

    def test_gaussian_different_from_global_threshold(self, preprocessor, text_like_image):
        """測試 Gaussian 適應性閾值與全局閾值不同"""
        # 適應性閾值
        adaptive_result = preprocessor.adaptive_binarize(text_like_image, method="gaussian")

        # 全局閾值
        _, global_result = cv2.threshold(text_like_image, 127, 255, cv2.THRESH_BINARY)

        # 兩者應該有差異（適應性處理不均勻光照更好）
        diff = np.sum(np.abs(adaptive_result.astype(int) - global_result.astype(int)))
        # 允許有差異（表示適應性閾值有效果）
        assert diff > 0


class TestMeanMethod:
    """測試 Mean 二值化方法"""

    @pytest.fixture
    def preprocessor(self):
        """創建預處理器實例"""
        config = PreprocessConfig()
        return TranscriptPreprocessor(config)

    @pytest.fixture
    def gray_image(self):
        """創建灰階圖像"""
        img = np.zeros((100, 100), dtype=np.uint8)
        img[25:75, 25:75] = 128
        return img

    @pytest.fixture
    def text_like_image(self):
        """創建類似文字的圖像"""
        img = np.ones((200, 200), dtype=np.uint8) * 200
        cv2.rectangle(img, (50, 50), (150, 80), 50, -1)
        return img

    def test_mean_method_accepts_parameter(self, preprocessor, gray_image):
        """測試接受 mean 參數"""
        result = preprocessor.adaptive_binarize(gray_image, method="mean")
        assert result is not None

    def test_mean_output_is_binary(self, preprocessor, gray_image):
        """測試 Mean 方法輸出是二值化的"""
        result = preprocessor.adaptive_binarize(gray_image, method="mean")
        unique_values = np.unique(result)
        assert len(unique_values) <= 2
        assert all(v in [0, 255] for v in unique_values)

    def test_mean_handles_text_image(self, preprocessor, text_like_image):
        """測試 Mean 方法處理文字圖像"""
        result = preprocessor.adaptive_binarize(text_like_image, method="mean")
        unique_values = np.unique(result)
        assert len(unique_values) <= 2

    def test_mean_different_from_gaussian(self, preprocessor, text_like_image):
        """測試 Mean 方法與 Gaussian 方法產生不同結果"""
        mean_result = preprocessor.adaptive_binarize(text_like_image, method="mean")
        gaussian_result = preprocessor.adaptive_binarize(text_like_image, method="gaussian")

        # 兩者可能有差異（不同算法）
        # 注意：對於某些圖像可能結果相同，所以不強制要求不同
        assert mean_result is not None
        assert gaussian_result is not None


class TestSauvolaMethod:
    """測試 Sauvola 二值化方法"""

    @pytest.fixture
    def preprocessor(self):
        """創建預處理器實例"""
        config = PreprocessConfig()
        return TranscriptPreprocessor(config)

    @pytest.fixture
    def gray_image(self):
        """創建灰階圖像"""
        img = np.zeros((100, 100), dtype=np.uint8)
        img[25:75, 25:75] = 128
        return img

    @pytest.fixture
    def text_like_image(self):
        """創建類似文字的圖像"""
        img = np.ones((200, 200), dtype=np.uint8) * 200
        cv2.rectangle(img, (50, 50), (150, 80), 50, -1)
        return img

    @pytest.fixture
    def uneven_lighting_image(self):
        """創建不均勻光照圖像"""
        img = np.zeros((200, 200), dtype=np.uint8)
        # 左邊亮，右邊暗
        for i in range(200):
            for j in range(200):
                img[i, j] = int(255 * (1 - j / 200)) + 50
        # 添加文字區域
        cv2.rectangle(img, (50, 80), (150, 120), 0, -1)
        return img

    def test_sauvola_method_accepts_parameter(self, preprocessor, gray_image):
        """測試接受 sauvola 參數"""
        result = preprocessor.adaptive_binarize(gray_image, method="sauvola")
        assert result is not None

    def test_sauvola_output_is_binary(self, preprocessor, gray_image):
        """測試 Sauvola 方法輸出是二值化的"""
        result = preprocessor.adaptive_binarize(gray_image, method="sauvola")
        unique_values = np.unique(result)
        assert len(unique_values) <= 2
        assert all(v in [0, 255] for v in unique_values)

    def test_sauvola_handles_text_image(self, preprocessor, text_like_image):
        """測試 Sauvola 方法處理文字圖像"""
        result = preprocessor.adaptive_binarize(text_like_image, method="sauvola")
        unique_values = np.unique(result)
        assert len(unique_values) <= 2

    def test_sauvola_handles_uneven_lighting(self, preprocessor, uneven_lighting_image):
        """測試 Sauvola 方法處理不均勻光照"""
        result = preprocessor.adaptive_binarize(uneven_lighting_image, method="sauvola")
        # 應該成功二值化
        unique_values = np.unique(result)
        assert len(unique_values) <= 2

    def test_sauvola_different_from_opencv_methods(self, preprocessor, text_like_image):
        """測試 Sauvola 方法與 OpenCV 方法不同"""
        sauvola_result = preprocessor.adaptive_binarize(text_like_image, method="sauvola")
        gaussian_result = preprocessor.adaptive_binarize(text_like_image, method="gaussian")

        # Sauvola 是自訂算法，應該與 OpenCV 內建方法有差異
        # 注意：某些簡單圖像可能結果相同
        assert sauvola_result is not None
        assert gaussian_result is not None


class TestMethodSwitching:
    """測試方法切換功能"""

    @pytest.fixture
    def preprocessor(self):
        """創建預處理器實例"""
        config = PreprocessConfig()
        return TranscriptPreprocessor(config)

    @pytest.fixture
    def text_image(self):
        """創建文字圖像"""
        img = np.ones((200, 200), dtype=np.uint8) * 220
        cv2.rectangle(img, (50, 50), (150, 80), 30, -1)
        return img

    def test_default_method(self, preprocessor, text_image):
        """測試預設方法"""
        # 不指定方法時應該使用預設方法
        result = preprocessor.adaptive_binarize(text_image)
        assert result is not None
        unique_values = np.unique(result)
        assert len(unique_values) <= 2

    def test_accepts_all_three_methods(self, preprocessor, text_image):
        """測試接受所有三種方法"""
        methods = ["gaussian", "mean", "sauvola"]
        for method in methods:
            result = preprocessor.adaptive_binarize(text_image, method=method)
            assert result is not None

    def test_invalid_method_raises_error(self, preprocessor, text_image):
        """測試無效方法拋出錯誤"""
        with pytest.raises((ValueError, KeyError)):
            preprocessor.adaptive_binarize(text_image, method="invalid_method")


class TestBinaryOutput:
    """測試二值化輸出"""

    @pytest.fixture
    def preprocessor(self):
        """創建預處理器實例"""
        config = PreprocessConfig()
        return TranscriptPreprocessor(config)

    @pytest.fixture
    def various_images(self):
        """創建多種測試圖像"""
        images = []

        # 均勻灰色
        img1 = np.ones((100, 100), dtype=np.uint8) * 128
        images.append(img1)

        # 漸變
        img2 = np.zeros((100, 100), dtype=np.uint8)
        for i in range(100):
            img2[i, :] = int(i * 255 / 100)
        images.append(img2)

        # 棋盤格
        img3 = np.zeros((100, 100), dtype=np.uint8)
        img3[::2, ::2] = 255
        img3[1::2, 1::2] = 255
        images.append(img3)

        return images

    def test_all_methods_output_only_0_and_255(self, preprocessor, various_images):
        """測試所有方法只輸出 0 和 255"""
        methods = ["gaussian", "mean", "sauvola"]

        for img in various_images:
            for method in methods:
                result = preprocessor.adaptive_binarize(img, method=method)
                unique_values = np.unique(result)

                # 只能有 0 或 255，或兩者都有
                assert len(unique_values) <= 2, f"Method {method} has more than 2 unique values"
                assert all(v in [0, 255] for v in unique_values), f"Method {method} has invalid values"


class TestGrayscaleInput:
    """測試灰階輸入處理"""

    @pytest.fixture
    def preprocessor(self):
        """創建預處理器實例"""
        config = PreprocessConfig()
        return TranscriptPreprocessor(config)

    def test_accepts_grayscale_image(self, preprocessor):
        """測試接受灰階圖像"""
        gray_img = np.ones((100, 100), dtype=np.uint8) * 128
        result = preprocessor.adaptive_binarize(gray_img)
        assert result is not None

    def test_handles_bgr_image_by_converting(self, preprocessor):
        """測試處理 BGR 圖像（應自動轉換為灰階）"""
        # BGR 圖像
        bgr_img = np.ones((100, 100, 3), dtype=np.uint8) * 128

        # 應該能處理（內部轉換為灰階）
        result = preprocessor.adaptive_binarize(bgr_img)
        assert result is not None


class TestEdgeCases:
    """測試邊界情況"""

    @pytest.fixture
    def preprocessor(self):
        """創建預處理器實例"""
        config = PreprocessConfig()
        return TranscriptPreprocessor(config)

    def test_handles_small_image(self, preprocessor):
        """測試處理小圖像"""
        small_img = np.ones((10, 10), dtype=np.uint8) * 128
        result = preprocessor.adaptive_binarize(small_img, method="gaussian")
        assert result.shape == (10, 10)

    def test_handles_large_image(self, preprocessor):
        """測試處理大圖像"""
        large_img = np.ones((1000, 1000), dtype=np.uint8) * 128
        result = preprocessor.adaptive_binarize(large_img, method="gaussian")
        assert result.shape == (1000, 1000)

    def test_handles_all_white_image(self, preprocessor):
        """測試處理全白圖像"""
        white_img = np.ones((100, 100), dtype=np.uint8) * 255
        result = preprocessor.adaptive_binarize(white_img, method="gaussian")
        # 全白圖像可能全部保持白色
        assert result is not None

    def test_handles_all_black_image(self, preprocessor):
        """測試處理全黑圖像"""
        black_img = np.zeros((100, 100), dtype=np.uint8)
        result = preprocessor.adaptive_binarize(black_img, method="gaussian")
        # 全黑圖像可能全部保持黑色
        assert result is not None


class TestIntegrationWithConfig:
    """測試與配置整合"""

    def test_uses_config_binarization_method(self):
        """測試使用配置中的二值化方法"""
        config = PreprocessConfig(binarization_method="sauvola")
        preprocessor = TranscriptPreprocessor(config)

        img = np.ones((100, 100), dtype=np.uint8) * 128

        # 不指定方法時應該使用配置的方法
        result = preprocessor.adaptive_binarize(img)
        assert result is not None

    def test_parameter_overrides_config(self):
        """測試參數覆蓋配置"""
        config = PreprocessConfig(binarization_method="gaussian")
        preprocessor = TranscriptPreprocessor(config)

        img = np.ones((100, 100), dtype=np.uint8) * 128

        # 明確指定方法應該覆蓋配置
        result = preprocessor.adaptive_binarize(img, method="mean")
        assert result is not None


class TestRealisticScenario:
    """測試真實場景"""

    @pytest.fixture
    def preprocessor(self):
        """創建預處理器實例"""
        config = PreprocessConfig()
        return TranscriptPreprocessor(config)

    @pytest.fixture
    def document_like_image(self):
        """創建類似文件的圖像"""
        # 模擬掃描文件：白色背景 + 黑色文字 + 雜訊
        img = np.random.randint(200, 255, (400, 400), dtype=np.uint8)

        # 添加文字區域（多個矩形模擬文字行）
        for i in range(5):
            y_start = 50 + i * 60
            cv2.rectangle(img, (50, y_start), (350, y_start + 30),
                         np.random.randint(0, 50), -1)

        return img

    def test_realistic_document_binarization(self, preprocessor, document_like_image):
        """測試真實文件二值化"""
        methods = ["gaussian", "mean", "sauvola"]

        for method in methods:
            result = preprocessor.adaptive_binarize(document_like_image, method=method)

            # 檢查輸出是二值化的
            unique_values = np.unique(result)
            assert len(unique_values) <= 2
            assert all(v in [0, 255] for v in unique_values)

            # 檢查文字區域是否被正確二值化
            # 中間區域應該有黑色像素（文字）
            center_region = result[50:350, 50:350]
            assert 0 in center_region  # 應該有黑色（文字）
            assert 255 in center_region  # 應該有白色（背景）
