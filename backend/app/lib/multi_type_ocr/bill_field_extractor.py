"""
帳單關鍵欄位抽取器

票證式抽取水電/管理費等帳單關鍵欄位並計算信心度;劣化影像以 LLM Vision(few-shot)
補齊。缺漏關鍵欄位標記於 needs_confirmation 供補齊。

抽取欄位:金額(amount)、日期(date)、戶號/電號(account_no);
電費 4 欄(address、period_start、period_end、kwh)以標籤規則讀,正規化、驗證與待確認判定
交 bill_electric_fields(與直讀共用)。電費 4 欄不進 LLM 補欄位,也不算必要欄位。
"""

import re
from typing import Any, Dict, List, Optional

from .bill_electric_fields import resolve_electric_fields
from .field_extraction_base import RegexFieldExtractor, _first_captured_group

# 西元或民國日期(2026/09/15、115/09/15、民國115年9月15日);容許數字與分隔號之間有空白
_DATE = (
    r"(?:(?:中華民國|民國)\s*)?[0-9]{2,4}\s*[/年.\-]\s*[0-9]{1,2}\s*[/月.\-]\s*[0-9]{1,2}\s*日?"
)
_PERIOD_LABEL = r"(?:計費期間|用電期間)"


class BillFieldExtractor(RegexFieldExtractor):
    """帳單欄位抽取(規則 + LLM Vision + few-shot)"""

    PATTERNS = {
        "amount": re.compile(
            r"(?:本期應繳|應繳金額|應繳|金額)[:：\s]*(?:NT\$|\$)?\s*([0-9,]+)"
        ),
        "date": re.compile(
            r"(?:繳費期限|繳費日期|帳單日期|日期|期限)[:：\s]*"
            # 支援西元(2026/03/15)與民國(民國115年3月15日)雙格式
            r"((?:中華民國|民國)?\s*[0-9]{2,4}[/年.\-][0-9]{1,2}[/月.\-][0-9]{1,2}\s*日?)"
        ),
        "account_no": re.compile(r"(?:電號|戶號|用戶號|帳號)[:：\s]*([0-9A-Za-z\-]+)"),
    }
    # 電費 4 欄:比對前文字已做 NFKC(全形冒號、數字都已轉半形)
    ELECTRIC_PATTERNS = {
        "address": re.compile(r"用電地址[:\s]*([^\n]+)"),
        "period": re.compile(
            _PERIOD_LABEL + r"[:\s]*(" + _DATE + r")\s*(?:至|到|~|～|－|—|-)\s*(" + _DATE + r")"
        ),
        "kwh": re.compile(
            r"(?:本期計費度數|計費度數|本期用電度數|用電度數)[:\s]*([0-9][0-9,]*(?:\.[0-9]+)?)"
        ),
    }
    KEY_FIELDS = ("amount", "date", "account_no")
    FIELD_LABELS = {"amount": "金額", "date": "日期", "account_no": "戶號/電號"}
    DOC_LABEL = "帳單"
    # LLM 補欄位依分流表 LLM_PROVIDER_BY_DOCUMENT_TYPE["bill"] 取供應商
    ROUTING_DOCUMENT_TYPE = "bill"

    async def extract(
        self,
        text: str,
        image_data: Optional[str] = None,
        use_llm_fallback: bool = False,
        few_shot: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        result = await super().extract(
            text, image_data=image_data, use_llm_fallback=use_llm_fallback, few_shot=few_shot
        )
        values, confidences, needs = resolve_electric_fields(
            *self._extract_electric_raw(self._normalize_for_matching(text or ""))
        )
        result.update(values)
        result["field_confidences"] = {**result["field_confidences"], **confidences}
        result["needs_confirmation"] = list(result["needs_confirmation"]) + needs
        return result

    def _extract_electric_raw(self, text: str):
        """回傳 (4 欄原始讀值, 是否有兩段以上計費期間)。規則讀值一律視為確定。"""
        address = _first_captured_group(self.ELECTRIC_PATTERNS["address"].search(text))
        kwh = _first_captured_group(self.ELECTRIC_PATTERNS["kwh"].search(text))
        periods = {
            (re.sub(r"\s+", "", m.group(1)), re.sub(r"\s+", "", m.group(2)))
            for m in self.ELECTRIC_PATTERNS["period"].finditer(text)
        }
        start, end = next(iter(periods)) if len(periods) == 1 else (None, None)
        raw = {
            "address": (address, True),
            "kwh": (kwh, True),
            "period_start": (start, True),
            "period_end": (end, True),
        }
        return raw, len(periods) > 1
