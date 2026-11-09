"""S2 電子 PDF 位置(.kiro/specs/transcript-records-converge/plan-s2.md §2)

不依賴真 PDF:用「每字一格」的合成幾何(第 r 行第 c 個原文字元佔 [c*10, r*12, c*10+10, r*12+12],頁 2000x2000)
取代 PyMuPDF 的逐字框,預期框直接由原文行列算出,與實作無關。
"""

import copy

import pytest

from app.lib.multi_type_ocr import transcript_positions as tp
from app.lib.multi_type_ocr.transcript_full_parser import parse_transcript_pages
from app.lib.multi_type_ocr.transcript_records import (
    apply_transcript_format,
    build_transcript_records,
)
from tests.unit.test_transcript_full_parser import P1, P2, P3

PAGES = [P1, P2, P3]
W = H = 2000.0


def grid_geo(text):
    chars, boxes = [], []
    for r, line in enumerate(text.split("\n")):
        for c, ch in enumerate(line):
            chars.append((ch, (c * 10.0, r * 12.0, c * 10.0 + 10, r * 12.0 + 12)))
    return tp._Geo(text, chars, W, H)


@pytest.fixture
def grid(monkeypatch):
    monkeypatch.setattr(tp, "_page_geometries", lambda data, texts: [grid_geo(t) for t in texts])


def expect_box(page_text, needle, nth=0):
    """needle 在原文(未正規化)第 nth 次出現的行列 → 預期 box。"""
    seen = 0
    for r, line in enumerate(page_text.split("\n")):
        start = 0
        while (c := line.find(needle, start)) >= 0:
            if seen == nth:
                return [round(c * 10 / W, 4), round(r * 12 / H, 4), round((c + len(needle)) * 10 / W, 4),
                        round((r + 1) * 12 / H, 4)]
            seen += 1
            start = c + 1
    raise AssertionError(needle)


def result_for(pages=PAGES, text_layer=True):
    ts = parse_transcript_pages(pages)
    recs = build_transcript_records(ts)
    return {"document_fields": {"transcripts": ts, "transcript_records": recs},
            "pages": [{"page_number": i + 1, "ocr_raw": {"text": t}, "rule_postprocessed": {"text": t},
                       "text_layer": text_layer, "structured_data": None} for i, t in enumerate(pages)]}


def positions(**kw):
    out = apply_transcript_format(result_for(**kw), kw.get("contents", b"%PDF"))
    return out["document_fields"]["transcript_records"]


# ---------------- 對位:長度會變的字元 ----------------
class TestGeo:
    def test_length_changing_char_maps_back_to_its_glyph(self):
        text = "AⅫB\nC"          # Ⅻ(羅馬數字 12)正規化成 XII,3 個字
        g = grid_geo(text)
        assert g.ok
        assert [g.char_box(0, i)[0] for i in range(5)] == ["A", "Ⅻ", "Ⅻ", "Ⅻ", "B"]
        assert g.char_box(1, 0)[0] == "C"
        assert g.char_box(0, 5) is None and g.char_box(2, 0) is None

    def test_enclosed_char_mapping(self):
        g = grid_geo("㈱甲\n乙")   # 帶框字還原成「株」(去掉括號),長度不變
        assert g.ok and g.char_box(0, 1)[0] == "甲"

    def test_text_not_matching_rawdict_is_rejected(self, monkeypatch):
        import fitz
        # _page_geometries 的檢查:文字與 rawdict 逐字不同 → 該頁 None
        doc = fitz.open()
        doc.new_page().insert_text((20, 50), "abc", fontsize=10)
        data = doc.tobytes()
        assert tp._page_geometries(data, ["abc"])[0] is not None
        assert tp._page_geometries(data, ["abd"]) == [None]
        assert tp._page_geometries(data, ["abc", "x"]) == [None, None]      # 頁數不同

    def test_frame_first_page_only_and_ignores_spaces(self):
        geos = [grid_geo("ab c\nde"), grid_geo("xy")]
        pos = tp._frame([(1, 0, 0), (1, 0, 1), (1, 0, 2), (1, 0, 3), (2, 0, 0)], geos)
        assert pos == {"page": 1, "box": [0.0, 0.0, 0.02, 0.006], "unit": "ratio"}   # 空白(col2)不算,跨頁只框第一頁
        assert tp._frame([], geos) is None
        assert tp._frame([(1, 0, 3)], [None]) is None
        assert tp._frame([(1, 9, 0)], geos) is None                                  # 行不存在


# ---------------- 位置規則 ----------------
class TestRules:
    def test_substring_value_is_framed_exactly(self, grid):
        rec = positions()[0]
        pos = rec["標示部"]["建物門牌"]["position"]
        assert rec["標示部"]["建物門牌"]["value"] == "忠孝東路四段285號五樓"
        assert pos["page"] == 1 and pos["unit"] == "ratio"
        assert pos["box"] == expect_box(P1, "忠孝東路四段285號五樓")

    def test_number_frames_the_number_token_only(self, grid):
        m = positions()[0]["標示部"]
        assert m["總面積"]["value"] == 193.02
        assert m["總面積"]["position"]["box"] == expect_box(P1, "193.02")
        rights = positions()[0]["他項權利部"][0]
        assert rights["擔保債權總金額"]["value"] == 93600000
        assert rights["擔保債權總金額"]["position"]["box"] == expect_box(P1, "93,600,000")

    def test_split_district_values_are_substrings_of_the_district(self, grid):
        h = positions()[0]["謄本"]
        assert h["行政區"]["position"]["box"] == expect_box(P1, "大安區")
        assert h["段"]["position"]["box"] == expect_box(P1, "仁愛段")

    def test_type_frames_the_title_word(self, grid):
        rec = positions()[0]
        assert rec["類型"]["value"] == "建物"
        assert rec["類型"]["position"]["box"] == expect_box(P1, "建物")
        land = positions()[1]["類型"]
        assert land["value"] == "土地" and land["position"]["page"] == 3 and land["position"]["box"] == expect_box(P3, "㈯㆞")

    def test_page_count_is_null(self, grid):
        assert positions()[0]["謄本"]["頁數"] == {"value": 2, "position": None}

    def test_label_value_frames_the_label_text(self, grid):
        h = positions()[0]["謄本"]
        assert h["查驗碼標籤"]["value"] == "謄本檢查號"
        assert h["查驗碼標籤"]["position"]["box"] == expect_box(P1, "謄本檢查號")

    def test_paired_values_use_each_source(self, grid):
        floors = positions()[0]["標示部"]["層次"]
        assert floors[0]["層次"]["position"]["box"] == expect_box(P1, "一層")
        assert floors[0]["面積"]["value"] == 96.51
        assert floors[0]["面積"]["position"]["box"] == expect_box(P1, "96.51", 0)
        assert floors[1]["面積"]["position"]["box"] == expect_box(P1, "96.51", 1)

    def test_filled_value_has_null_position(self, grid):
        pages = [P1, P2]                                           # 一張謄本才會補單值
        r = result_for(pages)
        r["document_fields"]["completion_date"] = "民國 70 年 1 月 2 日"    # 謄本印的是空白標記 → 規則補進
        out = apply_transcript_format(r, b"%PDF")["document_fields"]["transcript_records"][0]["標示部"]
        assert out["建築完成日期"] == {"value": "民國 70 年 1 月 2 日", "position": None}
        assert out["建物門牌"]["position"]["box"] == expect_box(P1, "忠孝東路四段285號五樓")

    def test_every_non_null_position_has_the_r4_shape(self, grid):
        def walk(o):
            if isinstance(o, dict):
                if set(o) == {"value", "position"}:
                    yield o["position"]
                else:
                    for k, v in o.items():
                        if k not in ("判定", "部是否印出"):
                            yield from walk(v)
            elif isinstance(o, list):
                for v in o:
                    yield from walk(v)
        got = [p for r in positions() for p in walk(r) if p is not None]
        assert len(got) > 30
        for p in got:
            assert set(p) == {"page", "box", "unit"} and p["unit"] == "ratio" and isinstance(p["page"], int) and p["page"] >= 1
            x0, y0, x1, y1 = p["box"]
            assert 0 <= x0 <= x1 <= 1 and 0 <= y0 <= y1 <= 1


# ---------------- 對不上 → null ----------------
class TestNull:
    def test_no_file_contents_or_photo_means_all_null(self):
        def all_null(recs):
            def walk(o):
                if isinstance(o, dict):
                    if set(o) == {"value", "position"}:
                        yield o["position"]
                    else:
                        for k, v in o.items():
                            if k not in ("判定", "部是否印出"):
                                yield from walk(v)
                elif isinstance(o, list):
                    for v in o:
                        yield from walk(v)
            return all(p is None for r in recs for p in walk(r))
        r = result_for()
        assert all_null(apply_transcript_format(r)["document_fields"]["transcript_records"])
        assert all_null(apply_transcript_format(r, None)["document_fields"]["transcript_records"])
        photo = result_for(text_layer=False)
        assert all_null(apply_transcript_format(photo, b"%PDF")["document_fields"]["transcript_records"])

    def test_page_that_does_not_align_is_all_null(self, monkeypatch):
        geos = [None, grid_geo(P2), grid_geo(P3)]
        monkeypatch.setattr(tp, "_page_geometries", lambda data, texts: geos)
        rec = apply_transcript_format(result_for(), b"%PDF")["document_fields"]["transcript_records"][0]
        assert rec["標示部"]["建物門牌"]["position"] is None            # 在第 1 頁
        assert rec["所有權部"][0]["所有權人"]["position"] is None

    def test_rebuilt_records_differ_means_all_null(self, grid):
        r = result_for()
        r["document_fields"]["transcript_records"][0]["標示部"]["建物門牌"] = "被改過的值"
        out = apply_transcript_format(r, b"%PDF")["document_fields"]["transcript_records"][0]
        assert out["標示部"]["建物門牌"] == {"value": "被改過的值", "position": None}
        assert out["謄本"]["編號"]["position"] is None
        assert tp.compute_positions(PAGES, b"%PDF", r["document_fields"]["transcript_records"]) is None

    def test_failure_inside_assembly_degrades_to_null(self, monkeypatch):
        def boom(*a, **k):
            raise RuntimeError("fitz missing")
        monkeypatch.setattr(tp, "_page_geometries", boom)
        out = apply_transcript_format(result_for(), b"%PDF")["document_fields"]["transcript_records"][0]
        assert out["標示部"]["建物門牌"]["position"] is None

    def test_values_unchanged_by_positions(self, grid):
        r = result_for()
        a = apply_transcript_format(r)["document_fields"]["transcript_records"]
        b = apply_transcript_format(r, b"%PDF")["document_fields"]["transcript_records"]

        def values(o):
            if isinstance(o, dict):
                if set(o) == {"value", "position"}:
                    return o["value"]
                return {k: values(v) for k, v in o.items()}
            if isinstance(o, list):
                return [values(v) for v in o]
            return o
        assert values(a) == values(b)

    def test_input_not_mutated(self, grid):
        r = result_for()
        before = copy.deepcopy(r)
        apply_transcript_format(r, b"%PDF")
        assert r == before
