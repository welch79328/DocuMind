"""
基準測試執行器

以指定引擎組態對保留評估集(`CorrectionSample.purpose='holdout'`)執行辨識,
產出字元錯誤率(CER)、欄位準確率,以及**低信心攔截觸發率**——後者是後續分層
成本策略(cascade)是否具效益的唯一判斷依據,不得以假設替代實測。

本執行器的核心價值在於「會拒絕產出無效結果」:

1. **架構守衛**(需求 1.10):主力 OCR 引擎於 ARM64 有上游缺陷會導致程序中止,
   容器繼承主機架構故開發機必然觸發。此情況一律拋出
   `UnsupportedArchitectureError`,不得回報異常數值或空結果充當基準。
2. **樣本數守衛**(需求 1.6):樣本數低於門檻時拒絕標記為正式基準線,避免統計上
   無意義的數字被當作決策依據;探索性執行(is_baseline=False)仍可進行,但報告會
   標記 `baseline_eligible=False`。

觸發率一律經既有 `QualityAssessor` 判定,與線上複核入列採用同一套保守策略,
確保基準數字與實際攔截行為一致。

對應需求: 1.3, 1.4, 1.5, 1.6, 1.10
"""

from __future__ import annotations

import importlib.util
import inspect
import platform
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional, TypedDict

from app.config import settings
from app.lib.document_types import DocumentType
from app.lib.ocr_enhanced.quality_assessor import QualityAssessor

# 於 ARM64 有上游缺陷、會導致程序中止的引擎(生產與基準測試皆須 x86_64)
_ARM_INCOMPATIBLE_ENGINES = frozenset({"paddleocr"})

# ARM 架構識別字(不分大小寫)
_ARM_MACHINES = frozenset({"arm64", "aarch64", "armv7l", "armv8l"})

# 引擎名稱 → 可匯入模組名
_ENGINE_MODULES: Dict[str, str] = {
    "paddleocr": "paddleocr",
    "tesseract": "pytesseract",
    "textract": "boto3",
}

# EvaluationRecord.labeled_set_version 的欄位長度上限
_VERSION_MAX_LENGTH = 50


class EnvironmentCheck(TypedDict):
    """執行環境檢查結果"""

    architecture: str
    primary_engine_available: bool
    reason: Optional[str]


class BaselineReport(TypedDict):
    """基準測試報告"""

    document_type: str
    engine_profile: str
    cer: float
    field_accuracy: float
    sample_count: int
    review_trigger_rate: float
    per_field_accuracy: Dict[str, float]
    environment: EnvironmentCheck
    executed_at: str
    labeled_set_version: str
    baseline_eligible: bool
    warnings: List[str]


class UnsupportedArchitectureError(RuntimeError):
    """處理器架構不支援主力 OCR 引擎,拒絕產出基準(需求 1.10)"""


class InsufficientSamplesError(RuntimeError):
    """保留評估集樣本數低於門檻,拒絕標記為正式基準線(需求 1.6)"""


def _is_engine_installed(engine: str) -> bool:
    """檢查引擎所需套件是否可匯入(不實際載入模型)"""
    module_name = _ENGINE_MODULES.get(engine, engine)
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ValueError):
        return False


def _type_value(document_type: Any) -> str:
    if isinstance(document_type, DocumentType):
        return document_type.value
    return str(document_type)


class BaselineRunner:
    """基準測試執行器(辨識來源以 predictor 注入,便於在無 OCR 環境下驗證守衛邏輯)"""

    def __init__(
        self,
        evaluation_service: Any,
        predictor: Optional[Callable[[str], Awaitable[Dict[str, Any]]]] = None,
        min_samples: Optional[int] = None,
        threshold: Optional[float] = None,
        sample_service: Optional[Any] = None,
    ) -> None:
        """
        Args:
            evaluation_service: 既有評估服務(提供 CER / 欄位準確率與持久化)
            predictor: 辨識來源,`predictor(input_ref)` 回傳
                `{"fields": {...}, "confidence": float, "field_confidences": {...}}`
            min_samples: 正式基準線的最低樣本數;未提供時採 settings.BASELINE_MIN_SAMPLES
            threshold: 低信心攔截門檻;未提供時採 settings.OCR_QUALITY_THRESHOLD
            sample_service: 校正樣本服務;未提供時以評估服務的連線自建
        """
        self.evaluation_service = evaluation_service
        self.predictor = predictor
        self.min_samples = (
            min_samples if min_samples is not None else settings.BASELINE_MIN_SAMPLES
        )
        self.assessor = QualityAssessor(threshold)

        if sample_service is None:
            from app.services.correction_sample_service import CorrectionSampleService

            sample_service = CorrectionSampleService(evaluation_service.db)
        self.sample_service = sample_service

    # ------------------------------------------------------------------ #
    @staticmethod
    def check_environment(engines: Optional[List[str]] = None) -> EnvironmentCheck:
        """
        檢查執行環境是否可運行主力 OCR 引擎。

        Args:
            engines: 引擎組態(第一個為主力);未提供時採 settings.OCR_ENGINES

        Returns:
            EnvironmentCheck:架構、主力引擎是否可用、不可用事由
        """
        engine_list = engines if engines else list(settings.OCR_ENGINES)
        architecture = platform.machine()
        primary = engine_list[0] if engine_list else ""

        if primary and primary in _ARM_INCOMPATIBLE_ENGINES and (
            architecture.lower() in _ARM_MACHINES
        ):
            return {
                "architecture": architecture,
                "primary_engine_available": False,
                "reason": (
                    f"主力引擎 {primary} 於 {architecture} 有上游缺陷會導致程序中止,"
                    f"基準測試須於 x86_64 執行"
                ),
            }

        if primary and not _is_engine_installed(primary):
            return {
                "architecture": architecture,
                "primary_engine_available": False,
                "reason": f"主力引擎 {primary} 未安裝,無法執行基準測試",
            }

        return {
            "architecture": architecture,
            "primary_engine_available": True,
            "reason": None,
        }

    # ------------------------------------------------------------------ #
    async def run(
        self,
        document_type: Any,
        engine_profile: str,
        is_baseline: bool = False,
    ) -> BaselineReport:
        """
        對保留評估集執行基準測試。

        Args:
            document_type: 文件類型
            engine_profile: 引擎組態標記(例如 "paddleocr+tesseract")
            is_baseline: 是否標記為正式基準線

        Returns:
            BaselineReport

        Raises:
            UnsupportedArchitectureError: 處理器架構不支援主力引擎(需求 1.10)
            InsufficientSamplesError: 樣本數低於門檻且要求標記為基準線(需求 1.6)
            ValueError: 未提供辨識來源
        """
        doc_type = _type_value(document_type)

        # --- 守衛 1:執行環境(需求 1.10)------------------------------- #
        environment = self.check_environment(self._engines_of(engine_profile))
        if not environment["primary_engine_available"]:
            raise UnsupportedArchitectureError(environment["reason"])

        holdout = self.sample_service.list_samples(doc_type, purpose="holdout")
        sample_count = len(holdout)
        baseline_eligible = sample_count >= self.min_samples

        # --- 守衛 2:樣本數(需求 1.6)---------------------------------- #
        warnings: List[str] = []
        if not baseline_eligible:
            message = (
                f"樣本不足:保留評估集僅 {sample_count} 筆,低於門檻 "
                f"{self.min_samples} 筆,不得標記為正式基準線"
            )
            if is_baseline:
                raise InsufficientSamplesError(message)
            warnings.append(message)

        if self.predictor is None:
            raise ValueError("未提供辨識來源(predictor),無法執行基準測試")

        # --- 辨識與觸發率統計 ------------------------------------------ #
        predictions: Dict[str, Dict[str, Any]] = {}
        triggered = 0
        for sample in holdout:
            input_ref = sample["input_ref"]
            fields, decision, failure = await self._predict(input_ref)
            predictions[input_ref] = fields
            if decision["needs_review"]:
                triggered += 1
            if failure is not None:
                warnings.append(f"{input_ref}: 辨識失敗({failure}),計為最差結果")

        review_trigger_rate = (
            round(triggered / sample_count, 4) if sample_count else 0.0
        )

        # --- 指標計算與持久化 ------------------------------------------ #
        executed_at = datetime.now(timezone.utc)
        version = self._version_tag(engine_profile, executed_at)

        metrics = self.evaluation_service.evaluate(
            doc_type,
            predictions=predictions,
            holdout_version=version,
            is_baseline=is_baseline,
            persist=True,
        )
        # 無樣本時 evaluate() 不持久化,此處亦不得留下孤立的觸發率紀錄
        if sample_count:
            self.evaluation_service.record_metric(
                doc_type,
                metric_type="review_trigger_rate",
                value=review_trigger_rate,
                holdout_version=version,
                is_baseline=is_baseline,
            )

        return {
            "document_type": doc_type,
            "engine_profile": engine_profile,
            "cer": metrics["cer"],
            "field_accuracy": metrics["field_accuracy"],
            "sample_count": sample_count,
            "review_trigger_rate": review_trigger_rate,
            "per_field_accuracy": self._per_field_accuracy(holdout, predictions),
            "environment": environment,
            "executed_at": executed_at.isoformat(),
            "labeled_set_version": version,
            "baseline_eligible": baseline_eligible,
            "warnings": warnings,
        }

    # ------------------------------------------------------------------ #
    async def _predict(self, input_ref: str):
        """
        取得單筆預測與複核判定。

        辨識失敗不得中斷整批基準:計為空結果(最差),並回報事由。
        """
        try:
            outcome = self.predictor(input_ref)
            if inspect.isawaitable(outcome):
                outcome = await outcome
        except Exception as exc:  # noqa: BLE001 — 單筆失敗不得中斷整批
            decision = self.assessor.assess(0.0, None)
            return {}, decision, f"{type(exc).__name__}: {exc}"

        outcome = outcome or {}
        fields = outcome.get("fields") or {}
        confidence = float(outcome.get("confidence") or 0.0)
        decision = self.assessor.assess(
            confidence, outcome.get("field_confidences")
        )
        return fields, decision, None

    @staticmethod
    def _per_field_accuracy(
        holdout: List[Dict[str, Any]], predictions: Dict[str, Dict[str, Any]]
    ) -> Dict[str, float]:
        """逐欄位準確率:該欄位預測正確的樣本數 / 有標註該欄位的樣本數"""
        totals: Dict[str, int] = {}
        corrects: Dict[str, int] = {}
        for sample in holdout:
            truth = sample.get("corrected_fields") or {}
            pred = predictions.get(sample["input_ref"], {})
            for field, value in truth.items():
                totals[field] = totals.get(field, 0) + 1
                if pred.get(field) == value:
                    corrects[field] = corrects.get(field, 0) + 1
        return {
            field: round(corrects.get(field, 0) / count, 4)
            for field, count in totals.items()
        }

    @staticmethod
    def _engines_of(engine_profile: str) -> List[str]:
        """由引擎組態標記解析引擎清單(例如 "paddleocr+tesseract")"""
        return [part.strip() for part in engine_profile.split("+") if part.strip()]

    @staticmethod
    def _version_tag(engine_profile: str, executed_at: datetime) -> str:
        """組出含引擎組態與執行時間的標註集版本標記(受欄位長度限制)"""
        stamp = executed_at.strftime("%Y%m%dT%H%M%SZ")
        return f"{engine_profile}@{stamp}"[:_VERSION_MAX_LENGTH]
