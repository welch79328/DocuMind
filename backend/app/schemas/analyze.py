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


class LlmCallRecord(BaseModel):
    """單次 LLM 呼叫紀錄(bedrock-qwen-documind D-6)。

    一頁可能有多筆:校正一筆、抽取一筆;Bedrock 的 flex 失敗改送 default 時,
    失敗的那次與重送的那次各記一筆。
    """
    stage: str                                     # correction | extraction | photo_understanding
    provider: str                                  # openai | bedrock | anthropic | local_qwen
    model: Optional[str] = None
    requested_service_tier: Optional[str] = None   # 送出時要求的等級(只有 Bedrock 會帶:flex / default)
    service_tier: Optional[str] = None             # API 回應實際標示的等級;失敗時為 None
    ok: bool
    # 只放類別(timeout、rate_limited、unavailable、http_403…),不放供應商的原始訊息
    error: Optional[str] = None


class OcrPageResult(BaseModel):
    """單頁 OCR 處理結果"""
    model_config = {"extra": "ignore"}

    page_number: int
    # ⚠️ ocr_raw / rule_postprocessed 對「影像理解型」而言必然是 None
    # (repair_photo、handover_photo 走 VLM,不跑 OCR,見
    #  multi_type_ocr/processor.py 的 ImageUnderstandingProcessor.analyze)。
    # 這兩欄原本宣告為必填,導致那條路徑一律在回應驗證階段炸成 500;
    # 2026-09-09 以 handover_photo 開發時實測發現,連既有的 repair_photo
    # 也一樣中招。放寬為選填是修這個 bug,不是為新型別開後門——
    # 不要因為「OCR 一定有值」就改回必填。
    ocr_raw: Optional[OcrRawOutput] = None
    rule_postprocessed: Optional[RulePostprocessedOutput] = None
    llm_postprocessed: Optional[LlmPostprocessedOutput] = None
    structured_data: Optional[Dict[str, Any]] = None
    # 欄位層共識(需求 4;新增欄位皆為選填,既有欄位語意不變)
    field_confidences: Dict[str, float] = {}               # 逐欄位信心度
    consensus: Optional[Dict[str, Any]] = None             # 共識明細(未啟用時為 None)
    # 這一頁的每次 LLM 呼叫(選填;analyze 端點每頁都會帶,沒有呼叫時是空陣列)。
    # 不宣告在這裡就會被 extra: "ignore" 丟掉,呼叫端永遠看不到。
    llm_calls: Optional[List[LlmCallRecord]] = None


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
    # 跨頁彙整後的結構化欄位（新增，2026-09-03）。謄本關鍵欄位散在多頁時
    # （地號在 p1、建號在 p3），單頁 structured_data 必然殘缺；此欄位是
    # 各頁「只填補缺值」合併後的完整結果。None 表示所有頁面皆無 structured_data。
    document_fields: Optional[Dict[str, Any]] = None
    answer: Optional[str] = None
    stats: ProcessingStats
    # 信心度攔截(任務 3.3)
    needs_review: bool = False                              # 是否需人工複核
    review_item_id: Optional[str] = None                   # 入列後的複核項目 id
    field_confidences: Dict[str, float] = {}               # 欄位信心度彙整


class BatchItemResult(BaseModel):
    """批次分析中單一檔案的結果。

    成功時 `result` 有值、`detail`/`error_code` 為 None;失敗時相反。
    **失敗不會中斷整批**——一張照片壞掉不該讓另外十九張重傳。
    """
    index: int                                    # 對應請求中 files 的順序,從 0 起算
    file_name: str
    status: str                                   # "ok" | "error"
    result: Optional["AnalyzeResponse"] = None
    detail: Optional[str] = None
    error_code: Optional[str] = None


class BatchAnalyzeResponse(BaseModel):
    """批次分析 API 回應。

    `results` 與請求的 files 同序,呼叫端可用 index 對回自己的檔案。
    """
    document_type: str
    total: int
    succeeded: int
    failed: int
    results: List[BatchItemResult]


BatchItemResult.model_rebuild()
