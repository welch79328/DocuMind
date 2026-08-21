"""
測試雙模態 LLM 校正(ocr-vlm-consensus 任務 8.1~8.3)

- 8.1 校正經 create_provider() 抽象呼叫;雲端停用時拒絕外送
- 8.2 雙模態輸入、影像失敗降級、模型拒絕保留原文、停用時零呼叫
- 8.3 提示詞與實際模態一致

對應需求: 2.1, 2.3, 2.4, 2.6, 2.7, 2.8
"""

import base64

import pytest
from unittest.mock import AsyncMock

from app.config import settings
from app.lib.llm_service.providers import (
    AnthropicProvider,
    LocalQwenProvider,
    OpenAIProvider,
    create_provider,
)
from app.lib.ocr_enhanced.dual_modal_corrector import (
    DualModalCorrector,
    build_correction_prompt,
    is_refusal,
    normalize_image_data,
)
from app.lib.ocr_enhanced.llm_postprocessor import LLMPostprocessor

VALID_B64 = base64.b64encode(b"fake-png-bytes").decode()
OCR_TEXT = "中焉區中班息三小旋 o221-oooo 地號"


class _FakeProvider:
    """記錄呼叫參數的假 Provider,讓斷言能檢查實際送出的模態"""

    def __init__(self, response: str = "校正後全文"):
        self.response = response
        self.calls: list[dict] = []
        self.stats = {
            "llm_calls": 0,
            "tokens_used": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "estimated_cost": 0.0,
        }

    async def call(self, prompt, image_data=None, few_shot=None, **kwargs):
        self.calls.append({"prompt": prompt, "image_data": image_data})
        self.stats["llm_calls"] += 1
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


@pytest.fixture
def dual_on(monkeypatch):
    monkeypatch.setattr(settings, "LLM_DUAL_MODAL_ENABLED", True)


@pytest.fixture
def dual_off(monkeypatch):
    monkeypatch.setattr(settings, "LLM_DUAL_MODAL_ENABLED", False)


# ====================================================================== #
# 任務 8.1:統一抽象 + 隱私守衛
# ====================================================================== #
class TestProviderAbstraction:
    def test_postprocessor_builds_provider_via_factory(self, monkeypatch):
        """校正器經 create_provider 取得模型,而非直接綁定雲端服務層"""
        monkeypatch.setattr(settings, "LLM_CLOUD_ENABLED", True)
        processor = LLMPostprocessor(provider="openai", api_key="x")
        assert isinstance(processor._provider, OpenAIProvider)

    def test_local_provider_is_supported(self, monkeypatch):
        """抽象支援本地部署選項(需求 2.6)"""
        monkeypatch.setattr(settings, "LLM_PROVIDER", "local_qwen")
        monkeypatch.setattr(settings, "LOCAL_QWEN_ENDPOINT", "http://localhost:8001")
        processor = LLMPostprocessor()
        assert isinstance(processor._provider, LocalQwenProvider)

    def test_cloud_disabled_refuses_to_build_cloud_provider(self, monkeypatch):
        """停用雲端時,校正器建立階段即被擋下,文件內容無從外送(需求 2.7)"""
        monkeypatch.setattr(settings, "LLM_CLOUD_ENABLED", False)
        with pytest.raises(ValueError, match="個資不外送"):
            LLMPostprocessor(provider="openai")

    def test_cloud_disabled_still_allows_local(self, monkeypatch):
        monkeypatch.setattr(settings, "LLM_CLOUD_ENABLED", False)
        monkeypatch.setattr(settings, "LOCAL_QWEN_ENDPOINT", "http://localhost:8001")
        processor = LLMPostprocessor(provider="local_qwen")
        assert isinstance(processor._provider, LocalQwenProvider)

    def test_anthropic_provider_registered(self, monkeypatch):
        """anthropic 已列於 CLOUD_PROVIDERS,工廠必須真的建得出來"""
        monkeypatch.setattr(settings, "LLM_CLOUD_ENABLED", True)
        assert isinstance(create_provider("anthropic"), AnthropicProvider)

    def test_anthropic_blocked_when_cloud_disabled(self, monkeypatch):
        monkeypatch.setattr(settings, "LLM_CLOUD_ENABLED", False)
        with pytest.raises(ValueError, match="個資不外送"):
            create_provider("anthropic")

    def test_stats_keeps_estimated_cost_key(self, monkeypatch):
        """既有成本紀錄讀 estimated_cost,遷移後不得消失"""
        monkeypatch.setattr(settings, "LLM_CLOUD_ENABLED", True)
        processor = LLMPostprocessor(provider="openai", api_key="x")
        assert "estimated_cost" in processor.stats


class TestAnthropicProviderAssembly:
    def test_text_only_content_is_string(self):
        p = AnthropicProvider(api_key="x")
        assert p._build_content("hello", None) == "hello"

    def test_image_content_strips_data_uri_prefix(self):
        p = AnthropicProvider(api_key="x")
        content = p._build_content("prompt", f"data:image/png;base64,{VALID_B64}")
        assert content[0]["type"] == "image"
        assert content[0]["source"]["data"] == VALID_B64
        assert content[1]["text"] == "prompt"


# ====================================================================== #
# 任務 8.2:三條路徑
# ====================================================================== #
class TestDualModality:
    @pytest.mark.asyncio
    async def test_dual_modal_sends_text_and_image(self, dual_on):
        """場景 1:正常頁面,校正輸入同時含文字與影像"""
        provider = _FakeProvider()
        result = await DualModalCorrector(provider).correct(OCR_TEXT, image_data=VALID_B64)

        assert result["modality"] == "dual"
        assert result["degraded_reason"] is None
        assert provider.calls[0]["image_data"] == VALID_B64
        assert OCR_TEXT in provider.calls[0]["prompt"]

    @pytest.mark.asyncio
    async def test_disabled_flag_keeps_text_only(self, dual_off):
        """預設關閉時行為與現行純文字校正一致,且不算降級"""
        provider = _FakeProvider()
        result = await DualModalCorrector(provider).correct(OCR_TEXT, image_data=VALID_B64)

        assert result["modality"] == "text_only"
        assert result["degraded_reason"] is None
        assert provider.calls[0]["image_data"] is None


class TestDegradation:
    @pytest.mark.asyncio
    async def test_missing_image_degrades_with_reason(self, dual_on):
        """場景 2:影像未提供 → 純文字且記錄事由,流程不中斷"""
        provider = _FakeProvider()
        result = await DualModalCorrector(provider).correct(OCR_TEXT, image_data=None)

        assert result["modality"] == "text_only"
        assert result["degraded_reason"] and "影像不可用" in result["degraded_reason"]
        assert result["text"] == "校正後全文"

    @pytest.mark.asyncio
    async def test_invalid_base64_degrades_with_reason(self, dual_on):
        """影像編碼失敗 → 純文字降級,不得拋出中斷辨識"""
        provider = _FakeProvider()
        result = await DualModalCorrector(provider).correct(
            OCR_TEXT, image_data="!!!not-base64!!!"
        )

        assert result["modality"] == "text_only"
        assert "影像不可用" in result["degraded_reason"]

    @pytest.mark.asyncio
    async def test_dual_call_failure_falls_back_to_text(self, dual_on):
        """帶影像呼叫失敗時重試純文字,而非讓整份文件失敗"""
        class _FailOnImage(_FakeProvider):
            async def call(self, prompt, image_data=None, few_shot=None, **kwargs):
                if image_data is not None:
                    self.calls.append({"prompt": prompt, "image_data": image_data})
                    raise RuntimeError("模型不支援影像")
                return await _FakeProvider.call(
                    self, prompt, image_data, few_shot, **kwargs
                )

        provider = _FailOnImage()
        result = await DualModalCorrector(provider).correct(OCR_TEXT, image_data=VALID_B64)

        assert result["modality"] == "text_only"
        assert "雙模態呼叫失敗" in result["degraded_reason"]
        assert result["text"] == "校正後全文"
        assert len(provider.calls) == 2

    def test_normalize_rejects_empty(self):
        with pytest.raises(ValueError):
            normalize_image_data(None)
        with pytest.raises(ValueError):
            normalize_image_data("data:image/png;base64,")


class TestRefusal:
    @pytest.mark.asyncio
    async def test_refusal_returns_original_text(self, dual_off):
        """場景 6:模型拒絕時回傳原始辨識文字,不得以拒絕訊息覆蓋(需求 2.8)"""
        provider = _FakeProvider(response="抱歉，我無法處理這份文件。")
        result = await DualModalCorrector(provider).correct(OCR_TEXT)

        assert result["refused"] is True
        assert result["text"] == OCR_TEXT

    @pytest.mark.asyncio
    async def test_long_text_containing_apology_is_not_refusal(self, dual_off):
        """正常長文中出現「抱歉」不得誤判為拒絕"""
        long_text = "抱歉" + "土地登記第三類謄本" * 30
        provider = _FakeProvider(response=long_text)
        result = await DualModalCorrector(provider).correct(OCR_TEXT)

        assert result["refused"] is False
        assert result["text"] == long_text

    def test_is_refusal_boundaries(self):
        assert is_refusal("I'm sorry, I can't assist with that.") is True
        assert is_refusal("土地登記第三類謄本(所有權個人全部)") is False


class TestDisabledCorrectionCostsNothing:
    @pytest.mark.asyncio
    async def test_no_model_call_when_llm_disabled(self):
        """場景 3:停用 LLM 時完全跳過校正,不產生任何模型呼叫(需求 2.4)"""
        from app.lib.ocr_enhanced.postprocessor import TranscriptPostprocessor

        postprocessor = TranscriptPostprocessor(enable_llm=False)
        assert postprocessor.llm_processor is None

        result = await postprocessor._apply_llm_correction(OCR_TEXT, 0.1)
        assert result["used"] is False
        assert result["cost"] == 0.0

    @pytest.mark.asyncio
    async def test_strategy_none_skips_model_call(self, monkeypatch):
        """策略為 none 時不觸發 Provider 呼叫"""
        from app.lib.ocr_enhanced.postprocessor import TranscriptPostprocessor

        postprocessor = TranscriptPostprocessor(enable_llm=False, llm_strategy="none")
        provider = _FakeProvider()
        postprocessor.enable_llm = True
        postprocessor.llm_processor = LLMPostprocessor.__new__(LLMPostprocessor)
        postprocessor.llm_processor._provider = provider

        result = await postprocessor._apply_llm_correction(OCR_TEXT, 0.1)
        assert result["used"] is False
        assert provider.stats["llm_calls"] == 0


# ====================================================================== #
# 任務 8.3:提示詞與模態一致
# ====================================================================== #
class TestPromptModalityConsistency:
    def test_text_only_prompt_has_no_image_instruction(self):
        prompt = build_correction_prompt(OCR_TEXT, has_image=False)
        assert "圖片" not in prompt
        assert "不要憑上下文臆測" in prompt

    def test_dual_prompt_keeps_image_instruction(self):
        prompt = build_correction_prompt(OCR_TEXT, has_image=True)
        assert "請仔細查看上面提供的文件圖片" in prompt

    def test_both_prompts_carry_the_ocr_text(self):
        for has_image in (True, False):
            assert OCR_TEXT in build_correction_prompt(OCR_TEXT, has_image=has_image)

    @pytest.mark.asyncio
    async def test_actual_call_prompt_matches_modality(self, dual_on):
        """實際送出的提示詞須與該次呼叫的模態一致,而非寫死"""
        provider = _FakeProvider()
        corrector = DualModalCorrector(provider)

        await corrector.correct(OCR_TEXT, image_data=VALID_B64)
        assert "請仔細查看上面提供的文件圖片" in provider.calls[0]["prompt"]

        await corrector.correct(OCR_TEXT, image_data=None)
        assert "圖片" not in provider.calls[1]["prompt"]


# ====================================================================== #
# 向後相容
# ====================================================================== #
class TestBackwardCompatibility:
    @pytest.mark.asyncio
    async def test_correct_full_text_signature_unchanged(self, dual_off, monkeypatch):
        monkeypatch.setattr(settings, "LLM_CLOUD_ENABLED", True)
        processor = LLMPostprocessor(provider="openai", api_key="x")
        provider = _FakeProvider()
        processor._provider = provider
        processor._corrector = DualModalCorrector(provider)

        text, stats = await processor.correct_full_text(OCR_TEXT, doc_type="transcript")

        assert text == "校正後全文"
        assert stats["llm_calls"] == 1
        assert processor.last_result["modality"] == "text_only"

    @pytest.mark.asyncio
    async def test_correct_fields_uses_provider(self, monkeypatch):
        monkeypatch.setattr(settings, "LLM_CLOUD_ENABLED", True)
        processor = LLMPostprocessor(provider="openai", api_key="x")
        provider = _FakeProvider(response="0221-0000")
        processor._provider = provider

        text, corrections = await processor.correct_fields(
            "地號 o221-oooo", fields_to_correct=["land_number"]
        )

        assert provider.stats["llm_calls"] == 1
        assert corrections["land_number"]["corrected"] == "0221-0000"
