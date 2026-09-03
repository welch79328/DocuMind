"""信心度只計必要欄位——選配欄位缺席不該扣分。

2026-09-04：謄本抽取器由 5 欄擴充到 23 欄後，extraction_confidence
從 0.54 掉到 0.196。但掉下去的那 10 欄（附屬建物、共有部分、他項權利、
查封註記等）是**這份謄本本來就沒有的東西**，不是抽取失敗。

其中 seizure_mark（查封註記）最極端：**沒有查封才是正常且理想的情況**，
把它的缺席計為信心度 0，會讓一份乾淨的謄本反而被判低信心。
"""

import asyncio

import pytest

from app.lib.multi_type_ocr.field_extraction_base import RegexFieldExtractor
from app.lib.multi_type_ocr.transcript_field_extractor import TranscriptFieldExtractor


class TestOptionalFieldsDoNotPenalise:
    def test_optional_fields_are_excluded_from_scoring(self):
        """選配欄位不進分母：只算必要欄位的平均"""
        ex = TranscriptFieldExtractor()
        result = asyncio.run(ex.extract("地號：1234", use_llm_fallback=False))

        required = set(TranscriptFieldExtractor.REQUIRED_FIELDS)
        # 分數應等於「必要欄位的平均」，而非全部 KEY_FIELDS 的平均
        conf = result["field_confidences"]
        expected = round(sum(conf[k] for k in required) / len(required), 4)
        assert result["extraction_confidence"] == expected

    def test_scoring_ignores_optional_zero_confidence(self):
        """加入更多抽不到的選配欄位，不應讓分數下降"""
        ex = TranscriptFieldExtractor()
        result = asyncio.run(ex.extract("地號：1234", use_llm_fallback=False))

        optional = set(TranscriptFieldExtractor.KEY_FIELDS) - set(
            TranscriptFieldExtractor.REQUIRED_FIELDS
        )
        assert optional, "測試前提：必須存在選配欄位"
        # 選配欄位確實都是 0（沒抽到），但沒有拉低分數
        assert all(result["field_confidences"][k] == 0.0 for k in optional)
        assert result["extraction_confidence"] > 0.0

    def test_seizure_mark_absence_is_not_penalised(self):
        """查封註記缺席是好消息，不得計入評分"""
        assert "seizure_mark" in TranscriptFieldExtractor.KEY_FIELDS
        assert "seizure_mark" not in TranscriptFieldExtractor.REQUIRED_FIELDS

    def test_optional_fields_still_returned_when_found(self):
        """不評分不代表不回傳——抽到就要給下游"""
        ex = TranscriptFieldExtractor()
        result = asyncio.run(
            ex.extract("其他登記事項：查封", use_llm_fallback=False)
        )
        assert result["seizure_mark"] == "查封"


class TestCoreFieldsStillRequired:
    """擴充不得讓核心欄位變成選配。"""

    @pytest.mark.parametrize(
        "field", ["land_number", "building_number", "area", "rights_scope", "owner"]
    )
    def test_core_five_remain_required(self, field):
        assert field in TranscriptFieldExtractor.REQUIRED_FIELDS


class TestBackwardCompatibility:
    """未宣告 REQUIRED_FIELDS 的抽取器行為不得改變。"""

    def test_falls_back_to_key_fields(self):
        class _Legacy(RegexFieldExtractor):
            KEY_FIELDS = ("a", "b")
            PATTERNS = {}

        assert _Legacy()._required_fields() == ("a", "b")

    def test_bill_extractor_unaffected(self):
        from app.lib.multi_type_ocr.bill_field_extractor import BillFieldExtractor

        ex = BillFieldExtractor()
        assert ex._required_fields() == BillFieldExtractor.KEY_FIELDS
