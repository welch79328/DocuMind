"""
API 用量記錄模型
"""

from sqlalchemy import Column, String, Integer, Boolean, Float, DateTime, func, Index
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base
import uuid


class ApiUsageLog(Base):
    """API 用量記錄"""

    __tablename__ = "api_usage_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    endpoint = Column(String(100), nullable=False)
    document_type = Column(String(50), nullable=False)
    total_pages = Column(Integer, nullable=False, default=0)
    llm_used = Column(Boolean, nullable=False, default=False)
    llm_cost = Column(Float, nullable=False, default=0.0)
    processing_time_ms = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_usage_created_at", "created_at"),
    )
