"""
謄本 OCR 辨識效果測試 - 多種預處理配置

測試不同預處理配置的效果
"""

import asyncio
import sys
from pathlib import Path
from PIL import Image
import numpy as np

# 添加專案根目錄到 Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.lib.ocr_enhanced.preprocessor import TranscriptPreprocessor
from app.lib.ocr_enhanced.config import PreprocessConfig


async def ocr_with_paddleocr(image_input) -> tuple[str, float]:
    """使用 PaddleOCR 辨識圖片"""
    import time
    import cv2
    from paddleocr import PaddleOCR

    # 初始化 PaddleOCR
    ocr = PaddleOCR(use_angle_cls=True, lang='chinese_cht', use_gpu=False, show_log=False)

    # 處理輸入
    if isinstance(image_input, str):
        image = Image.open(image_input)
        img_array = np.array(image)
    elif isinstance(image_input, np.ndarray):
        img_array = image_input
        # 確保是 RGB 格式
        if len(img_array.shape) == 2:
            img_array = cv2.cvtColor(img_array, cv2.COLOR_GRAY2RGB)
        elif img_array.shape[2] == 3:
            img_array = cv2.cvtColor(img_array, cv2.COLOR_BGR2RGB)
    else:
        img_array = np.array(image_input)

    # 計時
    start_time = time.time()

    # OCR 辨識
    result = ocr.ocr(img_array, cls=True)

    # 計算處理時間
    processing_time = (time.time() - start_time) * 1000

    # 提取文字
    text_lines = []
    if result and result[0]:
        for line in result[0]:
            text_content = line[1][0]
            text_lines.append(text_content)

    return "\n".join(text_lines), processing_time


async def test_image_with_config(image_path: str, config: PreprocessConfig, config_name: str):
    """使用指定配置測試圖片"""
    print(f"\n{'─'*80}")
    print(f"配置: {config_name}")
    print(f"{'─'*80}")

    # 讀取原始圖片
    pil_image = Image.open(image_path)

    # 預處理
    preprocessor = TranscriptPreprocessor(config)
    processed, metadata = await preprocessor.preprocess(pil_image)

    print(f"⏱️  預處理時間: {metadata['processing_time_ms']:.2f} ms")
    print(f"✓ 浮水印移除: {metadata['watermark_removed']}")
    print(f"✓ 二值化: {metadata['binarization_applied']}")
    if metadata.get('binarization_applied'):
        print(f"  方法: {metadata.get('binarization_method', 'N/A')}")

    # OCR 辨識
    text, ocr_time = await ocr_with_paddleocr(processed)

    print(f"⏱️  OCR 時間: {ocr_time:.2f} ms")
    print(f"📝 辨識字符數: {len(text)}")

    # 關鍵字檢測
    keywords = ['地號', '面積', '統一編號', '謄本', '建物', '土地', '所有權', '登記']
    keyword_count = sum(1 for kw in keywords if kw in text)
    print(f"🔍 關鍵字: {keyword_count}/{len(keywords)}")

    # 顯示前 150 字
    print(f"\n文字預覽:")
    print(text[:150])

    return {
        "config": config_name,
        "chars": len(text),
        "keywords": keyword_count,
        "preprocessing_time": metadata['processing_time_ms'],
        "ocr_time": ocr_time,
        "total_time": metadata['processing_time_ms'] + ocr_time
    }


async def main():
    """主函數"""
    print("=" * 80)
    print("謄本 OCR 辨識效果測試 - 多種配置對比")
    print("=" * 80)

    # 測試檔案
    image_path = project_root / "data" / "建物謄本.jpg"

    if not image_path.exists():
        print(f"❌ 檔案不存在: {image_path}")
        return

    # 原始圖片 OCR（基準）
    print(f"\n{'='*80}")
    print("基準測試: 原始圖片（無預處理）")
    print(f"{'='*80}")

    original_text, original_time = await ocr_with_paddleocr(str(image_path))
    original_keywords = sum(1 for kw in ['地號', '面積', '統一編號', '謄本', '建物', '土地', '所有權', '登記'] if kw in original_text)

    print(f"⏱️  OCR 時間: {original_time:.2f} ms")
    print(f"📝 辨識字符數: {len(original_text)}")
    print(f"🔍 關鍵字: {original_keywords}/8")
    print(f"\n文字預覽:")
    print(original_text[:150])

    # 測試多種配置
    configs = [
        (PreprocessConfig(
            enable_watermark_removal=False,
            enable_binarization=False,
            enable_denoising=False
        ), "無處理"),

        (PreprocessConfig(
            enable_watermark_removal=True,
            enable_binarization=False,
            enable_denoising=False
        ), "僅移除浮水印"),

        (PreprocessConfig(
            enable_watermark_removal=False,
            enable_binarization=True,
            enable_denoising=False,
            binarization_method="sauvola"
        ), "僅二值化(Sauvola)"),

        (PreprocessConfig(
            enable_watermark_removal=True,
            enable_binarization=False,
            enable_denoising=True
        ), "移除浮水印+去噪"),

        (PreprocessConfig(
            enable_watermark_removal=True,
            enable_binarization=True,
            enable_denoising=False,
            binarization_method="sauvola"
        ), "浮水印+二值化(Sauvola)"),

        (PreprocessConfig(
            enable_watermark_removal=True,
            enable_binarization=True,
            enable_denoising=True,
            binarization_method="gaussian"
        ), "完整處理(Gaussian)"),
    ]

    results = []

    for config, config_name in configs:
        try:
            result = await test_image_with_config(str(image_path), config, config_name)
            results.append(result)
        except Exception as e:
            print(f"❌ 配置 '{config_name}' 測試失敗: {e}")

    # 生成對比報告
    print(f"\n\n{'='*80}")
    print("對比報告")
    print(f"{'='*80}")

    print(f"\n基準 (原始圖片):")
    print(f"  字符數: {len(original_text)}")
    print(f"  關鍵字: {original_keywords}/8")
    print(f"  時間: {original_time:.2f} ms")

    print(f"\n預處理配置對比:")
    print(f"{'配置':<30} {'字符數':>10} {'關鍵字':>10} {'總時間(ms)':>15} {'vs基準':>10}")
    print("─" * 80)

    for result in results:
        char_diff = result['chars'] - len(original_text)
        char_diff_pct = (char_diff / len(original_text) * 100) if len(original_text) > 0 else 0

        print(f"{result['config']:<30} {result['chars']:>10} {result['keywords']:>10}/8 {result['total_time']:>15.2f} {char_diff_pct:>+9.1f}%")

    # 找出最佳配置
    best_result = max(results, key=lambda x: x['chars'])

    print(f"\n🏆 最佳配置: {best_result['config']}")
    print(f"   字符數: {best_result['chars']} ({best_result['chars'] - len(original_text):+d})")
    print(f"   關鍵字: {best_result['keywords']}/8")
    print(f"   總時間: {best_result['total_time']:.2f} ms")

    print(f"\n{'='*80}")
    print("✅ 測試完成")
    print(f"{'='*80}")


if __name__ == "__main__":
    asyncio.run(main())
