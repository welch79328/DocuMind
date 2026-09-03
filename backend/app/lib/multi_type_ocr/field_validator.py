"""欄位值的型別合理性檢查——攔截「語法合法但填錯欄位」的值。

## 為什麼需要,而且為什麼不能只靠 field_normalizer

2026-09-03 於線上實測一份謄本,系統回傳:

    "building_number": "過溝段00004-000",
    "area": "0555-0000",          ← 這是地號,被填進面積欄位
    "field_confidences": { "area": 0.8 }

錯值帶著 0.8 的高信心度。字串合法、型別看似正確,規則檢查與信心度都攔不住,
該頁只因整體信心度 0.320 才被拖進複核——**運氣,不是機制**。
這正是需求 2 點名的「語法合法但數值錯誤」的靜默污染。

`field_normalizer` 擋不住,因為它是**為比對而設計的寬鬆正規化**,不是驗證器:

    normalize_number("0555-0000")   → 555.0     ← 地號被解析成數字
    normalize_number("過溝段00004-000") → 4.0      ← 建號被解析成 4

⚠️ **這同時是共識機制的隱憂**:`values_agree` 用的就是這支,
所以 `area="0555-0000"` 與 `area="555"` 在共識比對裡會被判定為一致。

## 設計約束

檢查只回報「這個值不像該欄位該有的東西」,**不修改值、不猜正確答案**。
呼叫端據此壓低信心度——與共識同一不變量:只收緊,不放寬。
"""

import re
from typing import Any, Dict, Optional

from .field_normalizer import field_type_of, normalize_date, normalize_number

# 識別碼形狀:數字-數字(地號 0555-0000、建號 00004-000)。
# 數值欄位出現這種形狀,幾乎必然是把識別碼填錯欄位——
# 而 normalize_number 會把它硬解析成數字,不會報錯。
_IDENTIFIER_SHAPE = re.compile(r"\d+\s*[-–—]\s*\d+")

_ABSENT = {None, "", "null", "N/A", "無", "需人工標註", "[待標註]"}


def _is_absent(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() in _ABSENT)


def validate_field_value(field_name: str, value: Any) -> Optional[str]:
    """檢查單一欄位值;通過回傳 None,不通過回傳可讀的原因。

    未取得的欄位視為通過——「沒抽到」由 needs_confirmation 處理,不是型別錯誤。
    """
    if _is_absent(value):
        return None

    text = str(value).strip()
    kind = field_type_of(field_name)

    if kind == "number":
        if _IDENTIFIER_SHAPE.search(text):
            return f"數值欄位出現識別碼形狀(如地號/建號):{text!r}"
        if normalize_number(text) is None:
            return f"數值欄位無法解析為數字:{text!r}"
        return None

    if kind == "date":
        if normalize_date(text) is None:
            return f"日期欄位無法解析為日期:{text!r}"
        return None

    if kind == "identifier":
        if not any(ch.isdigit() for ch in text):
            return f"識別碼欄位不含任何數字:{text!r}"
        return None

    # person / string / enum 的合法形態太廣,不做形狀檢查——
    # 硬訂規則的誤判成本高於它能攔下的錯誤。
    return None


def validate_fields(data: Dict[str, Any]) -> Dict[str, str]:
    """檢查整份抽取結果,回傳 {欄位名: 不通過的原因}。

    同時掃頂層與巢狀的 `fields`,因為不同處理器的結構不同。
    """
    problems: Dict[str, str] = {}
    if not isinstance(data, dict):
        return problems

    def scan(mapping: Dict[str, Any]) -> None:
        for key, value in mapping.items():
            if key in ("field_confidences", "needs_confirmation", "fields"):
                continue
            if isinstance(value, dict):
                scan(value)
                continue
            reason = validate_field_value(key, value)
            if reason:
                problems[key] = reason

    scan(data)
    nested = data.get("fields")
    if isinstance(nested, dict):
        scan(nested)
    return problems
