"""
OCR Postprocessor Module

OCR 後處理模組，提供錯別字修正、格式校正等功能。
"""

import re
from typing import Optional, Literal

from .typo_dict import (
    ALL_TYPOS,
    TRANSCRIPT_KEYWORDS,
    LAND_NUMBER_PATTERN,
    UNIFIED_ID_PATTERN,
    ROC_DATE_PATTERN,
    AREA_PATTERN,
)


class TranscriptPostprocessor:
    """
    謄本文件後處理器

    提供 OCR 後處理功能，包括錯別字修正、格式校正、LLM 智能修正等。

    智能策略：
    - 高信心度 (>0.8): 只用規則修正
    - 中信心度 (0.6-0.8): 關鍵欄位用 LLM
    - 低信心度 (<0.6): 全文用 LLM
    """

    def __init__(
        self,
        enable_typo_fix: bool = True,
        enable_format_correction: bool = True,
        enable_llm: bool = False,
        llm_provider: Literal["anthropic", "openai"] = "anthropic",
        llm_strategy: Literal["auto", "full", "fields", "none"] = "auto"
    ):
        """
        初始化後處理器

        Args:
            enable_typo_fix: 是否啟用錯別字修正
            enable_format_correction: 是否啟用格式校正
            enable_llm: 是否啟用 LLM 修正
            llm_provider: LLM 提供商
            llm_strategy: LLM 策略 (auto/full/fields/none)
        """
        self.enable_typo_fix = enable_typo_fix
        self.enable_format_correction = enable_format_correction
        self.enable_llm = enable_llm
        self.llm_strategy = llm_strategy

        # LLM 後處理器（延遲初始化）
        self.llm_processor = None
        if enable_llm:
            try:
                from .llm_postprocessor import LLMPostprocessor
                self.llm_processor = LLMPostprocessor(provider=llm_provider)
            except Exception as e:
                print(f"⚠️  LLM 後處理器初始化失敗: {e}")
                print(f"   將繼續使用規則修正")
                self.enable_llm = False

        # 統計資訊
        self.stats = {
            "typo_fixes": 0,
            "format_corrections": 0,
            "total_chars_before": 0,
            "total_chars_after": 0,
            "llm_used": False,
            "llm_cost": 0.0,
        }

    async def postprocess(
        self,
        text: str,
        ocr_confidence: float = 1.0,
        image_data: Optional[str] = None
    ) -> tuple[str, dict]:
        """
        執行完整的後處理流程

        Args:
            text: OCR 原始文字
            ocr_confidence: OCR 信心度 (0-1)，用於智能策略
            image_data: base64 編碼的圖片資料（可選，提供給 LLM 用於視覺修正）

        Returns:
            (處理後文字, 統計資訊)

        Processing Pipeline:
            1. 規則修正（錯別字、格式）
            2. LLM 智能修正（根據信心度，可搭配圖片）
            3. 清理與優化
        """
        # 重置統計
        self.stats = {
            "typo_fixes": 0,
            "format_corrections": 0,
            "total_chars_before": len(text),
            "total_chars_after": 0,
            "llm_used": False,
            "llm_cost": 0.0,
        }

        processed_text = text

        # ========== 階段 1: 規則修正 ==========
        # 1. 錯別字修正
        if self.enable_typo_fix:
            processed_text = self.fix_traditional_chinese_typos(processed_text)

        # 2. 格式校正
        if self.enable_format_correction:
            processed_text = self.correct_field_formats(processed_text)

        # ========== 階段 2: LLM 智能修正 ==========
        if self.enable_llm and self.llm_processor:
            llm_result = await self._apply_llm_correction(
                processed_text,
                ocr_confidence,
                image_data
            )
            processed_text = llm_result["text"]
            self.stats["llm_used"] = llm_result["used"]
            self.stats["llm_cost"] = llm_result.get("cost", 0.0)

        # ========== 階段 3: 清理優化 ==========
        processed_text = self._clean_whitespace(processed_text)

        # 更新統計
        self.stats["total_chars_after"] = len(processed_text)

        return processed_text, self.stats.copy()

    async def _apply_llm_correction(
        self,
        text: str,
        confidence: float,
        image_data: Optional[str] = None
    ) -> dict:
        """
        應用 LLM 修正（智能策略）

        Args:
            text: 文字
            confidence: OCR 信心度
            image_data: base64 編碼的圖片資料（可選）

        Returns:
            {
                "text": 修正後文字,
                "used": 是否使用了 LLM,
                "cost": 成本
            }
        """
        # 決定策略
        strategy = self._determine_llm_strategy(confidence)

        if strategy == "none":
            return {"text": text, "used": False, "cost": 0.0}

        try:
            if strategy == "full":
                # 全文修正（可搭配圖片）
                corrected, stats = await self.llm_processor.correct_full_text(
                    text,
                    image_data=image_data
                )
            elif strategy == "fields":
                # 欄位修正
                corrected, stats = await self.llm_processor.correct_fields(text)
            else:
                return {"text": text, "used": False, "cost": 0.0}

            return {
                "text": corrected,
                "used": True,
                "cost": self.llm_processor.stats.get("estimated_cost", 0.0)
            }

        except Exception as e:
            print(f"⚠️  LLM 修正失敗: {e}")
            return {"text": text, "used": False, "cost": 0.0}

    def _determine_llm_strategy(self, confidence: float) -> str:
        """
        決定 LLM 策略

        Args:
            confidence: OCR 信心度

        Returns:
            策略名稱 (full/fields/none)
        """
        if not self.enable_llm:
            return "none"

        if self.llm_strategy == "none":
            return "none"

        if self.llm_strategy == "full":
            return "full"

        if self.llm_strategy == "fields":
            return "fields"

        # auto 策略：根據信心度決定（優化版：更積極使用全文修正）
        if confidence < 0.85:
            # 信心度 < 85%：全文修正（測試顯示全文修正效果遠優於欄位修正）
            return "full"
        else:
            # 信心度 >= 85%：不使用 LLM（規則修正已足夠）
            return "none"

    def fix_traditional_chinese_typos(self, text: str) -> str:
        """
        修正繁體中文錯別字

        Task 7.2 實作

        Args:
            text: 原始文字

        Returns:
            修正後文字

        Process:
            1. 使用字典進行批量替換
            2. 優先處理長字串（避免部分匹配問題）
            3. 記錄修正次數
        """
        if not text:
            return text

        # 按字串長度排序（長的先處理，避免部分匹配）
        sorted_typos = sorted(ALL_TYPOS.items(), key=lambda x: len(x[0]), reverse=True)

        result = text
        fix_count = 0

        for wrong, correct in sorted_typos:
            if wrong in result:
                # 計算替換次數
                count = result.count(wrong)
                result = result.replace(wrong, correct)
                fix_count += count

        self.stats["typo_fixes"] = fix_count

        return result

    def correct_field_formats(self, text: str) -> str:
        """
        校正已知欄位格式

        Task 7.2 實作

        Args:
            text: 文字

        Returns:
            格式校正後文字

        Corrections:
            - 地號格式: XXXX-XXXX
            - 統一編號格式: 8位數字或遮罩格式
            - 日期格式: 民國XXX年XX月XX日
            - 面積格式: 數字 + 平方公尺
        """
        if not text:
            return text

        result = text
        correction_count = 0

        # 1. 修正地號格式
        # 例如: "地號: 0221 - 0000" → "地號: 0221-0000"
        def fix_land_number(match):
            nonlocal correction_count
            correction_count += 1
            return f"{match.group(1)}-{match.group(2)}"

        result = re.sub(
            r"地號[\s:：]*(\d{4})\s*[-\-]\s*(\d{4,8})",
            lambda m: f"地號: {fix_land_number(m)}",
            result
        )

        # 2. 修正統一編號格式
        # 確保統一編號格式正確
        result = re.sub(
            r"統一編號[\s:：]*([A-Z0-9\*]{8,10})",
            r"統一編號: \1",
            result
        )

        # 3. 修正民國日期格式
        # 例如: "民國108年04月09日" 確保格式統一
        def fix_roc_date(match):
            nonlocal correction_count
            correction_count += 1
            year, month, day = match.groups()
            return f"民國{year}年{month.zfill(2)}月{day.zfill(2)}日"

        result = re.sub(
            r"民國\s*(\d{2,3})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日",
            fix_roc_date,
            result
        )

        # 4. 修正面積格式
        # 統一為 "平方公尺"
        result = re.sub(
            r"(\d+\.?\d*)\s*平方公[米尺]",
            r"\1平方公尺",
            result
        )

        # 5. 修正常見欄位名稱
        field_names = {
            "所有傑": "所有權",
            "所有樺": "所有權",
            "權利範園": "權利範圍",
            "權利範闕": "權利範圍",
            "使用分園": "使用分區",
            "使用㆞類別": "使用地類別",
        }

        for wrong, correct in field_names.items():
            if wrong in result:
                result = result.replace(wrong, correct)
                correction_count += 1

        self.stats["format_corrections"] = correction_count

        return result

    def remove_duplicate_watermark_text(self, text: str) -> str:
        """
        移除重複的浮水印文字

        Task 7.3 實作

        Args:
            text: 文字

        Returns:
            移除浮水印後文字

        Removes:
            - "已列印" 重複出現
            - "本謄本列印完畢" 重複出現
            - 其他重複的干擾文字
        """
        if not text:
            return text

        result = text

        # 移除常見浮水印模式
        watermark_patterns = [
            r"已列印\s*已列印",  # 重複的"已列印"
            r"本謄本列印完畢\s*本謄本列印完畢",  # 重複的完畢訊息
            r"(\*{3,})",  # 多個星號（遮罩）
        ]

        for pattern in watermark_patterns:
            result = re.sub(pattern, "", result)

        return result

    def restore_logical_structure(self, text: str) -> str:
        """
        還原文件邏輯結構

        Task 7.3 實作

        Args:
            text: 文字

        Returns:
            結構化後文字

        Structure Markers:
            - 土地標示部
            - 土地所有權部
            - 建物標示部
            - 建物所有權部
            - 建物他項權利部
        """
        if not text:
            return text

        result = text

        # 標準化區塊標題
        section_titles = {
            "土㆞標示部": "土地標示部",
            "土㆞所有權部": "土地所有權部",
            "建物標不部": "建物標示部",
            "建物標元音": "建物標示部",
            "建物所有傑部": "建物所有權部",
            "建物他預耀利部": "建物他項權利部",
        }

        for wrong, correct in section_titles.items():
            if wrong in result:
                result = result.replace(wrong, correct)

        # 確保區塊標題前有換行
        section_markers = [
            "土地標示部",
            "土地所有權部",
            "建物標示部",
            "建物所有權部",
            "建物他項權利部",
        ]

        for marker in section_markers:
            # 在區塊標題前添加分隔線
            result = result.replace(
                marker,
                f"\n{'='*40}\n{marker}\n{'='*40}\n"
            )

        return result

    def _clean_whitespace(self, text: str) -> str:
        """
        清理多餘空白

        Args:
            text: 文字

        Returns:
            清理後文字
        """
        if not text:
            return text

        # 移除行尾空白
        lines = text.split('\n')
        lines = [line.rstrip() for line in lines]

        # 移除多餘空行（超過 2 個連續空行）
        result = '\n'.join(lines)
        result = re.sub(r'\n{3,}', '\n\n', result)

        return result

    def validate_transcript_content(self, text: str) -> dict:
        """
        驗證謄本內容完整性

        Args:
            text: 文字

        Returns:
            驗證結果 {
                "has_keywords": bool,
                "missing_keywords": list[str],
                "keyword_count": int,
                "confidence": float
            }
        """
        missing_keywords = []
        found_count = 0

        for keyword in TRANSCRIPT_KEYWORDS:
            if keyword in text:
                found_count += 1
            else:
                missing_keywords.append(keyword)

        confidence = found_count / len(TRANSCRIPT_KEYWORDS)

        return {
            "has_keywords": found_count >= len(TRANSCRIPT_KEYWORDS) * 0.6,  # 至少 60%
            "missing_keywords": missing_keywords,
            "keyword_count": found_count,
            "total_keywords": len(TRANSCRIPT_KEYWORDS),
            "confidence": confidence
        }


# ============================================================================
# 匯出
# ============================================================================

__all__ = [
    "TranscriptPostprocessor",
]
