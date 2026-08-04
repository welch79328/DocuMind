"""
欄位值正規化

建立共識機制中「一致」的判準:**逐欄位正規化後相等即視為一致**。

兩個方向的失效都很貴,故規則刻意保守:

- **正規化不足** → `153.00` 與 `153` 被誤判為不一致,不一致率虛高、複核佇列塞爆
- **過度正規化** → `0221-0000` 與 `0221-0001` 被誤判為一致,真實錯誤被共識掩蓋

因此僅正規化「已知的表示法差異」(空白、全形半形、千分位、單位、紀年、
常見 OCR 字元誤判),絕不觸碰語意內容。

本模組為**獨立純函式**,不依賴 `TranscriptPostprocessor` 的內部狀態——後者的
`correct_field_formats()` 內 `fix_land_number` / `fix_roc_date` 為巢狀函式,
簽章接收 regex match object,語意為「整段文字的 re.sub 格式統一」,與「單一欄位
值正規化」不同,故僅參考其 regex 樣式與轉換規則,不直接呼叫。

對應需求: 4.1, 4.2
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional

try:  # Python 3.8+ 皆可用;此處僅為型別標註
    from typing import Literal

    FieldType = Literal["identifier", "number", "date", "enum", "person", "string"]
except ImportError:  # pragma: no cover
    FieldType = str  # type: ignore


# --------------------------------------------------------------------------- #
# 欄位型別對應表
# --------------------------------------------------------------------------- #
FIELD_TYPES: Dict[str, str] = {
    # 識別碼
    "land_number": "identifier",
    "building_number": "identifier",
    "unified_id": "identifier",
    "title_number": "identifier",
    "contract_number": "identifier",
    "account_number": "identifier",
    "additional_numbers": "identifier",
    # 數值
    "area": "number",
    "contract_amount": "number",
    "amount": "number",
    "total_amount": "number",
    # 日期
    "register_date": "date",
    "registration_date": "date",
    "construction_date": "date",
    "signing_date": "date",
    "effective_date": "date",
    "due_date": "date",
    "billing_date": "date",
    "print_date": "date",
    # 列舉字串
    "rights_scope": "enum",
    "main_use": "enum",
    "currency": "enum",
    "floor_description": "enum",
    # 人名
    "owner": "person",
    "party_a": "person",
    "party_b": "person",
}

# 數值比對容差(吸收四捨五入雜訊,但不足以掩蓋真實差異)
NUMBER_TOLERANCE = 0.01

# 常見 OCR 字元誤判(僅套用於識別碼:其內容本為數字,誤判方向明確)
_IDENTIFIER_CHAR_FIXES = {"O": "0", "o": "0", "l": "1", "I": "1"}

# 連字號變體統一為半形 hyphen
_HYPHEN_VARIANTS = "‐‑‒–—―−﹣－"

# 數值欄位常見的幣別符號與單位
_NUMBER_NOISE = re.compile(
    r"(NT\$|NTD|TWD|USD|CNY|RMB|JPY|EUR|[$￥¥€元圓整]|新?台幣|人民幣|美元|"
    r"平方公[尺米]|坪|㎡|m2|m²)",
    re.IGNORECASE,
)

_CJK_NUMERALS = {
    "零": 0, "〇": 0, "一": 1, "二": 2, "兩": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9,
    "壹": 1, "貳": 2, "参": 3, "參": 3, "叁": 3, "肆": 4, "伍": 5,
    "陸": 6, "柒": 7, "捌": 8, "玖": 9,
}
_CJK_UNITS = {"十": 10, "拾": 10, "百": 100, "佰": 100, "千": 1000, "仟": 1000}
_CJK_SECTIONS = {"萬": 10 ** 4, "万": 10 ** 4, "億": 10 ** 8, "亿": 10 ** 8}

_NUMBER_PATTERN = re.compile(r"-?\d+(?:\.\d+)?")

# 日期樣式(參考 correct_field_formats() 內民國日期 regex)
_ROC_DATE_PATTERN = re.compile(
    r"(民國)?\s*(\d{1,4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?"
)
_DELIMITED_DATE_PATTERN = re.compile(
    r"^(\d{1,4})\s*[/\-.]\s*(\d{1,2})\s*[/\-.]\s*(\d{1,2})$"
)
_COMPACT_DATE_PATTERN = re.compile(r"^(\d{3,4})(\d{2})(\d{2})$")

# 民國/西元分界:年份小於此值視為民國紀年
_ROC_YEAR_CEILING = 200
_ROC_EPOCH_OFFSET = 1911


# --------------------------------------------------------------------------- #
# 共用小工具
# --------------------------------------------------------------------------- #
def _to_halfwidth(text: str) -> str:
    """全形轉半形(NFKC 正規化);全形空白一併轉為半形空白"""
    return unicodedata.normalize("NFKC", text)


def _strip_all_whitespace(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _is_absent(value: Any) -> bool:
    """None 與純空白視為未取得該欄位"""
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


# --------------------------------------------------------------------------- #
# 各型別正規化(純函式)
# --------------------------------------------------------------------------- #
def normalize_identifier(value: Any) -> str:
    """
    識別碼:去空白 → 全形轉半形 → 常見 OCR 字元誤判修正 → 統一連字號 → 大寫

    僅修正 O/o→0、l/I→1 這類方向明確的誤判;不做任何長度補齊或截斷,
    以免 `0221-000` 與 `0221-0000` 被誤判為一致。
    """
    text = _to_halfwidth(str(value))
    text = _strip_all_whitespace(text)
    text = "".join(_IDENTIFIER_CHAR_FIXES.get(ch, ch) for ch in text)
    text = "".join("-" if ch in _HYPHEN_VARIANTS else ch for ch in text)
    return text.upper()


def _cjk_to_arabic(text: str) -> Optional[float]:
    """中文數字轉阿拉伯數字(支援十/百/千/萬/億與大寫數字);無法解析回 None"""
    total = 0
    section = 0
    number = 0
    seen = False

    for ch in text:
        if ch in _CJK_NUMERALS:
            number = _CJK_NUMERALS[ch]
            seen = True
        elif ch in _CJK_UNITS:
            # 「十五」開頭省略「一」
            section += (number or 1) * _CJK_UNITS[ch]
            number = 0
            seen = True
        elif ch in _CJK_SECTIONS:
            section = (section + number) * _CJK_SECTIONS[ch]
            total += section
            section = 0
            number = 0
            seen = True
        else:
            return None

    return float(total + section + number) if seen else None


def normalize_number(value: Any) -> Optional[float]:
    """
    數值:去千分位、幣別符號與單位後轉 float;支援中文數字。

    無法解析為數值時回傳 None(視為未取得,不會與任何數值一致)。
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = _to_halfwidth(str(value))
    text = _strip_all_whitespace(text)
    text = _NUMBER_NOISE.sub("", text)
    text = text.replace(",", "")

    match = _NUMBER_PATTERN.search(text)
    if match:
        return float(match.group())

    return _cjk_to_arabic(text)


def normalize_date(value: Any) -> Optional[str]:
    """
    日期:民國與西元紀年統一轉為 `YYYY-MM-DD`。

    年份 ≤ 200 或帶「民國」前綴者視為民國紀年(+1911)。
    無法解析為日期時回傳 None,由呼叫端退回字串比對。
    """
    text = _strip_all_whitespace(_to_halfwidth(str(value)))

    roc = _ROC_DATE_PATTERN.match(text)
    if roc:
        prefixed, year, month, day = roc.groups()
        return _format_date(int(year), int(month), int(day), force_roc=bool(prefixed))

    for pattern in (_DELIMITED_DATE_PATTERN, _COMPACT_DATE_PATTERN):
        match = pattern.match(text)
        if match:
            year, month, day = (int(g) for g in match.groups())
            return _format_date(year, month, day)

    return None


def _format_date(year: int, month: int, day: int, force_roc: bool = False) -> Optional[str]:
    if force_roc or year <= _ROC_YEAR_CEILING:
        year += _ROC_EPOCH_OFFSET
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"


def normalize_enum(value: Any) -> str:
    """列舉字串:全形轉半形後去除所有空白"""
    return _strip_all_whitespace(_to_halfwidth(str(value)))


def normalize_person(value: Any) -> str:
    """人名:去空白並去除標點,保留中日韓文字與英數"""
    text = _strip_all_whitespace(_to_halfwidth(str(value)))
    return "".join(
        ch for ch in text
        if ch.isalnum() or unicodedata.category(ch).startswith("L")
    )


def normalize_string(value: Any) -> str:
    """預設:去頭尾空白"""
    return _to_halfwidth(str(value)).strip()


_NORMALIZERS = {
    "identifier": normalize_identifier,
    "number": normalize_number,
    "date": normalize_date,
    "enum": normalize_enum,
    "person": normalize_person,
    "string": normalize_string,
}


# --------------------------------------------------------------------------- #
# 公開介面
# --------------------------------------------------------------------------- #
def field_type_of(field_name: str) -> str:
    """取得欄位的正規化型別;未列於對應表者採預設字串正規化"""
    return FIELD_TYPES.get(field_name, "string")


def normalize(field_name: str, value: Any) -> Any:
    """
    依欄位型別正規化欄位值。

    Args:
        field_name: 欄位名稱(決定套用哪組規則)
        value: 原始欄位值

    Returns:
        正規化後的可比對表示;未取得該欄位時回傳 None。
        清單值逐元素正規化後回傳 tuple。
    """
    if _is_absent(value):
        return None

    if isinstance(value, (list, tuple)):
        return tuple(normalize(field_name, item) for item in value)

    normalizer = _NORMALIZERS[field_type_of(field_name)]
    normalized = normalizer(value)

    # 日期無法解析時退回字串比對,避免「簽約當日」這類自由文字被視為缺值
    if normalized is None and field_type_of(field_name) == "date":
        return normalize_string(value)

    return normalized


def values_agree(field_name: str, left: Any, right: Any) -> bool:
    """
    判定兩個候選對同一欄位是否一致。

    - 兩邊皆未取得 → 一致(無可比對的差異)
    - 單邊缺值      → **不一致**(保守方向,寧可觸發複核)
    - 數值型別      → 差值在容差 0.01 內即視為一致
    """
    normalized_left = normalize(field_name, left)
    normalized_right = normalize(field_name, right)

    if normalized_left is None and normalized_right is None:
        return True
    if normalized_left is None or normalized_right is None:
        return False

    if isinstance(normalized_left, float) and isinstance(normalized_right, float):
        return abs(normalized_left - normalized_right) <= NUMBER_TOLERANCE

    return normalized_left == normalized_right


class FieldNormalizer:
    """
    欄位正規化器(無狀態);供 `FieldConsensusResolver` 以組合方式注入。

    所有行為委派給模組層純函式,類別本身不持有任何狀態。
    """

    @staticmethod
    def field_type_of(field_name: str) -> str:
        return field_type_of(field_name)

    @staticmethod
    def normalize(field_name: str, value: Any) -> Any:
        return normalize(field_name, value)

    @staticmethod
    def values_agree(field_name: str, left: Any, right: Any) -> bool:
        return values_agree(field_name, left, right)
