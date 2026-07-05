"""
校正樣本服務

將人工校正沉澱為可回灌 few-shot 的校正樣本;支援黃金範例標記與去重。
以 purpose 區隔訓練池(train)與保留評估集(holdout)。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.lib.document_types import DocumentType
from app.models.correction_sample import CorrectionSample


def _type_value(document_type: Any) -> str:
    if isinstance(document_type, DocumentType):
        return document_type.value
    return str(document_type)


class CorrectionSampleService:
    """校正樣本入庫、黃金範例標記與去重(同步資料庫存取)"""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------ #
    def save(
        self,
        document_type: Any,
        input_ref: str,
        corrected_fields: Dict[str, Any],
        source_review_id: Optional[Any] = None,
        layout_signature: str = "",
        purpose: str = "train",
    ) -> str:
        """儲存一筆校正樣本,回傳樣本 id"""
        sample = CorrectionSample(
            document_type=_type_value(document_type),
            layout_signature=layout_signature,
            purpose=purpose,
            input_ref=input_ref,
            corrected_fields=corrected_fields,
            is_golden=False,
            source_review_id=(
                str(source_review_id) if source_review_id is not None else None
            ),
        )
        self.db.add(sample)
        self.db.commit()
        self.db.refresh(sample)
        return sample.id

    # ------------------------------------------------------------------ #
    def mark_golden(self, sample_id: Any, is_golden: bool = True) -> None:
        """標記 / 取消黃金範例"""
        sample = (
            self.db.query(CorrectionSample)
            .filter(CorrectionSample.id == sample_id)
            .first()
        )
        if sample is None:
            raise ValueError(f"校正樣本不存在:{sample_id}")
        sample.is_golden = is_golden
        self.db.commit()

    # ------------------------------------------------------------------ #
    def dedupe(self, document_type: Any) -> int:
        """
        去重:同類型、同 purpose、同 input_ref 視為重複來源,每組僅保留一筆
        (優先保留黃金範例,其次保留最新建立)。回傳刪除筆數。

        以 (input_ref, purpose) 分組,確保去重不跨 train / holdout 邊界,
        避免誤刪保留評估集樣本(防資料洩漏)。
        """
        doc_type = _type_value(document_type)
        samples = (
            self.db.query(CorrectionSample)
            .filter(CorrectionSample.document_type == doc_type)
            .all()
        )

        groups: Dict[tuple, List[CorrectionSample]] = {}
        for s in samples:
            groups.setdefault((s.input_ref, s.purpose), []).append(s)

        removed = 0
        for group in groups.values():
            if len(group) <= 1:
                continue
            # 保留:黃金優先,其次建立時間最新
            keeper = sorted(
                group,
                key=lambda s: (1 if s.is_golden else 0, s.created_at or 0),
                reverse=True,
            )[0]
            for s in group:
                if s.id != keeper.id:
                    self.db.delete(s)
                    removed += 1

        if removed:
            self.db.commit()
        return removed

    # ------------------------------------------------------------------ #
    def list_samples(
        self,
        document_type: Any,
        purpose: Optional[str] = None,
        golden_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """列出指定類型的校正樣本(可依 purpose / 黃金過濾)"""
        query = self.db.query(CorrectionSample).filter(
            CorrectionSample.document_type == _type_value(document_type)
        )
        if purpose is not None:
            query = query.filter(CorrectionSample.purpose == purpose)
        if golden_only:
            query = query.filter(CorrectionSample.is_golden.is_(True))
        query = query.order_by(CorrectionSample.created_at.asc())
        return [self._to_dict(s) for s in query.all()]

    def list_for_fewshot(
        self, document_type: Any, golden_first: bool = True
    ) -> List[Dict[str, Any]]:
        """
        取得可供 few-shot 回灌的樣本(防洩漏:硬性僅回 purpose='train',
        絕不含 holdout 評估集)。黃金範例優先排序。

        供 FewShotSelector(任務 9.1)使用;不接受 purpose 參數以杜絕誤取 holdout。
        """
        query = self.db.query(CorrectionSample).filter(
            CorrectionSample.document_type == _type_value(document_type),
            CorrectionSample.purpose == "train",
        )
        samples = query.all()
        if golden_first:
            samples = sorted(
                samples,
                key=lambda s: (1 if s.is_golden else 0, s.created_at or 0),
                reverse=True,
            )
        return [self._to_dict(s) for s in samples]

    def count(self, document_type: Any, purpose: str = "train") -> int:
        """統計指定類型 / purpose 的樣本數"""
        return (
            self.db.query(CorrectionSample)
            .filter(
                CorrectionSample.document_type == _type_value(document_type),
                CorrectionSample.purpose == purpose,
            )
            .count()
        )

    # ------------------------------------------------------------------ #
    @staticmethod
    def _to_dict(sample: CorrectionSample) -> Dict[str, Any]:
        return {
            "id": sample.id,
            "document_type": sample.document_type,
            "layout_signature": sample.layout_signature,
            "purpose": sample.purpose,
            "input_ref": sample.input_ref,
            "corrected_fields": sample.corrected_fields,
            "is_golden": sample.is_golden,
            "source_review_id": sample.source_review_id,
        }
