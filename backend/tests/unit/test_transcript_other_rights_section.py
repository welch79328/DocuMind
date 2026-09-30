"""
rights_scope / land_rights_scope 不得取到他項權利部的「設定權利範圍」(2026-09-23)

缺陷:他項權利部(抵押權等)印的是「設定權利範圍」,樣式 `(?<!歷次取得)權利範圍`
照樣命中。兩條路會把抵押權的範圍當成所有權的持分,信心度 0.9、不進複核:

  F2  沒有任何所有權部標題的頁(單獨的他項權利部頁)走 _scope_for 第 3 分支,
      退回全文比對。純土地謄本因此拿到抵押權的範圍,土地持分遞補也被擋掉
      (遞補只在 rights_scope 缺值時發生)。
  A1  所有權部那一行讀不出來時,比對範圍一路延伸到同頁的他項權利部。
      land_rights_scope(截到建物所有權部為止)與 rights_scope(從建物所有權部往後)
      都是如此。

修法兩道,各自獨立生效——任一道被 OCR 打壞時另一道還在:
  1. 區段:所有權部的比對範圍截到「他項權利部」標題為止。
  2. 樣式:`(?<!設定)`,不收「設定權利範圍」。

本檔對兩道各有一個「只有它擋得住」的案例,拿掉任一道都會有測試失敗。

固定案例保留相容碼位(㈯㆞、㈲、㆟),理由同 test_transcript_land_rights_scope。
"""

import pytest

from app.lib.multi_type_ocr.transcript_field_extractor import TranscriptFieldExtractor
from app.services.analyze_service import _merge_page_structured_data


# 抵押權的範圍刻意給 2分之1,與土地持分 4分之1、建物「全部」都不同,
# 取錯時才看得出來取到的是哪一筆。

LAND_ONLY_PAGE = """
*************  ㈯㆞標示部  ***************
    面　　積：******529.00平方公尺
    使用分區：山坡地保育區
*************  ㈯㆞所㈲權部  ***************
    （0001）登記次序：0001
      所㈲權㆟：某甲
    權利範圍：*********4分之1*********
"""

# 單獨一頁的他項權利部:沒有任何所有權部標題
OTHER_RIGHTS_PAGE = """
*************  ㈯㆞他項權利部  ***************
    （0001）登記次序：0002-000
    權利種類：抵押權
      權利㆟：某銀行
    設定權利範圍：*********2分之1*********
"""

# 只有「區段截斷」擋得住:OCR 把「設定」兩字讀丟,樣式的 (?<!設定) 無從作用
OTHER_RIGHTS_PAGE_PREFIX_LOST = """
*************  ㈯㆞他項權利部  ***************
    （0001）登記次序：0002-000
    權利種類：抵押權
    權利範圍：*********2分之1*********
"""

# 只有「樣式」擋得住:標題被 OCR 打壞,區段截斷找不到切點
OTHER_RIGHTS_PAGE_TITLE_MANGLED = """
*************  ㈯㆞他  權 部  ***************
    （0001）登記次序：0002-000
    權利種類：抵押權
    設定權利範圍：*********2分之1*********
"""

# A1:土地所有權部的權利範圍那一行讀不出來,同頁接著是他項權利部
LAND_SCOPE_UNREADABLE_THEN_MORTGAGE = """
*************  ㈯㆞所㈲權部  ***************
    （0001）登記次序：0001
      所㈲權㆟：某甲
*************  ㈯㆞他項權利部  ***************
    （0001）登記次序：0002-000
    權利種類：抵押權
    設定權利範圍：*********2分之1*********
"""

# 回歸:所有權部讀得到時,同頁有他項權利部也不影響
LAND_WITH_MORTGAGE = """
*************  ㈯㆞所㈲權部  ***************
    （0001）登記次序：0001
      所㈲權㆟：某甲
    權利範圍：*********4分之1*********
*************  ㈯㆞他項權利部  ***************
    （0001）登記次序：0002-000
    設定權利範圍：*********2分之1*********
"""

# A1 的建物版:建物所有權部的權利範圍讀不出來,同頁接著是建物他項權利部
BUILDING_SCOPE_UNREADABLE_THEN_MORTGAGE = """
*************  建物所㈲權部  ***************
    （0001）登記次序：0002
      所㈲權㆟：某甲
*************  建物他項權利部  ***************
    （0001）登記次序：0003-000
    權利種類：抵押權
    設定權利範圍：*********2分之1*********
"""

BUILDING_WITH_MORTGAGE = """
*************  建物所㈲權部  ***************
    （0001）登記次序：0002
    權利範圍：全部 *********1分之1*********
*************  建物他項權利部  ***************
    （0001）登記次序：0003-000
    設定權利範圍：*********2分之1*********
"""


def _fields(text: str) -> dict:
    fields, _ = TranscriptFieldExtractor()._extract_with_regex(text)
    return fields


async def _merged(*texts: str) -> dict:
    """走真實的逐頁抽取 → 跨頁合併,不模擬合併"""
    pages = []
    for t in texts:
        data = await TranscriptFieldExtractor().extract(t)
        pages.append({"ocr_raw": {"text": t, "confidence": 1.0}, "structured_data": data})
    return _merge_page_structured_data(pages)


class TestOtherRightsPageYieldsNothing:
    """F2:單獨的他項權利部頁不得提供 rights_scope"""

    def test_standalone_other_rights_page(self):
        assert _fields(OTHER_RIGHTS_PAGE)["rights_scope"] is None

    def test_section_cut_alone_blocks_it(self):
        """「設定」讀丟時,靠區段截斷擋下"""
        assert _fields(OTHER_RIGHTS_PAGE_PREFIX_LOST)["rights_scope"] is None

    def test_pattern_alone_blocks_it(self):
        """標題打壞時,靠樣式的 (?<!設定) 擋下"""
        assert _fields(OTHER_RIGHTS_PAGE_TITLE_MANGLED)["rights_scope"] is None

    async def test_pure_land_with_mortgage_page_gets_land_share(self):
        """純土地謄本加一頁抵押權:取土地持分,不是抵押權的 2分之1"""
        merged = await _merged(LAND_ONLY_PAGE, OTHER_RIGHTS_PAGE)
        assert merged["rights_scope"] == "4分之1"
        assert "rights_scope" not in merged["needs_confirmation"]

    async def test_mortgage_page_first_still_gets_land_share(self):
        """頁序顛倒也一樣:合併是先到先贏,他項頁在前時更容易取錯"""
        merged = await _merged(OTHER_RIGHTS_PAGE, LAND_ONLY_PAGE)
        assert merged["rights_scope"] == "4分之1"


class TestOwnershipScopeStopsAtOtherRights:
    """A1:所有權部那一行讀不出來時,比對範圍不得延伸進他項權利部"""

    def test_land_rights_scope_not_taken_from_mortgage(self):
        assert _fields(LAND_SCOPE_UNREADABLE_THEN_MORTGAGE)["land_rights_scope"] is None

    async def test_pure_land_stays_missing_for_review(self):
        """寧可缺值進複核,不可把抵押權的範圍遞補成 rights_scope"""
        merged = await _merged(LAND_SCOPE_UNREADABLE_THEN_MORTGAGE)
        assert merged.get("rights_scope") is None
        assert "rights_scope" in merged["needs_confirmation"]

    def test_building_rights_scope_not_taken_from_mortgage(self):
        assert _fields(BUILDING_SCOPE_UNREADABLE_THEN_MORTGAGE)["rights_scope"] is None


class TestReadableOwnershipUnchanged:
    """所有權部讀得到時,同頁有他項權利部不影響既有結果"""

    def test_land_share(self):
        assert _fields(LAND_WITH_MORTGAGE)["land_rights_scope"] == "4分之1"

    def test_building_scope(self):
        assert _fields(BUILDING_WITH_MORTGAGE)["rights_scope"] == "全部"

    async def test_merged_transcript_with_mortgages(self):
        """合併謄本、土地與建物都設定抵押:仍取建物的「全部」"""
        merged = await _merged(LAND_WITH_MORTGAGE, BUILDING_WITH_MORTGAGE)
        assert merged["rights_scope"] == "全部"
        assert merged["land_rights_scope"] == "4分之1"
