"""
規則欄位抽取基類(共用)

提供「規則正則抽取 → 每欄位信心度 → 低信心以 LLM Vision(注入 few-shot)補齊 →
標記需人工確認」的共用流程。各文件類型(謄本/帳單)只需宣告 PATTERNS / KEY_FIELDS /
欄位標籤與文件描述即可。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Pattern

from app.config import settings

logger = logging.getLogger(__name__)


def _first_captured_group(match) -> Optional[str]:
    """取第一個有值的擷取群組;全部為空時回傳 None。

    原本寫死 `match.group(1)`,交替樣式(`A|B`)只要命中第二個分支,
    group(1) 就是 None,`.strip()` 直接拋 AttributeError。

    2026-09-03 需要交替樣式的理由:真實謄本的地號寫成
    `竹田鄉過溝段0555-0000地號`——**值在標籤前面**,而少數表格式版型是標籤在前。
    兩種順序都要收,就必然用到交替群組。
    """
    if match is None:
        return None
    for value in match.groups():
        if value is not None and str(value).strip():
            return str(value).strip()
    return None



class RegexFieldExtractor:
    """規則 + LLM Vision 欄位抽取基類"""

    PATTERNS: Dict[str, Pattern] = {}
    KEY_FIELDS: tuple = ()
    FIELD_LABELS: Dict[str, str] = {}   # 欄位英文名 → 中文標籤(供 LLM 提示)
    DOC_LABEL: str = "文件"

    _MATCH_CONFIDENCE = 0.9
    _LLM_CONFIDENCE = 0.8

    def __init__(self, threshold: Optional[float] = None, provider: Any = None):
        self.threshold = (
            threshold if threshold is not None else settings.OCR_QUALITY_THRESHOLD
        )
        self._provider = provider

    async def extract(
        self,
        text: str,
        image_data: Optional[str] = None,
        use_llm_fallback: bool = False,
        few_shot: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        fields, confidences = self._extract_with_regex(text)
        needs = [k for k in self.KEY_FIELDS if confidences[k] < self.threshold]

        llm_used = False
        if use_llm_fallback and needs and image_data:
            llm_fields = await self._extract_with_llm(text, image_data, needs, few_shot)
            for key, value in llm_fields.items():
                if key in self.KEY_FIELDS and value:
                    fields[key] = value
                    confidences[key] = self._LLM_CONFIDENCE
            needs = [k for k in self.KEY_FIELDS if confidences[k] < self.threshold]
            llm_used = True

        return {
            **fields,
            "field_confidences": confidences,
            "needs_confirmation": needs,
            "extraction_confidence": round(
                sum(confidences.values()) / len(confidences), 4
            ) if confidences else 0.0,
            "llm_used_for_extraction": llm_used,
        }

    # ------------------------------------------------------------------ #
    def _extract_with_regex(self, text: str):
        fields: Dict[str, Any] = {}
        confidences: Dict[str, float] = {}
        for key in self.KEY_FIELDS:
            pattern = self.PATTERNS.get(key)
            match = pattern.search(text or "") if pattern else None
            captured = _first_captured_group(match)
            if captured is not None:
                fields[key] = captured
                confidences[key] = self._MATCH_CONFIDENCE
            else:
                fields[key] = None
                confidences[key] = 0.0
        return fields, confidences

    async def _extract_with_llm(
        self,
        text: str,
        image_data: str,
        needs: List[str],
        few_shot: Optional[List[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        provider = self._provider or self._default_provider()
        labels = "、".join(f"{k}={self.FIELD_LABELS.get(k, k)}" for k in needs)
        prompt = (
            f"請從這份{self.DOC_LABEL}圖像中提取以下欄位並以 JSON 回傳:{labels}。\n"
            f"OCR 參考文字:\n{text[:500]}\n"
            f"若欄位不存在請回傳 null。只回傳 JSON。"
        )
        try:
            response = await provider.call(
                prompt, image_data=image_data, few_shot=few_shot
            )
            return self._parse_json(response)
        except Exception as e:  # pragma: no cover - LLM 失敗降級
            logger.warning(f"{self.DOC_LABEL} LLM 欄位抽取失敗,降級為規則結果: {e}")
            return {}

    @staticmethod
    def _default_provider():
        from app.lib.llm_service.providers import create_provider
        return create_provider()

    @staticmethod
    def _parse_json(response: str) -> Dict[str, Any]:
        try:
            match = re.search(r"\{.*\}", response, re.DOTALL)
            data = json.loads(match.group(0) if match else response)
            return {k: (None if v in ("null", "") else v) for k, v in data.items()}
        except (json.JSONDecodeError, AttributeError):
            return {}
