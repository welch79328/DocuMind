"""
帳單電費欄位(address、period_start、period_end、kwh)的正規化、格式驗證與待確認判定。

直讀(BillDirectReadProcessor)與文字層規則(BillFieldExtractor)兩條路共用這一處,
兩條路回的值、格式、待確認語意才會一致。規格:docs/api/INTEGRATION.md §3.3、
.kiro/specs/bill-electric-fields/acceptance.md R1–R11。

每一欄的判定:
- 原始值是 null(單上沒有、讀不到)⇒ 值 null,不列 needs_confirmation、不放 field_confidences。
  水費、管理費單本來就沒有度數與計費期間,列進去會讓每張都 needs_review(quality_assessor
  任一欄位信心度低於門檻即判複核)。
- 讀到、格式驗證不過 ⇒ 值 null、列 needs_confirmation(R6)。
- 讀到、格式對、來源標「不確定」⇒ 保留值、列 needs_confirmation(R7)。
- 讀到、格式對、確定 ⇒ 保留值。
- 單上有兩段以上計費期間(跨期、補收)⇒ 起訖都 null、都列 needs_confirmation(R10)。
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from .direct_read_processor import (
    CONFIDENCE_CERTAIN,
    CONFIDENCE_MISSING,
    CONFIDENCE_UNCERTAIN,
    parse_date,
)

ELECTRIC_FIELDS = ("address", "period_start", "period_end", "kwh")

ADDRESS_MAX_CHARS = 80
KWH_MAX_CHARS = 30

# 地址不得含網址、@、半形或全形冒號(AIChatbot 規格;冒號在 NFKC 後都是 `:`)
_ADDRESS_FORBIDDEN = re.compile(r"https?://|www\.|@|:", re.IGNORECASE)
# 度數後面可能帶單位;只去單位,不去數字裡的任何字
_KWH_UNIT = re.compile(r"\s*(?:度|kwh|kWh|KWH|千瓦小時)\s*$")
_KWH_NUMBER = re.compile(r"^(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?$")

# 一個欄位的原始讀值:(值或 None, 來源是否確定)
Raw = Tuple[Optional[str], bool]


def _nfkc(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip()


def normalize_address(value: str) -> Optional[str]:
    """收成單行(換行與連續空白併成一個空白);超過 80 字或含網址、@、冒號回 None。"""
    text = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value)).strip()
    if not text or len(text) > ADDRESS_MAX_CHARS or _ADDRESS_FORBIDDEN.search(text):
        return None
    return text


def normalize_kwh(value: str) -> Optional[str]:
    """去掉尾端單位後必須是數字字串(可帶千分位與小數)、> 0、≤ 30 字;不合回 None。"""
    text = _KWH_UNIT.sub("", _nfkc(value)).replace(" ", "")
    if not text or len(text) > KWH_MAX_CHARS or not _KWH_NUMBER.match(text):
        return None
    if float(text.replace(",", "")) <= 0:
        return None
    return text


def resolve_electric_fields(
    raw: Dict[str, Raw], multiple_periods: bool = False
) -> Tuple[Dict[str, Optional[str]], Dict[str, float], List[str]]:
    """把 4 欄原始讀值轉成 (值, field_confidences, needs_confirmation)。

    值一定 4 個鍵都有;field_confidences 只放讀到東西的欄位(見模組說明)。
    """
    values: Dict[str, Optional[str]] = {name: None for name in ELECTRIC_FIELDS}
    confidences: Dict[str, float] = {}
    needs: List[str] = []

    def settle(name: str, normalized: Optional[str], certain: bool) -> None:
        if normalized is None:          # 讀到但格式驗證不過
            confidences[name] = CONFIDENCE_MISSING
            needs.append(name)
            return
        values[name] = normalized
        if certain:
            confidences[name] = CONFIDENCE_CERTAIN
        else:
            confidences[name] = CONFIDENCE_UNCERTAIN
            needs.append(name)

    address, address_certain = raw.get("address", (None, True))
    if address is not None:
        settle("address", normalize_address(address), address_certain)

    kwh, kwh_certain = raw.get("kwh", (None, True))
    if kwh is not None:
        settle("kwh", normalize_kwh(kwh), kwh_certain)

    start, start_certain = raw.get("period_start", (None, True))
    end, end_certain = raw.get("period_end", (None, True))
    if multiple_periods:
        for name in ("period_start", "period_end"):
            confidences[name] = CONFIDENCE_MISSING
            needs.append(name)
    elif start is not None or end is not None:
        start_date = parse_date(start) if start is not None else None
        end_date = parse_date(end) if end is not None else None
        if start_date and end_date and end_date < start_date:
            start_date = end_date = None     # 迄早於起:兩欄都算格式驗證不過
        # 只讀到一端時,另一端也列待確認:計費期間缺一端就不完整
        if start is not None:
            settle("period_start", start_date, start_certain and end is not None)
        else:
            confidences["period_start"] = CONFIDENCE_MISSING
            needs.append("period_start")
        if end is not None:
            settle("period_end", end_date, end_certain and start is not None)
        else:
            confidences["period_end"] = CONFIDENCE_MISSING
            needs.append("period_end")

    return values, confidences, needs
