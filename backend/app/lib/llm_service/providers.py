"""
LLM Provider 抽象與實作(可插拔:本地優先、雲端可選)

定義統一的 Provider 介面,支援多模態影像輸入與 few-shot 範例注入。
OpenAIProvider / AnthropicProvider 封裝既有雲端呼叫邏輯(行為不變);
LocalQwenProvider 於任務 7.2 加入;BedrockProvider(東京 Qwen3 VL,flex)於
bedrock-qwen-documind S1 加入。
Provider 由 `create_provider` 依名稱或 settings.LLM_PROVIDER 建立;四類文件
(帳單、修繕照片、點交照片、合約)的名稱來自分流表,見 `routing.py`。

每次呼叫(含重送)都記一筆 `llm_calls`(見 `call_log.py`)。
"""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union

from app.config import settings

from .call_log import classify_llm_error, record_llm_call, status_category

logger = logging.getLogger(__name__)

FewShot = Optional[List[Dict[str, Any]]]

# 每 1M token 的美元單價 (input, output);找不到時用 _DEFAULT_PRICE。
# 自架 Provider 無按量計價,一律 0.0。
_PRICING: Dict[str, tuple] = {
    # GPT-5 系列(2026-09-03 由第三方彙整站取得,**未經 OpenAI 官方頁核對**)
    "gpt-5.6-sol": (4.00, 20.00),   # 2026-09-09 對照官方定價頁更正:原填 5.00/30.00 是發表時的價,7/30 降價後未同步
    "gpt-5.6-terra": (2.00, 12.00),
    "gpt-5.6-luna": (0.20, 1.20),
    "gpt-5.5": (5.00, 30.00),
    "gpt-5.4": (2.50, 15.00),
    "gpt-5-nano": (0.05, 0.40),
    "gpt-4o-mini": (0.150, 0.600),
    "gpt-4o": (2.50, 10.00),
    "claude-opus-5": (5.00, 25.00),
    "claude-sonnet-5": (2.00, 10.00),   # 2026-09-01 更正:原填 3.00/15.00 是 Sonnet 4.6 的價
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-3-5-sonnet": (3.00, 15.00),
    "claude-3-5-haiku": (0.80, 4.00),
    # Bedrock 東京 Qwen3 VL 235B:標準等級(API 值 default)與 flex 分開計價。
    # 出處:docs/testing/bedrock-vlm-eval-20261023.md §2(AWS Price List API,
    # ap-northeast-1,2026-10-20 取得,flex 2026-10-23 再查)。
    # flex 用「<model ID>#flex」當鍵,由 _estimate_cost 先做完整比對,
    # 不會被下面的子字串比對誤配成標準價。
    "qwen.qwen3-vl-235b-a22b#flex": (0.32, 1.61),
    "qwen.qwen3-vl-235b-a22b": (0.64, 3.22),
}
_DEFAULT_PRICE = (0.150, 0.600)


def openai_call_kwargs(
    model: str,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    reasoning_effort: Optional[str] = None,
) -> Dict[str, Any]:
    """組出 OpenAI chat.completions 可接受的參數,依模型家族剔除不支援的。

    2026-09-03 換到 gpt-5.6-terra 後連續被兩個 400 擋下,每次都是同一類問題:

        Unsupported parameter: 'max_tokens' is not supported with this model.
        Use 'max_completion_tokens' instead.

        Unsupported value: 'temperature' does not support 0.0 with this model.
        Only the default (1) value is supported.

    **這類錯誤在本系統是靜默的**——降級設計會退回正則結果,HTTP 200、
    llm_pages_used=0、estimated_cost=$0,API 回應看不出 LLM 從未成功跑過。
    第一次修完 max_tokens 重跑,數字一模一樣,才發現後面還排著 temperature。
    所以這裡一次處理整類,不要再一個參數一個參數修。

    GPT-5 系列的規則:
      - 輸出上限用 `max_completion_tokens`,不是 `max_tokens`
      - `temperature` 只接受預設值 1 → **一律不傳**,讓 API 用預設

    方向刻意是「舊模型走舊行為」而非「新模型走新行為」:新模型會一直出,
    舊模型清單是封閉的。預設當成新模型,漏掉的新模型才不會壞。
    """
    legacy = model.startswith(("gpt-4", "gpt-3.5", "o1", "o3"))
    kwargs: Dict[str, Any] = {}

    if max_tokens is not None:
        kwargs["max_tokens" if legacy else "max_completion_tokens"] = max_tokens

    # 新模型不接受非預設 temperature;傳了就是 400,不傳則走預設 1
    if temperature is not None and legacy:
        kwargs["temperature"] = temperature

    # 推理強度:GPT-5 系列專屬,舊模型沒有這個參數(傳了就是 400)。
    #
    # **推理 token 按輸出計價**,而輸出單價是輸入的 6 倍(Terra $12 vs $2),
    # 所以這是不換模型也能降成本的旋鈕。GPT-5.6 預設 medium;
    # 照 schema 填值、照對照表改錯字這類機械工作用不到中等推理。
    # 值依模型而異,可為 none / minimal / low / medium / high / xhigh / max。
    if reasoning_effort and not legacy:
        kwargs["reasoning_effort"] = reasoning_effort

    return kwargs


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
    """依模型名稱比對定價(先完整比對,再比對子字串);比對不到時採最便宜級距,寧可低估也不虛報"""
    input_price, output_price = _PRICING.get(model, (None, None))
    if input_price is None:
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
        reasoning_effort: Optional[str] = None,
    ) -> str:
        """呼叫 LLM;支援影像(多模態)與 few-shot 範例注入,回傳文字。

        reasoning_effort 僅 OpenAI 的 GPT-5 系列有意義,其餘 Provider 忽略。
        """
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
        # 後備值一律讀 settings,**不要在這裡再寫一份預設值**。
        # 2026-09-03 踩過:設定改成 gpt-5.6-terra 後,這裡仍是寫死的 gpt-4o-mini,
        # 於是「create_provider 走新模型、直接 new Provider 走舊模型」——
        # 同一支程式跑兩種模型,而且不報錯。
        from app.config import settings as _settings

        self.model = model or _settings.OPENAI_MODEL
        # Provider 級的推理強度預設;個別呼叫可覆寫(校正段就是這樣做的)
        self.reasoning_effort = _settings.OPENAI_REASONING_EFFORT or None
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
        reasoning_effort: Optional[str] = None,
    ) -> str:
        full_prompt = self._build_prompt(prompt, few_shot)
        content = self._build_content(full_prompt, image_data)

        try:
            response = await self._get_client().chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": content}],
                **openai_call_kwargs(
                    self.model,
                    max_tokens,
                    temperature,
                    reasoning_effort or self.reasoning_effort,
                ),
            )
        except Exception as exc:
            record_llm_call(
                provider="openai", model=self.model, ok=False,
                error=classify_llm_error(exc),
            )
            raise
        record_llm_call(
            provider="openai", model=self.model, ok=True,
            service_tier=getattr(response, "service_tier", None),
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
        reasoning_effort: Optional[str] = None,   # Anthropic 無此參數,忽略
    ) -> str:
        full_prompt = self._build_prompt(prompt, few_shot)
        content = self._build_content(full_prompt, image_data)

        try:
            response = await self._get_client().messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": content}],
            )
        except Exception as exc:
            record_llm_call(
                provider="anthropic", model=self.model, ok=False,
                error=classify_llm_error(exc),
            )
            raise
        record_llm_call(provider="anthropic", model=self.model, ok=True)

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
        reasoning_effort: Optional[str] = None,   # 自架 vLLM 無此參數,忽略
    ) -> str:
        full_prompt = _inject_few_shot(prompt, few_shot)
        # 重用 OpenAI 相容的多模態 content 格式(vLLM 相容)
        content = OpenAIProvider._build_content(full_prompt, image_data)
        messages = [{"role": "user", "content": content}]
        try:
            result = await self._request(messages, max_tokens, temperature)
        except Exception as exc:
            record_llm_call(
                provider="local_qwen", model=self.model, ok=False,
                error=classify_llm_error(exc),
            )
            raise
        record_llm_call(provider="local_qwen", model=self.model, ok=True)
        self.stats["llm_calls"] += 1
        return result


class BedrockCallError(Exception):
    """Bedrock 呼叫失敗。**訊息只含類別與狀態碼,不含 AWS 回應內文**。

    AWS 拒絕存取的訊息可能帶 IAM ARN(安全審查 F7)。這個例外的字串會流進
    log 與回應(校正段把 str(e) 放進 stats.llm_error),所以從源頭就不帶內文。
    """

    def __init__(self, category: str, status_code: Optional[int] = None, retryable: bool = False):
        self.category = category
        self.status_code = status_code
        self.retryable = retryable
        detail = f"(HTTP {status_code})" if status_code is not None else ""
        super().__init__(f"Bedrock 呼叫失敗:{category}{detail}")


# Bedrock 單張影像上限 3.75MB(評估紀錄 §4 外部限制;超過時回「Failed to buffer」)。
# 取十進位 3,750,000 位元組,比 3.75 MiB 小,寧可提早重新編碼。
BEDROCK_MAX_IMAGE_BYTES = 3_750_000
# 超過上限時,為 Bedrock 請求以同尺寸 JPEG 重新編碼的品質(plan D-1、R7 放寬)
BEDROCK_REENCODE_JPEG_QUALITY = 92
# 單次請求的逾時(秒)。flex 失敗只再送一次 default,最壞情況一次呼叫約 2 倍;
# 線上 nginx 讀取逾時 600 秒,單 worker,不能讓一次呼叫無限等(SR-9)。
BEDROCK_TIMEOUT_SECONDS = 90.0
# 這三種失敗才改用標準等級重送一次(R2、D-3);其他錯誤不重送
_BEDROCK_RETRYABLE_STATUS = (429, 503)
_BEDROCK_FORBIDDEN_MODEL_PREFIXES = ("jp.", "global.")


def check_bedrock_model(model: Optional[str]) -> str:
    """model ID 檢查:不得為空;帶 `jp.`／`global.` 前綴即報錯。

    這兩種是跨區推論設定檔,請求會被送到東京以外的區域處理(jp. 含大阪、
    global. 可能離開日本,評估紀錄 §4)。區域鎖在東京(SR-7),所以直接拒絕,
    不嘗試替換成單區 ID——換掉等於替設定者決定模型。
    """
    model = (model or "").strip()
    if not model:
        raise ValueError("BEDROCK_MODEL 未設定")
    if model.lower().startswith(_BEDROCK_FORBIDDEN_MODEL_PREFIXES):
        raise ValueError(
            f"Bedrock model ID「{model}」是跨區推論設定檔(jp./global.),"
            "資料可能離開東京區;只接受單區 model ID"
        )
    return model


def _base64_decoded_length(b64: str) -> int:
    """不解碼就算出 base64 內容的位元組數"""
    b64 = b64.strip()
    padding = len(b64) - len(b64.rstrip("="))
    return (len(b64) * 3) // 4 - padding


class BedrockProvider(LLMProvider):
    """Bedrock 東京 OpenAI 相容端點(Qwen3 VL 235B),每次呼叫先送 flex。

    - 端點與區域寫死東京 ap-northeast-1,不開放設定(SR-7)。
    - 金鑰只從 settings.BEDROCK_API_KEY 讀,呼叫當下才取,不存成屬性、不印出。
    - 建構子自己檢查 LLM_CLOUD_ENABLED(SR-2):直接 new 這個類別也繞不過守衛。
    - flex 遇 429、503、逾時,同模型同區改 `default` 重送一次;仍失敗就拋出,
      由呼叫端走既有降級。**絕不改送 OpenAI**(R2、SR-3)。
    - 用 httpx 直接打,不經 OpenAI SDK:SDK 預設會自己重試兩次,
      重試次數就不是這裡說了算(SR-9)。httpx 不會自動重試。
    - 影像與 openai 路由送的完全相同;只有超過 3.75MB 才為這個請求以同尺寸
      JPEG 品質 92 重新編碼(D-1、R7)。
    """

    ENDPOINT = "https://bedrock-runtime.ap-northeast-1.amazonaws.com/openai/v1"
    # 測試注入 httpx.MockTransport 用;正式環境為 None(httpx 預設傳輸)
    _transport = None

    def __init__(self, model: Optional[str] = None):
        if not settings.LLM_CLOUD_ENABLED:
            raise ValueError(
                "雲端 Provider「bedrock」已停用(LLM_CLOUD_ENABLED=false),個資不外送"
            )
        self.model = check_bedrock_model(model or settings.BEDROCK_MODEL)
        self.stats = _new_stats()

    # -- 組裝 ------------------------------------------------------------- #
    @staticmethod
    def _prepare_content(
        prompt: str, image_data: Optional[str]
    ) -> Union[str, List[Dict[str, Any]]]:
        """與 OpenAIProvider 相同的多模態格式;影像超過上限時才重新編碼。"""
        content = OpenAIProvider._build_content(prompt, image_data)
        if not isinstance(content, list):
            return content

        url = content[1]["image_url"]["url"]
        header, _, b64 = url.partition(",")
        if _base64_decoded_length(b64) <= BEDROCK_MAX_IMAGE_BYTES:
            return content

        import base64
        import io

        from PIL import Image

        image = Image.open(io.BytesIO(base64.b64decode(b64)))
        image.load()
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=BEDROCK_REENCODE_JPEG_QUALITY)
        data = buf.getvalue()
        if len(data) > BEDROCK_MAX_IMAGE_BYTES:
            # 不縮尺寸:R7 要求送 Bedrock 的影像與 openai 路由同尺寸
            raise BedrockCallError("image_too_large")
        logger.info(
            "影像超過 Bedrock 單張上限,已為 Bedrock 請求以同尺寸 JPEG 重新編碼:%dx%d,%d → %d 位元組",
            image.size[0], image.size[1], _base64_decoded_length(b64), len(data),
        )
        new_url = "data:image/jpeg;base64," + base64.b64encode(data).decode("ascii")
        return [content[0], {"type": "image_url", "image_url": {"url": new_url}}]

    @staticmethod
    def _api_key() -> str:
        secret = settings.BEDROCK_API_KEY
        value = secret.get_secret_value() if secret is not None else ""
        if not value:
            raise BedrockCallError("missing_credentials")
        return value

    # -- 呼叫 ------------------------------------------------------------- #
    async def _post(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """送一次請求;失敗一律轉成只帶類別的 BedrockCallError。"""
        import asyncio

        import httpx

        headers = {"Authorization": f"Bearer {self._api_key()}"}
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(BEDROCK_TIMEOUT_SECONDS, connect=10.0),
                transport=self._transport,
            ) as client:
                response = await asyncio.wait_for(
                    client.post(
                        f"{self.ENDPOINT}/chat/completions", json=payload, headers=headers
                    ),
                    timeout=BEDROCK_TIMEOUT_SECONDS,
                )
        except (httpx.TimeoutException, asyncio.TimeoutError):
            raise BedrockCallError("timeout", retryable=True) from None
        except httpx.HTTPError:
            raise BedrockCallError("connection_error") from None

        if response.status_code != 200:
            # 只留狀態碼;回應內文(可能含 ARN)不讀、不記
            raise BedrockCallError(
                status_category(response.status_code),
                status_code=response.status_code,
                retryable=response.status_code in _BEDROCK_RETRYABLE_STATUS,
            ) from None
        try:
            data = response.json()
            data["choices"][0]["message"]
        except Exception:
            raise BedrockCallError("invalid_response") from None
        return data

    async def _attempt(self, payload: Dict[str, Any], tier: str) -> Dict[str, Any]:
        try:
            data = await self._post({**payload, "service_tier": tier})
        except BedrockCallError as exc:
            record_llm_call(
                provider="bedrock", model=self.model, ok=False,
                requested_service_tier=tier, error=exc.category,
            )
            raise
        record_llm_call(
            provider="bedrock", model=self.model, ok=True,
            requested_service_tier=tier, service_tier=data.get("service_tier"),
        )
        return data

    async def call(
        self,
        prompt: str,
        image_data: Optional[str] = None,
        few_shot: FewShot = None,
        max_tokens: int = 2048,
        temperature: float = 0.0,
        reasoning_effort: Optional[str] = None,   # Bedrock 無此參數,忽略
    ) -> str:
        full_prompt = _inject_few_shot(prompt, few_shot)
        try:
            content = self._prepare_content(full_prompt, image_data)
        except BedrockCallError as exc:
            record_llm_call(
                provider="bedrock", model=self.model, ok=False, error=exc.category,
            )
            raise

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": content}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        requested = "flex"
        try:
            data = await self._attempt(payload, requested)
        except BedrockCallError as exc:
            if not exc.retryable:
                raise
            logger.warning("Bedrock flex 失敗(%s),改用標準等級 default 重送一次", exc.category)
            requested = "default"
            data = await self._attempt(payload, requested)

        self.stats["llm_calls"] += 1
        usage = data.get("usage") or {}
        prompt_tokens = int(usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("completion_tokens") or 0)
        self.stats["tokens_used"] += int(usage.get("total_tokens") or (prompt_tokens + completion_tokens))
        self.stats["prompt_tokens"] += prompt_tokens
        self.stats["completion_tokens"] += completion_tokens
        # 依 API 實際回報的等級計價;回應沒標時以送出時要求的等級計
        tier = data.get("service_tier") or requested
        priced_model = f"{self.model}#flex" if tier == "flex" else self.model
        self.stats["estimated_cost"] += _estimate_cost(
            priced_model, prompt_tokens, completion_tokens
        )

        return data["choices"][0]["message"].get("content") or ""


# 雲端 Provider(個資會外送);LLM_CLOUD_ENABLED=false 時禁止載入
CLOUD_PROVIDERS = {"openai", "anthropic", "bedrock"}


def create_provider(
    provider_name: Optional[str] = None,
    *,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
) -> LLMProvider:
    """
    依名稱(或 settings.LLM_PROVIDER)建立 Provider。

    隱私守衛:當 settings.LLM_CLOUD_ENABLED=false 時,禁止載入雲端 Provider,
    確保個資不外送(本地 Provider 不受限)。BedrockProvider 的建構子另外再檢查一次。
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

    if name == "bedrock":
        # 金鑰只從 settings 讀;呼叫端帶進來的 api_key 不接受,避免金鑰從別的路徑流入
        if api_key is not None:
            raise ValueError("Bedrock 金鑰只從設定 BEDROCK_API_KEY 讀取,不接受呼叫端傳入")
        return BedrockProvider(model=model)

    if name == "local_qwen":
        return LocalQwenProvider(
            endpoint=settings.LOCAL_QWEN_ENDPOINT, model=model, api_key=api_key
        )

    raise ValueError(f"不支援或未啟用的 LLM Provider: {name}")
