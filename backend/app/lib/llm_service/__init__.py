"""
LLM Service Module

統一的 LLM 服務層，支援文字修正、結構化提取等任務
"""

from .llm_service import LLMService
from .types import LLMProvider, LLMTask

__all__ = [
    "LLMService",
    "LLMProvider",
    "LLMTask",
]
