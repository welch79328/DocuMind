"""S3 照片位置(.kiro/specs/transcript-records-converge/plan-s3.md §2)

合成行框,不跑真 OCR:
- engine_manager 行框換算(假 predict)
- 行框隨該頁結果交回、並發不串頁、extract_text 換成兩項函式也能跑、不外流
- 值文字反查 OCR 行:唯一／多行鍵名／多行無鍵名／0 行／數字記號／一致性不符／EXIF 旋轉
"""

import asyncio
import io

import pytest
from PIL import Image

from app.lib.multi_type_ocr import transcript_positions as tp
from app.lib.multi_type_ocr.transcript_processor import TranscriptProcessor
from app.lib.multi_type_ocr.transcript_records import apply_transcript_format
from app.lib.ocr_enhanced.engine_manager import EngineManager
from app.services.analyze_service import AnalyzeService


# ---------------- engine_manager 行框換算 ----------------
class _FakePaddle:
    def __init__(self, result):
        self.result = result
        self.seen_shape = None

    def predict(self, img):
        self.seen_shape = img.shape
        return self.result


def _run_paddle(monkeypatch, result, shape=(200, 400, 3)):
    import numpy as np
    fake = _FakePaddle(result)
    monkeypatch.setattr(EngineManager, "_paddleocr_instance", fake)
    em = EngineManager(engines=["paddleocr"])
    monkeypatch.setattr(em, "_ensure_paddleocr", lambda: fake)
    out = asyncio.run(em._run_paddleocr(np.zeros(shape, dtype=np.uint8)))
    return out, fake


def test_engine_lines_are_bbox_over_predict_image_size(monkeypatch):
    res = [{"rec_texts": ["甲乙", "丙"], "rec_scores": [0.9, 0.7],
            "rec_polys": [[[40, 20], [120, 22], [118, 50], [38, 48]], [[0, 100], [400, 100], [400, 200], [0, 200]]]}]
    out, fake = _run_paddle(monkeypatch, res)
    assert fake.seen_shape[:2] == (200, 400)
    assert out["lines"] == [{"text": "甲乙", "box": [0.095, 0.1, 0.3, 0.25]},
                            {"text": "丙", "box": [0.0, 0.5, 1.0, 1.0]}]
    assert out["text"] == "甲乙\n丙"
    assert out["confidence"] == pytest.approx(0.8)      # text／confidence 不受行框影響


@pytest.mark.parametrize("polys", [None, [[[0, 0], [1, 0], [1, 1], [0, 1]]]])
def test_engine_lines_none_when_polys_missing_or_count_mismatch(monkeypatch, polys):
    res = [{"rec_texts": ["甲", "乙"], "rec_scores": [0.9, 0.7]}]
    if polys is not None:
        res[0]["rec_polys"] = polys
    out, _ = _run_paddle(monkeypatch, res)
    assert out["lines"] is None
    assert out["text"] == "甲\n乙"


# ---------------- 行框交到該頁結果 ----------------
def _proc_with_fake_ocr(delays, with_lines=True):
    """假 OCR:以影像寬度當頁碼,各頁延遲不同(讓並發時後完成的頁蓋掉先完成的頁,若有共用狀態就會露餡)。"""
    p = TranscriptProcessor()

    async def _id(img):
        return img
    p.preprocess = _id

    async def fake_multi(arr):
        page = arr.shape[1]
        await asyncio.sleep(delays[page])
        text = f"第{page}頁甲\n第{page}頁乙"
        er = {"engine": "paddleocr", "text": text, "confidence": 0.9, "processing_time_ms": 1,
              "lines": [{"text": f"第{page}頁甲", "box": [0.1, 0.1, 0.5, 0.2]},
                        {"text": f"第{page}頁乙", "box": [0.1, 0.3, 0.5, 0.4]}] if with_lines else None}
        return text, 0.9, [er]
    p.engine_manager.extract_text_multi_engine = fake_multi
    return p


async def test_concurrent_pages_each_get_own_lines(monkeypatch):
    monkeypatch.setattr(TranscriptProcessor, "_consensus_enabled", staticmethod(lambda: False))
    delays = {11: 0.15, 12: 0.01, 13: 0.08, 14: 0.03}
    p = _proc_with_fake_ocr(delays)
    imgs = [Image.new("RGB", (w, 8)) for w in delays]
    rs = await asyncio.gather(*(p.analyze(im, image_data=None, enable_llm=False) for im in imgs))
    for w, r in zip(delays, rs):
        assert [l["text"] for l in r["_ocr_lines"]] == [f"第{w}頁甲", f"第{w}頁乙"]
        assert r["ocr_raw"]["text"] == f"第{w}頁甲\n第{w}頁乙"
    # 行框沒有留在處理器上
    assert not any("lines" in k for k in vars(p))


async def test_extract_text_swapped_to_two_tuple_still_works(monkeypatch):
    monkeypatch.setattr(TranscriptProcessor, "_consensus_enabled", staticmethod(lambda: False))
    p = _proc_with_fake_ocr({11: 0})
    calls = []

    async def two(img):
        calls.append(1)
        return "地號 123", 0.8
    p.extract_text = two
    r = await p.analyze(Image.new("RGB", (11, 8)), image_data=None, enable_llm=False)
    assert "_ocr_lines" not in r and len(calls) == 1
    assert r["ocr_raw"] == {"text": "地號 123", "confidence": 0.8}


async def test_no_lines_when_engine_gives_none(monkeypatch):
    monkeypatch.setattr(TranscriptProcessor, "_consensus_enabled", staticmethod(lambda: False))
    p = _proc_with_fake_ocr({11: 0}, with_lines=False)
    r = await p.analyze(Image.new("RGB", (11, 8)), image_data=None, enable_llm=False)
    assert "_ocr_lines" not in r


async def test_no_lines_when_fused_text_is_not_paddle_text(monkeypatch):
    monkeypatch.setattr(TranscriptProcessor, "_consensus_enabled", staticmethod(lambda: False))
    p = _proc_with_fake_ocr({11: 0})
    inner = p.engine_manager.extract_text_multi_engine

    async def other_text(arr):
        _t, c, ers = await inner(arr)
        return "別家引擎的文字", c, ers
    p.engine_manager.extract_text_multi_engine = other_text
    r = await p.analyze(Image.new("RGB", (11, 8)), image_data=None, enable_llm=False)
    assert "_ocr_lines" not in r


# ---------------- AnalyzeService 取出、不外流 ----------------
def _page(n):
    return {"page_number": n, "ocr_raw": {"text": "x", "confidence": 0.9}, "rule_postprocessed": {"text": "x", "stats": {}},
            "llm_postprocessed": None, "structured_data": None, "field_confidences": {}, "overall_confidence": 0.9,
            "_ocr_lines": [{"text": "x", "box": [0, 0, 1, 1]}]}


async def _analyze(container):
    svc = AnalyzeService()

    async def s3(*a, **k):
        return "u"

    async def ocr(*a, **k):
        return [_page(1), _page(2)], 2
    svc._upload_to_s3, svc._process_ocr = s3, ocr
    return await svc.analyze(b"x", "a.png", "transcript", False, ocr_lines_out=container) if container is not None \
        else await svc.analyze(b"x", "a.png", "transcript", False)


async def test_analyze_hands_lines_to_caller_only_and_leaves_none_in_response():
    box = {}
    res = await _analyze(box)
    assert set(box) == {1, 2} and box[2][0]["text"] == "x"
    assert "_ocr_lines" not in str(res)
    assert all("_ocr_lines" not in p for p in res["pages"])


async def test_analyze_without_container_discards_lines():
    res = await _analyze(None)
    assert "_ocr_lines" not in str(res)


# ---------------- 照片值 → 行位置 ----------------
def L(text, y):
    return {"text": text, "box": [0.1, y, 0.9, round(y + 0.05, 4)]}


def photo_result(lines_by_page, records=None, structured=None):
    pages = []
    for pno, lines in lines_by_page.items():
        pages.append({"page_number": pno, "ocr_raw": {"text": "\n".join(l["text"] for l in lines), "confidence": 0.9},
                      "rule_postprocessed": {"text": "\n".join(l["text"] for l in lines)}, "structured_data": None})
    return {"document_fields": {"transcript_records": records or []}, "pages": pages}


def rec(**kw):
    r = {"類型": "建物", "謄本": {"編號": None}, "標示部": {"層次": [], "總面積": None, "主要用途": None}, "所有權部": [],
         "判定": {}}
    r.update(kw)
    return r


def png(orientation=None):
    im = Image.new("RGB", (4, 4))
    buf = io.BytesIO()
    ex = im.getexif()
    if orientation is not None:
        ex[0x0112] = orientation
    im.save(buf, "PNG", exif=ex)
    return buf.getvalue()


def compute(pages_lines, filled, file_contents=None, records=None, pages=None):
    res = photo_result(pages_lines)
    return tp.compute_photo_positions(pages or res["pages"], pages_lines, file_contents or png(), records or filled, filled)


def test_unique_line():
    lines = [L("主要用途 住家用", 0.1), L("總面積 123.45", 0.2)]
    m = compute({1: lines}, [rec(標示部={"層次": [], "總面積": 123.45, "主要用途": "住家用"})])[0]
    assert m["標示部.主要用途"][1] == {"page": 1, "box": [0.1, 0.1, 0.9, 0.15], "unit": "ratio"}
    assert m["標示部.總面積"][1]["box"][1] == 0.2


def test_multi_line_prefers_line_with_key_before_value():
    lines = [L("備註 住家用", 0.1), L("主要用途 住家用", 0.2), L("用途 住家用", 0.3)]
    m = compute({1: lines}, [rec(標示部={"層次": [], "總面積": None, "主要用途": "住家用"})])[0]
    assert m["標示部.主要用途"][1]["box"][1] == 0.2          # 第一個「鍵名在值之前」的行(「備註」行沒有鍵名)


def test_multi_line_without_key_takes_first():
    lines = [L("甲 住家用", 0.1), L("乙 住家用", 0.2)]
    m = compute({1: lines}, [rec(標示部={"層次": [], "總面積": None, "主要用途": "住家用"})])[0]
    assert m["標示部.主要用途"][1]["box"][1] == 0.1


def test_zero_lines_gives_no_entry():
    m = compute({1: [L("無關的字", 0.1)]}, [rec(標示部={"層次": [], "總面積": None, "主要用途": "住家用"})])[0]
    assert "標示部.主要用途" not in m


def test_number_matches_by_number_token():
    lines = [L("面積 1,234.50 平方公尺", 0.1)]
    m = compute({1: lines}, [rec(標示部={"層次": [], "總面積": 1234.5, "主要用途": None})])[0]
    assert m["標示部.總面積"][1]["box"][1] == 0.1


def test_inconsistent_page_text_gives_none():
    lines = [L("主要用途 住家用", 0.1)]
    res = photo_result({1: lines})
    res["pages"][0]["ocr_raw"]["text"] += "\n多出來的字"
    filled = [rec(標示部={"層次": [], "總面積": None, "主要用途": "住家用"})]
    assert tp.compute_photo_positions(res["pages"], {1: lines}, png(), filled, filled) is None


def test_exif_rotation_gives_none_but_orientation_1_and_missing_ok():
    lines = [L("主要用途 住家用", 0.1)]
    filled = [rec(標示部={"層次": [], "總面積": None, "主要用途": "住家用"})]
    assert compute({1: lines}, filled, png(6)) is None
    assert compute({1: lines}, filled, png(1)) is not None
    assert compute({1: lines}, filled, png(None)) is not None


def test_text_layer_page_not_used():
    lines = [L("主要用途 住家用", 0.1)]
    res = photo_result({1: lines})
    res["pages"][0]["text_layer"] = True
    filled = [rec(標示部={"層次": [], "總面積": None, "主要用途": "住家用"})]
    assert tp.compute_photo_positions(res["pages"], {1: lines}, png(), filled, filled) is None


def test_position_page_is_hit_page_for_multi_page_pdf():
    # 無文字層 PDF(兩頁):值只出現在第 2 頁 → page=2;值在兩頁都有 → 頁序第一個
    p1 = [L("甲 乙", 0.1)]
    p2 = [L("主要用途 住家用", 0.3), L("甲 乙", 0.5)]
    filled = [rec(標示部={"層次": [], "總面積": None, "主要用途": "住家用"}, 謄本={"編號": "乙"})]
    m = compute({1: p1, 2: p2}, filled, file_contents=b"%PDF-1.4")[0]
    assert m["標示部.主要用途"][1]["page"] == 2
    assert m["謄本.編號"][1]["page"] == 1



def test_empty_sheet_page_set_falls_back_to_all_pages(monkeypatch):
    # 帳目有這張、但沒記到任何頁(OCR 文字解析不出帶來源的值)→ 候選用全部頁,不是一個都不給
    p1 = [L("甲 乙", 0.1)]
    p2 = [L("主要用途 住家用", 0.3)]
    filled = [rec(標示部={"層次": [], "總面積": None, "主要用途": "住家用"})]
    monkeypatch.setattr(tp, "_sheet_page_sets", lambda pages, records: [set()])
    m = compute({1: p1, 2: p2}, filled, file_contents=b"%PDF-1.4")[0]
    assert m["標示部.主要用途"][1]["page"] == 2
    monkeypatch.setattr(tp, "_sheet_page_sets", lambda pages, records: [{0}])   # 有記到頁 → 只用那些頁
    assert "標示部.主要用途" not in compute({1: p1, 2: p2}, filled, file_contents=b"%PDF-1.4")[0]


def test_multi_line_prefers_line_with_most_keys_before_value():
    # 「總面積 95.41」只對上「面積」,「層次面積 95.41」對上「層次」「面積」→ 取後者(AM-8)
    lines = [L("總面積：95.41平方公尺", 0.1), L("層次面積：95.41平方公尺", 0.2)]
    filled = [rec(標示部={"層次": [{"層次": "二層", "面積": 95.41}], "總面積": None, "主要用途": None})]
    m = compute({1: lines}, filled)[0]
    assert m["標示部.層次[0].面積"][1]["box"][1] == 0.2


def _head(kind, no, y0=0.0):
    return [L(f"{kind}登記第二類謄本", y0), L(f"中正區中正段二小段{no}{'建號' if kind == '建物' else '地號'}", y0 + 0.01), L("頁次：1", y0 + 0.02)]


def test_multi_page_sheet_uses_pages_whose_head_prints_its_number(monkeypatch):
    # 土地 1、2 頁＋建物第 3 頁,帳目沒記到頁:建物那張只找頁首印 00465-000 的第 3 頁(AM-8)
    monkeypatch.setattr(tp, "_sheet_page_sets", lambda pages, records: None)
    pl = {1: _head("土地", "0221-0000") + [L("所有權人：黃**", 0.4)],
          2: _head("土地", "0221-0001") + [L("所有權人：黃**", 0.4)],
          3: _head("建物", "00465-000") + [L("所有權人：黃**", 0.5)]}
    filled = [rec(謄本={"編號": "00465-000"}, 所有權部=[{"所有權人": "黃**"}])]
    m = compute(pl, filled, file_contents=b"%PDF-1.4")[0]
    assert m["所有權部[0].所有權人"][1]["page"] == 3
    assert m["類型"][1]["page"] == 3 and m["類型"][1]["box"][1] == 0.0


def test_multi_page_head_falls_back_to_kind_then_all_pages(monkeypatch):
    monkeypatch.setattr(tp, "_sheet_page_sets", lambda pages, records: None)
    pl = {1: _head("土地", "0221-0000") + [L("所有權人：黃**", 0.4)],
          2: _head("建物", "00465-000") + [L("所有權人：黃**", 0.5)],
          3: [L("所有權人：黃**", 0.6)]}                       # 頁首讀不到的頁一律留著
    filled = [rec(謄本={"編號": None}, 所有權部=[{"所有權人": "黃**"}])]  # 沒有編號 → 比種類「建物登記」
    m = compute(pl, filled, file_contents=b"%PDF-1.4")[0]
    assert m["所有權部[0].所有權人"][1]["page"] == 2
    filled = [rec(類型=None, 謄本={"編號": None}, 所有權部=[{"所有權人": "黃**"}])]  # 都沒有 → 全部頁,頁序第一
    assert compute(pl, filled, file_contents=b"%PDF-1.4")[0]["所有權部[0].所有權人"][1]["page"] == 1


def test_same_value_in_list_items_maps_to_kth_line():
    # 三個層次面積都是 96.51 → 依序框第 1、2、3 行;同值次數多於行數 → 取最後一行(AM-9)
    lines = [L("層次：二層 層次面積：96.51平方公尺", 0.1), L("層次：三層 層次面積：96.51平方公尺", 0.2),
             L("層次：四層 層次面積：96.51平方公尺", 0.3)]
    floors = [{"層次": None, "面積": 96.51} for _ in range(4)]
    m = compute({1: lines}, [rec(標示部={"層次": floors, "總面積": None, "主要用途": None})])[0]
    assert [m[f"標示部.層次[{i}].面積"][1]["box"][1] for i in range(4)] == [0.1, 0.2, 0.3, 0.3]


def test_same_value_continuation_lines_without_key():
    # 只有第一行印鍵名,續行只印數字 → 從鍵名行起往下數;前面的「總面積」行不算(AM-9)
    lines = [L("總面積：96.51平方公尺", 0.05), L("層次面積：96.51平方公尺", 0.1), L("96.51平方公尺", 0.2), L("96.51平方公尺", 0.3)]
    floors = [{"層次": None, "面積": 96.51} for _ in range(3)]
    m = compute({1: lines}, [rec(標示部={"層次": floors, "總面積": None, "主要用途": None})])[0]
    assert [m[f"標示部.層次[{i}].面積"][1]["box"][1] for i in range(3)] == [0.1, 0.2, 0.3]


def test_list_item_prefers_line_with_its_other_field_values():
    # 一行印兩筆地號、段小段只印一次;第 2 筆的段小段要框同一行,不是往下數到別頁頁首(AM-9)
    p1 = [L("中正區公園段三小段00312-000建號", 0.05), L("建物坐落地號：公園段三小段 0167-0000 0168-0000", 0.25)]
    p2 = [L("中正區公園段三小段00312-000建號", 0.05)]
    lots = [{"段小段": "公園段三小段", "編號": "0167-0000"}, {"段小段": "公園段三小段", "編號": "0168-0000"}]
    filled = [rec(標示部={"層次": [], "總面積": None, "主要用途": None, "建物坐落地號": lots})]
    m = compute({1: p1, 2: p2}, filled, file_contents=b"%PDF-1.4")[0]
    assert [m[f"標示部.建物坐落地號[{i}].段小段"][1]["box"][1] for i in range(2)] == [0.25, 0.25]


def test_other_field_values_in_lower_scored_lines_do_not_win():
    # 他項權利部「債務人」行也印了所有權人名與「全部」:所有權人仍框有鍵名的那一行(AM-9 第三版)
    lines = [L("所有權人：志嘉建設股份有限公司", 0.5), L("權利範圍：全部", 0.55),
             L("債務人及債務額比例：志嘉建設股份有限公司債務額比例全部", 0.8)]
    filled = [rec(所有權部=[{"所有權人": "志嘉建設股份有限公司", "權利範圍": "全部"}])]
    m = compute({1: lines}, filled)[0]
    assert m["所有權部[0].所有權人"][1]["box"][1] == 0.5
    assert m["所有權部[0].權利範圍"][1]["box"][1] == 0.55


def test_other_field_values_unused_when_no_key_matches():
    # 編號被 OCR 拆到沒印鍵名的下一行;後面「共同擔保地號」行也印了段小段與編號 → 仍取第一個候選(AM-9 第四版)
    p1 = [L("建物坐落地號：過溝段", 0.25), L("0555-0000", 0.26)]
    p2 = [L("共同擔保地號：過溝段0555-0000", 0.1)]
    filled = [rec(標示部={"層次": [], "總面積": None, "主要用途": None,
                       "建物坐落地號": [{"段小段": "過溝段", "編號": "0555-0000"}]})]
    m = compute({1: p1, 2: p2}, filled, file_contents=b"%PDF-1.4")[0]
    assert m["標示部.建物坐落地號[0].編號"][1]["page"] == 1

# ---------------- apply_transcript_format 串接 ----------------
def _all_positions(o):
    if isinstance(o, dict):
        if set(o) == {"value", "position"}:
            yield o["position"]
            return
        for v in o.values():
            yield from _all_positions(v)
    elif isinstance(o, list):
        for v in o:
            yield from _all_positions(v)


def test_apply_format_wraps_photo_position_and_keeps_none_without_lines():
    from app.lib.multi_type_ocr.transcript_full_parser import parse_transcript_pages
    from app.lib.multi_type_ocr.transcript_records import build_transcript_records
    from tests.unit.test_transcript_full_parser import P1
    lines = [L(t, round(0.01 * i, 4)) for i, t in enumerate(P1.split("\n")) if t.strip()]
    text = "\n".join(l["text"] for l in lines)
    ts = parse_transcript_pages([text])
    res = {"document_fields": {"transcripts": ts, "transcript_records": build_transcript_records(ts)},
           "pages": [{"page_number": 1, "ocr_raw": {"text": text, "confidence": 0.9},
                      "rule_postprocessed": {"text": text}, "structured_data": None}]}
    out = apply_transcript_format(res, png(), ocr_lines={1: lines})
    ps = [p for p in _all_positions(out["document_fields"]["transcript_records"]) if p is not None]
    assert ps and all(p["page"] == 1 and p["unit"] == "ratio" and len(p["box"]) == 4 for p in ps)
    out2 = apply_transcript_format(res, png())
    assert all(p is None for p in _all_positions(out2["document_fields"]["transcript_records"]))
