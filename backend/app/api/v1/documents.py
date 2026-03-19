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
    Upload a new document

    - Validates file type and size
    - Uploads to S3/R2
    - Creates document record in database
    """
    return await document_service.upload_document(file, db)


@router.post("/{document_id}/process", response_model=DocumentResponse)
async def process_document(
    document_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Trigger AI processing for a document

    Steps:
    1. OCR processing
    2. AI classification
    3. Field extraction
    4. Summary generation
    5. Risk detection
    """
    return await document_service.process_document(document_id, db)


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    db: Session = Depends(get_db)
):
    """Get document by ID with all related data"""
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
    """Get AI processing result for a document"""
    result = await document_service.get_ai_result(document_id, db)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI result not found"
        )
    return result


@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """List all documents with pagination"""
    return await document_service.list_documents(skip, limit, db)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    db: Session = Depends(get_db)
):
    """Delete a document and all related data"""
    success = await document_service.delete_document(document_id, db)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    return None
