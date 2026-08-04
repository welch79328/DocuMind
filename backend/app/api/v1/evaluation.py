"""
評估 API

提供各文件類型的準確率檢視(最新/基準線指標 + 樣本累積量),
以及以標註集重新評估並產出前後對照。
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.lib.document_types import normalize_document_type
from app.services.baseline_runner import (
    BaselineRunner,
    InsufficientSamplesError,
    UnsupportedArchitectureError,
)
from app.services.evaluation_service import EvaluationService
from app.services.correction_sample_service import CorrectionSampleService

router = APIRouter()


class RunRequest(BaseModel):
    predictions: Dict[str, Dict[str, Any]]
    holdout_version: str = "v1"
    is_baseline: bool = False
    compare_to: Optional[str] = None


class BaselineRequest(BaseModel):
    engine_profile: str
    is_baseline: bool = False
    # 辨識來源:{input_ref: 欄位} 與 {input_ref: 信心度}
    # 基準測試須於可執行主力引擎的 x86 環境產出後提供(需求 1.10)
    predictions: Optional[Dict[str, Dict[str, Any]]] = None
    confidences: Optional[Dict[str, float]] = None
    field_confidences: Optional[Dict[str, Dict[str, float]]] = None
    min_samples: Optional[int] = None


def _error(status_code: int, detail: str, error_code: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"detail": detail, "error_code": error_code},
    )


def _resolve_type(document_type: str) -> Optional[str]:
    normalized = normalize_document_type(document_type)
    return normalized.value if normalized is not None else None


@router.get("/{document_type}", summary="評估指標檢視")
def get_evaluation(document_type: str, db: Session = Depends(get_db)):
    """回傳最新/基準線指標與各 purpose 樣本累積量"""
    resolved = _resolve_type(document_type)
    if resolved is None:
        return _error(400, f"不支援的文件類型：{document_type}", "UNSUPPORTED_DOCUMENT_TYPE")

    eval_svc = EvaluationService(db)
    samples = CorrectionSampleService(db)
    summary = eval_svc.summary(resolved)
    return {
        "document_type": resolved,
        "latest": summary["latest"],
        "baseline": summary["baseline"],
        "sample_counts": {
            "holdout": samples.count(resolved, purpose="holdout"),
            "train": samples.count(resolved, purpose="train"),
        },
        "records": eval_svc.list_records(resolved),
    }


@router.post("/{document_type}/run", summary="以標註集重新評估")
def run_evaluation(document_type: str, body: RunRequest, db: Session = Depends(get_db)):
    """以提供的預測對保留評估集重新評估;可對照指定版本產出前後差異"""
    resolved = _resolve_type(document_type)
    if resolved is None:
        return _error(400, f"不支援的文件類型：{document_type}", "UNSUPPORTED_DOCUMENT_TYPE")

    eval_svc = EvaluationService(db)
    metrics = eval_svc.evaluate(
        resolved,
        predictions=body.predictions,
        holdout_version=body.holdout_version,
        is_baseline=body.is_baseline,
    )

    comparison = None
    if body.compare_to is not None:
        comparison = eval_svc.compare(resolved, body.compare_to, body.holdout_version)

    return {"metrics": metrics, "comparison": comparison}


@router.post("/{document_type}/baseline", summary="執行基準測試")
async def run_baseline(
    document_type: str, body: BaselineRequest, db: Session = Depends(get_db)
):
    """
    以指定引擎組態對保留評估集產出基準:CER、欄位準確率,以及低信心攔截觸發率
    (後續分層成本策略是否具效益的判斷依據)。

    兩條拒絕路徑一律回 409,不以異常數值或空結果冒充基準:
    架構不支援主力引擎(需求 1.10)、樣本數低於門檻(需求 1.6)。
    """
    resolved = _resolve_type(document_type)
    if resolved is None:
        return _error(400, f"不支援的文件類型：{document_type}", "UNSUPPORTED_DOCUMENT_TYPE")

    if body.predictions is None:
        return _error(
            422,
            "未提供辨識來源(predictions);基準測試須於可執行主力引擎的環境產出後提供",
            "MISSING_PREDICTIONS",
        )

    predictions = body.predictions
    confidences = body.confidences or {}
    field_confidences = body.field_confidences or {}

    async def predictor(input_ref: str) -> Dict[str, Any]:
        return {
            "fields": predictions.get(input_ref, {}),
            "confidence": confidences.get(input_ref, 0.0),
            "field_confidences": field_confidences.get(input_ref),
        }

    runner = BaselineRunner(
        EvaluationService(db), predictor=predictor, min_samples=body.min_samples
    )
    try:
        report = await runner.run(resolved, body.engine_profile, body.is_baseline)
    except UnsupportedArchitectureError as exc:
        return _error(409, str(exc), "UNSUPPORTED_ARCHITECTURE")
    except InsufficientSamplesError as exc:
        return _error(409, str(exc), "INSUFFICIENT_SAMPLES")

    return report
