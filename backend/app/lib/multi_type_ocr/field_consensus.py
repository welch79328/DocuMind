"""
欄位層共識解析

以「多引擎對同一欄位是否得出相同結果」作為信心度訊號,取代對單一模型自評
信心度的信任。

**為什麼需要這一層**:傳統 OCR 誤判產出亂碼(肉眼可見),生成式模型誤判則產出
語法合法但數值錯誤的內容(隱形),且模型自評信心度的可靠度隨模型能力大幅變動。
既有 `QualityAssessor` 與人工複核機制完全建立在信心度之上——若信心度來源失準,
整套攔截機制會同步失效而毫無徵兆。共識訊號不依賴任何單一模型的自我評估。

**邊界**:本層只產生訊號,不做判定。是否需人工複核完全交由既有 `QualityAssessor`
依門檻決定,故其介面零變更(需求 6.2)。

規則:
- 全部一致   → 採該值,信心度取各引擎之**最小值**(保守)
- 不一致     → 採最高信心度候選之值,信心度**壓低**至懲罰值(只能往下)
- 僅單一候選 → 退回單引擎信心度,標記 `consensus_available=False`,不偽報共識

對應需求: 4.1, 4.2, 4.4, 4.5, 4.7
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict

from .field_normalizer import FieldNormalizer

# 不一致時的信心度懲罰值(0-1);低於既有 OCR_QUALITY_THRESHOLD 才能觸發複核
DEFAULT_DISAGREE_PENALTY = 0.3

# 抽取結果中屬統計/旗標而非欄位值的鍵
_META_KEYS = frozenset({
    "field_confidences",
    "needs_confirmation",
    "extraction_confidence",
    "llm_used_for_extraction",
})


class FieldCandidate(TypedDict):
    """
    單一引擎的欄位抽取結果。

    來源限定為**規則式(regex)抽取**——共識路徑不得對各候選觸發 LLM,否則 LLM
    呼叫次數將隨候選數倍增,直接衝擊成本約束。
    """

    engine: str
    fields: Dict[str, Any]
    field_confidences: Dict[str, float]
    extraction_method: str


class FieldAgreement(TypedDict):
    """單一欄位的共識狀態"""

    value: Any
    confidence: float
    agreed: bool
    engine_values: Dict[str, Any]


class ConsensusResult(TypedDict):
    """共識解析結果"""

    fields: Dict[str, Any]
    field_confidences: Dict[str, float]
    agreements: Dict[str, FieldAgreement]
    consensus_available: bool


def field_candidate_from_extraction(
    engine: str, extracted: Optional[Dict[str, Any]]
) -> FieldCandidate:
    """
    將既有欄位抽取結果轉為共識候選。

    需同時支援兩種既有輸出形狀:
    - **扁平 + 逐欄位信心度**(謄本 / 帳單,`RegexFieldExtractor`)
    - **巢狀 + 僅整體信心度**(合約,`ContractFieldExtractor`)

    巢狀結構會被攤平一層(如 `contract_metadata.contract_number` → `contract_number`);
    無逐欄位信心度時,以整體 `extraction_confidence` 作為每個欄位的信心度。
    """
    extracted = extracted or {}
    fields: Dict[str, Any] = {}

    for key, value in extracted.items():
        if key in _META_KEYS:
            continue
        if isinstance(value, dict):
            # 巢狀區塊攤平一層(合約形狀)
            fields.update(value)
        else:
            fields[key] = value

    declared = extracted.get("field_confidences")
    if isinstance(declared, dict) and declared:
        confidences = {key: float(declared.get(key, 0.0)) for key in fields}
    else:
        overall = float(extracted.get("extraction_confidence") or 0.0)
        confidences = {key: overall for key in fields}

    return {
        "engine": engine,
        "fields": fields,
        "field_confidences": confidences,
        "extraction_method": "regex",
    }


class FieldConsensusResolver:
    """欄位層共識解析器(純運算,無外部依賴)"""

    def __init__(
        self,
        normalizer: Optional[FieldNormalizer] = None,
        disagree_penalty: Optional[float] = None,
    ) -> None:
        """
        Args:
            normalizer: 欄位值正規化器;未提供時採預設規則
            disagree_penalty: 不一致時的信心度上限;未提供時採設定值
        """
        self.normalizer = normalizer or FieldNormalizer()
        if disagree_penalty is None:
            disagree_penalty = self._configured_penalty()
        self.disagree_penalty = disagree_penalty

    # ------------------------------------------------------------------ #
    def resolve(self, candidates: List[FieldCandidate]) -> ConsensusResult:
        """
        逐欄位比對多個候選,產出共識結果。

        Args:
            candidates: 各引擎的規則式欄位抽取結果

        Returns:
            ConsensusResult:合併欄位、欄位信心度、逐欄位共識明細、共識是否可用
        """
        if not candidates:
            return {
                "fields": {},
                "field_confidences": {},
                "agreements": {},
                "consensus_available": False,
            }

        consensus_available = len(candidates) > 1
        field_names = self._field_names(candidates)

        fields: Dict[str, Any] = {}
        field_confidences: Dict[str, float] = {}
        agreements: Dict[str, FieldAgreement] = {}

        for field in field_names:
            agreement = self._resolve_field(field, candidates, consensus_available)
            agreements[field] = agreement
            fields[field] = agreement["value"]
            field_confidences[field] = agreement["confidence"]

        return {
            "fields": fields,
            "field_confidences": field_confidences,
            "agreements": agreements,
            "consensus_available": consensus_available,
        }

    def normalize(self, field_name: str, value: Any) -> Any:
        """欄位值正規化(比對前套用,避免格式差異被誤判為不一致)"""
        return self.normalizer.normalize(field_name, value)

    # ------------------------------------------------------------------ #
    def _resolve_field(
        self,
        field: str,
        candidates: List[FieldCandidate],
        consensus_available: bool,
    ) -> FieldAgreement:
        engine_values = {
            candidate["engine"]: candidate["fields"].get(field)
            for candidate in candidates
        }
        confidences = [
            float(candidate["field_confidences"].get(field, 0.0))
            for candidate in candidates
        ]

        # 單一候選:退回該引擎信心度,不宣稱已達成共識(需求 4.5)
        if not consensus_available:
            only = candidates[0]
            return {
                "value": only["fields"].get(field),
                "confidence": confidences[0],
                "agreed": False,
                "engine_values": engine_values,
            }

        agreed = self._all_agree(field, candidates)
        preferred = self._highest_confidence_value(field, candidates)

        if agreed:
            confidence = min(confidences)
        else:
            # 壓低只能往下:原本更低的信心度不得被懲罰值抬高
            confidence = min(max(confidences), self.disagree_penalty)

        return {
            "value": preferred,
            "confidence": round(confidence, 4),
            "agreed": agreed,
            "engine_values": engine_values,
        }

    def _all_agree(self, field: str, candidates: List[FieldCandidate]) -> bool:
        """
        逐對比較所有候選。

        數值型別的容差比較不具遞移性(a≈b 且 b≈c 不保證 a≈c),故不可只與第一個
        候選比對,必須兩兩比較。
        """
        for i in range(len(candidates)):
            for j in range(i + 1, len(candidates)):
                if not self.normalizer.values_agree(
                    field,
                    candidates[i]["fields"].get(field),
                    candidates[j]["fields"].get(field),
                ):
                    return False
        return True

    @staticmethod
    def _highest_confidence_value(
        field: str, candidates: List[FieldCandidate]
    ) -> Any:
        """取信心度最高且**有值**的候選之原始值;全部無值時回傳 None"""
        with_value = [
            candidate for candidate in candidates
            if candidate["fields"].get(field) is not None
        ]
        if not with_value:
            return None
        best = max(
            with_value,
            key=lambda c: float(c["field_confidences"].get(field, 0.0)),
        )
        return best["fields"].get(field)

    @staticmethod
    def _field_names(candidates: List[FieldCandidate]) -> List[str]:
        """所有候選欄位名的聯集,維持首次出現順序以利閱讀"""
        names: List[str] = []
        for candidate in candidates:
            for field in candidate["fields"]:
                if field not in names:
                    names.append(field)
        return names

    @staticmethod
    def _configured_penalty() -> float:
        from app.config import settings

        return float(
            getattr(settings, "OCR_CONSENSUS_DISAGREE_PENALTY", DEFAULT_DISAGREE_PENALTY)
        )
