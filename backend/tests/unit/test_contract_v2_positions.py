"""合約 v2 值位置(contract_format=v2)——計畫 .kiro/specs/contract-v2-positions/plan.md,驗收 acceptance.md C3、C7。

測試 PDF 用 PyMuPDF 內建 china-t 字型產生;內建 CJK 字型的半形數字抽回來會夾空白,所以數字一律寫全形
(比對前 normalize_for_matching 會轉成半形,值與真實全形合約相同)。
"""

import copy
from unittest.mock import AsyncMock, patch

import fitz
import pytest

from app.api.v1 import analyze as analyze_api
from app.lib.multi_type_ocr.contract_field_extractor import ContractFieldExtractor
from app.lib.multi_type_ocr.contract_positions import POSITION_FIELDS, apply_contract_format
from app.lib.multi_type_ocr.text_normalize import normalize_for_matching
from app.lib.pdf_text_layer import extract_text_layer_pages
from app.services.analyze_service import AnalyzeService, _merge_page_structured_data
from tests.unit.test_transcript_format_v2 import _client, db_override  # noqa: F401

LEASE = [
    "租賃標的：臺北市中正區範例路１號３樓",
    "租期：中華民國１１３年１月１日起",
    "至中華民國１１４年１２月３１日止",
    "每月租金：新臺幣５０，０００元",
    "押金：新臺幣５０，０００元",
    "承租人：王小明",
]


def _pdf(pages, rotate=0):
    doc = fitz.open()
    for lines in pages:
        page = doc.new_page()
        page.insert_text((50, 80), "\n".join(lines), fontname="china-t", fontsize=12)
        if rotate:
            page.set_rotation(rotate)
    return doc.tobytes()


async def _result(pdf: bytes) -> dict:
    """走與線上相同的文字層路徑(抽文字 → 逐頁抽欄位 → 跨頁合併),不經 S3 與資料庫。"""
    pages = extract_text_layer_pages(pdf)
    pages = await AnalyzeService()._extract_fields_for_text_layer(pages, "contract", False)
    return {"document_type": "contract", "pages": pages,
            "document_fields": _merge_page_structured_data(pages)}


def _box_text(pdf: bytes, pos: dict) -> str:
    """C2 判法:字元框中心落在 box 內、非空白的字,依 rawdict 順序串接後正規化。"""
    page = fitz.open(stream=pdf, filetype="pdf")[pos["page"] - 1]
    w, h = page.rect.width, page.rect.height
    x0, y0, x1, y1 = pos["box"]
    out = []
    for b in page.get_text("rawdict")["blocks"]:
        for ln in b.get("lines", []):
            for s in ln["spans"]:
                for c in s["chars"]:
                    cx = (c["bbox"][0] + c["bbox"][2]) / 2 / w
                    cy = (c["bbox"][1] + c["bbox"][3]) / 2 / h
                    if c["c"].strip() and x0 <= cx <= x1 and y0 <= cy <= y1:
                        out.append(c["c"])
    return normalize_for_matching("".join(out))


def _digits(s):
    return "".join(ch for ch in s if ch.isdigit())


# ---------------- 抽取器:位置來自同一次比對 ----------------
class TestMatchFields:
    def test_values_identical_to_extract_with_regex(self):
        text = "\n".join(LEASE)
        ex = ContractFieldExtractor()
        hits = ex._match_fields(text)
        assert {k: (v[0] if v else None) for k, v in hits.items()} == ex._extract_with_regex(text)

    def test_single_group_span_is_the_stripped_value(self):
        text = "\n".join(LEASE)
        norm = normalize_for_matching(text)
        hits = ContractFieldExtractor()._match_fields(text)
        for name in ("monthly_rent", "deposit", "rental_address", "tenant_name"):
            value, (s, e) = hits[name]
            assert norm[s:e] == value

    def test_same_amount_rent_and_deposit_point_to_their_own_lines(self):
        text = "\n".join(LEASE)
        norm = normalize_for_matching(text)
        hits = ContractFieldExtractor()._match_fields(text)
        assert hits["monthly_rent"][0] == hits["deposit"][0] == "50,000"
        assert hits["monthly_rent"][1] != hits["deposit"][1]
        assert "押金" in norm[norm.rfind("\n", 0, hits["deposit"][1][0]) + 1:hits["deposit"][1][0]]

    def test_multi_group_roc_date_span_first_to_last_group(self):
        text = "\n".join(LEASE)
        norm = normalize_for_matching(text)
        value, (s, e) = ContractFieldExtractor()._match_fields(text)["date_start"]
        assert value == "113 1 1"
        assert norm[s:e] == "113年1月1"


# ---------------- 包裝與位置 ----------------
class TestApply:
    async def test_shape_values_and_c2_judge(self):
        pdf = _pdf([LEASE])
        r = await _result(pdf)
        before = copy.deepcopy(r)
        out = apply_contract_format(r, pdf)
        assert r == before                                   # 不改原物件
        rt = out["document_fields"]["rental_terms"]
        for name in POSITION_FIELDS:
            assert set(rt[name]) == {"value", "position"}
            assert rt[name]["value"] == before["document_fields"]["rental_terms"][name]
            pos = rt[name]["position"]
            assert pos is not None and pos["page"] == 1 and pos["unit"] == "ratio"
            assert all(0 <= x <= 1 for x in pos["box"])
            got = _box_text(pdf, pos)
            if name.startswith("date_"):
                assert _digits(got) == _digits(rt[name]["value"])
                assert set(got) <= set("0123456789年月日民國西元中華./-")
            else:
                assert got == normalize_for_matching(rt[name]["value"]).replace(" ", "")
        assert rt["monthly_rent"]["position"]["box"] != rt["deposit"]["position"]["box"]
        # 其他欄位不包
        assert out["document_fields"]["rental_terms"]["management_fee"] is None
        assert out["pages"] == before["pages"]

    async def test_first_non_empty_page_rule(self):
        pdf = _pdf([LEASE[:5], ["第二頁", "承租人：李大華"]])
        out = apply_contract_format(await _result(pdf), pdf)
        tn = out["document_fields"]["rental_terms"]["tenant_name"]
        assert tn["value"] == "李大華" and tn["position"]["page"] == 2
        assert _box_text(pdf, tn["position"]) == "李大華"

    async def test_null_value_null_position(self):
        pdf = _pdf([LEASE[:5]])
        out = apply_contract_format(await _result(pdf), pdf)
        assert out["document_fields"]["rental_terms"]["tenant_name"] == {"value": None, "position": None}

    async def test_cross_line_roc_date_gets_null(self):
        lines = ["租期：中華民國１１３年", "１月１日起"] + LEASE[2:]
        pdf = _pdf([lines])
        out = apply_contract_format(await _result(pdf), pdf)
        ds = out["document_fields"]["rental_terms"]["date_start"]
        assert ds["value"] == "113 1 1" and ds["position"] is None
        assert out["document_fields"]["rental_terms"]["deposit"]["position"] is not None

    async def test_value_mismatch_gets_null(self):
        pdf = _pdf([LEASE])
        r = await _result(pdf)
        r["document_fields"]["rental_terms"]["deposit"] = "99,999"
        out = apply_contract_format(r, pdf)
        assert out["document_fields"]["rental_terms"]["deposit"] == {"value": "99,999", "position": None}
        assert out["document_fields"]["rental_terms"]["monthly_rent"]["position"] is not None

    async def test_text_layer_mismatch_all_null(self):
        pdf = _pdf([LEASE])
        r = await _result(pdf)
        r["pages"][0]["ocr_raw"]["text"] += "多一行\n"
        out = apply_contract_format(r, pdf)
        assert all(out["document_fields"]["rental_terms"][n]["position"] is None for n in POSITION_FIELDS)

    async def test_not_text_layer_all_null(self):
        pdf = _pdf([LEASE])
        r = await _result(pdf)
        r["pages"][0]["text_layer"] = False
        out = apply_contract_format(r, pdf)
        rt = out["document_fields"]["rental_terms"]
        assert all(rt[n]["position"] is None for n in POSITION_FIELDS)
        assert rt["deposit"]["value"] == "50,000"

    async def test_rotated_page_null(self):
        pdf = _pdf([LEASE], rotate=90)
        out = apply_contract_format(await _result(pdf), pdf)
        assert all(out["document_fields"]["rental_terms"][n]["position"] is None for n in POSITION_FIELDS)

    def test_no_rental_terms_unchanged(self):
        r = {"document_type": "contract", "pages": [], "document_fields": {"parties": {"party_a": "甲"}}}
        assert apply_contract_format(r, b"") == r

    def test_garbage_file_values_kept_positions_null(self):
        r = {"pages": [{"page_number": 1, "text_layer": True, "ocr_raw": {"text": "押金：新臺幣１元"},
                        "structured_data": {"rental_terms": {"deposit": "1"}}}],
             "document_fields": {"rental_terms": {"deposit": "1"}}}
        out = apply_contract_format(r, b"not a pdf")
        assert out["document_fields"]["rental_terms"]["deposit"] == {"value": "1", "position": None}


# ---------------- 參數與端點 ----------------
def _api_result():
    rt = {k: None for k in ("date_start", "date_end", "monthly_rent", "deposit", "rental_address",
                            "management_fee", "parking_fee", "payment_day", "tenant_name", "tenant_id_number",
                            "tenant_phone", "landlord_name", "landlord_id_number", "landlord_phone")}
    rt["deposit"] = "50,000"
    return {"file_name": "c.pdf", "file_url": None, "document_type": "contract", "total_pages": 1,
            "pages": [{"page_number": 1, "text_layer": False, "ocr_raw": {"text": "x", "confidence": 0.9},
                       "structured_data": {"rental_terms": dict(rt)}, "overall_confidence": 0.99}],
            "document_fields": {"rental_terms": rt, "extraction_confidence": 0.99},
            "answer": None, "stats": {"total_time_ms": 1, "total_pages": 1, "llm_pages_used": 0, "estimated_cost": 0.0}}


async def _post(doc_type="contract", gating=None, **extra):
    with patch.object(analyze_api, "AnalyzeService") as M:
        res = _api_result()
        res["document_type"] = doc_type
        M.return_value.analyze = AsyncMock(return_value=res)
        ctx = patch.object(analyze_api, "_apply_confidence_gating", gating) if gating else None
        if ctx:
            ctx.start()
        try:
            async with _client() as c:
                data = {"document_type": doc_type, "enable_llm": "false", **extra}
                return await c.post("/api/v1/analyze",
                                    files={"file": ("c.pdf", b"%PDF-1.4 fake", "application/pdf")}, data=data)
        finally:
            if ctx:
                ctx.stop()


class TestApi:
    @pytest.mark.parametrize("bad", ["v3", "", "V2"])
    async def test_invalid_value_400(self, db_override, bad):
        resp = await _post(contract_format=bad)
        assert resp.status_code == 400 and resp.json()["error_code"] == "INVALID_CONTRACT_FORMAT"

    async def test_param_absent_unchanged(self, db_override):
        resp = await _post()
        assert resp.status_code == 200
        assert resp.json()["document_fields"]["rental_terms"]["deposit"] == "50,000"

    async def test_v2_wraps_six_fields_for_contract(self, db_override):
        resp = await _post(contract_format="v2")
        rt = resp.json()["document_fields"]["rental_terms"]
        assert rt["deposit"] == {"value": "50,000", "position": None}      # 非文字層 ⇒ null
        assert all(set(rt[n]) == {"value", "position"} for n in POSITION_FIELDS)
        assert rt["management_fee"] is None
        assert resp.json()["pages"][0]["structured_data"]["rental_terms"]["deposit"] == "50,000"

    async def test_non_contract_ignores_param(self, db_override):
        a = await _post(doc_type="bill")
        b = await _post(doc_type="bill", contract_format="v2")
        assert a.status_code == b.status_code == 200
        assert a.json() == b.json()

    async def test_gating_sees_unconverted_result(self, db_override):
        seen = []
        resp = await _post(contract_format="v2", gating=lambda result, db: seen.append(copy.deepcopy(result)))
        assert resp.status_code == 200
        assert seen and seen[0]["document_fields"]["rental_terms"]["deposit"] == "50,000"
