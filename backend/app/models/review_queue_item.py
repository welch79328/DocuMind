"""
Review Queue Item Model

人工複核佇列項目:當文件整體或關鍵欄位信心度低於門檻時入列,
以認領式狀態機(pending → in_review → completed)供複核者校正。
"""

from sqlalchemy import (
    Column, String, Numeric, DateTime, ForeignKey, func, Index
)
from sqlalchemy.orm import relationship
from app.database import Base
from app.models._column_types import uuid_column_type, jsonb_column_type, new_uuid


class ReviewQueueItem(Base):
    """人工複核佇列項目"""

    __tablename__ = "review_queue_items"

    id = Column(uuid_column_type(), primary_key=True, default=new_uuid)
    # nullable:統一分析流程目前為無狀態(不持久化 Document),佇列項目以
    # original_result 快照自足;未來加入文件持久化時可回填 document_id
    document_id = Column(
        uuid_column_type(),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=True,
    )
    document_type = Column(String(50), nullable=False)
    overall_confidence = Column(Numeric(5, 4), nullable=False)
    status = Column(String(20), nullable=False, default="pending")  # pending / in_review / completed
    reviewer = Column(String(100), nullable=True)
    claimed_at = Column(DateTime(timezone=True), nullable=True)
    original_result = Column(jsonb_column_type(), nullable=False)   # 校正前結果
    corrected_result = Column(jsonb_column_type(), nullable=True)   # 校正後結果
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships(單向,不修改既有 Document 模型)
    document = relationship("Document")

    # Indexes
    __table_args__ = (
        Index("idx_review_status", "status"),
        Index("idx_review_doc_type", "document_type"),
    )

    def __repr__(self):
        return (
            f"<ReviewQueueItem(id={self.id}, "
            f"document_type={self.document_type}, status={self.status})>"
        )
