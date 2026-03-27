"""
LLM Service Type Definitions

LLM 服務相關的型別定義
"""

from typing import Literal, TypedDict, Optional


# LLM 提供商型別
LLMProvider = Literal["openai", "anthropic"]


# LLM 任務型別
class LLMTask:
    """LLM 任務類型定義"""
    TEXT_CORRECTION = "text_correction"      # 文字修正
    STRUCTURED_EXTRACTION = "structured_extraction"  # 結構化提取
    GENERAL = "general"                      # 通用任務


# LLM 調用統計
class LLMStats(TypedDict):
    """LLM 調用統計資料"""
    llm_calls: int              # 調用次數
    tokens_used: int            # 使用的 token 數
    estimated_cost: float       # 預估成本（美元）
