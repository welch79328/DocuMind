"""
每頁 LLM 呼叫紀錄 `llm_calls`(bedrock-qwen-documind D-6、SR-8)

回應裡要分得出「沒用到 LLM」與「LLM 失敗了」,也要看得出每次呼叫實際送到哪個
供應商、哪個模型、服務等級是什麼。所以每個 Provider 在每次呼叫(含重送)結束時
記一筆;analyze_service 為每一頁開一個收集範圍,處理器標出目前是哪個階段。

用 contextvars 而不是一路傳參數:Provider 被很多層呼叫(校正、抽取、照片理解),
把紀錄器塞進每一層的簽章會動到大量既有介面。asyncio 的每個 Task 各自複製一份
context,analyze_service 的頁面併發彼此不會混在一起。

**錯誤只放類別,不放原始訊息。** AWS 拒絕存取的訊息可能帶 IAM ARN(F7);
這裡只接受固定清單裡的類別或 `http_<三位數狀態碼>`,其他一律記成 `error`,
所以就算呼叫端誤傳了原始訊息也不會進到回應。
"""

from __future__ import annotations

import re
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Dict, Iterator, List, Optional

# 階段名稱(回應裡的 stage)
STAGE_CORRECTION = "correction"                # OCR 文字校正
STAGE_EXTRACTION = "extraction"                # 欄位抽取
STAGE_PHOTO_UNDERSTANDING = "photo_understanding"  # 照片理解(修繕、點交)
STAGE_DIRECT_READ = "direct_read"              # Qwen 直讀(收據、帳單、合約,不跑本機 OCR)

# 允許出現在回應裡的錯誤類別
ERROR_CATEGORIES = frozenset({
    "timeout",              # 逾時
    "rate_limited",         # HTTP 429
    "unavailable",          # HTTP 503
    "connection_error",     # 連不上
    "invalid_response",     # 回應不是預期的格式
    "missing_credentials",  # 沒有設定金鑰
    "image_too_large",      # 重新編碼後仍超過 Bedrock 單張上限
    "error",                # 其他
})
_HTTP_CATEGORY = re.compile(r"^http_\d{3}$")

_calls: ContextVar[Optional[List[Dict[str, Any]]]] = ContextVar("llm_calls", default=None)
_stage: ContextVar[Optional[str]] = ContextVar("llm_stage", default=None)


def sanitize_error_category(category: Optional[str]) -> str:
    """只放行固定類別與 http_<狀態碼>;其他(包括任何原始訊息)一律回 `error`。"""
    if isinstance(category, str) and (
        category in ERROR_CATEGORIES or _HTTP_CATEGORY.match(category)
    ):
        return category
    return "error"


@contextmanager
def collect_llm_calls() -> Iterator[List[Dict[str, Any]]]:
    """開一個收集範圍;範圍內所有 Provider 呼叫都記進回傳的 list。"""
    calls: List[Dict[str, Any]] = []
    token = _calls.set(calls)
    try:
        yield calls
    finally:
        _calls.reset(token)


@contextmanager
def llm_stage(name: str) -> Iterator[None]:
    """標出範圍內的呼叫屬於哪個階段(校正、抽取、照片理解)。"""
    token = _stage.set(name)
    try:
        yield
    finally:
        _stage.reset(token)


def record_llm_call(
    *,
    provider: str,
    model: Optional[str],
    ok: bool,
    service_tier: Optional[str] = None,
    requested_service_tier: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    """記一筆呼叫;不在收集範圍內(例如非 analyze 端點)時什麼都不做。

    service_tier 是 API 回應實際標示的等級(失敗時沒有回應,為 None);
    requested_service_tier 是送出時要求的等級(只有 Bedrock 會帶)。
    """
    calls = _calls.get()
    if calls is None:
        return
    calls.append({
        "stage": _stage.get() or "unknown",
        "provider": provider,
        "model": model if isinstance(model, str) else None,
        "requested_service_tier": (
            requested_service_tier if isinstance(requested_service_tier, str) else None
        ),
        "service_tier": service_tier if isinstance(service_tier, str) else None,
        "ok": bool(ok),
        "error": None if ok else sanitize_error_category(error),
    })


def status_category(status_code: int) -> str:
    """HTTP 狀態碼 → 錯誤類別"""
    if status_code == 429:
        return "rate_limited"
    if status_code == 503:
        return "unavailable"
    return f"http_{int(status_code):03d}"


def classify_llm_error(exc: BaseException) -> str:
    """把任何 Provider 拋出的例外歸成類別(不看、不保留訊息內容)。"""
    category = getattr(exc, "category", None)
    if isinstance(category, str):
        return sanitize_error_category(category)

    status = getattr(exc, "status_code", None)
    if status is None:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
    if isinstance(status, int):
        return status_category(status)

    import asyncio

    names = {cls.__name__ for cls in type(exc).__mro__}
    if isinstance(exc, asyncio.TimeoutError) or any("Timeout" in n for n in names):
        return "timeout"
    if any("Connect" in n for n in names):
        return "connection_error"
    return "error"
