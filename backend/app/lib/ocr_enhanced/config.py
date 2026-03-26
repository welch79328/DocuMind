"""
Configuration Module

配置管理模組，定義所有可調參數。
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PreprocessConfig:
    """
    預處理配置

    定義圖像預處理的所有可調參數。
    """

    enable_watermark_removal: bool = True
    enable_binarization: bool = False  # 預設關閉二值化（PaddleOCR 適合用灰階圖）
    enable_denoising: bool = False     # 預設關閉去噪（避免過度模糊）
    binarization_method: str = "gaussian"
    target_dpi: int = 1500
    # HSV 閾值調整：更寬鬆的紅色範圍以完整移除浮水印
    hsv_lower: tuple = (0, 30, 30)      # 降低 S, V 下限以捕捉更多紅色
    hsv_upper1: tuple = (15, 255, 255)  # 擴大 H 上限到 15
    hsv_upper2: tuple = (155, 255, 255) # 降低 H 下限到 155
    gaussian_kernel_size: int = 3       # 降低去噪核大小（如果啟用）


@dataclass
class EngineConfig:
    """
    OCR 引擎配置

    定義 OCR 引擎的所有可調參數。
    """

    engines: Optional[list] = field(default=None)
    parallel: bool = False
    fusion_method: str = "best"
    paddleocr_lang: str = "chinese_cht"
    tesseract_lang: str = "chi_tra"
    tesseract_psm: int = 6

    def __post_init__(self):
        if self.engines is None:
            self.engines = ["paddleocr", "tesseract"]


@dataclass
class QualityConfig:
    """
    品質評估配置

    定義品質評估的所有可調參數。
    """

    quality_threshold: float = 60.0
    max_retries: int = 3
    confidence_weight: float = 0.4
    density_weight: float = 0.2
    field_match_weight: float = 0.3
    anomaly_penalty: float = 0.1


# ========== 配置驗證函數 ==========

def validate_quality_config(config: QualityConfig) -> None:
    """
    驗證品質配置參數

    Args:
        config: 品質配置物件

    Raises:
        ValueError: 配置參數無效
    """
    # 驗證 quality_threshold 範圍 (0-100)
    if not (0 <= config.quality_threshold <= 100):
        raise ValueError(
            f"quality_threshold 必須在 0-100 範圍內，當前值: {config.quality_threshold}"
        )

    # 驗證 max_retries 範圍 (0-10)
    if not (0 <= config.max_retries <= 10):
        raise ValueError(
            f"max_retries 必須在 0-10 範圍內，當前值: {config.max_retries}"
        )


def validate_engine_config(config: EngineConfig) -> None:
    """
    驗證引擎配置參數

    Args:
        config: 引擎配置物件

    Raises:
        ValueError: 配置參數無效
    """
    # 有效的引擎名稱
    valid_engines = ["paddleocr", "tesseract", "textract"]

    # 驗證引擎列表不為空
    if not config.engines or len(config.engines) == 0:
        raise ValueError(
            f"engines 列表不能為空，至少需要一個引擎。有效引擎: {', '.join(valid_engines)}"
        )

    # 驗證每個引擎名稱有效
    for engine in config.engines:
        if engine not in valid_engines:
            raise ValueError(
                f"無效的引擎名稱: {engine}。有效引擎: {', '.join(valid_engines)}"
            )

    # 驗證 fusion_method
    valid_fusion_methods = ["best", "weighted", "vote"]
    if config.fusion_method not in valid_fusion_methods:
        raise ValueError(
            f"無效的 fusion_method: {config.fusion_method}。"
            f"有效方法: {', '.join(valid_fusion_methods)}"
        )


def validate_preprocess_config(config: PreprocessConfig) -> None:
    """
    驗證預處理配置參數

    Args:
        config: 預處理配置物件

    Raises:
        ValueError: 配置參數無效
    """
    # 驗證 binarization_method
    valid_methods = ["gaussian", "mean", "sauvola"]
    if config.binarization_method not in valid_methods:
        raise ValueError(
            f"無效的 binarization_method: {config.binarization_method}。"
            f"有效方法: {', '.join(valid_methods)}"
        )

    # 驗證 target_dpi 範圍 (100-3000)
    if not (100 <= config.target_dpi <= 3000):
        raise ValueError(
            f"target_dpi 必須在 100-3000 範圍內，當前值: {config.target_dpi}"
        )

    # 驗證 HSV 閾值
    def validate_hsv_tuple(name: str, hsv: tuple) -> None:
        """驗證 HSV 元組的值範圍"""
        if len(hsv) != 3:
            raise ValueError(f"{name} 必須是包含 3 個值的元組")

        h, s, v = hsv

        # H (色相) 範圍: 0-180
        if not (0 <= h <= 180):
            raise ValueError(
                f"{name} 的 H (色相) 值必須在 0-180 範圍內，當前值: {h}"
            )

        # S (飽和度) 範圍: 0-255
        if not (0 <= s <= 255):
            raise ValueError(
                f"{name} 的 S (飽和度) 值必須在 0-255 範圍內，當前值: {s}"
            )

        # V (明度) 範圍: 0-255
        if not (0 <= v <= 255):
            raise ValueError(
                f"{name} 的 V (明度) 值必須在 0-255 範圍內，當前值: {v}"
            )

    validate_hsv_tuple("hsv_lower", config.hsv_lower)
    validate_hsv_tuple("hsv_upper1", config.hsv_upper1)
    validate_hsv_tuple("hsv_upper2", config.hsv_upper2)


def validate_config(
    preprocess_config: PreprocessConfig,
    engine_config: EngineConfig,
    quality_config: QualityConfig
) -> None:
    """
    驗證所有配置參數

    Args:
        preprocess_config: 預處理配置
        engine_config: 引擎配置
        quality_config: 品質配置

    Raises:
        ValueError: 任何配置參數無效
    """
    validate_preprocess_config(preprocess_config)
    validate_engine_config(engine_config)
    validate_quality_config(quality_config)
