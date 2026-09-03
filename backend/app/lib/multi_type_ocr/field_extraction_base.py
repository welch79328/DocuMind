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
import unicodedata
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

    # 必要欄位:這份文件「應該要有」的欄位。信心度只以這些欄位計算,
    # 抽不到才進 needs_confirmation、才觸發 LLM 補齊。
    #
    # 未宣告時退回 KEY_FIELDS(維持既有行為,帳單等尚未區分的抽取器不受影響)。
    #
    # 2026-09-04 引入的理由:謄本抽取器由 5 欄擴充到 23 欄後,
    # extraction_confidence 從 0.54 掉到 0.196——但掉下去的那 10 欄
    # (附屬建物、共有部分、他項權利、查封註記等)是**這份謄本本來就沒有的東西**,
    # 不是抽取失敗。把它們算進分母等於懲罰「這棟房子沒有附屬建物」。
    #
    # `seizure_mark`(查封註記)更是相反:**沒有查封才是正常且理想的情況**,
    # 把它的缺席計為信心度 0 在語意上是反的。
    REQUIRED_FIELDS: tuple = ()

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
        required = self._required_fields()
        needs = [k for k in required if confidences[k] < self.threshold]

        llm_used = False
        if use_llm_fallback and needs and image_data:
            llm_fields = await self._extract_with_llm(text, image_data, needs, few_shot)
            for key, value in llm_fields.items():
                if key in self.KEY_FIELDS and value:
                    fields[key] = value
                    confidences[key] = self._LLM_CONFIDENCE
            needs = [k for k in required if confidences[k] < self.threshold]
            llm_used = True

        # 信心度只計必要欄位:選配欄位抽到是加分,抽不到不該扣分。
        # 例:一棟沒有附屬建物的透天,不該因為抽不到「附屬建物面積」而被判低信心。
        scored = {k: confidences[k] for k in required if k in confidences}

        return {
            **fields,
            "field_confidences": confidences,
            "needs_confirmation": needs,
            "extraction_confidence": round(
                sum(scored.values()) / len(scored), 4
            ) if scored else 0.0,
            "llm_used_for_extraction": llm_used,
        }

    def _required_fields(self) -> tuple:
        """必要欄位;未宣告 REQUIRED_FIELDS 時退回 KEY_FIELDS(既有行為)。"""
        return self.REQUIRED_FIELDS or self.KEY_FIELDS

    # ------------------------------------------------------------------ #
    @staticmethod
    def _normalize_for_matching(text: str) -> str:
        """比對前一律做 NFKC:同一個字有多種碼位,不正規化就比不到。

        2026-09-04 實測:一份真實電子謄本的 PDF 文字層裡,「權利範圍」的「利」是
        U+F9DD(CJK 相容表意文字)而不是一般的 U+5229——**外觀完全一樣,碼位不同**,
        `"權利範圍" in text` 永遠是 False。同一份文件受影響的還有「權利種類」
        與「他項權利」,NFKC 之後才數得到 5／2／4 次。

        為什麼以前沒事、現在才浮現:走 OCR 時是「看圖重新辨識」,輸出的是正常碼位;
        改成文字層直讀之後,PDF 內嵌的相容字原樣進來,樣式就比不到了。
        該份謄本用文字層路徑時規則抽中 13/23,加上這一步之後 17/23。

        地政謄本常見的三類特殊字 NFKC 都能處理:
          相容表意文字 U+F900–FAFF   利(U+F9DD) → 利(U+5229)
          表意註記符號 U+3190–32FF   ㆞ → 地、㈰ → 日
          全形英數     U+FF00–FFEF   １１１ → 111、： → :

        放在基底而非個別抽取器:合約與帳單只要來源是 PDF 文字層,會踩到同一個坑。

        ⚠️ 只影響「比對用」的文字。回傳給呼叫端的 pages[].text 不動,
        那是使用者要看的原文,不該被我們改寫。
        """
        if not text:
            return ""
        return unicodedata.normalize("NFKC", text)

    def _extract_with_regex(self, text: str):
        text = self._normalize_for_matching(text)
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
