"""
Image Preprocessor Module

圖像預處理模組，提供浮水印移除、二值化、去噪等功能。
"""

from typing import Optional
import time
import numpy as np
import cv2
from PIL import Image

from .types import PreprocessingStrategy, BinarizationMethod


class TranscriptPreprocessor:
    """
    謄本文件預處理器

    提供針對謄本文件的專用圖像預處理功能。
    """

    def __init__(self, config):
        """
        初始化預處理器

        Args:
            config: PreprocessConfig 配置物件
        """
        self.config = config

    async def preprocess(
        self,
        image: Image.Image,
        strategy: Optional[PreprocessingStrategy] = None
    ) -> tuple[np.ndarray, dict]:
        """
        執行預處理

        Args:
            image: 原始 PIL Image
            strategy: 自訂策略，None 使用預設

        Returns:
            (處理後的 numpy 陣列, 處理元數據)

        Raises:
            ValueError: image 為 None
            TypeError: image 不是 PIL Image
            AttributeError: image 缺少必要屬性

        Processing Pipeline:
            1. PIL → numpy array (BGR format)
            2. Remove red watermark (if enabled)
            3. Adaptive binarization (if enabled)
            4. Denoise (if enabled)
            5. Resolution adjustment
        """
        # 開始計時
        start_time = time.time()

        # 初始化元數據
        metadata = {
            "watermark_removed": False,
            "binarization_applied": False,
            "processing_time_ms": 0
        }

        # 驗證輸入
        if image is None:
            raise ValueError("image 不能為 None")

        if not isinstance(image, Image.Image):
            raise TypeError("image 必須是 PIL Image")

        # 1. 轉換 PIL → numpy (BGR for OpenCV)
        # PIL uses RGB, OpenCV uses BGR
        img_array = np.array(image)

        # Convert RGB to BGR if color image
        if len(img_array.shape) == 3 and img_array.shape[2] == 3:
            img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

        # 2. 浮水印移除
        if self.config.enable_watermark_removal:
            img_array = self.remove_red_watermark(img_array)
            metadata["watermark_removed"] = True

        # 3. 二值化
        if self.config.enable_binarization:
            img_array = self.adaptive_binarize(
                img_array,
                method=self.config.binarization_method
            )
            metadata["binarization_applied"] = True
            metadata["binarization_method"] = self.config.binarization_method

        # 4. 去噪
        if self.config.enable_denoising:
            img_array = self.denoise(img_array)

        # 5. 解析度調整
        img_array = self.adjust_resolution(
            img_array,
            target_dpi=self.config.target_dpi
        )

        # 計算處理時間
        end_time = time.time()
        metadata["processing_time_ms"] = (end_time - start_time) * 1000

        return img_array, metadata

    def remove_red_watermark(
        self,
        image: np.ndarray,
        lower_hsv: tuple = None,
        upper_hsv1: tuple = None,
        upper_hsv2: tuple = None
    ) -> np.ndarray:
        """
        移除紅色浮水印

        Args:
            image: BGR 格式 numpy 陣列
            lower_hsv: HSV 下界 (預設使用 config)
            upper_hsv1: 紅色範圍 1 上界 [0, 10] (預設使用 config)
            upper_hsv2: 紅色範圍 2 上界 [160, 179] (預設使用 config)

        Returns:
            移除浮水印後的圖像

        Algorithm:
            1. Convert BGR → HSV
            2. Create mask for red range (兩個區間)
            3. Morphological operations (移除雜訊)
            4. Fill masked area with white
        """
        # 使用配置的預設值或傳入的參數
        if lower_hsv is None:
            lower_hsv = self.config.hsv_lower
        if upper_hsv1 is None:
            upper_hsv1 = self.config.hsv_upper1
        if upper_hsv2 is None:
            upper_hsv2 = self.config.hsv_upper2

        # 確保是 numpy 陣列
        if not isinstance(image, np.ndarray):
            raise TypeError("image 必須是 numpy 陣列")

        # 複製圖像避免修改原始數據
        result = image.copy()

        # 1. 轉換 BGR → HSV
        hsv = cv2.cvtColor(result, cv2.COLOR_BGR2HSV)

        # 2. 創建紅色遮罩 (兩個區間)
        # 紅色在 HSV 中有兩個範圍：[0, 10] 和 [160, 179]
        lower_hsv_np = np.array(lower_hsv, dtype=np.uint8)
        upper_hsv1_np = np.array(upper_hsv1, dtype=np.uint8)
        upper_hsv2_np = np.array(upper_hsv2, dtype=np.uint8)

        # 範圍 1: H=[0, 10]
        mask1 = cv2.inRange(hsv, lower_hsv_np, upper_hsv1_np)

        # 範圍 2: H=[160, 179] (使用 lower_hsv 的 S, V 但改變 H)
        lower_hsv2 = np.array([upper_hsv2_np[0], lower_hsv_np[1], lower_hsv_np[2]], dtype=np.uint8)
        upper_hsv2_full = np.array([179, upper_hsv2_np[1], upper_hsv2_np[2]], dtype=np.uint8)
        mask2 = cv2.inRange(hsv, lower_hsv2, upper_hsv2_full)

        # 合併兩個遮罩
        mask = cv2.bitwise_or(mask1, mask2)

        # 3. 形態學操作：移除小雜訊
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))

        # 先開運算（侵蝕後膨脹）移除小白點
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

        # 再閉運算（膨脹後侵蝕）填充小黑洞
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)

        # 4. 填充被遮罩區域為白色
        result[mask > 0] = [255, 255, 255]

        return result

    def adaptive_binarize(
        self,
        image: np.ndarray,
        method: BinarizationMethod = None
    ) -> np.ndarray:
        """
        適應性二值化

        Args:
            image: 灰階圖像或 BGR 圖像（會自動轉換）
            method: 二值化方法 (gaussian/mean/sauvola)，None 時使用配置預設值

        Returns:
            二值化後圖像（只有 0 或 255）

        Raises:
            ValueError: 無效的二值化方法
        """
        # 使用配置預設值或傳入參數
        if method is None:
            method = self.config.binarization_method

        # 驗證方法有效性
        valid_methods = ["gaussian", "mean", "sauvola"]
        if method not in valid_methods:
            raise ValueError(
                f"無效的二值化方法: {method}。"
                f"有效方法: {', '.join(valid_methods)}"
            )

        # 確保是 numpy 陣列
        if not isinstance(image, np.ndarray):
            raise TypeError("image 必須是 numpy 陣列")

        # 轉換為灰階圖像（如果是 BGR）
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # 根據方法執行二值化
        if method == "gaussian":
            return self._binarize_gaussian(gray)
        elif method == "mean":
            return self._binarize_mean(gray)
        elif method == "sauvola":
            return self._binarize_sauvola(gray)

        # 不應該到達這裡
        return gray

    def _binarize_gaussian(self, gray: np.ndarray) -> np.ndarray:
        """
        使用 Gaussian 適應性閾值二值化

        Args:
            gray: 灰階圖像

        Returns:
            二值化後圖像
        """
        # 使用 Gaussian 加權平均計算局部閾值
        # block_size: 必須是奇數，決定局部區域大小（增大以適應謄本）
        # C: 從平均值減去的常數，用於微調（減小以保留更多文字）
        block_size = 25  # 增大以適應謄本的文字大小
        C = 5            # 調整以避免過度二值化

        binary = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            block_size,
            C
        )

        return binary

    def _binarize_mean(self, gray: np.ndarray) -> np.ndarray:
        """
        使用 Mean 適應性閾值二值化

        Args:
            gray: 灰階圖像

        Returns:
            二值化後圖像
        """
        # 使用算術平均計算局部閾值
        block_size = 25  # 增大以適應謄本
        C = 5            # 調整以保留更多細節

        binary = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_MEAN_C,
            cv2.THRESH_BINARY,
            block_size,
            C
        )

        return binary

    def _binarize_sauvola(
        self,
        gray: np.ndarray,
        window_size: int = 15,
        k: float = 0.5,
        R: float = 128.0
    ) -> np.ndarray:
        """
        使用 Sauvola 方法二值化

        Sauvola 方法特別適合處理不均勻光照的文件圖像。

        Args:
            gray: 灰階圖像
            window_size: 局部窗口大小（必須是奇數）
            k: 調整參數，控制標準差的影響（通常 0.2-0.5）
            R: 標準差的動態範圍（通常 128）

        Returns:
            二值化後圖像

        Algorithm:
            對每個像素 (x,y):
            T(x,y) = m(x,y) * [1 + k * (s(x,y) / R - 1)]
            其中:
            - m(x,y): 局部均值
            - s(x,y): 局部標準差
            - 如果 pixel(x,y) > T(x,y)，設為 255（白色），否則 0（黑色）
        """
        # 確保窗口大小是奇數
        if window_size % 2 == 0:
            window_size += 1

        # 轉換為 float 進行計算
        img_float = gray.astype(np.float64)

        # 計算局部均值
        mean = cv2.boxFilter(
            img_float,
            ddepth=-1,
            ksize=(window_size, window_size),
            normalize=True
        )

        # 計算局部標準差
        # std = sqrt(E[X^2] - E[X]^2)
        mean_sq = cv2.boxFilter(
            img_float ** 2,
            ddepth=-1,
            ksize=(window_size, window_size),
            normalize=True
        )
        variance = mean_sq - mean ** 2
        # 避免負數（由於浮點誤差）
        variance = np.maximum(variance, 0)
        std = np.sqrt(variance)

        # 計算 Sauvola 閾值
        # T(x,y) = m(x,y) * [1 + k * (s(x,y) / R - 1)]
        threshold = mean * (1 + k * (std / R - 1))

        # 應用閾值
        binary = np.where(img_float > threshold, 255, 0).astype(np.uint8)

        return binary

    def denoise(self, image: np.ndarray, kernel_size: int = None) -> np.ndarray:
        """
        去噪處理

        使用 Gaussian blur 移除圖像雜訊，同時保持邊緣清晰度。

        Args:
            image: 圖像 numpy 陣列（BGR 或灰階）
            kernel_size: Gaussian kernel 大小（必須是奇數），None 時使用配置預設值

        Returns:
            去噪後圖像

        Note:
            - kernel_size 越大，模糊效果越強，但可能失去細節
            - 建議範圍：3-9
            - 預設值 5 適合一般文件
        """
        # 使用配置預設值或傳入參數
        if kernel_size is None:
            kernel_size = self.config.gaussian_kernel_size

        # 確保是 numpy 陣列
        if not isinstance(image, np.ndarray):
            raise TypeError("image 必須是 numpy 陣列")

        # 確保 kernel size 是奇數
        if kernel_size % 2 == 0:
            kernel_size += 1

        # 複製圖像避免修改原始數據
        result = image.copy()

        # 使用 Gaussian blur 去噪
        # sigma=0 表示根據 kernel_size 自動計算
        denoised = cv2.GaussianBlur(result, (kernel_size, kernel_size), 0)

        return denoised

    def adjust_resolution(self, image: np.ndarray, target_dpi: int = None) -> np.ndarray:
        """
        調整解析度

        當圖像解析度低於目標 DPI 時放大圖像，使用高品質插值方法。

        Args:
            image: 圖像 numpy 陣列
            target_dpi: 目標 DPI，None 時使用配置預設值

        Returns:
            調整後圖像

        Algorithm:
            假設當前 DPI 為 current_dpi（從圖像大小推估）
            如果 current_dpi < target_dpi:
                scale_factor = target_dpi / current_dpi
                放大圖像
            否則:
                保持原樣

        Note:
            - 使用 INTER_CUBIC 插值（高品質）
            - 保持長寬比
            - 對於極小圖像，假設當前 DPI 較低
        """
        # 使用配置預設值或傳入參數
        if target_dpi is None:
            target_dpi = self.config.target_dpi

        # 確保是 numpy 陣列
        if not isinstance(image, np.ndarray):
            raise TypeError("image 必須是 numpy 陣列")

        # 複製圖像避免修改原始數據
        result = image.copy()

        # 推估當前 DPI
        # 假設標準文件大小為 A4 (210mm × 297mm)
        # 對於小圖像（< 500px），假設為低解析度掃描（~300 DPI）
        # 對於大圖像（>= 500px），假設接近目標解析度
        height, width = result.shape[:2]
        max_dim = max(height, width)

        # 根據圖像大小推估當前 DPI
        if max_dim < 500:
            # 小圖像，假設 300 DPI
            estimated_current_dpi = 300
        elif max_dim < 700:
            # 中等圖像，假設 600 DPI
            estimated_current_dpi = 600
        elif max_dim < 900:
            # 較大圖像，假設 900 DPI
            estimated_current_dpi = 900
        else:
            # 大圖像（>= 900px），假設已經是高解析度或接近
            estimated_current_dpi = 1500

        # 計算縮放比例
        if estimated_current_dpi < target_dpi:
            scale_factor = target_dpi / estimated_current_dpi

            # 計算新尺寸
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)

            # 使用雙三次插值放大（高品質）
            resized = cv2.resize(
                result,
                (new_width, new_height),
                interpolation=cv2.INTER_CUBIC
            )

            return resized
        else:
            # 已經是高解析度，保持不變
            return result
