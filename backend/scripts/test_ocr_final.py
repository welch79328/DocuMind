"""
最終 OCR 測試 - 使用優化後的預設配置
"""

import asyncio
import sys
from pathlib import Path
from PIL import Image
import numpy as np
import time
import cv2

# 添加專案根目錄到 Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.lib.ocr_enhanced.preprocessor import TranscriptPreprocessor
from app.lib.ocr_enhanced.config import PreprocessConfig


async def ocr_with_paddleocr(image_input) -> tuple[str, float]:
    """使用 PaddleOCR 辨識圖片"""
    from paddleocr import PaddleOCR

    ocr = PaddleOCR(use_angle_cls=True, lang='chinese_cht', use_gpu=False, show_log=False)

    # 處理輸入
    if isinstance(image_input, str):
        image = Image.open(image_input)
        img_array = np.array(image)
    elif isinstance(image_input, np.ndarray):
        img_array = image_input
        if len(img_array.shape) == 2:
            img_array = cv2.cvtColor(img_array, cv2.COLOR_GRAY2RGB)
        elif img_array.shape[2] == 3:
            img_array = cv2.cvtColor(img_array, cv2.COLOR_BGR2RGB)
    else:
        img_array = np.array(image_input)

    start_time = time.time()
    result = ocr.ocr(img_array, cls=True)
    processing_time = (time.time() - start_time) * 1000

    text_lines = []
    if result and result[0]:
        for line in result[0]:
            text_content = line[1][0]
            text_lines.append(text_content)

    return "\n".join(text_lines), processing_time


async def test_with_default_config(image_path: str):
    """使用預設配置測試"""
    print(f"\n{'='*80}")
    print(f"測試檔案: {Path(image_path).name}")
    print(f"使用優化後的預設配置")
    print(f"{'='*80}")

    # 讀取原始圖片
    pil_image = Image.open(image_path)
    print(f"\n📐 原始尺寸: {pil_image.size[0]} x {pil_image.size[1]}")

    # === 步驟 1: 原始圖片 OCR（基準） ===
    print(f"\n{'─'*80}")
    print("步驟 1: 原始圖片 OCR 辨識（基準）")
    print(f"{'─'*80}")

    original_text, original_time = await ocr_with_paddleocr(str(image_path))

    print(f"⏱️  OCR 時間: {original_time:.2f} ms")
    print(f"📝 辨識字符數: {len(original_text)}")

    keywords = ['地號', '面積', '統一編號', '謄本', '建物', '土地', '所有權', '登記']
    original_keywords = sum(1 for kw in keywords if kw in original_text)
    print(f"🔍 關鍵字: {original_keywords}/{len(keywords)}")

    print(f"\n文字預覽 (前 200 字):")
    print(original_text[:200])

    # === 步驟 2: 使用預設配置預處理 ===
    print(f"\n{'─'*80}")
    print("步驟 2: 使用優化後的預設配置預處理")
    print(f"{'─'*80}")

    config = PreprocessConfig()  # 使用預設配置
    print(f"配置:")
    print(f"  • 浮水印移除: {config.enable_watermark_removal}")
    print(f"  • 二值化: {config.enable_binarization}")
    print(f"  • 去噪: {config.enable_denoising}")
    print(f"  • 目標 DPI: {config.target_dpi}")
    print(f"  • HSV 閾值: lower={config.hsv_lower}, upper1={config.hsv_upper1}, upper2={config.hsv_upper2}")

    preprocessor = TranscriptPreprocessor(config)
    processed, metadata = await preprocessor.preprocess(pil_image)

    print(f"\n處理結果:")
    print(f"  ⏱️  處理時間: {metadata['processing_time_ms']:.2f} ms")
    print(f"  🖼️  輸出尺寸: {processed.shape[1]} x {processed.shape[0]}")
    print(f"  ✓ 浮水印移除: {metadata['watermark_removed']}")
    print(f"  ✓ 二值化: {metadata['binarization_applied']}")

    # === 步驟 3: 預處理後 OCR ===
    print(f"\n{'─'*80}")
    print("步驟 3: 預處理後圖片 OCR 辨識")
    print(f"{'─'*80}")

    enhanced_text, enhanced_time = await ocr_with_paddleocr(processed)

    print(f"⏱️  OCR 時間: {enhanced_time:.2f} ms")
    print(f"📝 辨識字符數: {len(enhanced_text)}")

    enhanced_keywords = sum(1 for kw in keywords if kw in enhanced_text)
    print(f"🔍 關鍵字: {enhanced_keywords}/{len(keywords)}")

    print(f"\n文字預覽 (前 200 字):")
    print(enhanced_text[:200])

    # === 步驟 4: 結果對比 ===
    print(f"\n{'='*80}")
    print("最終結果對比")
    print(f"{'='*80}")

    char_diff = len(enhanced_text) - len(original_text)
    char_diff_pct = (char_diff / len(original_text) * 100) if len(original_text) > 0 else 0

    keyword_diff = enhanced_keywords - original_keywords

    total_enhanced_time = metadata['processing_time_ms'] + enhanced_time
    time_overhead = total_enhanced_time - original_time
    time_overhead_pct = (time_overhead / original_time * 100) if original_time > 0 else 0

    print(f"\n📊 辨識字符數:")
    print(f"  原始: {len(original_text)} 字符")
    print(f"  預處理後: {len(enhanced_text)} 字符")
    print(f"  提升: {char_diff:+d} 字符 ({char_diff_pct:+.1f}%)")

    if char_diff_pct >= 15:
        print(f"  ✅ 達標！超過 15% 目標")
    else:
        print(f"  ❌ 未達標 (目標: ≥15%)")

    print(f"\n🔍 關鍵字檢測:")
    print(f"  原始: {original_keywords}/{len(keywords)}")
    print(f"  預處理後: {enhanced_keywords}/{len(keywords)}")
    print(f"  提升: {keyword_diff:+d}")

    print(f"\n⏱️  處理時間:")
    print(f"  原始 OCR: {original_time:.2f} ms")
    print(f"  預處理: {metadata['processing_time_ms']:.2f} ms")
    print(f"  預處理後 OCR: {enhanced_time:.2f} ms")
    print(f"  總時間: {total_enhanced_time:.2f} ms")
    print(f"  時間開銷: {time_overhead:+.2f} ms ({time_overhead_pct:+.1f}%)")

    # 保存結果
    output_dir = project_root / "data" / "ocr_results"
    output_dir.mkdir(exist_ok=True, parents=True)

    file_stem = Path(image_path).stem
    result_file = output_dir / f"{file_stem}_final_result.txt"

    with open(result_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("OCR 辨識最終結果\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"測試檔案: {Path(image_path).name}\n")
        f.write(f"配置: 優化後的預設配置\n\n")
        f.write(f"字符數提升: {char_diff:+d} ({char_diff_pct:+.1f}%)\n")
        f.write(f"關鍵字提升: {keyword_diff:+d}\n")
        f.write(f"時間開銷: {time_overhead:+.2f} ms ({time_overhead_pct:+.1f}%)\n\n")
        f.write("─" * 80 + "\n")
        f.write("原始 OCR 結果:\n")
        f.write("─" * 80 + "\n")
        f.write(original_text + "\n\n")
        f.write("─" * 80 + "\n")
        f.write("預處理後 OCR 結果:\n")
        f.write("─" * 80 + "\n")
        f.write(enhanced_text + "\n")

    print(f"\n📁 詳細結果已保存: {result_file}")

    return {
        "original_chars": len(original_text),
        "enhanced_chars": len(enhanced_text),
        "improvement_pct": char_diff_pct,
        "original_keywords": original_keywords,
        "enhanced_keywords": enhanced_keywords,
        "success": char_diff_pct >= 15
    }


async def main():
    """主函數"""
    print("=" * 80)
    print("OCR 預處理效果最終測試")
    print("使用優化後的預設配置")
    print("=" * 80)

    data_dir = project_root / "data"

    # 測試檔案
    test_files = [
        "建物謄本.jpg",
        # "建物土地謄本-杭州南路一段.pdf"  # PDF 測試稍後進行
    ]

    results = []

    for file_name in test_files:
        file_path = data_dir / file_name

        if not file_path.exists():
            print(f"\n⚠️  檔案不存在: {file_path}")
            continue

        try:
            result = await test_with_default_config(str(file_path))
            results.append((file_name, result))
        except Exception as e:
            print(f"\n❌ 測試失敗: {e}")
            import traceback
            traceback.print_exc()

    # 總結
    print(f"\n\n{'='*80}")
    print("測試總結")
    print(f"{'='*80}")

    all_success = True
    for file_name, result in results:
        status = "✅ 達標" if result['success'] else "❌ 未達標"
        print(f"\n📄 {file_name}: {status}")
        print(f"  字符數提升: {result['improvement_pct']:+.1f}%")
        print(f"  關鍵字: {result['enhanced_keywords']}/{8} (提升: {result['enhanced_keywords'] - result['original_keywords']:+d})")

        if not result['success']:
            all_success = False

    print(f"\n{'='*80}")
    if all_success:
        print("🎉 所有測試通過！預處理配置已優化完成。")
    else:
        print("⚠️  仍需進一步優化")
    print(f"{'='*80}")


if __name__ == "__main__":
    asyncio.run(main())
