"""
LLM Postprocessor Module

使用 LLM 進行智能 OCR 錯誤修正。

任務 8.1 起,模型一律經 `llm_service.providers.create_provider()` 取得,
不再直接綁定僅支援雲端的 LLMService——此抽象同時提供本地部署選項與
LLM_CLOUD_ENABLED 隱私守衛(需求 2.6、2.7)。全文校正委派給
DualModalCorrector,由它決定雙模態 / 純文字降級 / 模型拒絕三條路徑。
"""

import logging
import re
from typing import Optional

from app.lib.llm_service.providers import create_provider
from .dual_modal_corrector import (
    CorrectionResult,
    DualModalCorrector,
    build_correction_prompt,
    is_refusal,
)

logger = logging.getLogger(__name__)


class LLMPostprocessor:
    """
    LLM 智能後處理器

    使用語言模型修正 OCR 錯誤，提升準確率
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        """
        初始化 LLM 後處理器

        Args:
            provider: LLM 提供商 (openai/anthropic/local_qwen)，None 依 settings.LLM_PROVIDER
            model: 模型名稱，None 使用該 Provider 預設
            api_key: API 金鑰，None 從環境變數讀取
        """
        # 隱私守衛在此生效:雲端停用時 create_provider 會直接拒絕建立雲端 Provider
        self._provider = create_provider(provider, model=model, api_key=api_key)
        self._corrector = DualModalCorrector(provider=self._provider)

        # 保持向後兼容
        self.provider = provider
        self.model = getattr(self._provider, "model", model)
        self.last_result: Optional[CorrectionResult] = None

    @property
    def stats(self):
        """獲取統計資料（向後兼容，含 estimated_cost）"""
        return dict(self._provider.stats)

    async def correct_full_text(
        self,
        ocr_text: str,
        doc_type: str = "transcript",
        image_data: Optional[str] = None
    ) -> tuple[str, dict]:
        """
        全文修正（適合低信心度文件）

        影像僅在 LLM_DUAL_MODAL_ENABLED=true 時送出;關閉時行為與現行純文字校正一致。

        Args:
            ocr_text: OCR 原始文字
            doc_type: 文件類型
            image_data: base64 編碼的圖片資料（可選，雙模態啟用時提升準確率）

        Returns:
            (修正後文字, 統計資訊)；完整路徑資訊見 self.last_result
        """
        result = await self._corrector.correct(
            ocr_text=ocr_text,
            doc_type=doc_type,
            image_data=image_data,
        )
        self.last_result = result

        if result["refused"]:
            logger.warning("LLM 拒絕處理，回退使用原始文字")

        return result["text"], self.stats

    async def correct_fields(
        self,
        ocr_text: str,
        fields_to_correct: Optional[list[str]] = None
    ) -> tuple[str, dict]:
        """
        欄位級修正（精確控制）

        Args:
            ocr_text: OCR 原始文字
            fields_to_correct: 要修正的欄位列表，None=全部

        Returns:
            (修正後文字, 修正詳情)
        """
        # 提取候選欄位
        candidates = self._extract_field_candidates(ocr_text)

        # 決定要修正的欄位
        if fields_to_correct is None:
            fields_to_correct = list(candidates.keys())

        corrections = {}

        # 逐欄位修正
        for field_name in fields_to_correct:
            if field_name not in candidates:
                continue

            candidate_value = candidates[field_name]

            # 根據欄位類型選擇修正方法
            if field_name == "land_number":
                corrected = await self._correct_land_number(candidate_value)
            elif field_name == "date":
                corrected = await self._correct_date(candidate_value)
            elif field_name == "owner":
                corrected = await self._correct_owner(candidate_value)
            elif field_name == "area":
                corrected = await self._correct_area(candidate_value)
            else:
                corrected = candidate_value

            corrections[field_name] = {
                "original": candidate_value,
                "corrected": corrected
            }

        # 應用修正
        corrected_text = self._apply_corrections(ocr_text, corrections)

        return corrected_text, corrections

    def _extract_field_candidates(self, text: str) -> dict:
        """提取候選欄位"""
        candidates = {}

        # 地號
        land_number_patterns = [
            r"地號[\s:：]*([0-9oOlI\-\s]{8,20})",
            r"(\d{4}[\s\-oOlI]{1,3}\d{4,8})",
        ]
        for pattern in land_number_patterns:
            match = re.search(pattern, text)
            if match:
                candidates["land_number"] = match.group(1).strip()
                break

        # 日期
        date_pattern = r"民國\s*(\d{2,3})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"
        match = re.search(date_pattern, text)
        if match:
            candidates["date"] = match.group(0)

        # 面積
        area_pattern = r"面積[\s:：]*(\d+\.?\d*)\s*平方公[尺米]"
        match = re.search(area_pattern, text)
        if match:
            candidates["area"] = match.group(0)

        # 所有權人（簡單提取）
        owner_pattern = r"所有權人[\s:：]*([^\n]{2,20})"
        match = re.search(owner_pattern, text)
        if match:
            candidates["owner"] = match.group(1).strip()

        return candidates

    async def _correct_land_number(self, candidate: str) -> str:
        """修正地號"""
        prompt = f"""修正這個台灣地號格式：

OCR 結果: "{candidate}"

地號標準格式: XXXX-XXXX 或 XXXX-XXXXXXXX
常見 OCR 錯誤:
- o/O → 0
- l/I → 1
- 空格要移除
- 只保留數字和連字號

請直接輸出修正後的地號，格式為 XXXX-XXXX，不要解釋。
如果無法修正，輸出 "INVALID"。"""

        result = await self._provider.call(prompt, max_tokens=50)
        result = result.strip().replace(" ", "")

        # 驗證格式
        if re.match(r"^\d{4}-\d{4,8}$", result):
            return result
        else:
            return candidate  # 無法修正，返回原值

    async def _correct_date(self, candidate: str) -> str:
        """修正日期"""
        prompt = f"""修正這個民國紀年日期：

OCR 結果: "{candidate}"

正確格式: 民國XXX年XX月XX日
規則:
- 年份: 2-3位數字
- 月份: 01-12
- 日期: 01-31

請直接輸出修正後的日期，不要解釋。"""

        result = await self._provider.call(prompt, max_tokens=50)
        return result.strip()

    async def _correct_owner(self, candidate: str) -> str:
        """修正所有權人"""
        prompt = f"""修正這個人名：

OCR 結果: "{candidate}"

規則:
- 台灣常見姓名
- 移除特殊符號
- 修正常見 OCR 錯誤

請直接輸出修正後的姓名，不要解釋。"""

        result = await self._provider.call(prompt, max_tokens=30)
        return result.strip()

    async def _correct_area(self, candidate: str) -> str:
        """修正面積"""
        prompt = f"""修正這個面積資料：

OCR 結果: "{candidate}"

格式: 數字 + "平方公尺"
例如: 153.00平方公尺

請直接輸出修正後的面積，不要解釋。"""

        result = await self._provider.call(prompt, max_tokens=50)
        return result.strip()

    def _is_refusal(self, text: str) -> bool:
        """檢查 LLM 回應是否為拒絕訊息（委派共用實作，避免兩份規則分歧）"""
        return is_refusal(text)

    def _apply_corrections(self, text: str, corrections: dict) -> str:
        """應用修正到文字"""
        result = text

        for field_name, correction in corrections.items():
            original = correction["original"]
            corrected = correction["corrected"]

            if original != corrected and original in result:
                result = result.replace(original, corrected, 1)

        return result

    def _build_full_text_prompt(
        self, ocr_text: str, doc_type: str, has_image: bool = False
    ) -> str:
        """建立全文修正提示詞（委派共用實作）

        提示詞須與實際模態一致:純文字模態不得保留「查看圖片」的指示，
        否則等於要模型對照一張不存在的圖（任務 8.3）。
        """
        return build_correction_prompt(ocr_text, doc_type, has_image=has_image)


# ============================================================================
# 匯出
# ============================================================================

__all__ = [
    "LLMPostprocessor",
]
