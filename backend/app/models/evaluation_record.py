"""
Evaluation Record Model

評估紀錄:依文件類型記錄以保留評估集量測的準確率指標(CER / 欄位級準確率),
標記基準線並保留量測歷史,供前後對照與 fine-tune 決策。
"""

from sqlalchemy import (
    Column, String, Numeric, Boolean, DateTime, func, Index
)
from app.database import Base
from app.models._column_types import uuid_column_type, new_uuid


class EvaluationRecord(Base):
    """評估指標紀錄"""

    __tablename__ = "evaluation_records"

    id = Column(uuid_column_type(), primary_key=True, default=new_uuid)
    document_type = Column(String(50), nullable=False)
    metric_type = Column(String(30), nullable=False)         # cer / field_accuracy
    value = Column(Numeric(6, 4), nullable=False)
    labeled_set_version = Column(String(50), nullable=False)  # 保留評估集版本
    is_baseline = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Indexes
    __table_args__ = (
        Index("idx_eval_type_metric", "document_type", "metric_type"),
    )

    def __repr__(self):
        return (
            f"<EvaluationRecord(id={self.id}, document_type={self.document_type}, "
            f"metric_type={self.metric_type}, value={self.value})>"
        )
