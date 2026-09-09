"""
測試 rights_scope 取的是「建物」的權利範圍,不是土地的持分(2026-09-10)

缺陷:一份土地＋建物的合併謄本依序印「土地所有權部 → 土地所有權部 →
建物所有權部」,三段都有「權利範圍」。原本的正規式全文比對取第一個命中,
拿到土地的持分(4分之1);而下游把這個值填進契約的「專有部分 權利範圍」,
那個欄位的語意是建物(該份文件的正確值是「全部 1分之1」)。

⚠️ 只驗單頁建物謄本抓不到這個缺陷——單頁時全文比對剛好命中正確那筆。
本檔的固定案例刻意採「土地在前、建物在後」的版型。
"""

import pytest

from app.lib.multi_type_ocr.transcript_field_extractor import TranscriptFieldExtractor


# 依實際 PDF 的版面重建(去識別化)。「㈲」是謄本原文用的相容碼位,
# NFKC 之後會變成帶括號的「(有)」而不是「有」——這正是區段比對最容易踩的坑,
# 所以固定案例保留原始碼位,不要「順手改成正常的字」。
MERGED = """
*************  ㈯㆞所㈲權部  ***************
    （0001）登記次序：0005
      所㈲權㆟：某甲
    權利範圍：*********4分之1*********
    歷次取得權利範圍：*********4分之1*********

*************  ㈯㆞所㈲權部  ***************
    （0001）登記次序：0005
      所㈲權㆟：某甲
    權利範圍：*********4分之1*********
    歷次取得權利範圍：*********4分之1*********

*************  建物所㈲權部  ***************
    （0001）登記次序：0002
      所㈲權㆟：某甲
    權利範圍：全部 *********1分之1*********
"""

BUILDING_ONLY = """
*************  建物所㈲權部  ***************
    （0001）登記次序：0002
    權利範圍：全部 *********1分之1*********
"""

# 沒有任何區段標題的殘缺版面:應退回全文比對,而不是一個欄位都抽不到
NO_SECTION_HEADER = """
    （0001）登記次序：0002
    權利範圍：*********3分之2*********
"""


def _rights_scope(text: str):
    ex = TranscriptFieldExtractor()
    fields, _ = ex._extract_with_regex(text)
    return fields.get("rights_scope")


class TestRightsScopeSection:

    def test_merged_transcript_takes_building_not_land(self):
        """本案例的重點:土地在前、建物在後時,不可取到土地的 4分之1"""
        assert _rights_scope(MERGED) == "全部"   # 建物那筆,不是土地的 4分之1

    def test_building_only_still_works(self):
        """單張建物謄本不能因為加了區段限定而壞掉"""
        assert _rights_scope(BUILDING_ONLY) == "全部"

    def test_falls_back_to_full_text_without_header(self):
        """找不到區段標題時退回全文,而不是抽不到"""
        assert _rights_scope(NO_SECTION_HEADER) == "3分之2"

    def test_historical_value_is_not_picked_up(self):
        """「歷次取得權利範圍」是歷史值,不是現況,不得被當成答案"""
        only_historical = "    歷次取得權利範圍：*********8分之1*********\n"
        assert _rights_scope(only_historical) is None

    def test_returns_quan_bu_not_the_fraction(self):
        """建物印成「全部 1分之1」時回「全部」——本專案既有語意,勿改

        曾試著改成回「1分之1」,3 個既有測試立刻掛掉。「全部」與「1分之1」
        等價,而「全部」是契約用語。要改請先確認下游 JGB 那端。
        """
        assert _rights_scope(BUILDING_ONLY) == "全部"


class TestOwnerCompatibilityCodepoints:
    """owner 在真實謄本上一直抽不到,原因是 NFKC 把「㈲」正規化成「(有)」

    謄本原文寫「所㈲權㆟」,NFKC 之後是「所(有)權人」——**帶括號**。
    比對「所有權人」在真實文件上一次都比不到,而 owner 是必要欄位,
    抽不到就直接壓低信心度、把整份文件拖進人工複核。

    這一組固定案例保留原始相容碼位,不要「順手改成正常的字」——
    改掉就測不到這個缺陷了。
    """

    def test_compatibility_codepoint_form_is_matched(self):
        """謄本原文的「所㈲權㆟」形式必須抽得到"""
        assert _rights_scope  # 確保上方的輔助函式仍在(避免檔案被拆時失聯)
        ex = TranscriptFieldExtractor()
        fields, _ = ex._extract_with_regex("      所㈲權㆟：某甲\n")
        assert fields.get("owner") == "某甲"

    def test_plain_form_still_matched(self):
        """一般寫法不能因為放寬樣式而壞掉"""
        ex = TranscriptFieldExtractor()
        fields, _ = ex._extract_with_regex("      所有權人：某乙\n")
        assert fields.get("owner") == "某乙"

    def test_alternative_label_still_matched(self):
        """另一種標籤「登記名義人」維持可用"""
        ex = TranscriptFieldExtractor()
        fields, _ = ex._extract_with_regex("      登記名義人：某丙\n")
        assert fields.get("owner") == "某丙"


# 逐頁的版面。**正式管線是逐頁抽取再跨頁合併,不是整份一次抽。**
# 2026-09-10:只驗「整份文字」的測試會過,但線上仍回 4分之1——
# 因為土地頁自己抽出 4分之1、合併時「只填補缺值」先落地,建物頁補不進去。
LAND_PAGE = """
*************  ㈯㆞所㈲權部  ***************
    （0001）登記次序：0005
    權利範圍：*********4分之1*********
"""

BUILDING_PAGE = """
*************  建物所㈲權部  ***************
    （0001）登記次序：0002
    權利範圍：全部 *********1分之1*********
"""


class TestPerPageExtractionThenMerge:
    """這一組才是會抓到線上缺陷的測試——只驗整份文字抓不到"""

    def test_land_page_yields_nothing(self):
        """土地頁不得提供 rights_scope,否則合併時它會先落地並贏過建物頁"""
        assert _rights_scope(LAND_PAGE) is None

    def test_building_page_yields_the_value(self):
        assert _rights_scope(BUILDING_PAGE) == "全部"

    def test_merge_of_pages_takes_building(self):
        """模擬 _merge_page_structured_data 的「只填補缺值」:取第一個非空"""
        pages = [LAND_PAGE, LAND_PAGE, BUILDING_PAGE]
        values = [_rights_scope(p) for p in pages]
        merged = next((v for v in values if v), None)
        assert values == [None, None, "全部"]
        assert merged == "全部"
