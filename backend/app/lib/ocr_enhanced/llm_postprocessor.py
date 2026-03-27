"""
LLM Postprocessor Module

使用 LLM (Claude/GPT) 進行智能 OCR 錯誤修正
"""

import re
from typing import Optional, Literal
from app.lib.llm_service import LLMService


class LLMPostprocessor:
    """
    LLM 智能後處理器

    使用語言模型修正 OCR 錯誤，提升準確率
    """

    def __init__(
        self,
        provider: Literal["anthropic", "openai"] = "anthropic",
        model: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        """
        初始化 LLM 後處理器

        Args:
            provider: LLM 提供商 (anthropic/openai)
            model: 模型名稱，None 使用預設
            api_key: API 金鑰，None 從環境變數讀取
        """
        # 使用統一的 LLMService
        self.llm_service = LLMService(
            provider=provider,
            model=model,
            api_key=api_key
        )

        # 保持向後兼容
        self.provider = provider
        self.model = self.llm_service.model

    @property
    def stats(self):
        """獲取統計資料（向後兼容）"""
        return self.llm_service.get_stats()

    async def correct_full_text(
        self,
        ocr_text: str,
        doc_type: str = "transcript",
        image_data: Optional[str] = None
    ) -> tuple[str, dict]:
        """
        全文修正（適合低信心度文件）

        Args:
            ocr_text: OCR 原始文字
            doc_type: 文件類型
            image_data: base64 編碼的圖片資料（可選，提供可提升準確率）

        Returns:
            (修正後文字, 統計資訊)
        """
        # 使用詳細的提示詞（保持原有的高品質 prompt）
        prompt = self._build_full_text_prompt(ocr_text, doc_type)

        # 調用 LLMService
        corrected_text = await self.llm_service.call(
            prompt=prompt,
            image_data=image_data,
            max_tokens=3000,
            temperature=0.1
        )

        return corrected_text, self.stats

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

        result = await self.llm_service.call(prompt, max_tokens=50)
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

        result = await self.llm_service.call(prompt, max_tokens=50)
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

        result = await self.llm_service.call(prompt, max_tokens=30)
        return result.strip()

    async def _correct_area(self, candidate: str) -> str:
        """修正面積"""
        prompt = f"""修正這個面積資料：

OCR 結果: "{candidate}"

格式: 數字 + "平方公尺"
例如: 153.00平方公尺

請直接輸出修正後的面積，不要解釋。"""

        result = await self.llm_service.call(prompt, max_tokens=50)
        return result.strip()

    def _apply_corrections(self, text: str, corrections: dict) -> str:
        """應用修正到文字"""
        result = text

        for field_name, correction in corrections.items():
            original = correction["original"]
            corrected = correction["corrected"]

            if original != corrected and original in result:
                result = result.replace(original, corrected, 1)

        return result

    def _build_full_text_prompt(self, ocr_text: str, doc_type: str) -> str:
        """建立全文修正提示詞（優化版：加入更多範例和明確指引）"""
        prompt = f"""你是專業的台灣地政謄本 OCR 錯誤修正專家。請修正以下 OCR 辨識的錯誤文字。

【重要原則】
1. **請仔細查看上面提供的文件圖片**，對照圖片中的實際文字來修正 OCR 錯誤
2. 只修正明顯的 OCR 錯誤，不要過度解讀或改寫
3. 保持原文的所有內容，包括數字、符號、換行
4. 無法確定的文字請參考圖片，如果圖片也看不清楚則保持原樣

【常見 OCR 錯誤對照表】
文字錯誤：
- 十 → 土（土地）
- 膽/徐/朕 → 謄（謄本）
- 攝 → 登（登記）
- 焉/班 → 正（中正）
- 息 → 段（正段）
- 旋 → 段（小段）
- 傑/樺 → 權（所有權）
- 園/闕 → 圍（範圍）
- 蕉 → 共（共4棟）
- 害 → 割（分割）
- 勁為 → 鑑界
- 朕 → 謄

數字與字母錯誤：
- o/O → 0（地號中）
- l/I/| → 1
- 空格要移除（地號中不能有空格）

【台灣地政謄本標準格式範例】
正確格式：
✓ 土地登記第三類謄本（所有權個人全部）
✓ 中正區中正段三小段 0221-0000 地號
✓ 列印時間：民國108年04月09日17時09分
✓ 本謄本係網路申領之電子謄本，由申請人自行列印
✓ 謄本種類碼：L944V64QT3
✓ 建成地政事務所 主任 曾錫雄
✓ 登記日期：民國075年05月27日
✓ 登記原因：鑑界分割
✓ 面積：153.00平方公尺
✓ 所有權人：黃水木
✓ 統一編號：A202******6
✓ 權利範圍：全部

【修正範例】
錯誤：十:攝登記第三類有徐生 (所有權個人人金義5》 全
正確：土地登記第三類謄本（所有權個人全部）

錯誤：中焉區中班息三小旋 o221-oooolta中的0
正確：中正區中正段三小段 0221-0000 地號

錯誤：電子朕本
正確：電子謄本

錯誤：膽本種類碼
正確：謄本種類碼

錯誤：勁為分割
正確：鑑界分割

錯誤：蕉4棟
正確：共4棟

錯誤：因分害增加地號
正確：因分割增加地號

【要修正的 OCR 文字】
{ocr_text}

請直接輸出修正後的完整文字，不要添加任何解釋或說明。保持所有原有的換行和格式。"""

        return prompt



# ============================================================================
# 匯出
# ============================================================================

__all__ = [
    "LLMPostprocessor",
]
