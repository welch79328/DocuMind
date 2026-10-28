"""
「文件類型 → 供應商」分流(bedrock-qwen-documind S1;acceptance.md A7 ①②⑨)

  A7 ① 謄本抽取與校正是 openai,四類抽取與校正是 bedrock → TestA7_1_RoutingPerStage
  A7 ② 分流表未知名稱報錯、預設全 openai              → TestA7_2_RoutingTable
  A7 ⑨ 抽取失敗時 llm_used_for_extraction=False      → TestA7_9_ExtractionFailureFlag

處理器層的實跑:OCR 引擎以替身取代(只回固定文字),LLM 以 _llm_fakes 的
Bedrock/OpenAI 替身取代;判斷依據是每次呼叫記下的 llm_calls 與替身收到的請求。
"""

import inspect
import re

import pytest
from PIL import Image

from _llm_fakes import (
    ALL_FOUR_BEDROCK,
    BedrockRecorder,
    OpenAIRecorder,
    bedrock_ok,
    install_bedrock,
    install_openai,
    no_network,  # noqa: F401  (pytest fixture)
)
from app.config import (
    LLM_ROUTABLE_DOCUMENT_TYPES,
    LLM_ROUTABLE_PROVIDERS,
    Settings,
    settings,
)
from app.lib.llm_service.call_log import collect_llm_calls
from app.lib.llm_service.providers import (
    OpenAIProvider,
    create_provider,
)
from app.lib.llm_service.routing import provider_name_for, routed_provider_name
from app.lib.multi_type_ocr.bill_field_extractor import BillFieldExtractor
from app.lib.multi_type_ocr.bill_processor import BillProcessor
from app.lib.multi_type_ocr.contract_field_extractor import ContractFieldExtractor
from app.lib.multi_type_ocr.contract_processor import ContractProcessor
from app.lib.multi_type_ocr.handover_photo_processor import HandoverPhotoProcessor
from app.lib.multi_type_ocr.repair_photo_processor import RepairPhotoProcessor
from app.lib.multi_type_ocr.transcript_field_extractor import TranscriptFieldExtractor
from app.lib.multi_type_ocr.transcript_processor import TranscriptProcessor

# 低信心 OCR 文字:信心度 0.5 < 0.85 觸發全文校正;必要欄位缺 → 觸發 LLM 補欄位
LOW_CONFIDENCE = 0.5
OCR_TEXT = {
    BillProcessor: "戶號: 01-2345-6789",
    ContractProcessor: "付款方式：轉帳",
    TranscriptProcessor: "土地登記第二類謄本",
}


@pytest.fixture
def fake_ocr(monkeypatch):
    """OCR 只回固定文字與低信心度,不跑引擎"""
    for cls, text in OCR_TEXT.items():
        async def _pre(self, image):
            return image

        async def _ocr(self, image, _text=text):
            return _text, LOW_CONFIDENCE

        monkeypatch.setattr(cls, "preprocess", _pre)
        monkeypatch.setattr(cls, "extract_text", _ocr)


@pytest.fixture
def llm(monkeypatch, no_network):
    """Bedrock 與 OpenAI 都換成替身;回傳 (bedrock, openai) 兩個記錄器"""
    bedrock = install_bedrock(monkeypatch, BedrockRecorder(default=bedrock_ok("{}")))
    openai = install_openai(monkeypatch, OpenAIRecorder(content="{}"))
    return bedrock, openai


async def _run_page(processor, enable_llm=True):
    image = Image.new("RGB", (64, 48), "white")
    with collect_llm_calls() as calls:
        result = await processor.analyze(image, image_data="QUJD", enable_llm=enable_llm)
    return result, calls


def _routes(calls):
    return [(c["stage"], c["provider"]) for c in calls]


# --------------------------------------------------------------------------- #
class TestA7_1_RoutingPerStage:
    @pytest.fixture(autouse=True)
    def _all_four_bedrock(self, monkeypatch):
        monkeypatch.setattr(settings, "LLM_PROVIDER_BY_DOCUMENT_TYPE", dict(ALL_FOUR_BEDROCK))

    async def test_bill_correction_and_extraction_go_to_bedrock(self, fake_ocr, llm):
        bedrock, openai = llm
        _, calls = await _run_page(BillProcessor())
        assert _routes(calls) == [("correction", "bedrock"), ("extraction", "bedrock")]
        assert openai.calls == []
        assert len(bedrock.requests) == 2

    async def test_contract_correction_and_extraction_go_to_bedrock(self, fake_ocr, llm):
        bedrock, openai = llm
        _, calls = await _run_page(ContractProcessor())
        assert _routes(calls) == [("correction", "bedrock"), ("extraction", "bedrock")]
        assert {c["model"] for c in calls} == {"qwen.qwen3-vl-235b-a22b"}
        assert openai.calls == []

    @pytest.mark.parametrize("processor_cls", [RepairPhotoProcessor, HandoverPhotoProcessor])
    async def test_photo_understanding_goes_to_bedrock(self, llm, processor_cls):
        bedrock, openai = llm
        _, calls = await _run_page(processor_cls())
        assert _routes(calls) == [("photo_understanding", "bedrock")]
        assert openai.calls == []

    async def test_transcript_stays_on_openai_even_with_all_four_on_bedrock(self, fake_ocr, llm):
        """R3「不含謄本」:四類全切 bedrock 時,謄本的校正與抽取仍是 openai、模型不變"""
        bedrock, openai = llm
        _, calls = await _run_page(TranscriptProcessor())
        assert _routes(calls) == [("correction", "openai"), ("extraction", "openai")]
        assert bedrock.requests == []
        assert [c["model"] for c in openai.calls] == [settings.OPENAI_MODEL, settings.OPENAI_MODEL]

    def test_transcript_cannot_be_put_into_the_table(self, monkeypatch):
        with pytest.raises(ValueError, match="謄本不在分流範圍"):
            Settings(LLM_PROVIDER_BY_DOCUMENT_TYPE={"transcript": "bedrock"})
        monkeypatch.setattr(settings, "LLM_PROVIDER_BY_DOCUMENT_TYPE", {"transcript": "bedrock"})
        with pytest.raises(ValueError):
            routed_provider_name("bill")

    def test_transcript_extractor_does_not_consult_the_table(self):
        assert TranscriptFieldExtractor.ROUTING_DOCUMENT_TYPE is None
        assert isinstance(TranscriptFieldExtractor()._default_provider(), OpenAIProvider)
        assert TranscriptProcessor().llm_provider == "openai"

    def test_global_llm_provider_semantics_unchanged(self, monkeypatch):
        """分流表不改 LLM_PROVIDER:不帶名稱的 create_provider() 仍照全域設定"""
        assert isinstance(create_provider(), OpenAIProvider)
        assert settings.LLM_PROVIDER == "openai"

    async def test_single_type_can_be_switched_back(self, fake_ocr, llm, monkeypatch):
        """R6 切回單一類:只改那一鍵,其他類不受影響"""
        table = dict(ALL_FOUR_BEDROCK, bill="openai")
        monkeypatch.setattr(settings, "LLM_PROVIDER_BY_DOCUMENT_TYPE", table)
        _, bill_calls = await _run_page(BillProcessor())
        _, contract_calls = await _run_page(ContractProcessor())
        assert {c["provider"] for c in bill_calls} == {"openai"}
        assert {c["provider"] for c in contract_calls} == {"bedrock"}


# --------------------------------------------------------------------------- #
class TestA7_2_RoutingTable:
    def test_default_table_is_empty_and_every_stage_resolves_to_openai(self):
        assert Settings.model_fields["LLM_PROVIDER_BY_DOCUMENT_TYPE"].default == {}
        assert settings.LLM_PROVIDER_BY_DOCUMENT_TYPE == {}
        # 校正
        assert BillProcessor().llm_provider == "openai"
        assert ContractProcessor().llm_provider == "openai"
        # 抽取與照片理解
        assert isinstance(BillFieldExtractor()._default_provider(), OpenAIProvider)
        assert isinstance(RepairPhotoProcessor._default_provider(), OpenAIProvider)
        assert isinstance(HandoverPhotoProcessor._default_provider(), OpenAIProvider)
        assert ContractFieldExtractor._llm_provider_name() == "openai"

    @pytest.mark.parametrize("doc_type", sorted(LLM_ROUTABLE_DOCUMENT_TYPES))
    def test_unlisted_type_keeps_its_existing_default(self, doc_type):
        assert routed_provider_name(doc_type) is None
        assert provider_name_for(doc_type, "openai") == "openai"

    async def test_default_routing_sends_everything_to_openai(self, fake_ocr, llm):
        bedrock, openai = llm
        for processor in (BillProcessor(), ContractProcessor(), RepairPhotoProcessor(),
                          HandoverPhotoProcessor()):
            _, calls = await _run_page(processor)
            assert calls and {c["provider"] for c in calls} == {"openai"}
        assert bedrock.requests == []

    async def test_contract_openai_route_keeps_gpt4o(self, fake_ocr, llm, monkeypatch):
        """合約抽取原本寫死 gpt-4o;預設與明寫 openai(R6 切回)都要送一樣的模型"""
        _, openai = llm
        for table in ({}, {"contract": "openai"}):
            openai.calls.clear()
            monkeypatch.setattr(settings, "LLM_PROVIDER_BY_DOCUMENT_TYPE", table)
            await ContractFieldExtractor().extract("付款方式：轉帳", image_data="QUJD", use_llm_fallback=True)
            assert [c["model"] for c in openai.calls] == ["gpt-4o"]
            assert openai.calls[0]["max_tokens"] == 1000
            assert openai.calls[0]["temperature"] == 0.1

    @pytest.mark.parametrize("table", [
        {"bill": "bedrok"},
        {"bill": "gpt"},
        {"bil": "bedrock"},
        {"transcript": "openai"},   # 謄本不在分流範圍(receipt 自直讀計畫起可分流)
    ])
    def test_unknown_names_raise_at_settings_load(self, table):
        with pytest.raises(ValueError):
            Settings(LLM_PROVIDER_BY_DOCUMENT_TYPE=table)

    def test_unknown_names_raise_at_resolution_too(self, monkeypatch):
        """以屬性直接改設定不會經過 pydantic 驗證;解析時同樣要報錯"""
        monkeypatch.setattr(settings, "LLM_PROVIDER_BY_DOCUMENT_TYPE", {"bill": "bedrok"})
        with pytest.raises(ValueError, match="未知的供應商"):
            BillProcessor().llm_provider
        with pytest.raises(ValueError, match="未知的供應商"):
            BillFieldExtractor()._default_provider()

    def test_env_json_is_parsed_and_normalized(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER_BY_DOCUMENT_TYPE", '{"Bill": " Bedrock ", "contract": "openai"}')
        assert Settings().LLM_PROVIDER_BY_DOCUMENT_TYPE == {"bill": "bedrock", "contract": "openai"}

    def test_routable_providers_match_create_provider_branches(self):
        """分流表接受的名稱必須正是 create_provider 認得的名稱,不多不少"""
        branches = set(re.findall(r'name == "([a-z0-9_]+)"', inspect.getsource(create_provider)))
        assert branches == set(LLM_ROUTABLE_PROVIDERS)


# --------------------------------------------------------------------------- #
class TestA7_9_ExtractionFailureFlag:
    async def test_bill_bedrock_failure_marks_llm_unused(self, monkeypatch, no_network):
        install_bedrock(monkeypatch, BedrockRecorder([(500, {"message": "boom"})]))
        monkeypatch.setattr(settings, "LLM_PROVIDER_BY_DOCUMENT_TYPE", {"bill": "bedrock"})
        result = await BillFieldExtractor().extract(
            "戶號: 01-2345-6789", image_data="QUJD", use_llm_fallback=True
        )
        assert result["llm_used_for_extraction"] is False
        assert "amount" in result["needs_confirmation"]

    async def test_bill_success_still_marks_llm_used(self, monkeypatch, no_network):
        install_bedrock(monkeypatch, BedrockRecorder([bedrock_ok('{"amount": "980"}')]))
        monkeypatch.setattr(settings, "LLM_PROVIDER_BY_DOCUMENT_TYPE", {"bill": "bedrock"})
        result = await BillFieldExtractor().extract(
            "戶號: 01-2345-6789", image_data="QUJD", use_llm_fallback=True
        )
        assert result["amount"] == "980"
        assert result["llm_used_for_extraction"] is True

    async def test_openai_failure_marks_llm_unused(self, monkeypatch, no_network):
        """修的是共用基底(F6),openai 路由的失敗也一樣不再標 True"""
        install_openai(monkeypatch, OpenAIRecorder(fail=RuntimeError("invalid api key")))
        result = await BillFieldExtractor().extract(
            "戶號: 01-2345-6789", image_data="QUJD", use_llm_fallback=True
        )
        assert result["llm_used_for_extraction"] is False

    async def test_contract_bedrock_failure_marks_llm_unused(self, monkeypatch, no_network):
        install_bedrock(monkeypatch, BedrockRecorder([(403, {"message": "denied"})]))
        monkeypatch.setattr(settings, "LLM_PROVIDER_BY_DOCUMENT_TYPE", {"contract": "bedrock"})
        result = await ContractFieldExtractor().extract(
            "合約編號：REGEX-001", image_data="QUJD", use_llm_fallback=True
        )
        assert result["llm_used_for_extraction"] is False
        assert result["contract_metadata"]["contract_number"] == "REGEX-001"

    async def test_bill_page_reports_failure_in_llm_calls(self, fake_ocr, monkeypatch, no_network):
        recorder = install_bedrock(monkeypatch, BedrockRecorder(default=(400, {"message": "bad"})))
        monkeypatch.setattr(settings, "LLM_PROVIDER_BY_DOCUMENT_TYPE", {"bill": "bedrock"})
        result, calls = await _run_page(BillProcessor())
        assert result["structured_data"]["llm_used_for_extraction"] is False
        assert [(c["stage"], c["ok"], c["error"]) for c in calls] == [
            ("correction", False, "http_400"),
            ("extraction", False, "http_400"),
        ]
        assert len(recorder.requests) == 2
