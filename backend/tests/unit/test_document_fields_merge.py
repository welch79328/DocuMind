"""跨頁欄位彙整：_merge_page_structured_data / _merge_fill_missing

2026-09-03 發現：謄本關鍵欄位散在多頁，單頁 structured_data 必然殘缺，
但合起來是完整的。既有的 `_answer_question` 已經做過一次合併
（`all_structured.update(structured)`），但那是「後蓋前」——若某頁把欄位
判成 None，會蓋掉前頁已抽對的值。改為「只填補缺值」並抽成獨立函式，
供 analyze() 的 `document_fields` 與 `_answer_question` 共用。
"""
import sys
sys.path.insert(0, "backend")

from app.services.analyze_service import (
    _merge_page_structured_data,
    _merge_fill_missing,
)


def page(structured):
    return {"structured_data": structured}


class TestFillsMissingAcrossPages:
    def test_scattered_fields_are_combined(self):
        """實測的真實情境：地號在 p1、建號在 p3"""
        pages = [
            page({"land_number": "0555-0000", "area": None, "owner": "林順山"}),
            page({}),
            page({"land_number": None, "building_number": "00004-000", "area": "1,924.86"}),
            page({}),
        ]
        merged = _merge_page_structured_data(pages)
        assert merged["land_number"] == "0555-0000"
        assert merged["building_number"] == "00004-000"
        assert merged["area"] == "1,924.86"
        assert merged["owner"] == "林順山"

    def test_all_pages_missing_structured_data_returns_none(self):
        pages = [{"structured_data": None}, {"ocr_raw": {}}]
        assert _merge_page_structured_data(pages) is None

    def test_empty_page_list_returns_none(self):
        assert _merge_page_structured_data([]) is None


class TestDoesNotOverwriteWithLaterEmptyValues:
    """核心修正點：後面頁面的 None / 空字串不得蓋掉前面已抽到的值。

    原始 `all_structured.update(structured)` 會被這個情境咬到。
    """

    def test_later_none_does_not_overwrite_earlier_value(self):
        pages = [
            page({"owner": "林順山"}),
            page({"owner": None}),
        ]
        assert _merge_page_structured_data(pages)["owner"] == "林順山"

    def test_later_empty_string_does_not_overwrite(self):
        pages = [page({"area": "3,406.98"}), page({"area": ""})]
        assert _merge_page_structured_data(pages)["area"] == "3,406.98"

    def test_earlier_missing_can_be_filled_by_later_page(self):
        pages = [page({"area": None}), page({"area": "1,924.86"})]
        assert _merge_page_structured_data(pages)["area"] == "1,924.86"


class TestNestedStructures:
    """合約是巢狀結構（parties.party_a），謄本是扁平——遞迴要處理兩者。"""

    def test_nested_dict_fields_are_merged_recursively(self):
        pages = [
            page({"parties": {"party_a": "台北科技有限公司", "party_b": None}}),
            page({"parties": {"party_a": None, "party_b": "新創軟體股份有限公司"}}),
        ]
        merged = _merge_page_structured_data(pages)
        assert merged["parties"]["party_a"] == "台北科技有限公司"
        assert merged["parties"]["party_b"] == "新創軟體股份有限公司"

    def test_nested_dict_does_not_get_overwritten_wholesale(self):
        """不能整個 dict 互相取代，否則第二頁的巢狀 dict 會蓋掉第一頁已填的欄位"""
        target: dict = {}
        _merge_fill_missing(target, {"parties": {"party_a": "A公司"}})
        _merge_fill_missing(target, {"parties": {"party_b": "B公司"}})
        assert target["parties"] == {"party_a": "A公司", "party_b": "B公司"}


class TestFieldConfidencesTakeMax:
    """信心度取各頁最高值，不是任意一頁的殘值。"""

    def test_higher_confidence_wins(self):
        pages = [
            page({"area": "x", "field_confidences": {"area": 0.3}}),
            page({"area": "x", "field_confidences": {"area": 0.9}}),
        ]
        assert _merge_page_structured_data(pages)["field_confidences"]["area"] == 0.9

    def test_lower_confidence_does_not_overwrite_higher(self):
        pages = [
            page({"area": "x", "field_confidences": {"area": 0.9}}),
            page({"area": "x", "field_confidences": {"area": 0.3}}),
        ]
        assert _merge_page_structured_data(pages)["field_confidences"]["area"] == 0.9
