"""
LLM 測試替身(bedrock-qwen-documind S1 的測試共用)。

- Bedrock:以 httpx.MockTransport 取代網路,記下每個送出的請求。
- OpenAI:以假的 AsyncOpenAI 客戶端取代,記下每次呼叫的參數。

所有測試都不連外;test 檔另以 socket 封鎖再確認一次。
"""

from __future__ import annotations

import json
import socket
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional, Union

import httpx
import pytest
from pydantic import SecretStr

from app.config import settings
from app.lib.llm_service.providers import BedrockProvider, OpenAIProvider

FAKE_BEDROCK_KEY = "test-bedrock-key-NOT-REAL-7f3a9c"

# 模擬 AWS 拒絕存取時帶 IAM ARN 的回應內文(F7:這種字串不得出現在回應)
ARN_BODY = {
    "error": {
        "message": (
            "User: arn:aws:iam::123456789012:user/app-jgb-ai-cs-bedrock is not authorized "
            "to perform: bedrock:InvokeModel on resource: "
            "arn:aws:bedrock:ap-northeast-1::foundation-model/qwen.qwen3-vl-235b-a22b"
        )
    }
}

Reply = Union[Exception, tuple, Callable[[httpx.Request], httpx.Response]]


def bedrock_ok(content: str = "{}", tier: Optional[str] = "flex") -> tuple:
    body: Dict[str, Any] = {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": 1000, "completion_tokens": 100, "total_tokens": 1100},
    }
    if tier is not None:
        body["service_tier"] = tier
    return (200, body)


class BedrockRecorder:
    """依序回覆;回覆用完後一律回 bedrock_ok()。記下每個請求的 JSON 內容。"""

    def __init__(self, replies: Optional[List[Reply]] = None, default: Optional[Reply] = None):
        self.replies = list(replies or [])
        self.default = default if default is not None else bedrock_ok()
        self.requests: List[httpx.Request] = []

    @property
    def bodies(self) -> List[Dict[str, Any]]:
        return [json.loads(r.content) for r in self.requests]

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        reply = self.replies.pop(0) if self.replies else self.default
        if callable(reply) and not isinstance(reply, Exception):
            return reply(request)
        if isinstance(reply, Exception):
            raise reply
        status, body = reply
        return httpx.Response(status, json=body)

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)


@pytest.fixture
def no_network(monkeypatch):
    """把真正的 socket 連線封死:任何測試若真的連外會立刻失敗。"""
    def _blocked(self, address, *args, **kwargs):
        raise AssertionError(f"測試嘗試對外連線:{address}")

    monkeypatch.setattr(socket.socket, "connect", _blocked, raising=False)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked, raising=False)


def install_bedrock(monkeypatch, recorder: BedrockRecorder) -> BedrockRecorder:
    monkeypatch.setattr(settings, "LLM_CLOUD_ENABLED", True)
    monkeypatch.setattr(settings, "BEDROCK_API_KEY", SecretStr(FAKE_BEDROCK_KEY))
    monkeypatch.setattr(BedrockProvider, "_transport", recorder.transport())
    return recorder


class OpenAIRecorder:
    """假的 AsyncOpenAI:記下每次 chat.completions.create 的參數。"""

    def __init__(self, content: str = "{}", fail: Optional[Exception] = None):
        self.content = content
        self.fail = fail
        self.calls: List[Dict[str, Any]] = []

    async def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail is not None:
            raise self.fail
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            service_tier="default",
        )

    def client(self):
        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=self._create)))


def install_openai(monkeypatch, recorder: OpenAIRecorder) -> OpenAIRecorder:
    monkeypatch.setattr(OpenAIProvider, "_get_client", lambda self: recorder.client())
    return recorder


ALL_FOUR_BEDROCK = {
    "bill": "bedrock",
    "repair_photo": "bedrock",
    "handover_photo": "bedrock",
    "contract": "bedrock",
}
