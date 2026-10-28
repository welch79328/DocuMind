"""
「文件類型 → 供應商」分流(bedrock-qwen-documind D-2、SR-1)

帳單 bill、修繕照片 repair_photo、點交照片 handover_photo、合約 contract 的
每一次 LLM 呼叫(欄位抽取、照片理解、OCR 文字校正)都從這裡取得供應商名稱。
表在 settings.LLM_PROVIDER_BY_DOCUMENT_TYPE。

刻意**不改全域 LLM_PROVIDER**:表裡沒列的類別、以及所有不在表內的呼叫
(謄本、question 問答、chat、documents)都照舊。謄本的抽取與校正不呼叫本模組,
寫進表也會在設定載入時報錯(R3「不含謄本」)。

為什麼「表裡沒列」要回到各呼叫點的既有預設,而不是一律 openai:
各呼叫點原本的預設不同——帳單抽取與照片理解吃全域 LLM_PROVIDER,
帳單與合約的校正、合約抽取固定 openai。空表時全部維持原狀,
LLM_PROVIDER 預設 openai,所以預設四類都走 openai;而 LLM_PROVIDER=local_qwen
的地端部署(DEPLOYMENT 選項 C)也不會因為這張表被改送雲端。
"""

from __future__ import annotations

from typing import Optional

from app.config import (
    LLM_ROUTABLE_DOCUMENT_TYPES,
    settings,
    validate_llm_routing_table,
)


def routed_provider_name(document_type: Optional[str]) -> Optional[str]:
    """分流表為這個文件類型指定的供應商;沒指定、或不是可分流類型時回 None。

    每次呼叫都重新驗證設定:測試或執行期以屬性直接改 settings 時不會經過
    pydantic 驗證,未知名稱在這裡同樣報錯。
    """
    table = validate_llm_routing_table(settings.LLM_PROVIDER_BY_DOCUMENT_TYPE)
    if document_type not in LLM_ROUTABLE_DOCUMENT_TYPES:
        return None
    return table.get(document_type)


def provider_name_for(document_type: str, default: Optional[str]) -> Optional[str]:
    """分流表有指定就用表的;沒有就用呼叫點既有的預設(None = 全域 LLM_PROVIDER)。"""
    routed = routed_provider_name(document_type)
    return routed if routed is not None else default
