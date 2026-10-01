"""
floors / sub_buildings / floor_area_checks:各層與附屬建物「全部」讀出(2026-10-01,slice B2)

既有 floor_level、floor_area、sub_building_* 是單值,只回第一層、第一筆(附屬建物連面積都常常沒有)。
線上 8 份公開範本:謄本印出 12 筆層次面積、9 筆附屬建物,只回得到 5 筆面積、0 筆附屬面積。

配對規則是「寧可缺,不可錯」:OCR 常把左欄名稱(一層/陽台)與右欄面積拆散、漏字,
所以只有兩邊數量相等才依序配對;數量對不上就只給面積、名稱留空,不猜。
各層面積加總另與總面積比對(floor_area_checks),對得上代表面積沒有漏讀或多讀。

OCR 固定案例取自正式環境對公開範本跑出的 rule_postprocessed 原文(含錯字、說明框殘字),
不要順手修正。範本來源見 test_transcript_shared_part_scope.py。
"""

from pathlib import Path

import pytest

from app.lib.multi_type_ocr.field_consensus import field_candidate_from_extraction
from app.lib.multi_type_ocr.transcript_field_extractor import TranscriptFieldExtractor
from app.lib.pdf_text_layer import extract_text_layer_pages
from app.services.analyze_service import _merge_page_structured_data


# 高雄透天(03):四層面積都在,層次名稱只剩「一層」「四層」;附屬建物只認出「陽台」,
# 「箱」是 OCR 雜訊,面積四筆都在。層數標籤只剩單獨的「數:」。
KCG_MULTIFLOOR_OCR = """建物標示部
主要用途:住商用
層層
數:004層
總面積:*128.32平方公尺
次:一層
層次面積:37.52平方公尺

37.52平方公尺
37.52平方公尺
四層
15.76平方公尺
建築完成日期:民國084年02月日
附屬建物用途:陽台
面積:10.29平方公尺
箱
8.80平方公尺
8.00平方公尺
3.23平方公尺
其他登記事項:使用執照字號:84高縣建局營字第
"""

# 高雄公寓(04):「唇数:005唇」;「005唇」是層數,不是層次
KCG_APARTMENT_OCR = """建物標示部
唇数:005唇
總面積:69.52平方公尺
次:五層
次面積:69.52平方公尺
建築完成日期:民國---年--月--日
附屬建物用途:陽台
面積:8.71平方公尺
花台
2.39平方公尺
共有部分:吉慶段00697-000建號19.62平方公尺
"""

# 瑞芳(06):導讀範本的說明框殘字「附屬建物及公」夾在層數與層次之間,不能把區段切斷
RUIFANG_OCR = """瑞芳區測試段00071-000建號
建物標示部
層
數:005層
總面積:75.63平方公尺
附屬建物及公
層
次:四層
層次面積:75.63平方公尺
設面積)
建築完成日期:民國083年07月15日
附屬建物用途:陽台
面積:5.54平方公尺
共有部分:测試段00067-000建號18.00平方公尺
"""

# repo 掃描件(07):層數的值讀壞成「00.」,區段仍要成立;四層含騎樓
REPO_SCAN_OCR = """三重區文化北段01391-000建號
建物標示部
層
数:00.
總面積:*202.95平方公尺
唇
次:一層
層次面積:62.19平方公尺
二層
79.98平方公尺
三層
47.39平方公尺
騎樓
13.39平方公尺
建築完成日期:民國049年10月01日
其他登記事項:(一般註記)登記原因:增建·增建前面積:地面層62.19平方公尺
"""

# 士林(02):附屬建物的面積被 OCR 讀丟,只剩用途
SHILIN_SUB_OCR = """建物標示部
附屬建物用途:陽台
面
横
雨遮
******
共有部分:測試段一小段11994-000建號****509.05平方公尺
"""

MERGED_PDF = Path(__file__).resolve().parents[2] / "data" / "建物土地謄本-杭州南路一段.pdf"


async def _merged(*texts: str) -> dict:
    pages = [
        {"ocr_raw": {"text": t, "confidence": 1.0},
         "structured_data": await TranscriptFieldExtractor().extract(t)}
        for t in texts
    ]
    return _merge_page_structured_data(pages)


def _floors(d):
    return [(f["level"], f["area"]) for f in d["floors"]]


def _subs(d):
    return [(s["usage"], s["area"]) for s in d["sub_buildings"]]


class TestFloors:

    async def test_pairs_when_counts_match(self):
        """07:四個名稱對四個面積,含騎樓;層數值讀壞(00.)不影響"""
        m = await _merged(REPO_SCAN_OCR)
        assert _floors(m) == [
            ("一層", "62.19"), ("二層", "79.98"), ("三層", "47.39"), ("騎樓", "13.39"),
        ]
        assert m["floors"][0]["transcript_id"] == "01391-000"

    async def test_areas_only_when_labels_lost(self):
        """03:名稱只剩兩個、面積四個——不配對,名稱留空,面積照給"""
        m = await _merged(KCG_MULTIFLOOR_OCR)
        assert _floors(m) == [
            (None, "37.52"), (None, "37.52"), (None, "37.52"), (None, "15.76"),
        ]

    async def test_total_area_line_is_not_a_floor(self):
        """總面積那一行的面積不算某一層"""
        assert "128.32" not in [a for _, a in _floors(await _merged(KCG_MULTIFLOOR_OCR))]

    async def test_floor_count_value_is_not_a_level(self):
        """04:「005唇」是層數,不是層次;「次:五層」才是"""
        assert _floors(await _merged(KCG_APARTMENT_OCR)) == [("五層", "69.52")]

    async def test_callout_containing_fushu_does_not_cut_region(self):
        """06:「附屬建物及公」不是附屬建物用途標籤,不能把層次區段切斷"""
        assert _floors(await _merged(RUIFANG_OCR)) == [("四層", "75.63")]

    @pytest.mark.parametrize("label", ["數:004層", "数:004層", "唇数:004唇", "層    數:004層"])
    async def test_start_label_variants(self, label):
        text = f"{label}\n層    次:二層   層次面積:*****95.41平方公尺\n建築完成日期:民國091年\n"
        assert _floors(await _merged(text)) == [("二層", "95.41")]

    async def test_no_floor_count_label_no_floors(self):
        """土地謄本沒有層數標籤:不產生 floors"""
        assert (await _merged("土地標示部\n面積:****359.00平方公尺\n"))["floors"] == []


class TestFloorAreaChecks:

    async def test_sum_matches_total(self):
        for text, total in ((KCG_MULTIFLOOR_OCR, "128.32"), (REPO_SCAN_OCR, "202.95"),
                            (KCG_APARTMENT_OCR, "69.52"), (RUIFANG_OCR, "75.63")):
            checks = (await _merged(text))["floor_area_checks"]
            assert len(checks) == 1
            assert checks[0]["total"] == total
            assert checks[0]["matches"] is True

    async def test_mismatch_is_reported(self):
        text = "數:002層\n總面積:****100.00平方公尺\n層次:一層 層次面積:****60.00平方公尺\n建築完成日期:x\n"
        check = (await _merged(text))["floor_area_checks"][0]
        assert check["matches"] is False
        assert check["sum"] == "60.00"

    async def test_no_total_means_unknown(self):
        text = "數:001層\n層次:一層 層次面積:****60.00平方公尺\n建築完成日期:x\n"
        assert (await _merged(text))["floor_area_checks"][0]["matches"] is None


class TestSubBuildings:

    async def test_pairs_when_counts_match(self):
        assert _subs(await _merged(KCG_APARTMENT_OCR)) == [("陽台", "8.71"), ("花台", "2.39")]
        assert _subs(await _merged(RUIFANG_OCR)) == [("陽台", "5.54")]

    async def test_areas_only_when_usages_lost(self):
        """03:「箱」是雜訊不是用途;一個用途對四個面積——不配對"""
        assert _subs(await _merged(KCG_MULTIFLOOR_OCR)) == [
            (None, "10.29"), (None, "8.80"), (None, "8.00"), (None, "3.23"),
        ]

    async def test_noise_word_never_pairs(self):
        """雜訊字若被當成用途,數量會剛好相等而配出錯的一對——只認固定詞彙"""
        text = "附屬建物用途:陽台\n面積:5.00平方公尺\n箱\n3.00平方公尺\n共有部分:x\n"
        assert _subs(await _merged(text)) == [(None, "5.00"), (None, "3.00")]

    async def test_usages_only_when_areas_lost(self):
        """02:面積被 OCR 讀丟,只給用途"""
        assert _subs(await _merged(SHILIN_SUB_OCR)) == [("陽台", None), ("雨遮", None)]

    async def test_shared_part_area_is_not_a_sub_building(self):
        """區段在共有部分前結束,公設的 509.05 不算附屬建物"""
        assert "509.05" not in [a for _, a in _subs(await _merged(SHILIN_SUB_OCR))]

    async def test_floor_areas_are_not_sub_buildings(self):
        assert _subs(await _merged(REPO_SCAN_OCR)) == []


class TestMergeIdentity:

    async def test_same_page_twice_is_deduplicated(self):
        m = await _merged(REPO_SCAN_OCR, REPO_SCAN_OCR)
        assert len(m["floors"]) == 4
        assert len(m["floor_area_checks"]) == 1

    async def test_without_title_never_deduplicated(self):
        """沒有建號抬頭就沒有完整身分:跨頁寧可重複也不誤併"""
        m = await _merged(KCG_APARTMENT_OCR, KCG_APARTMENT_OCR)
        assert len(m["floors"]) == 2


@pytest.mark.skipif(not MERGED_PDF.exists(), reason="真實電子謄本不在 repo")
class TestRealElectronicTranscript:

    async def test_pdf_floors(self):
        pages = extract_text_layer_pages(MERGED_PDF.read_bytes())
        for page in pages:
            page["structured_data"] = await TranscriptFieldExtractor().extract(page["ocr_raw"]["text"])
        m = _merge_page_structured_data(pages)
        assert _floors(m) == [("二層", "95.41")]
        assert m["floors"][0]["transcript_id"] == "00465-000"
        assert m["floor_area_checks"][0]["matches"] is True
        assert m["sub_buildings"] == []
        assert m["floor_area"] == "95.41"          # 既有單值不變


class TestListsAreMetadata:

    async def test_not_fields(self):
        data = await TranscriptFieldExtractor().extract(REPO_SCAN_OCR)
        candidate = field_candidate_from_extraction("paddleocr", data)
        for key in ("floors", "sub_buildings", "floor_area_checks"):
            assert key not in candidate["fields"]
            assert key not in data["field_confidences"]
            assert key not in data["needs_confirmation"]
