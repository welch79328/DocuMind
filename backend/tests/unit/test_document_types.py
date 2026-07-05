"""
測試權威文件類型列舉與型別收斂(任務 1.1)

驗收標準:
- 四種型別以單一列舉定義(transcript / bill / contract / repair_photo)
- 舊型別體系(lease / lease_contract / repair_quote)可正規化為權威列舉
- 未知 / 空字串型別正規化為 None(供 API 拒絕)
- 型別-檔案格式相容性:修繕照片僅接受影像,不接受 PDF
- 工廠可接受權威列舉成員
"""

import pytest

from app.lib.document_types import (
    DocumentType,
    normalize_document_type,
    is_extension_allowed,
    SUPPORTED_EXTENSIONS,
)


class TestDocumentTypeEnum:
    """權威列舉定義"""

    def test_has_four_canonical_types(self):
        values = {t.value for t in DocumentType}
        assert values == {"transcript", "bill", "contract", "repair_photo"}

    def test_enum_member_equals_string_value(self):
        # str Enum:成員可與其字串值直接比較,確保向後相容
        assert DocumentType.TRANSCRIPT == "transcript"
        assert DocumentType.CONTRACT == "contract"


class TestNormalizeDocumentType:
    """型別正規化(收斂三處不一致的舊型別)"""

    @pytest.mark.parametrize("value,expected", [
        ("transcript", DocumentType.TRANSCRIPT),
        ("bill", DocumentType.BILL),
        ("contract", DocumentType.CONTRACT),
        ("repair_photo", DocumentType.REPAIR_PHOTO),
    ])
    def test_canonical_passthrough(self, value, expected):
        assert normalize_document_type(value) == expected

    def test_trims_and_lowercases(self):
        assert normalize_document_type("  Transcript ") == DocumentType.TRANSCRIPT

    @pytest.mark.parametrize("legacy,expected", [
        ("lease", DocumentType.CONTRACT),
        ("lease_contract", DocumentType.CONTRACT),
        ("repair_quote", DocumentType.BILL),
    ])
    def test_legacy_aliases_converge(self, legacy, expected):
        assert normalize_document_type(legacy) == expected

    @pytest.mark.parametrize("value", [None, "", "   ", "invoice", "id_card", "unknown"])
    def test_unknown_or_empty_returns_none(self, value):
        assert normalize_document_type(value) is None


class TestExtensionCompatibility:
    """型別-檔案格式相容性(需求 1.5)"""

    def test_supported_extensions_constant(self):
        assert SUPPORTED_EXTENSIONS == {".pdf", ".jpg", ".jpeg", ".png"}

    def test_repair_photo_rejects_pdf(self):
        assert is_extension_allowed(DocumentType.REPAIR_PHOTO, ".pdf") is False

    @pytest.mark.parametrize("ext", [".jpg", ".jpeg", ".png"])
    def test_repair_photo_accepts_images(self, ext):
        assert is_extension_allowed(DocumentType.REPAIR_PHOTO, ext) is True

    @pytest.mark.parametrize("ext", [".pdf", ".jpg", ".png"])
    def test_transcript_accepts_pdf_and_images(self, ext):
        assert is_extension_allowed(DocumentType.TRANSCRIPT, ext) is True

    def test_extension_check_is_case_insensitive(self):
        assert is_extension_allowed(DocumentType.TRANSCRIPT, ".PDF") is True


class TestFactoryAcceptsEnum:
    """工廠可接受權威列舉成員(向後相容,不破壞字串鍵)"""

    def test_get_processor_accepts_enum_member(self):
        from app.lib.multi_type_ocr.processor_factory import ProcessorFactory
        from app.lib.multi_type_ocr.processor import DocumentProcessor
        processor = ProcessorFactory.get_processor(DocumentType.TRANSCRIPT)
        assert isinstance(processor, DocumentProcessor)
