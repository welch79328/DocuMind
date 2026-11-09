"""S1: /analyze transcript_format=v2 —— 規則補值、{value, position} 包裝、舊鍵移除。"""

import copy
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.database import get_db
from app.lib.multi_type_ocr.transcript_field_extractor import TranscriptFieldExtractor
from app.lib.multi_type_ocr.transcript_records import (
    apply_transcript_format,
    build_transcript_records,
    fill_from_rules,
)
from app.main import app
from app.services.analyze_service import _LIST_DETAIL_KEYS

OLD_KEYS = set(TranscriptFieldExtractor.KEY_FIELDS) | set(_LIST_DETAIL_KEYS)


def _rec(no=None, kind=None):
    r = build_transcript_records([{}])[0]
    r["類型"] = kind
    r["謄本"]["編號"] = no
    return r


def _building(no=None):
    return fill_from_rules([_rec(no, "建物")], {})[0]  # 建立標示部骨架


def _wrapped(v):
    return {"value": v, "position": None}


# ---------------- R1 補值規則 ----------------
class TestFill:
    def test_single_sheet_fills_building_values(self):
        f = {"building_number": "100", "building_address": "某路1號", "main_usage": "住家用",
             "total_area": "37.52", "completion_date": "民國 70 年 1 月 2 日"}
        out = fill_from_rules([_rec()], f)[0]
        assert out["類型"] == "建物" and out["謄本"]["編號"] == "100"
        m = out["標示部"]
        assert m["建物門牌"] == "某路1號" and m["主要用途"] == "住家用"
        assert m["總面積"] == 37.52 or m["總面積"] == "37.52"
        assert m["建築完成日期"] == "民國 70 年 1 月 2 日"

    def test_multi_sheet_no_single_value_fill(self):  # (a)
        recs = [_rec("100", "建物"), _rec("200", "建物")]
        out = fill_from_rules(recs, {"building_address": "某路1號", "building_number": "100"})
        assert all(r["標示部"] is None or r["標示部"]["建物門牌"] is None for r in out)
        assert out[0]["謄本"]["編號"] == "100" and out[1]["謄本"]["編號"] == "200"

    def test_list_ownership_by_transcript_id(self):  # (b)
        recs = [_rec("100", "建物"), _rec("200", "建物")]
        f = {"owners": [
            {"part": "building", "transcript_id": "100", "order": "0001", "name": "甲", "rights_scope": "全部"},
            {"part": "building", "transcript_id": "200", "order": "0001", "name": "乙", "rights_scope": "全部"},
            {"part": "building", "order": "0002", "name": "無歸屬"},
        ]}
        out = fill_from_rules(recs, f)
        assert [o["所有權人"] for o in out[0]["所有權部"]] == ["甲"]
        assert [o["所有權人"] for o in out[1]["所有權部"]] == ["乙"]

    def test_list_item_without_tid_belongs_when_one_sheet(self):
        out = fill_from_rules([_rec("100", "建物")],
                              {"owners": [{"part": "building", "order": "1", "name": "甲"}]})[0]
        assert out["所有權部"][0]["所有權人"] == "甲"
        assert out["所有權部"][0]["登記次序"] == "1"

    def test_owner_part_must_match_type(self):
        out = fill_from_rules([_rec("100", "建物")],
                              {"owners": [{"part": "land", "order": "1", "name": "甲"}]})[0]
        assert out["所有權部"] == []

    def test_no_overwrite(self):  # (c)
        r = _building("100")
        r["標示部"]["主要用途"] = "原值"
        r["所有權部"] = [{"所有權人": "原"}]
        out = fill_from_rules([r], {"main_usage": "新值", "owners": [{"part": "building", "name": "新"}]})[0]
        assert out["標示部"]["主要用途"] == "原值"
        assert out["所有權部"] == [{"所有權人": "原"}]

    @pytest.mark.parametrize("date,ok", [("民國", False), ("民國 70 年 1 月", False), ("70年1月2日", True)])
    def test_date_check(self, date, ok):  # (d)
        out = fill_from_rules([_rec("100", "建物")], {"completion_date": date})[0]
        assert (out["標示部"]["建築完成日期"] == date) is ok

    def test_land_values_and_verdict_recomputed(self):
        out = fill_from_rules([_rec(None, None)], {"land_number": "5", "area": "100", "land_use_zone": "住宅區"})[0]
        assert out["類型"] == "土地" and out["標示部"]["使用分區"] == "住宅區"
        assert set(out["判定"]) == {"他項權利", "限制登記", "信託"}

    def test_other_right_filled_only_when_one_sheet(self):
        f = {"other_right_type": "抵押權", "building_number": "1"}
        assert fill_from_rules([_rec()], f)[0]["他項權利部"][0]["權利種類"] == "抵押權"
        multi = fill_from_rules([_rec("1", "建物"), _rec("2", "建物")], f)
        assert all(r["他項權利部"] == [] for r in multi)


# ---------------- 包裝與移除 ----------------
def _result():
    recs = [_rec()]
    df = {k: "x" for k in TranscriptFieldExtractor.KEY_FIELDS}
    df["building_number"] = "100"
    df["building_address"] = "某路1號"
    df["owners"] = [{"part": "building", "order": "1", "name": "甲", "rights_scope": "全部"}]
    for k in _LIST_DETAIL_KEYS:
        df.setdefault(k, [])
    df.update({"transcripts": [{"a": 1}], "transcript_records": recs,
               "field_confidences": {"area": 0.9}, "needs_confirmation": ["area"]})
    sd = {k: "x" for k in OLD_KEYS}
    sd.update({"validation_warnings": ["w"], "_flag": True, "other": 1})
    return {"file_name": "t.pdf", "file_url": None, "total_pages": 2,
            "stats": {"total_time_ms": 1, "total_pages": 2, "llm_pages_used": 0, "estimated_cost": 0.0},
            "document_type": "transcript", "pages": [
        {"page_number": 1, "structured_data": sd}, {"page_number": 2, "structured_data": None}],
        "document_fields": df}


class TestApply:
    def test_input_not_mutated(self):
        r = _result()
        before = copy.deepcopy(r)
        out = apply_transcript_format(r)
        assert r == before and out is not r

    def test_wrap_shape(self):
        rec = apply_transcript_format(_result())["document_fields"]["transcript_records"][0]
        assert rec["謄本"]["編號"] == _wrapped("100")
        assert rec["標示部"]["建物門牌"] == _wrapped("某路1號")
        assert rec["標示部"]["主要用途"] == _wrapped("x")  # 由規則補入後也要包
        assert rec["標示部"]["登記日期"] is None            # null 葉子不包
        assert rec["所有權部"][0]["所有權人"] == _wrapped("甲")
        assert rec["所有權部"][0]["統一編號"] is None
        assert rec["類型"] == _wrapped("建物")
        assert rec["判定"]["他項權利"] in ("有", "未見", "無法判定")   # 不包
        assert rec["部是否印出"] == {"標示部": False, "所有權部": False, "他項權利部": False}

    def test_document_fields_keys(self):
        df = apply_transcript_format(_result())["document_fields"]
        assert not (OLD_KEYS | {"transcripts"}) & set(df)
        assert df["field_confidences"] == {"area": 0.9} and df["needs_confirmation"] == ["area"]
        assert "transcript_records" in df

    def test_structured_data_remove_list_only(self):
        pages = apply_transcript_format(_result())["pages"]
        sd = pages[0]["structured_data"]
        assert not OLD_KEYS & set(sd)
        assert sd == {"validation_warnings": ["w"], "_flag": True, "other": 1}
        assert pages[1]["structured_data"] is None

    def test_removed_key_sets(self):
        assert len(TranscriptFieldExtractor.KEY_FIELDS) == 25 and len(_LIST_DETAIL_KEYS) == 6


# ---------------- API ----------------
def _client():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@pytest.fixture
def db_override(feedback_session):
    app.dependency_overrides[get_db] = lambda: feedback_session
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_db, None)


async def _post(doc_type="transcript", **extra):
    with patch("app.api.v1.analyze.AnalyzeService") as M:
        res = _result()
        res["document_type"] = doc_type
        M.return_value.analyze = AsyncMock(return_value=res)
        async with _client() as c:
            data = {"document_type": doc_type, "enable_llm": "false", **extra}
            return await c.post("/api/v1/analyze",
                                files={"file": ("t.pdf", b"%PDF-1.4 fake", "application/pdf")}, data=data)


class TestApi:
    async def test_param_absent_unchanged(self, db_override):
        body = (await _post()).json()
        assert body["document_fields"]["building_number"] == "100"
        assert "transcripts" in body["document_fields"]
        assert body["pages"][0]["structured_data"]["owners"] == "x"

    async def test_v2_applied(self, db_override):
        resp = await _post(transcript_format="v2")
        assert resp.status_code == 200
        df = resp.json()["document_fields"]
        assert "building_number" not in df and "transcripts" not in df
        assert df["transcript_records"][0]["謄本"]["編號"] == {"value": "100", "position": None}

    async def test_v2_passes_uploaded_bytes_to_transform(self, db_override):
        """S2:電子 PDF 位置要從上傳原檔取,API 第 8 步把 contents 傳進轉換"""
        from app.lib.multi_type_ocr import transcript_records as tr
        seen = {}
        real = tr.apply_transcript_format

        def spy(result, file_contents=None):
            seen["contents"] = file_contents
            return real(result, file_contents)
        with patch.object(tr, "apply_transcript_format", spy):
            resp = await _post(transcript_format="v2")
        assert resp.status_code == 200 and seen["contents"] == b"%PDF-1.4 fake"

    async def test_invalid_value_400(self, db_override):
        resp = await _post(transcript_format="v3")
        assert resp.status_code == 400
        assert resp.json()["error_code"] == "INVALID_TRANSCRIPT_FORMAT"

    async def test_ignored_for_non_transcript(self, db_override):
        resp = await _post(doc_type="contract", transcript_format="v2")
        assert resp.status_code == 200
        assert resp.json()["document_fields"]["building_number"] == "100"


class TestReviewQueueUntransformed:  # C15:複核佇列存的是未轉換的 pages
    async def test_queue_keeps_old_structured_data(self, feedback_session):
        from app.services.review_queue_service import ReviewQueueService
        app.dependency_overrides[get_db] = lambda: feedback_session
        try:
            with patch("app.api.v1.analyze.AnalyzeService") as M:
                res = _result()
                res["pages"][0]["ocr_raw"] = {"text": "t", "confidence": 0.5}
                M.return_value.analyze = AsyncMock(return_value=res)
                async with _client() as c:
                    resp = await c.post("/api/v1/analyze",
                                        files={"file": ("t.pdf", b"%PDF-1.4 fake", "application/pdf")},
                                        data={"document_type": "transcript", "enable_llm": "false",
                                              "transcript_format": "v2"})
            assert resp.status_code == 200 and resp.json()["needs_review"] is True
            item = ReviewQueueService(feedback_session).get_item(resp.json()["review_item_id"])
            sd = item["original_result"]["pages"][0]["structured_data"]
            assert OLD_KEYS <= set(sd)
        finally:
            app.dependency_overrides.pop(get_db, None)


# ---------------- C8:補值後仍符合 transcript_records.schema.json ----------------
class TestFilledMatchesSchema:
    """補進的 所有權部／他項權利部 筆、新建的 標示部 骨架,陣列鍵要是 []、不是 null(照片實測曾因此不合 schema)"""

    @pytest.mark.parametrize("kind,f", [
        ("建物", {"building_number": "100", "main_usage": "住家用", "other_right_type": "抵押權",
                 "owners": [{"part": "building", "order": "0001", "name": "甲", "rights_scope": "全部"}],
                 "floors": [{"level": "一層", "area": "10.5"}],
                 "shared_parts": [{"build_number": "200", "area": "30", "rights_scope": "10分之1"}]}),
        ("土地", {"land_number": "0001-0000", "area": "50", "other_right_type": "地上權",
                 "owners": [{"part": "land", "order": "0001", "name": "乙", "rights_scope": "2分之1"}]}),
    ])
    def test_filled_record_validates(self, kind, f):
        from tests.unit.test_transcript_records import SCHEMA, _validate
        out = fill_from_rules([_rec()], f)
        assert out[0]["類型"] == kind and out[0]["所有權部"] and out[0]["他項權利部"]
        assert _validate(out, SCHEMA) == []

    def test_unmatched_floor_name_filled_as_null(self):
        """AM-1:配不上層次名稱時面積照補、名稱 null;只合帶參數格式 schema(層次、附屬建物的名稱與面積可為 null)"""
        from tests.unit.test_transcript_records import SCHEMA, _validate
        f = {"building_number": "100", "floors": [{"level": None, "area": "10.5"}, {"level": None, "area": "20"}],
             "sub_buildings": [{"usage": None, "area": "3"}]}
        out = fill_from_rules([_rec()], f)
        assert out[0]["標示部"]["層次"] == [{"層次": None, "面積": 10.5}, {"層次": None, "面積": 20}]
        assert _validate(out, SCHEMA) != []          # 舊 schema 不允許
        assert validate_v2(out) == []


def validate_v2(value):
    """以帶參數格式 schema 驗證(_validate 的 $ref 解析讀模組層 SCHEMA,驗證期間暫換)"""
    import tests.unit.test_transcript_records as TR
    old = TR.SCHEMA
    TR.SCHEMA = v2_schema(old)
    try:
        return TR._validate(value, TR.SCHEMA)
    finally:
        TR.SCHEMA = old


def v2_schema(schema):
    """帶參數格式 schema(AM-1):舊 schema 只放寬 層次[]、附屬建物[] 的名稱與面積可為 null"""
    s = copy.deepcopy(schema)
    props = s["$defs"]["building_mark"]["properties"]
    for lst, keys in (("層次", ("層次", "面積")), ("附屬建物", ("用途", "面積"))):
        for k in keys:
            t = props[lst]["items"]["properties"][k]["type"]
            props[lst]["items"]["properties"][k]["type"] = [t, "null"] if isinstance(t, str) else list(t) + ["null"]
    return s
