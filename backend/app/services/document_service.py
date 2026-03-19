"""
Document Service - Business Logic
"""

from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
import time

from app.models.document import Document
from app.models.ocr_result import DocumentOcrResult
from app.models.ai_result import DocumentAiResult
from app.lib.s3_service import upload_file_to_s3
from app.lib.ocr_service import extract_text_from_document
from app.lib.ai_service import classify_document, extract_fields, generate_summary
from app.config import settings


async def upload_document(file: UploadFile, db: Session) -> Document:
    """
    Upload document to S3 and create database record
    """
    # Validate file type
    if file.content_type not in settings.ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"File type {file.content_type} not allowed"
        )

    # Validate file size
    file_content = await file.read()
    file_size = len(file_content)

    if file_size > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File size exceeds {settings.MAX_FILE_SIZE} bytes"
        )

    # Upload to S3
    file_url = await upload_file_to_s3(file.filename, file_content)

    # Create document record
    document = Document(
        file_name=file.filename,
        file_url=file_url,
        mime_type=file.content_type,
        file_size=file_size,
        status="uploaded"
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    return document


async def process_document(document_id: UUID, db: Session) -> Document:
    """
    Process document through OCR and AI pipeline
    """
    # Get document
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Update status to processing
    document.status = "processing"
    db.commit()

    try:
        # Step 1: OCR
        start_time = time.time()
        ocr_text = await extract_text_from_document(document.file_url)
        ocr_time = int((time.time() - start_time) * 1000)

        # Save OCR result
        ocr_result = DocumentOcrResult(
            document_id=document.id,
            raw_text=ocr_text,
            ocr_service=settings.OCR_SERVICE,
            processing_time=ocr_time
        )
        db.add(ocr_result)
        db.commit()

        # Step 2: AI Classification
        start_time = time.time()
        classification = await classify_document(ocr_text)

        # Step 3: Field Extraction
        extracted_data = await extract_fields(ocr_text, classification["doc_type"])

        # Step 4: Summary Generation
        summary = await generate_summary(ocr_text, classification["doc_type"])

        ai_time = int((time.time() - start_time) * 1000)

        # Save AI result
        ai_result = DocumentAiResult(
            document_id=document.id,
            doc_type=classification["doc_type"],
            confidence=classification["confidence"],
            summary=summary,
            extracted_data=extracted_data,
            ai_model=settings.OPENAI_MODEL,
            processing_time=ai_time
        )
        db.add(ai_result)

        # Update document status
        document.status = "completed"
        db.commit()
        db.refresh(document)

        return document

    except Exception as e:
        # Handle errors
        document.status = "failed"
        document.error_message = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


async def get_document(document_id: UUID, db: Session) -> Document:
    """Get document by ID"""
    return db.query(Document).filter(Document.id == document_id).first()


async def get_ai_result(document_id: UUID, db: Session) -> DocumentAiResult:
    """Get AI result for document"""
    return db.query(DocumentAiResult).filter(
        DocumentAiResult.document_id == document_id
    ).first()


async def list_documents(skip: int, limit: int, db: Session) -> dict:
    """List documents with pagination"""
    documents = db.query(Document).order_by(
        Document.created_at.desc()
    ).offset(skip).limit(limit).all()

    total = db.query(Document).count()

    return {
        "documents": documents,
        "total": total
    }


async def delete_document(document_id: UUID, db: Session) -> bool:
    """Delete document"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        return False

    db.delete(document)
    db.commit()
    return True
