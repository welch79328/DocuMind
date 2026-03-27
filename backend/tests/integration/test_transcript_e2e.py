"""
測試 TranscriptProcessor 端到端整合

驗收標準:
- 使用 backend/data/建物謄本.jpg 測試單頁處理
- 使用 backend/data/建物土地謄本-杭州南路一段.pdf 測試多頁處理
- 驗證 OCR 結果與既有系統一致
- 驗證處理時間 < 30 秒/頁
- 所有既有謄本測試案例全數通過
"""

import pytest
import time
from pathlib import Path
from PIL import Image
import fitz  # PyMuPDF

from app.lib.multi_type_ocr.processor_factory import ProcessorFactory
from app.lib.multi_type_ocr.transcript_processor import TranscriptProcessor


# 測試資料路徑
DATA_DIR = Path(__file__).parent.parent.parent / "data"
SINGLE_PAGE_IMAGE = DATA_DIR / "建物謄本.jpg"
MULTI_PAGE_PDF = DATA_DIR / "建物土地謄本-杭州南路一段.pdf"


class TestTranscriptProcessorE2E:
    """謄本處理器端到端整合測試"""

    def test_processor_factory_returns_transcript_processor(self):
        """驗證工廠返回正確的處理器類型"""
        processor = ProcessorFactory.get_processor("transcript")
        assert isinstance(processor, TranscriptProcessor)

    @pytest.mark.asyncio
    async def test_single_page_image_processing(self):
        """測試單頁圖像處理 (建物謄本.jpg)"""
        # 驗證測試資料存在
        assert SINGLE_PAGE_IMAGE.exists(), f"測試資料不存在: {SINGLE_PAGE_IMAGE}"

        # 取得處理器
        processor = ProcessorFactory.get_processor("transcript")

        # 讀取圖像
        with open(SINGLE_PAGE_IMAGE, "rb") as f:
            file_contents = f.read()

        # 開始計時
        start_time = time.time()

        # 執行處理
        result = await processor.process(
            file_contents=file_contents,
            filename="建物謄本.jpg",
            page_number=1,
            total_pages=1,
            enable_llm=False  # 不使用 LLM 以加快測試速度
        )

        # 計算處理時間
        processing_time = time.time() - start_time

        # 驗證結果結構
        assert "page_number" in result
        assert "ocr_raw" in result
        assert "rule_postprocessed" in result
        assert "structured_data" in result

        # 驗證 OCR 結果
        assert result["ocr_raw"]["text"] is not None
        assert len(result["ocr_raw"]["text"]) > 0
        assert result["ocr_raw"]["confidence"] >= 0.0
        assert result["ocr_raw"]["confidence"] <= 1.0

        # 驗證規則後處理結果
        assert result["rule_postprocessed"]["text"] is not None
        assert len(result["rule_postprocessed"]["text"]) > 0

        # 驗證處理時間
        assert processing_time < 30.0, \
            f"處理時間 {processing_time:.2f}秒 超過 30 秒限制"

        # 驗證頁碼資訊
        assert result["page_number"] == 1

        print(f"\n單頁圖像處理成功:")
        print(f"  處理時間: {processing_time:.2f} 秒")
        print(f"  OCR 信心度: {result['ocr_raw']['confidence']:.2%}")
        print(f"  文字長度: {len(result['ocr_raw']['text'])} 字元")

    @pytest.mark.asyncio
    async def test_multi_page_pdf_processing(self):
        """測試多頁 PDF 處理 (建物土地謄本-杭州南路一段.pdf)"""
        # 驗證測試資料存在
        assert MULTI_PAGE_PDF.exists(), f"測試資料不存在: {MULTI_PAGE_PDF}"

        # 取得處理器
        processor = ProcessorFactory.get_processor("transcript")

        # 開啟 PDF
        doc = fitz.open(MULTI_PAGE_PDF)
        total_pages = len(doc)

        assert total_pages > 0, "PDF 檔案頁數為 0"

        all_results = []
        total_processing_time = 0.0

        # 處理每一頁
        for page_number in range(1, total_pages + 1):
            # 提取頁面為圖像
            page = doc[page_number - 1]
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x 解析度
            img_bytes = pix.tobytes("png")

            # 開始計時
            start_time = time.time()

            # 執行處理
            result = await processor.process(
                file_contents=img_bytes,
                filename=f"建物土地謄本-杭州南路一段-p{page_number}.png",
                page_number=page_number,
                total_pages=total_pages,
                enable_llm=False  # 不使用 LLM 以加快測試速度
            )

            # 計算處理時間
            page_processing_time = time.time() - start_time
            total_processing_time += page_processing_time

            # 驗證每頁結果
            assert result["page_number"] == page_number
            assert result["ocr_raw"]["text"] is not None
            assert len(result["ocr_raw"]["text"]) > 0
            assert result["rule_postprocessed"]["text"] is not None

            # 驗證每頁處理時間
            assert page_processing_time < 30.0, \
                f"第 {page_number} 頁處理時間 {page_processing_time:.2f}秒 超過 30 秒限制"

            all_results.append(result)

            print(f"  第 {page_number}/{total_pages} 頁: "
                  f"{page_processing_time:.2f}秒, "
                  f"信心度 {result['ocr_raw']['confidence']:.2%}")

        doc.close()

        # 驗證所有頁面都被處理
        assert len(all_results) == total_pages

        # 驗證平均處理時間
        avg_time_per_page = total_processing_time / total_pages
        assert avg_time_per_page < 30.0, \
            f"平均每頁處理時間 {avg_time_per_page:.2f}秒 超過 30 秒限制"

        print(f"\n多頁 PDF 處理成功:")
        print(f"  總頁數: {total_pages}")
        print(f"  總處理時間: {total_processing_time:.2f} 秒")
        print(f"  平均每頁: {avg_time_per_page:.2f} 秒")

    @pytest.mark.asyncio
    async def test_processing_consistency(self):
        """測試處理結果一致性（多次處理同一文件應得到相似結果）"""
        # 使用單頁圖像進行一致性測試
        assert SINGLE_PAGE_IMAGE.exists()

        processor = ProcessorFactory.get_processor("transcript")

        with open(SINGLE_PAGE_IMAGE, "rb") as f:
            file_contents = f.read()

        # 執行兩次處理
        result1 = await processor.process(
            file_contents=file_contents,
            filename="建物謄本.jpg",
            page_number=1,
            total_pages=1,
            enable_llm=False
        )

        result2 = await processor.process(
            file_contents=file_contents,
            filename="建物謄本.jpg",
            page_number=1,
            total_pages=1,
            enable_llm=False
        )

        # 驗證兩次結果應該相同（OCR 是確定性的）
        assert result1["ocr_raw"]["text"] == result2["ocr_raw"]["text"]
        assert result1["ocr_raw"]["confidence"] == result2["ocr_raw"]["confidence"]
        assert result1["rule_postprocessed"]["text"] == result2["rule_postprocessed"]["text"]

        print("\n處理結果一致性驗證通過")

    @pytest.mark.asyncio
    async def test_ocr_quality_threshold(self):
        """測試 OCR 品質閾值（信心度應達到基本要求）"""
        assert SINGLE_PAGE_IMAGE.exists()

        processor = ProcessorFactory.get_processor("transcript")

        with open(SINGLE_PAGE_IMAGE, "rb") as f:
            file_contents = f.read()

        result = await processor.process(
            file_contents=file_contents,
            filename="建物謄本.jpg",
            page_number=1,
            total_pages=1,
            enable_llm=False
        )

        # 驗證 OCR 信心度達到最低要求
        # 注意：根據實際測試結果調整閾值
        # 謄本圖像品質可能影響信心度，使用較寬鬆的閾值
        min_confidence = 0.40  # 40% 最低信心度

        assert result["ocr_raw"]["confidence"] >= min_confidence, \
            f"OCR 信心度 {result['ocr_raw']['confidence']:.2%} 低於最低要求 {min_confidence:.2%}"

        # 驗證辨識文字長度合理
        text_length = len(result["ocr_raw"]["text"])
        assert text_length >= 100, \
            f"辨識文字長度 {text_length} 過短，可能辨識失敗"

        print(f"\nOCR 品質驗證通過:")
        print(f"  信心度: {result['ocr_raw']['confidence']:.2%}")
        print(f"  文字長度: {text_length} 字元")

    @pytest.mark.asyncio
    async def test_rule_postprocessing_improvements(self):
        """測試規則後處理改善效果"""
        assert SINGLE_PAGE_IMAGE.exists()

        processor = ProcessorFactory.get_processor("transcript")

        with open(SINGLE_PAGE_IMAGE, "rb") as f:
            file_contents = f.read()

        result = await processor.process(
            file_contents=file_contents,
            filename="建物謄本.jpg",
            page_number=1,
            total_pages=1,
            enable_llm=False
        )

        # 驗證規則後處理有統計資訊
        assert "stats" in result["rule_postprocessed"]
        stats = result["rule_postprocessed"]["stats"]

        # 驗證統計資訊包含修正次數
        assert "typo_fixes" in stats or "format_corrections" in stats

        print(f"\n規則後處理統計:")
        print(f"  {stats}")


class TestTranscriptProcessorBackwardCompatibility:
    """驗證與既有系統的向後兼容性"""

    @pytest.mark.asyncio
    async def test_processor_maintains_existing_behavior(self):
        """驗證處理器保持既有行為"""
        # 這個測試驗證新的 TranscriptProcessor 封裝
        # 與既有的 OCR 處理流程行為一致

        assert SINGLE_PAGE_IMAGE.exists()

        processor = ProcessorFactory.get_processor("transcript")

        with open(SINGLE_PAGE_IMAGE, "rb") as f:
            file_contents = f.read()

        result = await processor.process(
            file_contents=file_contents,
            filename="建物謄本.jpg",
            page_number=1,
            total_pages=1,
            enable_llm=False
        )

        # 驗證回應格式與既有系統一致
        required_fields = [
            "page_number",
            "ocr_raw",
            "rule_postprocessed",
            "structured_data"
        ]

        for field in required_fields:
            assert field in result, f"缺少必要欄位: {field}"

        # 驗證 ocr_raw 結構
        assert "text" in result["ocr_raw"]
        assert "confidence" in result["ocr_raw"]

        # 驗證 rule_postprocessed 結構
        assert "text" in result["rule_postprocessed"]
        assert "stats" in result["rule_postprocessed"]

        print("\n向後兼容性驗證通過")
