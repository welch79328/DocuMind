"""
Chat Pydantic Schemas
"""

from pydantic import BaseModel
from uuid import UUID


class ChatRequest(BaseModel):
    """Schema for chat request"""

    question: str


class ChatResponse(BaseModel):
    """Schema for chat response"""

    document_id: UUID
    question: str
    answer: str
    ai_model: str
    response_time: int
