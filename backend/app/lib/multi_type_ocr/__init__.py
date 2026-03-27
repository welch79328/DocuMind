"""
多文件類型 OCR 處理套件

提供文件類型處理器架構，支援謄本、合約等不同類型文件的專門化辨識與結構化資訊提取。
"""

from .types import (
    DocumentTypeEnum,
    OcrRawResult,
    RulePostprocessedResult,
    LlmPostprocessedResult,
    PageResult,
    ContractMetadata,
    PartyInfo,
    FinancialTerms,
    ContractStructuredData,
)
from .processor import DocumentProcessor
from .processor_factory import ProcessorFactory
from .transcript_processor import TranscriptProcessor
from .contract_processor import ContractProcessor

__all__ = [
    "DocumentTypeEnum",
    "OcrRawResult",
    "RulePostprocessedResult",
    "LlmPostprocessedResult",
    "PageResult",
    "ContractMetadata",
    "PartyInfo",
    "FinancialTerms",
    "ContractStructuredData",
    "DocumentProcessor",
    "ProcessorFactory",
    "TranscriptProcessor",
    "ContractProcessor",
]
