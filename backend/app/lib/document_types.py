"""
權威文件類型定義(單一真相來源)

收斂專案中原本散落三處、彼此不一致的文件類型體系:
- 工廠(processor_factory): transcript / contract
- 分類器(ocr_enhanced.document_classifier): transcript / lease / id_card / unknown
- AI 服務(ai_service): lease_contract / repair_quote / id_card / unknown

本模組提供唯一權威列舉 `DocumentType`、舊型別正規化 `normalize_document_type`,
以及型別-檔案格式相容性檢查,供路由層與 API 統一引用。
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, Optional, Set


class DocumentType(str, Enum):
    """
    權威文件類型列舉

    繼承 str 以確保與既有字串鍵向後相容
    (例如 DocumentType.TRANSCRIPT == "transcript",可直接用於字典查詢)。
    """

    TRANSCRIPT = "transcript"      # 建物土地謄本(最高優先)
    BILL = "bill"                  # 帳單(水電/管理費等)
    CONTRACT = "contract"          # 合約 PDF
    REPAIR_PHOTO = "repair_photo"  # 修繕照片(影像理解)


# 舊型別體系 → 權威列舉 的映射
# 用於將分類器 / AI 服務的既有輸出正規化到單一權威型別。
# 註:id_card / unknown 無對應的可處理型別,正規化時回傳 None。
LEGACY_TYPE_ALIASES: Dict[str, DocumentType] = {
    "lease": DocumentType.CONTRACT,           # 租約屬合約
    "lease_contract": DocumentType.CONTRACT,
    "repair_quote": DocumentType.BILL,         # 修繕報價單以金額為核心,歸帳單
}


def normalize_document_type(value: Optional[str]) -> Optional[DocumentType]:
    """
    將任意文件類型字串正規化為權威列舉

    Args:
        value: 文件類型字串(可能為權威值、舊型別別名、未知或空)

    Returns:
        對應的 `DocumentType`;若為空、未指定或無法對應則回傳 None。
    """
    if value is None:
        return None

    key = value.strip().lower()
    if not key:
        return None

    for document_type in DocumentType:
        if document_type.value == key:
            return document_type

    return LEGACY_TYPE_ALIASES.get(key)


# 全系統支援的檔案副檔名
SUPPORTED_EXTENSIONS: Set[str] = {".pdf", ".jpg", ".jpeg", ".png"}

# 影像副檔名(不含 PDF)
_IMAGE_EXTENSIONS: Set[str] = {".jpg", ".jpeg", ".png"}

# 各文件類型允許的檔案格式(型別-格式相容性)
# 修繕照片為影像理解型,僅接受影像,不接受 PDF。
TYPE_ALLOWED_EXTENSIONS: Dict[DocumentType, Set[str]] = {
    DocumentType.TRANSCRIPT: set(SUPPORTED_EXTENSIONS),
    DocumentType.BILL: set(SUPPORTED_EXTENSIONS),
    DocumentType.CONTRACT: set(SUPPORTED_EXTENSIONS),
    DocumentType.REPAIR_PHOTO: set(_IMAGE_EXTENSIONS),
}


def is_extension_allowed(document_type: DocumentType, ext: str) -> bool:
    """
    檢查指定文件類型是否接受該檔案副檔名

    Args:
        document_type: 權威文件類型
        ext: 檔案副檔名(含點,例如 ".pdf");不分大小寫

    Returns:
        該類型是否允許此格式。
    """
    allowed = TYPE_ALLOWED_EXTENSIONS.get(document_type, SUPPORTED_EXTENSIONS)
    return ext.lower() in allowed
