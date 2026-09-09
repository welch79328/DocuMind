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
        assert _rights_scope(MERGED) == "1分之1"

    def test_building_only_still_works(self):
        """單張建物謄本不能因為加了區段限定而壞掉"""
        assert _rights_scope(BUILDING_ONLY) == "1分之1"

    def test_falls_back_to_full_text_without_header(self):
        """找不到區段標題時退回全文,而不是抽不到"""
        assert _rights_scope(NO_SECTION_HEADER) == "3分之2"

    def test_historical_value_is_not_picked_up(self):
        """「歷次取得權利範圍」是歷史值,不是現況,不得被當成答案"""
        only_historical = "    歷次取得權利範圍：*********8分之1*********\n"
        assert _rights_scope(only_historical) is None

    def test_quan_bu_prefix_is_skipped_for_the_fraction(self):
        """建物印成「全部 1分之1」,取分數而非「全部」——與土地的表示法一致"""
        assert _rights_scope(BUILDING_ONLY) != "全部"


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
