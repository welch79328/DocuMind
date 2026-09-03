"""
統一分析服務

協調 S3 上傳、OCR 處理、問答等流程。
"""

import asyncio
from app.config import settings
import logging
from typing import Optional, List, Tuple, Dict, Any

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

def _merge_page_structured_data(pages: List[dict]) -> Optional[Dict[str, Any]]:
    """跨頁彙整結構化欄位，只填補缺值，不用後面頁面覆蓋已抽到的值。

    2026-09-03 發現：謄本的關鍵欄位散在多頁（地號在 p1、建號在 p3，
    權利範圍可能在 p2 或 p4），而每頁各自跑一次正則抽取——單頁必然殘缺，
    但四頁合起來其實完整。

    既有的 `_answer_question` 已經做過一次合併（`all_structured.update(structured)`），
    但那是「後面覆蓋前面」，且只供問答使用、沒有進最終回應。若某頁把值誤判為
    None 或空字串，update 會把前面頁已經抽對的值蓋掉——本函式改為只填補缺值，
    且遞迴處理巢狀結構（合約是 `{parties: {party_a: ...}}` 巢狀，謄本是扁平）。
    """
    merged: Dict[str, Any] = {}
    seen_any = False
    for page in pages:
        data = page.get("structured_data")
        if not isinstance(data, dict):
            continue
        seen_any = True
        _merge_fill_missing(merged, data)

    if not seen_any:
        return None

    # needs_confirmation 與 extraction_confidence 必須在彙整後**重算**,
    # 不能沿用任一頁的值——它們描述的是「這一頁」的狀態,套到整份文件上是錯的。
    #
    # 2026-09-04 實測:一份 4 頁謄本彙整後,document_fields 同時出現
    #   building_number = "00004-000"（p3 抽到,信心度 0.9）
    #   needs_confirmation 卻包含 building_number（沿用 p1 的清單,p1 沒抽到）
    # 八個待確認欄位裡六個其實已經抽到,下游會把已知的值也丟給人工確認。
    _recompute_merged_status(merged, pages)
    return merged


def _scored_fields_from_pages(pages: List[dict]) -> set:
    """反推「應納入評分的欄位」= 各頁 needs_confirmation 的聯集 ∪ 已抽到的欄位。

    抽取器已依 REQUIRED_FIELDS 算好每頁的 needs_confirmation（只含必要欄位），
    所以聯集就是「必要且至少在某頁沒抽到」的集合；再併入「有值且高信心」的欄位，
    才不會漏掉每頁都成功抽到的必要欄位。

    刻意不從 analyze_service 直接讀 REQUIRED_FIELDS：抽取器是 processor 內部
    臨時建立的，這裡取不到實例，而為此建立耦合不值得——各頁輸出已含足夠資訊。

    副作用是選配欄位若剛好在某頁抽到，也會進入評分；那是加分項（信心度 0.9），
    不會造成先前那種「選配欄位缺席拉低分數」的稀釋問題。
    """
    scored: set = set()
    for page in pages:
        data = page.get("structured_data")
        if not isinstance(data, dict):
            continue
        needs = data.get("needs_confirmation")
        if isinstance(needs, (list, tuple)):
            scored.update(needs)
        confidences = data.get("field_confidences")
        if isinstance(confidences, dict):
            scored.update(
                k for k, v in confidences.items()
                if isinstance(v, (int, float)) and v > 0
            )
    return scored


def _recompute_merged_status(merged: Dict[str, Any], pages: List[dict]) -> None:
    """依彙整後的 field_confidences 重算待確認清單與整體信心度。

    只計「應納入評分的欄位」，避免把從未出現在任何一頁的選配欄位算進分母
    （那正是 2026-09-04 REQUIRED_FIELDS 修正要解決的稀釋問題）。
    """
    confidences = merged.get("field_confidences")
    if not isinstance(confidences, dict) or not confidences:
        return

    scored_keys = _scored_fields_from_pages(pages)
    if not scored_keys:
        return

    threshold = settings.OCR_QUALITY_THRESHOLD
    merged["needs_confirmation"] = sorted(
        name for name in scored_keys
        if isinstance(confidences.get(name), (int, float))
        and confidences[name] < threshold
    )
    scored = [
        confidences[k] for k in scored_keys
        if isinstance(confidences.get(k), (int, float))
    ]
    if scored:
        merged["extraction_confidence"] = round(sum(scored) / len(scored), 4)


def _merge_fill_missing(target: Dict[str, Any], source: Dict[str, Any]) -> None:
    """遞迴地把 source 裡「target 缺少或為空」的欄位填進 target。

    field_confidences 等中繼欄位不遞迴合併值本身，改為取各頁最高信心度——
    分數應反映「這份文件裡目前看到的最佳信心度」，而不是任意一頁的殘值。
    """
    for key, value in source.items():
        if key == "field_confidences" and isinstance(value, dict):
            existing = target.get(key)
            existing = existing if isinstance(existing, dict) else {}
            for fk, fv in value.items():
                if not isinstance(fv, (int, float)):
                    continue
                if fk not in existing or fv > existing[fk]:
                    existing[fk] = fv
            target[key] = existing
            continue

        if isinstance(value, dict):
            existing = target.get(key)
            if not isinstance(existing, dict):
                existing = {}
                target[key] = existing
            _merge_fill_missing(existing, value)
            continue

        current = target.get(key)
        is_missing = current is None or current == "" or current == [] 
        if is_missing and value not in (None, "", []):
            target[key] = value



class AnalyzeService:
    """統一文件分析服務"""

    async def _extract_fields_for_text_layer(
        self,
        pages: list,
        document_type: str,
        enable_llm: bool,
        few_shot=None,
    ) -> list:
        """為文字層頁面補上欄位抽取。

        `extract_text_layer_pages` 只負責取文字,structured_data 留 None。
        少了這一步,走文字層的文件會拿到完美的文字卻**一個欄位都沒有**。

        文字層的信心度為 1.0(它就是產生該 PDF 的原始字串,不是辨識結果),
        故欄位抽取的品質完全取決於抽取器本身,與 OCR 無關。
        """
        processor = ProcessorFactory.get_processor(document_type)
        page_gate = asyncio.Semaphore(max(1, int(settings.OCR_MAX_CONCURRENT_PAGES)))

        async def one(page: dict) -> dict:
            async with page_gate:
                try:
                    structured = await processor.extract_fields(
                        page["ocr_raw"]["text"],
                        image_data=None,          # 文字層無需影像:文字已是精確值
                        enable_llm=enable_llm,
                        few_shot=few_shot,
                    )
                    page["structured_data"] = structured
                    if isinstance(structured, dict):
                        fc = structured.get("field_confidences")
                        if isinstance(fc, dict):
                            page["field_confidences"] = fc
                except Exception as e:
                    logger.error("文字層欄位抽取失敗(第 %s 頁): %s",
                                 page.get("page_number"), e)
                    # 不中斷:文字仍然可用,欄位留 None 由複核處理
                return page

        return list(await asyncio.gather(*(one(p) for p in pages)))

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

        # PDF 含文字層 → 直接抽取文字,略過 OCR。
        #
        # 2026-09-03 實測(4 頁電子謄本,線上):
        #   走 OCR      85s,字元錯誤率 14.5%
        #   走文字層    <1s,**逐字精確**(文字層就是產生該 PDF 的原始字串)
        # 快 85 倍且零錯誤。台灣的網路申領電子謄本一律含文字層。
        #
        # 原本這條路只給 contract。謄本同樣受益,而且受益更大——
        # 謄本的 OCR 錯誤率(14.5%)高於它在合約上的表現。
        # 純掃描件不含文字層,has_text_layer 會回 False 自動走 OCR,
        # 判定門檻 20 字避免掃描件夾帶的少量浮水印文字造成誤判。
        if is_pdf and has_text_layer(file_contents):
            logger.info("PDF 含文字層,直接抽取文字(略過 OCR):%s", document_type)
            pages = extract_text_layer_pages(file_contents)
            # ⚠️ extract_text_layer_pages 只給文字,structured_data 是 None。
            # 少了這一步,走文字層的文件會拿到完美的文字但**一個欄位都沒有**
            # ——比走 OCR 還糟,因為使用者看得到字卻拿不到結構化結果。
            pages = await self._extract_fields_for_text_layer(
                pages, document_type, enable_llm, few_shot
            )
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
        #
        # ⚠️ document_fields：跨頁彙整後的結構化欄位（新增，2026-09-03）。
        # 謄本的關鍵欄位散在多頁（地號在 p1、建號在 p3），單頁抽取必然殘缺——
        # 實測一份 4 頁謄本，每頁 structured_data 各自只有 1-3 個欄位，
        # 合起來卻是完整的一份。舊欄位 `pages[].structured_data` 不變，
        # 呼叫端要逐頁結果可用舊欄位，要完整文件結果改讀這個新欄位。
        document_fields = _merge_page_structured_data(pages)

        return {
            "file_name": filename,
            "file_url": file_url,
            "document_type": document_type,
            "total_pages": total_pages,
            "pages": pages,
            "document_fields": document_fields,
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

            # 合併結構化欄位：改用 _merge_page_structured_data（只填補缺值，
            # 不用後面頁面的殘值覆蓋前面已抽到的值）。原本這裡是
            # `all_structured.update(structured)`，後頁若把某欄位判成 None
            # 會蓋掉前頁已抽對的值。
            all_structured = _merge_page_structured_data(pages) or {}

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
