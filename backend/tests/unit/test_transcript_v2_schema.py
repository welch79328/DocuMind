"""S4: 帶參數格式 schema(docs/api/transcript_records_v2.schema.json)——由舊 schema 以固定規則衍生,不手寫。

衍生規則(plan-s4.md §2 路徑 1):
(a) 先套 AM-1(test_transcript_format_v2.v2_schema 同一放寬);
(b) 每個葉子型別 T 換成「null,或 {value: T 去掉 null, position: Position 或 null}」
    (additionalProperties false、兩鍵 required);判定、部是否印出 不換(transcript_records._UNWRAPPED_KEYS);
    類型 例外:土地、建物兩支的 類型 必須是包裝後物件、value 為該 const、不可為 null;null 支維持只能是 null;
    標示部 的 description 改寫(類型 已知時一律是物件,沒印時是全空骨架);
(c) Position = {page: 整數 ≥1, box: 4 個 0～1 數字, unit: const "ratio"}。
"""

import copy
import json
import os

import pytest

from app.lib.multi_type_ocr.transcript_records import _UNWRAPPED_KEYS, _wrap_record, build_transcript_records, \
    fill_from_rules
from tests.unit.test_transcript_format_v2 import v2_schema

DOCS = os.path.join(os.path.dirname(__file__), "..", "..", "..", "docs", "api")
OLD_PATH = os.path.join(DOCS, "transcript_records.schema.json")
V2_PATH = os.path.join(DOCS, "transcript_records_v2.schema.json")

_SCALARS = {"string", "number", "integer", "boolean", "null"}
POSITION = {
    "type": "object", "additionalProperties": False, "required": ["page", "box", "unit"],
    "properties": {
        "page": {"type": "integer", "description": "第幾頁,從 1 起算"},
        "box": {"type": "array", "minItems": 4, "maxItems": 4,
                "items": {"type": "number", "minimum": 0, "maximum": 1},
                "description": "[x0, y0, x1, y1],0～1 比例,原點在頁面左上"},
        "unit": {"const": "ratio"},
    },
    "description": "值在原檔的位置(INTEGRATION.md §3.1.4)",
}
_POS_REF = {"anyOf": [{"type": "null"}, {"$ref": "#/$defs/position"}]}
_MARK_DESC = "類型 已知時一律是物件(謄本沒印標示部時是全空骨架),類型 為 null 時為 null;有沒有印看 部是否印出.標示部"


def _is_leaf(s):
    if "$ref" in s or "anyOf" in s or "oneOf" in s:
        return False
    t = s.get("type")
    ts = set(t if isinstance(t, list) else [t]) if t is not None else set()
    if ts and ts <= _SCALARS:
        return ts != {"null"}
    return not ts and ("const" in s or "enum" in s)


def _wrapped_obj(value_schema):
    return {"type": "object", "additionalProperties": False, "required": ["value", "position"],
            "properties": {"value": value_schema, "position": copy.deepcopy(_POS_REF)}}


def _strip_null(s):
    s = copy.deepcopy(s)
    t = s.get("type")
    if isinstance(t, list):
        rest = [x for x in t if x != "null"]
        s["type"] = rest[0] if len(rest) == 1 else rest
    return s


def _wrap_schema(s):
    if _is_leaf(s):
        return {"anyOf": [{"type": "null"}, _wrapped_obj(_strip_null(s))]}
    s = copy.deepcopy(s)
    for k in ("anyOf", "oneOf"):
        if k in s:
            s[k] = [_wrap_schema(o) for o in s[k]]
    if "properties" in s:
        s["properties"] = {k: _wrap_schema(v) for k, v in s["properties"].items()}
    if "items" in s:
        s["items"] = _wrap_schema(s["items"])
    return s


def derive_v2(old):
    s = v2_schema(old)                                   # (a) AM-1
    out = copy.deepcopy(s)
    out["$id"] = "https://documind/transcript_records_v2.schema.json"
    out["title"] = "document_fields.transcript_records(transcript_format=v2)"
    out["description"] = ("帶 transcript_format=v2 時的謄本固定輸出格式:每張謄本一筆,鍵一律存在;每個非 null 葉子包成 "
                          "{value, position},null 葉子照舊;判定、部是否印出 不包。由 transcript_records.schema.json "
                          "以固定規則衍生(backend/tests/unit/test_transcript_v2_schema.py)。見 docs/api/INTEGRATION.md §3.1.4。")
    unwrapped_refs = {s["items"]["oneOf"][0]["properties"][k]["$ref"].split("/")[-1] for k in _UNWRAPPED_KEYS}
    out["$defs"] = {k: (copy.deepcopy(v) if k in unwrapped_refs else _wrap_schema(v)) for k, v in s["$defs"].items()}
    out["$defs"]["position"] = copy.deepcopy(POSITION)
    branches = []
    for b in s["items"]["oneOf"]:
        nb = copy.deepcopy(b)
        nb["properties"] = {k: (copy.deepcopy(v) if k in _UNWRAPPED_KEYS else _wrap_schema(v))
                            for k, v in b["properties"].items()}
        kind = b["properties"]["類型"]
        if "const" in kind:                              # 類型 例外:土地/建物支不可為 null
            nb["properties"]["類型"] = _wrapped_obj({"const": kind["const"]})
            nb["properties"]["標示部"]["description"] = _MARK_DESC
        else:
            assert kind == {"type": "null"}, kind
        branches.append(nb)
    out["items"]["oneOf"] = branches
    return out


def _load(p):
    return json.load(open(p, encoding="utf-8"))


def validate(value, schema, root=None):
    """用 test_transcript_records._validate(解析 $ref 讀模組層 SCHEMA,驗證期間暫換成 root)"""
    import tests.unit.test_transcript_records as TR
    old = TR.SCHEMA
    TR.SCHEMA = root or schema
    try:
        return TR._validate(value, schema)
    finally:
        TR.SCHEMA = old


def _wrapped_records(pos=None):
    from tests.unit.test_transcript_records import _records
    return [_wrap_record(r, pos) for r in fill_from_rules(_records(), {})]


class TestV2Schema:
    def test_schema_file_equals_derived(self):
        """repo 內 v2 schema 檔＝由舊 schema 衍生的結果(舊 schema 改了沒同步就紅)"""
        assert _load(V2_PATH) == derive_v2(_load(OLD_PATH))

    def test_wrapped_records_validate(self):
        recs = _wrapped_records()
        assert len(recs) == 2 and {r["類型"]["value"] for r in recs} == {"建物", "土地"}
        assert validate(recs, _load(V2_PATH)) == []

    def test_non_null_position_validates(self):
        recs = _wrapped_records()
        recs[0]["謄本"]["編號"]["position"] = {"page": 1, "box": [0.1, 0.2, 0.3, 0.25], "unit": "ratio"}
        assert validate(recs, _load(V2_PATH)) == []

    def test_null_type_sheet_validates_once(self):
        """類型 為 null 的張只符合 null 支(oneOf 恰好 1 支;_validate 的 oneOf 不是恰好 1 支就報錯)"""
        rec = _wrap_record(fill_from_rules(build_transcript_records([{}]) * 2, {})[0])
        assert rec["類型"] is None and rec["標示部"] is None
        sch = _load(V2_PATH)
        hits = [b for b in sch["items"]["oneOf"] if validate(rec, b, sch) == []]
        assert len(hits) == 1 and hits[0]["properties"]["類型"] == {"type": "null"}
        assert validate([rec], sch) == []

    @pytest.mark.parametrize("breaker", ["unit_px", "missing_position", "unwrapped_old_shape"])
    def test_negatives_rejected(self, breaker):
        sch = _load(V2_PATH)
        if breaker == "unwrapped_old_shape":
            from tests.unit.test_transcript_records import _records
            recs = fill_from_rules(_records(), {})
        else:
            recs = _wrapped_records()
            leaf = recs[0]["謄本"]["編號"]
            if breaker == "unit_px":
                leaf["position"] = {"page": 1, "box": [0.1, 0.2, 0.3, 0.25], "unit": "px"}
            else:
                del leaf["position"]
        assert validate(recs, sch) != []
