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

# 確認為本地部署、不外送的 Provider 名稱;
# create_provider 新增分支時必須落入這裡或 CLOUD_PROVIDERS 其中之一
LOCAL_PROVIDERS = {"local_qwen"}

CONTRACT_TEXT = """
合約編號：ABC-2026-001
簽訂日期：2026年3月26日
甲方：台灣科技股份有限公司
乙方：全球資訊有限公司
合約金額：新台幣 1,000,000 元
"""


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

        # 先確認被測路徑真的碰到網路——no_outbound 為空時下面的 all() 恆真,
        # 那樣這條測試就只是在證明「什麼都沒發生」
        assert no_outbound, "校正路徑未觸及網路,本測試失去意義"

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

    def test_every_provider_branch_is_classified(self):
        """每個 create_provider 分支都必須被歸類為雲端或本地。

        原本這裡寫的是 `CLOUD_PROVIDERS == {"openai","anthropic"}`,
        但那在它自稱要抓的情境下恆真——新增一個 gemini 分支卻不列進
        CLOUD_PROVIDERS,集合仍然等於那兩個,測試照樣綠。
        改為從函式原始碼取出所有分支名稱,逐一要求歸類。
        """
        import inspect
        import re

        source = inspect.getsource(create_provider)
        branches = set(re.findall(r'name == "([a-z0-9_]+)"', source))
        assert branches, "找不到任何 Provider 分支,取法可能已失效"

        unclassified = branches - CLOUD_PROVIDERS - LOCAL_PROVIDERS
        assert not unclassified, (
            f"這些 Provider 分支未被歸類:{sorted(unclassified)}。"
            "雲端的必須列入 CLOUD_PROVIDERS 才會被守衛擋下;"
            "本地的請列入本測試的 LOCAL_PROVIDERS。"
        )

    def test_known_cloud_providers_are_all_guarded(self):
        assert {"openai", "anthropic"} <= CLOUD_PROVIDERS


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


class TestContractExtractionHonoursTheGuard:
    """
    曾經的缺口(現已修補):`ContractFieldExtractor._extract_with_llm` 直接建構
    僅支援雲端的 `LLMService`,完全繞過 `LLM_CLOUD_ENABLED`,在全地端組態下
    仍把合約文字與頁面影像送往 OpenAI。

    守衛已下放至 `LLMService.__init__`——那是舊路徑的匯流點,
    只要有任何一處直接 new 它,地端承諾就會再破一次。
    """

    def test_llm_service_refuses_cloud_when_disabled(self, cloud_disabled, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
        from app.lib.llm_service import LLMService

        with pytest.raises(ValueError, match="個資不外送"):
            LLMService(provider="openai", model="gpt-4o")

    def test_llm_service_refuses_anthropic_too(self, cloud_disabled, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-real")
        from app.lib.llm_service import LLMService

        with pytest.raises(ValueError, match="個資不外送"):
            LLMService(provider="anthropic")

    def test_llm_service_still_works_when_cloud_enabled(self, monkeypatch):
        """守衛只在地端組態下生效,不得順手把雲端模式也弄壞"""
        monkeypatch.setattr(settings, "LLM_CLOUD_ENABLED", True)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
        from app.lib.llm_service import LLMService

        assert LLMService(provider="openai", model="gpt-4o").provider == "openai"

    def test_two_cloud_lists_stay_in_sync(self):
        """LLMService 與 providers 各有一份雲端清單,分歧會讓其中一條路徑漏掉守衛"""
        from app.lib.llm_service.llm_service import _CLOUD_ONLY_PROVIDERS

        assert set(_CLOUD_ONLY_PROVIDERS) == set(CLOUD_PROVIDERS)

    @pytest.mark.asyncio
    async def test_contract_extraction_sends_nothing_when_cloud_disabled(
        self, cloud_disabled, no_outbound, monkeypatch
    ):
        """驗收核心:全地端組態下跑完整合約抽取,不得有任何對外連線"""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
        from app.lib.multi_type_ocr.contract_field_extractor import (
            ContractFieldExtractor,
        )

        result = await ContractFieldExtractor().extract(
            CONTRACT_TEXT, image_data="ZmFrZS1pbWFnZQ==", use_llm_fallback=True
        )

        assert no_outbound == [], f"合約內容外送了:{no_outbound}"
        # 流程不中斷:仍回傳正則抽取結果,交由既有低信心流程處理
        assert result["contract_metadata"]["contract_number"] == "ABC-2026-001"
        assert result["llm_used_for_extraction"] is False

    @pytest.mark.asyncio
    async def test_skip_is_logged_as_policy_not_failure(
        self, cloud_disabled, no_outbound, monkeypatch, caplog
    ):
        """紀錄要講清楚「這是政策決定」。只靠 LLMService 守衛兜底的話,
        日誌會寫成「LLM 提取失敗」,值班的人會去查一個不存在的故障"""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
        from app.lib.multi_type_ocr.contract_field_extractor import (
            ContractFieldExtractor,
        )

        logger_name = "app.lib.multi_type_ocr.contract_field_extractor"
        with caplog.at_level("INFO", logger=logger_name):
            await ContractFieldExtractor().extract(
                CONTRACT_TEXT, image_data="ZmFrZS1pbWFnZQ==", use_llm_fallback=True
            )

        assert "合約內容不外送" in caplog.text
        assert "LLM 提取失敗" not in caplog.text

    @pytest.mark.asyncio
    async def test_low_confidence_alone_no_longer_triggers_egress(
        self, cloud_disabled, no_outbound, monkeypatch
    ):
        """信心度低正是 OCR 難讀、最需要保密的時候,絕不能因此外送"""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
        from app.lib.multi_type_ocr.contract_field_extractor import (
            ContractFieldExtractor,
        )

        extractor = ContractFieldExtractor()
        result = await extractor.extract(
            "幾乎讀不出東西的雜訊", image_data="ZmFrZS1pbWFnZQ==", use_llm_fallback=True
        )

        assert result["extraction_confidence"] < extractor.CONFIDENCE_THRESHOLD
        assert no_outbound == []
