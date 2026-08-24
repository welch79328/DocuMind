"""
帳單文件處理器

以票證式鍵值抽取水電/管理費等帳單關鍵欄位(金額/日期/戶號);
劣化影像以 LLM Vision 補齊。重用 ocr_enhanced 模組並依設定啟用 PaddleOCR。
"""

import logging
from typing import Dict, Any, Optional
from PIL import Image

from .processor import OcrDocumentProcessor
from .bill_field_extractor import BillFieldExtractor
from ..ocr_enhanced.config import PreprocessConfig
from ..ocr_enhanced.preprocessor import TranscriptPreprocessor
from ..ocr_enhanced.engine_manager import EngineManager
from ..ocr_enhanced.postprocessor import TranscriptPostprocessor

logger = logging.getLogger(__name__)


class BillProcessor(OcrDocumentProcessor):
    """帳單文件處理器(OCR 型)"""

    def __init__(self) -> None:
        logger.info("初始化 BillProcessor")
        # 帳單:保留去噪,不需去浮水印/二值化
        preprocess_config = PreprocessConfig(
            enable_watermark_removal=False,
            enable_binarization=False,
            enable_denoising=True,
        )
        self.preprocessor = TranscriptPreprocessor(config=preprocess_config)

        from app.config import settings
        self.engine_manager = EngineManager(
            engines=list(settings.OCR_ENGINES),
            parallel=settings.OCR_PARALLEL_ENGINES,
            fusion_method=settings.OCR_FUSION_METHOD,
            paddleocr_lang=settings.OCR_PADDLEOCR_LANG,
        )
        self.llm_provider = "openai"
        self.llm_strategy = "auto"

    async def preprocess(self, image: Image.Image) -> Image.Image:
        processed_array, _metadata = await self.preprocessor.preprocess(image)
        if len(processed_array.shape) == 3 and processed_array.shape[2] == 3:
            rgb_array = processed_array[:, :, ::-1].copy()
        else:
            rgb_array = processed_array
        return Image.fromarray(rgb_array)

    async def extract_text(self, image: Image.Image) -> tuple[str, float]:
        image_array = self._to_bgr_array(image)
        text, confidence, _ = await self.engine_manager.extract_text_multi_engine(image_array)
        return text, confidence

    async def extract_text_candidates(self, image: Image.Image) -> list:
        """
        回傳各引擎原始候選,供共識層逐欄位比對。

        複用既有多引擎呼叫,不重跑引擎,新增辨識成本為零。
        """
        image_array = self._to_bgr_array(image)
        _text, _confidence, engine_results = \
            await self.engine_manager.extract_text_multi_engine(image_array)
        return engine_results

    async def postprocess(
        self, text: str, confidence: float, image_data: Optional[str] = None
    ) -> tuple[str, Dict[str, Any]]:
        enable_llm = image_data is not None
        postprocessor = TranscriptPostprocessor(
            enable_typo_fix=True,
            enable_format_correction=True,
            enable_llm=enable_llm,
            llm_provider=self.llm_provider,
            llm_strategy=self.llm_strategy,
            field_labels=getattr(BillFieldExtractor, "FIELD_LABELS", None),
        )
        return await postprocessor.postprocess(
            text, ocr_confidence=confidence, image_data=image_data
        )

    async def extract_fields(
        self,
        text: str,
        image_data: Optional[str] = None,
        enable_llm: bool = False,
        few_shot: Optional[list] = None,
    ) -> Dict[str, Any]:
        """票證式抽取金額/日期/戶號;劣化件以 LLM Vision(few-shot)補齊,缺漏標記"""
        extractor = BillFieldExtractor()
        return await extractor.extract(
            text,
            image_data=image_data,
            use_llm_fallback=enable_llm,
            few_shot=few_shot,
        )
