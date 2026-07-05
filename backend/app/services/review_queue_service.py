"""
人工複核佇列服務

實作認領式複核狀態機(pending → in_review → completed):
- enqueue:低信心文件入列
- claim:以資料庫條件更新保證單一認領者(需求 6.7 併發鎖定)
- submit_correction:僅認領者可提交,記錄校正前後差異並轉 completed
- release:釋出回 pending
- list_queue:列表(可依狀態過濾)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.lib.document_types import DocumentType
from app.models.review_queue_item import ReviewQueueItem


def _type_value(document_type: Any) -> str:
    """取得文件類型的字串值(相容 DocumentType 列舉與純字串)"""
    if isinstance(document_type, DocumentType):
        return document_type.value
    return str(document_type)


def _input_ref_from(original_result: Optional[Dict[str, Any]]) -> str:
    """由原始結果快照萃取輸入參照(各頁 OCR 文字彙整,截斷)"""
    pages = (original_result or {}).get("pages") or []
    texts = [
        (page.get("ocr_raw") or {}).get("text", "")
        for page in pages
        if isinstance(page, dict)
    ]
    return "\n".join(t for t in texts if t)[:2000]


class ReviewQueueService:
    """人工複核佇列服務(同步資料庫存取)"""

    def __init__(self, db: Session, sample_service: Optional[Any] = None):
        self.db = db
        # 選填:提交校正時觸發校正樣本入庫(僅人工校正路徑,防自我增強偏誤)
        self.sample_service = sample_service

    # ------------------------------------------------------------------ #
    def enqueue(
        self,
        document_id: Any,
        document_type: Any,
        overall_confidence: float,
        result: Dict[str, Any],
    ) -> str:
        """將低信心文件加入複核佇列,回傳項目 id"""
        item = ReviewQueueItem(
            document_id=str(document_id) if document_id is not None else None,
            document_type=_type_value(document_type),
            overall_confidence=overall_confidence,
            status="pending",
            original_result=result,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item.id

    # ------------------------------------------------------------------ #
    def claim(self, item_id: Any, reviewer: str) -> bool:
        """
        認領並鎖定一份文件

        以「條件更新」(WHERE status='pending')保證併發下僅單一認領者成功:
        受影響列數為 1 表示認領成功,為 0 表示已被他人認領或不存在。

        Returns:
            是否認領成功。
        """
        rowcount = (
            self.db.query(ReviewQueueItem)
            .filter(
                ReviewQueueItem.id == item_id,
                ReviewQueueItem.status == "pending",
            )
            .update(
                {
                    "status": "in_review",
                    "reviewer": reviewer,
                    "claimed_at": datetime.now(timezone.utc),
                },
                synchronize_session=False,
            )
        )
        self.db.commit()
        return rowcount == 1

    # ------------------------------------------------------------------ #
    def submit_correction(
        self,
        item_id: Any,
        reviewer: str,
        corrected_fields: Dict[str, Any],
    ) -> Dict[str, Dict[str, Any]]:
        """
        提交校正:僅認領者且處於複核中可提交;記錄前後差異,狀態轉 completed。

        Returns:
            校正前後差異 {欄位: {"before": ..., "after": ...}}(僅含變動欄位)。
        """
        item = self._get(item_id)
        if item.status != "in_review" or item.reviewer != reviewer:
            raise PermissionError("僅認領者可提交校正,且項目需處於複核中狀態")

        item.corrected_result = corrected_fields
        item.status = "completed"
        self.db.commit()

        # 觸發校正樣本入庫(人工校正 → 樣本;analyze 自動攔截不經此路徑)
        if self.sample_service is not None:
            self.sample_service.save(
                document_type=item.document_type,
                input_ref=_input_ref_from(item.original_result),
                corrected_fields=corrected_fields,
                source_review_id=item.id,
            )

        return self.compute_diff(item.original_result, corrected_fields)

    # ------------------------------------------------------------------ #
    def release(self, item_id: Any, reviewer: str) -> None:
        """釋出認領:僅認領者可釋出,狀態回 pending 供他人重新認領"""
        item = self._get(item_id)
        if item.reviewer != reviewer:
            raise PermissionError("僅認領者可釋出此項目")

        item.status = "pending"
        item.reviewer = None
        item.claimed_at = None
        self.db.commit()

    # ------------------------------------------------------------------ #
    def get_item(self, item_id: Any) -> Dict[str, Any]:
        """取得單一複核項目;不存在時拋出 ValueError"""
        return self._to_dict(self._get(item_id))

    def list_queue(self, status: Optional[Any] = None) -> List[Dict[str, Any]]:
        """列出複核佇列項目,可依狀態過濾;依建立時間排序"""
        query = self.db.query(ReviewQueueItem)
        if status is not None:
            query = query.filter(ReviewQueueItem.status == str(status))
        query = query.order_by(ReviewQueueItem.created_at.asc())
        return [self._to_dict(item) for item in query.all()]

    # ------------------------------------------------------------------ #
    @staticmethod
    def compute_diff(
        before: Optional[Dict[str, Any]],
        after: Optional[Dict[str, Any]],
    ) -> Dict[str, Dict[str, Any]]:
        """計算校正前後差異(僅回傳變動欄位)"""
        before = before or {}
        after = after or {}
        diff: Dict[str, Dict[str, Any]] = {}
        for key in set(before) | set(after):
            b = before.get(key)
            a = after.get(key)
            if b != a:
                diff[key] = {"before": b, "after": a}
        return diff

    # ------------------------------------------------------------------ #
    def _get(self, item_id: Any) -> ReviewQueueItem:
        item = (
            self.db.query(ReviewQueueItem)
            .filter(ReviewQueueItem.id == item_id)
            .first()
        )
        if item is None:
            raise ValueError(f"複核項目不存在:{item_id}")
        return item

    @staticmethod
    def _to_dict(item: ReviewQueueItem) -> Dict[str, Any]:
        return {
            "id": item.id,
            "document_id": item.document_id,
            "document_type": item.document_type,
            "overall_confidence": (
                float(item.overall_confidence)
                if item.overall_confidence is not None
                else None
            ),
            "status": item.status,
            "reviewer": item.reviewer,
            "original_result": item.original_result,
            "corrected_result": item.corrected_result,
        }
