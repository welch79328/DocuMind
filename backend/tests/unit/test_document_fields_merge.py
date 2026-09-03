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


class TestMergedStatusIsRecomputed:
    """needs_confirmation / extraction_confidence 必須在彙整後重算。

    2026-09-04 實測：一份 4 頁謄本彙整後，document_fields 同時出現
        building_number = "00004-000"（p3 抽到，信心度 0.9）
        needs_confirmation 卻包含 building_number（沿用 p1 的清單）
    八個待確認欄位裡六個其實已經抽到——下游會把已知的值也丟給人工確認。

    原因是 _merge_fill_missing 對這兩個欄位採「取第一個非空值」，
    但它們描述的是「這一頁」的狀態，套到整份文件上是錯的。
    """

    def _pages(self):
        return [
            page({
                "land_number": "0555-0000",
                "building_number": None,
                "field_confidences": {"land_number": 0.9, "building_number": 0.0},
                "needs_confirmation": ["building_number"],
                "extraction_confidence": 0.45,
            }),
            page({
                "land_number": None,
                "building_number": "00004-000",
                "field_confidences": {"land_number": 0.0, "building_number": 0.9},
                "needs_confirmation": ["land_number"],
                "extraction_confidence": 0.45,
            }),
        ]

    def test_extracted_field_leaves_needs_confirmation(self):
        merged = _merge_page_structured_data(self._pages())
        assert "building_number" not in merged["needs_confirmation"]
        assert "land_number" not in merged["needs_confirmation"]

    def test_no_field_with_a_value_is_listed_for_confirmation(self):
        """核心不變量：待確認清單裡不得出現已經有值的欄位"""
        merged = _merge_page_structured_data(self._pages())
        for key in merged["needs_confirmation"]:
            assert not merged.get(key), f"{key} 已有值卻被列為待確認"

    def test_confidence_reflects_merged_state_not_first_page(self):
        """兩頁各抽到一半，合併後應高於任一頁的 0.45"""
        merged = _merge_page_structured_data(self._pages())
        assert merged["extraction_confidence"] > 0.45

    def test_genuinely_missing_field_stays_in_needs_confirmation(self):
        """真的沒抽到的欄位仍須列出——不能為了讓數字好看就全部清空"""
        pages = [
            page({
                "land_number": "0555-0000",
                "rights_scope": None,
                "field_confidences": {"land_number": 0.9, "rights_scope": 0.0},
                "needs_confirmation": ["rights_scope"],
            }),
        ]
        merged = _merge_page_structured_data(pages)
        assert "rights_scope" in merged["needs_confirmation"]
