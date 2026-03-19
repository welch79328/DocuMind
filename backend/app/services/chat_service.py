"""
Chat Service - Business Logic
"""

from sqlalchemy.orm import Session
from uuid import UUID
import time

from app.models.document import Document
from app.models.ocr_result import DocumentOcrResult
from app.models.ai_result import DocumentAiResult
from app.models.chat_log import DocumentChatLog
from app.lib.ai_service import answer_question
from app.config import settings


async def chat_with_document(document_id: UUID, question: str, db: Session) -> dict:
    """
    Answer questions about a document using AI
    """
    # Get document
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise ValueError("Document not found")

    if document.status != "completed":
        raise ValueError("Document processing not completed yet")

    # Get OCR result
    ocr_result = db.query(DocumentOcrResult).filter(
        DocumentOcrResult.document_id == document_id
    ).first()

    if not ocr_result:
        raise ValueError("OCR result not found")

    # Get AI result (optional, for context)
    ai_result = db.query(DocumentAiResult).filter(
        DocumentAiResult.document_id == document_id
    ).first()

    # Prepare context
    context = {
        "ocr_text": ocr_result.raw_text,
        "doc_type": ai_result.doc_type if ai_result else "unknown",
        "extracted_data": ai_result.extracted_data if ai_result else {},
        "summary": ai_result.summary if ai_result else None
    }

    # Ask AI
    start_time = time.time()
    answer = await answer_question(question, context)
    response_time = int((time.time() - start_time) * 1000)

    # Save chat log
    chat_log = DocumentChatLog(
        document_id=document_id,
        question=question,
        answer=answer,
        ai_model=settings.OPENAI_MODEL,
        response_time=response_time
    )
    db.add(chat_log)
    db.commit()

    return {
        "document_id": document_id,
        "question": question,
        "answer": answer,
        "ai_model": settings.OPENAI_MODEL,
        "response_time": response_time
    }
