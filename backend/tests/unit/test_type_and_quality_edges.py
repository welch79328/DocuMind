"""
型別收斂與信心度評估的邊界/邊緣案例(任務 1.3)

補強任務 1.1 / 1.2 尚未明確涵蓋的邊界:
- 型別映射(大小寫、round-trip、id_card 無對應)
- 白名單「動態」產生(新註冊型別即時反映)
- 信心度門檻分流的臨界值(恰好等於、略低於門檻、空欄位)

對應需求: 1.1, 6.1, 6.6
"""

import pytest

from app.config import settings
from app.lib.document_types import (
    DocumentType,
    normalize_document_type,
    is_extension_allowed,
    LEGACY_TYPE_ALIASES,
)
from app.lib.ocr_enhanced.quality_assessor import QualityAssessor


# --------------------------------------------------------------------------- #
# 型別映射邊界
# --------------------------------------------------------------------------- #
class TestTypeMappingEdges:

    @pytest.mark.parametrize("raw,expected", [
        ("LEASE", DocumentType.CONTRACT),
        ("  Lease_Contract  ", DocumentType.CONTRACT),
        ("Repair_Quote", DocumentType.BILL),
    ])
    def test_legacy_alias_is_case_insensitive(self, raw, expected):
        assert normalize_document_type(raw) == expected

    def test_every_canonical_type_round_trips(self):
        for dt in DocumentType:
            assert normalize_document_type(dt.value) is dt

    def test_normalize_returns_document_type_instance(self):
        assert isinstance(normalize_document_type("transcript"), DocumentType)

    def test_id_card_has_no_canonical_mapping(self):
        # id_card 不在本規格四型別範圍,應無法正規化(需使用者改選)
        assert normalize_document_type("id_card") is None
        assert "id_card" not in LEGACY_TYPE_ALIASES

    def test_repair_photo_rejects_uppercase_pdf(self):
        assert is_extension_allowed(DocumentType.REPAIR_PHOTO, ".PDF") is False


# --------------------------------------------------------------------------- #
# 白名單「動態」產生
# --------------------------------------------------------------------------- #
class TestDynamicWhitelist:

    def test_newly_registered_type_appears_in_supported(self):
        from app.lib.multi_type_ocr.processor_factory import ProcessorFactory
        from app.lib.multi_type_ocr.processor import DocumentProcessor

        class _TempProcessor(DocumentProcessor):
            async def preprocess(self, image):
                return image

            async def extract_text(self, image):
                return ("", 1.0)

            async def postprocess(self, text, confidence, image_data=None):
                return (text, {})

            async def extract_fields(self, text, image_data=None, enable_llm=False):
                return {}

        assert "temp_type" not in ProcessorFactory.supported_types()
        try:
            ProcessorFactory.register_processor("temp_type", _TempProcessor)
            # 白名單應「即時」反映新註冊的型別,而非寫死
            assert "temp_type" in ProcessorFactory.supported_types()
        finally:
            ProcessorFactory._processors.pop("temp_type", None)

        # 清理後不應殘留
        assert "temp_type" not in ProcessorFactory.supported_types()

    def test_default_registered_types_present(self):
        from app.lib.multi_type_ocr.processor_factory import ProcessorFactory
        supported = ProcessorFactory.supported_types()
        assert "transcript" in supported
        assert "contract" in supported


# --------------------------------------------------------------------------- #
# 信心度門檻分流臨界值
# --------------------------------------------------------------------------- #
class TestThresholdBoundaries:

    def setup_method(self):
        self.assessor = QualityAssessor(threshold=0.8)

    def test_just_below_threshold_triggers_review(self):
        decision = self.assessor.assess(ocr_confidence=0.7999)
        assert decision["needs_review"] is True

    def test_exactly_at_threshold_field_is_not_low(self):
        decision = self.assessor.assess(
            ocr_confidence=0.95,
            field_confidences={"area": 0.8},
        )
        assert decision["low_confidence_fields"] == []
        assert decision["needs_review"] is False

    def test_empty_field_dict_behaves_like_none(self):
        d_empty = self.assessor.assess(ocr_confidence=0.9, field_confidences={})
        d_none = self.assessor.assess(ocr_confidence=0.9, field_confidences=None)
        assert d_empty == d_none

    def test_multiple_low_fields_returned_sorted(self):
        decision = self.assessor.assess(
            ocr_confidence=0.95,
            field_confidences={"owner": 0.5, "area": 0.6, "land_no": 0.4},
        )
        assert decision["low_confidence_fields"] == ["area", "land_no", "owner"]

    def test_overall_reflects_lowest_ocr_when_ocr_is_worst(self):
        decision = self.assessor.assess(
            ocr_confidence=0.55,
            field_confidences={"area": 0.9},
        )
        assert decision["overall_confidence"] == pytest.approx(0.55)

    def test_settings_default_threshold_is_confidence_scale(self):
        # config 校正生效:預設門檻為 0-1 尺度的 0.8
        assert settings.OCR_QUALITY_THRESHOLD == 0.8
        assert QualityAssessor().threshold == 0.8
