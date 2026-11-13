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

**v2 格式(handover_format=v2,JGB #13541638271)**:每個品項多自評信心值、框、
損傷描述,另有 damages[]。舊格式一個位元都不能變(jgb2 現行版本在用),所以 v2
處理器**先照舊跑一次 `_to_vocabulary`**——攔截、複核佇列、few-shot 都吃舊形狀,
行為與不帶參數相同——再跑 `_to_vocabulary_v2`,結果放在私有鍵 `_handover_v2`,
由 analyze 端點在信心度攔截之後才換上(見 `apply_handover_format`)。
"""

from __future__ import annotations

import json
import logging
import re
import io
import math
from typing import Any, Dict, List, Optional

from PIL import Image, ImageOps

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


# v2 私有鍵:處理器放在 structured_data,process() 搬到頁層,AnalyzeService 取走。
# 回應、頁結果、複核佇列都不會留這個鍵。
HANDOVER_V2_KEY = "_handover_v2"

# Qwen3-VL 的 box_2d 是 0~1000 正規化刻度(2026-11-13 實測 3 張、兩種長寬比都落在
# 物件上;÷像素則偏移,見 ~/jgb-archive/handover-v2-20261113/probe/A6_result.md)。
_BOX_SCALE = 1000.0
# 框面積小於整張 0.5% 回 null(JGB 規格):太小的框裁出來看不出東西。
_MIN_BOX_AREA = 0.005
# 點交清單「情況簡述」上限 30 字。
_TEXT_LIMIT = 30

_EMPTY_V2: Dict[str, Any] = {
    "space": None,
    "space_label": "",
    "furniture": [],
    "appliance": [],
    "damages": [],
    "description": "",
    "confidence": 0.0,
    "dropped": [],
    "field_confidences": {},
}


class HandoverPhotoProcessor(ImageUnderstandingProcessor):
    """點交照片影像理解(VLM)+ 詞彙白名單過濾"""

    def __init__(self, provider: Any = None, fmt: Optional[str] = None):
        self._provider = provider
        self._fmt = fmt

    async def process(self, file_contents: bytes, *args: Any, **kwargs: Any):
        """v2 才在送模型前依 EXIF 轉正;舊格式完全不動(不改現行 jgb2 拿到的結果)。

        框要對到使用者在 jgb2 看到的方向(瀏覽器依 EXIF 轉正顯示)。只在照片真的帶
        非 1 的 Orientation 時才重新編碼,其餘原封不動交給共用模板。
        """
        if self._fmt == "v2":
            file_contents = _exif_upright(file_contents)
        page = await super().process(file_contents, *args, **kwargs)
        data = page.get("structured_data") if isinstance(page, dict) else None
        if isinstance(data, dict) and HANDOVER_V2_KEY in data:
            page[HANDOVER_V2_KEY] = data.pop(HANDOVER_V2_KEY)
        return page

    async def understand(
        self,
        image_data: str,
        few_shot: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        v2 = self._fmt == "v2"
        provider = self._provider or self._default_provider()
        prompt = self._build_prompt_v2() if v2 else self._build_prompt()
        try:
            response = await provider.call(
                prompt, image_data=image_data, few_shot=few_shot
            )
            result = self._parse_json(response)
        except Exception as e:  # VLM 不可用/失敗 → 降級,不讓整批中斷
            logger.warning(f"點交照片 VLM 理解失敗,降級為空結果: {e}")
            empty = dict(_EMPTY)
            if v2:
                empty[HANDOVER_V2_KEY] = _empty_v2()
            return empty

        legacy = self._to_vocabulary(result)
        if v2:
            legacy[HANDOVER_V2_KEY] = self._to_vocabulary_v2(result)
        return legacy

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

    @staticmethod
    def _build_prompt_v2() -> str:
        """v2 提示詞:多要自評信心值、框、損傷。

        ⚠️ 不列任何損傷範例詞(JGB 要求)。修繕照片的提示詞列了範例清單,模型就到處標
        那幾個詞;看不到損傷要回空,不要給模型可以套的詞。
        """
        return (
            "請辨識這張租賃點交現場照片,並以 JSON 回傳:\n"
            "- space: 這張照片拍的是哪個空間\n"
            "- furniture: 看到的傢俱陣列,每項是 {\"name\": 品項名稱, \"confidence\": 你對這一項判斷的 0 到 1 信心度, "
            "\"box_2d\": [x0, y0, x1, y1] 這一項在照片中的位置, \"condition\": 這一項看得到的損傷}\n"
            "- appliance: 看到的家電陣列,每項格式同 furniture\n"
            "- damages: 不屬於上述品項的損傷(例如牆面、地板、天花板上的),每筆是 {\"text\": 損傷描述, \"box_2d\": [x0, y0, x1, y1]}\n"
            "- description: 繁體中文描述\n"
            "- confidence: 0 到 1 的整張照片信心度\n"
            "\n"
            "box_2d 以照片左上角為原點,x 往右、y 往下。condition 與 text 用繁體中文,30 字以內。\n"
            "只回報照片中確實看得到的損傷;看不到損傷時 condition 回空字串、damages 回空陣列,不要猜測。\n"
            "\n"
            "**品項名稱只能使用下列詞彙,不要自創名稱、不要加形容詞:**\n"
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

    def _to_vocabulary_v2(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """v2 形狀。品項的收斂、分類、去重規則與 `_to_vocabulary` 完全相同,差別只有:

        - confidence 是模型對這一項的自評;沒給或不是數字 → None,**不拿整張補**
          (JGB:「不要再拿整張照片的信心值當預設」)。超出 0~1 夾回(同舊版)。
        - 多 box(0~1 比例,不合理回 None)、condition(30 字內)。
        - 多 damages[]:{text, box};text 空的整筆丟掉。
        - field_confidences 只放有自評的品項。
        """
        if not isinstance(result, dict):
            return _empty_v2()

        confidence = self._safe_float(result.get("confidence"))
        dropped: List[str] = []

        space_key = normalize_space(result.get("space"))
        if result.get("space") and space_key is None:
            dropped.append(str(result.get("space")))

        buckets: Dict[str, List[Dict[str, Any]]] = {"furniture": [], "appliance": []}
        seen: set = set()
        for field in ("furniture", "appliance"):
            for raw in self._as_list(result.get(field)):
                key = normalize_item(self._name_of(raw))
                if key is None:
                    dropped.append(str(self._name_of(raw)))
                    continue
                if key in seen:
                    continue
                seen.add(key)
                obj = raw if isinstance(raw, dict) else {}
                buckets[category_of(key)].append({
                    "key": key,
                    "label": ITEMS[key],
                    "confidence": self._item_confidence(obj.get("confidence")),
                    "box": normalize_box(obj.get("box_2d", obj.get("box"))),
                    "condition": clip_text(obj.get("condition")),
                })

        damages: List[Dict[str, Any]] = []
        for raw in self._as_list(result.get("damages")):
            if isinstance(raw, dict):
                text, box = clip_text(raw.get("text")), normalize_box(raw.get("box_2d", raw.get("box")))
            else:
                text, box = clip_text(raw), None
            if text:
                damages.append({"text": text, "box": box})

        return {
            "space": space_key,
            "space_label": SPACES.get(space_key, "") if space_key else "",
            "furniture": buckets["furniture"],
            "appliance": buckets["appliance"],
            "damages": damages,
            "description": str(result.get("description") or ""),
            "confidence": confidence,
            "dropped": dropped,
            "field_confidences": {
                item["key"]: item["confidence"]
                for bucket in buckets.values()
                for item in bucket
                if item["confidence"] is not None
            },
        }

    @staticmethod
    def _item_confidence(value: Any) -> Optional[float]:
        """品項自評:沒給或不是有限數字 → None;否則夾在 0..1。"""
        if isinstance(value, bool) or value is None:
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(number):
            return None
        return max(0.0, min(1.0, number))

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
        """未注入 provider 時依分流表建立;表裡沒指定 handover_photo 就維持全域 LLM_PROVIDER。"""
        from app.lib.llm_service.providers import create_provider
        from app.lib.llm_service.routing import provider_name_for

        return create_provider(provider_name_for("handover_photo", None))

    @staticmethod
    def _parse_json(response: str) -> Dict[str, Any]:
        try:
            match = re.search(r"\{.*\}", response, re.DOTALL)
            return json.loads(match.group(0) if match else response)
        except (json.JSONDecodeError, AttributeError, TypeError):
            return {}


# ---------------------------------------------------------------------- #
# v2 共用小工具(端點轉換與測試也用)

def _empty_v2() -> Dict[str, Any]:
    return {k: (list(v) if isinstance(v, list) else dict(v) if isinstance(v, dict) else v)
            for k, v in _EMPTY_V2.items()}


def normalize_box(value: Any) -> Optional[Dict[str, Any]]:
    """模型的 box_2d(0~1000)→ {"box":[x0,y0,x1,y1],"unit":"ratio"};不合理一律 None。

    不合理=不是 4 個有限數字、越界(不夾回)、x0>=x1 或 y0>=y1、面積小於整張 0.5%。
    """
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    coords: List[float] = []
    for v in value:
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            return None
        f = float(v)
        if not math.isfinite(f):
            return None
        coords.append(f / _BOX_SCALE)
    x0, y0, x1, y1 = coords
    if min(coords) < 0.0 or max(coords) > 1.0:
        return None
    if x0 >= x1 or y0 >= y1:
        return None
    if (x1 - x0) * (y1 - y0) < _MIN_BOX_AREA - 1e-12:
        return None
    return {"box": [round(c, 4) for c in coords], "unit": "ratio"}


def clip_text(value: Any, limit: int = _TEXT_LIMIT) -> str:
    """去頭尾空白後截到 limit 個字元(Unicode 字元數);不是字串回 ""。"""
    if not isinstance(value, str):
        return ""
    return value.strip()[:limit]


def _exif_upright(file_contents: bytes) -> bytes:
    """照片帶非 1 的 EXIF Orientation 才轉正並重新編碼成 PNG;其餘原樣回傳。"""
    try:
        image = Image.open(io.BytesIO(file_contents))
        orientation = image.getexif().get(0x0112, 1)
    except Exception:
        return file_contents
    if orientation in (None, 1):
        return file_contents
    from .processor import _cap_image_pixels

    upright = ImageOps.exif_transpose(image)
    upright = _cap_image_pixels(upright)
    if upright.mode not in ("RGB", "RGBA", "L", "LA", "P", "I", "1"):
        upright = upright.convert("RGB")
    buf = io.BytesIO()
    upright.save(buf, format="PNG")
    return buf.getvalue()


def apply_handover_format(
    result: Dict[str, Any], v2_pages: Dict[Any, Dict[str, Any]]
) -> Dict[str, Any]:
    """handover_format="v2":回傳新 dict(深拷貝,不改輸入)。

    **必須在 `_apply_confidence_gating` 之後呼叫**:誰要複核、複核佇列存什麼,
    都照舊形狀算(與不帶參數相同);這裡只換「看得到的」部分:

    - 每頁 structured_data 換成 v2 形狀,頁層 field_confidences 跟著換(只放有自評的品項)。
    - document_fields 的 furniture、appliance 換成 v2 品項並加 damages;
      field_confidences 換成 v2;needs_confirmation、extraction_confidence 依自評重算:
      自評低於 OCR_QUALITY_THRESHOLD **或沒給自評**的品項列入 needs_confirmation;
      extraction_confidence 只平均有自評的品項,一個都沒有就拿掉這個鍵。
    - 頂層 field_confidences 換成 v2。needs_review、review_item_id 不動。

    v2_pages 是 {頁碼: v2 structured_data},由 AnalyzeService.analyze 的 handover_v2_out 收集。
    """
    import copy

    from app.config import settings

    new = copy.deepcopy(result)
    pages = new.get("pages") or []
    v2_in_order: List[Dict[str, Any]] = []
    for page in pages:
        if not isinstance(page, dict):
            continue
        v2 = v2_pages.get(page.get("page_number"))
        if not isinstance(v2, dict):
            continue
        v2 = copy.deepcopy(v2)
        page["structured_data"] = v2
        page["field_confidences"] = dict(v2.get("field_confidences") or {})
        v2_in_order.append(v2)

    if not v2_in_order:
        return new

    # 跨頁彙整:點交只收影像,實際只有 1 頁;多頁時同一品項取第一次出現的那筆。
    seen: set = set()
    merged: Dict[str, List[Dict[str, Any]]] = {"furniture": [], "appliance": []}
    damages: List[Dict[str, Any]] = []
    for v2 in v2_in_order:
        for bucket in ("furniture", "appliance"):
            for item in v2.get(bucket) or []:
                if item.get("key") in seen:
                    continue
                seen.add(item.get("key"))
                merged[bucket].append(copy.deepcopy(item))
        damages.extend(copy.deepcopy(v2.get("damages") or []))

    items = merged["furniture"] + merged["appliance"]
    field_confidences = {
        item["key"]: item["confidence"] for item in items if item.get("confidence") is not None
    }

    df = new.get("document_fields")
    if isinstance(df, dict):
        df["furniture"] = merged["furniture"]
        df["appliance"] = merged["appliance"]
        df["damages"] = damages
        df["field_confidences"] = dict(field_confidences)
        threshold = settings.OCR_QUALITY_THRESHOLD
        df["needs_confirmation"] = sorted({
            item["key"] for item in items
            if item.get("confidence") is None or item["confidence"] < threshold
        })
        scored = [item["confidence"] for item in items if item.get("confidence") is not None]
        if scored:
            df["extraction_confidence"] = round(sum(scored) / len(scored), 4)
        else:
            df.pop("extraction_confidence", None)

    new["field_confidences"] = dict(field_confidences)
    return new
