"""
統一信心度評估點 QualityAssessor

作為全系統唯一的信心度評估與複核判定入口,取代原先散落各處的硬編碼門檻。
所有 pipeline 皆透過本元件依可配置門檻(settings.OCR_QUALITY_THRESHOLD,0-1 尺度)
取得:整體信心度、低信心欄位清單、是否需人工複核。
"""

from __future__ import annotations

from typing import Dict, List, Optional, TypedDict

from app.config import settings
from app.lib.document_types import DocumentType


class QualityDecision(TypedDict):
    """
    信心度評估結果

    Attributes:
        overall_confidence: 整體信心度(0-1),採保守最差值
        needs_review: 是否需進入人工複核佇列
        low_confidence_fields: 低於門檻的欄位名稱清單
    """
    overall_confidence: float
    needs_review: bool
    low_confidence_fields: List[str]


class QualityAssessor:
    """
    品質(信心度)評估器

    以單一可配置門檻判定文件處理結果是否可信、是否需人工複核。
    """

    def __init__(self, threshold: Optional[float] = None):
        """
        Args:
            threshold: 信心度門檻(0-1);未提供時採 settings.OCR_QUALITY_THRESHOLD
        """
        self.threshold = (
            threshold if threshold is not None else settings.OCR_QUALITY_THRESHOLD
        )

    def assess(
        self,
        ocr_confidence: float,
        field_confidences: Optional[Dict[str, float]] = None,
        document_type: Optional[DocumentType] = None,
    ) -> QualityDecision:
        """
        評估處理結果並產出複核判定

        Args:
            ocr_confidence: OCR / 整體辨識信心度(0-1)
            field_confidences: 各欄位信心度 {欄位名: 信心度},可選
            document_type: 文件類型(保留供未來依類型調整門檻),可選

        Returns:
            QualityDecision:整體信心度、是否需複核、低信心欄位清單。
        """
        fields = field_confidences or {}

        low_confidence_fields = sorted(
            name for name, conf in fields.items() if conf < self.threshold
        )

        # 整體信心度採保守最差值:任一低信心欄位都應反映在整體
        if fields:
            overall_confidence = min(ocr_confidence, min(fields.values()))
        else:
            overall_confidence = ocr_confidence

        needs_review = (
            overall_confidence < self.threshold or bool(low_confidence_fields)
        )

        return {
            "overall_confidence": overall_confidence,
            "needs_review": needs_review,
            "low_confidence_fields": low_confidence_fields,
        }
