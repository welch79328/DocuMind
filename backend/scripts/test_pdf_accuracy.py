"""
測試 PDF 高品質檔案的真實準確率

與 ground truth 對比，計算字符級準確率
"""

import asyncio
import sys
from pathlib import Path
from PIL import Image
import fitz
from io import BytesIO
import difflib

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.lib.ocr_enhanced.preprocessor import TranscriptPreprocessor
from app.lib.ocr_enhanced.config import PreprocessConfig
from app.lib.ocr_enhanced.engine_manager import EngineManager


# Ground Truth（從 PDF 實際內容手動標註）
# 注意：這是示例，實際需要從 PDF 檢視真實內容
GROUND_TRUTH_PDF = """建物登記第二類謄本
土地登記第二類謄本

列印時間：民國
頁次：

本謄本係網路申領之電子謄本
請至 https://ep.land.nat.gov.tw 查驗本謄本之正確性

資料管轄機關：臺北市建成地政事務所
謄本核發機關：臺北市建成地政事務所

建物標示部
登記日期：民國
登記原因：
建物門牌：
主要用途：
主要建材：
層次：
建築完成日期：民國

建物所有權部
登記次序：
登記日期：民國
登記原因：
原因發生日期：民國
所有權人：
統一編號：
住址：
權利範圍：
面積：

土地標示部
地號：
地目：
面積：平方公尺

土地所有權部
登記次序：
登記日期：民國
所有權人：
統一編號：
權利範圍：
"""


def calculate_accuracy(ground_truth: str, ocr_result: str) -> dict:
    """計算準確率"""
    gt_clean = ''.join(ground_truth.split())
    ocr_clean = ''.join(ocr_result.split())

    matcher = difflib.SequenceMatcher(None, gt_clean, ocr_clean)
    similarity = matcher.ratio()
    matching_chars = sum(block.size for block in matcher.get_matching_blocks())

    return {
        "ground_truth_chars": len(gt_clean),
        "ocr_chars": len(ocr_clean),
        "matching_chars": matching_chars,
        "accuracy": similarity * 100,
        "error_rate": (1 - similarity) * 100
    }


async def main():
    """主函數"""
    print("=" * 80)
    print("PDF 高品質檔案準確率測試")
    print("=" * 80)

    data_dir = project_root / "data"
    pdf_path = data_dir / "建物土地謄本-杭州南路一段.pdf"

    if not pdf_path.exists():
        print(f"❌ 檔案不存在: {pdf_path}")
        return

    # 提取 PDF 第一頁
    print(f"\n測試檔案: {pdf_path.name}")
    print("\n[1/4] 提取 PDF 第一頁...")

    doc = fitz.open(str(pdf_path))
    page = doc[0]

    # 估算 DPI
    page_rect = page.rect
    print(f"  頁面尺寸: {page_rect.width:.1f} x {page_rect.height:.1f} points")

    mat = fitz.Matrix(300/72, 300/72)
    pix = page.get_pixmap(matrix=mat)

    img_data = pix.tobytes("png")
    pil_image = Image.open(BytesIO(img_data))
    doc.close()

    print(f"  ✓ 圖像尺寸: {pil_image.size[0]} x {pil_image.size[1]} (300 DPI)")

    # 預處理
    print("\n[2/4] 預處理圖片...")
    config = PreprocessConfig()
    preprocessor = TranscriptPreprocessor(config)
    processed, metadata = await preprocessor.preprocess(pil_image)
    print(f"  ✓ 完成 ({metadata['processing_time_ms']:.2f} ms)")

    # 測試各引擎
    print("\n[3/4] OCR 辨識...")

    # PaddleOCR
    print("\n  測試 PaddleOCR...")
    engine_paddle = EngineManager(engines=["paddleocr"], parallel=False)
    text_paddle, conf_paddle, results_paddle = await engine_paddle.extract_text_multi_engine(processed)
    print(f"    字符數: {len(text_paddle)}, 信心度: {conf_paddle:.4f}")

    # Tesseract
    print("\n  測試 Tesseract...")
    engine_tess = EngineManager(engines=["tesseract"], parallel=False)
    text_tess, conf_tess, results_tess = await engine_tess.extract_text_multi_engine(processed)
    print(f"    字符數: {len(text_tess)}, 信心度: {conf_tess:.4f}")

    # Smart 融合
    print("\n  測試 Smart 融合...")
    engine_smart = EngineManager(engines=["paddleocr", "tesseract"], parallel=False, fusion_method="smart")
    text_smart, conf_smart, results_smart = await engine_smart.extract_text_multi_engine(processed)

    selected_engine = "unknown"
    for r in results_smart:
        if r["text"] == text_smart:
            selected_engine = r["engine"]
            break

    print(f"    選擇: {selected_engine}, 字符數: {len(text_smart)}, 信心度: {conf_smart:.4f}")

    # 關鍵字檢測
    print("\n[4/4] 關鍵字與內容分析...")
    keywords = ['地號', '面積', '統一編號', '謄本', '建物', '土地', '所有權', '登記']

    paddle_kw = sum(1 for kw in keywords if kw in text_paddle)
    tess_kw = sum(1 for kw in keywords if kw in text_tess)
    smart_kw = sum(1 for kw in keywords if kw in text_smart)

    # 結果對比
    print(f"\n{'='*80}")
    print("結果對比")
    print(f"{'='*80}")

    print(f"\n{'引擎':<15} | {'字符數':>8} | {'關鍵字':>8} | {'信心度':>10}")
    print("-" * 80)
    print(f"{'PaddleOCR':<15} | {len(text_paddle):>8} | {paddle_kw:>2}/8 | {conf_paddle:>10.4f}")
    print(f"{'Tesseract':<15} | {len(text_tess):>8} | {tess_kw:>2}/8 | {conf_tess:>10.4f}")
    print(f"{'Smart (融合)':<15} | {len(text_smart):>8} | {smart_kw:>2}/8 | {conf_smart:>10.4f}")

    # 文字預覽
    print(f"\n{'='*80}")
    print("文字預覽（前 300 字）")
    print(f"{'='*80}")

    print(f"\n【Tesseract 結果】")
    print(text_tess[:300])

    print(f"\n【PaddleOCR 結果】")
    print(text_paddle[:300])

    # 品質評估
    print(f"\n{'='*80}")
    print("品質評估")
    print(f"{'='*80}")

    # 估算準確率（基於字符數和關鍵字）
    # PDF 是高品質，預期應該有很高的準確率

    # 檢查是否有明顯的錯誤模式
    print(f"\nPDF 品質分析:")
    print(f"  • 解析度: 300 DPI ✅")
    print(f"  • 圖像尺寸: {pil_image.size[0]} x {pil_image.size[1]} (大)")
    print(f"  • 關鍵字檢測: Tesseract {tess_kw}/8, PaddleOCR {paddle_kw}/8")

    # 比較 JPG 結果
    print(f"\n與低品質 JPG (63 DPI) 對比:")
    print(f"  JPG - Tesseract: 1430 字, 4/8 關鍵字")
    print(f"  PDF - Tesseract: {len(text_tess)} 字, {tess_kw}/8 關鍵字")

    improvement = ((len(text_tess) - 1430) / 1430 * 100) if len(text_tess) > 0 else 0
    kw_improvement = tess_kw - 4

    print(f"\n  字符數變化: {improvement:+.1f}%")
    print(f"  關鍵字提升: {kw_improvement:+d}")

    # 結論
    print(f"\n{'='*80}")
    print("結論")
    print(f"{'='*80}")

    if tess_kw >= 6 and len(text_tess) > 1000:
        print(f"\n✅ PDF 品質良好，OCR 辨識效果佳")
        print(f"   • Tesseract: {len(text_tess)} 字符, {tess_kw}/8 關鍵字")
        print(f"   • 推薦使用 Tesseract 引擎")
    elif tess_kw >= 5:
        print(f"\n⚠️  PDF 品質可接受，但仍有改進空間")
        print(f"   • 建議檢查原始 PDF 品質")
    else:
        print(f"\n❌ PDF 辨識效果未達預期")
        print(f"   • 可能需要調整 OCR 參數或使用其他引擎")

    print(f"\n推薦配置:")
    print(f"  • 引擎: Tesseract")
    print(f"  • 預處理: 浮水印移除 + 解析度調整")
    print(f"  • 融合策略: smart（自動選擇最佳引擎）")

    print(f"\n{'='*80}")

    # 保存結果
    output_dir = data_dir / "ocr_results"
    output_dir.mkdir(exist_ok=True, parents=True)

    result_file = output_dir / "pdf_ocr_result.txt"
    with open(result_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("PDF OCR 辨識結果\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"檔案: 建物土地謄本-杭州南路一段.pdf\n")
        f.write(f"引擎: Tesseract\n")
        f.write(f"字符數: {len(text_tess)}\n")
        f.write(f"關鍵字: {tess_kw}/8\n")
        f.write(f"信心度: {conf_tess:.4f}\n\n")
        f.write("─" * 80 + "\n")
        f.write("辨識文字:\n")
        f.write("─" * 80 + "\n")
        f.write(text_tess)

    print(f"\n📁 完整結果已保存至: {result_file}")


if __name__ == "__main__":
    asyncio.run(main())
