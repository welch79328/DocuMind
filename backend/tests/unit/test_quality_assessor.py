"""
測試統一信心度評估點 QualityAssessor(任務 1.2)

驗收標準:
- 產出整體信心度與低信心欄位清單
- 門檻可由設定檔調整,預設值來自 settings.OCR_QUALITY_THRESHOLD(0-1 尺度)
- 各 pipeline 可透過同一元件取得複核判定(needs_review)
"""

import pytest

from app.config import settings
from app.lib.document_types import DocumentType
from app.lib.ocr_enhanced.quality_assessor import QualityAssessor, QualityDecision


class TestThresholdConfiguration:
    """門檻可配置"""

    def test_default_threshold_from_settings(self):
        assessor = QualityAssessor()
        assert assessor.threshold == settings.OCR_QUALITY_THRESHOLD

    def test_default_threshold_is_confidence_scale(self):
        # 預設應為 0-1 信心度尺度(0.8),而非舊的 0-100
        assert 0.0 < QualityAssessor().threshold <= 1.0

    def test_explicit_threshold_override(self):
        assessor = QualityAssessor(threshold=0.9)
        assert assessor.threshold == 0.9

    def test_no_arg_construction_still_supported(self):
        # ocr_enhanced/__init__.py 以無參數建立,不可破壞
        assert QualityAssessor() is not None


class TestAssessDecision:
    """assess 產出整體信心度、低信心欄位、複核判定"""

    def setup_method(self):
        self.assessor = QualityAssessor(threshold=0.8)

    def test_returns_quality_decision_keys(self):
        decision = self.assessor.assess(ocr_confidence=0.95)
        assert set(decision.keys()) == {
            "overall_confidence", "needs_review", "low_confidence_fields"
        }

    def test_high_confidence_no_fields_passes(self):
        decision = self.assessor.assess(ocr_confidence=0.95)
        assert decision["needs_review"] is False
        assert decision["overall_confidence"] == 0.95
        assert decision["low_confidence_fields"] == []

    def test_low_ocr_confidence_triggers_review(self):
        decision = self.assessor.assess(ocr_confidence=0.62)
        assert decision["needs_review"] is True

    def test_low_confidence_field_listed_and_triggers_review(self):
        decision = self.assessor.assess(
            ocr_confidence=0.95,
            field_confidences={"area": 0.6, "owner": 0.92},
        )
        assert "area" in decision["low_confidence_fields"]
        assert "owner" not in decision["low_confidence_fields"]
        assert decision["needs_review"] is True

    def test_all_fields_above_threshold_passes(self):
        decision = self.assessor.assess(
            ocr_confidence=0.95,
            field_confidences={"area": 0.9, "owner": 0.88},
        )
        assert decision["needs_review"] is False
        assert decision["low_confidence_fields"] == []

    def test_overall_confidence_is_worst_case(self):
        # 整體信心度採保守(最差)值:min(ocr, 各欄位)
        decision = self.assessor.assess(
            ocr_confidence=0.9,
            field_confidences={"area": 0.72, "owner": 0.85},
        )
        assert decision["overall_confidence"] == pytest.approx(0.72)

    def test_threshold_boundary_is_inclusive_pass(self):
        # 恰好等於門檻視為通過(不低於門檻)
        decision = self.assessor.assess(ocr_confidence=0.8)
        assert decision["needs_review"] is False

    def test_accepts_optional_document_type(self):
        decision = self.assessor.assess(
            ocr_confidence=0.95,
            document_type=DocumentType.TRANSCRIPT,
        )
        assert decision["needs_review"] is False
