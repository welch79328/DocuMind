"""
LLM Provider 抽象與實作(可插拔:本地優先、雲端可選)

定義統一的 Provider 介面,支援多模態影像輸入與 few-shot 範例注入。
OpenAIProvider 封裝既有 OpenAI 呼叫邏輯(行為不變);LocalQwenProvider 於任務 7.2 加入。
Provider 由 `create_provider` 依 settings.LLM_PROVIDER 建立。
"""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union

from app.config import settings

logger = logging.getLogger(__name__)

FewShot = Optional[List[Dict[str, Any]]]


class LLMProvider(ABC):
    """LLM Provider 統一介面"""

    @abstractmethod
    async def call(
        self,
        prompt: str,
        image_data: Optional[str] = None,
        few_shot: FewShot = None,
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> str:
        """呼叫 LLM;支援影像(多模態)與 few-shot 範例注入,回傳文字。"""
        raise NotImplementedError


def _inject_few_shot(prompt: str, few_shot: FewShot) -> str:
    """將 few-shot 範例注入提示詞前段(不改模型,純提示組裝)"""
    if not few_shot:
        return prompt
    blocks: List[str] = []
    for i, example in enumerate(few_shot, start=1):
        ref = example.get("input_ref", "")
        fields = example.get("corrected_fields", {})
        blocks.append(
            f"範例 {i}:\n"
            f"輸入摘要:{ref}\n"
            f"正確欄位:{json.dumps(fields, ensure_ascii=False)}"
        )
    examples = "\n\n".join(blocks)
    return f"【參考範例】\n{examples}\n\n【本次任務】\n{prompt}"


class OpenAIProvider(LLMProvider):
    """OpenAI(雲端)Provider — 封裝既有 OpenAI 呼叫邏輯"""

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        self.model = model or "gpt-4o"
        self._api_key = api_key
        self._client = None
        self.stats = {"llm_calls": 0, "tokens_used": 0}

    # -- 純組裝方法(可獨立測試,不觸發 API) -------------------------------- #
    @staticmethod
    def _build_prompt(prompt: str, few_shot: FewShot) -> str:
        return _inject_few_shot(prompt, few_shot)

    @staticmethod
    def _build_content(
        prompt: str, image_data: Optional[str]
    ) -> Union[str, List[Dict[str, Any]]]:
        if not image_data:
            return prompt
        if not image_data.startswith("data:image"):
            image_data = f"data:image/png;base64,{image_data}"
        return [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": image_data}},
        ]

    def _get_client(self):
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(
                api_key=self._api_key or os.getenv("OPENAI_API_KEY")
            )
        return self._client

    # -- 呼叫 ------------------------------------------------------------- #
    async def call(
        self,
        prompt: str,
        image_data: Optional[str] = None,
        few_shot: FewShot = None,
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> str:
        full_prompt = self._build_prompt(prompt, few_shot)
        content = self._build_content(full_prompt, image_data)

        response = await self._get_client().chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": content}],
            max_tokens=max_tokens,
            temperature=temperature,
        )

        self.stats["llm_calls"] += 1
        if getattr(response, "usage", None):
            self.stats["tokens_used"] += response.usage.total_tokens

        return response.choices[0].message.content or ""


class LocalQwenProvider(LLMProvider):
    """本地 / 自架(EC2)Qwen Provider — 對接 vLLM 的 OpenAI 相容端點,個資不外送"""

    def __init__(
        self,
        endpoint: str,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        if not endpoint:
            raise ValueError("LOCAL_QWEN_ENDPOINT 未設定,無法建立本地 Qwen Provider")
        self.endpoint = endpoint.rstrip("/")
        self.model = model or "Qwen2-VL-7B-Instruct"
        self._api_key = api_key
        self.stats = {"llm_calls": 0, "tokens_used": 0}

    async def _request(
        self, messages: List[Dict[str, Any]], max_tokens: int, temperature: float
    ) -> str:
        """POST 至 vLLM 的 OpenAI 相容端點並取回文字"""
        import httpx

        url = f"{self.endpoint}/v1/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        usage = data.get("usage") or {}
        self.stats["tokens_used"] += int(usage.get("total_tokens", 0))
        return data["choices"][0]["message"]["content"] or ""

    async def call(
        self,
        prompt: str,
        image_data: Optional[str] = None,
        few_shot: FewShot = None,
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> str:
        full_prompt = _inject_few_shot(prompt, few_shot)
        # 重用 OpenAI 相容的多模態 content 格式(vLLM 相容)
        content = OpenAIProvider._build_content(full_prompt, image_data)
        messages = [{"role": "user", "content": content}]
        result = await self._request(messages, max_tokens, temperature)
        self.stats["llm_calls"] += 1
        return result


# 雲端 Provider(個資會外送);LLM_CLOUD_ENABLED=false 時禁止載入
CLOUD_PROVIDERS = {"openai", "anthropic"}


def create_provider(
    provider_name: Optional[str] = None,
    *,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
) -> LLMProvider:
    """
    依名稱(或 settings.LLM_PROVIDER)建立 Provider。

    隱私守衛:當 settings.LLM_CLOUD_ENABLED=false 時,禁止載入雲端 Provider,
    確保個資不外送(本地 Provider 不受限)。
    """
    name = (provider_name or settings.LLM_PROVIDER or "openai").lower()

    if name in CLOUD_PROVIDERS and not settings.LLM_CLOUD_ENABLED:
        raise ValueError(
            f"雲端 Provider「{name}」已停用(LLM_CLOUD_ENABLED=false),個資不外送"
        )

    if name == "openai":
        return OpenAIProvider(model=model or settings.OPENAI_MODEL, api_key=api_key)

    if name == "local_qwen":
        return LocalQwenProvider(
            endpoint=settings.LOCAL_QWEN_ENDPOINT, model=model, api_key=api_key
        )

    raise ValueError(f"不支援或未啟用的 LLM Provider: {name}")
