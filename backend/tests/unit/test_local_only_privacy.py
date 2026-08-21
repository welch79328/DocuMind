"""
隱私與全本地運行驗收(ocr-vlm-consensus 任務 14.2)

驗收標準:
- 停用雲端時完整流程可全本地運行
- 驗證無對外連線傳送文件內容
- 相關路徑納入整合測試

「無對外連線」用真的把 socket 封死來驗,不是讀程式碼推論——
只要有任何一條路徑繞過守衛,封死的 socket 就會叫。

對應需求: 2.7, 3.4
"""

import socket

import pytest

from app.config import settings
from app.lib.llm_service.providers import (
    CLOUD_PROVIDERS,
    LocalQwenProvider,
    create_provider,
)
from app.lib.ocr_enhanced.llm_postprocessor import LLMPostprocessor

DOCUMENT_TEXT = "所有權人:黃水木 統一編號:A202******6 地號 0221-0000"


class OutboundBlocked(AssertionError):
    """封死的 socket 被撥出去了——代表文件內容有機會外送"""


@pytest.fixture
def no_outbound(monkeypatch):
    """把對外連線整個封死;localhost 也一併封,確保測試不依賴任何服務"""
    attempts: list = []

    def _blocked(self, address, *args, **kwargs):
        attempts.append(address)
        raise OutboundBlocked(f"嘗試對外連線:{address}")

    monkeypatch.setattr(socket.socket, "connect", _blocked, raising=False)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked, raising=False)
    return attempts


@pytest.fixture
def cloud_disabled(monkeypatch):
    monkeypatch.setattr(settings, "LLM_CLOUD_ENABLED", False)
    monkeypatch.setattr(settings, "LOCAL_QWEN_ENDPOINT", "http://localhost:8001")
    monkeypatch.setattr(settings, "LLM_PROVIDER", "local_qwen")


class TestCloudProvidersRefusedAtConstruction:
    """守衛在建立階段就生效——文件內容連被組裝的機會都沒有"""

    @pytest.mark.parametrize("name", sorted(CLOUD_PROVIDERS))
    def test_every_cloud_provider_is_refused(self, name, cloud_disabled, no_outbound):
        with pytest.raises(ValueError, match="個資不外送"):
            create_provider(name)
        assert no_outbound == []

    def test_correction_service_is_refused(self, cloud_disabled, no_outbound):
        with pytest.raises(ValueError, match="個資不外送"):
            LLMPostprocessor(provider="openai")
        assert no_outbound == []

    def test_default_provider_resolves_to_local(self, cloud_disabled):
        assert isinstance(create_provider(), LocalQwenProvider)

    def test_local_provider_still_available(self, cloud_disabled, no_outbound):
        processor = LLMPostprocessor()
        assert isinstance(processor._provider, LocalQwenProvider)
        # 僅建立 Provider 不應觸發任何連線
        assert no_outbound == []


class TestNoDocumentContentLeavesTheHost:
    @pytest.mark.asyncio
    async def test_correction_never_reaches_the_network(
        self, cloud_disabled, no_outbound
    ):
        """校正走本地端點;端點不通時只能是連線錯誤,不得改走雲端補救"""
        processor = LLMPostprocessor()

        with pytest.raises(BaseException) as exc:
            await processor.correct_full_text(DOCUMENT_TEXT)

        # 唯一被嘗試的位址必須是本地端點
        assert all(
            addr[0] in ("localhost", "127.0.0.1", "::1")
            for addr in no_outbound
            if isinstance(addr, tuple)
        ), no_outbound
        assert exc.value is not None

    def test_local_endpoint_is_the_only_destination(self, cloud_disabled):
        provider = create_provider()
        assert provider.endpoint.startswith("http://localhost")

    def test_cloud_provider_set_is_the_complete_egress_list(self):
        """雲端 Provider 清單即外送清單;新增雲端 Provider 卻忘了列進去,
        守衛就會漏掉它"""
        assert CLOUD_PROVIDERS == {"openai", "anthropic"}


class TestGuardCannotBeBypassedByArguments:
    def test_explicit_api_key_does_not_unlock_cloud(self, cloud_disabled):
        """帶 api_key 不構成豁免——守衛看的是設定,不是呼叫端的意圖"""
        with pytest.raises(ValueError, match="個資不外送"):
            create_provider("openai", api_key="sk-whatever")

    def test_explicit_model_does_not_unlock_cloud(self, cloud_disabled):
        with pytest.raises(ValueError, match="個資不外送"):
            create_provider("openai", model="gpt-4o")

    def test_case_variations_are_still_blocked(self, cloud_disabled):
        for name in ("OpenAI", "OPENAI", "  openai  ".strip()):
            with pytest.raises(ValueError, match="個資不外送"):
                create_provider(name)


class TestKnownGapContractFieldExtraction:
    """
    已知缺口(非本規格引入,已回報業主):
    ContractFieldExtractor._extract_with_llm 直接建構僅支援雲端的 LLMService,
    完全繞過 LLM_CLOUD_ENABLED。需求 2.7 只涵蓋「校正」,故不在本規格範圍,
    但地端承諾在合約欄位抽取這條路上是破的。

    這條測試以 strict xfail 釘住現況:缺口一旦被修好,它會 XPASS 而失敗,
    強迫有人回來把標記拿掉——比留一行 TODO 可靠。
    """

    @pytest.mark.xfail(
        strict=True,
        reason="已知缺口:合約欄位抽取繞過 LLM_CLOUD_ENABLED(待業主裁決後另案修正)",
    )
    def test_contract_extractor_should_honour_the_cloud_guard(
        self, cloud_disabled, monkeypatch
    ):
        from app.lib.multi_type_ocr.contract_field_extractor import (
            ContractFieldExtractor,
        )

        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
        extractor = ContractFieldExtractor()

        # 期望:雲端停用時建構雲端服務應被守衛擋下
        with pytest.raises(ValueError, match="個資不外送"):
            from app.lib.llm_service import LLMService

            extractor.llm_service = LLMService(provider="openai", model="gpt-4o")

    def test_the_gap_is_reachable_today(self, cloud_disabled, monkeypatch):
        """記錄現況:雲端停用時,直接建構 LLMService 仍然成功——這正是缺口所在"""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
        from app.lib.llm_service import LLMService

        service = LLMService(provider="openai", model="gpt-4o")
        assert service.provider == "openai"  # 守衛沒有介入
