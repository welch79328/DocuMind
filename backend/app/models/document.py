"""
Document Model
"""

from sqlalchemy import Column, String, Integer, Text, DateTime, func, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base
import uuid


class Document(Base):
    """Main document table"""

    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_name = Column(String(255), nullable=False)
    file_url = Column(Text, nullable=False)
    mime_type = Column(String(100), nullable=False)
    file_size = Column(Integer, nullable=False)
    status = Column(String(50), nullable=False, default="uploaded")
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    ocr_results = relationship(
        "DocumentOcrResult", back_populates="document", cascade="all, delete-orphan"
    )
    ai_results = relationship(
        "DocumentAiResult", back_populates="document", cascade="all, delete-orphan"
    )
    chat_logs = relationship(
        "DocumentChatLog", back_populates="document", cascade="all, delete-orphan"
    )
    created_records = relationship(
        "CreatedRecord", back_populates="source_document", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("idx_documents_status", "status"),
        Index("idx_documents_created_at", "created_at"),
    )

    def __repr__(self):
        return f"<Document(id={self.id}, file_name={self.file_name}, status={self.status})>"
