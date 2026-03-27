"""
合約文件處理器

實作合約文件的專門化處理邏輯，繼承 DocumentProcessor。
基礎版重用既有模組，Phase 2 將實作欄位提取功能。
"""

import logging
from typing import Dict, Any, Optional
from PIL import Image
import numpy as np

from .processor import DocumentProcessor
from .types import ContractStructuredData
from .contract_field_extractor import ContractFieldExtractor
from ..ocr_enhanced.config import PreprocessConfig
from ..ocr_enhanced.preprocessor import TranscriptPreprocessor
from ..ocr_enhanced.engine_manager import EngineManager
from ..ocr_enhanced.postprocessor import TranscriptPostprocessor

logger = logging.getLogger(__name__)


class ContractProcessor(DocumentProcessor):
    """
    合約文件處理器

    實作合約文件的專門化處理邏輯,繼承 DocumentProcessor 抽象基類。
    基礎版重用既有模組,Phase 2 將實作結構化欄位提取功能。

    與 TranscriptProcessor 的差異:
    - 預處理器禁用浮水印移除（合約通常無浮水印）
    - 啟用更強的去噪處理
    - extract_fields() 目前返回空結構（Phase 2 實作）

    處理流程:
        1. preprocess: 使用 TranscriptPreprocessor（合約專用配置）
        2. extract_text: 使用 EngineManager 進行 OCR 辨識
        3. postprocess: 使用 TranscriptPostprocessor 進行後處理
        4. extract_fields: 返回空的 ContractStructuredData（Phase 2 實作）

    Example:
        >>> processor = ContractProcessor()
        >>> result = await processor.process(
        ...     file_contents=pdf_bytes,
        ...     filename="合約.pdf",
        ...     page_number=1,
        ...     total_pages=3,
        ...     enable_llm=True
        ... )
    """

    def __init__(self) -> None:
        """
        初始化合約處理器

        創建並配置 TranscriptPreprocessor, EngineManager, TranscriptPostprocessor。
        使用合約專用配置（禁用浮水印移除、啟用去噪）。
        """
        logger.info("初始化 ContractProcessor")

        # 初始化預處理器（合約專用配置）
        preprocess_config = PreprocessConfig(
            enable_watermark_removal=False,  # 合約通常無浮水印
            enable_binarization=False,       # 保持與謄本一致
            enable_denoising=True            # 合約可能需要更強的去噪
        )
        self.preprocessor = TranscriptPreprocessor(config=preprocess_config)

        # 初始化 OCR 引擎管理器（與謄本相同配置）
        self.engine_manager = EngineManager(
            engines=["tesseract"],
            parallel=False,
            fusion_method="best"
        )

        # 初始化後處理器（與謄本相同配置）
        self.postprocessor = TranscriptPostprocessor(
            enable_typo_fix=True,
            enable_format_correction=True,
            enable_llm=False,  # 將由 process() 方法的 enable_llm 參數控制
            llm_provider="openai",
            llm_strategy="auto"
        )

        # 初始化欄位提取器（Phase 2）
        self.field_extractor = ContractFieldExtractor()

        logger.info("ContractProcessor 初始化完成")

    async def preprocess(self, image: Image.Image) -> Image.Image:
        """
        預處理圖像

        委派給 TranscriptPreprocessor 進行合約專用的預處理。
        使用合約專用配置：禁用浮水印移除、啟用去噪。

        Args:
            image: PIL Image 物件

        Returns:
            處理後的 Image 物件

        Raises:
            Exception: 預處理失敗時拋出異常
        """
        logger.debug("開始預處理合約圖像")

        try:
            # 調用既有的 TranscriptPreprocessor
            processed_array, metadata = await self.preprocessor.preprocess(image)

            # 轉換 numpy array 回 PIL Image
            # TranscriptPreprocessor 返回 BGR 格式的 numpy array
            # 需要轉換回 RGB 格式
            if len(processed_array.shape) == 3 and processed_array.shape[2] == 3:
                # 彩色圖像：BGR -> RGB (交換紅藍通道)
                rgb_array = processed_array[:, :, ::-1].copy()
            else:
                # 灰度圖像：直接使用
                rgb_array = processed_array

            processed_image = Image.fromarray(rgb_array)

            logger.debug(
                f"預處理完成，去噪: {metadata.get('denoising_applied', False)}"
            )

            return processed_image

        except Exception as e:
            logger.error(f"合約預處理失敗: {str(e)}", exc_info=True)
            raise

    async def extract_text(self, image: Image.Image) -> tuple[str, float]:
        """
        從圖像中提取文字

        委派給 EngineManager 使用 OCR 引擎進行文字辨識。
        與謄本使用相同的 OCR 邏輯。

        Args:
            image: 預處理後的 Image 物件

        Returns:
            (文字內容, OCR 信心度)
            - 文字內容: 辨識出的文字字串
            - OCR 信心度: 0.0 到 1.0 之間的浮點數

        Raises:
            Exception: OCR 處理失敗時拋出異常
        """
        logger.debug("開始 OCR 文字提取")

        try:
            # 轉換 PIL Image 為 numpy array
            # EngineManager 需要 numpy array 作為輸入
            image_array = np.array(image)

            # 轉換 RGB 為 BGR（OpenCV 格式）
            if len(image_array.shape) == 3 and image_array.shape[2] == 3:
                # RGB -> BGR (交換紅藍通道)
                image_array = image_array[:, :, ::-1].copy()

            # 調用 EngineManager 提取文字
            text, confidence, _engine_results = \
                await self.engine_manager.extract_text_multi_engine(image_array)

            logger.debug(f"OCR 完成，信心度: {confidence:.2f}")

            return text, confidence

        except Exception as e:
            logger.error(f"合約文字提取失敗: {str(e)}", exc_info=True)
            raise

    async def postprocess(
        self,
        text: str,
        confidence: float,
        image_data: Optional[str] = None
    ) -> tuple[str, Dict[str, Any]]:
        """
        後處理文字

        委派給 TranscriptPostprocessor 進行錯別字修正、格式校正。
        合約文件可能包含專業法律用語，使用與謄本相同的後處理邏輯。

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
        logger.debug("開始後處理文字")

        try:
            # 調用 TranscriptPostprocessor
            processed_text, stats = await self.postprocessor.postprocess(
                text,
                ocr_confidence=confidence,
                image_data=image_data
            )

            logger.debug(
                f"後處理完成，錯別字修正: {stats.get('typo_fixes', 0)} 次"
            )

            return processed_text, stats

        except Exception as e:
            logger.error(f"合約後處理失敗: {str(e)}", exc_info=True)
            raise

    async def extract_fields(
        self,
        text: str,
        image_data: Optional[str] = None,
        enable_llm: bool = False
    ) -> ContractStructuredData:
        """
        提取結構化欄位

        使用 ContractFieldExtractor 從合約文字中提取結構化欄位。
        包含合約編號、簽訂日期、雙方資訊、金額等關鍵欄位。

        當啟用 LLM 且正則提取信心度低於 0.7 時，會自動調用 GPT-4o Vision
        進行視覺輔助提取，提升準確率。

        Args:
            text: OCR 辨識的合約文字
            image_data: base64 編碼的圖像資料（啟用 LLM 時需要）
            enable_llm: 是否啟用 LLM 視覺輔助提取（預設 False）

        Returns:
            ContractStructuredData: 合約結構化資料
            - contract_metadata: 合約元資訊（編號、日期等）
            - parties: 雙方資訊（甲方、乙方、地址）
            - financial_terms: 財務條款（金額、幣別、付款方式）
            - extraction_confidence: 提取信心度 (0.0 - 1.0)

        Raises:
            Exception: 欄位提取失敗時拋出異常（但會捕獲並返回空結構）

        Example:
            >>> processor = ContractProcessor()
            >>> result = await processor.extract_fields(
            ...     text=ocr_text,
            ...     image_data=base64_image,
            ...     enable_llm=True
            ... )
            >>> print(f"信心度: {result['extraction_confidence']:.2%}")
        """
        logger.debug(
            f"提取結構化欄位（LLM: {'啟用' if enable_llm else '禁用'}）"
        )

        try:
            # 使用 ContractFieldExtractor 提取欄位
            result = await self.field_extractor.extract(
                text=text,
                image_data=image_data,
                use_llm_fallback=enable_llm
            )

            logger.info(
                f"欄位提取完成，信心度: {result['extraction_confidence']:.2%}"
                + (f"（LLM 輔助）" if enable_llm and result['extraction_confidence'] >= 0.7 else "")
            )

            return result

        except Exception as e:
            logger.error(f"欄位提取失敗: {str(e)}", exc_info=True)
            # 發生錯誤時返回空結構
            return {
                "contract_metadata": {
                    "contract_number": None,
                    "signing_date": None,
                    "effective_date": None,
                },
                "parties": {
                    "party_a": None,
                    "party_b": None,
                    "party_a_address": None,
                    "party_b_address": None,
                },
                "financial_terms": {
                    "contract_amount": None,
                    "currency": None,
                    "payment_method": None,
                    "payment_deadline": None,
                },
                "extraction_confidence": 0.0
            }
