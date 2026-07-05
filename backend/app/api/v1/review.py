"""
人工複核佇列 API

提供複核佇列的列表、認領、提交校正、釋出端點。
沿用專案的繁中錯誤格式:{"detail": ..., "error_code": ...}
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.review_queue_service import ReviewQueueService
from app.services.correction_sample_service import CorrectionSampleService

router = APIRouter()


class ClaimRequest(BaseModel):
    reviewer: str


class ReleaseRequest(BaseModel):
    reviewer: str


class SubmitRequest(BaseModel):
    reviewer: str
    corrected_fields: Dict[str, Any]


def _error(status_code: int, detail: str, error_code: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"detail": detail, "error_code": error_code},
    )


@router.get("/queue", summary="複核佇列列表")
def list_queue(
    status: Optional[str] = Query(default=None, description="狀態過濾:pending / in_review / completed"),
    db: Session = Depends(get_db),
):
    """列出複核佇列項目,可依狀態過濾"""
    service = ReviewQueueService(db)
    return {"items": service.list_queue(status=status)}


@router.get("/{item_id}", summary="取得單一複核項目")
def get_item(item_id: str, db: Session = Depends(get_db)):
    """取得單一複核項目(供校正頁載入原文與欄位)"""
    service = ReviewQueueService(db)
    try:
        return service.get_item(item_id)
    except ValueError as exc:
        return _error(404, str(exc), "NOT_FOUND")


@router.post("/{item_id}/claim", summary="認領複核項目")
def claim(item_id: str, body: ClaimRequest, db: Session = Depends(get_db)):
    """認領並鎖定一份文件;已被他人認領時回傳 409"""
    service = ReviewQueueService(db)
    if not service.claim(item_id, body.reviewer):
        return _error(409, "此複核項目已被他人認領或不存在", "ALREADY_CLAIMED")
    return {"claimed": True}


@router.post("/{item_id}/submit", summary="提交校正")
def submit(item_id: str, body: SubmitRequest, db: Session = Depends(get_db)):
    """提交校正結果;僅認領者可提交,記錄前後差異並轉 completed,並將校正沉澱為樣本"""
    service = ReviewQueueService(db, sample_service=CorrectionSampleService(db))
    try:
        diff = service.submit_correction(item_id, body.reviewer, body.corrected_fields)
    except ValueError as exc:
        return _error(404, str(exc), "NOT_FOUND")
    except PermissionError as exc:
        return _error(403, str(exc), "FORBIDDEN")
    return {"status": "completed", "diff": diff}


@router.post("/{item_id}/release", summary="釋出認領")
def release(item_id: str, body: ReleaseRequest, db: Session = Depends(get_db)):
    """釋出認領,狀態回 pending 供他人重新認領;僅認領者可釋出"""
    service = ReviewQueueService(db)
    try:
        service.release(item_id, body.reviewer)
    except ValueError as exc:
        return _error(404, str(exc), "NOT_FOUND")
    except PermissionError as exc:
        return _error(403, str(exc), "FORBIDDEN")
    return {"status": "pending"}
