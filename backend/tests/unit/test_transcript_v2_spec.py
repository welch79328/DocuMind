"""S4: INTEGRATION.md §3.1.4 規格句〔V2-xx〕對應的行為測試(plan-s4.md §2.5)。

只測既有行為,不改 backend/app/。測試名 test_v2_xx_ 的 xx 是規格行為 ID。
"""

import copy
import inspect
from unittest.mock import AsyncMock, patch

from PIL import Image

from app.api.v1 import analyze as analyze_api
from app.database import get_db
from app.lib.multi_type_ocr.transcript_processor import TranscriptProcessor
from app.lib.multi_type_ocr.transcript_records import (
    _wrap,
    _wrap_record,
    apply_transcript_format,
    build_transcript_records,
    fill_from_rules,
)
from app.main import app
from tests.unit.test_transcript_format_v2 import OLD_KEYS, _client, _post, _rec, _result, db_override  # noqa: F401
from tests.unit.test_transcript_positions_photo import L, _all_positions, _proc_with_fake_ocr, compute, png, rec

# 兩次請求之間本來就會不同的鍵(與帶不帶參數無關):review_item_id 是每次新建的複核佇列項目 id
VOLATILE = {"review_item_id"}


def _strip(o, keys):
    if isinstance(o, dict):
        return {k: _strip(v, keys) for k, v in o.items() if k not in keys}
    if isinstance(o, list):
        return [_strip(v, keys) for v in o]
    return o


def _walk_keys(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield k
            yield from _walk_keys(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk_keys(v)


def _one_building(no="100"):
    return _rec(no, "建物")


# ---------------- 參數與端點 ----------------
async def test_v2_01_invalid_value_400_for_contract(db_override):
    resp = await _post(doc_type="contract", transcript_format="v3")
    assert resp.status_code == 400 and resp.json()["error_code"] == "INVALID_TRANSCRIPT_FORMAT"


async def test_v2_01_empty_value_400(db_override):
    resp = await _post(transcript_format="")
    assert resp.status_code == 400 and resp.json()["error_code"] == "INVALID_TRANSCRIPT_FORMAT"


async def test_v2_02_non_transcript_whole_response_equal(db_override):
    a = await _post(doc_type="contract")
    b = await _post(doc_type="contract", transcript_format="v2")
    assert a.status_code == b.status_code == 200
    assert _strip(a.json(), VOLATILE) == _strip(b.json(), VOLATILE)
    assert "building_number" in b.json()["document_fields"]          # 沒被轉成帶參數格式


async def _post_batch(**extra):
    with patch("app.api.v1.analyze.AnalyzeService") as M:
        M.return_value.analyze = AsyncMock(return_value=_result())
        async with _client() as c:
            data = {"document_type": "transcript", "enable_llm": "false", **extra}
            return await c.post("/api/v1/analyze/batch",
                                files=[("files", ("t.pdf", b"%PDF-1.4 fake", "application/pdf"))], data=data)


async def test_v2_03_batch_ignores_param(db_override):
    assert "transcript_format" not in inspect.signature(analyze_api.analyze_batch).parameters
    a, b = await _post_batch(), await _post_batch(transcript_format="v2")
    assert a.status_code == b.status_code == 200
    assert _strip(a.json(), VOLATILE) == _strip(b.json(), VOLATILE)
    df = b.json()["results"][0]["result"]["document_fields"]
    assert "building_number" in df and "transcripts" in df              # 仍是不帶參數的舊格式


async def test_v2_04_review_queue_same_as_without_param(feedback_session):
    from app.services.review_queue_service import ReviewQueueService
    app.dependency_overrides[get_db] = lambda: feedback_session
    try:
        out = []
        for extra in ({}, {"transcript_format": "v2"}):
            with patch("app.api.v1.analyze.AnalyzeService") as M:
                res = _result()
                res["pages"][0]["ocr_raw"] = {"text": "t", "confidence": 0.5}
                M.return_value.analyze = AsyncMock(return_value=res)
                async with _client() as c:
                    resp = await c.post("/api/v1/analyze",
                                        files={"file": ("t.pdf", b"%PDF-1.4 fake", "application/pdf")},
                                        data={"document_type": "transcript", "enable_llm": "false", **extra})
            assert resp.status_code == 200
            out.append(resp.json())
        plain, v2 = out
        assert plain["needs_review"] == v2["needs_review"] is True
        assert plain["review_item_id"] is not None and v2["review_item_id"] is not None
        svc = ReviewQueueService(feedback_session)
        qa = svc.get_item(plain["review_item_id"])["original_result"]
        qb = svc.get_item(v2["review_item_id"])["original_result"]
        assert _strip(qa, VOLATILE) == _strip(qb, VOLATILE)
        assert set(qb) == {"pages", "field_confidences"}                # 佇列存 pages 與 field_confidences
        assert OLD_KEYS <= set(qb["pages"][0]["structured_data"])      # pages 是不帶參數(未轉換)的
    finally:
        app.dependency_overrides.pop(get_db, None)


# ---------------- 移除與包裝 ----------------
def test_v2_06_building_evidence_and_share_slots_kept():
    r = _result()
    r["pages"][0]["structured_data"].update({"has_building_evidence": True, "share_slots": [{"a": 1}]})
    sd = apply_transcript_format(r)["pages"][0]["structured_data"]
    assert sd["has_building_evidence"] is True and sd["share_slots"] == [{"a": 1}]
    assert not OLD_KEYS & set(sd)


def test_v2_07_absent_or_empty_records_still_drop_old_keys():
    for mode in ("empty", "absent"):
        r = _result()
        if mode == "empty":
            r["document_fields"]["transcript_records"] = []
        else:
            del r["document_fields"]["transcript_records"]
        df = apply_transcript_format(r)["document_fields"]
        assert not (OLD_KEYS | {"transcripts"}) & set(df)
        assert df.get("transcript_records") in ([], None) and ("transcript_records" in df) == (mode == "empty")


def test_v2_08_empty_string_wrapped():
    r = _one_building("")
    w = _wrap_record(r)
    assert w["謄本"]["編號"] == {"value": "", "position": None}
    assert _wrap(True) == {"value": True, "position": None} and _wrap(1.5) == {"value": 1.5, "position": None}
    assert _wrap(None) is None


# ---------------- 補值條件 ----------------
def test_v2_10_multi_sheet_no_number_or_land_numbers():
    recs = [_rec(None, "建物"), _rec(None, "建物")]
    f = {"building_number": "100", "land_numbers": [{"section": "某段", "number": "0001-0000"}]}
    out = fill_from_rules(recs, f)
    for r in out:
        assert r["謄本"]["編號"] is None and r["標示部"]["建物坐落地號"] == []


def test_v2_11_null_type_sheet_untouched():
    recs = [_rec(None, None), _rec("100", "建物")]
    before = copy.deepcopy(recs[0])
    out = fill_from_rules(recs, {"building_number": "100", "main_usage": "住家用",
                                 "owners": [{"part": "building", "name": "甲"}]})
    assert out[0] == before                                             # 整張不補、判定也不重算
    # 只有整份 1 張時才由 building_number 推出 類型
    assert fill_from_rules([_rec(None, None)], {"building_number": "100"})[0]["類型"] == "建物"


def test_v2_12_nonempty_list_not_merged():
    r = fill_from_rules([_one_building()], {})[0]
    r["所有權部"] = [dict(r["所有權部"][0]) if r["所有權部"] else {"所有權人": "原有"}]
    out = fill_from_rules([r], {"owners": [{"part": "building", "name": "新的"}]})[0]
    assert len(out["所有權部"]) == 1 and out["所有權部"][0]["所有權人"] != "新的"


def test_v2_14_unprinted_mark_part_becomes_skeleton_multi_sheet():
    recs = [_rec("1", "建物"), _rec("2", "建物")]
    assert all(r["標示部"] is None and r["部是否印出"]["標示部"] is False for r in recs)
    out = fill_from_rules(recs, {})
    for r in out:
        m = r["標示部"]
        assert isinstance(m, dict) and all(v in (None, []) for v in m.values())
        assert r["部是否印出"]["標示部"] is False


def test_v2_15_filled_other_right_sets_verdict_but_not_printed_flag():
    r = _one_building()
    assert r["他項權利部"] == [] and r["部是否印出"]["他項權利部"] is False
    out = fill_from_rules([r], {"other_right_type": "抵押權"})[0]
    assert out["他項權利部"][0]["權利種類"] == "抵押權"
    assert out["判定"]["他項權利"] == "有"
    assert out["部是否印出"] == r["部是否印出"]                        # 不隨補值改


def test_v2_24_s1_unfilled_keys_change_nothing():
    recs = [_one_building()]
    f = {"section": "某段", "subsection": "一小段", "print_date": "民國113年05月06日", "seizure_mark": "查封"}
    assert fill_from_rules(recs, f) == fill_from_rules(recs, {})


def test_v2_25_list_covered_singles_change_nothing():
    recs = [_one_building()]
    f = {"floor_level": "一層", "floor_area": "10.5", "sub_building_usage": "陽台", "sub_building_area": "3",
         "shared_build_number": "200", "shared_area": "30", "owner": "甲", "rights_scope": "全部",
         "land_rights_scope": "1分之1", "floors": [], "sub_buildings": [], "shared_parts": [], "owners": []}
    assert fill_from_rules(recs, f) == fill_from_rules(recs, {})


def test_v2_26_computed_items_absent():
    r = _result()
    df = r["document_fields"]
    df["shared_parts"] = [{"build_number": "200", "area": "30", "rights_scope": "10分之1", "share_area": 3.0,
                           "parking": [{"no": "1"}], "parking_total": 1}]
    df["floor_area_checks"] = [{"ok": True}]
    out = apply_transcript_format(r)
    keys = set(_walk_keys(out))
    assert not {"share_area", "parking", "parking_total", "floor_area_checks"} & keys


def test_v2_27_wrapped_leaf_has_only_value_and_position():
    recs = apply_transcript_format(_result())["document_fields"]["transcript_records"]

    def leaves(o, top=True):
        if isinstance(o, dict):
            if set(o) == {"value", "position"}:
                yield o
                return
            for k, v in o.items():
                if top and k in ("判定", "部是否印出"):
                    continue
                yield from leaves(v, False)
        elif isinstance(o, list):
            for v in o:
                yield from leaves(v, False)
    got = [x for r in recs for x in leaves(r)]
    assert got and all(set(x) == {"value", "position"} for x in got)
    assert not any("confidence" in k or "source" in k for k in _walk_keys(recs))


# ---------------- 照片位置 ----------------
def test_v2_19_box_clamped():
    lines = [{"text": "主要用途 住家用", "box": [-0.05, 0.1, 1.2, 0.15]}]
    m = compute({1: lines}, [rec(標示部={"層次": [], "總面積": None, "主要用途": "住家用"})])[0]
    assert m["標示部.主要用途"][1]["box"] == [0.0, 0.1, 1.0, 0.15]


def test_v2_19_filled_value_framed_on_photo():
    """照片補進的值(原本 null,由 25 欄 main_usage 補)經 apply_transcript_format 也找行給框"""
    r = fill_from_rules([_one_building()], {})[0]
    assert r["標示部"]["主要用途"] is None
    lines = [L("主要用途 住家用", 0.2)]
    res = {"document_fields": {"transcript_records": [r], "main_usage": "住家用", "building_number": "100"},
           "pages": [{"page_number": 1, "ocr_raw": {"text": lines[0]["text"], "confidence": 0.9},
                      "rule_postprocessed": {"text": lines[0]["text"]}, "structured_data": None}]}
    out = apply_transcript_format(res, png(), ocr_lines={1: lines})
    m = out["document_fields"]["transcript_records"][0]["標示部"]
    assert m["主要用途"]["value"] == "住家用"
    assert m["主要用途"]["position"] == {"page": 1, "box": lines[0]["box"], "unit": "ratio"}


def test_v2_21_bool_value_has_null_position():
    lines = [L("True 住家用", 0.1)]
    m = compute({1: lines}, [rec(標示部={"層次": [], "總面積": None, "主要用途": "住家用", "旗標": True})])[0]
    assert "標示部.旗標" not in m and "標示部.主要用途" in m


async def test_v2_21_consensus_mode_has_no_lines(monkeypatch):
    monkeypatch.setattr(TranscriptProcessor, "_consensus_enabled", staticmethod(lambda: True))
    p = _proc_with_fake_ocr({11: 0})
    r = await p.analyze(Image.new("RGB", (11, 8)), image_data=None, enable_llm=False)
    assert "_ocr_lines" not in r
    text = (r.get("ocr_raw") or {}).get("text") or ""
    recs = [_one_building()]
    recs[0]["標示部"] = fill_from_rules(recs, {})[0]["標示部"]
    recs[0]["標示部"]["主要用途"] = "第11頁甲"
    res = {"document_fields": {"transcript_records": recs},
           "pages": [{"page_number": 1, "ocr_raw": {"text": text, "confidence": 0.9}, "structured_data": None}]}
    lines = {1: r["_ocr_lines"]} if "_ocr_lines" in r else {}
    out = apply_transcript_format(res, png(), ocr_lines=lines)
    assert all(x is None for x in _all_positions(out["document_fields"]["transcript_records"]))


def test_v2_22_mixed_text_layer_pdf():
    ocr = [L("建物門牌 某路1號", 0.3)]
    pages = [{"page_number": 1, "text_layer": True, "ocr_raw": {"text": "主要用途 住家用\n建物門牌 某路1號"},
              "rule_postprocessed": {"text": "主要用途 住家用\n建物門牌 某路1號"}, "structured_data": None},
             {"page_number": 2, "text_layer": False, "ocr_raw": {"text": "建物門牌 某路1號"},
              "rule_postprocessed": {"text": "建物門牌 某路1號"}, "structured_data": None}]
    r = fill_from_rules([_one_building()], {})[0]
    r["標示部"]["主要用途"] = "住家用"          # 只印在有文字層的第 1 頁
    r["標示部"]["建物門牌"] = "某路1號"         # 第 1 頁有,無文字層的第 2 頁也有
    res = {"document_fields": {"transcript_records": [r]}, "pages": pages}
    out = apply_transcript_format(res, b"%PDF-1.4 fake", ocr_lines={2: ocr})
    m = out["document_fields"]["transcript_records"][0]["標示部"]
    assert m["主要用途"] == {"value": "住家用", "position": None}
    assert m["建物門牌"]["position"] == {"page": 2, "box": [0.1, 0.3, 0.9, 0.35], "unit": "ratio"}


def test_v2_28_photo_page_count_framed_to_any_line():
    lines = [L("甲 2", 0.4)]                    # 沒有「頁數」鍵名,只是含數字 2 的行
    m = compute({1: lines}, [rec(謄本={"編號": None, "頁數": 2})])[0]
    assert m["謄本.頁數"][1]["box"][1] == 0.4


def test_v2_29_enable_llm_defaults_true():
    d = inspect.signature(analyze_api.analyze_document).parameters["enable_llm"].default
    assert getattr(d, "default", d) is True

