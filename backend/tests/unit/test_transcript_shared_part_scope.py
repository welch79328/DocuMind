"""
公設(共有部分)的內容不得被當成本戶的欄位(2026-09-30)

線上實測(8 份公開範本送正式 DocuMind)抓到三個「公設串味」:

  1. building_number 取到公設的建號。士林範本本戶是 19998-000,
     回 11994-000——大字抬頭被 OCR 拆開、排到共有部分那一行後面,
     全文第一個「xxxxx-xxx建號」就成了公設那一筆。
  2. rights_scope 取到公設的權利範圍。只截到標示部的頁面沒有所有權部標題,
     走 _scope_for 第 3 條路退回全文,命中共有部分下一行的「權利範圍:5分之1」。
  3. floor_level 取到「建物層次:公共設施」——那是公設自己的其他登記事項。

另兩個同批抓到的位置錯誤:
  4. subsection / section 取到「重測前:大坑埔段大坑埔小段…」——那是舊地段。
  5. 「層數」被 OCR 讀成簡體「数」,total_floors 整個比不到。

以及文字層 PDF 的 completion_date:原文「建築完成㈰期」NFKC 後是「(日)」,
樣式寫死「日期」一次都比不到(2026-09-29 fresh verifier 抓到)。

固定案例直接取自正式環境對範本圖跑出的 OCR 原文(含 OCR 自己的錯字與斷行),
不要「順手修正」成乾淨的字——那樣就測不到真實輸入了。
範本來源:臺北市士林地政事務所「一分鐘看懂建物謄本」、高雄市政府地政局「土地及建物謄本導讀」圖九,
皆為地政機關公開的測試樣本(測試段、遮蔽姓名)。
"""

from app.lib.multi_type_ocr.transcript_field_extractor import TranscriptFieldExtractor


# 士林範本,正式環境 OCR 原文節錄。第一行大字抬頭被讀壞(「一十林區測試段一」),
# 本戶建號只剩續頁抬頭的「小段19998-000建號」,且排在共有部分之後。
SHILIN_BUILDING_OCR = """
一建物登記第二類謄本(所有權個人全部
一十林區測試段一
********************
建物標示部
********************
建物門牌:測試路439號五樓
建物坐落地號:測試段一小段0361-0000
主要用途:住家用
主要建材:鋼筋混凝土造
数:007層
層次面積
共有部分:測試段一小段11994-000建號****509.05平方公尺
權利範圍：
******1000分之193******
含車位編號2號，權利範圍：******1000分之55********
其他登記事項:使用執照字號：91使字第0101號
停車位共計：5位
其他登記事項:使用執照字號：91使字第0101號
*******************
建物所有權部
*******************
(0001)登記次序:0003
所有權人:皮**
權利範圍：全部*********
*********
林區測試段
小段19998-000建號
"""

# 高雄範本,正式環境 OCR 原文(只截到建物標示部,沒有所有權部)。
KCG_APARTMENT_OCR = """
建物標示部
登記日期：民國094年03月25日
建物坐落地號：吉慶段
主要用途：住家用
主要建材：鋼筋混凝上造
唇数：005唇
總面積：*****69.52平方公尺
次：五層
次面積：*****69.52平方公尺
建築完成日期：民國---年--月--日
附屬建物用途：陽台
面積：******8.71平方公尺
共有部分：吉慶段00697-000建號*****19.62平方公尺
權利範圍：*********5分之1*****冰***
其他登記事項：主要用途：水箱、樓梯問
建物層次：公共設施
使用執照字號：81瑞使40號
重测前：大坑埔段大坑埔小段01272-000建號
其他登記事項：使用執照字號：81瑞使40號
重测前：大坑埔段大坑埔小段01277-000建號
"""


def _fields(text: str) -> dict:
    fields, _ = TranscriptFieldExtractor()._extract_with_regex(text)
    return fields


class TestSharedPartIsNotTheUnit:

    def test_building_number_skips_shared_part(self):
        """士林:本戶 19998-000,不是公設 11994-000"""
        assert _fields(SHILIN_BUILDING_OCR)["building_number"] == "19998-000"

    def test_building_number_missing_rather_than_shared(self):
        """高雄:畫面上只有公設建號時寧可缺值,不能回公設的"""
        assert _fields(KCG_APARTMENT_OCR)["building_number"] is None

    def test_rights_scope_ignores_shared_part_scope(self):
        """高雄:只有標示部,rights_scope 不得是公設的 5分之1"""
        assert _fields(KCG_APARTMENT_OCR)["rights_scope"] is None

    def test_rights_scope_still_from_ownership_section(self):
        """士林:所有權部的「全部」照常取到"""
        assert _fields(SHILIN_BUILDING_OCR)["rights_scope"] == "全部"

    def test_floor_level_ignores_shared_part_floor(self):
        """「建物層次:公共設施」是公設自己的,不是本戶在幾樓"""
        assert _fields(KCG_APARTMENT_OCR)["floor_level"] != "公共設施"

    def test_floor_level_ignores_shared_floor_without_block_header(self):
        """第二道:OCR 漏掉「共有部分」那一行時,區塊切不出來,靠 (?<!建物) 擋"""
        assert _fields("建物層次：公共設施\n")["floor_level"] is None

    def test_shared_fields_still_extracted(self):
        """公設欄位本身不受影響"""
        f = _fields(SHILIN_BUILDING_OCR)
        assert f["shared_build_number"] == "11994-000"
        assert f["shared_area"] == "509.05"


class TestHistoricalLocationIgnored:

    def test_subsection_not_from_remeasure_line(self):
        """「重測前」是舊地段,不是現在的小段"""
        assert _fields(KCG_APARTMENT_OCR)["subsection"] != "大坑埔小段"

    def test_building_number_not_from_remeasure_line(self):
        """「重測前:…01272-000建號」是舊建號"""
        assert _fields(KCG_APARTMENT_OCR)["building_number"] != "01272-000"


class TestOcrLabelVariants:

    def test_total_floors_with_simplified_shu(self):
        """OCR 把「層數」讀成「数」(簡體)且吃掉「層」字"""
        assert _fields(SHILIN_BUILDING_OCR)["total_floors"] == "007層"

    def test_total_floors_traditional_unchanged(self):
        assert _fields("層　　數:004層\n")["total_floors"] == "004層"

    def test_page_number_is_not_a_floor(self):
        """放寬「層數」標籤時不能連「頁次」一起吃進來"""
        assert _fields("頁次:000001\n")["floor_level"] is None


class TestCompletionDateCompatibilityCodepoint:

    def test_compat_ri_matches(self):
        """文字層原文「建築完成㈰期」,NFKC 後是「(日)」"""
        f = _fields("建築完成㈰期:民國075年03㈪01㈰\n")
        assert f["completion_date"] is not None
        assert f["completion_date"].startswith("民國075年03")

    def test_plain_form_still_matches(self):
        assert _fields("建築完成日期:民國091年05月03日\n")["completion_date"] == (
            "民國091年05月03日"
        )


class TestHardeningFromVerifier:
    """2026-09-30 fresh verifier 提出的邊界,各鎖一個"""

    def test_collateral_list_section_is_kept(self):
        """共同擔保地號清單含本筆,段名可用;抬頭讀壞時它常是唯一來源"""
        f = _fields("小段0599-0000地號\n共同擔保地號:新峰段 0599-0000\n")
        assert f["section"] == "新峰段"
        assert f["land_number"] == "0599-0000"      # 仍取自抬頭,不是擔保清單

    def test_collateral_list_number_is_not_used(self):
        """擔保清單裡的編號可能是別筆,不能當本戶地號、建號

        ⚠️ 輸入刻意不放段名:「共同擔保地號:新峰段 0600-0000」這種寫法,
        段名本身就擋住了地號樣式,拿掉過濾照樣過——測不到過濾(verifier 抓到)。
        """
        f = _fields("共同擔保地號:0600-0000\n共同擔保建號:06373-000\n")
        assert f["land_number"] is None
        assert f["building_number"] is None

    def test_small_section_alone_is_not_a_section(self):
        """抬頭拆行剩「小段0361-0000地號」時,段名不可以是「小段」"""
        assert _fields("小段0361-0000地號\n")["section"] is None

    def test_shared_word_mid_line_does_not_start_block(self):
        """公設自己的謄本印「主要用途:共有部分」,不能把後面整段切掉"""
        f = _fields("主要用途:共有部分\n主要建材:鋼筋混凝土造\n總面積:****509.05平方公尺\n")
        assert f["main_material"] == "鋼筋混凝土造"
        assert f["total_area"] == "509.05"

    def test_block_stops_at_owner_list_when_heading_garbled(self):
        """區塊沒有自己的其他登記事項、所有權部標題又被讀壞時,不得改取到下一位"""
        text = (
            "共有部分:測試段00500-000建號****100.00平方公尺\n"
            "權利範圍:****1000分之193****\n"
            "建物所有楷部\n"
            "(0001)登記次序:0001\n"
            "所有權人:甲**\n"
            "權利範圍:****4分之1****\n"
            "(0002)登記次序:0002\n"
            "所有權人:乙**\n"
        )
        assert _fields(text)["owner"] == "甲**"

    def test_other_count_labels_are_not_floors(self):
        """放寬「層數」後,「筆數」「棟數」不可被當成層數"""
        assert _fields("筆數:002層\n棟數:001層\n")["total_floors"] is None
