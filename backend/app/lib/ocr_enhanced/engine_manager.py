"""
OCR Engine Manager Module

OCR 引擎管理模組，支援多引擎並行處理與結果融合。
"""

from typing import Literal, Any, Optional
import numpy as np
import time
import asyncio
import cv2

from .types import EngineResult, FusionMethod, OCREngineName


class EngineManager:
    """
    OCR 引擎管理器

    管理多個 OCR 引擎，支援並行處理與結果融合。
    """

    # 單例模式：確保模型常駐記憶體
    _paddleocr_instance = None

    def __init__(
        self,
        engines: Optional[list[OCREngineName]] = None,
        parallel: bool = False,
        fusion_method: FusionMethod = "best",
        paddleocr_lang: str = "chinese_cht"
    ):
        """
        初始化引擎管理器

        Args:
            engines: 引擎列表
            parallel: 是否並行處理
            fusion_method: 融合方法 (best/weighted/vote)
            paddleocr_lang: PaddleOCR 語言(繁中預設 chinese_cht)
        """
        self.engines: list[OCREngineName] = engines or ["paddleocr", "tesseract"]
        self.parallel = parallel
        self.fusion_method = fusion_method
        self.paddleocr_lang = paddleocr_lang
        # 註:PaddleOCR 改為首次使用時惰性載入(見 _ensure_paddleocr),
        # 避免未安裝 paddleocr 的環境在建構時即失敗

    def _ensure_paddleocr(self):
        """惰性初始化 PaddleOCR(單例);僅在實際辨識時載入"""
        if EngineManager._paddleocr_instance is None:
            try:
                from paddleocr import PaddleOCR

                # ⚠️ enable_mkldnn=False 不可拿掉 ⚠️
                #
                # paddle 3.x 的新執行器(PIR)與 oneDNN 之間有功能缺口,推論時拋
                #   NotImplementedError: ConvertPirAttribute2RuntimeAttribute
                #     not support [pir::ArrayAttribute<pir::DoubleAttribute>]
                #     (at .../new_executor/instruction/onednn/onednn_instruction.cc)
                #
                # 環境變數 FLAGS_use_mkldnn=0 對 3.x **無效**(2.x 才吃那個旗標),
                # 只有建構子參數有效。2026-08-24 於 x86_64 Linux 實測確認。
                EngineManager._paddleocr_instance = PaddleOCR(
                    lang=self.paddleocr_lang,
                    enable_mkldnn=False,
                    # 前處理模組預設開啟會拖慢且對已掃描的謄本無益;
                    # 手機拍攝路徑若要開 use_doc_unwarping,請另行實測比較
                    use_doc_orientation_classify=False,
                    use_doc_unwarping=False,
                    use_textline_orientation=True,
                )
            except Exception as e:
                raise RuntimeError(f"PaddleOCR 初始化失敗: {e}")
        return EngineManager._paddleocr_instance

    async def extract_text_multi_engine(
        self,
        image: np.ndarray,
        page_number: int = 1
    ) -> tuple[str, float, list[EngineResult]]:
        """
        使用多引擎提取文字

        Args:
            image: 圖像 numpy 陣列
            page_number: 頁碼（用於 PDF）

        Returns:
            (融合後文字, 融合後信心度, 各引擎結果)
        """
        # 準備任務列表
        tasks = []

        if "paddleocr" in self.engines:
            tasks.append(self._run_paddleocr(image))

        if "tesseract" in self.engines:
            tasks.append(self._run_tesseract(image))

        # 並行執行所有引擎（使用 asyncio.gather）
        try:
            if self.parallel and len(tasks) > 1:
                # 並行模式：同時執行
                results = await asyncio.gather(*tasks, return_exceptions=True)
            else:
                # 順序模式：逐個執行
                results = []
                for task in tasks:
                    try:
                        result = await task
                        results.append(result)
                    except Exception as e:
                        results.append(e)

            # 過濾失敗結果
            valid_results: list[EngineResult] = []
            for result in results:
                if isinstance(result, Exception):
                    # 記錄錯誤但繼續使用其他引擎結果
                    print(f"引擎執行失敗: {result}")
                else:
                    valid_results.append(result)

            if not valid_results:
                # 所有引擎都失敗
                return "", 0.0, []

            # 融合結果
            fused_text, fused_confidence = self._fuse_results(valid_results)

            return fused_text, fused_confidence, valid_results

        except Exception as e:
            print(f"多引擎處理失敗: {e}")
            return "", 0.0, []

    async def _run_paddleocr(self, image: np.ndarray) -> EngineResult:
        """
        執行 PaddleOCR

        Task 5.1 實作

        Args:
            image: 圖像 numpy 陣列（BGR 或 RGB）

        Returns:
            EngineResult with standardized output

        Raises:
            RuntimeError: PaddleOCR 執行失敗
        """
        # 惰性載入 PaddleOCR(首次辨識時)
        self._ensure_paddleocr()

        # 將同步 OCR 呼叫轉為非同步
        def _ocr_sync():
            start_time = time.time()

            # 確保圖像是 RGB 格式（PaddleOCR 需要 RGB）
            if len(image.shape) == 2:
                # 灰階 → RGB
                img_rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
            elif image.shape[2] == 3:
                # BGR → RGB
                img_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            else:
                img_rgb = image

            # 執行 OCR
            # paddleocr 3.x 的 API 是 predict();2.x 的 ocr(img, cls=True) 已移除
            result = EngineManager._paddleocr_instance.predict(img_rgb)
            processing_time_ms = int((time.time() - start_time) * 1000)

            # 3.x 回傳 list[dict],文字與信心度分別在 rec_texts / rec_scores
            # (2.x 是 list[list[[bbox, (text, conf)]]],結構完全不同)
            text_lines = []
            confidences = []

            for page in (result or []):
                texts = page.get("rec_texts") or []
                scores = page.get("rec_scores") or []
                for text_content, confidence in zip(texts, scores):
                    text_lines.append(text_content)
                    confidences.append(float(confidence))

            # 合併文字（逐行）
            text = "\n".join(text_lines)

            # 計算平均信心度
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

            return text, avg_confidence, processing_time_ms

        # 使用 asyncio.to_thread 執行同步函數
        text, confidence, processing_time_ms = await asyncio.to_thread(_ocr_sync)

        return {
            "engine": "paddleocr",
            "text": text,
            "confidence": self._standardize_confidence("paddleocr", confidence),
            "processing_time_ms": processing_time_ms
        }

    async def _run_tesseract(self, image: np.ndarray) -> EngineResult:
        """
        執行 Tesseract

        Task 5.2 實作

        Args:
            image: 圖像 numpy 陣列

        Returns:
            EngineResult with standardized output

        Raises:
            RuntimeError: Tesseract 執行失敗
        """
        try:
            import pytesseract
            from pytesseract import Output
        except ImportError:
            raise RuntimeError("pytesseract 未安裝，請執行: pip install pytesseract")

        # 將同步 OCR 呼叫轉為非同步
        def _ocr_sync():
            start_time = time.time()

            # 轉換為 PIL Image（pytesseract 接受 numpy 或 PIL）
            # PSM 6: 假設單一文字區塊（適合謄本）
            config = "--psm 6"

            # 提取文字
            text = pytesseract.image_to_string(
                image,
                lang="chi_tra",
                config=config
            )

            # 提取信心度（使用 image_to_data 獲取詳細資訊）
            try:
                data = pytesseract.image_to_data(
                    image,
                    lang="chi_tra",
                    config=config,
                    output_type=Output.DICT
                )

                # 計算平均信心度（過濾無效值）
                confidences = [
                    float(conf) for conf in data['conf']
                    if conf != -1 and conf != '-1'
                ]
                avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

                # Tesseract 信心度範圍是 0-100，需要標準化到 0-1
                avg_confidence = avg_confidence / 100.0

            except Exception as e:
                # 如果無法獲取信心度，使用預設值
                print(f"無法獲取 Tesseract 信心度: {e}")
                avg_confidence = 0.5  # 預設中等信心度

            processing_time_ms = int((time.time() - start_time) * 1000)

            return text, avg_confidence, processing_time_ms

        # 使用 asyncio.to_thread 執行同步函數
        text, confidence, processing_time_ms = await asyncio.to_thread(_ocr_sync)

        return {
            "engine": "tesseract",
            "text": text,
            "confidence": self._standardize_confidence("tesseract", confidence),
            "processing_time_ms": processing_time_ms
        }

    def fuse(self, results: list[EngineResult]) -> tuple[str, float]:
        """
        以設定的融合策略融合各引擎結果(公開入口)

        供已取得候選的呼叫端重用融合邏輯,避免為了拿融合文字而重跑引擎。
        行為完全委派給既有 _fuse_results,既有策略不受影響。

        Args:
            results: 各引擎結果列表

        Returns:
            (融合後文字, 融合後信心度)
        """
        return self._fuse_results(results)

    def _fuse_results(self, results: list[EngineResult]) -> tuple[str, float]:
        """
        融合多個引擎結果

        Task 5.3 實作（融合策略）

        Args:
            results: 各引擎結果列表

        Returns:
            (融合後文字, 融合後信心度)

        Fusion Strategies:
            - "best": 選擇信心度最高的結果（適合高品質圖片）
            - "smart": 綜合評分選擇（推薦，適應不同品質）
            - "vote": 選擇字符數最多的結果（適合低品質圖片）
            - "weighted": 加權平均（Phase 2）
        """
        if not results:
            return "", 0.0

        if self.fusion_method == "best":
            # Phase 1: 選擇信心度最高的結果
            best_result = max(results, key=lambda r: r["confidence"])
            return best_result["text"], best_result["confidence"]

        elif self.fusion_method == "smart":
            # 智能策略：綜合評分
            # 計算每個結果的綜合分數
            scored_results = []

            for result in results:
                # 因子 1: 信心度（0-1）
                confidence_score = result["confidence"]

                # 因子 2: 字符數（歸一化）
                max_chars = max(len(r["text"]) for r in results)
                char_score = len(result["text"]) / max_chars if max_chars > 0 else 0

                # 因子 3: 關鍵字檢測（謄本專用）
                keywords = ['地號', '面積', '統一編號', '謄本', '建物', '土地', '所有權', '登記']
                keyword_matches = sum(1 for kw in keywords if kw in result["text"])
                keyword_score = keyword_matches / len(keywords)

                # 綜合評分：
                # - 信心度高但字少 → 可能是 PaddleOCR 在低品質圖片上過度自信
                # - 字多但信心度低 → 可能是 Tesseract 在低品質圖片上表現更好
                # 權重調整：字符數 40%, 關鍵字 35%, 信心度 25%
                total_score = (
                    char_score * 0.40 +
                    keyword_score * 0.35 +
                    confidence_score * 0.25
                )

                scored_results.append({
                    "result": result,
                    "score": total_score,
                    "char_score": char_score,
                    "keyword_score": keyword_score,
                    "confidence_score": confidence_score
                })

            # 選擇綜合分數最高的結果
            best_scored = max(scored_results, key=lambda x: x["score"])
            best_result = best_scored["result"]

            return best_result["text"], best_result["confidence"]

        elif self.fusion_method == "vote":
            # Phase 2: 投票機制（字符級投票）
            # 簡化版本：選擇最長的結果（通常 Tesseract 在低品質圖片上更完整）
            best_result = max(results, key=lambda r: len(r["text"]))
            avg_confidence = sum(r["confidence"] for r in results) / len(results)

            return best_result["text"], avg_confidence

        elif self.fusion_method == "weighted":
            # Phase 2: 加權平均（根據信心度）
            total_confidence = sum(r["confidence"] for r in results)
            if total_confidence == 0:
                # 所有信心度都是 0，使用第一個結果
                return results[0]["text"], 0.0

            # 按信心度加權文字長度（簡化版本）
            # 完整實作需要逐字符對齊
            best_result = max(results, key=lambda r: r["confidence"])
            weighted_confidence = total_confidence / len(results)

            return best_result["text"], weighted_confidence

        else:
            # 預設：使用 smart 策略
            # 暫存當前策略
            original_method = self.fusion_method
            self.fusion_method = "smart"
            result = self._fuse_results(results)
            # 恢復原策略
            self.fusion_method = original_method
            return result

    def _standardize_confidence(
        self,
        engine: OCREngineName,
        raw_confidence: Any
    ) -> float:
        """
        標準化信心度

        Task 5.3 實作（信心度標準化）

        Args:
            engine: 引擎名稱
            raw_confidence: 原始信心度

        Returns:
            標準化後的信心度 (0-1)

        Notes:
            - PaddleOCR: 已經是 0-1 範圍
            - Tesseract: 0-100 範圍，已在 _run_tesseract 中轉換
            - Textract: 0-100 範圍（Phase 2）
        """
        # 確保是浮點數
        try:
            confidence = float(raw_confidence)
        except (TypeError, ValueError):
            return 0.0

        # 根據引擎調整
        if engine == "paddleocr":
            # PaddleOCR 已經是 0-1 範圍
            return max(0.0, min(1.0, confidence))

        elif engine == "tesseract":
            # Tesseract 已在 _run_tesseract 中轉換為 0-1
            return max(0.0, min(1.0, confidence))

        elif engine == "textract":
            # AWS Textract 通常是 0-100 範圍
            # Phase 2 實作時啟用
            if confidence > 1.0:
                confidence = confidence / 100.0
            return max(0.0, min(1.0, confidence))

        else:
            # 未知引擎，假設已經是 0-1 範圍
            return max(0.0, min(1.0, confidence))
