"""
使用者當場確認服務(ocr-vlm-consensus 任務 9.2)

使用者在結果頁對低信心 / 引擎不一致欄位做的確認與修正,沉澱為 purpose='train'
的校正樣本,進入既有 few-shot 回灌流程。

與人工複核佇列的關係:兩條路徑**並存且互不影響**。當場確認是即時路徑
(使用者即文件當事人);複核佇列保留為稍後處理的備援路徑,其認領、提交、
釋出行為完全不變——本服務不觸碰 ReviewQueueService。

對應需求: 6.3, 6.4
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, TypedDict

from app.services.few_shot_selector import compute_layout_signature

logger = logging.getLogger(__name__)

# 與 review_queue_service._input_ref_from 一致的截斷長度,
# 讓兩條路徑產生的 few-shot 範例形狀相同
_INPUT_REF_MAX = 2000

# 使用者對單一欄位的處置
VALID_ACTIONS = frozenset({"confirmed", "corrected"})


class FieldDecision(TypedDict, total=False):
    """前端 FieldConfirmation 元件送出的單筆決定"""

    field: str
    action: str
    before: Any
    after: Any


class ConfirmationReport(TypedDict):
    """回灌結果;created=False 代表沒有可回灌的內容,未寫入任何資料"""

    created: bool
    sample_id: Optional[str]
    fields_written: int
    skipped: List[str]


def input_ref_from_text(page_text: Optional[str]) -> str:
    """由頁面 OCR 文字萃取輸入參照(與複核佇列路徑同樣截斷)"""
    return (page_text or "")[:_INPUT_REF_MAX]


class FieldConfirmationService:
    """把使用者當場確認的欄位寫回為訓練用途樣本"""

    def __init__(self, sample_service: Any):
        self.samples = sample_service

    def record(
        self,
        document_type: Any,
        page_text: Optional[str],
        decisions: List[FieldDecision],
    ) -> ConfirmationReport:
        """
        寫入一筆校正樣本。

        只寫入使用者實際處置過的欄位——未經人確認的欄位是系統自己的輸出,
        回灌它等於拿自己的答案當標準答案,會讓 few-shot 自我強化錯誤。

        沒有任何有效決定時不寫入、不計成本,回傳 created=False。
        """
        corrected_fields: Dict[str, Any] = {}
        skipped: List[str] = []

        for decision in decisions or []:
            field = str(decision.get("field") or "").strip()
            action = decision.get("action")

            if not field:
                skipped.append("(欄位名為空)")
                continue
            if action not in VALID_ACTIONS:
                skipped.append(field)
                logger.warning("略過未知處置 action=%r,欄位=%s", action, field)
                continue

            final_value = decision.get("after")
            if final_value is None:
                # 缺最終值的決定不成立。寫進去會讓 null 混入 few-shot 範例,
                # 教模型「這個欄位就是空的」。空字串則是有效答案(使用者清空該欄)。
                skipped.append(field)
                logger.warning("略過缺少最終值的決定,欄位=%s", field)
                continue

            corrected_fields[field] = final_value

        if not corrected_fields:
            return {
                "created": False,
                "sample_id": None,
                "fields_written": 0,
                "skipped": skipped,
            }

        # 版型指紋沿用既有計算,使當場確認的樣本也吃得到「同版型優先」選取
        layout_signature = compute_layout_signature(
            {"ocr_raw": {"text": page_text or ""}}
        )

        sample_id = self.samples.save(
            document_type=document_type,
            input_ref=input_ref_from_text(page_text),
            corrected_fields=corrected_fields,
            layout_signature=layout_signature,
            purpose="train",  # 硬性 train:當場確認絕不寫入 holdout 評估集
        )

        return {
            "created": True,
            "sample_id": str(sample_id),
            "fields_written": len(corrected_fields),
            "skipped": skipped,
        }


__all__ = [
    "ConfirmationReport",
    "FieldConfirmationService",
    "FieldDecision",
    "VALID_ACTIONS",
    "input_ref_from_text",
]
