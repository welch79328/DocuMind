"""
帳單關鍵欄位抽取器

票證式抽取水電/管理費等帳單關鍵欄位並計算信心度;劣化影像以 LLM Vision(few-shot)
補齊。缺漏關鍵欄位標記於 needs_confirmation 供補齊。

抽取欄位:金額(amount)、日期(date)、戶號(account_no)。
"""

import re

from .field_extraction_base import RegexFieldExtractor


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
        "account_no": re.compile(r"(?:戶號|用戶號|帳號)[:：\s]*([0-9A-Za-z\-]+)"),
    }
    KEY_FIELDS = ("amount", "date", "account_no")
    FIELD_LABELS = {"amount": "金額", "date": "日期", "account_no": "戶號"}
    DOC_LABEL = "帳單"
