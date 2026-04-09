"""
LLM Service Core

統一的 LLM 服務層，管理多個提供商的客戶端並提供通用調用介面
"""

import os
import logging
from typing import Optional, Dict, Any, Union, List
from .types import LLMProvider, LLMStats

logger = logging.getLogger(__name__)


class LLMService:
    """
    統一 LLM 服務

    管理 OpenAI/Anthropic 客戶端，提供統一的調用介面，
    支援文字修正、結構化提取等多種任務。

    使用範例:
        # 初始化服務
        service = LLMService(provider="openai")

        # 文字修正
        corrected = await service.text_correction(
            text="OCR 辨識錯誤的文字",
            context="這是一份合約文件"
        )

        # 結構化提取
        fields = await service.structured_extraction(
            text="合約文字內容",
            image_data="base64_image_data",
            schema={"contract_number": "合約編號", ...}
        )
    """

    def __init__(
        self,
        provider: LLMProvider = "openai",
        model: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        """
        初始化 LLM 服務

        Args:
            provider: LLM 提供商 (openai/anthropic)
            model: 模型名稱，None 使用預設模型
            api_key: API 金鑰，None 從環境變數讀取
        """
        self.provider = provider
        self.api_key = api_key or self._get_api_key()
        self.model = model or self._get_default_model()

        # 客戶端（延遲初始化）
        self._client = None
        self._async_client = None

        # 統計資料
        self.stats: LLMStats = {
            "llm_calls": 0,
            "tokens_used": 0,
            "estimated_cost": 0.0
        }

        logger.info(f"LLMService 初始化: provider={provider}, model={self.model}")

    def _get_api_key(self) -> str:
        """從環境變數獲取 API 金鑰"""
        if self.provider == "openai":
            key = os.getenv("OPENAI_API_KEY")
            if not key:
                raise ValueError("OPENAI_API_KEY 環境變數未設定")
            return key
        elif self.provider == "anthropic":
            key = os.getenv("ANTHROPIC_API_KEY")
            if not key:
                raise ValueError("ANTHROPIC_API_KEY 環境變數未設定")
            return key
        else:
            raise ValueError(f"不支援的提供商: {self.provider}")

    def _get_default_model(self) -> str:
        """獲取預設模型"""
        if self.provider == "openai":
            return "gpt-4o"  # 支援視覺，準確率高
        elif self.provider == "anthropic":
            return "claude-3-5-haiku-20241022"  # 快速且便宜
        return ""

    @property
    def client(self):
        """獲取同步客戶端（延遲初始化）"""
        if self._client is None:
            self._client = self._init_client(async_client=False)
        return self._client

    @property
    def async_client(self):
        """獲取非同步客戶端（延遲初始化）"""
        if self._async_client is None:
            self._async_client = self._init_client(async_client=True)
        return self._async_client

    def _init_client(self, async_client: bool = False):
        """
        初始化 LLM 客戶端

        Args:
            async_client: 是否初始化非同步客戶端

        Returns:
            OpenAI 或 Anthropic 客戶端實例
        """
        try:
            if self.provider == "openai":
                if async_client:
                    from openai import AsyncOpenAI
                    return AsyncOpenAI(api_key=self.api_key)
                else:
                    from openai import OpenAI
                    return OpenAI(api_key=self.api_key)

            elif self.provider == "anthropic":
                if async_client:
                    from anthropic import AsyncAnthropic
                    return AsyncAnthropic(api_key=self.api_key)
                else:
                    from anthropic import Anthropic
                    return Anthropic(api_key=self.api_key)

        except ImportError as e:
            pkg = "openai" if self.provider == "openai" else "anthropic"
            raise ImportError(f"請安裝 {pkg} SDK: pip install {pkg}") from e

    async def call(
        self,
        prompt: str,
        image_data: Optional[str] = None,
        max_tokens: int = 2000,
        temperature: float = 0.1
    ) -> str:
        """
        通用 LLM 調用方法

        Args:
            prompt: 提示詞
            image_data: base64 編碼的圖像資料（可選，用於圖像分析任務）
            max_tokens: 最大輸出 token 數
            temperature: 溫度參數 (0.0-1.0)

        Returns:
            LLM 回應文字

        Raises:
            Exception: LLM 調用失敗時拋出異常
        """
        self.stats["llm_calls"] += 1

        try:
            if self.provider == "openai":
                return await self._call_openai(prompt, image_data, max_tokens, temperature)
            elif self.provider == "anthropic":
                return await self._call_anthropic(prompt, image_data, max_tokens, temperature)
            else:
                raise ValueError(f"不支援的提供商: {self.provider}")

        except Exception as e:
            logger.error(f"LLM 調用失敗: {str(e)}", exc_info=True)
            raise

    async def _call_openai(
        self,
        prompt: str,
        image_data: Optional[str],
        max_tokens: int,
        temperature: float
    ) -> str:
        """調用 OpenAI API"""
        # 構建消息內容
        if image_data:
            # 確保 image_data 格式正確
            if not image_data.startswith("data:image"):
                image_data = f"data:image/png;base64,{image_data}"

            content: Union[str, List[Dict[str, Any]]] = [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": image_data}
                }
            ]
        else:
            content = prompt

        # 調用 API
        response = await self.async_client.chat.completions.create(
            model=self.model,
            messages=[{
                "role": "user",
                "content": content
            }],
            max_tokens=max_tokens,
            temperature=temperature
        )

        # 更新統計
        self.stats["tokens_used"] += response.usage.total_tokens

        # 計算成本
        if "gpt-4o-mini" in self.model:
            input_cost, output_cost = 0.150, 0.600
        elif "gpt-4o" in self.model:
            input_cost, output_cost = 2.50, 10.00
        else:
            input_cost, output_cost = 0.150, 0.600

        cost = (
            response.usage.prompt_tokens * input_cost / 1_000_000 +
            response.usage.completion_tokens * output_cost / 1_000_000
        )
        self.stats["estimated_cost"] += cost

        logger.debug(
            f"OpenAI 調用完成: tokens={response.usage.total_tokens}, "
            f"cost=${cost:.4f}"
        )

        return response.choices[0].message.content or ""

    async def _call_anthropic(
        self,
        prompt: str,
        image_data: Optional[str],
        max_tokens: int,
        temperature: float
    ) -> str:
        """調用 Anthropic API"""
        # 構建消息內容
        if image_data:
            content: Union[str, List[Dict[str, Any]]] = [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": image_data.replace("data:image/png;base64,", "")
                    }
                },
                {"type": "text", "text": prompt}
            ]
        else:
            content = prompt

        # 調用 API
        response = await self.async_client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{
                "role": "user",
                "content": content
            }]
        )

        # 更新統計
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        self.stats["tokens_used"] += input_tokens + output_tokens

        # 計算成本 (Haiku: $0.25/1M input, $1.25/1M output)
        cost = (
            input_tokens * 0.25 / 1_000_000 +
            output_tokens * 1.25 / 1_000_000
        )
        self.stats["estimated_cost"] += cost

        logger.debug(
            f"Anthropic 調用完成: tokens={input_tokens + output_tokens}, "
            f"cost=${cost:.4f}"
        )

        return response.content[0].text

    async def text_correction(
        self,
        text: str,
        context: str = "文件",
        image_data: Optional[str] = None
    ) -> str:
        """
        文字修正任務

        使用 LLM 修正 OCR 辨識錯誤

        Args:
            text: 待修正的文字
            context: 文件上下文描述（例如：謄本、合約）
            image_data: 原始圖像資料（可選，提供可提升準確率）

        Returns:
            修正後的文字
        """
        prompt = f"""請修正以下 OCR 辨識的錯誤文字。

文件類型: {context}

【修正原則】
1. 只修正明顯的 OCR 錯誤
2. 保持原文的所有內容、格式、換行
3. 無法確定的文字保持原樣
4. 不要過度解讀或改寫

【要修正的文字】
{text}

請直接輸出修正後的文字，不要添加任何解釋。"""

        return await self.call(
            prompt=prompt,
            image_data=image_data,
            max_tokens=3000,
            temperature=0.1
        )

    async def structured_extraction(
        self,
        text: str,
        image_data: Optional[str],
        schema: Dict[str, str],
        context: str = "文件"
    ) -> Dict[str, Optional[str]]:
        """
        結構化欄位提取任務

        使用 LLM Vision 從文件中提取結構化欄位

        Args:
            text: OCR 辨識的文字（作為上下文）
            image_data: base64 編碼的圖像資料
            schema: 欄位定義，格式為 {field_name: field_description}
            context: 文件類型描述

        Returns:
            提取的欄位字典，格式為 {field_name: value}

        Raises:
            ValueError: schema 為空或 image_data 未提供時拋出異常
        """
        if not schema:
            raise ValueError("schema 不能為空")
        if not image_data:
            raise ValueError("structured_extraction 需要提供 image_data")

        # 構建欄位列表
        field_list = "\n".join([
            f"{i+1}. {name}: {desc}"
            for i, (name, desc) in enumerate(schema.items())
        ])

        # 構建 JSON 模板
        json_template = "{\n" + ",\n".join([
            f'  "{name}": "值或null"'
            for name in schema.keys()
        ]) + "\n}"

        prompt = f"""請從這份{context}圖像中提取以下關鍵欄位，並以 JSON 格式返回。

如果某個欄位在文件中不存在，請返回 null。

OCR 辨識文字（可作為參考）：
```
{text[:500]}
```

請提取的欄位：
{field_list}

請嚴格按照以下 JSON 格式返回：
```json
{json_template}
```

請只返回 JSON，不要包含其他說明文字。"""

        response = await self.call(
            prompt=prompt,
            image_data=image_data,
            max_tokens=1000,
            temperature=0.1
        )

        # 解析 JSON 回應
        return self._parse_json_response(response)

    def _parse_json_response(self, response: str) -> Dict[str, Optional[str]]:
        """
        解析 LLM 回應中的 JSON

        Args:
            response: LLM 回應文字

        Returns:
            解析後的字典

        Raises:
            ValueError: JSON 解析失敗時拋出異常
        """
        import json
        import re

        try:
            # 提取 JSON 部分（可能包含在 ```json ``` 標記中）
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 尋找第一個 { 和最後一個 }
                start = response.find('{')
                end = response.rfind('}') + 1
                if start != -1 and end != 0:
                    json_str = response[start:end]
                else:
                    json_str = response

            fields = json.loads(json_str)

            # 將 "null" 字串和空字串統一為 None
            for key, value in fields.items():
                if value == "null" or value == "":
                    fields[key] = None

            logger.debug(f"成功解析 LLM JSON 回應: {len(fields)} 個欄位")

            return fields

        except json.JSONDecodeError as e:
            logger.error(f"LLM 回應 JSON 解析失敗: {str(e)}\n回應內容: {response[:200]}")
            raise ValueError(f"LLM 回應格式錯誤: {str(e)}") from e

    def get_stats(self) -> LLMStats:
        """獲取統計資料副本"""
        return self.stats.copy()

    def reset_stats(self):
        """重置統計資料"""
        self.stats = {
            "llm_calls": 0,
            "tokens_used": 0,
            "estimated_cost": 0.0
        }
        logger.info("LLM 統計資料已重置")
