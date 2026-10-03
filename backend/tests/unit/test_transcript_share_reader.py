"""
持分通用讀值器(2026-10-03,G1):頂層 rights_scope / land_rights_scope、owners、公設、車位共用一套規則

業主裁示「需通用處理方式,非特規」。原本五處各寫一套,各自漏不同的洞;
這裡的案例按「規則」分組,不是按「版面」:每一組驗的是一條通用規則在五處都成立。

  規則 1  值必須緊接標籤且長得像持分;「全部」後面接說明文字不算。輸出只留「分數」或「全部」。
  規則 2  標籤後同行沒值,下一行整行是持分才採用;下一行是別的標籤或文字就留空。
  規則 3  一筆資料只有一個欄位格:取第一個欄位格(標籤後接冒號或直接接值),讀不到就留空、不往後找;
          沒冒號的「權利範圍為全部時…」是說明文字,跳過。頂層欄位只認編號 (0001) 那一筆。
  子句    車位條款依自己的語法(括號未閉合、結尾分隔號、標籤後沒值)決定延續到哪一行。

OCR 固定案例取自正式環境對公開範本跑出的 rule_postprocessed 原文,不要順手修正。
"""

import pytest

from app.lib.multi_type_ocr.transcript_field_extractor import TranscriptFieldExtractor
from app.services.analyze_service import _merge_page_structured_data


async def _extract(text: str) -> dict:
    return await TranscriptFieldExtractor().extract(text)


async def _merged(*texts: str) -> dict:
    pages = [
        {"ocr_raw": {"text": t, "confidence": 1.0},
         "structured_data": await TranscriptFieldExtractor().extract(t)}
        for t in texts
    ]
    return _merge_page_structured_data(pages)


BUILDING_ENTRY = "建物所有權部\n(0001)登記次序:0001\n所有權人:王\n"
SHARED_HEADER = "某段00071-000建號\n共有部分:某段00500-000建號****100.00平方公尺\n"


async def _shared(body: str) -> dict:
    return (await _merged(SHARED_HEADER + body))["shared_parts"][0]


def _parking(number, scope, area):
    return [{"number": number, "rights_scope": scope, "share_area": area}]


# 瑞芳(06)建物所有權部:「全部1分之1」以前原樣輸出,truth.json 正解是「全部」
RUIFANG_OWNERSHIP_OCR = """建物所有權部
的舊地段建號

(0001)登記次序:0002
登記日期:民國087年01月20日
登記原因:買賣
所有權取得的原因
原因發生日期:民國087年01月03日
所有權人:王
統一編號:F1239
所有權人的身分資料
址:新北市測試區測試路100號
權利範圍:全部1分之1
所有權人的土地持分
"""


class TestRule1ValueMustLookLikeAShare:

    async def test_ruifang_quanbu_with_fraction_is_quanbu(self):
        d = await _extract(RUIFANG_OWNERSHIP_OCR)
        assert d["rights_scope"] == "全部"
        assert [o["rights_scope"] for o in d["owners"]] == ["全部"]

    @pytest.mark.parametrize("value", ["全部", "全部1分之1", "全部 *1分之1*", "全部冰", "******全部******"])
    async def test_quanbu_forms_read_as_quanbu_everywhere(self, value):
        d = await _extract(f"{BUILDING_ENTRY}權利範圍:{value}\n")
        assert d["rights_scope"] == "全部"
        assert d["owners"][0]["rights_scope"] == "全部"
        assert (await _shared(f"權利範圍:{value}\n"))["rights_scope"] == "全部"

    async def test_callout_in_the_slot_is_not_the_value_top_level(self):
        """欄位格裡是說明文字:讀不到就留空,不往後找下一個標籤(規則 3)"""
        d = await _extract(f"{BUILDING_ENTRY}權利範圍:全部時表示單獨所有\n權利範圍:2分之1\n")
        assert d["rights_scope"] is None

    async def test_callout_is_not_the_value_owners(self):
        d = await _extract(f"{BUILDING_ENTRY}權利範圍:全部時表示單獨所有\n")
        assert d["owners"][0]["rights_scope"] is None

    async def test_callout_in_the_slot_is_not_the_value_shared(self):
        p = await _shared("權利範圍:全部時表示單獨所有\n權利範圍:100分之10\n")
        assert (p["rights_scope"], p["share_area"]) == (None, None)

    async def test_colonless_mention_is_prose_and_skipped(self):
        """「權利範圍為全部時…」沒有冒號、不是欄位格:跳過,後面的欄位格照讀"""
        d = await _extract(f"{BUILDING_ENTRY}權利範圍為全部時表示單獨所有\n權利範圍:2分之1\n")
        assert d["rights_scope"] == "2分之1"
        assert d["owners"][0]["rights_scope"] == "2分之1"

    async def test_noise_after_fraction_is_dropped_top_level(self):
        assert (await _extract(f"{BUILDING_ENTRY}權利範圍:5分之1冰\n"))["rights_scope"] == "5分之1"


class TestRule2FoldedValue:

    async def test_next_line_label_is_never_the_value(self):
        """以前跨行抓到「住址:台北市」當持分"""
        d = await _extract(f"{BUILDING_ENTRY}權利範圍:\n住址:台北市\n")
        assert d["rights_scope"] is None
        assert d["owners"][0]["rights_scope"] is None

    async def test_share_only_next_line_is_used(self):
        d = await _extract(f"{BUILDING_ENTRY}權利範圍:\n*****2分之1*****\n")
        assert d["rights_scope"] == "2分之1"
        assert d["owners"][0]["rights_scope"] == "2分之1"


class TestRule3OneOwnershipEntry:
    """共有時第一位讀不到,絕不拿第二位的持分(看似合法、不進複核的錯值)"""

    CO_OWNED = ("(0001)登記次序:0001\n所有權人:王\n權利範圍:\n住址:台北市\n"
                "(0002)登記次序:0002\n所有權人:李\n權利範圍:2分之1\n")

    async def test_building(self):
        d = await _extract("建物所有權部\n" + self.CO_OWNED)
        assert d["rights_scope"] is None
        assert [o["rights_scope"] for o in d["owners"]] == [None, "2分之1"]

    async def test_land_only_backfill(self):
        """純土地謄本:land_rights_scope 與合併層遞補的 rights_scope 都不能是第二位的"""
        mark = "某段0361-0000地號\n土地標示部\n面積:****359.00平方公尺\n"
        merged = await _merged(mark, mark + "土地所有權部\n" + self.CO_OWNED)
        assert merged.get("land_rights_scope") in (None, "")
        assert merged.get("rights_scope") in (None, "")

    async def test_callout_before_first_entry_is_skipped(self):
        d = await _extract("建物所有權部\n權利範圍為全部時表示單獨所有\n"
                           "(0001)登記次序:0001\n所有權人:王\n權利範圍:2分之1\n")
        assert d["rights_scope"] == "2分之1"


class TestParkingClause:

    async def test_label_and_value_each_wrapped(self):
        """以前「100分之3」被當成公設持分,車位反而留空"""
        p = await _shared("含車位編號2號,\n權利範圍:\n100分之3\n")
        assert (p["rights_scope"], p["share_area"]) == (None, None)
        assert p["parking"] == _parking("2號", "100分之3", "3.00")

    async def test_wrapped_after_unit_scope(self):
        p = await _shared("權利範圍:100分之10\n含車位編號2號,\n權利範圍:\n100分之3\n")
        assert p["rights_scope"] == "100分之10"
        assert p["parking"] == _parking("2號", "100分之3", "3.00")

    async def test_wrapped_value_on_label_line(self):
        p = await _shared("(含車位編號2號,\n權利範圍:100分之3)\n")
        assert (p["rights_scope"], p["share_area"]) == (None, None)
        assert p["parking"] == _parking("2號", "100分之3", "3.00")

    async def test_clause_label_value_folded(self):
        p = await _shared("權利範圍:100分之10\n含車位編號2號,權利範圍:\n100分之3\n")
        assert p["rights_scope"] == "100分之10"
        assert p["parking"] == _parking("2號", "100分之3", "3.00")

    @pytest.mark.parametrize("prefix", ["", "其他登記事項:"])
    async def test_unclosed_paren_without_separator(self, prefix):
        p = await _shared(f"權利範圍:*****\n{prefix}(含停車位編號7號\n權利範圍:100分之3)\n")
        assert p["rights_scope"] != "100分之3"
        assert p["parking"] == _parking("7號", "100分之3", "3.00")

    async def test_finished_clause_does_not_take_next_line(self):
        """車位在前、條款語法完整:下一行是公設持分,不歸車位"""
        p = await _shared("含車位編號7號\n權利範圍:100分之10\n")
        assert p["rights_scope"] == "100分之10"
        assert p["parking"] == _parking("7號", None, None)

    async def test_finished_paren_clause_does_not_take_next_line(self):
        p = await _shared("(含車位編號7號)\n權利範圍:100分之10\n")
        assert p["rights_scope"] == "100分之10"
        assert p["parking"] == _parking("7號", None, None)

    async def test_never_takes_another_clause_share(self):
        p = await _shared("含車位編號2號,\n含車位編號3號,權利範圍:100分之3\n")
        assert p["parking"] == _parking("2號", None, None) + _parking("3號", "100分之3", "3.00")

    async def test_clause_inside_other_items_line(self):
        p = await _shared("權利範圍:*****\n其他登記事項:(含停車位編號7號,權利範圍:100分之3)\n")
        assert p["rights_scope"] is None
        assert p["parking"] == _parking("7號", "100分之3", "3.00")

    async def test_clause_with_eaten_han_is_still_a_clause(self):
        """「含」被 OCR 吃掉:仍是車位子句,它的持分不能當公設持分"""
        p = await _shared("權利範圍:\n車位編號7號權利範圍100分之3\n")
        assert (p["rights_scope"], p["share_area"]) == (None, None)
        assert p["parking"] == _parking("7號", "100分之3", "3.00")

    @pytest.mark.parametrize("note", ["(不含車位)", "(車位另計)"])
    async def test_empty_clause_is_not_a_parking_item(self, note):
        """以前「不含車位」產生全空一筆、「車位另計」讓公設持分整行放棄"""
        p = await _shared(f"權利範圍:100分之10{note}\n")
        assert p["rights_scope"] == "100分之10"
        assert p["parking"] == []

    async def test_parking_total_is_not_a_clause(self):
        p = await _shared("停車位共計:5位\n權利範圍:100分之10\n")
        assert (p["rights_scope"], p["parking"], p["parking_total"]) == ("100分之10", [], "5位")


class TestRuleBoundaries:
    """每條規則各自鎖住:拿掉任一條,這裡至少一個測試會失敗"""

    async def test_share_must_be_right_after_label(self):
        """標籤後先是別的文字、後面才出現分數:不是持分"""
        d = await _extract(f"{BUILDING_ENTRY}權利範圍:見第3頁,例如1000分之5\n")
        assert d["rights_scope"] is None
        assert d["owners"][0]["rights_scope"] is None
        assert (await _shared("權利範圍:見第3頁,例如1000分之5\n"))["rights_scope"] is None

    async def test_closed_paren_ends_clause_even_without_value(self):
        """括號已閉合:下一行的分數不再屬於這個車位"""
        p = await _shared("(含車位編號7號,權利範圍:)\n100分之10\n")
        assert p["parking"] == _parking("7號", None, None)

    async def test_clause_ends_once_it_has_its_share(self):
        """車位持分讀到後即結束,即使後面多一個逗號;下一行是公設持分"""
        p = await _shared("含停車位編號7號,權利範圍:100分之3,\n權利範圍:100分之10\n")
        assert p["rights_scope"] == "100分之10"
        assert p["parking"] == _parking("7號", "100分之3", "3.00")

    @pytest.mark.parametrize("body", [
        "權利範圍:100分之10\n含車位編號2號,\n說明各70分之1\n",
        "權利範圍:100分之10\n(含車位編號2號\n說明各70分之1)\n",
        "權利範圍:100分之10\n(含車位編號2號,見1000分之5說明)\n",
    ])
    async def test_unlabelled_fraction_in_prose_is_not_parking_share(self, body):
        """沒有標籤、夾在說明文字裡的分數不是車位持分(verifier 2026-10-03)"""
        p = await _shared(body)
        assert p["rights_scope"] == "100分之10"
        assert p["parking"] == _parking("2號", None, None)

    async def test_unlabelled_share_only_continuation_line(self):
        """折到下一行、整行只有持分:照樣是車位持分(規則 2)"""
        p = await _shared("權利範圍:100分之10\n含車位編號2號,\n1000分之55\n")
        assert p["parking"] == _parking("2號", "1000分之55", "5.50")


class TestClauseIdentityAndBrackets:
    """verifier 2026-10-03 第二輪:內部括號、只提到車位的行"""

    HEADER_WITH_SCOPE = "某段00071-000建號\n共有部分:某段00500-000建號 100.00平方公尺 權利範圍:10000分之150\n"

    @pytest.mark.parametrize("clause, number, scope, area", [
        ("其他登記事項:含停車位(平面式)編號B1-7號,權利範圍:10000分之80", "B1-7號", "10000分之80", "0.80"),
        ("(含停車位編號(B1)7號,權利範圍:100分之3)", None, "100分之3", "3.00"),
        ("含車位(編號7號),權利範圍:100分之3", "7號", "100分之3", "3.00"),
        ("含停車位(機械)編號7號,權利範圍:100分之3", "7號", "100分之3", "3.00"),
    ])
    async def test_inner_brackets_do_not_end_clause(self, clause, number, scope, area):
        p = (await _merged(self.HEADER_WITH_SCOPE + clause + "\n"))["shared_parts"][0]
        assert p["rights_scope"] != scope
        assert len(p["parking"]) == 1
        assert p["parking"][0]["rights_scope"] == scope
        assert p["parking"][0]["share_area"] == area
        if number:
            assert p["parking"][0]["number"] == number

    @pytest.mark.parametrize("mention", ["本共有部分無停車位,", "車位另計,", "(不含車位,"])
    async def test_mention_without_number_does_not_take_next_line(self, mention):
        tail = ")" if mention.startswith("(") else ""
        p = await _shared(f"{mention}\n權利範圍:10000分之150{tail}\n")
        assert p["rights_scope"] == "10000分之150"
        assert p["parking"] == []

    async def test_value_stops_at_next_label_on_same_line(self):
        """OCR 把兩欄併成一行:「全部 住址:台北市」仍是全部"""
        d = await _extract(f"{BUILDING_ENTRY}權利範圍:全部 住址:台北市\n")
        assert d["rights_scope"] == "全部"
        assert d["owners"][0]["rights_scope"] == "全部"

    @pytest.mark.parametrize("historical", ["歷次取得\n權利範圍:2分之1", "歷次取得 權利範圍:2分之1",
                                            "歷 次 取 得權利範圍:2分之1"])
    async def test_historical_label_split_by_ocr_is_still_excluded(self, historical):
        """「歷次取得」被折到上一行或插空白:仍是歷史值,不能被規則 3 撿到"""
        d = await _extract(f"{BUILDING_ENTRY}權利範圍:\n住址:x\n{historical}\n")
        assert d["rights_scope"] is None
        assert d["owners"][0]["rights_scope"] is None

    async def test_awaiting_clause_returns_non_share_line_to_unit(self):
        """車位標籤沒值、下一行不是整行持分:那一行退回公設,公設持分照讀"""
        p = await _shared("含車位編號2號,權利範圍:\n權利範圍:100分之10\n")
        assert p["rights_scope"] == "100分之10"
        assert p["parking"] == _parking("2號", None, None)


class TestMultiPageCoOwned:
    """verifier 2026-10-03 第三輪:跨頁共有,第一頁第一位讀不到時不能由第二頁的 (0002) 補上"""

    PAGE1 = "建物所有權部\n(0001)登記次序:0001\n所有權人:王\n權利範圍:{value}\n權狀字號:099北字第001234號\n"
    PAGE2 = "{heading}(0002)登記次序:0002\n所有權人:李\n權利範圍:2分之1\n"

    @pytest.mark.parametrize("value", ["", "****", "全 部", "1O分之1", "二分之一"])
    @pytest.mark.parametrize("heading", ["", "建物所有權部\n"])
    async def test_second_page_second_owner_never_fills(self, value, heading):
        merged = await _merged(self.PAGE1.format(value=value), self.PAGE2.format(heading=heading))
        assert merged.get("rights_scope") in (None, "")
        assert "rights_scope" in merged["needs_confirmation"]

    async def test_first_owner_on_second_page_is_still_read(self):
        """第一頁只有標示部、所有權部從第二頁 (0001) 開始:照讀"""
        mark = "某段00071-000建號\n建物標示部\n總面積:****75.63平方公尺\n"
        merged = await _merged(mark, "建物所有權部\n(0001)登記次序:0001\n所有權人:王\n權利範圍:全部\n")
        assert merged["rights_scope"] == "全部"


class TestFirstSlotIsFinal:
    """verifier 2026-10-03 第三輪 A1:第一個欄位格讀不到時,後面任何標籤都不採用——
    不論那是讀壞的「歷次取得」、說明框、還是下一筆;不靠排除字串"""

    @pytest.mark.parametrize("later", [
        "歷次取淂權利範圍:2分之1", "歷次取得:權利範圍:2分之1", "歷次取得\n住址:x\n權利範圍:2分之1",
        "其他登記事項:(權利範圍:2分之1)",
    ])
    async def test_unreadable_first_slot_never_falls_through(self, later):
        d = await _extract(f"{BUILDING_ENTRY}權利範圍:****\n住址:台北市1號\n{later}\n")
        assert d["rights_scope"] is None
        assert d["owners"][0]["rights_scope"] is None

    async def test_label_with_value_directly_is_a_slot(self):
        """冒號被 OCR 吃掉、標籤直接接持分:仍是欄位格"""
        d = await _extract(f"{BUILDING_ENTRY}權利範圍 1000分之193\n")
        assert d["rights_scope"] == "1000分之193"

    async def test_historical_label_as_first_label_is_not_read_as_mangled_label(self):
        """本筆只剩被折行的「歷次取得權利範圍」:完整標籤被排除後,不能改用讀壞標籤的寬鬆比對撿回來"""
        d = await _extract(f"{BUILDING_ENTRY}歷次取得\n權利範圍:2分之1\n")
        assert d["rights_scope"] is None
        assert d["owners"][0]["rights_scope"] is None


class TestClauseNeedsIdentity:
    """verifier 2026-10-03 第四輪:只是提到車位的字不是車位子句"""

    @pytest.mark.parametrize("body", [
        "無車位,權利範圍:100分之10\n", "車位:無 權利範圍:100分之10\n",
        "本共有部分無停車位 權利範圍:100分之10\n", "主要用途:停車位 權利範圍:100分之10\n",
        "不含車位,權利範圍:100分之10\n",
    ])
    async def test_mention_on_same_line_is_not_a_parking_item(self, body):
        """不成一筆幽靈車位;標籤前有車位字樣,公設持分也寧可留空(第二道防線)"""
        p = await _shared(body + "其他登記事項:主要用途:樓梯間\n")
        assert p["rights_scope"] is None
        assert p["parking"] == []

    async def test_legal_parking_mention_does_not_create_item(self):
        p = await _shared("權利範圍:\n其他登記事項:法定停車位,權利範圍:100分之3\n")
        assert p["parking"] == []
        assert p["rights_scope"] is None

    @pytest.mark.parametrize("clause", ["停車位(平面式)編號B1-7號,權利範圍:10000分之80",
                                        "車位 編號B1-7號,權利範圍:10000分之80"])
    async def test_number_without_han_is_still_a_clause(self, clause):
        p = await _shared(f"權利範圍:10000分之150\n{clause}\n")
        assert p["rights_scope"] == "10000分之150"
        assert p["parking"] == _parking("B1-7號", "10000分之80", "0.80")


class TestSlotLockAcrossPages:
    """verifier 2026-10-03 第四輪 F2:多張謄本一起上傳,第一張讀不到不能拿第二張的持分。
    合併層以「最先看到欄位格的那一頁」定案(analyze_service._lock_share_slots)"""

    TRANSCRIPT_A = ("某段00071-000建號\n建物所有權部\n(0001)登記次序:0001\n所有權人:王\n"
                    "權利範圍:{value}\n權狀字號:099北字第1號\n")
    TRANSCRIPT_B = "某段00072-000建號\n建物所有權部\n(0001)登記次序:0001\n所有權人:李\n權利範圍:2分之1\n"

    @pytest.mark.parametrize("value", ["****", ""])
    async def test_second_transcript_never_fills_first(self, value):
        merged = await _merged(self.TRANSCRIPT_A.format(value=value), self.TRANSCRIPT_B)
        assert merged.get("rights_scope") is None
        assert merged["field_confidences"]["rights_scope"] == 0.0
        assert "rights_scope" in merged["needs_confirmation"]
        assert "share_slots" not in merged

    async def test_two_transcripts_that_disagree_leave_it_empty(self):
        """兩張建物謄本持分不同:頂層沒有唯一正解,留空進複核(各張在 owners 裡)"""
        merged = await _merged(self.TRANSCRIPT_A.format(value="3分之1"), self.TRANSCRIPT_B)
        assert merged.get("rights_scope") is None
        assert "rights_scope" in merged["needs_confirmation"]
        assert [o["rights_scope"] for o in merged["owners"]] == ["3分之1", "2分之1"]

    async def test_two_transcripts_that_agree_are_read(self):
        merged = await _merged(self.TRANSCRIPT_A.format(value="2分之1"), self.TRANSCRIPT_B)
        assert merged["rights_scope"] == "2分之1"

    async def test_title_repeated_on_next_page_is_same_transcript(self):
        """每頁都印抬頭:同一張謄本,不會被當成第二張而拿去比對一致性"""
        page1 = "某段00071-000建號\n建物所有權部\n(0001)登記次序:0001\n所有權人:王\n權利範圍:2分之1\n"
        page2 = "某段00071-000建號\n(0002)登記次序:0002\n所有權人:李\n權利範圍:3分之1\n"
        assert (await _merged(page1, page2))["rights_scope"] == "2分之1"

    async def test_value_on_next_page_is_not_borrowed(self):
        """第一筆資料的權利範圍落在下一頁:不補,留空進複核(第九輪 P1:分頁落在 (0002) 裡時,
        下一頁頂端是下一位的持分,兩種情況從文字上分不出來)"""
        page1 = "某段00071-000建號\n建物所有權部\n(0001)登記次序:0001\n所有權人:王\n"
        page2 = "權利範圍:2分之1\n權狀字號:099北字第1號\n"
        merged = await _merged(page1, page2)
        assert merged.get("rights_scope") is None
        assert "rights_scope" in merged["needs_confirmation"]

    @pytest.mark.parametrize("label", ["權利範圍丶2分之1", "權利範圍一2分之1", "權利範圍二分之一"])
    async def test_next_owner_share_on_next_page_is_never_used(self, label):
        """第九輪 P1:第一位讀壞、同頁接著 (0002)、下一頁頂端是 (0002) 的持分"""
        page1 = ("某段00071-000建號\n建物所有權部\n(0001)登記次序:0001\n所有權人:王\n"
                 f"{label}\n(0002)登記次序:0002\n所有權人:李\n")
        merged = await _merged(page1, "權利範圍:3分之1\n")
        assert merged.get("rights_scope") is None
        assert "rights_scope" in merged["needs_confirmation"]

    async def test_land_only_locked_slot_blocks_backfill(self):
        mark = "某段0361-0000地號\n土地標示部\n面積:****359.00平方公尺\n"
        land_a = mark + "土地所有權部\n(0001)登記次序:0001\n所有權人:王\n權利範圍:****\n"
        land_b = "某段0362-0000地號\n土地所有權部\n(0001)登記次序:0001\n所有權人:李\n權利範圍:2分之1\n"
        merged = await _merged(land_a, land_b)
        assert merged.get("land_rights_scope") is None
        assert merged.get("rights_scope") in (None, "")


class TestUnrecognisedClauseNeverFeedsSharedScope:
    """verifier 2026-10-03 第五輪:「含」被吃掉、編號寫法不緊接的車位條款,認不出來也不能變成公設持分"""

    @pytest.mark.parametrize("clause", [
        "停車位(地下二層機械式)編號7號,權利範圍:100分之3", "停車位,編號7號,權利範圍:100分之3",
        "(停車位B1-07號,權利範圍:10000分之80)", "停車位第7號權利範圍:100分之3",
        "車位B1-7號 權利範圍:100分之3", "(停車位(機械式)第7號,權利範圍:100分之3)",
    ])
    async def test_alone(self, clause):
        p = await _shared(clause + "\n")
        assert p["rights_scope"] is None
        assert p["share_area"] is None

    async def test_before_real_scope(self):
        p = await _shared("停車位(地下二層機械式)編號7號,權利範圍:100分之3\n權利範圍:100分之10\n")
        assert (p["rights_scope"], p["share_area"]) == ("100分之10", "10.00")

    async def test_parking_word_after_value_is_annotation(self):
        p = await _shared("權利範圍:100分之10 停車位第7號權利範圍:100分之3\n")
        assert p["rights_scope"] == "100分之10"


class TestMisreadSeparator:
    """verifier 2026-10-03 第六輪:冒號被 OCR 讀錯時,不能讓合併層改由另一張謄本定案"""

    A = "某段00071-000建號\n建物所有權部\n(0001)登記次序:0001\n所有權人:王\n權利範圍{sep}2分之1\n"
    B = "某段00072-000建號\n建物所有權部\n(0001)登記次序:0001\n所有權人:李\n權利範圍:3分之1\n"

    @pytest.mark.parametrize("sep", [";", "；", "|", "!", "l", "『", "∶", ":"])
    async def test_never_takes_second_transcript(self, sep):
        merged = await _merged(self.A.format(sep=sep), self.B)
        assert merged.get("rights_scope") in (None, "2分之1")
        if merged.get("rights_scope") is None:
            assert "rights_scope" in merged["needs_confirmation"]

    @pytest.mark.parametrize("sep", [";", "；", "|", "!", "∶", "『"])
    async def test_common_separators_are_read(self, sep):
        d = await _extract(BUILDING_ENTRY + f"權利範圍{sep}2分之1\n")
        assert d["rights_scope"] == "2分之1"
        assert d["owners"][0]["rights_scope"] == "2分之1"

    async def test_prose_after_label_is_still_prose(self):
        d = await _extract(BUILDING_ENTRY + "權利範圍為全部時表示單獨所有\n權利範圍:2分之1\n")
        assert d["rights_scope"] == "2分之1"


class TestStructuralLock:
    """verifier 2026-10-03 第七輪:合併層改依資料結構((0001) 資料開頭)定案,不看標籤讀得好不好"""

    A = "某段00071-000建號\n建物所有權部\n(0001)登記次序:0001\n所有權人:王\n{scope_line}\n權狀字號:099北字第1號\n"
    B = "某段00072-000建號\n建物所有權部\n(0001)登記次序:0001\n所有權人:李\n權利範圍:3分之1\n"

    @pytest.mark.parametrize("scope_line", [
        "權利範圍一2分之1", "權利範圍丶2分之1", "權利範圍丨2分之1", "權利範圍冫2分之1",
        "權利範圍為2分之1", "權利範圍二分之一", "利:2分之1", "權利範圍", "",
    ])
    async def test_second_transcript_never_fills_first(self, scope_line):
        merged = await _merged(self.A.format(scope_line=scope_line), self.B)
        assert merged.get("rights_scope") in (None, "2分之1")

    async def test_entry_page_without_slot_then_other_owner_page(self):
        """第一頁 (0001) 沒有欄位格、第二頁是 (0002):不補"""
        page1 = "某段00071-000建號\n建物所有權部\n(0001)登記次序:0001\n所有權人:王\n"
        page2 = "(0002)登記次序:0002\n所有權人:李\n權利範圍:2分之1\n"
        merged = await _merged(page1, page2)
        assert merged.get("rights_scope") is None
        assert "rights_scope" in merged["needs_confirmation"]

    async def test_continuation_then_new_transcript(self):
        """續頁補值後不再往後看;續頁之前若先出現另一張謄本則不補"""
        page1 = "某段00071-000建號\n建物所有權部\n(0001)登記次序:0001\n所有權人:王\n"
        merged = await _merged(page1, self.B, "權利範圍:2分之1\n")
        assert merged.get("rights_scope") is None

    async def test_land_section_same_rule(self):
        mark = "某段0361-0000地號\n土地標示部\n面積:****359.00平方公尺\n"
        land_a = mark + "土地所有權部\n(0001)登記次序:0001\n所有權人:王\n權利範圍一2分之1\n"
        land_b = "某段0362-0000地號\n土地所有權部\n(0001)登記次序:0001\n所有權人:李\n權利範圍:3分之1\n"
        merged = await _merged(land_a, land_b)
        assert merged.get("land_rights_scope") in (None, "2分之1")
        assert merged.get("rights_scope") in (None, "", "2分之1")

    async def test_slot_on_entry_page_is_final_even_if_next_page_looks_like_continuation(self):
        """定案頁已看到欄位格(讀不到):下一頁開頭的「權利範圍:」不是它的值,不補"""
        page1 = "某段00071-000建號\n建物所有權部\n(0001)登記次序:0001\n所有權人:王\n權利範圍:****\n"
        merged = await _merged(page1, "權利範圍:2分之1\n權狀字號:099北字第1號\n")
        assert merged.get("rights_scope") is None


class TestMisreadEntryIndex:
    """verifier 2026-10-03 第八輪:(0001) 被讀成 (0007) 時,另一張謄本不能補進來"""

    @pytest.mark.parametrize("index", ["0007", "0004"])
    async def test_building(self, index):
        a = f"某段00071-000建號\n建物所有權部\n({index})登記次序:0001\n所有權人:王\n權利範圍:2分之1\n"
        b = "某段00072-000建號\n建物所有權部\n(0001)登記次序:0001\n所有權人:李\n權利範圍:3分之1\n"
        merged = await _merged(a, b)
        assert merged.get("rights_scope") in (None, "2分之1")

    async def test_land_only(self):
        a = "某段0361-0000地號\n土地所有權部\n(0007)登記次序:0001\n所有權人:王\n權利範圍:4分之1\n"
        b = "某段0362-0000地號\n土地所有權部\n(0001)登記次序:0001\n所有權人:李\n權利範圍:5分之1\n"
        merged = await _merged(a, b)
        assert merged.get("land_rights_scope") in (None, "4分之1")
        assert merged.get("rights_scope") in (None, "", "4分之1")


class TestTranscriptGrouping:
    """合併層分組與一致性規則,各自鎖住"""

    A = "某段00071-000建號\n建物所有權部\n(0001)登記次序:0001\n所有權人:王\n權利範圍:{v}\n"
    B = "某段00072-000建號\n建物所有權部\n(0001)登記次序:0001\n所有權人:李\n權利範圍:{v}\n"

    async def test_second_transcript_unreadable_leaves_it_empty(self):
        """第二張讀不到:無從確認兩張一致,留空"""
        merged = await _merged(self.A.format(v="2分之1"), self.B.format(v="****"))
        assert merged.get("rights_scope") is None

    async def test_two_titles_on_one_page_leave_it_empty(self):
        page = self.A.format(v="2分之1") + self.B.format(v="2分之1")
        assert (await _merged(page)).get("rights_scope") is None

    async def test_new_entry_in_same_transcript_stops_continuation(self):
        """同一張:第一筆沒欄位格、接著是 (0002),之後的續頁不能補"""
        page1 = "某段00071-000建號\n建物所有權部\n(0001)登記次序:0001\n所有權人:王\n"
        page2 = "(0002)登記次序:0002\n所有權人:李\n權利範圍:2分之1\n"
        merged = await _merged(page1, page2, "權利範圍:3分之1\n")
        assert merged.get("rights_scope") is None

    async def test_untitled_first_page_belongs_to_next_title(self):
        """第一頁沒讀到抬頭、第二頁有:同一張謄本,不會被拆成兩張而因不一致留空"""
        page1 = "建物所有權部\n(0001)登記次序:0001\n所有權人:王\n權利範圍:2分之1\n"
        page2 = "某段00071-000建號\n(0002)登記次序:0002\n所有權人:李\n權利範圍:3分之1\n"
        assert (await _merged(page1, page2))["rights_scope"] == "2分之1"

    async def test_slot_without_entry_header_still_locks(self):
        """第一張的資料開頭沒讀到、欄位格讀不到:仍以它定案,第二張不能補"""
        a = "某段00071-000建號\n建物所有權部\n所有權人:王\n權利範圍:****\n"
        b = "某段00072-000建號\n建物所有權部\n(0001)登記次序:0001\n所有權人:李\n權利範圍:3分之1\n"
        assert (await _merged(a, b)).get("rights_scope") is None


class TestLLMFilledShareGoesToReview:
    """verifier 2026-10-03 第十輪:規則讀不到的持分由 LLM 補上時,一律進複核(業主裁示)。
    LLM 從整頁圖挑一個看得到的「權利範圍」,常是下一位所有權人的;原本給 0.8 剛好等於門檻,靜默送出"""

    @staticmethod
    async def _merged_with_llm(answer: str, *texts: str) -> dict:
        from unittest.mock import AsyncMock, MagicMock
        provider = MagicMock()
        provider.call = AsyncMock(return_value=answer)
        pages = []
        for t in texts:
            data = await TranscriptFieldExtractor(provider=provider).extract(
                t, image_data="BASE64", use_llm_fallback=True,
            )
            pages.append({"ocr_raw": {"text": t, "confidence": 1.0}, "structured_data": data})
        return _merge_page_structured_data(pages)

    async def test_land_continuation_page_llm_value_is_not_silent(self):
        title = "某段0361-0000地號\n"
        page1 = title + "土地所有權部\n(0001)登記次序:0001\n所有權人:王\n權利範圍:2分之1\n"
        page2 = title + "(0002)登記次序:0002\n所有權人:李\n權利範圍:3分之1\n"
        merged = await self._merged_with_llm('{"rights_scope": "3分之1"}', page1, page2)
        if merged.get("rights_scope") not in (None, "", "2分之1"):
            assert merged["field_confidences"]["rights_scope"] == 0.0
            assert "rights_scope" in merged["needs_confirmation"]

    async def test_unreadable_share_filled_by_llm_is_kept_for_reviewer(self):
        page = BUILDING_ENTRY + "權利範圍:****\n"
        data = await TranscriptFieldExtractor(provider=_fake_provider('{"rights_scope": "3分之1"}')).extract(
            page, image_data="BASE64", use_llm_fallback=True,
        )
        assert data["rights_scope"] == "3分之1"
        assert data["field_confidences"]["rights_scope"] == 0.0
        assert "rights_scope" in data["needs_confirmation"]

    async def test_rule_read_share_is_untouched_by_llm(self):
        """規則讀到的持分不受影響(LLM 只被問到其他缺值欄位)"""
        page = BUILDING_ENTRY + "權利範圍:2分之1\n"
        data = await TranscriptFieldExtractor(provider=_fake_provider('{"land_number": "0221-0000"}')).extract(
            page, image_data="BASE64", use_llm_fallback=True,
        )
        assert data["rights_scope"] == "2分之1"
        assert data["field_confidences"]["rights_scope"] == 0.9


def _fake_provider(answer: str):
    from unittest.mock import AsyncMock, MagicMock
    provider = MagicMock()
    provider.call = AsyncMock(return_value=answer)
    return provider


class TestLLMOverwriteGoesToReview:
    """verifier 2026-10-03 第十一輪:LLM 回傳沒被問到的持分、蓋掉規則讀到的值,也一律進複核"""

    async def test_unasked_rights_scope_overwrite(self):
        page = BUILDING_ENTRY + "權利範圍:全部\n"
        data = await TranscriptFieldExtractor(
            provider=_fake_provider('{"land_number": "0221-0000", "rights_scope": "3分之1"}')
        ).extract(page, image_data="BASE64", use_llm_fallback=True)
        assert data["field_confidences"]["rights_scope"] == 0.0
        assert "rights_scope" in data["needs_confirmation"]

    async def test_unasked_land_share_overwrite_is_flagged_after_backfill(self):
        page = "某段0361-0000地號\n土地所有權部\n(0001)登記次序:0001\n所有權人:王\n權利範圍:2分之1\n"
        merged = await TestLLMFilledShareGoesToReview._merged_with_llm(
            '{"land_rights_scope": "3分之1"}', page)
        if merged.get("rights_scope") not in (None, "", "2分之1"):
            assert merged["field_confidences"]["rights_scope"] == 0.0
            assert "rights_scope" in merged["needs_confirmation"]

    async def test_overwrite_on_deciding_page_is_flagged(self):
        """第十一輪 D:第一頁只有標示部、第二頁有所有權資料但規則值被 LLM 蓋掉"""
        page1 = "某段00071-000建號\n建物標示部\n總面積:****75.63平方公尺\n"
        page2 = "某段00071-000建號\n建物所有權部\n(0001)登記次序:0001\n所有權人:王\n權利範圍:全部\n"
        merged = await TestLLMFilledShareGoesToReview._merged_with_llm(
            '{"rights_scope": "3分之1"}', page1, page2)
        if merged.get("rights_scope") != "全部":
            assert merged["field_confidences"]["rights_scope"] == 0.0
            assert "rights_scope" in merged["needs_confirmation"]


class TestGeneralisedSeparatorsAndBrackets:
    """分隔與括號改用通用規則(業主 2026-10-04 裁示):沒列舉過的符號、任意長度的括號都照讀"""

    @pytest.mark.parametrize("sep", ["＞", "‧", "~", "－", "／", "》", "：*", " | "])
    async def test_any_symbol_separator(self, sep):
        d = await _extract(BUILDING_ENTRY + f"權利範圍{sep}2分之1\n")
        assert d["rights_scope"] == "2分之1"

    async def test_letter_is_not_a_separator(self):
        """英文字母不是分隔(讀成 l 的冒號寧可留空)"""
        assert (await _extract(BUILDING_ENTRY + "權利範圍l2分之1\n"))["rights_scope"] is None

    @pytest.mark.parametrize("bracket", ["(地下二層平面式大型)", "(地下二層機械式第3區)", "(B1)"])
    async def test_bracket_of_any_length_before_number(self, bracket):
        p = await _shared(f"權利範圍:10000分之150\n停車位{bracket}編號7號,權利範圍:100分之3\n")
        assert p["rights_scope"] == "10000分之150"
        assert p["parking"] == _parking("7號", "100分之3", "3.00")
