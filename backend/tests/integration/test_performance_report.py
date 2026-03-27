"""
效能報告測試 - 展示實際辨識率和成效

生成詳細的辨識結果報告，包含：
- OCR 原始結果
- 規則後處理改善
- 處理時間統計
- 信心度分析
"""

import pytest
import time
from pathlib import Path
from PIL import Image
import fitz

from app.lib.multi_type_ocr.processor_factory import ProcessorFactory


# 測試資料路徑
DATA_DIR = Path(__file__).parent.parent.parent / "data"
CONTRACTS_DIR = Path(__file__).parent.parent.parent.parent / "data" / "contracts"

SINGLE_PAGE_IMAGE = DATA_DIR / "建物謄本.jpg"
TEST_CONTRACTS = [
    "75038b05cd85c2d6971ae0f350d2ff11.pdf",
    "c3198c44a4482d38a2b61ccd86217aee.pdf",
    "5640a32102ce9988322ef710e877e60c.pdf",
]


class TestPerformanceReport:
    """效能報告與辨識率測試"""

    @pytest.mark.asyncio
    async def test_transcript_recognition_quality(self):
        """測試謄本辨識品質與效能"""
        print("\n" + "=" * 80)
        print("謄本辨識效能報告")
        print("=" * 80)

        processor = ProcessorFactory.get_processor("transcript")

        with open(SINGLE_PAGE_IMAGE, "rb") as f:
            file_contents = f.read()

        start_time = time.time()
        result = await processor.process(
            file_contents=file_contents,
            filename="建物謄本.jpg",
            page_number=1,
            total_pages=1,
            enable_llm=False
        )
        processing_time = time.time() - start_time

        # OCR 原始結果
        ocr_text = result["ocr_raw"]["text"]
        ocr_confidence = result["ocr_raw"]["confidence"]

        # 規則後處理結果
        processed_text = result["rule_postprocessed"]["text"]
        stats = result["rule_postprocessed"]["stats"]

        print(f"\n【基本資訊】")
        print(f"  檔案名稱: 建物謄本.jpg")
        print(f"  處理時間: {processing_time:.2f} 秒")
        print(f"  OCR 引擎信心度: {ocr_confidence:.2%}")

        print(f"\n【OCR 原始結果】")
        print(f"  辨識字元數: {len(ocr_text)}")
        print(f"  文字預覽（前 200 字元）:")
        print(f"  {ocr_text[:200]}")

        print(f"\n【規則後處理統計】")
        print(f"  錯別字修正次數: {stats.get('typo_fixes', 0)}")
        print(f"  格式校正次數: {stats.get('format_corrections', 0)}")
        print(f"  處理前字元數: {stats.get('total_chars_before', 0)}")
        print(f"  處理後字元數: {stats.get('total_chars_after', 0)}")

        print(f"\n【處理後文字預覽】（前 200 字元）")
        print(f"  {processed_text[:200]}")

        # 計算改善率
        if stats.get('total_chars_before', 0) > 0:
            chars_changed = abs(stats.get('total_chars_after', 0) - stats.get('total_chars_before', 0))
            change_rate = chars_changed / stats.get('total_chars_before', 0) * 100
            print(f"\n【改善效果】")
            print(f"  字元變化率: {change_rate:.2f}%")
            print(f"  總修正次數: {stats.get('typo_fixes', 0) + stats.get('format_corrections', 0)}")

        print("\n" + "=" * 80 + "\n")

    @pytest.mark.asyncio
    async def test_contract_recognition_quality(self):
        """測試合約辨識品質與效能"""
        print("\n" + "=" * 80)
        print("合約辨識效能報告")
        print("=" * 80)

        processor = ProcessorFactory.get_processor("contract")

        for i, contract_filename in enumerate(TEST_CONTRACTS[:3], 1):
            contract_path = CONTRACTS_DIR / contract_filename

            if not contract_path.exists():
                print(f"\n警告: {contract_filename} 不存在，跳過")
                continue

            print(f"\n【合約 #{i}: {contract_filename}】")

            # 開啟 PDF
            doc = fitz.open(contract_path)
            total_pages = len(doc)
            file_size = contract_path.stat().st_size

            print(f"  檔案大小: {file_size / 1024:.0f} KB")
            print(f"  總頁數: {total_pages}")

            # 處理第一頁
            page = doc[0]
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img_bytes = pix.tobytes("png")
            doc.close()

            start_time = time.time()
            result = await processor.process(
                file_contents=img_bytes,
                filename=contract_filename,
                page_number=1,
                total_pages=total_pages,
                enable_llm=False
            )
            processing_time = time.time() - start_time

            # 結果分析
            ocr_text = result["ocr_raw"]["text"]
            ocr_confidence = result["ocr_raw"]["confidence"]
            processed_text = result["rule_postprocessed"]["text"]
            stats = result["rule_postprocessed"]["stats"]

            print(f"\n  處理時間: {processing_time:.2f} 秒")
            print(f"  OCR 信心度: {ocr_confidence:.2%}")
            print(f"  辨識字元數: {len(ocr_text)}")
            print(f"  錯別字修正: {stats.get('typo_fixes', 0)} 次")
            print(f"  格式校正: {stats.get('format_corrections', 0)} 次")

            print(f"\n  辨識文字預覽（前 150 字元）:")
            print(f"  {ocr_text[:150]}")

            # 結構化資料
            structured_data = result.get("structured_data")
            if structured_data:
                print(f"\n  結構化欄位提取信心度: {structured_data.get('extraction_confidence', 0):.2%}")

        print("\n" + "=" * 80 + "\n")

    @pytest.mark.asyncio
    async def test_comprehensive_performance_summary(self):
        """綜合效能總結報告"""
        print("\n" + "=" * 80)
        print("綜合效能總結報告")
        print("=" * 80)

        # 測試謄本
        transcript_processor = ProcessorFactory.get_processor("transcript")
        with open(SINGLE_PAGE_IMAGE, "rb") as f:
            file_contents = f.read()

        t_start = time.time()
        t_result = await transcript_processor.process(
            file_contents=file_contents,
            filename="建物謄本.jpg",
            page_number=1,
            total_pages=1,
            enable_llm=False
        )
        t_time = time.time() - t_start

        # 測試合約
        contract_processor = ProcessorFactory.get_processor("contract")
        contract_times = []
        contract_confidences = []

        for contract_filename in TEST_CONTRACTS[:3]:
            contract_path = CONTRACTS_DIR / contract_filename
            if not contract_path.exists():
                continue

            doc = fitz.open(contract_path)
            page = doc[0]
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img_bytes = pix.tobytes("png")
            doc.close()

            c_start = time.time()
            c_result = await contract_processor.process(
                file_contents=img_bytes,
                filename=contract_filename,
                page_number=1,
                total_pages=1,
                enable_llm=False
            )
            c_time = time.time() - c_start

            contract_times.append(c_time)
            contract_confidences.append(c_result["ocr_raw"]["confidence"])

        print(f"\n【謄本處理效能】")
        print(f"  平均處理時間: {t_time:.2f} 秒/頁")
        print(f"  OCR 信心度: {t_result['ocr_raw']['confidence']:.2%}")
        print(f"  辨識字元數: {len(t_result['ocr_raw']['text'])}")
        print(f"  效能評級: {'✅ 優秀' if t_time < 10 else '⚠️ 尚可' if t_time < 30 else '❌ 需改進'}")

        if contract_times:
            avg_contract_time = sum(contract_times) / len(contract_times)
            avg_contract_confidence = sum(contract_confidences) / len(contract_confidences)

            print(f"\n【合約處理效能】")
            print(f"  測試合約數: {len(contract_times)}")
            print(f"  平均處理時間: {avg_contract_time:.2f} 秒/頁")
            print(f"  平均 OCR 信心度: {avg_contract_confidence:.2%}")
            print(f"  最快處理時間: {min(contract_times):.2f} 秒")
            print(f"  最慢處理時間: {max(contract_times):.2f} 秒")
            print(f"  效能評級: {'✅ 優秀' if avg_contract_time < 5 else '⚠️ 尚可' if avg_contract_time < 30 else '❌ 需改進'}")

        print(f"\n【與規格要求對比】")
        print(f"  規格要求: < 30 秒/頁")
        print(f"  謄本實際: {t_time:.2f} 秒 ({'✅ 符合' if t_time < 30 else '❌ 不符合'})")
        if contract_times:
            print(f"  合約實際: {avg_contract_time:.2f} 秒 ({'✅ 符合' if avg_contract_time < 30 else '❌ 不符合'})")

        print(f"\n【信心度要求對比】")
        print(f"  謄本信心度: {t_result['ocr_raw']['confidence']:.2%} (閾值 ≥ 40%)")
        if contract_confidences:
            print(f"  合約信心度: {avg_contract_confidence:.2%} (閾值 ≥ 60%)")

        print("\n" + "=" * 80 + "\n")
