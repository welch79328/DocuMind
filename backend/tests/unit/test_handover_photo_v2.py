"""
點交照片 handover_format=v2(JGB #13541638271;.kiro/specs/handover-photo-v2)

對應凍結驗收清單(acceptance.md):
- A1 不帶參數:同一組假模型回覆的輸出與改前固定檔逐鍵逐值相同(R2)
- A2 帶 v2:欄位齊全、document_fields、field_confidences、needs_confirmation／extraction_confidence、
  錯值 400、非點交類型忽略(R1, R3, R4, R7, R8, R16, R17, R19)
- A3 不合理的 box 回 null(R5)
- A4 condition、text 截到 30 字(R6, R7)
- A5 v2 提示詞不列損傷範例詞、要求繁體中文(R10)
- A7 v2 送模型前依 EXIF 轉正(R9)
- A8 複核判定與佇列內容和不帶參數相同;v2 看得到的 field_confidences 不含沒給自評的品項(R13, R17)
"""

import base64
import importlib.util
import io
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import numpy as np
import pytest
from PIL import Image

from app.database import get_db
from app.lib.multi_type_ocr.handover_photo_processor import (
    HandoverPhotoProcessor,
    apply_handover_format,
    clip_text,
    normalize_box,
)
from app.main import app
from app.models import ReviewQueueItem
from app.services.analyze_service import AnalyzeService

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _load_baseline_module():
    spec = importlib.util.spec_from_file_location(
        "make_handover_v1_baseline", FIXTURES / "make_handover_v1_baseline.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


BASE = _load_baseline_module()
BASELINE = json.loads((FIXTURES / "handover_v1_baseline.json").read_text(encoding="utf-8"))

ITEM_KEYS = {"key", "label", "confidence", "box", "condition"}
SD_KEYS = {"space", "space_label", "furniture", "appliance", "damages",
           "description", "confidence", "dropped", "field_confidences"}

# 自評混合:0.9 與 0.5;部分沒給;全部沒給
MIXED = json.dumps({
    "space": "房間",
    "furniture": [{"name": "雙人床", "confidence": 0.9, "box_2d": [120, 450, 680, 950], "condition": ""},
                  {"name": "衣櫃", "confidence": 0.5, "box_2d": [700, 100, 990, 900], "condition": "左門板下緣剝落"}],
    "appliance": [{"name": "冷氣", "confidence": 0.95, "box_2d": [400, 50, 600, 150]}],
    "damages": [{"text": "窗邊牆面水漬約手掌大", "box_2d": [700, 100, 850, 300]}],
    "description": "臥室", "confidence": 0.9,
}, ensure_ascii=False)
PARTIAL = json.dumps({
    "space": "房間",
    "furniture": [{"name": "雙人床", "confidence": 0.9}, {"name": "衣櫃"}],
    "appliance": ["冷氣"],
    "description": "臥室", "confidence": 0.85,
}, ensure_ascii=False)
NONE_GIVEN = json.dumps({
    "space": "房間", "furniture": ["雙人床", "衣櫃"], "appliance": [],
    "description": "臥室", "confidence": 0.3,
}, ensure_ascii=False)


def _png(w=64, h=48):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (200, 200, 200)).save(buf, format="PNG")
    return buf.getvalue()


def _provider(reply):
    p = MagicMock()
    p.call = AsyncMock(return_value=reply)
    return p


@pytest.fixture
def db(feedback_session):
    app.dependency_overrides[get_db] = lambda: feedback_session
    yield feedback_session
    app.dependency_overrides.pop(get_db, None)


def _client():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def _stubbed(reply):
    """假模型、S3 回固定 URL、用量紀錄不寫;複核佇列寫進測試用 sqlite。"""
    return [
        patch.object(HandoverPhotoProcessor, "_default_provider", staticmethod(lambda: _provider(reply))),
        patch.object(AnalyzeService, "_upload_to_s3", AsyncMock(return_value=BASE.FIXED_URL)),
        patch.object(AnalyzeService, "_record_usage", MagicMock(return_value=None)),
    ]


async def _post_single(reply, **data):
    ps = _stubbed(reply)
    for p in ps:
        p.start()
    try:
        async with _client() as c:
            return await c.post(
                "/api/v1/analyze",
                files={"file": ("room.png", _png(), "image/png")},
                data={"document_type": "handover_photo", **data},
            )
    finally:
        for p in ps:
            p.stop()


async def _post_batch(reply, n=2, **data):
    ps = _stubbed(reply)
    for p in ps:
        p.start()
    try:
        async with _client() as c:
            return await c.post(
                "/api/v1/analyze/batch",
                files=[("files", (f"r{i}.png", _png(), "image/png")) for i in range(n)],
                data={"document_type": "handover_photo", **data},
            )
    finally:
        for p in ps:
            p.stop()


# ---------------------------------------------------------------------- #
# A1:不帶參數,輸出與改前固定檔逐鍵逐值相同

class TestA1NoParamUnchanged:
    def test_baseline_was_made_before_code_change(self):
        meta = BASELINE["_meta"]
        assert meta["sha"].startswith("df41f2d")
        changed = [ln for ln in meta["git_status_backend"].splitlines() if ln.strip()]
        assert changed == ["?? backend/tests/fixtures/make_handover_v1_baseline.py"]

    @pytest.mark.parametrize("name", sorted(BASE.CASES))
    async def test_same_as_baseline(self, name):
        got = await BASE.run_case(BASE.CASES[name])
        assert got == BASELINE["cases"][name]

    async def test_endpoint_without_param_has_old_shape(self, db):
        resp = await _post_single(BASE.CASES["v2_shaped_reply"])
        body = resp.json()
        sd = body["pages"][0]["structured_data"]
        assert set(sd) == set(BASELINE["cases"]["v2_shaped_reply"]["understand"])
        assert "damages" not in sd and "damages" not in body["document_fields"]
        assert set(sd["furniture"][0]) == {"key", "label", "confidence"}


# ---------------------------------------------------------------------- #
# A2:帶 v2

class TestA2V2Fields:
    async def test_single_endpoint_shape(self, db):
        resp = await _post_single(MIXED, handover_format="v2")
        assert resp.status_code == 200
        body = resp.json()
        sd = body["pages"][0]["structured_data"]
        assert set(sd) == SD_KEYS
        for item in sd["furniture"] + sd["appliance"]:
            assert set(item) == ITEM_KEYS
        assert sd["space"] == "room" and sd["description"] == "臥室" and sd["confidence"] == 0.9
        bed = sd["furniture"][0]
        assert bed["confidence"] == 0.9
        assert bed["box"] == {"box": [0.12, 0.45, 0.68, 0.95], "unit": "ratio"}
        assert sd["damages"] == [{"text": "窗邊牆面水漬約手掌大",
                                  "box": {"box": [0.7, 0.1, 0.85, 0.3], "unit": "ratio"}}]
        df = body["document_fields"]
        assert df["furniture"] == sd["furniture"] and df["appliance"] == sd["appliance"]
        assert df["damages"] == sd["damages"]

    async def test_batch_endpoint_shape(self, db):
        resp = await _post_batch(MIXED, handover_format="v2")
        assert resp.status_code == 200
        for item in resp.json()["results"]:
            sd = item["result"]["pages"][0]["structured_data"]
            assert set(sd) == SD_KEYS
            assert all(set(i) == ITEM_KEYS for i in sd["furniture"] + sd["appliance"])
            assert item["result"]["document_fields"]["damages"] == sd["damages"]

    async def test_item_confidence_is_self_assessed_not_filled(self, db):
        body = (await _post_single(PARTIAL, handover_format="v2")).json()
        sd = body["pages"][0]["structured_data"]
        conf = {i["key"]: i["confidence"] for i in sd["furniture"] + sd["appliance"]}
        assert conf == {"double_bed": 0.9, "closet": None, "air_conditioner": None}

    @pytest.mark.parametrize("reply, fc, needs, extraction", [
        (MIXED, {"double_bed": 0.9, "closet": 0.5, "air_conditioner": 0.95},
         ["closet"], round((0.9 + 0.5 + 0.95) / 3, 4)),
        (PARTIAL, {"double_bed": 0.9}, ["air_conditioner", "closet"], 0.9),
        (NONE_GIVEN, {}, ["closet", "double_bed"], None),
    ])
    async def test_field_confidences_and_r19(self, db, reply, fc, needs, extraction):
        for body in [(await _post_single(reply, handover_format="v2")).json(),
                     (await _post_batch(reply, n=1, handover_format="v2")).json()["results"][0]["result"]]:
            assert body["field_confidences"] == fc
            assert body["pages"][0]["field_confidences"] == fc
            assert body["pages"][0]["structured_data"]["field_confidences"] == fc
            df = body["document_fields"]
            assert df["field_confidences"] == fc
            assert df["needs_confirmation"] == needs
            if extraction is None:
                assert "extraction_confidence" not in df
            else:
                assert df["extraction_confidence"] == extraction

    async def test_invalid_value_is_400_on_both_endpoints(self, db):
        r1 = await _post_single(MIXED, handover_format="v3")
        r2 = await _post_batch(MIXED, handover_format="v3")
        for r in (r1, r2):
            assert r.status_code == 400
            assert r.json()["error_code"] == "INVALID_HANDOVER_FORMAT"

    async def test_other_document_type_ignores_v2(self, db):
        result = {"file_name": "b.png", "file_url": None, "document_type": "bill", "total_pages": 1,
                  "pages": [], "document_fields": {"x": 1}, "answer": None,
                  "stats": {"total_time_ms": 1, "total_pages": 1, "llm_pages_used": 0, "estimated_cost": 0.0}}
        with patch("app.api.v1.analyze.AnalyzeService") as M:
            M.return_value.analyze = AsyncMock(return_value=dict(result))
            async with _client() as c:
                with_v2 = await c.post("/api/v1/analyze", files={"file": ("b.png", _png(), "image/png")},
                                       data={"document_type": "bill", "handover_format": "v2"})
            kwargs = M.return_value.analyze.call_args.kwargs
        assert with_v2.status_code == 200
        assert "handover_format" not in kwargs and "handover_v2_out" not in kwargs
        assert with_v2.json()["document_fields"] == {"x": 1}

    async def test_v2_private_key_never_leaks(self, db):
        body = (await _post_single(MIXED, handover_format="v2")).json()
        assert "_handover_v2" not in json.dumps(body, ensure_ascii=False)
        stored = db.query(ReviewQueueItem).all()
        assert all("_handover_v2" not in json.dumps(s.original_result, ensure_ascii=False) for s in stored)


# ---------------------------------------------------------------------- #
# A3:不合理的 box 回 null

class TestA3Box:
    @pytest.mark.parametrize("raw", [
        None, [], [1, 2, 3], [1, 2, 3, 4, 5], "0,0,500,500", {"x": 1},
        [-1, 0, 500, 500], [0, 0, 1001, 500],           # 越界
        [500, 0, 500, 500], [600, 0, 500, 500],          # x0 >= x1
        [0, 500, 500, 500], [0, 600, 500, 500],          # y0 >= y1
        [0, 0, 70, 70],                                  # 面積 0.0049 < 0.5%
        ["a", 0, 500, 500], [True, 0, 500, 500], [float("nan"), 0, 500, 500],
    ])
    def test_unreasonable_is_none(self, raw):
        assert normalize_box(raw) is None

    def test_area_exactly_half_percent_is_kept(self):
        assert normalize_box([0, 0, 100, 50]) == {"box": [0.0, 0.0, 0.1, 0.05], "unit": "ratio"}

    def test_ratio_and_four_decimals(self):
        assert normalize_box([123.456, 0, 1000, 1000]) == {"box": [0.1235, 0.0, 1.0, 1.0], "unit": "ratio"}

    def test_bad_box_in_reply_becomes_null(self):
        reply = {"furniture": [{"name": "雙人床", "confidence": 0.9, "box_2d": [600, 0, 500, 500]}],
                 "damages": [{"text": "牆面髒污", "box_2d": [0, 0, 10, 10]}], "confidence": 0.9}
        v2 = HandoverPhotoProcessor()._to_vocabulary_v2(reply)
        assert v2["furniture"][0]["box"] is None
        assert v2["damages"] == [{"text": "牆面髒污", "box": None}]


# ---------------------------------------------------------------------- #
# A4:condition、text 截到 30 字

class TestA4Text:
    def test_31_chars_clipped_to_30(self):
        assert clip_text("字" * 31) == "字" * 30

    def test_non_string_is_empty(self):
        for v in (None, 3, ["x"], {"a": 1}):
            assert clip_text(v) == ""

    def test_reply_condition_and_damage_text_clipped_and_empty_dropped(self):
        reply = {"furniture": [{"name": "衣櫃", "confidence": 0.7, "condition": "損" * 40}],
                 "damages": [{"text": "牆" * 31, "box_2d": [0, 0, 500, 500]}, {"text": "   "}, {"box_2d": [0, 0, 500, 500]}],
                 "confidence": 0.8}
        v2 = HandoverPhotoProcessor()._to_vocabulary_v2(reply)
        assert v2["furniture"][0]["condition"] == "損" * 30
        assert [d["text"] for d in v2["damages"]] == ["牆" * 30]


# ---------------------------------------------------------------------- #
# A5:v2 提示詞

class TestA5Prompt:
    DAMAGE_WORDS = ("漏水", "壁癌", "龜裂", "設備損壞", "剝落", "水漬")

    def test_no_damage_examples(self):
        prompt = HandoverPhotoProcessor._build_prompt_v2()
        for word in self.DAMAGE_WORDS:
            assert word not in prompt, word

    def test_asks_for_traditional_chinese(self):
        assert "繁體中文" in HandoverPhotoProcessor._build_prompt_v2()

    def test_old_prompt_unchanged(self):
        prompt = HandoverPhotoProcessor._build_prompt()
        assert "box_2d" not in prompt and "damages" not in prompt

    async def test_v2_processor_sends_v2_prompt(self):
        provider = _provider(MIXED)
        await HandoverPhotoProcessor(provider=provider, fmt="v2").understand("AAAA")
        assert provider.call.call_args.args[0] == HandoverPhotoProcessor._build_prompt_v2()


# ---------------------------------------------------------------------- #
# A7:v2 送模型前依 EXIF 轉正

def _oriented_jpeg():
    """像素 60x40(寬>高),EXIF Orientation=6(順時針轉 90 度顯示)→ 轉正後 40x60。"""
    arr = np.zeros((40, 60, 3), dtype=np.uint8)
    arr[:, :30] = (255, 0, 0)
    img = Image.fromarray(arr)
    exif = Image.Exif()
    exif[0x0112] = 6
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif.tobytes())
    return buf.getvalue()


def _sent_size(provider):
    b64 = provider.call.call_args.kwargs["image_data"]
    return Image.open(io.BytesIO(base64.b64decode(b64))).size


class TestA7Exif:
    async def test_v2_sends_upright_image(self):
        provider = _provider(MIXED)
        await HandoverPhotoProcessor(provider=provider, fmt="v2").process(
            file_contents=_oriented_jpeg(), filename="p.jpg", page_number=1, total_pages=1, enable_llm=True)
        assert _sent_size(provider) == (40, 60)

    async def test_old_path_untouched(self):
        provider = _provider(MIXED)
        await HandoverPhotoProcessor(provider=provider).process(
            file_contents=_oriented_jpeg(), filename="p.jpg", page_number=1, total_pages=1, enable_llm=True)
        assert _sent_size(provider) == (60, 40)

    async def test_no_orientation_passes_bytes_through(self):
        provider = _provider(MIXED)
        await HandoverPhotoProcessor(provider=provider, fmt="v2").process(
            file_contents=_png(64, 48), filename="p.png", page_number=1, total_pages=1, enable_llm=True)
        assert _sent_size(provider) == (64, 48)


# ---------------------------------------------------------------------- #
# A8:複核判定與佇列內容不受 v2 影響

class TestA8Review:
    @staticmethod
    def _queue(db):
        rows = db.query(ReviewQueueItem).order_by(ReviewQueueItem.created_at).all()
        return [r.original_result for r in rows]

    async def test_single_endpoint_same_gating(self, db):
        old = (await _post_single(NONE_GIVEN)).json()
        new = (await _post_single(NONE_GIVEN, handover_format="v2")).json()
        assert old["needs_review"] is True
        assert new["needs_review"] == old["needs_review"]
        assert (new["review_item_id"] is None) == (old["review_item_id"] is None)
        q_old, q_new = self._queue(db)
        assert q_new["pages"] == q_old["pages"]
        assert q_new["field_confidences"] == q_old["field_confidences"] == {"closet": 0.3, "double_bed": 0.3}
        # (b) v2 看得到的四處不含沒給自評的品項
        assert new["field_confidences"] == {}
        assert new["pages"][0]["field_confidences"] == {}
        assert new["pages"][0]["structured_data"]["field_confidences"] == {}
        assert new["document_fields"]["field_confidences"] == {}

    async def test_batch_endpoint_same_gating(self, db):
        old = (await _post_batch(NONE_GIVEN, n=1)).json()["results"][0]["result"]
        new = (await _post_batch(NONE_GIVEN, n=1, handover_format="v2")).json()["results"][0]["result"]
        assert new["needs_review"] == old["needs_review"] is True
        assert (new["review_item_id"] is None) == (old["review_item_id"] is None)
        q_old, q_new = self._queue(db)
        assert q_new == q_old
        assert new["field_confidences"] == {}
        assert new["document_fields"]["field_confidences"] == {}

    async def test_high_confidence_not_queued_either_way(self, db):
        reply = BASE.CASES["non_numeric_confidence"]
        old = (await _post_single(reply)).json()
        new = (await _post_single(reply, handover_format="v2")).json()
        assert old["needs_review"] is new["needs_review"] is False
        assert old["review_item_id"] is new["review_item_id"] is None
        assert self._queue(db) == []


# ---------------------------------------------------------------------- #
# 轉換函式本身

class TestApplyHandoverFormat:
    def test_does_not_mutate_input(self):
        result = {"pages": [{"page_number": 1, "structured_data": {"a": 1}, "field_confidences": {"a": 1.0}}],
                  "document_fields": {"a": 1, "field_confidences": {"a": 1.0}}, "field_confidences": {"a": 1.0},
                  "needs_review": True, "review_item_id": "x"}
        snapshot = json.loads(json.dumps(result))
        v2 = HandoverPhotoProcessor()._to_vocabulary_v2(json.loads(MIXED))
        new = apply_handover_format(result, {1: v2})
        assert result == snapshot
        assert new["needs_review"] is True and new["review_item_id"] == "x"
        assert new["document_fields"]["a"] == 1
