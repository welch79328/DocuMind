"""
AI Result Pydantic Schemas
"""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID


class AIResultResponse(BaseModel):
    """Schema for AI processing result"""

    id: UUID
    document_id: UUID
    doc_type: str
    confidence: float
    summary: Optional[str] = None
    risks: Optional[List[Dict[str, Any]]] = None
    extracted_data: Dict[str, Any]
    ai_model: Optional[str] = None
    processing_time: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True
