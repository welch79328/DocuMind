"""
OCR Result Model
"""

from sqlalchemy import Column, String, Integer, Text, DateTime, Numeric, ForeignKey, func, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base
import uuid


class DocumentOcrResult(Base):
    """OCR results table"""

    __tablename__ = "document_ocr_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    raw_text = Column(Text, nullable=False)
    page_count = Column(Integer, default=1, nullable=False)
    ocr_confidence = Column(Numeric(5, 2), nullable=True)
    ocr_service = Column(String(50), nullable=True)
    processing_time = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    document = relationship("Document", back_populates="ocr_results")

    # Indexes
    __table_args__ = (Index("idx_ocr_document_id", "document_id"),)

    def __repr__(self):
        return f"<DocumentOcrResult(id={self.id}, document_id={self.document_id})>"
