"""
謄本必要欄位依「部」決定、原文空白回 null、列印時間——G4(2026-10-14)

驗收清單:.kiro/specs/transcript-section-required/acceptance.md(C1–C6)。

測試分兩類,每個類別名稱標明:
- TestNew*:新行為,修正前失敗、修正後通過。
- TestLocked*:鎖住現行行為,修正前後都通過。
"""

import pytest

from app.lib.multi_type_ocr.bill_field_extractor import BillFieldExtractor
from app.lib.multi_type_ocr.transcript_field_extractor import TranscriptFieldExtractor as T
from app.services.analyze_service import (
    _merge_page_structured_data,
    _scored_fields_from_pages,
)

# 建物謄本的一頁(電子謄本版型,帶框字照原文)
BUILDING_PAGE = """
     建物登記第二類謄本（建號全部）
      大安區仁愛段六小段 01921-000建號
    列㊞時間：民國101年07㈪11㈰09時46分                                頁次：1
  ***************  建物標示部  ****************
    建物門牌：長春路14之1號
    主要用途：（空白）
    主要建材：鋼筋混凝土造
    層　　數：010層          層　　次：五層
    總面積：*****120.50平方公尺   層次面積：*****120.50平方公尺
    建築完成㈰期：民國---年--㈪--㈰
  ***************  建物所㈲權部  ****************
    （0001）登記次序：0001
      所㈲權㆟：某甲
    權利範圍：全部 *********1分之1*********
"""

# 純土地謄本的一頁
LAND_PAGE = """
     ㈯㆞登記第㆓類謄本（所㈲權個㆟全部）
      大安區仁愛段㈥小段 0100-0006㆞號
    列㊞時間：民國108年04㈪02㈰08時43分                                頁次：1
  ***************  ㈯㆞標示部  ****************
    面　　積：*******64.00平方公尺
    使用分區：（空白）                             使用㆞類別：（空白）
  ***************  ㈯㆞所㈲權部  ****************
    （0001）登記次序：0050
      所㈲權㆟：某甲
    權利範圍：*********4分之1*********
"""

# 只有抬頭、沒有任何「部」標題與建物欄位的建物頁(長春路第 2 頁那種續頁)
TITLE_ONLY_BUILDING_PAGE = """
     建物登記第二類謄本（建號全部）
    （0002）登記次序：0003
      所㈲權㆟：某乙
"""

# 抬頭與標題都讀壞,但建物欄位還在
MANGLED_BUILDING_PAGE = """
*************  建 標 部  ***************
    建物門牌：大同路123號七樓
    主要用途：住家用
"""

# 抬頭、標題、建物欄位全讀壞的建物頁:文字上認不出是哪一部
UNIDENTIFIABLE_PAGE = """
*************  建  所  權部  ***************
    （0001）登記次序：0002
      所㈲權㆟：某甲
"""

# 只拍到他項權利部的裁切圖(範本 05 的形狀)
OTHER_RIGHTS_CROP = """
(0002)登記次序:0022-000
權利種類:普通抵押權
登記日期:民國100年07月22日
"""

BUILDING_ONLY = {k for k, v in T.FIELD_SECTION.items() if v == "building"} & set(T.REQUIRED_FIELDS)


async def _page(text: str) -> dict:
    return {"ocr_raw": {"text": text, "confidence": 1.0},
            "structured_data": await T().extract(text)}


class TestNewSectionRequired:
    async def test_building_page_does_not_require_land_use_zone(self):
        """C1:建物謄本不要求使用分區"""
        r = await T().extract(BUILDING_PAGE)
        assert "land_use_zone" not in r["needs_confirmation"]

    async def test_land_page_does_not_require_building_fields(self):
        """C2:純土地謄本不要求建物欄位"""
        r = await T().extract(LAND_PAGE)
        assert not BUILDING_ONLY & set(r["needs_confirmation"])
        # 頁層級的 rights_scope 留給合併層以土地持分遞補(既有設計),所以整份要看合併後
        merged = _merge_page_structured_data([await _page(LAND_PAGE)])
        assert merged["needs_confirmation"] == []
        assert merged["rights_scope"] == "4分之1"

    async def test_title_only_page_counts_as_building(self):
        """C3①:只有抬頭「建物登記第二類謄本」也認成建物"""
        r = await T().extract(TITLE_ONLY_BUILDING_PAGE)
        assert r["has_building_evidence"] is True
        assert "land_use_zone" not in r["needs_confirmation"]

    async def test_mangled_titles_but_fields_read(self):
        """C3②:標題讀壞但建物欄位有讀到,仍認成建物"""
        r = await T().extract(MANGLED_BUILDING_PAGE)
        assert "land_use_zone" not in r["needs_confirmation"]

    def test_both_derived_from_one_declaration(self, monkeypatch):
        """C3⑤:建物專屬必要欄位與建物跡證都由 FIELD_SECTION 推導,改一處兩者同步"""
        ex = T()
        assert set(ex._required_fields(LAND_PAGE, {"land_use_zone": 0.9})) == (
            set(T.REQUIRED_FIELDS) - BUILDING_ONLY)
        # 把 main_usage 改成「兩種都有」:土地頁就要求它,且讀到它不再算建物跡證
        monkeypatch.setattr(T, "FIELD_SECTION", {k: v for k, v in T.FIELD_SECTION.items()
                                                 if k != "main_usage"})
        assert "main_usage" in ex._required_fields(LAND_PAGE, {"land_use_zone": 0.9})
        assert ex._page_sections("", {"main_usage": 0.9}) == set()


class TestNewBlankMarker:
    @pytest.mark.parametrize("value", ["(空白)", "( 空白 )", "民國---年--月--日",
                                       "民國 年 月 日", "---", "***"])
    def test_blank_markers(self, value):
        from app.lib.multi_type_ocr.text_normalize import is_blank_marker
        assert is_blank_marker(value)

    @pytest.mark.parametrize("value", ["(一般註記)登記原因:增建", "民國084年02月日",
                                       "黃**", "民國九十年五月三日", "住家用", "", None])
    def test_not_blank_markers(self, value):
        from app.lib.multi_type_ocr.text_normalize import is_blank_marker
        assert not is_blank_marker(value)

    async def test_printed_blank_is_null_but_read(self):
        """C4:原文印空白 → 值 null、信心度 0.9、不進待確認(必填的主要用途也一樣)"""
        r = await T().extract(BUILDING_PAGE)
        for key in ("main_usage", "completion_date"):
            assert r[key] is None
            assert r["field_confidences"][key] == 0.9
            assert key not in r["needs_confirmation"]
        r = await T().extract(LAND_PAGE)
        assert r["land_use_zone"] is None and r["land_use_type"] is None
        assert r["field_confidences"]["land_use_zone"] == 0.9

    async def test_document_fields_after_merge(self):
        """C4:合併後 document_fields 也是 null,且不在待確認"""
        merged = _merge_page_structured_data([await _page(BUILDING_PAGE)])
        assert merged.get("main_usage") is None
        assert "main_usage" not in merged["needs_confirmation"]


class TestNewPrintDate:
    async def test_print_date(self):
        """C5:列印時間只取到日,格式同 completion_date"""
        assert (await T().extract(LAND_PAGE))["print_date"] == "民國108年04月02日"
        assert (await T().extract(BUILDING_PAGE))["print_date"] == "民國101年07月11日"

    async def test_missing_print_date_is_not_required(self):
        """C5:裁切圖沒有抬頭 → null,不進待確認"""
        r = await T().extract(MANGLED_BUILDING_PAGE)
        assert r["print_date"] is None
        assert "print_date" not in r["needs_confirmation"]


class TestLockedSafety:
    async def test_unidentified_page_requires_everything(self):
        """C3③:一部都認不出 → 全部要求(現行)"""
        r = await T().extract(OTHER_RIGHTS_CROP)
        assert set(r["needs_confirmation"]) == set(T.REQUIRED_FIELDS)

    async def test_land_page_plus_unidentifiable_building_page_still_reviewed(self):
        """C3④:土地頁＋完全認不出的建物頁 → 文件層仍要求建物欄位(0658077 的兜底)。

        這種文件會被拿土地持分遞補 rights_scope(_backfill_land_rights_scope 已知限制 1),
        唯一的攔截是複核。不能因為「整份只認出土地」就放掉建物欄位。
        """
        pages = [await _page(LAND_PAGE), await _page(UNIDENTIFIABLE_PAGE)]
        merged = _merge_page_structured_data(pages)
        assert BUILDING_ONLY <= set(merged["needs_confirmation"])
        assert BUILDING_ONLY <= _scored_fields_from_pages(pages)

    @pytest.mark.parametrize("text,key,value", [
        ("主要用途:(住家用)兼營業", "main_usage", "(住家用)兼營業"),
        ("建築完成日期:民國084年02月日", "completion_date", "民國084年02月日"),
        ("所有權人:黃**", "owner", "黃**"),
    ])
    async def test_counterexamples_keep_value(self, text, key, value):
        """反例:不是整個值的括號註記、有數字的日期、遮罩姓名——原值保留"""
        r = await T().extract(text)
        assert r[key] == value

    def test_bill_extractor_unchanged(self):
        """帳單抽取器沒有 REQUIRED_FIELDS:必要欄位仍是 KEY_FIELDS"""
        assert BillFieldExtractor()._required_fields() == BillFieldExtractor.KEY_FIELDS
