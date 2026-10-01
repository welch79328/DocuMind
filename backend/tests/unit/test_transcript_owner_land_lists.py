"""
owners / land_numbers:所有權人與地號「全部」讀出(2026-09-30,slice B1)

既有的 owner、land_number 是單值欄位,一份謄本只回第一筆。線上 8 份公開範本實測:
謄本印出 9 筆所有權人、10 筆現行地號,只回得到 5/9、5/10,且所有權人分不出是土地
還是建物的。本批以「附加的清單欄位」補上,既有單值欄位的值與語意一律不動。

三條設計規則,各有測試鎖住:
  1. 去重依「身分」而非「顯示值」——第二類謄本的姓名遮成「王**」、持分又常相同,
     依值去重會把三位共有人併成一位。所有權人身分 = (part, transcript_id, order),
     任一段缺值就不去重。
  2. 每筆所有權人標明出自土地或建物所有權部(part),由上方標題決定、看不出就 None。
     土地持分被當成建物權利範圍正是 0658077 修掉的災情,清單形式不能讓它回來。
  3. 地號只取兩個來源:整行只有「[段名]數字-數字地號」的頁首抬頭,以及建物坐落地號那一行。
     「分割自」「因分割增加」「共同擔保」「重測前」等沿革/擔保行一律不取。

OCR 固定案例取自正式環境對公開範本跑出的 rule_postprocessed 原文(含 OCR 錯字),
不要順手修正。範本來源見 test_transcript_shared_part_scope.py 的說明。
"""

from pathlib import Path

import pytest

from app.lib.multi_type_ocr.field_consensus import field_candidate_from_extraction
from app.lib.multi_type_ocr.transcript_field_extractor import TranscriptFieldExtractor
from app.lib.pdf_text_layer import extract_text_layer_pages
from app.services.analyze_service import _merge_page_structured_data


# repo 內掃描件(07),正式環境 OCR 原文節錄。三位共有人姓名同樣遮成「王」、持分同為
# 3分之1,只有登記次序不同。權利範圍標籤被 OCR 讀壞成「利:」「檬利:」。
REPO_SCAN_OCR = """建物登記第二類謄本(建號全部)
三重區文化北段01391-000建號
建物標示部
建物坐落地號:文化北段 0931-0000 0932-0000 0933-0000 0934-0000
主要用途:住
重测前:三重埔段大竹小段00665-000建號

建物所有權部

(0001)登記次序:0003
所有權人:王
统一编號:C1206
利:3分之1
相關他項權利登記次序:0003-000
其他登記事項:(空白)
(0002)登記次序:0004
所有權人:王
檬利:3分之1
相關他項權利登記次序:0003-000
(0003)登記次序:0005
所有權人:王
檬利:3分之1
相關他項權利登記次序:0003-000
*
建物他項權利部
"""

# 瑞芳範本(06)的坐落地號行,兩筆地號
RUIFANG_SITE_OCR = """瑞芳區測試段00071-000建號
建物標示部
建物坐落地號:測試段 0139-0000 0140-0000
主要用途:住家用
"""

# 士林土地範本(01):抬頭大字被 OCR 讀壞,唯一可讀的抬頭只剩續頁的「小段0361-0000地號」,
# 而且出現在所有權部之後。重測前與共同擔保那兩行都不是現行地號。
SHILIN_LAND_OCR = """一十林區測試段一
土地標示部
其他登記事項:重測前:測試段測試小段27-12地號
土地所有權部
(0001)登記次序:0021
所有權人:皮
權利範圍:70分之11
土地他項權利部
共同擔保地號:測試段一小段0361-0000
小段0361-0000地號
"""

MERGED_PDF = Path(__file__).resolve().parents[2] / "data" / "建物土地謄本-杭州南路一段.pdf"


async def _extract(text: str) -> dict:
    return await TranscriptFieldExtractor().extract(text)


async def _merged_from_texts(*texts: str) -> dict:
    pages = [
        {"ocr_raw": {"text": t, "confidence": 1.0}, "structured_data": await _extract(t)}
        for t in texts
    ]
    return _merge_page_structured_data(pages)


def _numbers(data: dict) -> list:
    return [e["number"] for e in data["land_numbers"]]


class TestOwners:

    async def test_three_masked_coowners_survive_merge(self):
        """07:姓名、持分都一樣的三位共有人,合併後仍是三筆"""
        merged = await _merged_from_texts(REPO_SCAN_OCR)
        owners = merged["owners"]
        assert [o["order"] for o in owners] == ["0003", "0004", "0005"]
        assert all(o["part"] == "building" for o in owners)
        assert all(o["rights_scope"] == "3分之1" for o in owners)
        assert all(o["transcript_id"] == "01391-000" for o in owners)

    async def test_related_other_right_order_is_not_an_entry(self):
        """「相關他項權利登記次序:0003-000」不是所有權人的登記次序"""
        owners = (await _extract(REPO_SCAN_OCR))["owners"]
        assert "0003-000" not in [o["order"] for o in owners]

    async def test_same_page_twice_is_deduplicated(self):
        """同一頁重複上傳:每個身分只留一筆"""
        merged = await _merged_from_texts(REPO_SCAN_OCR, REPO_SCAN_OCR)
        assert len(merged["owners"]) == 3

    async def test_unreadable_order_is_never_deduplicated(self):
        """登記次序讀不出來時,即使姓名、持分相同也不去重"""
        page = (
            "建物所有權部\n"
            "(0001)登記次序:\n所有權人:王**\n權利範圍:3分之1\n"
            "(0002)登記次序:\n所有權人:王**\n權利範圍:3分之1\n"
        )
        merged = await _merged_from_texts(page)
        assert len(merged["owners"]) == 2

    async def test_land_share_never_labelled_building(self):
        """土地在前、建物在後的合併版型:土地持分不得被標成建物"""
        text = (
            "㈯㆞所㈲權部\n(0001)登記次序:0005\n所㈲權㆟:某甲\n權利範圍:4分之1\n"
            "建物所㈲權部\n(0001)登記次序:0002\n所㈲權㆟:某甲\n權利範圍:全部 1分之1\n"
        )
        owners = (await _extract(text))["owners"]
        assert [(o["part"], o["rights_scope"]) for o in owners] == [
            ("land", "4分之1"), ("building", "全部"),
        ]

    async def test_mortgage_only_page_has_no_owners(self):
        """只有他項權利部:設定權利範圍永遠不是所有權人的持分"""
        text = "土地他項權利部\n(0001)登記次序:0022-000\n權利人:某銀行\n設定權利範圍:100000分之16667\n"
        assert (await _extract(text))["owners"] == []

    async def test_no_ownership_heading_no_owners(self):
        """看不出是哪一部就不猜"""
        assert (await _extract("所有權人:王**\n權利範圍:全部\n"))["owners"] == []

    async def test_callout_text_is_not_a_name(self):
        """導讀範本的說明框「所有權人的身分資料」沒有冒號,不是姓名"""
        text = "建物所有權部\n(0001)登記次序:0002\n所有權人:王\n所有權人的身分資料\n權利範圍:全部\n"
        owners = (await _extract(text))["owners"]
        assert [o["name"] for o in owners] == ["王"]


class TestLandNumbers:

    async def test_all_site_parcels(self):
        """07:坐落地號四筆全讀"""
        merged = await _merged_from_texts(REPO_SCAN_OCR)
        assert _numbers(merged) == ["0931-0000", "0932-0000", "0933-0000", "0934-0000"]
        assert merged["land_numbers"][0]["section"] == "文化北段"

    async def test_two_site_parcels(self):
        merged = await _merged_from_texts(RUIFANG_SITE_OCR)
        assert _numbers(merged) == ["0139-0000", "0140-0000"]

    async def test_late_split_title_counts_and_lineage_does_not(self):
        """01:抬頭只剩「小段0361-0000地號」也要算;重測前、共同擔保都不算"""
        merged = await _merged_from_texts(SHILIN_LAND_OCR)
        assert _numbers(merged) == ["0361-0000"]

    async def test_building_title_is_not_a_parcel(self):
        """建物抬頭「…01391-000建號」不是地號"""
        assert "01391-000" not in _numbers(await _merged_from_texts(REPO_SCAN_OCR))


@pytest.mark.skipif(not MERGED_PDF.exists(), reason="真實電子謄本不在 repo")
class TestRealElectronicTranscript:
    """08:兩份土地謄本+一份建物謄本在同一個 PDF(文字層)"""

    @pytest.fixture
    async def merged(self):
        pages = extract_text_layer_pages(MERGED_PDF.read_bytes())
        for page in pages:
            page["structured_data"] = await _extract(page["ocr_raw"]["text"])
        return _merge_page_structured_data(pages)

    async def test_parcels_exact_without_duplicates_or_lineage(self, merged):
        """土地抬頭與建物坐落都有 0221-0000,只算一筆;分割自/因分割增加不算"""
        assert _numbers(merged) == ["0221-0000", "0221-0001"]

    async def test_owners_attributed_by_part(self, merged):
        got = [(o["part"], o["transcript_id"], o["rights_scope"]) for o in merged["owners"]]
        assert got == [
            ("land", "0221-0000", "4分之1"),
            ("land", "0221-0001", "4分之1"),
            ("building", "00465-000", "全部"),
        ]

    async def test_scalar_fields_unchanged(self, merged):
        """既有單值欄位不受影響"""
        assert merged["land_number"] == "0221-0000"
        assert merged["owner"] == "黃**"
        assert merged["rights_scope"] == "全部"
        assert merged["land_rights_scope"] == "4分之1"


class TestListsAreMetadataNotFields:

    async def test_not_consensus_fields(self):
        data = await _extract(REPO_SCAN_OCR)
        candidate = field_candidate_from_extraction("paddleocr", data)
        for key in ("owners", "land_numbers"):
            assert key not in candidate["fields"]
            assert key not in candidate["field_confidences"]

    async def test_not_scored(self):
        """清單欄位沒有信心度、不進待確認"""
        data = await _extract(REPO_SCAN_OCR)
        for key in ("owners", "land_numbers"):
            assert key not in data["field_confidences"]
            assert key not in data["needs_confirmation"]


class TestRulesLockedByVerifier:
    """2026-09-30 fresh verifier:以下規則原本拔掉也不會有測試失敗,各補一個"""

    async def test_callout_before_name_is_not_a_name(self):
        """說明框排在姓名之前時,沒有冒號的「所有權人的身分資料」仍不能當姓名"""
        text = "建物所有權部\n(0001)登記次序:0002\n所有權人的身分資料\n所有權人:王\n權利範圍:全部\n"
        assert [o["name"] for o in (await _extract(text))["owners"]] == ["王"]

    async def test_historical_share_not_taken_by_mangled_label(self):
        """本筆的權利範圍讀不出來時,不能改拿「歷次取得權利範圍」"""
        text = "土地所有權部\n(0001)登記次序:0005\n所有權人:甲\n歷次取得權利範圍:2分之1\n"
        assert (await _extract(text))["owners"][0]["rights_scope"] is None

    async def test_title_must_be_the_whole_line(self):
        """「中正段0221-0009地號之一部分」不是抬頭,不能多出一筆地號"""
        text = "中正段0221-0000地號\n中正段0221-0009地號之一部分\n"
        merged = await _merged_from_texts(text)
        assert _numbers(merged) == ["0221-0000"]

    async def test_lineage_title_shaped_line_is_not_a_parcel(self):
        """長得像抬頭的「重測前中正段0221-0003地號」是舊地號"""
        text = "中正段0221-0000地號\n重測前中正段0221-0003地號\n"
        assert _numbers(await _merged_from_texts(text)) == ["0221-0000"]

    async def test_unreadable_share_is_missing_not_junk(self):
        """「權利範圍:」後面讀不出值時是缺值,不是「:」"""
        for line in ("權利範圍:\n", "權利範圍:*********\n"):
            text = "建物所有權部\n(0001)登記次序:0002\n所有權人:王\n" + line
            assert (await _extract(text))["owners"][0]["rights_scope"] is None

    async def test_two_titles_on_one_page_keep_both_owners(self):
        """一頁兩個抬頭:各筆掛到自己上方的抬頭,合併時兩位都在"""
        text = (
            "中正段0221-0000地號\n土地所有權部\n(0001)登記次序:0001\n所有權人:甲\n權利範圍:2分之1\n"
            "中正段0221-0001地號\n土地所有權部\n(0001)登記次序:0001\n所有權人:乙\n權利範圍:3分之1\n"
        )
        merged = await _merged_from_texts(text)
        assert [(o["transcript_id"], o["name"]) for o in merged["owners"]] == [
            ("0221-0000", "甲"), ("0221-0001", "乙"),
        ]


class TestOwnerLocksFromVerifier:
    """2026-10-01 品質加固:B1 驗證時沒被測試鎖住的規則"""

    async def test_late_title_is_the_default_transcript_id(self):
        """01:抬頭只在頁尾出現,所有權人仍掛到它"""
        owners = (await _extract(SHILIN_LAND_OCR))["owners"]
        assert [o["transcript_id"] for o in owners] == ["0361-0000"]

    @pytest.mark.parametrize("line", [
        "設定權利範圍:全部",            # 他項權利部標題讀壞時混進來的抵押範圍
        "相關他項權利:0003-000",        # 「登記次序」被 OCR 吃掉的相關他項權利
        "登記次序利:0004",              # 登記次序與「利:」黏在一起的 OCR 殘行
    ])
    async def test_mangled_label_exclusions(self, line):
        text = "建物所有權部\n(0001)登記次序:0002\n所有權人:王\n" + line + "\n"
        assert (await _extract(text))["owners"][0]["rights_scope"] is None
