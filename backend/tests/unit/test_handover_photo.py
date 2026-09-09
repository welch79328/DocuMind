"""
測試點交照片影像理解與詞彙白名單

- HandoverPhotoProcessor 為影像理解型(非 OCR)
- 輸出必須收斂到 jgb2 的品項/空間 key,詞彙表外的一律丟棄
- 空房回空陣列、模糊回低信心、VLM 失敗降級
- handover_photo 可被路由,且只收影像不收 PDF

對應規格條款: S1, S2, S3, S4, S5
"""

import io

import numpy as np
import pytest
from unittest.mock import AsyncMock, MagicMock
from PIL import Image

from app.lib.multi_type_ocr.handover_photo_processor import HandoverPhotoProcessor
from app.lib.multi_type_ocr.processor import ImageUnderstandingProcessor
from app.lib.multi_type_ocr.processor_factory import ProcessorFactory
from app.lib.document_types import (
    DocumentType,
    is_extension_allowed,
    normalize_document_type,
)
from app.lib.handover_vocabulary import ITEMS, SPACES, normalize_item, normalize_space
from app.schemas.analyze import AnalyzeResponse


def _png():
    img = Image.fromarray(np.zeros((40, 40, 3), dtype=np.uint8))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _provider(json_str):
    p = MagicMock()
    p.call = AsyncMock(return_value=json_str)
    return p


def _boom():
    p = MagicMock()
    p.call = AsyncMock(side_effect=RuntimeError("VLM 掛了"))
    return p


class TestType:
    def test_is_image_understanding_processor(self):
        assert isinstance(HandoverPhotoProcessor(), ImageUnderstandingProcessor)

    def test_registered_in_factory(self):
        assert "handover_photo" in ProcessorFactory.supported_types()
        assert isinstance(
            ProcessorFactory.get_processor("handover_photo"), HandoverPhotoProcessor
        )

    def test_document_type_enum(self):
        assert DocumentType.HANDOVER_PHOTO.value == "handover_photo"
        assert normalize_document_type("handover_photo") is DocumentType.HANDOVER_PHOTO

    def test_images_only_no_pdf(self):
        """S1:點交照片是影像理解型,PDF 沒有意義。"""
        for ext in (".jpg", ".jpeg", ".png"):
            assert is_extension_allowed(DocumentType.HANDOVER_PHOTO, ext)
        assert not is_extension_allowed(DocumentType.HANDOVER_PHOTO, ".pdf")


class TestVocabulary:
    """S2/S3:輸出一定要落在 jgb2 的詞彙表裡。"""

    @pytest.mark.asyncio
    async def test_maps_labels_to_keys(self):
        p = HandoverPhotoProcessor(_provider(
            '{"space":"廚房","furniture":["流理臺"],'
            '"appliance":["冰箱","排油煙機"],"description":"廚房","confidence":0.9}'
        ))
        r = await p.understand("data")
        assert r["space"] == "kitchen"
        assert r["space_label"] == "廚房"
        assert [i["key"] for i in r["furniture"]] == ["kitchen_table"]
        assert sorted(i["key"] for i in r["appliance"]) == ["range_hood", "refrigerator"]
        assert r["dropped"] == []

    @pytest.mark.asyncio
    async def test_drops_words_outside_vocabulary(self):
        """最要命的一條:模型自創的詞不可以流到下游。"""
        p = HandoverPhotoProcessor(_provider(
            '{"space":"廚房","furniture":["單人床架"],'
            '"appliance":["電冰箱","冰箱"],"confidence":0.8}'
        ))
        r = await p.understand("data")
        assert [i["key"] for i in r["appliance"]] == ["refrigerator"]
        assert r["furniture"] == []
        assert sorted(r["dropped"]) == ["單人床架", "電冰箱"]

    @pytest.mark.asyncio
    async def test_accepts_aliases(self):
        """jgb2 的 itemKeyMaps 同義詞:茶几/餐桌/書桌 都是 table。"""
        p = HandoverPhotoProcessor(_provider(
            '{"space":"客廳/餐廳","furniture":["茶几"],"confidence":0.85}'
        ))
        r = await p.understand("data")
        assert [i["key"] for i in r["furniture"]] == ["table"]
        assert r["furniture"][0]["label"] == "桌子"

    @pytest.mark.asyncio
    async def test_recategorises_by_our_taxonomy(self):
        """模型把冰箱放進 furniture 是常見錯誤,以我們的分類為準。"""
        p = HandoverPhotoProcessor(_provider(
            '{"space":"廚房","furniture":["冰箱"],"appliance":["沙發"],"confidence":0.7}'
        ))
        r = await p.understand("data")
        assert [i["key"] for i in r["appliance"]] == ["refrigerator"]
        assert [i["key"] for i in r["furniture"]] == ["sofa"]

    @pytest.mark.asyncio
    async def test_dedupes_across_arrays(self):
        p = HandoverPhotoProcessor(_provider(
            '{"space":"廚房","furniture":["冰箱"],"appliance":["冰箱"],"confidence":0.7}'
        ))
        r = await p.understand("data")
        assert [i["key"] for i in r["appliance"]] == ["refrigerator"]
        assert r["furniture"] == []

    @pytest.mark.asyncio
    async def test_unknown_space_is_dropped_not_guessed(self):
        p = HandoverPhotoProcessor(_provider(
            '{"space":"玄關","appliance":["冰箱"],"confidence":0.6}'
        ))
        r = await p.understand("data")
        assert r["space"] is None
        assert r["space_label"] == ""
        assert "玄關" in r["dropped"]

    @pytest.mark.asyncio
    async def test_item_objects_with_per_item_confidence(self):
        p = HandoverPhotoProcessor(_provider(
            '{"space":"衛浴","furniture":[{"name":"洗手台","confidence":0.42}],'
            '"confidence":0.9}'
        ))
        r = await p.understand("data")
        assert r["furniture"][0]["key"] == "washstand"
        assert r["furniture"][0]["confidence"] == pytest.approx(0.42)
        assert r["field_confidences"]["washstand"] == pytest.approx(0.42)

    @pytest.mark.asyncio
    async def test_item_confidence_falls_back_to_overall(self):
        p = HandoverPhotoProcessor(_provider(
            '{"space":"衛浴","furniture":["洗手台"],"confidence":0.77}'
        ))
        r = await p.understand("data")
        assert r["furniture"][0]["confidence"] == pytest.approx(0.77)

    @pytest.mark.asyncio
    async def test_string_instead_of_array_is_not_lost(self):
        p = HandoverPhotoProcessor(_provider(
            '{"space":"廚房","appliance":"冰箱","confidence":0.8}'
        ))
        r = await p.understand("data")
        assert [i["key"] for i in r["appliance"]] == ["refrigerator"]

    def test_every_vocabulary_key_round_trips(self):
        """詞彙表自身的完整性:每個 key 與其 label 都要正規化回自己。"""
        for key, label in ITEMS.items():
            assert normalize_item(key) == key
            assert normalize_item(label) == key
        for key, label in SPACES.items():
            assert normalize_space(key) == key
            assert normalize_space(label) == key


class TestDegradation:
    """S4/S5:認不出來要說認不出來,不可以硬猜。"""

    @pytest.mark.asyncio
    async def test_empty_room_returns_empty_arrays(self):
        p = HandoverPhotoProcessor(_provider(
            '{"space":"房間","furniture":[],"appliance":[],'
            '"description":"空房,沒有家具","confidence":0.88}'
        ))
        r = await p.understand("data")
        assert r["furniture"] == []
        assert r["appliance"] == []
        assert r["space"] == "room"
        assert r["confidence"] == pytest.approx(0.88)

    @pytest.mark.asyncio
    async def test_blurry_photo_keeps_low_confidence(self):
        p = HandoverPhotoProcessor(_provider(
            '{"space":"衛浴","furniture":[],"appliance":[],"confidence":0.12}'
        ))
        r = await p.understand("data")
        assert r["confidence"] == pytest.approx(0.12)

    @pytest.mark.asyncio
    async def test_vlm_failure_degrades_to_empty(self):
        r = await HandoverPhotoProcessor(_boom()).understand("data")
        assert r["confidence"] == 0.0
        assert r["furniture"] == [] and r["appliance"] == []
        assert r["space"] is None

    @pytest.mark.asyncio
    async def test_unparsable_response_degrades(self):
        r = await HandoverPhotoProcessor(_provider("我不知道")).understand("data")
        assert r["confidence"] == 0.0
        assert r["furniture"] == [] and r["appliance"] == []

    @pytest.mark.asyncio
    async def test_confidence_is_clamped(self):
        p = HandoverPhotoProcessor(_provider(
            '{"space":"房間","confidence":"很高"}'
        ))
        assert (await p.understand("data"))["confidence"] == 0.0
        p2 = HandoverPhotoProcessor(_provider('{"space":"房間","confidence":7}'))
        assert (await p2.understand("data"))["confidence"] == 1.0


class TestAnalyzeIntegration:
    @pytest.mark.asyncio
    async def test_analyze_returns_structured_data_not_ocr(self):
        """走完基底類別的 analyze():影像理解型不產 OCR 欄位。"""
        p = HandoverPhotoProcessor(_provider(
            '{"space":"廚房","appliance":["冰箱"],"confidence":0.9}'
        ))
        page = await p.analyze(Image.open(io.BytesIO(_png())), image_data="data")
        assert page["ocr_raw"] is None
        assert page["overall_confidence"] == pytest.approx(0.9)
        assert page["structured_data"]["space"] == "kitchen"
        assert page["field_confidences"]["refrigerator"] == pytest.approx(0.9)

    @pytest.mark.asyncio
    async def test_prompt_carries_the_vocabulary(self):
        """提示詞必須把清單餵進去,否則模型無從遵守。"""
        prov = _provider('{"space":"房間","confidence":0.5}')
        await HandoverPhotoProcessor(prov).understand("data")
        prompt = prov.call.call_args[0][0]
        assert "沙發" in prompt and "冰箱" in prompt and "客廳/餐廳" in prompt
        assert "只能使用下列詞彙" in prompt


class TestResponseSchemaAcceptsImageUnderstanding:
    """回歸:影像理解型的頁面必須通過 AnalyzeResponse 驗證。

    2026-09-09 實測:`ocr_raw` 與 `rule_postprocessed` 原宣告為必填,
    而 ImageUnderstandingProcessor 兩者都回 None,於是 repair_photo 與
    handover_photo 打 /api/v1/analyze 一律在回應驗證階段炸成 500。
    這兩個案例就是那個 bug 的守門員,不要因為「OCR 一定有值」把欄位改回必填。
    """

    @staticmethod
    def _response(page):
        return AnalyzeResponse(
            file_name="a.jpg",
            document_type="handover_photo",
            total_pages=1,
            pages=[page],
            stats={
                "total_time_ms": 1, "total_pages": 1,
                "llm_pages_used": 0, "estimated_cost": 0.0,
            },
        )

    def test_vlm_page_with_null_ocr_fields_validates(self):
        r = self._response({
            "page_number": 0,
            "ocr_raw": None,
            "rule_postprocessed": None,
            "llm_postprocessed": None,
            "structured_data": {"space": "kitchen"},
            "field_confidences": {"refrigerator": 0.9},
        })
        assert r.pages[0].ocr_raw is None
        assert r.pages[0].structured_data["space"] == "kitchen"

    def test_ocr_page_still_validates(self):
        """正對照組:一般 OCR 頁不能因為放寬而壞掉。"""
        r = self._response({
            "page_number": 1,
            "ocr_raw": {"text": "土地登記第三類謄本", "confidence": 0.85},
            "rule_postprocessed": {"text": "土地登記第三類謄本", "stats": {}},
        })
        assert r.pages[0].ocr_raw.confidence == pytest.approx(0.85)
        assert r.pages[0].rule_postprocessed.text == "土地登記第三類謄本"
