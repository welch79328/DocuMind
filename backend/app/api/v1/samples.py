"""
校正樣本 API

提供依類型檢視校正樣本 / 黃金範例、種子範例冷啟動匯入,以及黃金範例標記。
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.lib.document_types import normalize_document_type
from app.services.annotation_importer import (
    AnnotationImporter,
    InvalidAnnotationFormatError,
)
from app.services.correction_sample_service import CorrectionSampleService

router = APIRouter()


class SeedExample(BaseModel):
    input_ref: str
    corrected_fields: Dict[str, Any]
    layout_signature: str = ""
    purpose: str = "train"


class SeedRequest(BaseModel):
    examples: List[SeedExample]


class ImportRequest(BaseModel):
    file_path: str
    purpose: str = "holdout"


class GoldenRequest(BaseModel):
    is_golden: bool = True


def _error(status_code: int, detail: str, error_code: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"detail": detail, "error_code": error_code},
    )


def _resolve_type(document_type: str) -> Optional[str]:
    """正規化為權威型別字串;未知回傳 None"""
    normalized = normalize_document_type(document_type)
    return normalized.value if normalized is not None else None


@router.get("/{document_type}", summary="檢視校正樣本")
def list_samples(
    document_type: str,
    purpose: Optional[str] = Query(default=None, description="train / holdout"),
    golden_only: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    """檢視指定類型的校正樣本與累積量(可依 purpose / 黃金過濾)"""
    resolved = _resolve_type(document_type)
    if resolved is None:
        return _error(400, f"不支援的文件類型：{document_type}", "UNSUPPORTED_DOCUMENT_TYPE")

    service = CorrectionSampleService(db)
    samples = service.list_samples(resolved, purpose=purpose, golden_only=golden_only)
    return {"document_type": resolved, "count": len(samples), "samples": samples}


@router.post("/{document_type}/seed", summary="種子範例匯入")
def seed_samples(document_type: str, body: SeedRequest, db: Session = Depends(get_db)):
    """上線前手動準備標準答案冷啟動;種子可指定 purpose(train / holdout)"""
    resolved = _resolve_type(document_type)
    if resolved is None:
        return _error(400, f"不支援的文件類型：{document_type}", "UNSUPPORTED_DOCUMENT_TYPE")

    service = CorrectionSampleService(db)
    created_ids = []
    for example in body.examples:
        sid = service.save(
            document_type=resolved,
            input_ref=example.input_ref,
            corrected_fields=example.corrected_fields,
            layout_signature=example.layout_signature,
            purpose=example.purpose,
        )
        created_ids.append(str(sid))
    return {"created": len(created_ids), "ids": created_ids}


@router.post("/{document_type}/import", summary="標註檔匯入評估集")
def import_annotations(
    document_type: str, body: ImportRequest, db: Session = Depends(get_db)
):
    """
    將檔案型標註(ground truth JSON)匯入為校正樣本,預設用途為保留評估集
    (holdout),供 EvaluationService 作為基準來源。

    未標註(空值 / 佔位值)的項目會被略過並列於 skipped_refs,不寫入資料。
    """
    resolved = _resolve_type(document_type)
    if resolved is None:
        return _error(400, f"不支援的文件類型：{document_type}", "UNSUPPORTED_DOCUMENT_TYPE")

    importer = AnnotationImporter(CorrectionSampleService(db))
    try:
        report = importer.import_from_file(body.file_path, resolved, body.purpose)
    except FileNotFoundError as exc:
        return _error(404, str(exc), "ANNOTATION_FILE_NOT_FOUND")
    except InvalidAnnotationFormatError as exc:
        return _error(422, str(exc), "INVALID_ANNOTATION_FORMAT")

    return {"document_type": resolved, **report}


@router.post("/{sample_id}/golden", summary="標記黃金範例")
def mark_golden(sample_id: str, body: GoldenRequest, db: Session = Depends(get_db)):
    """標記 / 取消黃金範例"""
    service = CorrectionSampleService(db)
    try:
        service.mark_golden(sample_id, body.is_golden)
    except ValueError as exc:
        return _error(404, str(exc), "NOT_FOUND")
    return {"id": sample_id, "is_golden": body.is_golden}
