"""
Created Record Model
"""

from sqlalchemy import Column, String, DateTime, ForeignKey, func, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base
import uuid


class CreatedRecord(Base):
    """Records created from documents table"""

    __tablename__ = "created_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_document_id = Column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    record_type = Column(String(50), nullable=False)
    payload = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    source_document = relationship("Document", back_populates="created_records")

    # Indexes
    __table_args__ = (
        Index("idx_records_document_id", "source_document_id"),
        Index("idx_records_type", "record_type"),
    )

    def __repr__(self):
        return f"<CreatedRecord(id={self.id}, record_type={self.record_type})>"
