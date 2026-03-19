"""
AI Result Model
"""

from sqlalchemy import Column, String, Integer, Text, DateTime, Numeric, ForeignKey, func, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base
import uuid


class DocumentAiResult(Base):
    """AI processing results table"""

    __tablename__ = "document_ai_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    doc_type = Column(String(50), nullable=False)
    confidence = Column(Numeric(5, 2), nullable=False)
    summary = Column(Text, nullable=True)
    risks = Column(JSONB, nullable=True)
    extracted_data = Column(JSONB, nullable=False)
    ai_model = Column(String(50), nullable=True)
    processing_time = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    document = relationship("Document", back_populates="ai_results")

    # Indexes
    __table_args__ = (
        Index("idx_ai_document_id", "document_id"),
        Index("idx_ai_doc_type", "doc_type"),
        Index("idx_ai_extracted_data", "extracted_data", postgresql_using="gin"),
    )

    def __repr__(self):
        return f"<DocumentAiResult(id={self.id}, doc_type={self.doc_type})>"
