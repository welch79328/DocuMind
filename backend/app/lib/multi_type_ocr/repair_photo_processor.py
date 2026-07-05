"""
修繕照片處理器(影像理解型)

以 VLM(多模態)理解修繕現場照片,產出瑕疵分類標籤、繁中描述與信心度;
非傳統 OCR。模糊/無法辨識時回低信心(由 gating 導入人工複核)。
支援 few-shot 注入;VLM 失敗時降級為空結果。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from .processor import ImageUnderstandingProcessor

logger = logging.getLogger(__name__)


class RepairPhotoProcessor(ImageUnderstandingProcessor):
    """修繕照片影像理解(VLM)"""

    def __init__(self, provider: Any = None):
        self._provider = provider

    async def understand(
        self,
        image_data: str,
        few_shot: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        provider = self._provider or self._default_provider()
        prompt = (
            "請辨識這張修繕/維修現場照片的瑕疵或問題,並以 JSON 回傳:\n"
            "- defect_labels: 瑕疵標籤陣列(如 漏水、壁癌、龜裂、設備損壞)\n"
            "- description: 繁體中文描述\n"
            "- confidence: 0 到 1 的信心度\n"
            "若影像模糊或無法辨識,confidence 請給低值。只回傳 JSON。"
        )
        try:
            response = await provider.call(
                prompt, image_data=image_data, few_shot=few_shot
            )
            result = self._parse_json(response)
        except Exception as e:  # VLM 不可用/失敗 → 降級
            logger.warning(f"修繕照片 VLM 理解失敗,降級為空結果: {e}")
            return {"defect_labels": [], "description": "", "confidence": 0.0}

        return {
            "defect_labels": result.get("defect_labels") or [],
            "description": result.get("description") or "",
            "confidence": self._safe_float(result.get("confidence")),
        }

    @staticmethod
    def _safe_float(value: Any) -> float:
        """安全轉換信心度(非數值 → 0.0)"""
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _default_provider():
        from app.lib.llm_service.providers import create_provider
        return create_provider()

    @staticmethod
    def _parse_json(response: str) -> Dict[str, Any]:
        try:
            match = re.search(r"\{.*\}", response, re.DOTALL)
            return json.loads(match.group(0) if match else response)
        except (json.JSONDecodeError, AttributeError):
            return {}
