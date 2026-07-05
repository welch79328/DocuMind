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
from app.services.evaluation_service import EvaluationService
from app.services.correction_sample_service import CorrectionSampleService

router = APIRouter()


class RunRequest(BaseModel):
    predictions: Dict[str, Dict[str, Any]]
    holdout_version: str = "v1"
    is_baseline: bool = False
    compare_to: Optional[str] = None


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
