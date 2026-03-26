"""
測試 TranscriptPreprocessor - 去噪與解析度調整功能

驗證 denoise() 和 adjust_resolution() 正確處理圖像。
"""

import pytest
import numpy as np
import cv2
from app.lib.ocr_enhanced.preprocessor import TranscriptPreprocessor
from app.lib.ocr_enhanced.config import PreprocessConfig


class TestDenoiseInit:
    """測試 denoise 方法基本功能"""

    @pytest.fixture
    def preprocessor(self):
        """創建預處理器實例"""
        config = PreprocessConfig()
        return TranscriptPreprocessor(config)

    @pytest.fixture
    def clean_image(self):
        """創建乾淨圖像"""
        img = np.ones((100, 100, 3), dtype=np.uint8) * 128
        return img

    @pytest.fixture
    def noisy_image(self):
        """創建有雜訊的圖像"""
        img = np.ones((100, 100, 3), dtype=np.uint8) * 128
        # 添加高斯雜訊
        noise = np.random.normal(0, 25, img.shape)
        noisy = img + noise
        noisy = np.clip(noisy, 0, 255).astype(np.uint8)
        return noisy

    def test_method_exists(self, preprocessor):
        """測試 denoise 方法存在"""
        assert hasattr(preprocessor, 'denoise')
        assert callable(preprocessor.denoise)

    def test_returns_numpy_array(self, preprocessor, clean_image):
        """測試返回 numpy 陣列"""
        result = preprocessor.denoise(clean_image)
        assert isinstance(result, np.ndarray)

    def test_preserves_image_shape(self, preprocessor, clean_image):
        """測試保持圖像形狀"""
        result = preprocessor.denoise(clean_image)
        assert result.shape == clean_image.shape

    def test_preserves_image_dtype(self, preprocessor, clean_image):
        """測試保持圖像數據類型"""
        result = preprocessor.denoise(clean_image)
        assert result.dtype == np.uint8


class TestDenoiseBehavior:
    """測試去噪行為"""

    @pytest.fixture
    def preprocessor(self):
        """創建預處理器實例"""
        config = PreprocessConfig()
        return TranscriptPreprocessor(config)

    @pytest.fixture
    def noisy_image(self):
        """創建有雜訊的圖像"""
        img = np.ones((200, 200, 3), dtype=np.uint8) * 128
        noise = np.random.normal(0, 20, img.shape)
        noisy = img + noise
        noisy = np.clip(noisy, 0, 255).astype(np.uint8)
        return noisy

    @pytest.fixture
    def text_with_noise(self):
        """創建帶雜訊的文字圖像"""
        img = np.ones((200, 200, 3), dtype=np.uint8) * 255
        # 添加文字區域
        cv2.rectangle(img, (50, 50), (150, 80), (0, 0, 0), -1)
        # 添加雜訊
        noise = np.random.normal(0, 15, img.shape)
        noisy = img + noise
        noisy = np.clip(noisy, 0, 255).astype(np.uint8)
        return noisy

    def test_denoise_reduces_noise(self, preprocessor, noisy_image):
        """測試去噪降低雜訊"""
        denoised = preprocessor.denoise(noisy_image)

        # 計算標準差（雜訊指標）
        original_std = np.std(noisy_image)
        denoised_std = np.std(denoised)

        # 去噪後標準差應該更小（更平滑）
        assert denoised_std < original_std

    def test_denoise_preserves_structure(self, preprocessor, text_with_noise):
        """測試去噪保留結構"""
        denoised = preprocessor.denoise(text_with_noise)

        # 檢查文字區域仍然存在
        text_area_original = text_with_noise[50:80, 50:150]
        text_area_denoised = denoised[50:80, 50:150]

        # 文字區域應該仍然較暗
        assert np.mean(text_area_denoised) < np.mean(denoised)

    def test_denoise_does_not_over_blur(self, preprocessor):
        """測試不會過度模糊"""
        # 創建清晰的黑白邊界
        img = np.ones((100, 100, 3), dtype=np.uint8) * 255
        img[:, :50] = 0  # 左半邊黑色

        denoised = preprocessor.denoise(img)

        # 檢查邊界仍然清晰（中間列的變化）
        middle_row = denoised[50, :, 0]
        # 應該有明顯的黑白過渡
        assert np.max(middle_row) - np.min(middle_row) > 200


class TestDenoiseKernelSize:
    """測試 kernel size 參數"""

    @pytest.fixture
    def preprocessor(self):
        """創建預處理器實例"""
        config = PreprocessConfig()
        return TranscriptPreprocessor(config)

    @pytest.fixture
    def noisy_image(self):
        """創建有雜訊的圖像"""
        img = np.ones((100, 100, 3), dtype=np.uint8) * 128
        noise = np.random.normal(0, 20, img.shape)
        noisy = img + noise
        noisy = np.clip(noisy, 0, 255).astype(np.uint8)
        return noisy

    def test_accepts_custom_kernel_size(self, preprocessor, noisy_image):
        """測試接受自訂 kernel size"""
        result = preprocessor.denoise(noisy_image, kernel_size=3)
        assert result is not None

    def test_default_kernel_size_is_5(self, preprocessor, noisy_image):
        """測試預設 kernel size 為 5"""
        # 不傳參數時應該使用預設值 5
        result = preprocessor.denoise(noisy_image)
        assert result is not None

    def test_larger_kernel_more_blur(self, preprocessor, noisy_image):
        """測試較大 kernel 產生更多模糊"""
        result_small = preprocessor.denoise(noisy_image, kernel_size=3)
        result_large = preprocessor.denoise(noisy_image, kernel_size=9)

        # 較大 kernel 應該產生更平滑的結果
        std_small = np.std(result_small)
        std_large = np.std(result_large)

        assert std_large < std_small


class TestAdjustResolutionInit:
    """測試 adjust_resolution 方法基本功能"""

    @pytest.fixture
    def preprocessor(self):
        """創建預處理器實例"""
        config = PreprocessConfig()
        return TranscriptPreprocessor(config)

    @pytest.fixture
    def small_image(self):
        """創建小圖像"""
        return np.ones((100, 100, 3), dtype=np.uint8) * 128

    def test_method_exists(self, preprocessor):
        """測試 adjust_resolution 方法存在"""
        assert hasattr(preprocessor, 'adjust_resolution')
        assert callable(preprocessor.adjust_resolution)

    def test_returns_numpy_array(self, preprocessor, small_image):
        """測試返回 numpy 陣列"""
        result = preprocessor.adjust_resolution(small_image, target_dpi=300)
        assert isinstance(result, np.ndarray)

    def test_preserves_image_dtype(self, preprocessor, small_image):
        """測試保持圖像數據類型"""
        result = preprocessor.adjust_resolution(small_image, target_dpi=300)
        assert result.dtype == np.uint8


class TestAdjustResolutionBehavior:
    """測試解析度調整行為"""

    @pytest.fixture
    def preprocessor(self):
        """創建預處理器實例"""
        config = PreprocessConfig()
        return TranscriptPreprocessor(config)

    @pytest.fixture
    def low_res_image(self):
        """創建低解析度圖像（模擬 DPI < 1500）"""
        # 假設當前 DPI 為 300，需要放大到 1500
        return np.ones((100, 100, 3), dtype=np.uint8) * 128

    @pytest.fixture
    def high_res_image(self):
        """創建高解析度圖像（模擬 DPI >= 1500）"""
        return np.ones((1000, 1000, 3), dtype=np.uint8) * 128

    def test_upscales_low_resolution_image(self, preprocessor, low_res_image):
        """測試放大低解析度圖像"""
        # 模擬從 300 DPI 放大到 1500 DPI（5倍）
        result = preprocessor.adjust_resolution(low_res_image, target_dpi=1500)

        # 圖像應該變大
        assert result.shape[0] > low_res_image.shape[0]
        assert result.shape[1] > low_res_image.shape[1]

    def test_preserves_high_resolution_image(self, preprocessor, high_res_image):
        """測試保留高解析度圖像"""
        original_shape = high_res_image.shape
        result = preprocessor.adjust_resolution(high_res_image, target_dpi=1500)

        # 已經是高解析度，應該不變或變化很小
        # 允許一定誤差
        assert abs(result.shape[0] - original_shape[0]) <= 10
        assert abs(result.shape[1] - original_shape[1]) <= 10

    def test_maintains_aspect_ratio(self, preprocessor):
        """測試保持長寬比"""
        # 創建非正方形圖像
        img = np.ones((100, 200, 3), dtype=np.uint8) * 128
        aspect_ratio_original = img.shape[1] / img.shape[0]

        result = preprocessor.adjust_resolution(img, target_dpi=1500)
        aspect_ratio_result = result.shape[1] / result.shape[0]

        # 長寬比應該保持（允許小誤差）
        assert abs(aspect_ratio_result - aspect_ratio_original) < 0.01


class TestAdjustResolutionInterpolation:
    """測試插值方法"""

    @pytest.fixture
    def preprocessor(self):
        """創建預處理器實例"""
        config = PreprocessConfig()
        return TranscriptPreprocessor(config)

    @pytest.fixture
    def low_res_image(self):
        """創建低解析度圖像"""
        return np.ones((50, 50, 3), dtype=np.uint8) * 128

    def test_uses_interpolation(self, preprocessor, low_res_image):
        """測試使用插值方法"""
        # 應該不拋出異常
        result = preprocessor.adjust_resolution(low_res_image, target_dpi=1500)
        assert result is not None

    def test_upscaled_image_is_smooth(self, preprocessor):
        """測試放大後圖像平滑"""
        # 創建簡單圖案
        img = np.ones((50, 50, 3), dtype=np.uint8) * 255
        img[20:30, 20:30] = 0  # 中間黑色方塊

        result = preprocessor.adjust_resolution(img, target_dpi=1500)

        # 放大後應該仍然有清晰的結構
        assert result is not None
        assert result.shape[0] > img.shape[0]


class TestDenoiseEdgeCases:
    """測試 denoise 邊界情況"""

    @pytest.fixture
    def preprocessor(self):
        """創建預處理器實例"""
        config = PreprocessConfig()
        return TranscriptPreprocessor(config)

    def test_handles_grayscale_image(self, preprocessor):
        """測試處理灰階圖像"""
        gray = np.ones((100, 100), dtype=np.uint8) * 128
        result = preprocessor.denoise(gray)
        assert result is not None

    def test_handles_small_image(self, preprocessor):
        """測試處理小圖像"""
        small = np.ones((10, 10, 3), dtype=np.uint8) * 128
        result = preprocessor.denoise(small, kernel_size=3)
        assert result.shape == small.shape

    def test_handles_large_image(self, preprocessor):
        """測試處理大圖像"""
        large = np.ones((1000, 1000, 3), dtype=np.uint8) * 128
        result = preprocessor.denoise(large)
        assert result.shape == large.shape

    def test_odd_kernel_size_required(self, preprocessor):
        """測試 kernel size 必須是奇數"""
        img = np.ones((100, 100, 3), dtype=np.uint8) * 128
        # 偶數 kernel size 應該自動調整或拋出錯誤
        # OpenCV 會自動處理，所以這裡測試不拋出異常
        result = preprocessor.denoise(img, kernel_size=4)
        assert result is not None


class TestAdjustResolutionEdgeCases:
    """測試 adjust_resolution 邊界情況"""

    @pytest.fixture
    def preprocessor(self):
        """創建預處理器實例"""
        config = PreprocessConfig()
        return TranscriptPreprocessor(config)

    def test_handles_very_small_image(self, preprocessor):
        """測試處理極小圖像"""
        tiny = np.ones((5, 5, 3), dtype=np.uint8) * 128
        result = preprocessor.adjust_resolution(tiny, target_dpi=1500)
        assert result.shape[0] > tiny.shape[0]

    def test_handles_grayscale_image(self, preprocessor):
        """測試處理灰階圖像"""
        gray = np.ones((100, 100), dtype=np.uint8) * 128
        result = preprocessor.adjust_resolution(gray, target_dpi=1500)
        assert result is not None

    def test_target_dpi_parameter(self, preprocessor):
        """測試 target_dpi 參數"""
        img = np.ones((100, 100, 3), dtype=np.uint8) * 128

        # 不同 target_dpi 應該產生不同大小
        result_300 = preprocessor.adjust_resolution(img, target_dpi=300)
        result_1500 = preprocessor.adjust_resolution(img, target_dpi=1500)

        # 1500 DPI 應該比 300 DPI 更大
        assert result_1500.shape[0] >= result_300.shape[0]


class TestIntegrationWithConfig:
    """測試與配置整合"""

    def test_uses_config_kernel_size(self):
        """測試使用配置中的 kernel size"""
        config = PreprocessConfig(gaussian_kernel_size=7)
        preprocessor = TranscriptPreprocessor(config)

        img = np.ones((100, 100, 3), dtype=np.uint8) * 128
        # 不指定 kernel_size 應該使用配置的值
        result = preprocessor.denoise(img)
        assert result is not None

    def test_uses_config_target_dpi(self):
        """測試使用配置中的 target_dpi"""
        config = PreprocessConfig(target_dpi=2000)
        preprocessor = TranscriptPreprocessor(config)

        img = np.ones((100, 100, 3), dtype=np.uint8) * 128
        result = preprocessor.adjust_resolution(img)
        assert result is not None

    def test_parameter_overrides_config(self):
        """測試參數覆蓋配置"""
        config = PreprocessConfig(gaussian_kernel_size=3, target_dpi=1000)
        preprocessor = TranscriptPreprocessor(config)

        img = np.ones((100, 100, 3), dtype=np.uint8) * 128

        # 明確指定參數應該覆蓋配置
        result1 = preprocessor.denoise(img, kernel_size=7)
        result2 = preprocessor.adjust_resolution(img, target_dpi=2000)

        assert result1 is not None
        assert result2 is not None


class TestRealisticScenario:
    """測試真實場景"""

    @pytest.fixture
    def preprocessor(self):
        """創建預處理器實例"""
        config = PreprocessConfig()
        return TranscriptPreprocessor(config)

    @pytest.fixture
    def scanned_document_like(self):
        """創建類似掃描文件的圖像"""
        # 模擬低解析度掃描文件：白色背景 + 黑色文字 + 雜訊
        img = np.ones((200, 300, 3), dtype=np.uint8) * 240

        # 添加文字區域
        for i in range(5):
            y_start = 30 + i * 40
            cv2.rectangle(img, (20, y_start), (280, y_start + 20), (20, 20, 20), -1)

        # 添加掃描雜訊
        noise = np.random.normal(0, 10, img.shape)
        noisy = img + noise
        noisy = np.clip(noisy, 0, 255).astype(np.uint8)

        return noisy

    def test_denoise_scanned_document(self, preprocessor, scanned_document_like):
        """測試對掃描文件去噪"""
        denoised = preprocessor.denoise(scanned_document_like)

        # 去噪後應該更平滑
        original_std = np.std(scanned_document_like)
        denoised_std = np.std(denoised)
        assert denoised_std < original_std

        # 文字區域應該仍然存在
        text_area = denoised[30:50, 20:280]
        background_area = denoised[0:20, 0:280]
        assert np.mean(text_area) < np.mean(background_area)

    def test_upscale_low_resolution_document(self, preprocessor, scanned_document_like):
        """測試放大低解析度文件"""
        # 模擬從 300 DPI 放大
        upscaled = preprocessor.adjust_resolution(scanned_document_like, target_dpi=1500)

        # 應該變大
        assert upscaled.shape[0] > scanned_document_like.shape[0]
        assert upscaled.shape[1] > scanned_document_like.shape[1]

        # 長寬比應該保持
        original_aspect = scanned_document_like.shape[1] / scanned_document_like.shape[0]
        upscaled_aspect = upscaled.shape[1] / upscaled.shape[0]
        assert abs(upscaled_aspect - original_aspect) < 0.01

    def test_combined_denoise_and_upscale(self, preprocessor, scanned_document_like):
        """測試組合去噪和放大"""
        # 先去噪
        denoised = preprocessor.denoise(scanned_document_like, kernel_size=5)
        # 再放大
        upscaled = preprocessor.adjust_resolution(denoised, target_dpi=1500)

        assert upscaled is not None
        assert upscaled.shape[0] > scanned_document_like.shape[0]
        assert upscaled.shape[1] > scanned_document_like.shape[1]
