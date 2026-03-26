"""
測試 TranscriptPreprocessor - 浮水印移除功能

驗證 remove_red_watermark() 正確移除紅色浮水印。
"""

import pytest
import numpy as np
import cv2
from app.lib.ocr_enhanced.preprocessor import TranscriptPreprocessor
from app.lib.ocr_enhanced.config import PreprocessConfig


class TestRemoveRedWatermarkInit:
    """測試 remove_red_watermark 方法基本功能"""

    @pytest.fixture
    def preprocessor(self):
        """創建預處理器實例"""
        config = PreprocessConfig()
        return TranscriptPreprocessor(config)

    @pytest.fixture
    def white_image(self):
        """創建純白色圖像 (BGR 格式)"""
        # 100x100 白色圖像
        return np.ones((100, 100, 3), dtype=np.uint8) * 255

    @pytest.fixture
    def red_image(self):
        """創建純紅色圖像 (BGR 格式)"""
        # 100x100 紅色圖像 (BGR: [0, 0, 255])
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        img[:, :, 2] = 255  # R channel
        return img

    @pytest.fixture
    def mixed_image(self):
        """創建帶紅色區域的混合圖像"""
        # 白色背景
        img = np.ones((100, 100, 3), dtype=np.uint8) * 255
        # 添加紅色矩形 (20x20)
        img[40:60, 40:60] = [0, 0, 255]  # BGR 紅色
        return img

    def test_method_exists(self, preprocessor):
        """測試 remove_red_watermark 方法存在"""
        assert hasattr(preprocessor, 'remove_red_watermark')
        assert callable(preprocessor.remove_red_watermark)

    def test_returns_numpy_array(self, preprocessor, white_image):
        """測試返回 numpy 陣列"""
        result = preprocessor.remove_red_watermark(white_image)
        assert isinstance(result, np.ndarray)

    def test_preserves_image_shape(self, preprocessor, white_image):
        """測試保持圖像形狀"""
        result = preprocessor.remove_red_watermark(white_image)
        assert result.shape == white_image.shape

    def test_preserves_image_dtype(self, preprocessor, white_image):
        """測試保持圖像數據類型"""
        result = preprocessor.remove_red_watermark(white_image)
        assert result.dtype == np.uint8


class TestRemoveRedWatermarkBehavior:
    """測試浮水印移除行為"""

    @pytest.fixture
    def preprocessor(self):
        """創建預處理器實例"""
        config = PreprocessConfig()
        return TranscriptPreprocessor(config)

    @pytest.fixture
    def white_image(self):
        """純白色圖像"""
        return np.ones((100, 100, 3), dtype=np.uint8) * 255

    @pytest.fixture
    def red_image(self):
        """純紅色圖像"""
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        img[:, :, 2] = 255
        return img

    @pytest.fixture
    def mixed_image(self):
        """混合圖像：白色背景 + 紅色區域"""
        img = np.ones((100, 100, 3), dtype=np.uint8) * 255
        img[40:60, 40:60] = [0, 0, 255]  # 紅色矩形
        return img

    def test_white_image_unchanged(self, preprocessor, white_image):
        """測試純白圖像保持不變"""
        result = preprocessor.remove_red_watermark(white_image)
        # 白色圖像應該幾乎不變（允許極小誤差）
        assert np.allclose(result, white_image, atol=5)

    def test_red_image_becomes_white(self, preprocessor, red_image):
        """測試純紅色圖像被填充為白色"""
        result = preprocessor.remove_red_watermark(red_image)
        # 紅色應該被移除，變成白色
        # 檢查平均值接近 255（白色）
        mean_value = np.mean(result)
        assert mean_value > 240, f"Expected white (>240), got {mean_value}"

    def test_red_area_removed_in_mixed_image(self, preprocessor, mixed_image):
        """測試混合圖像中的紅色區域被移除"""
        result = preprocessor.remove_red_watermark(mixed_image)

        # 檢查原本紅色區域 (40:60, 40:60) 變成白色
        red_area = result[40:60, 40:60]
        mean_red_area = np.mean(red_area)

        # 紅色區域應該變成白色（平均值接近 255）
        assert mean_red_area > 240, f"Red area not removed: mean={mean_red_area}"

    def test_non_red_area_preserved(self, preprocessor, mixed_image):
        """測試非紅色區域保持不變"""
        result = preprocessor.remove_red_watermark(mixed_image)

        # 檢查角落的白色區域是否保持白色
        corner_area = result[0:20, 0:20]
        mean_corner = np.mean(corner_area)

        assert mean_corner > 240, f"Non-red area changed: mean={mean_corner}"


class TestRemoveRedWatermarkHSVParameters:
    """測試 HSV 參數功能"""

    @pytest.fixture
    def preprocessor(self):
        """創建預處理器實例"""
        config = PreprocessConfig()
        return TranscriptPreprocessor(config)

    @pytest.fixture
    def red_image(self):
        """純紅色圖像"""
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        img[:, :, 2] = 255
        return img

    def test_accepts_custom_hsv_lower(self, preprocessor, red_image):
        """測試接受自訂 lower_hsv 參數"""
        # 應該不拋出異常
        result = preprocessor.remove_red_watermark(
            red_image,
            lower_hsv=(0, 40, 40)
        )
        assert result is not None

    def test_accepts_custom_hsv_upper1(self, preprocessor, red_image):
        """測試接受自訂 upper_hsv1 參數"""
        result = preprocessor.remove_red_watermark(
            red_image,
            upper_hsv1=(15, 255, 255)
        )
        assert result is not None

    def test_accepts_custom_hsv_upper2(self, preprocessor, red_image):
        """測試接受自訂 upper_hsv2 參數"""
        result = preprocessor.remove_red_watermark(
            red_image,
            upper_hsv2=(170, 255, 255)
        )
        assert result is not None

    def test_uses_default_hsv_from_config(self, preprocessor, red_image):
        """測試使用配置中的預設 HSV 值"""
        # 不傳參數時應使用 config 預設值
        result = preprocessor.remove_red_watermark(red_image)
        assert result is not None
        assert np.mean(result) > 240  # 應該成功移除紅色


class TestRemoveRedWatermarkTwoRanges:
    """測試紅色雙區間檢測"""

    @pytest.fixture
    def preprocessor(self):
        """創建預處理器實例"""
        config = PreprocessConfig()
        return TranscriptPreprocessor(config)

    def test_detects_low_hue_red(self, preprocessor):
        """測試檢測低色相紅色 (H: 0-10)"""
        # 創建 H=5 的紅色圖像
        img_hsv = np.zeros((50, 50, 3), dtype=np.uint8)
        img_hsv[:, :] = [5, 200, 200]  # H=5, S=200, V=200
        img_bgr = cv2.cvtColor(img_hsv, cv2.COLOR_HSV2BGR)

        result = preprocessor.remove_red_watermark(img_bgr)
        mean_value = np.mean(result)

        # 應該被檢測並移除（變白色）
        assert mean_value > 200, f"Low hue red not detected: mean={mean_value}"

    def test_detects_high_hue_red(self, preprocessor):
        """測試檢測高色相紅色 (H: 160-179)"""
        # 創建 H=170 的紅色圖像
        img_hsv = np.zeros((50, 50, 3), dtype=np.uint8)
        img_hsv[:, :] = [170, 200, 200]  # H=170, S=200, V=200
        img_bgr = cv2.cvtColor(img_hsv, cv2.COLOR_HSV2BGR)

        result = preprocessor.remove_red_watermark(img_bgr)
        mean_value = np.mean(result)

        # 應該被檢測並移除（變白色）
        assert mean_value > 200, f"High hue red not detected: mean={mean_value}"

    def test_does_not_detect_green(self, preprocessor):
        """測試不會誤判綠色為紅色"""
        # 創建綠色圖像 (H=60)
        img_hsv = np.zeros((50, 50, 3), dtype=np.uint8)
        img_hsv[:, :] = [60, 200, 200]  # 綠色
        img_bgr = cv2.cvtColor(img_hsv, cv2.COLOR_HSV2BGR)

        original_mean = np.mean(img_bgr)
        result = preprocessor.remove_red_watermark(img_bgr)
        result_mean = np.mean(result)

        # 綠色應該保持不變（允許小誤差）
        assert abs(result_mean - original_mean) < 20, "Green color incorrectly removed"


class TestRemoveRedWatermarkMorphology:
    """測試形態學操作"""

    @pytest.fixture
    def preprocessor(self):
        """創建預處理器實例"""
        config = PreprocessConfig()
        return TranscriptPreprocessor(config)

    @pytest.fixture
    def noisy_red_image(self):
        """創建帶雜訊的紅色圖像"""
        # 白色背景
        img = np.ones((100, 100, 3), dtype=np.uint8) * 255

        # 添加一些紅色點（模擬雜訊）
        for i in range(10):
            x, y = np.random.randint(10, 90, 2)
            img[x, y] = [0, 0, 255]

        return img

    def test_removes_small_noise(self, preprocessor, noisy_red_image):
        """測試移除小雜訊"""
        result = preprocessor.remove_red_watermark(noisy_red_image)

        # 雜訊應該被形態學操作移除
        # 檢查結果大部分是白色
        mean_value = np.mean(result)
        assert mean_value > 245, f"Noise not removed properly: mean={mean_value}"

    def test_preserves_large_red_areas(self, preprocessor):
        """測試保留大塊紅色區域（正確檢測浮水印）"""
        # 創建帶大塊紅色區域的圖像
        img = np.ones((100, 100, 3), dtype=np.uint8) * 255
        img[30:70, 30:70] = [0, 0, 255]  # 大塊紅色

        result = preprocessor.remove_red_watermark(img)

        # 大塊紅色區域應該被檢測並填充為白色
        red_area = result[30:70, 30:70]
        mean_red_area = np.mean(red_area)

        assert mean_red_area > 240, f"Large red area not removed: mean={mean_red_area}"


class TestRemoveRedWatermarkEdgeCases:
    """測試邊界情況"""

    @pytest.fixture
    def preprocessor(self):
        """創建預處理器實例"""
        config = PreprocessConfig()
        return TranscriptPreprocessor(config)

    def test_handles_small_image(self, preprocessor):
        """測試處理小圖像 (10x10)"""
        small_img = np.ones((10, 10, 3), dtype=np.uint8) * 255
        result = preprocessor.remove_red_watermark(small_img)
        assert result.shape == (10, 10, 3)

    def test_handles_large_image(self, preprocessor):
        """測試處理大圖像 (1000x1000)"""
        large_img = np.ones((1000, 1000, 3), dtype=np.uint8) * 255
        result = preprocessor.remove_red_watermark(large_img)
        assert result.shape == (1000, 1000, 3)

    def test_handles_grayscale_converted_to_bgr(self, preprocessor):
        """測試處理灰階圖像轉 BGR"""
        gray_img = np.ones((100, 100), dtype=np.uint8) * 128
        bgr_img = cv2.cvtColor(gray_img, cv2.COLOR_GRAY2BGR)

        result = preprocessor.remove_red_watermark(bgr_img)
        assert result is not None
        assert result.shape == bgr_img.shape

    def test_handles_image_with_no_red(self, preprocessor):
        """測試處理完全無紅色的圖像"""
        # 藍色圖像
        blue_img = np.zeros((100, 100, 3), dtype=np.uint8)
        blue_img[:, :, 0] = 255  # B channel

        result = preprocessor.remove_red_watermark(blue_img)

        # 藍色不應該被移除
        assert np.mean(result[:, :, 0]) > 200  # B channel 保持高值


class TestRemoveRedWatermarkIntegration:
    """測試整合功能"""

    @pytest.fixture
    def preprocessor(self):
        """創建預處理器實例"""
        config = PreprocessConfig(
            hsv_lower=(0, 50, 50),
            hsv_upper1=(10, 255, 255),
            hsv_upper2=(160, 255, 255)
        )
        return TranscriptPreprocessor(config)

    def test_uses_config_hsv_values(self, preprocessor):
        """測試使用配置中的 HSV 值"""
        # 創建紅色圖像
        red_img = np.zeros((100, 100, 3), dtype=np.uint8)
        red_img[:, :, 2] = 255

        # 使用配置的預設值
        result = preprocessor.remove_red_watermark(red_img)

        assert np.mean(result) > 240

    def test_realistic_transcript_simulation(self, preprocessor):
        """測試模擬真實謄本情境"""
        # 創建模擬謄本：白色背景 + 黑色文字 + 紅色浮水印
        img = np.ones((200, 200, 3), dtype=np.uint8) * 255

        # 添加黑色文字區域（模擬）
        cv2.rectangle(img, (50, 50), (150, 70), (0, 0, 0), -1)

        # 添加紅色浮水印
        cv2.putText(img, "COPY", (80, 120), cv2.FONT_HERSHEY_SIMPLEX,
                    1, (0, 0, 255), 2)

        result = preprocessor.remove_red_watermark(img)

        # 檢查紅色區域被移除
        watermark_area = result[100:130, 70:130]
        mean_watermark = np.mean(watermark_area)

        # 浮水印區域應該變白
        assert mean_watermark > 220, f"Watermark not removed: mean={mean_watermark}"

        # 檢查黑色文字保留
        text_area = result[50:70, 50:150]
        mean_text = np.mean(text_area)

        # 文字區域應該仍是黑色
        assert mean_text < 50, f"Black text not preserved: mean={mean_text}"
