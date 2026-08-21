"""
設定衝突檢查(ocr-vlm-consensus 任務 10.3)

某些設定組合語法合法、啟動也不會失敗,但實際行為與設定者的意圖不符——
啟用共識卻只配了一個引擎、要求地端卻同時開了雲端雙模態。這類組合不該
默默上線,啟動時就要講清楚。

只警告,不阻擋:設定衝突是判斷問題而非錯誤,擋下啟動會把一個可運行
(只是效果打折)的系統變成完全不能用。
"""

from __future__ import annotations

import logging
from typing import Any, List

logger = logging.getLogger(__name__)


def check_setting_conflicts(settings: Any) -> List[str]:
    """
    檢查設定衝突組合,回傳警告訊息清單(無衝突時為空)。

    純函式,不記錄也不拋出,方便測試逐條斷言;記錄由
    `log_setting_conflicts()` 負責。
    """
    warnings: List[str] = []

    # 共識需要至少兩個引擎才有「不一致」可言(需求 4.7)
    if getattr(settings, "OCR_CONSENSUS_ENABLED", False):
        engines = list(getattr(settings, "OCR_ENGINES", []) or [])
        if len(engines) < 2:
            warnings.append(
                f"OCR_CONSENSUS_ENABLED=true 但 OCR_ENGINES 只有 {len(engines)} 個引擎"
                f"({engines});共識需要至少兩個引擎才能比對,"
                "執行期將標記 consensus_available=False,信心度不會因共識而收緊。"
            )

    # 雙模態把整頁影像送給模型;走雲端等於把文件影像外送(需求 2.7)
    if getattr(settings, "LLM_DUAL_MODAL_ENABLED", False) and getattr(
        settings, "LLM_CLOUD_ENABLED", False
    ):
        provider = getattr(settings, "LLM_PROVIDER", "")
        warnings.append(
            f"LLM_DUAL_MODAL_ENABLED=true 且 LLM_CLOUD_ENABLED=true"
            f"(LLM_PROVIDER={provider!r});雙模態會將**頁面影像**送至雲端模型,"
            "個資外送範圍大於純文字校正。地端需求請設 LLM_CLOUD_ENABLED=false "
            "並改用本地 Provider。"
        )

    # 索取欄位信心度卻沒開雙模態:自評品質會比雙模態差(需求 2.2 的立論前提)
    if getattr(settings, "LLM_FIELD_CONFIDENCE_ENABLED", False) and not getattr(
        settings, "LLM_DUAL_MODAL_ENABLED", False
    ):
        warnings.append(
            "LLM_FIELD_CONFIDENCE_ENABLED=true 但 LLM_DUAL_MODAL_ENABLED=false;"
            "純文字模態下模型看不到原圖,自評信心度品質較差,"
            "建議一併啟用雙模態或改以多引擎共識作為信心度來源。"
        )

    # 分層成本控制的效益取決於實測升級觸發率(需求 5;設定於任務 13 加入)
    if getattr(settings, "CASCADE_ENABLED", False):
        warnings.append(
            "CASCADE_ENABLED=true;分層僅在升級觸發率低時才省錢,"
            "觸發率高時反而更貴。請先取得基準實測觸發率再啟用。"
        )

    return warnings


def log_setting_conflicts(settings: Any) -> List[str]:
    """檢查並記錄設定衝突;回傳同一份警告清單供呼叫端使用"""
    warnings = check_setting_conflicts(settings)
    for message in warnings:
        logger.warning("⚠️ 設定衝突:%s", message)
    return warnings


__all__ = ["check_setting_conflicts", "log_setting_conflicts"]
