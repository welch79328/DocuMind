"""
多文件類型 OCR 型別定義

定義文件處理過程中使用的所有型別，包括文件類型列舉、處理結果等。
使用 TypedDict 確保型別安全與 IDE 支援。
"""

from typing import TypedDict, Literal, Optional, Dict, Any

# 權威文件類型列舉的單一真相來源(re-export,供既有引用者收斂)
from app.lib.document_types import DocumentType


# 文件類型列舉(Literal 形式,對齊權威 DocumentType 的四種型別)
DocumentTypeEnum = Literal["transcript", "bill", "contract", "repair_photo"]
"""
支援的文件類型列舉(與權威 `DocumentType` 一致)

- transcript: 建物土地謄本
- bill: 帳單
- contract: 合約
- repair_photo: 修繕照片
"""


# OCR 原始結果
class OcrRawResult(TypedDict):
    """
    OCR 引擎的原始辨識結果

    Attributes:
        text: 辨識出的文字內容
        confidence: OCR 信心度 (0.0 - 1.0)
    """
    text: str
    confidence: float


# 規則後處理結果
class RulePostprocessedResult(TypedDict):
    """
    規則後處理結果

    應用錯別字修正、格式校正等規則後的結果

    Attributes:
        text: 規則修正後的文字
        stats: 處理統計資訊（如修正次數）
    """
    text: str
    stats: Dict[str, Any]


# LLM 後處理結果
class LlmPostprocessedResult(TypedDict):
    """
    LLM 後處理結果

    使用 LLM 文字校正後的結果

    Attributes:
        text: LLM 修正後的文字
        stats: LLM 處理統計（如成本、使用時間）
        used: 是否實際使用了 LLM
    """
    text: str
    stats: Dict[str, Any]
    used: bool


# 頁面處理結果
class PageResult(TypedDict):
    """
    單一頁面的完整處理結果

    Attributes:
        page_number: 頁碼（從 1 開始）
        original_image: 原始圖像的 base64 編碼字串
        ocr_raw: OCR 原始結果
        rule_postprocessed: 規則後處理結果
        llm_postprocessed: LLM 後處理結果（可選）
        structured_data: 結構化欄位提取結果（依文件類型而異，可選）
        accuracy: 準確率評估（可選）
        processing_steps: 處理步驟記錄
    """
    page_number: int
    original_image: str
    ocr_raw: Optional[OcrRawResult]
    rule_postprocessed: Optional[RulePostprocessedResult]
    llm_postprocessed: Optional[LlmPostprocessedResult]
    structured_data: Optional[Dict[str, Any]]
    accuracy: Optional[Dict[str, float]]
    processing_steps: Dict[str, str]
    field_confidences: Dict[str, float]     # 各欄位信心度(任務 8.1)
    overall_confidence: float               # 整體信心度(供 QualityAssessor)


# 合約結構化資料型別定義

class ContractMetadata(TypedDict):
    """
    合約元資訊

    Attributes:
        contract_number: 合約編號
        signing_date: 簽訂日期
        effective_date: 生效日期
    """
    contract_number: Optional[str]
    signing_date: Optional[str]
    effective_date: Optional[str]


class PartyInfo(TypedDict):
    """
    合約雙方資訊

    Attributes:
        party_a: 甲方名稱
        party_b: 乙方名稱
        party_a_address: 甲方地址
        party_b_address: 乙方地址
    """
    party_a: Optional[str]
    party_b: Optional[str]
    party_a_address: Optional[str]
    party_b_address: Optional[str]


class FinancialTerms(TypedDict):
    """
    合約財務條款

    Attributes:
        contract_amount: 合約金額
        currency: 貨幣類型
        payment_method: 付款方式
        payment_deadline: 付款期限
    """
    contract_amount: Optional[str]
    currency: Optional[str]
    payment_method: Optional[str]
    payment_deadline: Optional[str]


class ContractStructuredData(TypedDict):
    """
    合約結構化資料

    包含從合約中提取的所有結構化欄位資訊

    Attributes:
        contract_metadata: 合約元資訊
        parties: 合約雙方資訊
        financial_terms: 財務條款
        extraction_confidence: 欄位提取信心度 (0.0 - 1.0)
    """
    contract_metadata: ContractMetadata
    parties: PartyInfo
    financial_terms: FinancialTerms
    extraction_confidence: float
