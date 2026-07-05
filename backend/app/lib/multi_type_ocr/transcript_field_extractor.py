"""
謄本關鍵欄位抽取器

以規則抽取謄本關鍵欄位並計算信心度;低信心且允許時以 LLM Vision(few-shot)補齊。
共用流程見 field_extraction_base.RegexFieldExtractor。

抽取欄位:地號(land_number)、建號(building_number)、面積(area)、
權利範圍(rights_scope)、所有權人(owner)。
"""

import re

from .field_extraction_base import RegexFieldExtractor


class TranscriptFieldExtractor(RegexFieldExtractor):
    """謄本欄位抽取(規則 + LLM Vision + few-shot)"""

    PATTERNS = {
        "land_number": re.compile(r"地\s*號[:：\s]*([0-9Oo\-]+)"),
        "building_number": re.compile(r"建\s*號[:：\s]*([0-9Oo\-]+)"),
        "area": re.compile(r"面\s*積[:：\s]*([0-9,\.]+)"),
        "rights_scope": re.compile(r"權利範圍[:：\s]*([^\s\n]+)"),
        "owner": re.compile(r"(?:所有權人|登記名義人)[:：\s]*([^\s\n]+)"),
    }
    KEY_FIELDS = ("land_number", "building_number", "area", "rights_scope", "owner")
    FIELD_LABELS = {
        "land_number": "地號", "building_number": "建號", "area": "面積",
        "rights_scope": "權利範圍", "owner": "所有權人",
    }
    DOC_LABEL = "土地/建物謄本"
