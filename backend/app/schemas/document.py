"""
Document Pydantic Schemas
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from uuid import UUID


class DocumentStatus(BaseModel):
    """Document status enum"""

    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentCreate(BaseModel):
    """Schema for creating a document"""

    file_name: str
    file_url: str
    mime_type: str
    file_size: int


class DocumentResponse(BaseModel):
    """Schema for document response"""

    id: UUID
    file_name: str
    file_url: str
    mime_type: str
    file_size: int
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    """Schema for list of documents"""

    documents: list[DocumentResponse]
    total: int
