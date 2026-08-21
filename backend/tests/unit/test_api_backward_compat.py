"""
API 向後相容與影像理解路徑驗證(ocr-vlm-consensus 任務 10.2)

驗收標準:
- 端點請求參數不變
- 回應結構向後相容,新增欄位為選填
- 影像理解路徑行為不變
- 類型路由支援的文件類型與行為不變

這組測試刻意用**寫死的期望清單**而非從程式推導。從程式推導等於拿被測物
當標準答案,參數被改名時兩邊會一起變、測試照樣通過,守不住相容性。

對應需求: 6.1, 6.5
"""

import inspect

import pytest
from PIL import Image

from app.api.v1.analyze import analyze_document
from app.config import settings
from app.lib.document_types import DocumentType, normalize_document_type
from app.lib.multi_type_ocr.processor import ImageUnderstandingProcessor
from app.lib.multi_type_ocr.processor_factory import ProcessorFactory
from app.schemas.analyze import (
    AnalyzeResponse,
    OcrPageResult,
    OcrRawOutput,
    ProcessingStats,
    RulePostprocessedOutput,
)

# 本規格開工前就存在的端點參數(凍結清單)
FROZEN_REQUEST_PARAMS = {"file", "document_type", "enable_llm", "question"}

# 本規格開工前就存在的回應欄位(凍結清單)
FROZEN_RESPONSE_FIELDS = {
    "file_name", "file_url", "document_type", "total_pages",
    "pages", "answer", "stats",
}
FROZEN_PAGE_FIELDS = {
    "page_number", "ocr_raw", "rule_postprocessed",
    "llm_postprocessed", "structured_data",
}

# 本規格新增的欄位——全部必須為選填
ADDED_RESPONSE_FIELDS = {"needs_review", "review_item_id", "field_confidences"}
ADDED_PAGE_FIELDS = {"field_confidences", "consensus"}

# 本規格開工前就支援的文件類型(凍結清單)
FROZEN_DOCUMENT_TYPES = {"transcript", "bill", "contract", "repair_photo"}


def _client_visible_params() -> set:
    """端點中呼叫端真的要送的參數;Depends 注入(如 db session)不算"""
    from fastapi import params as fastapi_params

    visible = set()
    for name, param in inspect.signature(analyze_document).parameters.items():
        if isinstance(param.default, fastapi_params.Depends):
            continue
        visible.add(name)
    return visible


class TestRequestParamsUnchanged:
    def test_client_visible_params_exactly_match_frozen_list(self):
        """端點請求參數不變:既不得少,也不得偷加必填參數"""
        assert _client_visible_params() == FROZEN_REQUEST_PARAMS

    def test_db_stays_a_dependency_not_a_request_field(self):
        """db 是 Depends 注入(本規格開工前就有),不得變成呼叫端要送的欄位"""
        param = inspect.signature(analyze_document).parameters["db"]
        from fastapi import params as fastapi_params

        assert isinstance(param.default, fastapi_params.Depends)

    def test_no_new_config_leaks_into_request(self):
        """新設定必須走環境變數,不得變成請求參數影響既有呼叫端"""
        params = _client_visible_params()
        for leaked in ("consensus", "dual_modal", "cascade", "field_confidence"):
            assert not any(leaked in p for p in params)


class TestResponseBackwardCompatible:
    def test_frozen_response_fields_all_present(self):
        assert FROZEN_RESPONSE_FIELDS <= set(AnalyzeResponse.model_fields)

    def test_frozen_page_fields_all_present(self):
        assert FROZEN_PAGE_FIELDS <= set(OcrPageResult.model_fields)

    def test_every_added_response_field_is_optional(self):
        """新增欄位為選填:舊版呼叫端不帶這些欄位仍可建構回應"""
        for name in ADDED_RESPONSE_FIELDS:
            field = AnalyzeResponse.model_fields[name]
            assert not field.is_required(), f"{name} 不得為必填"

    def test_every_added_page_field_is_optional(self):
        for name in ADDED_PAGE_FIELDS:
            field = OcrPageResult.model_fields[name]
            assert not field.is_required(), f"{name} 不得為必填"

    def test_response_constructible_without_any_new_field(self):
        """以本規格開工前的欄位集合建構,必須成功"""
        response = AnalyzeResponse(
            file_name="a.pdf",
            document_type="transcript",
            total_pages=1,
            pages=[
                OcrPageResult(
                    page_number=1,
                    ocr_raw=OcrRawOutput(text="x", confidence=0.9),
                    rule_postprocessed=RulePostprocessedOutput(text="x", stats={}),
                )
            ],
            stats=ProcessingStats(
                total_time_ms=1, total_pages=1, llm_pages_used=0, estimated_cost=0.0
            ),
        )
        assert response.needs_review is False
        assert response.review_item_id is None
        assert response.field_confidences == {}
        assert response.pages[0].consensus is None
        assert response.pages[0].field_confidences == {}

    def test_unknown_extra_keys_are_ignored_not_rejected(self):
        """OcrPageResult 設 extra=ignore,新增鍵不得讓舊版回應解析失敗"""
        page = OcrPageResult(
            page_number=1,
            ocr_raw=OcrRawOutput(text="x", confidence=0.9),
            rule_postprocessed=RulePostprocessedOutput(text="x", stats={}),
            some_future_key="whatever",
        )
        assert page.page_number == 1


class TestDocumentTypeRoutingUnchanged:
    def test_supported_types_exactly_match_frozen_list(self):
        assert set(ProcessorFactory.supported_types()) == FROZEN_DOCUMENT_TYPES

    def test_authoritative_enum_unchanged(self):
        assert {t.value for t in DocumentType} == FROZEN_DOCUMENT_TYPES

    @pytest.mark.parametrize(
        "legacy,expected",
        [
            ("lease", DocumentType.CONTRACT),
            ("lease_contract", DocumentType.CONTRACT),
            ("repair_quote", DocumentType.BILL),
            ("transcript", DocumentType.TRANSCRIPT),
            ("invoice", None),
            ("", None),
            (None, None),
        ],
    )
    def test_legacy_alias_normalization_unchanged(self, legacy, expected):
        assert normalize_document_type(legacy) is expected

    @pytest.mark.parametrize("doc_type", sorted(FROZEN_DOCUMENT_TYPES))
    def test_every_type_still_resolves_to_a_processor(self, doc_type):
        assert ProcessorFactory.get_processor(doc_type) is not None


class TestImageUnderstandingPathUnaffected:
    """影像理解路徑(修繕照片)不走 OCR,不得被共識機制沾到"""

    class _Probe(ImageUnderstandingProcessor):
        def __init__(self):
            self.calls = 0

        async def understand(self, image_data, few_shot=None):
            self.calls += 1
            return {
                "defect_labels": ["漏水"],
                "description": "牆面滲水",
                "confidence": 0.88,
                "field_confidences": {"defect_labels": 0.88},
            }

        async def preprocess(self, image):  # pragma: no cover - 介面填充
            return image

    @pytest.fixture
    def probe(self):
        return self._Probe()

    @pytest.fixture
    def image(self):
        return Image.new("RGB", (8, 8), "white")

    @pytest.mark.asyncio
    async def test_result_has_no_ocr_sections(self, probe, image):
        page = await probe.analyze(image, image_data="b64")
        assert page["ocr_raw"] is None
        assert page["rule_postprocessed"] is None
        assert page["llm_postprocessed"] is None

    @pytest.mark.asyncio
    async def test_no_consensus_key_regardless_of_setting(
        self, probe, image, monkeypatch
    ):
        """即使全域啟用共識,影像理解結果也不得出現共識鍵"""
        monkeypatch.setattr(settings, "OCR_CONSENSUS_ENABLED", True)
        page = await probe.analyze(image, image_data="b64")
        assert "consensus" not in page

    @pytest.mark.asyncio
    async def test_confidence_comes_from_understanding_not_ocr(self, probe, image):
        page = await probe.analyze(image, image_data="b64")
        assert page["overall_confidence"] == 0.88
        assert page["field_confidences"] == {"defect_labels": 0.88}

    @pytest.mark.asyncio
    async def test_dual_modal_setting_does_not_add_a_call(
        self, probe, image, monkeypatch
    ):
        """雙模態校正屬 OCR 管線,不得讓影像理解多打一次模型"""
        monkeypatch.setattr(settings, "LLM_DUAL_MODAL_ENABLED", True)
        await probe.analyze(image, image_data="b64")
        assert probe.calls == 1

    @pytest.mark.asyncio
    async def test_repair_photo_routes_to_image_understanding(self):
        processor = ProcessorFactory.get_processor("repair_photo")
        assert isinstance(processor, ImageUnderstandingProcessor)

    @pytest.mark.parametrize("doc_type", ["transcript", "bill", "contract"])
    def test_ocr_types_do_not_route_to_image_understanding(self, doc_type):
        processor = ProcessorFactory.get_processor(doc_type)
        assert not isinstance(processor, ImageUnderstandingProcessor)
