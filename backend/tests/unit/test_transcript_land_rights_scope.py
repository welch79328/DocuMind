"""
純土地謄本的 rights_scope 不得遺失,且不得因此在合併謄本上取到土地持分(2026-09-21)

缺陷:0658077 讓 rights_scope 在土地頁回空字串、等建物頁補值,防的是
合併謄本取到土地持分。但純土地謄本沒有建物頁,權利範圍因此永久遺失。

修法:抽取器另給 land_rights_scope(土地所有權部的持分)與 has_building_evidence
(這一頁有沒有建物跡證);合併層只在「每一頁都沒有建物跡證」時拿前者遞補。

⚠️ 本檔的重點是**反向**那兩個案例(合併謄本的建物頁抽不到值)。
遞補條件若寫成「rights_scope 缺值就補」,正向案例照樣會過,
但合併謄本會靜默拿到土地持分——正是 0658077 修掉的災情。

固定案例一律保留相容碼位(㈯㆞、㈲、㆟):旗標與區段比對都必須在 NFKC 之後做,
改成正常的字就測不到這一點了。

所有案例都走**真實**的逐頁抽取 → _merge_page_structured_data,不模擬合併。
"""

import pytest

from app.lib.multi_type_ocr.field_consensus import field_candidate_from_extraction
from app.lib.multi_type_ocr.transcript_field_extractor import TranscriptFieldExtractor
from app.services.analyze_service import (
    _merge_page_structured_data,
    _scored_fields_from_pages,
)


# 純土地謄本的一頁。「地上建物建號」刻意給真實格式的數字:
# 它屬於土地標示部,不可被當成建物跡證(building_number 以 (?<!地上建物) 排除)。
LAND_ONLY_PAGE = """
*************  ㈯㆞標示部  ***************
    面　　積：******529.00平方公尺
    使用分區：山坡地保育區
    地上建物建號：00032-000
*************  ㈯㆞所㈲權部  ***************
    （0001）登記次序：0001
      所㈲權㆟：某甲
    權利範圍：*********4分之1*********
    歷次取得權利範圍：*********8分之1*********
"""

# 合併謄本的土地頁,與 test_transcript_rights_scope.LAND_PAGE 同形
MERGED_LAND_PAGE = """
*************  ㈯㆞所㈲權部  ***************
    （0001）登記次序：0005
    權利範圍：*********4分之1*********
"""

MERGED_BUILDING_PAGE = """
*************  建物所㈲權部  ***************
    （0001）登記次序：0002
    權利範圍：全部 *********1分之1*********
"""

# 建物頁,兩個區段標題都被打壞(模擬 OCR 讀壞),但建物標示部的欄位還在。
# **刻意不含「權利範圍」這一行**:含的話,該頁既無建物標題也無土地標題,
# 會走 _scope_for 第 3 分支退回全文、抽出「全部」——那是正確值,
# 就測不到「偵測防護」本身了。
BUILDING_PAGE_TITLES_MANGLED = """
*************  建 標 部  ***************
    建物門牌：大同路123號七樓
    主要用途：住家用
    層　　次：七層           層次面積：*****62.46平方公尺
*************  建物所  權部  ***************
    （0001）登記次序：0002
      所㈲權㆟：某甲
"""

# 建物頁,標題完好、但沒有權利範圍這一行(該行讀不出來)。
# 除了標題之外沒有任何建物欄位——跡證完全來自標題比對,
# 因此也鎖住「標題必須在 NFKC 之後比對」這一點(㈲ 不正規化就比不到)。
BUILDING_PAGE_READABLE_NO_SCOPE = """
*************  建物所㈲權部  ***************
    （0001）登記次序：0002
      所㈲權㆟：某甲
"""


async def _page(text: str) -> dict:
    """走真實抽取器,組成與正式管線同形的頁面"""
    data = await TranscriptFieldExtractor().extract(text)
    return {"ocr_raw": {"text": text, "confidence": 1.0}, "structured_data": data}


async def _merged(*texts: str) -> tuple:
    pages = [await _page(t) for t in texts]
    return _merge_page_structured_data(pages), pages


class TestBuildingEvidenceFlag:

    async def test_land_only_page_has_no_building_evidence(self):
        """純土地頁:含「地上建物建號」也不可判定為有建物"""
        page = await _page(LAND_ONLY_PAGE)
        data = page["structured_data"]
        assert data["building_number"] is None
        assert data["has_building_evidence"] is False

    async def test_compatibility_codepoint_title_counts_as_evidence(self):
        """只有「建物所㈲權部」標題、沒有任何建物欄位,仍須判定為有建物"""
        page = await _page(BUILDING_PAGE_READABLE_NO_SCOPE)
        assert page["structured_data"]["has_building_evidence"] is True

    async def test_building_fields_count_when_titles_mangled(self):
        """標題全壞時,靠建物欄位(門牌、層次面積)判定"""
        page = await _page(BUILDING_PAGE_TITLES_MANGLED)
        data = page["structured_data"]
        assert data["building_address"] == "大同路123號七樓"
        assert data["has_building_evidence"] is True


class TestPureLandBackfill:

    async def test_pure_land_gets_land_share(self):
        """A1(a):純土地謄本的 rights_scope 取到土地持分"""
        merged, _ = await _merged(LAND_ONLY_PAGE)
        assert merged["rights_scope"] == "4分之1"

    async def test_backfilled_value_is_consistent(self):
        """A1(a):值、信心度、待確認三者一致——有值就不能還在待確認清單裡"""
        merged, _ = await _merged(LAND_ONLY_PAGE)
        fc = merged["field_confidences"]
        assert fc["rights_scope"] == fc["land_rights_scope"]
        assert fc["rights_scope"] > 0
        assert "rights_scope" not in merged["needs_confirmation"]

    async def test_historical_share_is_not_used(self):
        """「歷次取得權利範圍」是歷史值,土地持分同樣不得取到它"""
        merged, _ = await _merged(LAND_ONLY_PAGE)
        assert merged["land_rights_scope"] == "4分之1"   # 不是 8分之1


class TestMergedTranscriptNeverTakesLandShare:
    """合併謄本的建物頁抽不到值時,寧可缺值進複核,不得拿土地持分遞補"""

    async def test_titles_mangled_building_page_blocks_backfill(self):
        """A1(b):建物標題被打壞、該頁無權利範圍 → 維持缺值"""
        merged, _ = await _merged(MERGED_LAND_PAGE, BUILDING_PAGE_TITLES_MANGLED)
        assert merged.get("rights_scope") is None
        assert "rights_scope" in merged["needs_confirmation"]
        assert "4分之1" != merged.get("rights_scope")

    async def test_readable_title_without_scope_blocks_backfill(self):
        """A1(c):建物標題完好但該行缺值 → 維持缺值"""
        merged, _ = await _merged(MERGED_LAND_PAGE, BUILDING_PAGE_READABLE_NO_SCOPE)
        assert merged.get("rights_scope") is None
        assert "rights_scope" in merged["needs_confirmation"]
        assert "4分之1" != merged.get("rights_scope")

    async def test_normal_merged_transcript_still_takes_building(self):
        """A1(d):既有合併謄本行為不變——取建物的「全部」"""
        merged, _ = await _merged(
            MERGED_LAND_PAGE, MERGED_LAND_PAGE, MERGED_BUILDING_PAGE
        )
        assert merged["rights_scope"] == "全部"


class TestFlagIsMetadataNotAField:
    """has_building_evidence 是中繼資料:各頁 structured_data 會帶著它
    (同 llm_used_for_extraction),但絕不能被當成欄位。"""

    async def test_flag_not_in_document_fields(self):
        """合併結果(document_fields)不帶旗標——合併後的值只是第一頁的殘值"""
        merged, _ = await _merged(LAND_ONLY_PAGE)
        assert "has_building_evidence" not in merged
        merged, _ = await _merged(MERGED_LAND_PAGE, MERGED_BUILDING_PAGE)
        assert "has_building_evidence" not in merged

    async def test_flag_is_not_a_consensus_field(self):
        """共識模式:漏列 _META_KEYS 時旗標會變成欄位,拿到 0.0 信心度混進
        field_confidences 與共識比對(2026-09-21 verifier 實測抓到)"""
        page = await _page(MERGED_BUILDING_PAGE)
        candidate = field_candidate_from_extraction("paddleocr", page["structured_data"])
        assert "has_building_evidence" not in candidate["fields"]
        assert "has_building_evidence" not in candidate["field_confidences"]

    async def test_merge_is_idempotent_across_calls(self):
        """合併在 document_fields 與複核閘控各被呼叫一次,兩次結果必須相同。
        若合併時把旗標從各頁移除,第二次就無從判斷而不再遞補。"""
        _, pages = await _merged(LAND_ONLY_PAGE)
        first = _merge_page_structured_data(pages)
        second = _merge_page_structured_data(pages)
        assert first["rights_scope"] == second["rights_scope"] == "4分之1"


class TestNoScoringDrift:

    async def test_land_rights_scope_is_not_scored(self):
        """land_rights_scope 不得進入評分:否則所有含土地區段的謄本分數會無故上升"""
        _, pages = await _merged(
            MERGED_LAND_PAGE, MERGED_LAND_PAGE, MERGED_BUILDING_PAGE
        )
        assert "land_rights_scope" not in _scored_fields_from_pages(pages)
