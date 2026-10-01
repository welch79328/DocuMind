"""
shared_parts:公設的建號、持分、本戶分到的面積與公設內車位(2026-10-01,slice B3)

既有 shared_build_number、shared_area 只回第一筆,而且 shared_area 是「整棟公設」的面積,
權利範圍與本戶分到的面積都沒讀。本批以附加清單補上,既有欄位不動(shared_area 語意照舊)。

- 區塊邊界與 _strip_shared_parts 完全相同(共用同一個切塊函式):其他欄位排除掉的,
  正是這裡收進來的。
- 持分只留分數本身(「1000分之193」「全部」),OCR 雜訊(「冰」、星號)去掉;認不出就留空。
- 本戶公設面積 = 公設總面積 × 持分,兩者都讀得到才算,四捨五入到小數兩位。
- 不收「主要用途」:那是照抄 OCR 的文字(高雄範本把「樓梯間」讀成「樓梯問」),品質無從保證。

OCR 固定案例取自正式環境對公開範本跑出的 rule_postprocessed 原文,不要順手修正。
"""

from app.lib.multi_type_ocr.field_consensus import field_candidate_from_extraction
from app.lib.multi_type_ocr.transcript_field_extractor import TranscriptFieldExtractor
from app.services.analyze_service import _merge_page_structured_data


# 士林(02):權利範圍的值在下一行;含車位;停車位共計在區塊內
SHILIN_OCR = """小段19998-000建號
建物標示部
共有部分:測試段一小段11994-000建號*509.05平方公尺
權利範圍:
1000分之193
含車位編號2號,權利範圍:1000分之55
其他登記事項:使用執照字號:91使字第0101號
停車位共計:5位
這個公設的車位數量.
其他登記事項:使用執照字號:91使字第0101號
建物所有權部
(0001)登記次序:0003
所有權人:皮
權利範圍:全部
"""

# 高雄公寓(04):持分後面黏著 OCR 雜訊「冰」;沒有建號抬頭(重測前那兩行不是抬頭)
KCG_OCR = """建物標示部
共有部分:吉慶段00697-000建號19.62平方公尺
權利範圍:5分之1冰
其他登記事項:主要用途:水箱、樓梯問
建物層次:公共設施
重测前:大坑埔段大坑埔小段01272-000建號
其他登記事項:使用執照字號:81瑞使40號
重测前:大坑埔段大坑埔小段01277-000建號
"""

# 瑞芳(06):導讀說明框殘字「整棟建築物住户(共用)共有性」夾在區塊裡
RUIFANG_OCR = """瑞芳區測試段00071-000建號
建物標示部
共有部分:测試段00067-000建號18.00平方公尺
整棟建築物住户(共用)共有性
權利範圍:10分之1
其他登記事項:使用執照字號:83瑞使981號
質的建物,通常稱為公設.
重测前:龍潭堵段02372-000建號
其他登記事項:使用執照字號:83瑞使981號
建物所有權部
(0001)登記次序:0002
所有權人:王
權利範圍:全部1分之1
"""


async def _merged(*texts: str) -> dict:
    pages = [
        {"ocr_raw": {"text": t, "confidence": 1.0},
         "structured_data": await TranscriptFieldExtractor().extract(t)}
        for t in texts
    ]
    return _merge_page_structured_data(pages)


class TestRealSamples:

    async def test_shilin_with_parking(self):
        assert (await _merged(SHILIN_OCR))["shared_parts"] == [{
            "transcript_id": "19998-000", "build_number": "11994-000", "area": "509.05",
            "rights_scope": "1000分之193", "share_area": "98.25",
            "parking": [{"number": "2號", "rights_scope": "1000分之55", "share_area": "28.00"}],
            "parking_total": "5位",
        }]

    async def test_kcg_noise_removed_and_no_title(self):
        assert (await _merged(KCG_OCR))["shared_parts"] == [{
            "transcript_id": None, "build_number": "00697-000", "area": "19.62",
            "rights_scope": "5分之1", "share_area": "3.92",
            "parking": [], "parking_total": None,
        }]

    async def test_ruifang_callout_inside_block(self):
        assert (await _merged(RUIFANG_OCR))["shared_parts"] == [{
            "transcript_id": "00071-000", "build_number": "00067-000", "area": "18.00",
            "rights_scope": "10分之1", "share_area": "1.80",
            "parking": [], "parking_total": None,
        }]

    async def test_unit_rights_scope_not_taken_from_shared_block(self):
        """區塊之外的本戶權利範圍(全部)不受影響"""
        m = await _merged(SHILIN_OCR)
        assert m["rights_scope"] == "全部"
        assert m["shared_area"] == "509.05"        # 既有欄位語意照舊:整棟公設面積


class TestRules:

    async def test_quanbu_share_equals_area(self):
        text = "共有部分:某段00500-000建號****100.00平方公尺\n權利範圍:全部\n"
        part = (await _merged(text))["shared_parts"][0]
        assert (part["rights_scope"], part["share_area"]) == ("全部", "100.00")

    async def test_unreadable_share_gives_no_area(self):
        """持分讀不出來:持分與本戶面積都留空,不猜"""
        text = "共有部分:某段00500-000建號****100.00平方公尺\n權利範圍:*****\n"
        part = (await _merged(text))["shared_parts"][0]
        assert (part["rights_scope"], part["share_area"]) == (None, None)

    async def test_parking_scope_is_not_the_unit_scope(self):
        """車位那一行的權利範圍不能當成公設持分(即使它排在前面)"""
        text = (
            "共有部分:某段00500-000建號****100.00平方公尺\n"
            "(含車位編號7號,權利範圍:100分之3)\n"
            "權利範圍:100分之10\n"
        )
        part = (await _merged(text))["shared_parts"][0]
        assert part["rights_scope"] == "100分之10"
        assert part["parking"] == [{"number": "7號", "rights_scope": "100分之3", "share_area": "3.00"}]

    async def test_parking_without_number(self):
        text = (
            "共有部分:某段00500-000建號****100.00平方公尺\n權利範圍:100分之10\n"
            "含停車位,權利範圍:100分之3\n"
        )
        parking = (await _merged(text))["shared_parts"][0]["parking"]
        assert parking == [{"number": None, "rights_scope": "100分之3", "share_area": "3.00"}]

    async def test_two_blocks(self):
        text = (
            "某段00071-000建號\n"
            "共有部分:某段00500-000建號****100.00平方公尺\n權利範圍:100分之10\n"
            "共有部分:某段00501-000建號****50.00平方公尺\n權利範圍:10分之1\n"
        )
        parts = (await _merged(text))["shared_parts"]
        assert [(p["build_number"], p["share_area"]) for p in parts] == [
            ("00500-000", "10.00"), ("00501-000", "5.00"),
        ]

    async def test_round_half_up(self):
        """98.24665 → 98.25(四捨五入,不是銀行家捨入)"""
        assert (await _merged(SHILIN_OCR))["shared_parts"][0]["share_area"] == "98.25"
        text = "共有部分:某段00500-000建號****0.25平方公尺\n權利範圍:10分之1\n"   # 0.025
        assert (await _merged(text))["shared_parts"][0]["share_area"] == "0.03"


class TestMergeIdentity:

    async def test_same_page_twice(self):
        assert len((await _merged(SHILIN_OCR, SHILIN_OCR))["shared_parts"]) == 1

    async def test_no_title_never_deduplicated(self):
        assert len((await _merged(KCG_OCR, KCG_OCR))["shared_parts"]) == 2


class TestMetadata:

    async def test_not_a_field(self):
        data = await TranscriptFieldExtractor().extract(SHILIN_OCR)
        assert "shared_parts" not in field_candidate_from_extraction("paddleocr", data)["fields"]
        assert "shared_parts" not in data["field_confidences"]
        assert "shared_parts" not in data["needs_confirmation"]

    async def test_no_usage_key(self):
        """主要用途是照抄 OCR 的文字,刻意不收"""
        assert "usage" not in (await _merged(KCG_OCR))["shared_parts"][0]
