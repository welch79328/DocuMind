"""
Chat Log Model
"""

from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, func, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base
import uuid


class DocumentChatLog(Base):
    """Document chat history table"""

    __tablename__ = "document_chat_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    ai_model = Column(String(50), nullable=True)
    response_time = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    document = relationship("Document", back_populates="chat_logs")

    # Indexes
    __table_args__ = (
        Index("idx_chat_document_id", "document_id"),
        Index("idx_chat_created_at", "created_at"),
    )

    def __repr__(self):
        return f"<DocumentChatLog(id={self.id}, document_id={self.document_id})>"
