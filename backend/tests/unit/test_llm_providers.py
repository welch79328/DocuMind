"""
測試 LLMProvider 抽象與 OpenAIProvider(任務 7.1)

- Provider 介面(ABC)不可直接實例化
- OpenAIProvider 支援影像輸入與 few-shot 注入
- 工廠依 settings.LLM_PROVIDER 建立 Provider
- 既有雲端呼叫行為不變(訊息組裝與 OpenAI 一致)

對應需求: 7.3
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.lib.llm_service.providers import (
    LLMProvider,
    OpenAIProvider,
    create_provider,
)


class TestABC:
    def test_llm_provider_is_abstract(self):
        with pytest.raises(TypeError):
            LLMProvider()  # type: ignore


class TestFewShotInjection:
    def test_no_few_shot_returns_prompt_unchanged(self):
        p = OpenAIProvider(model="gpt-4o", api_key="x")
        assert p._build_prompt("原始提示", None) == "原始提示"
        assert p._build_prompt("原始提示", []) == "原始提示"

    def test_few_shot_injected_into_prompt(self):
        p = OpenAIProvider(model="gpt-4o", api_key="x")
        few_shot = [
            {"input_ref": "土地登記 doc1", "corrected_fields": {"area": "128.45"}},
        ]
        result = p._build_prompt("請抽取欄位", few_shot)
        # 應包含參考範例與正確欄位值,且保留原始任務
        assert "128.45" in result
        assert "doc1" in result
        assert "請抽取欄位" in result
        assert result != "請抽取欄位"


class TestContentBuilding:
    def test_text_only_content_is_string(self):
        p = OpenAIProvider(api_key="x")
        assert p._build_content("hello", None) == "hello"

    def test_image_content_is_multimodal_list(self):
        p = OpenAIProvider(api_key="x")
        content = p._build_content("prompt", "BASE64DATA")
        assert isinstance(content, list)
        assert content[0]["type"] == "text"
        assert content[1]["type"] == "image_url"
        # 自動補上 data:image 前綴
        assert content[1]["image_url"]["url"].startswith("data:image")

    def test_image_with_existing_prefix_kept(self):
        p = OpenAIProvider(api_key="x")
        url = "data:image/png;base64,ABC"
        content = p._build_content("prompt", url)
        assert content[1]["image_url"]["url"] == url


class TestFactory:
    def test_create_openai_provider(self):
        provider = create_provider("openai")
        assert isinstance(provider, OpenAIProvider)

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError):
            create_provider("nonexistent")

    def test_default_from_settings(self):
        # 預設 settings.LLM_PROVIDER = openai
        provider = create_provider()
        assert isinstance(provider, OpenAIProvider)


class TestCall:
    async def test_call_invokes_client_and_returns_content(self):
        p = OpenAIProvider(model="gpt-4o", api_key="x")

        fake_response = MagicMock()
        fake_response.choices = [MagicMock(message=MagicMock(content="修正後文字"))]
        fake_response.usage = MagicMock(total_tokens=100, prompt_tokens=60, completion_tokens=40)

        fake_client = MagicMock()
        fake_client.chat.completions.create = AsyncMock(return_value=fake_response)
        p._client = fake_client  # 注入 mock,避免真實 openai 呼叫

        result = await p.call("請修正", image_data=None)
        assert result == "修正後文字"
        assert fake_client.chat.completions.create.await_count == 1

    async def test_call_injects_few_shot_into_message(self):
        p = OpenAIProvider(model="gpt-4o", api_key="x")
        fake_response = MagicMock()
        fake_response.choices = [MagicMock(message=MagicMock(content="ok"))]
        fake_response.usage = MagicMock(total_tokens=1, prompt_tokens=1, completion_tokens=0)
        fake_client = MagicMock()
        fake_client.chat.completions.create = AsyncMock(return_value=fake_response)
        p._client = fake_client

        await p.call("任務", few_shot=[{"input_ref": "ref1", "corrected_fields": {"a": "1"}}])
        _, kwargs = fake_client.chat.completions.create.call_args
        sent_content = kwargs["messages"][0]["content"]
        # 純文字任務時 content 為字串,應含注入的範例
        assert "ref1" in sent_content
