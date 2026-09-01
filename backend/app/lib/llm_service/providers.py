"""
LLM Provider 抽象與實作(可插拔:本地優先、雲端可選)

定義統一的 Provider 介面,支援多模態影像輸入與 few-shot 範例注入。
OpenAIProvider / AnthropicProvider 封裝既有雲端呼叫邏輯(行為不變);
LocalQwenProvider 於任務 7.2 加入。
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

# 每 1M token 的美元單價 (input, output);找不到時用 _DEFAULT_PRICE。
# 自架 Provider 無按量計價,一律 0.0。
_PRICING: Dict[str, tuple] = {
    "gpt-4o-mini": (0.150, 0.600),
    "gpt-4o": (2.50, 10.00),
    "claude-opus-5": (5.00, 25.00),
    "claude-sonnet-5": (2.00, 10.00),   # 2026-09-01 更正:原填 3.00/15.00 是 Sonnet 4.6 的價
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-3-5-sonnet": (3.00, 15.00),
    "claude-3-5-haiku": (0.80, 4.00),
}
_DEFAULT_PRICE = (0.150, 0.600)


def _new_stats() -> Dict[str, Any]:
    """Provider 統計的統一形狀;estimated_cost 供既有成本紀錄沿用"""
    return {
        "llm_calls": 0,
        "tokens_used": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "estimated_cost": 0.0,
    }


def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """依模型名稱前綴比對定價;比對不到時採最便宜級距,寧可低估也不虛報"""
    input_price, output_price = _DEFAULT_PRICE
    for key, price in _PRICING.items():
        if key in model:
            input_price, output_price = price
            break
    return (
        prompt_tokens * input_price / 1_000_000
        + completion_tokens * output_price / 1_000_000
    )


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
        self.model = model or "gpt-4o-mini"   # 與 settings.OPENAI_MODEL 一致(2026-09-01 統一)
        self._api_key = api_key
        self._client = None
        self.stats = _new_stats()

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
        usage = getattr(response, "usage", None)
        if usage:
            prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
            completion_tokens = getattr(usage, "completion_tokens", 0) or 0
            self.stats["tokens_used"] += usage.total_tokens
            self.stats["prompt_tokens"] += prompt_tokens
            self.stats["completion_tokens"] += completion_tokens
            self.stats["estimated_cost"] += _estimate_cost(
                self.model, prompt_tokens, completion_tokens
            )

        return response.choices[0].message.content or ""


class AnthropicProvider(LLMProvider):
    """Anthropic(雲端)Provider — 封裝既有 Anthropic 呼叫邏輯

    影像走 base64 content block;訊息組裝與遷移前的 LLMService._call_anthropic 一致。
    """

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        self.model = model or "claude-3-5-haiku-20241022"
        self._api_key = api_key
        self._client = None
        self.stats = _new_stats()

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
        # Anthropic 的 base64 image block 只吃裸 base64,須剝掉 data URI 前綴
        raw = image_data.split("base64,", 1)[-1]
        return [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": raw,
                },
            },
            {"type": "text", "text": prompt},
        ]

    def _get_client(self):
        if self._client is None:
            from anthropic import AsyncAnthropic
            self._client = AsyncAnthropic(
                api_key=self._api_key or os.getenv("ANTHROPIC_API_KEY")
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

        response = await self._get_client().messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": content}],
        )

        self.stats["llm_calls"] += 1
        usage = getattr(response, "usage", None)
        if usage:
            prompt_tokens = getattr(usage, "input_tokens", 0) or 0
            completion_tokens = getattr(usage, "output_tokens", 0) or 0
            self.stats["tokens_used"] += prompt_tokens + completion_tokens
            self.stats["prompt_tokens"] += prompt_tokens
            self.stats["completion_tokens"] += completion_tokens
            self.stats["estimated_cost"] += _estimate_cost(
                self.model, prompt_tokens, completion_tokens
            )

        return response.content[0].text


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
        self.stats = _new_stats()

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
        self.stats["prompt_tokens"] += int(usage.get("prompt_tokens", 0))
        self.stats["completion_tokens"] += int(usage.get("completion_tokens", 0))
        # 自架推論無按量計價,estimated_cost 維持 0.0(硬體成本不在此統計)
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

    if name == "anthropic":
        return AnthropicProvider(
            model=model or settings.ANTHROPIC_MODEL, api_key=api_key
        )

    if name == "local_qwen":
        return LocalQwenProvider(
            endpoint=settings.LOCAL_QWEN_ENDPOINT, model=model, api_key=api_key
        )

    raise ValueError(f"不支援或未啟用的 LLM Provider: {name}")
