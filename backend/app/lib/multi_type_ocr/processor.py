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
import numpy as np
from PIL import Image
import io
import base64

from ..ocr_enhanced.types import EngineResult
from .field_consensus import FieldConsensusResolver, field_candidate_from_extraction
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

    @staticmethod
    def _to_bgr_array(image: Image.Image) -> np.ndarray:
        """
        將 PIL Image 轉為 OpenCV(BGR)格式的 numpy array

        EngineManager 以 BGR 陣列為輸入。彩色(三通道)影像需交換紅藍通道;
        灰階與含 alpha 的影像維持原樣。

        供 extract_text() 與 extract_text_candidates() 共用,避免兩處重複。
        """
        array = np.array(image)
        if len(array.shape) == 3 and array.shape[2] == 3:
            array = array[:, :, ::-1].copy()
        return array

    async def extract_text_candidates(
        self, image: Image.Image
    ) -> List[EngineResult]:
        """
        產出多引擎辨識候選,供共識層比對。

        預設實作:包裝既有 extract_text(),回傳單一元素列表。

        ⚠️ 此預設僅保證「既有子類別不會失效」,**不足以啟動共識**——因
        extract_text() 回傳的是融合後的單一文字。真正的共識能力必須由子類別
        覆寫提供,改為回傳 EngineManager 各引擎的原始結果。
        """
        text, confidence = await self.extract_text(image)
        return [{
            "engine": "default",
            "text": text,
            "confidence": confidence,
            "processing_time_ms": 0,
        }]

    async def fuse_candidates(
        self, candidates: List[EngineResult]
    ) -> tuple[str, float]:
        """
        由既有候選產生融合文字與信心度,**不重跑引擎**。

        具 EngineManager 的處理器一律委派給它,以沿用設定的融合策略;
        其餘情況退回「取信心度最高者」。
        """
        if not candidates:
            return "", 0.0

        engine_manager = getattr(self, "engine_manager", None)
        if engine_manager is not None and hasattr(engine_manager, "fuse"):
            return engine_manager.fuse(candidates)

        best = max(candidates, key=lambda c: c["confidence"])
        return best["text"], best["confidence"]

    @staticmethod
    def _consensus_enabled() -> bool:
        """共識模式是否啟用(可由開關或融合模式擇一設定;需求 4.7)"""
        from app.config import settings

        return bool(getattr(settings, "OCR_CONSENSUS_ENABLED", False)) or (
            getattr(settings, "OCR_FUSION_METHOD", "") == "cross_check"
        )

    async def _resolve_consensus(
        self, candidates: List[EngineResult]
    ) -> Optional[Dict[str, Any]]:
        """
        對各候選分別做**純規則式**欄位抽取後解析共識。

        關鍵成本約束:此處一律以 `enable_llm=False`、`image_data=None` 呼叫,
        使各候選走零成本的 regex 路徑。若對每個候選觸發 LLM,呼叫次數會隨候選數
        倍增,直接衝擊月成本上限——LLM 補全只對共識後的單一結果執行一次。
        """
        field_candidates = []
        for candidate in candidates:
            extracted = await self.extract_fields(
                candidate["text"],
                image_data=None,
                enable_llm=False,
                few_shot=None,
            )
            field_candidates.append(
                field_candidate_from_extraction(candidate["engine"], extracted)
            )
        return FieldConsensusResolver().resolve(field_candidates)

    @staticmethod
    def _apply_consensus(
        structured_data: Optional[Dict[str, Any]],
        consensus: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        將共識信心度覆蓋至既有抽取結果。

        **只取較低者**:共識訊號只能收緊攔截,不得放寬。此為核心不變量
        「信心度回報不得高於實際可信程度」的落實點——共識絕不會把一個原本
        低信心的欄位抬高到門檻之上。

        欄位值本身維持既有抽取結果(該結果來自融合文字,且可能已由 LLM 補齊),
        共識僅提供信心度訊號與各引擎原始值對照。
        """
        if not structured_data:
            return structured_data

        existing = structured_data.get("field_confidences")
        merged: Dict[str, float] = dict(existing) if isinstance(existing, dict) else {}

        for field, confidence in consensus["field_confidences"].items():
            if field in merged:
                merged[field] = min(merged[field], confidence)
            else:
                merged[field] = confidence

        structured_data["field_confidences"] = merged
        return structured_data

    @staticmethod
    def _apply_correction_confidences(
        structured_data: Optional[Dict[str, Any]],
        correction_confidences: Optional[Dict[str, float]],
    ) -> Optional[Dict[str, Any]]:
        """
        併入校正階段回報的欄位信心度(需求 2.2)。

        **只取較低者**,與共識同一不變量:任何新訊號都只能收緊攔截、不得放寬。
        模型自評信心度尤其不可用來抬高——本規格的核心論點正是自評不可信。
        """
        if not structured_data or not correction_confidences:
            return structured_data

        existing = structured_data.get("field_confidences")
        merged: Dict[str, float] = dict(existing) if isinstance(existing, dict) else {}

        for field, confidence in correction_confidences.items():
            value = float(confidence)
            merged[field] = min(merged[field], value) if field in merged else value

        structured_data["field_confidences"] = merged
        return structured_data

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
        # 共識模式改走候選路徑,並由既有候選重用融合結果——引擎執行次數與現行相同。
        # 共識關閉時(預設)程式路徑完全不變,行為與現行版本一致。
        consensus_enabled = self._consensus_enabled()
        candidates: List[EngineResult] = []
        if consensus_enabled:
            try:
                candidates = await self.extract_text_candidates(preprocessed_image)
                raw_text, ocr_confidence = await self.fuse_candidates(candidates)
            except Exception as e:
                logger.warning(f"共識模式候選提取失敗,降級為單引擎模式: {e}")
                consensus_enabled = False
                candidates = []
                raw_text, ocr_confidence = await self.extract_text(preprocessed_image)
        else:
            raw_text, ocr_confidence = await self.extract_text(preprocessed_image)
        ocr_raw_result = {"text": raw_text, "confidence": ocr_confidence}

        # 步驟 3b:各候選純規則式抽取 → 欄位層共識(零 LLM 成本)
        consensus = None
        if consensus_enabled:
            try:
                consensus = await self._resolve_consensus(candidates)
            except Exception as e:
                logger.warning(f"共識解析失敗,降級為單引擎信心度: {e}")
                consensus = None

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

        # 步驟 5b:共識信心度覆蓋(只取較低者,絕不放寬攔截)
        if consensus is not None:
            structured_data = self._apply_consensus(structured_data, consensus)

        # 步驟 5c:雙模態校正回報的欄位信心度(任務 8.4);同樣只取較低者
        structured_data = self._apply_correction_confidences(
            structured_data, postprocess_stats.get("llm_field_confidences")
        )

        field_confidences: Dict[str, float] = {}
        if isinstance(structured_data, dict):
            fc = structured_data.get("field_confidences")
            if isinstance(fc, dict):
                field_confidences = fc

        llm_step = "✓ 完成（LLM 文字校正）" if llm_used else "⊗ 未使用"
        result: PageResult = {
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

        # 共識明細為選填欄位;未啟用時完全不出現,結果與現行版本逐鍵一致
        if consensus is not None:
            result["consensus"] = {
                "available": consensus["consensus_available"],
                "agreements": consensus["agreements"],
            }

        return result


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
