"""
文件處理器抽象基類(統一 analyze 模板)

以「載入影像 → analyze → 產出統一 PageResult」為模板核心,分出:
- OcrDocumentProcessor:OCR 型(謄本/帳單/合約),預設四步驟編排
- ImageUnderstandingProcessor:影像理解型(修繕照片),不走 OCR

如此 QualityAssessor 能以同一套 PageResult(含 overall_confidence / field_confidences)判定。
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from PIL import Image
import io
import base64

from .types import PageResult

logger = logging.getLogger(__name__)


class DocumentProcessor(ABC):
    """文件處理器共同基類:定義 analyze 契約與 process 模板"""

    @abstractmethod
    async def analyze(
        self,
        image: Image.Image,
        image_data: Optional[str] = None,
        enable_llm: bool = False,
        few_shot: Optional[List[Dict[str, Any]]] = None,
    ) -> PageResult:
        """分析單頁影像並回傳統一 PageResult(page_number / original_image 由 process 補上)"""
        raise NotImplementedError

    async def process(
        self,
        file_contents: bytes,
        filename: str,
        page_number: int,
        total_pages: int,
        enable_llm: bool,
        few_shot: Optional[List[Dict[str, Any]]] = None,
    ) -> PageResult:
        """
        處理單一頁面(模板方法)

        載入影像 → 轉 RGB → 保存原圖 base64 → 呼叫 analyze → 補上頁碼與原圖。
        """
        logger.info(f"開始處理頁面 {page_number}/{total_pages}: {filename}")
        try:
            loaded_image = Image.open(io.BytesIO(file_contents))
            image = loaded_image.convert("RGB") if loaded_image.mode != "RGB" else loaded_image

            original_image_bytes = io.BytesIO()
            image.save(original_image_bytes, format="PNG")
            original_image_b64 = base64.b64encode(
                original_image_bytes.getvalue()
            ).decode("utf-8")
            original_image_data = f"data:image/png;base64,{original_image_b64}"

            result = await self.analyze(
                image,
                image_data=original_image_b64,
                enable_llm=enable_llm,
                few_shot=few_shot,
            )
            result["page_number"] = page_number
            result["original_image"] = original_image_data

            logger.info(f"頁面 {page_number}/{total_pages} 處理完成")
            return result
        except Exception as e:
            logger.error(
                f"處理頁面 {page_number}/{total_pages} 失敗: {str(e)}", exc_info=True
            )
            raise


class OcrDocumentProcessor(DocumentProcessor):
    """OCR 型處理器:預設以四步驟(預處理→OCR→後處理→欄位提取)編排 analyze"""

    @abstractmethod
    async def preprocess(self, image: Image.Image) -> Image.Image:
        """預處理圖像(去噪、二值化、去浮水印等)"""
        pass

    @abstractmethod
    async def extract_text(self, image: Image.Image) -> tuple[str, float]:
        """OCR 文字提取,回傳 (文字, 信心度 0.0-1.0)"""
        pass

    @abstractmethod
    async def postprocess(
        self, text: str, confidence: float, image_data: Optional[str] = None
    ) -> tuple[str, Dict[str, Any]]:
        """文字後處理(錯別字、格式、可選 LLM),回傳 (修正後文字, 統計)"""
        pass

    @abstractmethod
    async def extract_fields(
        self,
        text: str,
        image_data: Optional[str] = None,
        enable_llm: bool = False,
        few_shot: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """結構化欄位提取(依文件類型),支援 few-shot 注入"""
        pass

    async def analyze(
        self,
        image: Image.Image,
        image_data: Optional[str] = None,
        enable_llm: bool = False,
        few_shot: Optional[List[Dict[str, Any]]] = None,
    ) -> PageResult:
        # 步驟 2:預處理
        preprocessed_image = await self.preprocess(image)

        # 步驟 3:OCR 文字提取
        raw_text, ocr_confidence = await self.extract_text(preprocessed_image)
        ocr_raw_result = {"text": raw_text, "confidence": ocr_confidence}

        # 步驟 4:後處理(image_data 供 LLM,依 enable_llm 決定)
        image_data_for_llm = image_data if enable_llm else None
        postprocessed_text, postprocess_stats = await self.postprocess(
            raw_text, ocr_confidence, image_data_for_llm
        )
        rule_postprocessed_result = {"text": postprocessed_text, "stats": postprocess_stats}

        llm_used = postprocess_stats.get("llm_used", False)
        llm_postprocessed_result = None
        if llm_used:
            llm_postprocessed_result = {
                "text": postprocessed_text,
                "stats": {
                    "llm_used": True,
                    "llm_cost": postprocess_stats.get("llm_cost", 0.0),
                },
                "used": True,
            }

        # 步驟 5:結構化欄位提取
        structured_data = await self.extract_fields(
            postprocessed_text,
            image_data=(image_data if enable_llm else None),
            enable_llm=enable_llm,
            few_shot=few_shot,
        )

        field_confidences: Dict[str, float] = {}
        if isinstance(structured_data, dict):
            fc = structured_data.get("field_confidences")
            if isinstance(fc, dict):
                field_confidences = fc

        llm_step = "✓ 完成（LLM 文字校正）" if llm_used else "⊗ 未使用"
        return {
            "page_number": 0,          # 由 process 補上
            "original_image": "",      # 由 process 補上
            "ocr_raw": ocr_raw_result,
            "rule_postprocessed": rule_postprocessed_result,
            "llm_postprocessed": llm_postprocessed_result,
            "structured_data": structured_data if structured_data else None,
            "accuracy": None,
            "processing_steps": {
                "1_preprocess": "完成",
                "2_ocr": "完成",
                "3_postprocess": "完成",
                "4_llm": llm_step,
                "5_extract_fields": "完成",
            },
            "field_confidences": field_confidences,
            "overall_confidence": ocr_confidence,
        }


class ImageUnderstandingProcessor(DocumentProcessor):
    """影像理解型處理器:以 VLM 理解影像(如修繕照片),不走 OCR"""

    @abstractmethod
    async def understand(
        self,
        image_data: str,
        few_shot: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """影像理解,回傳結構化結果(如 {defect_labels, description, confidence})"""
        pass

    async def analyze(
        self,
        image: Image.Image,
        image_data: Optional[str] = None,
        enable_llm: bool = True,
        few_shot: Optional[List[Dict[str, Any]]] = None,
    ) -> PageResult:
        result = await self.understand(image_data or "", few_shot=few_shot)

        field_confidences: Dict[str, float] = {}
        if isinstance(result, dict):
            fc = result.get("field_confidences")
            if isinstance(fc, dict):
                field_confidences = fc

        overall_confidence = 1.0
        if isinstance(result, dict) and result.get("confidence") is not None:
            overall_confidence = float(result["confidence"])

        return {
            "page_number": 0,
            "original_image": "",
            "ocr_raw": None,           # 影像理解型不走 OCR
            "rule_postprocessed": None,
            "llm_postprocessed": None,
            "structured_data": result if result else None,
            "accuracy": None,
            "processing_steps": {"1_understand": "完成"},
            "field_confidences": field_confidences,
            "overall_confidence": overall_confidence,
        }
