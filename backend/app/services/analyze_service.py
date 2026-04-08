"""
統一分析服務

協調 S3 上傳、OCR 處理、問答等流程。
"""

import logging
from typing import Optional, List, Tuple

import fitz

from app.lib.storage_service import storage_service
from app.lib.multi_type_ocr.processor_factory import ProcessorFactory
from app.lib.ai_service import answer_question

logger = logging.getLogger(__name__)

# S3 路徑對應表
S3_PATH_MAP = {
    "transcript": "uploads/ocr_transcripts",
    "contract": "uploads/ocr_contracts",
}


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
    ) -> Tuple[List[dict], int]:
        """
        執行 OCR 處理

        Returns:
            (pages, total_pages) - 各頁結果列表與總頁數
        """
        is_pdf = filename.lower().endswith(".pdf")

        if is_pdf:
            doc = fitz.open(stream=file_contents, filetype="pdf")
            total_pages = len(doc)
            doc.close()
            pages_to_process = list(range(1, total_pages + 1))
        else:
            total_pages = 1
            pages_to_process = [1]

        processor = ProcessorFactory.get_processor(document_type)
        results = []

        for page_num in pages_to_process:
            try:
                # 提取單頁圖片
                if is_pdf:
                    doc = fitz.open(stream=file_contents, filetype="pdf")
                    page = doc[page_num - 1]
                    mat = fitz.Matrix(300 / 72, 300 / 72)
                    pix = page.get_pixmap(matrix=mat)
                    page_bytes = pix.tobytes("png")
                    doc.close()
                else:
                    page_bytes = file_contents

                # OCR 處理
                page_result = await processor.process(
                    file_contents=page_bytes,
                    filename=filename,
                    page_number=page_num,
                    total_pages=total_pages,
                    enable_llm=enable_llm,
                )

                # 移除 original_image（節省回應大小）
                page_result.pop("original_image", None)

                results.append(page_result)

            except Exception as e:
                logger.error(f"頁面 {page_num} 處理失敗: {e}")
                results.append({
                    "page_number": page_num,
                    "error": f"頁面處理失敗: {str(e)}",
                    "ocr_raw": {"text": "", "confidence": 0.0},
                    "rule_postprocessed": {"text": "", "stats": {}},
                    "llm_postprocessed": None,
                    "structured_data": None,
                })

        return results, total_pages

    async def analyze(
        self,
        file_contents: bytes,
        filename: str,
        document_type: str,
        enable_llm: bool,
        question: Optional[str] = None,
    ) -> dict:
        """
        執行完整的文件分析流程

        流程：S3 上傳 → OCR 處理 → 統計計算 → 組裝回應
        """
        import time

        start_time = time.time()

        # 1. S3 上傳（失敗不影響後續）
        file_url = await self._upload_to_s3(file_contents, filename, document_type)

        # 2. OCR 處理
        pages, total_pages = await self._process_ocr(
            file_contents, filename, document_type, enable_llm
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
