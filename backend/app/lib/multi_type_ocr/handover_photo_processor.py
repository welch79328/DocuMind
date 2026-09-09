"""
點交照片處理器(影像理解型)

以 VLM 理解租賃點交現場照片,判定空間並辨識家具家電;非傳統 OCR。
與 `RepairPhotoProcessor` 的差別只有兩點:提示詞問的是「有什麼」而不是
「壞在哪」,以及**輸出必須先過詞彙白名單**。

為什麼要過白名單:下游 jgb2 的點交清單只認得
`handover_vocabulary` 那 94 個品項 key 與 7 個空間 key。模型回
「電冰箱」「單人床架」這種自由文字,清單那端對不上,使用者還是得手動
重打一次。所以認不出來的一律丟棄——**寧可漏報,不可誤報**:
憑空多出一個品項比少一個更難被發現,而點交清單是有法律效力的文件。

被丟掉的詞會留在 `dropped` 欄位。那不是給使用者看的,是給我們看的:
同一個詞反覆出現在 dropped,代表詞彙表該補,或提示詞沒把清單餵好。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from app.lib.handover_vocabulary import (
    ITEMS,
    SPACES,
    category_of,
    normalize_item,
    normalize_space,
    prompt_vocabulary,
)

from .processor import ImageUnderstandingProcessor

logger = logging.getLogger(__name__)

# 影像模糊或空房時的降級結果。四個鍵都要在,呼叫端才不必到處防 None。
_EMPTY: Dict[str, Any] = {
    "space": None,
    "space_label": "",
    "furniture": [],
    "appliance": [],
    "description": "",
    "confidence": 0.0,
    "dropped": [],
    "field_confidences": {},
}


class HandoverPhotoProcessor(ImageUnderstandingProcessor):
    """點交照片影像理解(VLM)+ 詞彙白名單過濾"""

    def __init__(self, provider: Any = None):
        self._provider = provider

    async def understand(
        self,
        image_data: str,
        few_shot: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        provider = self._provider or self._default_provider()
        prompt = self._build_prompt()
        try:
            response = await provider.call(
                prompt, image_data=image_data, few_shot=few_shot
            )
            result = self._parse_json(response)
        except Exception as e:  # VLM 不可用/失敗 → 降級,不讓整批中斷
            logger.warning(f"點交照片 VLM 理解失敗,降級為空結果: {e}")
            return dict(_EMPTY)

        return self._to_vocabulary(result)

    # ------------------------------------------------------------------ #

    @staticmethod
    def _build_prompt() -> str:
        """組提示詞。詞彙清單每次都重新產生,詞彙表改了提示詞就跟著改。"""
        return (
            "請辨識這張租賃點交現場照片,並以 JSON 回傳:\n"
            "- space: 這張照片拍的是哪個空間\n"
            "- furniture: 看到的傢俱名稱陣列\n"
            "- appliance: 看到的家電名稱陣列\n"
            "- description: 繁體中文描述\n"
            "- confidence: 0 到 1 的信心度\n"
            "\n"
            "**只能使用下列詞彙,不要自創名稱、不要加形容詞:**\n"
            f"{prompt_vocabulary()}\n"
            "\n"
            "清單上沒有的東西不要回報。若是空房、只拍到牆面地板,"
            "或影像模糊看不清楚,furniture 與 appliance 請回空陣列並給低 confidence。"
            "只回傳 JSON。"
        )

    def _to_vocabulary(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """把模型的自由文字收斂成 jgb2 的 key;不在詞彙表的一律丟棄。"""
        if not isinstance(result, dict):
            return dict(_EMPTY)

        confidence = self._safe_float(result.get("confidence"))
        dropped: List[str] = []

        space_key = normalize_space(result.get("space"))
        if result.get("space") and space_key is None:
            dropped.append(str(result.get("space")))

        # 模型常把冰箱放進 furniture。正規化後一律用 category_of() 重新分類,
        # 以我們的分類為準,不信模型放在哪個陣列。
        buckets: Dict[str, List[Dict[str, Any]]] = {"furniture": [], "appliance": []}
        seen: set = set()
        for field in ("furniture", "appliance"):
            for raw in self._as_list(result.get(field)):
                key = normalize_item(self._name_of(raw))
                if key is None:
                    dropped.append(str(self._name_of(raw)))
                    continue
                if key in seen:  # 同一品項出現在兩個陣列時只留一次
                    continue
                seen.add(key)
                buckets[category_of(key)].append({
                    "key": key,
                    "label": ITEMS[key],
                    "confidence": self._safe_float(
                        self._confidence_of(raw), default=confidence
                    ),
                })

        field_confidences = {
            item["key"]: item["confidence"]
            for bucket in buckets.values()
            for item in bucket
        }

        if dropped:
            logger.info(f"點交照片辨識丟棄了不在詞彙表的詞: {dropped}")

        return {
            "space": space_key,
            "space_label": SPACES.get(space_key, "") if space_key else "",
            "furniture": buckets["furniture"],
            "appliance": buckets["appliance"],
            "description": str(result.get("description") or ""),
            "confidence": confidence,
            "dropped": dropped,
            "field_confidences": field_confidences,
        }

    # ------------------------------------------------------------------ #

    @staticmethod
    def _as_list(value: Any) -> List[Any]:
        """模型有時回單一字串而非陣列,包成 list 以免整筆被丟掉。"""
        if isinstance(value, list):
            return value
        if isinstance(value, str) and value.strip():
            return [value]
        return []

    @staticmethod
    def _name_of(raw: Any) -> Any:
        """品項可能是字串,也可能是 {name/label/item: ...} 物件。"""
        if isinstance(raw, dict):
            for k in ("name", "label", "item", "key"):
                if raw.get(k):
                    return raw[k]
            return ""
        return raw

    @staticmethod
    def _confidence_of(raw: Any) -> Any:
        return raw.get("confidence") if isinstance(raw, dict) else None

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        """安全轉換信心度(非數值 → default),並夾在 0..1。"""
        try:
            if value is None:
                return default
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _default_provider():
        from app.lib.llm_service.providers import create_provider
        return create_provider()

    @staticmethod
    def _parse_json(response: str) -> Dict[str, Any]:
        try:
            match = re.search(r"\{.*\}", response, re.DOTALL)
            return json.loads(match.group(0) if match else response)
        except (json.JSONDecodeError, AttributeError, TypeError):
            return {}
