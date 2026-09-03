"""
統一分析服務

協調 S3 上傳、OCR 處理、問答等流程。
"""

import asyncio
from app.config import settings
import logging
from typing import Optional, List, Tuple

from app.lib.storage_service import storage_service
from app.lib.multi_type_ocr.processor_factory import ProcessorFactory
from app.lib.ai_service import answer_question
from app.lib.pdf_text_layer import has_text_layer, extract_text_layer_pages

logger = logging.getLogger(__name__)

# S3 路徑對應表
S3_PATH_MAP = {
    "transcript": "uploads/ocr_transcripts",
    "contract": "uploads/ocr_contracts",
}


def _render_scale(rect) -> float:
    """算出單頁渲染倍率:以 OCR_RENDER_DPI 為目標,但受像素上限約束。

    原本寫死 `fitz.Matrix(300/72, 300/72)`。A4 在 300 DPI 是 2480×3508
    ≈ 8.7M 像素,單頁 PNG 加解碼後的點陣就數十 MB,再乘上雙引擎與後續
    保存的 base64 原圖——2026-08-24 在 3.7GB 的線上機器上實測會 OOM
    (`docker inspect .State.OOMKilled` = true,load average 衝到 51.35)。

    這裡只降**解析度**,不動頁數、不丟棄任何內容:超過上限時等比例縮到剛好
    貼齊上限。以 4M 像素上限計,A4 大約落在 200 DPI,對掃描文件的辨識影響有限。

    `OCR_MAX_RENDER_PIXELS <= 0` 表示停用上限,退回純 DPI 行為。
    """
    from app.config import settings

    base = settings.OCR_RENDER_DPI / 72.0
    cap = settings.OCR_MAX_RENDER_PIXELS
    if cap <= 0:
        return base

    # rect 的單位是 point(1/72 吋),乘上倍率即為輸出像素
    width_pt, height_pt = float(rect.width), float(rect.height)
    if width_pt <= 0 or height_pt <= 0:
        return base

    pixels_at_base = (width_pt * base) * (height_pt * base)
    if pixels_at_base <= cap:
        return base

    # 面積與倍率平方成正比,故以平方根等比例縮
    return base * (cap / pixels_at_base) ** 0.5


class AnalyzeService:
    """統一文件分析服務"""

    async def _upload_to_s3(
        self,
        file_contents: bytes,
        filename: str,
        document_type: str,
    ) -> Optional[str]:
        """
        上傳檔案至 S3

        Returns:
            CDN URL，上傳失敗時回傳 None
        """
        path_prefix = S3_PATH_MAP.get(document_type, "uploads/ocr_others")

        try:
            url = await storage_service.upload_file(
                filename,
                file_contents,
                path_prefix=path_prefix,
                acl="public-read",
            )
            logger.info(f"檔案上傳成功: {url}")
            return url
        except Exception as e:
            logger.warning(f"S3 上傳失敗，降級處理: {e}")
            return None

    async def _process_ocr(
        self,
        file_contents: bytes,
        filename: str,
        document_type: str,
        enable_llm: bool,
        few_shot: Optional[List[dict]] = None,
    ) -> Tuple[List[dict], int]:
        """
        執行 OCR 處理

        Returns:
            (pages, total_pages) - 各頁結果列表與總頁數
        """
        is_pdf = filename.lower().endswith(".pdf")

        # 合約 PDF 且含文字層 → 直接抽取文字並分段,略過 OCR(省成本)
        if is_pdf and document_type == "contract" and has_text_layer(file_contents):
            logger.info("合約 PDF 含文字層,直接抽取文字並分段(略過 OCR)")
            pages = extract_text_layer_pages(file_contents)
            return pages, len(pages)

        # 惰性匯入 PyMuPDF(僅 PDF 處理需要),避免未安裝環境匯入 app 失敗
        if is_pdf:
            import fitz
            doc = fitz.open(stream=file_contents, filetype="pdf")
            total_pages = len(doc)
            doc.close()
            pages_to_process = list(range(1, total_pages + 1))
        else:
            total_pages = 1
            pages_to_process = [1]

        processor = ProcessorFactory.get_processor(document_type)

        # 頁面併發,但 OCR 仍由 EngineManager 的閘門序列化。
        #
        # 2026-09-03 實測 4 頁謄本:總計 151s,其中 LLM 佔 24.6s/頁(98s,65%)。
        # LLM 在遠端算,本機只是等 HTTP——那 98 秒是**排隊等網路**,不是在用記憶體。
        # 逐頁串接等於把四段網路等待接起來;讓頁面重疊後那段降到約 25s(取最慢者)。
        #
        # OCR 不能跟著重疊:單頁峰值 1141–1778 MB,容器可用約 1695 MB。
        # 但閘門放在 EngineManager 而非此處,所以這裡放心併發——
        # 真正吃記憶體的那一段自己會排隊。
        page_gate = asyncio.Semaphore(max(1, int(settings.OCR_MAX_CONCURRENT_PAGES)))

        async def _process_page(page_num: int) -> dict:
            async with page_gate:
                return await _run_one_page(page_num)

        async def _run_one_page(page_num: int) -> dict:
            try:
                # 提取單頁圖片
                if is_pdf:
                    doc = fitz.open(stream=file_contents, filetype="pdf")
                    page = doc[page_num - 1]
                    scale = _render_scale(page.rect)
                    mat = fitz.Matrix(scale, scale)
                    pix = page.get_pixmap(matrix=mat)
                    page_bytes = pix.tobytes("png")
                    doc.close()
                else:
                    page_bytes = file_contents

                # OCR 處理(注入 few-shot 範例)
                page_result = await processor.process(
                    file_contents=page_bytes,
                    filename=filename,
                    page_number=page_num,
                    total_pages=total_pages,
                    enable_llm=enable_llm,
                    few_shot=few_shot,
                )

                # 移除 original_image（節省回應大小）
                page_result.pop("original_image", None)

                return page_result

            except Exception as e:
                logger.error(f"頁面 {page_num} 處理失敗: {e}")
                return {
                    "page_number": page_num,
                    "error": f"頁面處理失敗: {str(e)}",
                    "ocr_raw": {"text": "", "confidence": 0.0},
                    "rule_postprocessed": {"text": "", "stats": {}},
                    "llm_postprocessed": None,
                    "structured_data": None,
                }

        # gather 保序:回傳順序與傳入順序一致,故頁碼不會亂
        results = list(await asyncio.gather(*(_process_page(n) for n in pages_to_process)))

        return results, total_pages

    async def analyze(
        self,
        file_contents: bytes,
        filename: str,
        document_type: str,
        enable_llm: bool,
        question: Optional[str] = None,
        few_shot: Optional[List[dict]] = None,
    ) -> dict:
        """
        執行完整的文件分析流程

        流程：S3 上傳 → OCR 處理（注入 few-shot）→ 統計計算 → 組裝回應
        """
        import time

        start_time = time.time()

        # 1. S3 上傳（失敗不影響後續）
        file_url = await self._upload_to_s3(file_contents, filename, document_type)

        # 2. OCR 處理（注入 few-shot 範例）
        pages, total_pages = await self._process_ocr(
            file_contents, filename, document_type, enable_llm, few_shot
        )

        # 3. AI 問答（可選）
        answer = None
        if question:
            answer = await self._answer_question(question, pages, document_type)

        # 4. 計算統計
        elapsed_ms = int((time.time() - start_time) * 1000)
        llm_pages_used = 0
        estimated_cost = 0.0

        for page in pages:
            llm_result = page.get("llm_postprocessed")
            if llm_result and llm_result.get("used"):
                llm_pages_used += 1
                estimated_cost += llm_result.get("stats", {}).get("llm_cost", 0.0)

        # 5. 記錄用量（失敗不影響回應）
        try:
            self._record_usage(
                document_type=document_type,
                total_pages=total_pages,
                llm_used=llm_pages_used > 0,
                llm_cost=estimated_cost,
                processing_time_ms=elapsed_ms,
            )
        except Exception as e:
            logger.warning(f"用量記錄失敗: {e}")

        # 6. 組裝回應
        return {
            "file_name": filename,
            "file_url": file_url,
            "document_type": document_type,
            "total_pages": total_pages,
            "pages": pages,
            "answer": answer,
            "stats": {
                "total_time_ms": elapsed_ms,
                "total_pages": total_pages,
                "llm_pages_used": llm_pages_used,
                "estimated_cost": round(estimated_cost, 4),
            },
        }

    async def _answer_question(
        self,
        question: str,
        pages: List[dict],
        document_type: str,
    ) -> Optional[str]:
        """
        基於 OCR 結果回答問題

        Returns:
            AI 回答，失敗時回傳 None
        """
        try:
            # 合併所有頁面的最佳文字
            all_text = []
            all_structured = {}
            for page in pages:
                # 優先用 LLM 修正文字，其次規則修正，最後原始 OCR
                llm = page.get("llm_postprocessed")
                rule = page.get("rule_postprocessed", {})
                raw = page.get("ocr_raw", {})

                if llm and llm.get("used"):
                    all_text.append(llm.get("text", ""))
                elif rule.get("text"):
                    all_text.append(rule["text"])
                else:
                    all_text.append(raw.get("text", ""))

                # 合併結構化欄位
                structured = page.get("structured_data")
                if structured:
                    all_structured.update(structured)

            context = {
                "ocr_text": "\n".join(all_text),
                "doc_type": document_type,
                "extracted_data": all_structured,
                "summary": None,
            }

            return await answer_question(question, context)

        except Exception as e:
            logger.warning(f"AI 問答失敗: {e}")
            return None

    def _record_usage(
        self,
        document_type: str,
        total_pages: int,
        llm_used: bool,
        llm_cost: float,
        processing_time_ms: int,
    ) -> None:
        """記錄 API 用量"""
        from app.database import SessionLocal
        from app.models.api_usage_log import ApiUsageLog

        db = SessionLocal()
        try:
            log = ApiUsageLog(
                endpoint="/api/v1/analyze",
                document_type=document_type,
                total_pages=total_pages,
                llm_used=llm_used,
                llm_cost=llm_cost,
                processing_time_ms=processing_time_ms,
            )
            db.add(log)
            db.commit()
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
