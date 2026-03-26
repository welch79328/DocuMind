"""
Type Definitions for OCR Enhanced Module

定義所有核心型別、Protocol 介面與型別別名。
確保型別安全與介面契約清晰。
"""

from typing import TypedDict, Protocol, Optional, Literal
import numpy as np


# ============================================================================
# Core Result Types
# ============================================================================

class OCRResult(TypedDict):
    """
    OCR 辨識結果

    Attributes:
        text: OCR 辨識文字
        page_count: 頁數
        quality_score: 品質分數 (0-100)
        confidence: 平均信心度 (0-1)
        metadata: 處理元數據
    """
    text: str
    page_count: int
    quality_score: float
    confidence: float
    metadata: dict


class ProcessingMetadata(TypedDict):
    """
    處理元數據

    記錄整個 OCR 處理流程的詳細資訊。

    Attributes:
        doc_type: 文件類型 (transcript/lease/id_card/unknown)
        preprocessing_applied: 是否套用預處理
        preprocessing_strategy: 預處理策略名稱
        ocr_engines_used: 使用的 OCR 引擎列表
        processing_time_ms: 總處理時間（毫秒）
        retry_count: 重試次數
        watermark_removed: 是否移除浮水印
        confidence_scores: 各引擎信心度字典
    """
    doc_type: str
    preprocessing_applied: bool
    preprocessing_strategy: str
    ocr_engines_used: list[str]
    processing_time_ms: int
    retry_count: int
    watermark_removed: bool
    confidence_scores: dict[str, float]


class EngineResult(TypedDict):
    """
    單一 OCR 引擎結果

    Attributes:
        engine: 引擎名稱 (paddleocr/tesseract/textract)
        text: 辨識文字
        confidence: 信心度 (0-1)
        processing_time_ms: 處理時間（毫秒）
    """
    engine: str
    text: str
    confidence: float
    processing_time_ms: int


# ============================================================================
# Quality Assessment Types
# ============================================================================

class QualityMetrics(TypedDict):
    """
    品質指標

    用於評估 OCR 結果的品質。

    Attributes:
        confidence_score: 信心度分數 (0-100)
        character_density: 字符密度 (0-1)
        field_match_rate: 欄位匹配率 (0-1)
        anomaly_rate: 異常字符比例 (0-1)
        overall_score: 總體分數 (0-100)
    """
    confidence_score: float
    character_density: float
    field_match_rate: float
    anomaly_rate: float
    overall_score: float


# ============================================================================
# Field Extraction Types
# ============================================================================

class ExtractedFields(TypedDict):
    """
    提取的謄本欄位

    Attributes:
        land_number: 地號 (格式: XXXX-XXXX)
        area: 面積（平方公尺）
        owner: 所有權人
        unified_id: 統一編號
        title_number: 權狀字號
        register_date: 登記日期（民國紀年）
        validation_status: 欄位驗證狀態 {field_name: is_valid}
    """
    land_number: Optional[str]
    area: Optional[float]
    owner: Optional[str]
    unified_id: Optional[str]
    title_number: Optional[str]
    register_date: Optional[str]
    validation_status: dict[str, bool]


# ============================================================================
# Strategy Protocol Interfaces
# ============================================================================

class PreprocessingStrategy(Protocol):
    """
    預處理策略介面

    定義預處理策略的統一介面，支援策略模式。

    使用範例:
        class CustomStrategy:
            def apply(self, image: np.ndarray) -> np.ndarray:
                # 自訂預處理邏輯
                return processed_image

        preprocessor = TranscriptPreprocessor(config)
        result = await preprocessor.preprocess(image, strategy=CustomStrategy())
    """

    def apply(self, image: np.ndarray) -> np.ndarray:
        """
        應用預處理策略

        Args:
            image: 輸入圖像（numpy 陣列）

        Returns:
            處理後的圖像（numpy 陣列）
        """
        ...


class OCREngine(Protocol):
    """
    OCR 引擎介面

    定義 OCR 引擎的統一介面。

    使用範例:
        class CustomEngine:
            async def extract_text(self, image: np.ndarray) -> tuple[str, float]:
                # 自訂 OCR 邏輯
                return text, confidence

        engine_manager.register_engine("custom", CustomEngine())
    """

    async def extract_text(self, image: np.ndarray) -> tuple[str, float]:
        """
        提取文字

        Args:
            image: 輸入圖像（numpy 陣列）

        Returns:
            (辨識文字, 信心度)
        """
        ...


# ============================================================================
# Type Aliases
# ============================================================================

# 文件類型字面量
DocumentType = Literal["transcript", "lease", "id_card", "unknown", "auto"]

# 融合方法字面量
FusionMethod = Literal["best", "weighted", "vote", "smart"]

# 二值化方法字面量
BinarizationMethod = Literal["gaussian", "mean", "sauvola"]

# OCR 引擎名稱字面量
OCREngineName = Literal["paddleocr", "tesseract", "textract"]


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    # Result Types
    "OCRResult",
    "ProcessingMetadata",
    "EngineResult",
    # Quality Types
    "QualityMetrics",
    # Field Types
    "ExtractedFields",
    # Protocol Interfaces
    "PreprocessingStrategy",
    "OCREngine",
    # Type Aliases
    "DocumentType",
    "FusionMethod",
    "BinarizationMethod",
    "OCREngineName",
]
