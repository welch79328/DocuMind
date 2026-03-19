"""
Chat API Routes
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID

from app.database import get_db
from app.schemas.chat import ChatRequest, ChatResponse
from app.services import chat_service

router = APIRouter()


@router.post("/{document_id}", response_model=ChatResponse)
async def chat_with_document(
    document_id: UUID,
    chat_request: ChatRequest,
    db: Session = Depends(get_db)
):
    """
    Ask questions about a document

    - Loads document context (OCR text + extracted fields)
    - Sends question to AI with context
    - Returns AI answer
    - Optionally saves chat log
    """
    try:
        return await chat_service.chat_with_document(
            document_id=document_id,
            question=chat_request.question,
            db=db
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat failed: {str(e)}"
        )
