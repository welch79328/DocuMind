"""
統一分析 API 回應 Schema

定義 POST /api/v1/analyze 端點的回應格式。
"""

from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class OcrRawOutput(BaseModel):
    """OCR 原始辨識輸出"""
    text: str
    confidence: float


class RulePostprocessedOutput(BaseModel):
    """規則後處理輸出"""
    text: str
    stats: Dict[str, Any]


class LlmPostprocessedOutput(BaseModel):
    """LLM 後處理輸出"""
    text: str
    stats: Dict[str, Any]
    used: bool


class OcrPageResult(BaseModel):
    """單頁 OCR 處理結果"""
    page_number: int
    ocr_raw: OcrRawOutput
    rule_postprocessed: RulePostprocessedOutput
    llm_postprocessed: Optional[LlmPostprocessedOutput] = None
    structured_data: Optional[Dict[str, Any]] = None


class ProcessingStats(BaseModel):
    """處理統計資訊"""
    total_time_ms: int
    total_pages: int
    llm_pages_used: int
    estimated_cost: float


class AnalyzeResponse(BaseModel):
    """統一分析 API 回應"""
    file_name: str
    file_url: Optional[str] = None
    document_type: str
    total_pages: int
    pages: List[OcrPageResult]
    answer: Optional[str] = None
    stats: ProcessingStats
