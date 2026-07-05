"""
Correction Sample Model

校正樣本:人工複核校正後的正確結果,依文件類型分庫,供 few-shot 回灌。
以 layout_signature 支援「同版型優先」選取;以 purpose 區隔訓練池(train)與
保留評估集(holdout),於資料層防止 few-shot 與評估資料互相污染。
"""

from sqlalchemy import (
    Column, String, Text, Boolean, DateTime, ForeignKey, func, Index
)
from sqlalchemy.orm import relationship
from app.database import Base
from app.models._column_types import uuid_column_type, jsonb_column_type, new_uuid


class CorrectionSample(Base):
    """校正樣本 / 黃金範例"""

    __tablename__ = "correction_samples"

    id = Column(uuid_column_type(), primary_key=True, default=new_uuid)
    document_type = Column(String(50), nullable=False)
    layout_signature = Column(String(120), nullable=False, default="")  # 版型指紋(同版型選取)
    purpose = Column(String(10), nullable=False, default="train")        # train / holdout(防洩漏)
    input_ref = Column(Text, nullable=False)          # 原始輸入參照(影像路徑 / 文字摘要)
    corrected_fields = Column(jsonb_column_type(), nullable=False)   # 校正後正確欄位值
    is_golden = Column(Boolean, nullable=False, default=False)
    source_review_id = Column(
        uuid_column_type(),
        ForeignKey("review_queue_items.id"),
        nullable=True,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships(單向)
    source_review = relationship("ReviewQueueItem")

    # Indexes
    __table_args__ = (
        Index(
            "idx_sample_select",
            "document_type", "purpose", "is_golden", "layout_signature",
        ),
        Index(
            "idx_sample_corrected_fields",
            "corrected_fields",
            postgresql_using="gin",
        ),
    )

    def __repr__(self):
        return (
            f"<CorrectionSample(id={self.id}, document_type={self.document_type}, "
            f"purpose={self.purpose}, is_golden={self.is_golden})>"
        )
