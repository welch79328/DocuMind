"""
Documents API Routes
"""

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.database import get_db
from app.schemas.document import DocumentResponse, DocumentListResponse
from app.schemas.ai_result import AIResultResponse
from app.services import document_service

router = APIRouter()


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    上傳新文件

    - 驗證檔案類型與大小
    - 上傳至 S3/R2 儲存
    - 建立文件記錄至資料庫
    """
    return await document_service.upload_document(file, db)


@router.post("/{document_id}/process", response_model=DocumentResponse)
async def process_document(
    document_id: UUID,
    db: Session = Depends(get_db)
):
    """
    觸發文件 AI 處理

    處理步驟：
    1. OCR 文字辨識
    2. AI 文件分類
    3. 欄位提取
    4. 摘要生成
    5. 風險偵測
    """
    return await document_service.process_document(document_id, db)


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    db: Session = Depends(get_db)
):
    """依 ID 取得文件及所有關聯資料"""
    document = await document_service.get_document(document_id, db)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    return document


@router.get("/{document_id}/ai-result", response_model=AIResultResponse)
async def get_ai_result(
    document_id: UUID,
    db: Session = Depends(get_db)
):
    """取得文件的 AI 處理結果"""
    result = await document_service.get_ai_result(document_id, db)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI result not found"
        )
    return result


@router.get("/{document_id}/ocr-result")
async def get_ocr_result(
    document_id: UUID,
    db: Session = Depends(get_db)
):
    """取得文件的 OCR 辨識結果"""
    result = await document_service.get_ocr_result(document_id, db)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OCR result not found"
        )
    return result


@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """取得文件列表（支援分頁）"""
    return await document_service.list_documents(skip, limit, db)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    db: Session = Depends(get_db)
):
    """刪除文件及所有關聯資料"""
    success = await document_service.delete_document(document_id, db)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    return None
