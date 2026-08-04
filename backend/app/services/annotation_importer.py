"""
標註資料匯入器

將檔案型標註(ground truth JSON)轉換並匯入為 `CorrectionSample`,銜接
「檔案型標註」與「資料庫型評估體系」兩套原本不相通的機制。

預設以 `purpose='holdout'`(保留評估集)匯入,使 `EvaluationService` 能以其為
ground truth 計算 CER 與欄位準確率;`CorrectionSampleService.list_for_fewshot()`
硬性僅取 `purpose='train'`,故匯入的評估集不會回灌 few-shot(防資料洩漏)。

未標註(空值 / 佔位字串)的項目一律略過並列入回報,不寫入資料,避免以假值
汙染評估基準。

對應需求: 1.7, 1.8, 1.9
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TypedDict

from app.lib.document_types import normalize_document_type

# 標註檔中屬「檔案層級後設資料」而非文件項目的保留鍵
_RESERVED_TOP_LEVEL_KEYS = frozenset({
    "annotation_metadata",
    "description",
    "version",
    "created_at",
    "updated_at",
    "note",
    "notes",
    "field_definitions",
    "critical_fields",
    "accuracy_threshold",
})

# 文件項目中屬描述性資訊、不列為標註欄位的鍵
_NON_FIELD_KEYS = frozenset({
    "document_type",
    "metadata",
    "quality_notes",
    "full_text",
    "pages",
    "note",
    "notes",
})

# 視為「尚未標註」的佔位值
_PLACEHOLDER_VALUES = frozenset({"", "[待標註]", "待標註", "需人工標註", "TBD"})


class ImportReport(TypedDict):
    """匯入結果回報"""

    imported: int
    skipped: int
    skipped_refs: List[str]
    errors: List[str]


class InvalidAnnotationFormatError(ValueError):
    """標註檔格式無法解析(非 JSON 物件、文件類型不支援等)"""


def _is_annotated(value: Any) -> bool:
    """判定欄位值是否為有效標註(非空值、非佔位字串)"""
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() not in _PLACEHOLDER_VALUES
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return True


class AnnotationImporter:
    """標註檔 → 校正樣本 的匯入器(同步資料庫存取)"""

    def __init__(self, sample_service: Any) -> None:
        self.sample_service = sample_service

    # ------------------------------------------------------------------ #
    def import_from_file(
        self,
        file_path: str,
        document_type: Any,
        purpose: str = "holdout",
    ) -> ImportReport:
        """
        匯入標註檔為校正樣本。

        Args:
            file_path: 標註 JSON 路徑
            document_type: 目標文件類型(權威列舉或可正規化的字串)
            purpose: 樣本用途,預設 'holdout'(保留評估集)

        Returns:
            ImportReport:{imported, skipped, skipped_refs, errors}

        Raises:
            FileNotFoundError: 標註檔不存在
            InvalidAnnotationFormatError: JSON 無法解析、頂層非物件,
                或文件類型不支援
        """
        resolved_type = normalize_document_type(
            document_type.value
            if hasattr(document_type, "value")
            else str(document_type)
        )
        if resolved_type is None:
            raise InvalidAnnotationFormatError(
                f"不支援的文件類型:{document_type}"
            )

        payload = self._load(file_path)
        entries, critical_fields = self._locate_entries(payload)

        report: ImportReport = {
            "imported": 0, "skipped": 0, "skipped_refs": [], "errors": [],
        }

        for input_ref, entry in entries.items():
            if not isinstance(entry, dict):
                report["errors"].append(
                    f"{input_ref}: 項目格式錯誤,預期物件卻得到 {type(entry).__name__}"
                )
                continue

            fields = self._extract_fields(entry)
            if fields is None:
                report["errors"].append(f"{input_ref}: 找不到可辨識的標註欄位")
                continue

            annotated = {k: v for k, v in fields.items() if _is_annotated(v)}
            if not self._counts_as_annotated(annotated, critical_fields):
                report["skipped"] += 1
                report["skipped_refs"].append(input_ref)
                continue

            self.sample_service.save(
                document_type=resolved_type.value,
                input_ref=input_ref,
                corrected_fields=annotated,
                purpose=purpose,
            )
            report["imported"] += 1

        return report

    # ------------------------------------------------------------------ #
    @staticmethod
    def _load(file_path: str) -> Dict[str, Any]:
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"標註檔不存在:{file_path}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise InvalidAnnotationFormatError(
                f"標註檔非有效 JSON:{file_path}({exc})"
            ) from exc
        if not isinstance(payload, dict):
            raise InvalidAnnotationFormatError(
                f"標註檔頂層須為物件,實得 {type(payload).__name__}:{file_path}"
            )
        return payload

    @staticmethod
    def _locate_entries(
        payload: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Optional[List[str]]]:
        """
        定位文件項目與關鍵欄位宣告。

        支援兩種既有標註檔形狀:
        - 謄本:頂層即為 {檔名: 標註},後設資料以保留鍵表示
        - 合約:標註集中於 `contracts` 物件下,並以 `critical_fields` 宣告關鍵欄位
        """
        critical = payload.get("critical_fields")
        critical_fields = (
            [str(f) for f in critical] if isinstance(critical, list) and critical
            else None
        )

        container = payload.get("contracts")
        if isinstance(container, dict):
            return container, critical_fields

        entries = {
            key: value
            for key, value in payload.items()
            if key not in _RESERVED_TOP_LEVEL_KEYS
        }
        return entries, critical_fields

    @staticmethod
    def _extract_fields(entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        取出項目的標註欄位。

        `key_fields` 存在時以其為準(謄本形狀);否則以項目本身扣除描述性鍵
        (合約形狀)。兩者皆無可辨識欄位時回傳 None。
        """
        key_fields = entry.get("key_fields")
        if isinstance(key_fields, dict):
            return dict(key_fields)

        fields = {
            key: value
            for key, value in entry.items()
            if key not in _NON_FIELD_KEYS and not key.startswith("page_")
        }
        return fields or None

    @staticmethod
    def _counts_as_annotated(
        annotated: Dict[str, Any], critical_fields: Optional[List[str]]
    ) -> bool:
        """
        判定項目是否已完成標註。

        標註檔宣告 `critical_fields` 時,須至少一個關鍵欄位已標註才算數——
        避免 `currency` 之類的預設值使未標註項目被誤判為可用樣本。
        """
        if not annotated:
            return False
        if critical_fields:
            return any(field in annotated for field in critical_fields)
        return True
