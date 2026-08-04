"""
評估服務

以「保留評估集」(CorrectionSample.purpose='holdout')為 ground truth,計算
字元錯誤率(CER)與欄位級準確率,並持久化為 EvaluationRecord;支援基準線與前後對照。

資料隔離(防洩漏):評估一律僅讀 purpose='holdout',絕不觸及 few-shot 訓練池(train)。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict

from sqlalchemy.orm import Session

from app.lib.document_types import DocumentType
from app.models.correction_sample import CorrectionSample
from app.models.evaluation_record import EvaluationRecord

HOLDOUT = "holdout"


class EvalMetrics(TypedDict):
    cer: float
    field_accuracy: float
    sample_count: int


def _type_value(document_type: Any) -> str:
    if isinstance(document_type, DocumentType):
        return document_type.value
    return str(document_type)


# --------------------------------------------------------------------------- #
# 純指標函數
# --------------------------------------------------------------------------- #
def levenshtein(a: str, b: str) -> int:
    """計算兩字串的編輯距離(Levenshtein)"""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            current.append(min(
                previous[j] + 1,       # 刪除
                current[j - 1] + 1,    # 插入
                previous[j - 1] + cost,  # 替換
            ))
        previous = current
    return previous[-1]


def character_error_rate(pred_text: str, truth_text: str) -> float:
    """字元錯誤率 = 編輯距離 / 真值長度(真值為空時回 0)"""
    if not truth_text:
        return 0.0
    return levenshtein(pred_text, truth_text) / len(truth_text)


def field_accuracy(pred_fields: Dict[str, Any], truth_fields: Dict[str, Any]) -> float:
    """欄位準確率 = 預測正確的欄位數 / 真值欄位總數(真值為空時回 1.0)"""
    if not truth_fields:
        return 1.0
    correct = sum(
        1 for key, value in truth_fields.items()
        if pred_fields.get(key) == value
    )
    return correct / len(truth_fields)


def _canonical_text(fields: Dict[str, Any]) -> str:
    """將欄位字典轉為穩定文字表示,供 CER 計算"""
    return "\n".join(f"{k}={fields.get(k)}" for k in sorted(fields))


# --------------------------------------------------------------------------- #
class EvaluationService:
    """準確率評估與基準線 / 前後對照(同步資料庫存取)"""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------ #
    def evaluate(
        self,
        document_type: Any,
        predictions: Dict[str, Dict[str, Any]],
        holdout_version: str = "v1",
        is_baseline: bool = False,
        persist: bool = True,
    ) -> EvalMetrics:
        """
        以保留評估集計算 CER 與欄位準確率。

        Args:
            document_type: 文件類型
            predictions: {input_ref: 預測欄位};缺漏者視為最差(0 準確、CER 1.0)
            holdout_version: 標註集版本標記
            is_baseline: 是否記錄為基準線
            persist: 是否寫入 EvaluationRecord

        Returns:
            EvalMetrics:{cer, field_accuracy, sample_count}
        """
        holdout = self._load_holdout(document_type)
        if not holdout:
            return {"cer": 0.0, "field_accuracy": 0.0, "sample_count": 0}

        cer_values: List[float] = []
        acc_values: List[float] = []
        for sample in holdout:
            truth = sample.corrected_fields or {}
            pred = predictions.get(sample.input_ref, {})
            acc_values.append(field_accuracy(pred, truth))
            cer_values.append(
                character_error_rate(_canonical_text(pred), _canonical_text(truth))
            )

        metrics: EvalMetrics = {
            "cer": round(sum(cer_values) / len(cer_values), 4),
            "field_accuracy": round(sum(acc_values) / len(acc_values), 4),
            "sample_count": len(holdout),
        }

        if persist:
            self._persist(document_type, metrics, holdout_version, is_baseline)
        return metrics

    # ------------------------------------------------------------------ #
    def record_baseline(
        self, document_type: Any, metrics: EvalMetrics, holdout_version: str = "baseline"
    ) -> None:
        """將指標記錄為基準線"""
        self._persist(document_type, metrics, holdout_version, is_baseline=True)

    # ------------------------------------------------------------------ #
    def record_metric(
        self,
        document_type: Any,
        metric_type: str,
        value: float,
        holdout_version: str = "v1",
        is_baseline: bool = False,
    ) -> None:
        """
        記錄單一指標(供 CER / 欄位準確率以外的量測使用,例如低信心攔截觸發率)。

        不改變既有 evaluate / record_baseline 的行為,僅補上單點寫入能力。
        """
        self.db.add(EvaluationRecord(
            document_type=_type_value(document_type),
            metric_type=metric_type,
            value=value,
            labeled_set_version=holdout_version,
            is_baseline=is_baseline,
        ))
        self.db.commit()

    # ------------------------------------------------------------------ #
    def compare(
        self, document_type: Any, before_version: str, after_version: str
    ) -> Dict[str, Dict[str, float]]:
        """比較兩個版本的指標,回傳每個指標的 before / after / delta"""
        result: Dict[str, Dict[str, float]] = {}
        for metric_type in ("cer", "field_accuracy"):
            before = self._latest_value(document_type, metric_type, before_version)
            after = self._latest_value(document_type, metric_type, after_version)
            result[metric_type] = {
                "before": before,
                "after": after,
                "delta": (after - before) if (before is not None and after is not None) else None,
            }
        return result

    # ------------------------------------------------------------------ #
    def summary(self, document_type: Any) -> Dict[str, Optional[Dict[str, Any]]]:
        """回傳最新指標與基準線指標(各含 cer / field_accuracy / version)"""
        records = (
            self.db.query(EvaluationRecord)
            .filter(EvaluationRecord.document_type == _type_value(document_type))
            .order_by(EvaluationRecord.created_at.asc())
            .all()
        )
        if not records:
            return {"latest": None, "baseline": None}

        latest_version = records[-1].labeled_set_version
        baseline_records = [r for r in records if r.is_baseline]
        baseline_version = baseline_records[-1].labeled_set_version if baseline_records else None

        def _collect(version: Optional[str]) -> Optional[Dict[str, Any]]:
            if version is None:
                return None
            metrics = {
                r.metric_type: float(r.value)
                for r in records if r.labeled_set_version == version
            }
            if not metrics:
                return None
            return {**metrics, "version": version}

        return {"latest": _collect(latest_version), "baseline": _collect(baseline_version)}

    # ------------------------------------------------------------------ #
    def readiness_for_finetune(
        self,
        document_type: Any,
        min_samples: Optional[int] = None,
        target_accuracy: Optional[float] = None,
        improvement_epsilon: float = 0.02,
    ) -> Dict[str, Any]:
        """
        fine-tune 就緒判斷(需求 9;僅決策,不執行訓練)。

        當「訓練池樣本量達門檻」且「holdout 欄位準確率低於目標且停滯」時,標示可評估
        fine-tune 並附前後對照;否則維持 few-shot。
        """
        from app.config import settings
        from app.services.correction_sample_service import CorrectionSampleService

        min_samples = min_samples if min_samples is not None else settings.FINETUNE_MIN_SAMPLES
        target = target_accuracy if target_accuracy is not None else settings.FINETUNE_TARGET_ACCURACY

        train_count = CorrectionSampleService(self.db).count(document_type, "train")
        history = [
            r["value"] for r in self.list_records(document_type)
            if r["metric_type"] == "field_accuracy"
        ]
        latest = history[-1] if history else None

        comparison = None
        if len(history) >= 2:
            comparison = {
                "first": history[0],
                "latest": history[-1],
                "delta": round(history[-1] - history[0], 4),
            }

        stalled = len(history) >= 2 and (history[-1] - history[-2]) < improvement_epsilon

        if train_count < min_samples:
            ready, reason = False, f"訓練樣本不足({train_count}/{min_samples}),維持 few-shot"
        elif latest is None:
            ready, reason = False, "尚無 holdout 評估,維持 few-shot"
        elif latest >= target:
            ready, reason = False, f"few-shot 準確率已達目標({latest}≥{target}),維持 few-shot"
        elif not stalled:
            ready, reason = False, "準確率仍在提升,維持 few-shot"
        else:
            ready, reason = True, (
                f"訓練樣本量足({train_count})且準確率停滯於目標下({latest}<{target}),"
                f"可評估 fine-tune(需人工核准)"
            )

        return {
            "document_type": _type_value(document_type),
            "ready": ready,
            "reason": reason,
            "train_sample_count": train_count,
            "min_samples": min_samples,
            "latest_field_accuracy": latest,
            "target_accuracy": target,
            "comparison": comparison,
        }

    def record_finetune_decision(
        self, document_type: Any, approver: str, approved: bool
    ) -> None:
        """記錄 fine-tune 決策的人工核准(附核准者)"""
        self.db.add(EvaluationRecord(
            document_type=_type_value(document_type),
            metric_type="finetune_decision",
            value=1.0 if approved else 0.0,
            labeled_set_version=approver,
            is_baseline=False,
        ))
        self.db.commit()

    # ------------------------------------------------------------------ #
    def list_records(self, document_type: Any) -> List[Dict[str, Any]]:
        """列出指定類型的評估紀錄"""
        records = (
            self.db.query(EvaluationRecord)
            .filter(EvaluationRecord.document_type == _type_value(document_type))
            .order_by(EvaluationRecord.created_at.asc())
            .all()
        )
        return [
            {
                "metric_type": r.metric_type,
                "value": float(r.value),
                "labeled_set_version": r.labeled_set_version,
                "is_baseline": r.is_baseline,
            }
            for r in records
        ]

    # ------------------------------------------------------------------ #
    def _load_holdout(self, document_type: Any) -> List[CorrectionSample]:
        """僅載入 purpose='holdout' 樣本(防洩漏:絕不讀取 train)"""
        return (
            self.db.query(CorrectionSample)
            .filter(
                CorrectionSample.document_type == _type_value(document_type),
                CorrectionSample.purpose == HOLDOUT,
            )
            .all()
        )

    def _persist(
        self, document_type: Any, metrics: EvalMetrics, version: str, is_baseline: bool
    ) -> None:
        doc_type = _type_value(document_type)
        for metric_type in ("cer", "field_accuracy"):
            self.db.add(EvaluationRecord(
                document_type=doc_type,
                metric_type=metric_type,
                value=metrics[metric_type],
                labeled_set_version=version,
                is_baseline=is_baseline,
            ))
        self.db.commit()

    def _latest_value(
        self, document_type: Any, metric_type: str, version: str
    ) -> Optional[float]:
        record = (
            self.db.query(EvaluationRecord)
            .filter(
                EvaluationRecord.document_type == _type_value(document_type),
                EvaluationRecord.metric_type == metric_type,
                EvaluationRecord.labeled_set_version == version,
            )
            .order_by(EvaluationRecord.created_at.desc())
            .first()
        )
        return float(record.value) if record is not None else None
