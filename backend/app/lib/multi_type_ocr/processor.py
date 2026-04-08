"""
文件處理器抽象基類

定義所有文件類型處理器必須實作的介面與標準處理流程。
使用模板方法模式確保處理流程一致性。
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from PIL import Image
import io
import base64

from .types import PageResult, OcrRawResult, RulePostprocessedResult

logger = logging.getLogger(__name__)


class DocumentProcessor(ABC):
    """
    文件處理器抽象基類

    定義所有文件類型處理器必須實作的介面。
    使用模板方法模式統一編排處理流程。

    子類別必須實作以下抽象方法：
    - preprocess: 圖像預處理
    - extract_text: 文字提取
    - postprocess: 文字後處理
    - extract_fields: 結構化欄位提取

    Example:
        class MyProcessor(DocumentProcessor):
            async def preprocess(self, image):
                # 實作預處理邏輯
                return processed_image

            async def extract_text(self, image):
                # 實作 OCR 邏輯
                return (text, confidence)

            async def postprocess(self, text, confidence, image_data=None):
                # 實作後處理邏輯
                return (processed_text, stats)

            async def extract_fields(self, text):
                # 實作欄位提取邏輯
                return fields_dict
    """

    @abstractmethod
    async def preprocess(self, image: Image.Image) -> Image.Image:
        """
        預處理圖像

        對原始圖像進行預處理，如去噪、二值化、增強對比度等。
        不同文件類型可能需要不同的預處理策略。

        Args:
            image: PIL Image 物件

        Returns:
            處理後的 Image 物件

        Raises:
            Exception: 預處理失敗時拋出異常
        """
        pass

    @abstractmethod
    async def extract_text(self, image: Image.Image) -> tuple[str, float]:
        """
        從圖像中提取文字

        使用 OCR 引擎從預處理後的圖像中提取文字。

        Args:
            image: 預處理後的 Image 物件

        Returns:
            (文字內容, OCR 信心度)
            - 文字內容: 辨識出的文字字串
            - OCR 信心度: 0.0 到 1.0 之間的浮點數

        Raises:
            Exception: OCR 處理失敗時拋出異常
        """
        pass

    @abstractmethod
    async def postprocess(
        self,
        text: str,
        confidence: float,
        image_data: Optional[str] = None
    ) -> tuple[str, Dict[str, Any]]:
        """
        後處理文字

        對 OCR 結果進行後處理，如錯別字修正、格式校正、LLM 修正等。

        Args:
            text: 原始 OCR 文字
            confidence: OCR 信心度
            image_data: base64 編碼的圖像（可選，供 LLM 使用）

        Returns:
            (修正後文字, 處理統計)
            - 修正後文字: 後處理後的文字字串
            - 處理統計: 包含修正次數、使用的工具等統計資訊

        Raises:
            Exception: 後處理失敗時拋出異常
        """
        pass

    @abstractmethod
    async def extract_fields(
        self,
        text: str,
        image_data: Optional[str] = None,
        enable_llm: bool = False
    ) -> Dict[str, Any]:
        """
        提取結構化欄位

        從文字中提取結構化資訊。不同文件類型提取不同欄位。
        例如：謄本提取地號、面積；合約提取合約編號、雙方、金額等。

        Args:
            text: OCR 文字
            image_data: base64 編碼的圖像資料（可選，供 LLM 視覺提取使用）
            enable_llm: 是否啟用 LLM 輔助提取（預設 False）

        Returns:
            結構化欄位字典，格式依文件類型而異

        Raises:
            Exception: 欄位提取失敗時拋出異常
        """
        pass

    async def process(
        self,
        file_contents: bytes,
        filename: str,
        page_number: int,
        total_pages: int,
        enable_llm: bool
    ) -> PageResult:
        """
        處理單一頁面（模板方法）

        定義標準處理流程，編排所有處理步驟。
        子類別通常不需要覆寫此方法，而是實作各個抽象方法。

        處理流程：
        1. 載入圖像
        2. 預處理
        3. OCR 文字提取
        4. 後處理（包含規則修正與可選的 LLM 修正）
        5. 結構化欄位提取
        6. 組裝結果

        Args:
            file_contents: 圖像檔案的二進制內容
            filename: 檔案名稱
            page_number: 當前頁碼
            total_pages: 總頁數
            enable_llm: 是否啟用 LLM 後處理

        Returns:
            包含完整處理結果的字典，符合 PageResult 格式

        Raises:
            Exception: 處理過程中任何步驟失敗時拋出異常
        """
        logger.info(
            f"開始處理頁面 {page_number}/{total_pages}: {filename}"
        )

        try:
            # 步驟 1: 載入圖像
            logger.debug(f"載入圖像: {filename}")
            loaded_image = Image.open(io.BytesIO(file_contents))

            # 轉換為 RGB（如果需要）
            if loaded_image.mode != 'RGB':
                image = loaded_image.convert('RGB')
            else:
                image = loaded_image

            # 保存原始圖像為 base64
            original_image_bytes = io.BytesIO()
            image.save(original_image_bytes, format='PNG')
            original_image_b64 = base64.b64encode(
                original_image_bytes.getvalue()
            ).decode('utf-8')
            original_image_data = f"data:image/png;base64,{original_image_b64}"

            # 步驟 2: 預處理
            logger.debug("執行預處理")
            preprocessed_image = await self.preprocess(image)

            # 步驟 3: OCR 文字提取
            logger.debug("執行 OCR 文字提取")
            raw_text, ocr_confidence = await self.extract_text(preprocessed_image)

            ocr_raw_result: OcrRawResult = {
                "text": raw_text,
                "confidence": ocr_confidence
            }

            # 步驟 4: 後處理
            logger.debug("執行後處理")
            image_data_for_llm = original_image_b64 if enable_llm else None
            postprocessed_text, postprocess_stats = await self.postprocess(
                raw_text,
                ocr_confidence,
                image_data_for_llm
            )

            rule_postprocessed_result: RulePostprocessedResult = {
                "text": postprocessed_text,
                "stats": postprocess_stats
            }

            # 組裝 LLM 後處理結果
            llm_used = postprocess_stats.get("llm_used", False)
            llm_postprocessed_result = None
            if llm_used:
                llm_postprocessed_result = {
                    "text": postprocessed_text,
                    "stats": {
                        "llm_used": True,
                        "llm_cost": postprocess_stats.get("llm_cost", 0.0)
                    },
                    "used": True
                }

            # 步驟 5: 結構化欄位提取
            logger.debug("執行結構化欄位提取")
            structured_data = await self.extract_fields(
                postprocessed_text,
                image_data=original_image_b64 if enable_llm else None,
                enable_llm=enable_llm
            )

            # 步驟 6: 組裝結果
            llm_step = "✓ 完成（視覺修正）" if llm_used else "⊗ 未使用"
            result: PageResult = {
                "page_number": page_number,
                "original_image": original_image_data,
                "ocr_raw": ocr_raw_result,
                "rule_postprocessed": rule_postprocessed_result,
                "llm_postprocessed": llm_postprocessed_result,
                "structured_data": structured_data if structured_data else None,
                "accuracy": None,  # 需要 ground_truth 才能計算
                "processing_steps": {
                    "1_preprocess": "完成",
                    "2_ocr": "完成",
                    "3_postprocess": "完成",
                    "4_llm": llm_step,
                    "5_extract_fields": "完成"
                }
            }

            logger.info(
                f"頁面 {page_number}/{total_pages} 處理完成，"
                f"OCR 信心度: {ocr_confidence:.2f}"
            )

            return result

        except Exception as e:
            logger.error(
                f"處理頁面 {page_number}/{total_pages} 失敗: {str(e)}",
                exc_info=True
            )
            raise
