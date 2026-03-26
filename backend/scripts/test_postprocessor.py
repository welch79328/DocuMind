"""
測試 Postprocessor 後處理效果

驗證錯別字修正與格式校正是否提升準確率
"""

import asyncio
import sys
from pathlib import Path
from PIL import Image
import fitz
from io import BytesIO

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.lib.ocr_enhanced.preprocessor import TranscriptPreprocessor
from app.lib.ocr_enhanced.config import PreprocessConfig
from app.lib.ocr_enhanced.engine_manager import EngineManager
from app.lib.ocr_enhanced.postprocessor import TranscriptPostprocessor


async def test_pdf_with_postprocessing():
    """測試 PDF 完整流程：預處理 → OCR → 後處理"""
    print("=" * 80)
    print("後處理效果測試（PDF 高品質檔案）")
    print("=" * 80)

    data_dir = project_root / "data"
    pdf_path = data_dir / "建物土地謄本-杭州南路一段.pdf"

    if not pdf_path.exists():
        print(f"❌ 檔案不存在: {pdf_path}")
        return

    # ========== 步驟 1: 提取 PDF ==========
    print(f"\n[1/5] 提取 PDF 第一頁...")
    doc = fitz.open(str(pdf_path))
    page = doc[0]
    mat = fitz.Matrix(300/72, 300/72)
    pix = page.get_pixmap(matrix=mat)

    img_data = pix.tobytes("png")
    pil_image = Image.open(BytesIO(img_data))
    doc.close()
    print(f"  ✓ 圖像尺寸: {pil_image.size[0]} x {pil_image.size[1]}")

    # ========== 步驟 2: 預處理 ==========
    print(f"\n[2/5] 預處理圖片...")
    config = PreprocessConfig()
    preprocessor = TranscriptPreprocessor(config)
    processed, metadata = await preprocessor.preprocess(pil_image)
    print(f"  ✓ 完成 ({metadata['processing_time_ms']:.2f} ms)")

    # ========== 步驟 3: OCR 辨識 ==========
    print(f"\n[3/5] OCR 辨識（Tesseract）...")
    engine_manager = EngineManager(engines=["tesseract"], parallel=False)
    raw_text, confidence, results = await engine_manager.extract_text_multi_engine(processed)
    print(f"  ✓ 辨識完成")
    print(f"     字符數: {len(raw_text)}")
    print(f"     信心度: {confidence:.4f}")

    # 關鍵字檢測（原始）
    keywords = ['地號', '面積', '統一編號', '謄本', '建物', '土地', '所有權', '登記']
    raw_keywords = sum(1 for kw in keywords if kw in raw_text)
    print(f"     關鍵字: {raw_keywords}/8")

    # ========== 步驟 4: 後處理 ==========
    print(f"\n[4/5] 後處理...")
    postprocessor = TranscriptPostprocessor(
        enable_typo_fix=True,
        enable_format_correction=True
    )

    processed_text, post_stats = postprocessor.postprocess(raw_text)

    print(f"  ✓ 後處理完成")
    print(f"     錯別字修正: {post_stats['typo_fixes']} 次")
    print(f"     格式校正: {post_stats['format_corrections']} 次")
    print(f"     字符數變化: {post_stats['total_chars_before']} → {post_stats['total_chars_after']}")

    # 關鍵字檢測（後處理）
    processed_keywords = sum(1 for kw in keywords if kw in processed_text)
    print(f"     關鍵字: {processed_keywords}/8 ({processed_keywords - raw_keywords:+d})")

    # ========== 步驟 5: 結果對比 ==========
    print(f"\n[5/5] 效果分析...")

    # 內容驗證
    validation = postprocessor.validate_transcript_content(processed_text)
    print(f"  內容完整性:")
    print(f"     關鍵字匹配: {validation['keyword_count']}/{validation['total_keywords']}")
    print(f"     完整性信心: {validation['confidence']*100:.1f}%")

    # 文字對比
    print(f"\n{'='*80}")
    print("文字對比（前 300 字）")
    print(f"{'='*80}")

    print(f"\n【原始 OCR 結果】")
    print(raw_text[:300])

    print(f"\n【後處理結果】")
    print(processed_text[:300])

    # 顯示具體修正
    print(f"\n{'='*80}")
    print("具體修正範例")
    print(f"{'='*80}")

    # 查找一些常見修正
    corrections_found = []

    if "十地" in raw_text and "土地" in processed_text:
        corrections_found.append("「十地」 → 「土地」")
    if "膽本" in raw_text and "謄本" in processed_text:
        corrections_found.append("「膽本」 → 「謄本」")
    if "攝記" in raw_text and "登記" in processed_text:
        corrections_found.append("「攝記」 → 「登記」")

    if corrections_found:
        for correction in corrections_found:
            print(f"  ✓ {correction}")
    else:
        print("  （檢查前 300 字範圍內無明顯修正）")

    # 最終評估
    print(f"\n{'='*80}")
    print("最終評估")
    print(f"{'='*80}")

    char_improvement = ((post_stats['total_chars_after'] - post_stats['total_chars_before']) /
                       post_stats['total_chars_before'] * 100) if post_stats['total_chars_before'] > 0 else 0
    keyword_improvement = processed_keywords - raw_keywords

    print(f"\n改善指標:")
    print(f"  • 字符數變化: {char_improvement:+.1f}%")
    print(f"  • 關鍵字提升: {keyword_improvement:+d}")
    print(f"  • 錯別字修正: {post_stats['typo_fixes']} 次")
    print(f"  • 格式校正: {post_stats['format_corrections']} 次")

    # 準確率估算
    # 基於關鍵字和內容完整性
    estimated_accuracy_before = (raw_keywords / len(keywords)) * 0.6 + confidence * 0.4
    estimated_accuracy_after = (processed_keywords / len(keywords)) * 0.6 + validation['confidence'] * 0.4

    print(f"\n估算準確率:")
    print(f"  • OCR 原始: {estimated_accuracy_before*100:.1f}%")
    print(f"  • 後處理後: {estimated_accuracy_after*100:.1f}%")
    print(f"  • 提升: {(estimated_accuracy_after - estimated_accuracy_before)*100:+.1f} 百分點")

    # 結論
    print(f"\n{'='*80}")
    print("結論")
    print(f"{'='*80}")

    if post_stats['typo_fixes'] >= 50:
        print(f"\n✅ 後處理效果顯著")
        print(f"   • 修正了 {post_stats['typo_fixes']} 處錯誤")
        print(f"   • 關鍵字從 {raw_keywords}/8 提升到 {processed_keywords}/8")
    elif post_stats['typo_fixes'] >= 20:
        print(f"\n⚠️  後處理有改善，但仍需優化")
        print(f"   • 修正了 {post_stats['typo_fixes']} 處錯誤")
    else:
        print(f"\n❌ 後處理效果有限")
        print(f"   • 僅修正了 {post_stats['typo_fixes']} 處錯誤")
        print(f"   • 可能需要擴充錯別字字典")

    if estimated_accuracy_after >= 0.85:
        print(f"\n🎯 達到目標準確率 85%+")
    elif estimated_accuracy_after >= 0.70:
        print(f"\n📈 準確率良好 (70-85%)")
    else:
        print(f"\n📊 準確率仍需提升 (<70%)")

    print(f"\n{'='*80}")

    # 保存結果
    output_dir = data_dir / "ocr_results"
    output_dir.mkdir(exist_ok=True, parents=True)

    result_file = output_dir / "pdf_postprocessed_result.txt"
    with open(result_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("後處理結果\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"錯別字修正: {post_stats['typo_fixes']} 次\n")
        f.write(f"格式校正: {post_stats['format_corrections']} 次\n")
        f.write(f"關鍵字: {processed_keywords}/8\n\n")
        f.write("─" * 80 + "\n")
        f.write("處理後文字:\n")
        f.write("─" * 80 + "\n")
        f.write(processed_text)

    print(f"\n📁 完整結果已保存至: {result_file}")


if __name__ == "__main__":
    asyncio.run(test_pdf_with_postprocessing())
