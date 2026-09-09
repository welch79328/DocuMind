"""
統一分析 API

提供單一端點完成文件上傳、OCR 辨識、結構化欄位提取、AI 問答。
"""

import logging

import asyncio

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import List, Optional

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from app.schemas.analyze import (
    AnalyzeResponse,
    BatchAnalyzeResponse,
    BatchItemResult,
)
from app.services.analyze_service import (
    AnalyzeService,
    _merge_page_structured_data,
    _scored_fields_from_pages,
)
from app.database import get_db
from app.models.api_usage_log import ApiUsageLog
from app.lib.document_types import (
    SUPPORTED_EXTENSIONS,
    normalize_document_type,
    is_extension_allowed,
)
from app.lib.multi_type_ocr.processor_factory import ProcessorFactory
from app.lib.ocr_enhanced.quality_assessor import QualityAssessor
from app.services.review_queue_service import ReviewQueueService
from app.services.correction_sample_service import CorrectionSampleService
from app.services.few_shot_selector import FewShotSelector

logger = logging.getLogger(__name__)

router = APIRouter()

# 檔案大小限制 (20MB)
MAX_FILE_SIZE = 20 * 1024 * 1024

# 批次一次最多幾張。上限不是技術限制,是成本與逾時的閘門:
# 每張都是一次 VLM 呼叫,20 張已經是幾十秒等級的同步請求。
MAX_BATCH_FILES = 20

# 批次併發度。每張照片是一次遠端 VLM 呼叫(等網路,不吃本機記憶體),
# 所以可以重疊;但仍設上限,避免一次打爆上游的速率限制。
# 記憶體上界 = 併發度 x MAX_FILE_SIZE = 4 x 20MB = 80MB。
BATCH_MAX_CONCURRENT = 4


def _file_extension(file: UploadFile) -> str:
    """取得上傳檔案的小寫副檔名(含點),無副檔名則回傳空字串"""
    filename = file.filename or ""
    if "." in filename:
        return "." + filename.rsplit(".", 1)[-1].lower()
    return ""


class AnalyzeError(Exception):
    """分析 API 錯誤"""
    def __init__(self, status_code: int, detail: str, error_code: str):
        self.status_code = status_code
        self.detail = detail
        self.error_code = error_code


def _validate_file(file: UploadFile) -> None:
    """驗證上傳檔案的格式"""
    ext = _file_extension(file)

    if ext not in SUPPORTED_EXTENSIONS:
        raise AnalyzeError(
            status_code=400,
            detail=f"不支援的檔案格式：{ext or '未知'}。支援的格式：PDF、JPG、JPEG、PNG",
            error_code="UNSUPPORTED_FILE_TYPE",
        )


def _resolve_document_type(document_type: str) -> str:
    """
    正規化並驗證文件類型

    - 將舊型別別名(如 lease)正規化為權威型別(contract)
    - 依工廠動態產生的白名單驗證(僅已註冊處理器的型別可路由)
    - 未指定 / 未知 / 未註冊者拋出繁中錯誤

    Returns:
        正規化後的權威型別字串(例如 "contract")
    """
    supported = [str(t) for t in ProcessorFactory.supported_types()]
    normalized = normalize_document_type(document_type)

    if normalized is None or normalized.value not in supported:
        supported_display = "、".join(supported)
        raise AnalyzeError(
            status_code=400,
            detail=(
                f"不支援的文件類型：{document_type or '未指定'}。"
                f"支援的類型：{supported_display}"
            ),
            error_code="UNSUPPORTED_DOCUMENT_TYPE",
        )

    return normalized.value


async def _validate_and_read(file: UploadFile, resolved_document_type: str) -> bytes:
    """驗證單一上傳檔並讀進記憶體。

    單張與批次共用同一套驗證,避免兩條路徑對「什麼叫合法檔案」有兩種答案。
    任何一關不過都丟 AnalyzeError,由呼叫端決定要回 4xx 還是記成該筆失敗。
    """
    _validate_file(file)
    _validate_type_file_compatibility(resolved_document_type, file)

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise AnalyzeError(
            status_code=413,
            detail=f"檔案大小超過限制：{MAX_FILE_SIZE // (1024 * 1024)}MB",
            error_code="FILE_TOO_LARGE",
        )
    return contents


def _apply_confidence_gating(result: dict, db: Session) -> None:
    """
    信心度攔截(任務 3.3)

    跨頁彙整信心度,以 QualityAssessor 判定是否需人工複核;低信心自動入複核佇列,
    並於回應加上 needs_review / review_item_id / field_confidences。高信心則放行。
    就地修改 result。

    2026-09-03 修正:原本用 `field_confidences.update(page_fields)` 逐頁覆蓋,
    後面頁面即使沒抽到某欄位(信心度 0.0)也會蓋掉前面頁面已抽到的高信心度值
    ——實測一份 4 頁謄本,4/5 個欄位的信心度因此被錯誤地覆蓋成 0.0,
    導致明明已抽到的欄位仍被判定需要複核。改用 `_merge_page_structured_data`
    (與 document_fields 同一套邏輯):field_confidences 取各頁最大值,
    反映「這份文件目前看到的最佳信心度」,而不是任意一頁的殘值。
    """
    pages = result.get("pages") or []

    # OCR 信心度取各頁最小值(保守):任一頁辨識困難都應反映在整體判斷
    page_confidences = [
        p["ocr_raw"]["confidence"]
        for p in pages
        if p.get("ocr_raw") and p["ocr_raw"].get("confidence") is not None
    ]
    overall_ocr_confidence = min(page_confidences) if page_confidences else 1.0

    merged = _merge_page_structured_data(pages) or {}
    field_confidences: dict = merged.get("field_confidences") or {}
    if not isinstance(field_confidences, dict):
        field_confidences = {}

    # 複核判定只看「應評分的欄位」,與 document_fields 的重算採同一組。
    #
    # 2026-09-04 實測:NFKC 修正後 17 個欄位全為 0.9、needs_confirmation 為空,
    # needs_review 卻仍是 True——因為 QualityAssessor 取最差值,而
    # field_confidences 裡還有 6 個選配欄位是 0.0(附屬建物、共有部分、
    # 查封註記等,這份謄本本來就沒有)。等於一份抽得完整的謄本,
    # 因為「沒有附屬建物」「沒有被查封」而被判定需要人工複核。
    #
    # field_confidences 仍完整回傳給下游(它要知道每個欄位的狀態),
    # 只是判定時排除從未出現在任何一頁的選配欄位。
    scored_keys = _scored_fields_from_pages(pages)
    gating_confidences = (
        {k: v for k, v in field_confidences.items() if k in scored_keys}
        if scored_keys else field_confidences
    )

    decision = QualityAssessor().assess(overall_ocr_confidence, gating_confidences)

    result["needs_review"] = decision["needs_review"]
    result["field_confidences"] = field_confidences
    result["review_item_id"] = None

    if decision["needs_review"]:
        review_id = ReviewQueueService(db).enqueue(
            document_id=None,  # analyze 流程無狀態,佇列項目以快照自足
            document_type=result.get("document_type"),
            overall_confidence=decision["overall_confidence"],
            result={"pages": pages, "field_confidences": field_confidences},
        )
        result["review_item_id"] = str(review_id)


def _validate_type_file_compatibility(document_type: str, file: UploadFile) -> None:
    """驗證檔案格式與所選文件類型是否相容(需求 1.5)"""
    ext = _file_extension(file)
    normalized = normalize_document_type(document_type)
    if normalized is not None and not is_extension_allowed(normalized, ext):
        raise AnalyzeError(
            status_code=400,
            detail=(
                f"檔案格式 {ext or '未知'} 與文件類型「{document_type}」不相容。"
                f"請確認上傳的檔案格式正確。"
            ),
            error_code="INCOMPATIBLE_FILE_TYPE",
        )


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    summary="統一文件分析",
    responses={
        200: {
            "description": "分析成功",
            "content": {
                "application/json": {
                    "example": {
                        "file_name": "謄本.pdf",
                        "file_url": "https://d1h2hzes3rmzug.cloudfront.net/uploads/ocr_transcripts/uuid.pdf",
                        "document_type": "transcript",
                        "total_pages": 1,
                        "pages": [{
                            "page_number": 1,
                            "ocr_raw": {"text": "土地登記第三類謄本...", "confidence": 0.85},
                            "rule_postprocessed": {
                                "text": "土地登記第三類謄本...",
                                "stats": {"typo_fixes": 12, "format_corrections": 3}
                            },
                            "llm_postprocessed": {
                                "text": "土地登記第三類謄本...",
                                "stats": {"llm_used": True, "llm_cost": 0.02},
                                "used": True
                            },
                            "structured_data": None
                        }],
                        "answer": None,
                        "stats": {
                            "total_time_ms": 12500,
                            "total_pages": 1,
                            "llm_pages_used": 1,
                            "estimated_cost": 0.02
                        }
                    }
                }
            }
        },
        400: {
            "description": "參數錯誤",
            "content": {
                "application/json": {
                    "examples": {
                        "unsupported_file": {
                            "summary": "不支援的檔案格式",
                            "value": {
                                "detail": "不支援的檔案格式：.docx。支援的格式：PDF、JPG、JPEG、PNG",
                                "error_code": "UNSUPPORTED_FILE_TYPE"
                            }
                        },
                        "unsupported_doc_type": {
                            "summary": "不支援的文件類型",
                            "value": {
                                "detail": "不支援的文件類型：invoice。支援的類型：transcript、contract",
                                "error_code": "UNSUPPORTED_DOCUMENT_TYPE"
                            }
                        }
                    }
                }
            }
        },
        413: {
            "description": "檔案過大",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "檔案大小超過限制：20MB",
                        "error_code": "FILE_TOO_LARGE"
                    }
                }
            }
        },
        500: {
            "description": "處理失敗",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "文件處理失敗，請稍後再試",
                        "error_code": "PROCESSING_ERROR"
                    }
                }
            }
        }
    }
)
async def analyze_document(
    file: UploadFile = File(..., description="PDF 或圖片檔案（支援 .pdf, .jpg, .jpeg, .png，上限 20MB）"),
    document_type: str = Form(
        default="transcript",
        description="文件類型（transcript: 謄本, contract: 合約）"
    ),
    enable_llm: bool = Form(
        default=True,
        description="是否啟用 LLM 文字校正（啟用時使用 GPT-4o，成本約 $0.02/頁）"
    ),
    question: Optional[str] = Form(
        default=None,
        description="針對文件的問題（選填，提供時會基於 OCR 結果使用 AI 回答）"
    ),
    db: Session = Depends(get_db),
):
    """
    ## 統一文件分析

    上傳 PDF 或圖片，一次完成 OCR 辨識、文字校正、結構化欄位提取。

    ### 功能特色
    - **多格式支援**: PDF、JPG、JPEG、PNG
    - **多文件類型**: 謄本（transcript）、合約（contract）
    - **OCR + 規則修正**: 自動辨識文字並修正常見 OCR 錯誤
    - **LLM 文字校正**: 可選啟用 GPT-4o 進一步校正（信心度 < 85% 時觸發）
    - **結構化欄位提取**: 合約文件自動提取合約編號、簽約日期、甲乙方、金額等
    - **AI 問答**: 提供 `question` 參數即可針對文件內容提問
    - **S3 儲存**: 檔案自動上傳至 S3，回傳 CDN URL

    ### 使用範例

    **基本 OCR（不含 LLM）**:
    ```bash
    curl -X POST "https://your-domain.com/api/v1/analyze" \\
      -F "file=@謄本.pdf" \\
      -F "document_type=transcript" \\
      -F "enable_llm=false"
    ```

    **完整分析（含 LLM 校正）**:
    ```bash
    curl -X POST "https://your-domain.com/api/v1/analyze" \\
      -F "file=@謄本.pdf" \\
      -F "document_type=transcript" \\
      -F "enable_llm=true"
    ```

    **含 AI 問答**:
    ```bash
    curl -X POST "https://your-domain.com/api/v1/analyze" \\
      -F "file=@合約.pdf" \\
      -F "document_type=contract" \\
      -F "question=合約金額是多少？"
    ```

    ### 錯誤代碼

    | error_code | HTTP 狀態碼 | 說明 |
    |------------|-----------|------|
    | UNSUPPORTED_FILE_TYPE | 400 | 不支援的檔案格式 |
    | UNSUPPORTED_DOCUMENT_TYPE | 400 | 不支援的文件類型 |
    | FILE_TOO_LARGE | 413 | 檔案超過 20MB |
    | PROCESSING_ERROR | 500 | 處理過程發生錯誤 |
    """
    try:
        # 1. 文件類型驗證與正規化(動態白名單 + 舊型別收斂)
        resolved_document_type = _resolve_document_type(document_type)

        # 2. 檔案格式、型別相容性、大小驗證(與批次端點共用)
        contents = await _validate_and_read(file, resolved_document_type)

        # 5. 選取 few-shot 範例(依文件類型;校正累積後越用越準)
        few_shot = FewShotSelector(CorrectionSampleService(db)).select(
            resolved_document_type
        )

        # 6. 呼叫分析服務(傳入正規化後的權威型別與 few-shot)
        service = AnalyzeService()
        result = await service.analyze(
            file_contents=contents,
            filename=file.filename or "unknown",
            document_type=resolved_document_type,
            enable_llm=enable_llm,
            question=question,
            few_shot=few_shot,
        )

        # 7. 信心度攔截:低信心自動入複核佇列並標示 needs_review
        _apply_confidence_gating(result, db)
        return result

    except AnalyzeError as e:
        return JSONResponse(
            status_code=e.status_code,
            content={"detail": e.detail, "error_code": e.error_code}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文件處理失敗: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "detail": "文件處理失敗，請稍後再試",
                "error_code": "PROCESSING_ERROR"
            }
        )


@router.get(
    "/usage",
    summary="查詢 API 用量統計",
    response_model=None,
    responses={
        200: {
            "description": "用量統計",
            "content": {
                "application/json": {
                    "example": {
                        "total_calls": 156,
                        "total_pages": 423,
                        "total_llm_cost": 8.46,
                        "period": "all_time"
                    }
                }
            }
        }
    }
)
def get_usage(db: Session = Depends(get_db)):
    """
    ## 查詢 API 用量統計

    回傳累計的 API 呼叫次數、處理頁數、LLM 成本。

    ### 使用範例
    ```bash
    curl "https://your-domain.com/api/v1/usage"
    ```
    """
    total_calls = db.query(ApiUsageLog).count()

    result = db.query(ApiUsageLog).with_entities(
        sa_func.coalesce(sa_func.sum(ApiUsageLog.total_pages), 0),
        sa_func.coalesce(sa_func.sum(ApiUsageLog.llm_cost), 0.0),
    ).first()

    total_pages = int(result[0]) if result else 0
    total_llm_cost = round(float(result[1]), 4) if result else 0.0

    return {
        "total_calls": total_calls,
        "total_pages": total_pages,
        "total_llm_cost": total_llm_cost,
        "period": "all_time",
    }


@router.post(
    "/analyze/batch",
    response_model=BatchAnalyzeResponse,
    summary="批次文件分析",
    responses={
        400: {
            "description": "參數錯誤（沒帶檔案、超過張數上限、不支援的文件類型）",
            "content": {
                "application/json": {
                    "examples": {
                        "too_many": {
                            "summary": "超過張數上限",
                            "value": {
                                "detail": "一次最多 20 個檔案，本次收到 25 個",
                                "error_code": "TOO_MANY_FILES",
                            },
                        },
                        "empty": {
                            "summary": "沒帶檔案",
                            "value": {
                                "detail": "請至少上傳一個檔案",
                                "error_code": "NO_FILES",
                            },
                        },
                    }
                }
            },
        }
    },
)
async def analyze_batch(
    files: List[UploadFile] = File(
        ..., description=f"檔案陣列，一次最多 {MAX_BATCH_FILES} 個，單檔上限 20MB"
    ),
    document_type: str = Form(
        default="handover_photo",
        description="文件類型，整批共用（handover_photo: 點交照片）",
    ),
    enable_llm: bool = Form(default=True, description="是否啟用 LLM 文字校正"),
    db: Session = Depends(get_db),
):
    """
    ## 批次文件分析

    一次上傳多個檔案，逐一分析後一次回傳。為點交照片而設：現場一次拍十幾張，
    逐張呼叫要送十幾次請求，中間斷一次就不知道補哪幾張。

    ### 單張失敗不會中斷整批
    每個檔案獨立處理，某一張壞掉只會讓那一筆 `status` 是 `"error"`，
    其餘照常回傳。呼叫端用 `index` 對回自己的檔案順序即可（與送出順序一致）。

    ### 使用範例
    ```bash
    curl -X POST "http://<host>:8000/api/v1/analyze/batch" \\
      -F "files=@客廳.jpg" \\
      -F "files=@廚房.jpg" \\
      -F "files=@衛浴.jpg" \\
      -F "document_type=handover_photo"
    ```

    ### 注意
    - 整批共用同一個 `document_type`，不能一張謄本一張照片混送。
    - 這是**同步**端點：全部處理完才回應。張數上限 20 就是為了壓住等待時間。
    """
    if not files:
        return JSONResponse(
            status_code=400,
            content={"detail": "請至少上傳一個檔案", "error_code": "NO_FILES"},
        )

    if len(files) > MAX_BATCH_FILES:
        return JSONResponse(
            status_code=400,
            content={
                "detail": f"一次最多 {MAX_BATCH_FILES} 個檔案，本次收到 {len(files)} 個",
                "error_code": "TOO_MANY_FILES",
            },
        )

    # 文件類型不合法是整批的問題,不是某一筆的問題,直接 400。
    try:
        resolved_document_type = _resolve_document_type(document_type)
    except AnalyzeError as e:
        return JSONResponse(
            status_code=e.status_code,
            content={"detail": e.detail, "error_code": e.error_code},
        )

    # few-shot 依文件類型選取,整批共用。放在迴圈外有兩個理由:
    # 一是省掉 N 次相同的 DB 查詢,二是讓後面的併發區段完全不碰 Session。
    few_shot = FewShotSelector(CorrectionSampleService(db)).select(
        resolved_document_type
    )

    gate = asyncio.Semaphore(BATCH_MAX_CONCURRENT)
    service = AnalyzeService()

    async def _one(index: int, file: UploadFile) -> dict:
        """回傳純 dict,不在這裡組 Pydantic 模型——
        信心度攔截要就地改寫結果,dict 比模型好改也少一次來回轉換。"""
        name = file.filename or "unknown"
        async with gate:
            try:
                contents = await _validate_and_read(file, resolved_document_type)
                result = await service.analyze(
                    file_contents=contents,
                    filename=name,
                    document_type=resolved_document_type,
                    enable_llm=enable_llm,
                    question=None,
                    few_shot=few_shot,
                )
                return {"index": index, "file_name": name,
                        "status": "ok", "result": result}
            except AnalyzeError as e:
                return {"index": index, "file_name": name, "status": "error",
                        "detail": e.detail, "error_code": e.error_code}
            except Exception as e:
                logger.error(f"批次第 {index} 筆（{name}）處理失敗: {e}", exc_info=True)
                return {"index": index, "file_name": name, "status": "error",
                        "detail": "文件處理失敗，請稍後再試",
                        "error_code": "PROCESSING_ERROR"}

    # gather 保序:回傳順序與傳入順序一致,index 因此可信。
    results = list(await asyncio.gather(*(_one(i, f) for i, f in enumerate(files))))

    # 信心度攔截會寫 DB。SQLAlchemy Session 不打算被多個協程同時使用,
    # 所以放在併發區段之外循序跑——這段只有 DB,不等網路,不值得為它冒險。
    for item in results:
        if item["status"] == "ok" and item.get("result") is not None:
            _apply_confidence_gating(item["result"], db)

    succeeded = sum(1 for r in results if r["status"] == "ok")
    return {
        "document_type": resolved_document_type,
        "total": len(results),
        "succeeded": succeeded,
        "failed": len(results) - succeeded,
        "results": results,
    }
