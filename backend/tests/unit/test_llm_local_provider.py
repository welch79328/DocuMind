"""
測試本地 Qwen Provider 與隱私守衛(任務 7.2)

- 可切換 openai / local_qwen
- 雲端停用(LLM_CLOUD_ENABLED=false)時載入雲端 Provider 被阻擋
- 本地端點缺失時配置驗證報錯
- LocalQwenProvider 走 OpenAI 相容格式(重用 few-shot / 多模態 content)

對應需求: 7.3
"""

import pytest
from unittest.mock import AsyncMock

from app.config import settings
from app.lib.llm_service.providers import (
    OpenAIProvider,
    LocalQwenProvider,
    create_provider,
)


@pytest.fixture
def local_endpoint(monkeypatch):
    monkeypatch.setattr(settings, "LOCAL_QWEN_ENDPOINT", "http://localhost:8001")
    return "http://localhost:8001"


class TestProviderSwitching:
    def test_create_local_qwen(self, local_endpoint):
        provider = create_provider("local_qwen")
        assert isinstance(provider, LocalQwenProvider)
        assert provider.endpoint == "http://localhost:8001"

    def test_create_openai_when_cloud_enabled(self, monkeypatch):
        monkeypatch.setattr(settings, "LLM_CLOUD_ENABLED", True)
        assert isinstance(create_provider("openai"), OpenAIProvider)


class TestPrivacyGuard:
    def test_cloud_provider_blocked_when_disabled(self, monkeypatch):
        monkeypatch.setattr(settings, "LLM_CLOUD_ENABLED", False)
        with pytest.raises(ValueError):
            create_provider("openai")

    def test_local_provider_allowed_when_cloud_disabled(self, monkeypatch, local_endpoint):
        monkeypatch.setattr(settings, "LLM_CLOUD_ENABLED", False)
        # 本地不外送,雲端停用時仍可用
        assert isinstance(create_provider("local_qwen"), LocalQwenProvider)


class TestEndpointValidation:
    def test_missing_endpoint_raises(self, monkeypatch):
        monkeypatch.setattr(settings, "LOCAL_QWEN_ENDPOINT", "")
        with pytest.raises(ValueError):
            create_provider("local_qwen")

    def test_constructor_rejects_empty_endpoint(self):
        with pytest.raises(ValueError):
            LocalQwenProvider(endpoint="")


class TestLocalCall:
    async def test_call_uses_openai_compatible_format(self, local_endpoint):
        provider = create_provider("local_qwen")
        captured = {}

        async def fake_request(messages, max_tokens, temperature):
            captured["messages"] = messages
            return "本地回應"

        provider._request = fake_request  # type: ignore

        result = await provider.call(
            "任務", image_data="ABC",
            few_shot=[{"input_ref": "ref1", "corrected_fields": {"a": "1"}}],
        )
        assert result == "本地回應"
        content = captured["messages"][0]["content"]
        # 多模態格式(list)且含影像
        assert isinstance(content, list)
        assert content[1]["type"] == "image_url"
        # few-shot 注入於文字段
        assert "ref1" in content[0]["text"]

    async def test_request_posts_to_vllm_endpoint(self, local_endpoint, monkeypatch):
        provider = create_provider("local_qwen")

        # 攔截 httpx.AsyncClient.post
        class FakeResp:
            def raise_for_status(self):
                pass

            def json(self):
                return {"choices": [{"message": {"content": "ok"}}]}

        posted = {}

        class FakeClient:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def post(self, url, json, headers):
                posted["url"] = url
                posted["payload"] = json
                return FakeResp()

        import httpx
        monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

        out = await provider.call("hi")
        assert out == "ok"
        assert posted["url"].endswith("/v1/chat/completions")
        assert posted["payload"]["model"]
