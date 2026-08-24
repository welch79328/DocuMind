"""
謄本文件處理器

封裝既有的謄本處理邏輯為 TranscriptProcessor,確保向後兼容。
重用 ocr_enhanced 套件中的 TranscriptPreprocessor, EngineManager, TranscriptPostprocessor。
"""

import logging
from typing import Dict, Any, Optional
from PIL import Image

from .processor import OcrDocumentProcessor
from ..ocr_enhanced.config import PreprocessConfig
from ..ocr_enhanced.preprocessor import TranscriptPreprocessor
from ..ocr_enhanced.engine_manager import EngineManager
from ..ocr_enhanced.postprocessor import TranscriptPostprocessor
from .transcript_field_extractor import TranscriptFieldExtractor

logger = logging.getLogger(__name__)


class TranscriptProcessor(OcrDocumentProcessor):
    """
    謄本文件處理器

    封裝既有的謄本處理邏輯,繼承 DocumentProcessor 抽象基類。
    通過組合方式使用 ocr_enhanced 套件的既有模組,確保向後兼容性。

    處理流程:
        1. preprocess: 使用 TranscriptPreprocessor 進行預處理
        2. extract_text: 使用 EngineManager 進行 OCR 辨識
        3. postprocess: 使用 TranscriptPostprocessor 進行後處理
        4. extract_fields: 返回空字典(未來擴展)

    Example:
        >>> processor = TranscriptProcessor()
        >>> result = await processor.process(
        ...     file_contents=pdf_bytes,
        ...     filename="謄本.pdf",
        ...     page_number=1,
        ...     total_pages=1,
        ...     enable_llm=True
        ... )
    """

    def __init__(self) -> None:
        """
        初始化謄本處理器

        創建並配置 TranscriptPreprocessor, EngineManager, TranscriptPostprocessor。
        使用預設配置確保與既有系統行為一致。
        """
        logger.info("初始化 TranscriptProcessor")

        # 初始化預處理器（預設含浮水印移除）
        preprocess_config = PreprocessConfig()
        self.preprocessor = TranscriptPreprocessor(config=preprocess_config)

        # 初始化 OCR 引擎管理器（依設定啟用 PaddleOCR;繁中優先,PaddleOCR 惰性載入）
        from app.config import settings
        self.engine_manager = EngineManager(
            engines=list(settings.OCR_ENGINES),
            parallel=settings.OCR_PARALLEL_ENGINES,
            fusion_method=settings.OCR_FUSION_METHOD,
            paddleocr_lang=settings.OCR_PADDLEOCR_LANG,
        )

        # 初始化後處理器（LLM 由 process() 的 enable_llm 參數動態控制）
        self.llm_provider = "openai"
        self.llm_strategy = "auto"

        logger.info("TranscriptProcessor 初始化完成")

    async def preprocess(self, image: Image.Image) -> Image.Image:
        """
        預處理圖像

        委派給 TranscriptPreprocessor 進行謄本專用的預處理。
        處理浮水印移除、解析度提升等操作。

        Args:
            image: PIL Image 物件

        Returns:
            處理後的 Image 物件

        Raises:
            Exception: 預處理失敗時拋出異常
        """
        logger.debug("開始預處理圖像")

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
                f"預處理完成，浮水印移除: {metadata.get('watermark_removed', False)}"
            )

            return processed_image

        except Exception as e:
            logger.error(f"預處理失敗: {str(e)}", exc_info=True)
            raise

    async def extract_text(self, image: Image.Image) -> tuple[str, float]:
        """
        從圖像中提取文字

        委派給 EngineManager 使用 OCR 引擎進行文字辨識。

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
            # 轉換為 EngineManager 所需的 BGR numpy array(共用輔助方法)
            image_array = self._to_bgr_array(image)

            # 調用 EngineManager 提取文字
            text, confidence, _engine_results = \
                await self.engine_manager.extract_text_multi_engine(image_array)

            logger.debug(f"OCR 完成，信心度: {confidence:.2f}")

            return text, confidence

        except Exception as e:
            logger.error(f"文字提取失敗: {str(e)}", exc_info=True)
            raise

    async def extract_text_candidates(self, image: Image.Image) -> list:
        """
        回傳各引擎原始候選,供共識層逐欄位比對。

        複用既有多引擎呼叫,不重跑引擎——引擎本來就已並行執行,此覆寫僅停止
        丟棄既有結果,**新增辨識成本為零**。
        """
        image_array = self._to_bgr_array(image)
        _text, _confidence, engine_results = \
            await self.engine_manager.extract_text_multi_engine(image_array)
        return engine_results

    async def postprocess(
        self,
        text: str,
        confidence: float,
        image_data: Optional[str] = None
    ) -> tuple[str, Dict[str, Any]]:
        """
        後處理文字

        委派給 TranscriptPostprocessor 進行錯別字修正、格式校正。
        可選擇性使用 LLM 進行文字校正。

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
            # 根據是否傳入 image_data 決定啟用 LLM
            enable_llm = image_data is not None
            postprocessor = TranscriptPostprocessor(
                enable_typo_fix=True,
                enable_format_correction=True,
                enable_llm=enable_llm,
                llm_provider=self.llm_provider,
                llm_strategy=self.llm_strategy,
                field_labels=getattr(TranscriptFieldExtractor, "FIELD_LABELS", None),
            )

            # 調用 TranscriptPostprocessor
            processed_text, stats = await postprocessor.postprocess(
                text,
                ocr_confidence=confidence,
                image_data=image_data
            )

            logger.debug(
                f"後處理完成，錯別字修正: {stats.get('typo_fixes', 0)} 次"
            )

            return processed_text, stats

        except Exception as e:
            logger.error(f"後處理失敗: {str(e)}", exc_info=True)
            raise

    async def extract_fields(
        self,
        text: str,
        image_data: Optional[str] = None,
        enable_llm: bool = False,
        few_shot: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        提取謄本關鍵欄位(地號/建號、面積、權利範圍、所有權人)

        以規則抽取為主;啟用 LLM 且有圖像時,對低信心欄位以 LLM Vision 補齊
        (注入 few-shot)。每欄位附信心度,低信心欄位標記於 needs_confirmation。

        Args:
            text: OCR 文字
            image_data: base64 編碼的圖像資料(供 LLM Vision)
            enable_llm: 是否啟用 LLM 輔助提取
            few_shot: few-shot 範例(注入 LLM 提示)

        Returns:
            結構化欄位字典(含 field_confidences / needs_confirmation)
        """
        from .transcript_field_extractor import TranscriptFieldExtractor

        extractor = TranscriptFieldExtractor()
        return await extractor.extract(
            text,
            image_data=image_data,
            use_llm_fallback=enable_llm,
            few_shot=few_shot,
        )
