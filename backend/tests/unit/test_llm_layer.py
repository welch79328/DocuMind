"""
LLM 層整合/邊界測試(任務 7.3)

補強 7.1/7.2 的邊界,聚焦:
- Provider 多型可插拔(兩者皆為 LLMProvider,可經介面呼叫)
- few-shot 注入的多範例、順序、空欄位
- 隱私守衛完整性(所有雲端 Provider 於停用時皆被阻擋)

對應需求: 7.3
"""

import pytest
from unittest.mock import AsyncMock

from app.config import settings
from app.lib.llm_service.providers import (
    LLMProvider,
    OpenAIProvider,
    LocalQwenProvider,
    _inject_few_shot,
    create_provider,
)


class TestPluggability:
    def test_both_providers_are_llm_provider(self, monkeypatch):
        monkeypatch.setattr(settings, "LOCAL_QWEN_ENDPOINT", "http://x:8000")
        assert isinstance(OpenAIProvider(api_key="x"), LLMProvider)
        assert isinstance(LocalQwenProvider(endpoint="http://x:8000"), LLMProvider)

    async def test_polymorphic_call_through_interface(self):
        # 任何 LLMProvider 皆可用相同介面呼叫
        async def use_provider(p: LLMProvider) -> str:
            return await p.call("提示", few_shot=None)

        oa = OpenAIProvider(api_key="x")
        oa.call = AsyncMock(return_value="A")  # type: ignore
        lq = LocalQwenProvider(endpoint="http://x:8000")
        lq.call = AsyncMock(return_value="B")  # type: ignore

        assert await use_provider(oa) == "A"
        assert await use_provider(lq) == "B"


class TestFewShotEdges:
    def test_multiple_examples_order_preserved(self):
        few_shot = [
            {"input_ref": "first", "corrected_fields": {"a": "1"}},
            {"input_ref": "second", "corrected_fields": {"b": "2"}},
        ]
        result = _inject_few_shot("任務", few_shot)
        assert result.index("first") < result.index("second")
        assert "範例 1" in result and "範例 2" in result

    def test_empty_corrected_fields_handled(self):
        result = _inject_few_shot("任務", [{"input_ref": "ref", "corrected_fields": {}}])
        assert "ref" in result
        assert "任務" in result

    def test_injection_identical_across_providers(self):
        # OpenAI 與 Local 使用同一 few-shot 注入邏輯
        few_shot = [{"input_ref": "r", "corrected_fields": {"x": "9"}}]
        oa = OpenAIProvider._build_prompt("t", few_shot)
        common = _inject_few_shot("t", few_shot)
        assert oa == common


class TestPrivacyGuardCompleteness:
    def test_all_cloud_providers_blocked_when_disabled(self, monkeypatch):
        monkeypatch.setattr(settings, "LLM_CLOUD_ENABLED", False)
        for cloud in ("openai", "anthropic"):
            with pytest.raises(ValueError):
                create_provider(cloud)

    def test_disabled_message_mentions_privacy(self, monkeypatch):
        monkeypatch.setattr(settings, "LLM_CLOUD_ENABLED", False)
        with pytest.raises(ValueError, match="外送|停用"):
            create_provider("openai")

    def test_default_provider_respects_guard(self, monkeypatch):
        # settings.LLM_PROVIDER 預設 openai;雲端停用時預設路徑亦被阻擋
        monkeypatch.setattr(settings, "LLM_PROVIDER", "openai")
        monkeypatch.setattr(settings, "LLM_CLOUD_ENABLED", False)
        with pytest.raises(ValueError):
            create_provider()

    def test_local_provider_unaffected_by_guard(self, monkeypatch):
        monkeypatch.setattr(settings, "LLM_CLOUD_ENABLED", False)
        monkeypatch.setattr(settings, "LOCAL_QWEN_ENDPOINT", "http://x:8000")
        assert isinstance(create_provider("local_qwen"), LocalQwenProvider)
