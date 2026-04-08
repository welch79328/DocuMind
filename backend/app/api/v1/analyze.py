"""
統一分析 API

提供單一端點完成文件上傳、OCR 辨識、結構化欄位提取、AI 問答。
"""

import logging

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import Optional

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from app.schemas.analyze import AnalyzeResponse
from app.services.analyze_service import AnalyzeService
from app.database import get_db
from app.models.api_usage_log import ApiUsageLog

logger = logging.getLogger(__name__)

router = APIRouter()

# 支援的檔案格式
SUPPORTED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}

# 支援的文件類型
SUPPORTED_DOCUMENT_TYPES = {"transcript", "contract"}

# 檔案大小限制 (20MB)
MAX_FILE_SIZE = 20 * 1024 * 1024


class AnalyzeError(Exception):
    """分析 API 錯誤"""
    def __init__(self, status_code: int, detail: str, error_code: str):
        self.status_code = status_code
        self.detail = detail
        self.error_code = error_code


def _validate_file(file: UploadFile) -> None:
    """驗證上傳檔案的格式"""
    filename = file.filename or ""
    ext = ""
    if "." in filename:
        ext = "." + filename.rsplit(".", 1)[-1].lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise AnalyzeError(
            status_code=400,
            detail=f"不支援的檔案格式：{ext or '未知'}。支援的格式：PDF、JPG、JPEG、PNG",
            error_code="UNSUPPORTED_FILE_TYPE",
        )


def _validate_document_type(document_type: str) -> None:
    """驗證文件類型"""
    if document_type not in SUPPORTED_DOCUMENT_TYPES:
        supported = "、".join(SUPPORTED_DOCUMENT_TYPES)
        raise AnalyzeError(
            status_code=400,
            detail=f"不支援的文件類型：{document_type}。支援的類型：{supported}",
            error_code="UNSUPPORTED_DOCUMENT_TYPE",
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
        # 1. 檔案格式驗證
        _validate_file(file)

        # 2. 文件類型驗證
        _validate_document_type(document_type)

        # 3. 讀取檔案內容並檢查大小
        contents = await file.read()
        if len(contents) > MAX_FILE_SIZE:
            raise AnalyzeError(
                status_code=413,
                detail=f"檔案大小超過限制：{MAX_FILE_SIZE // (1024 * 1024)}MB",
                error_code="FILE_TOO_LARGE",
            )

        # 4. 呼叫分析服務
        service = AnalyzeService()
        result = await service.analyze(
            file_contents=contents,
            filename=file.filename or "unknown",
            document_type=document_type,
            enable_llm=enable_llm,
            question=question,
        )
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
