"""
測試真實謄本文件的預處理

處理 data/ 目錄下的謄本文件，並保存處理前後的對比圖。
"""

import asyncio
import sys
from pathlib import Path
from PIL import Image
import numpy as np
import cv2
import time

# 添加專案根目錄到 Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.lib.ocr_enhanced.preprocessor import TranscriptPreprocessor
from app.lib.ocr_enhanced.config import PreprocessConfig
from app.lib.ocr_enhanced.image_utils import save_image_smart


def save_comparison_image(original: np.ndarray, processed: np.ndarray, output_path: str):
    """
    保存處理前後的對比圖

    Args:
        original: 原始圖像（BGR）
        processed: 處理後圖像（BGR 或灰階）
        output_path: 輸出路徑
    """
    # 確保兩個圖像有相同的通道數
    if len(original.shape) == 3 and len(processed.shape) == 2:
        # 灰階 → BGR
        processed_bgr = cv2.cvtColor(processed, cv2.COLOR_GRAY2BGR)
    elif len(original.shape) == 2 and len(processed.shape) == 3:
        # BGR → 灰階
        original = cv2.cvtColor(original, cv2.COLOR_BGR2GRAY)
        original = cv2.cvtColor(original, cv2.COLOR_GRAY2BGR)
        processed_bgr = processed
    elif len(original.shape) == 2 and len(processed.shape) == 2:
        # 兩個都是灰階
        original = cv2.cvtColor(original, cv2.COLOR_GRAY2BGR)
        processed_bgr = cv2.cvtColor(processed, cv2.COLOR_GRAY2BGR)
    else:
        processed_bgr = processed

    # 調整大小以便並排顯示
    h1, w1 = original.shape[:2]
    h2, w2 = processed_bgr.shape[:2]

    # 統一高度為較小的高度
    target_height = min(h1, h2)

    # 等比例縮放
    scale1 = target_height / h1
    scale2 = target_height / h2

    original_resized = cv2.resize(original, (int(w1 * scale1), target_height))
    processed_resized = cv2.resize(processed_bgr, (int(w2 * scale2), target_height))

    # 並排拼接
    comparison = np.hstack([original_resized, processed_resized])

    # 添加標籤
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(comparison, "Original", (10, 30), font, 1, (0, 255, 0), 2)
    cv2.putText(comparison, "Processed", (original_resized.shape[1] + 10, 30),
                font, 1, (0, 255, 0), 2)

    # 保存（使用智能壓縮）
    final_path, file_size = save_image_smart(
        comparison,
        output_path,
        max_size_mb=4.5,
        prefer_png=False  # 對比圖優先使用 JPEG 壓縮
    )
    print(f"✅ 對比圖已保存: {final_path} ({file_size:.2f} MB)")


async def process_image_file(image_path: str, config: PreprocessConfig):
    """
    處理圖像文件

    Args:
        image_path: 圖像文件路徑
        config: 預處理配置
    """
    print(f"\n{'='*60}")
    print(f"處理文件: {Path(image_path).name}")
    print(f"{'='*60}")

    # 讀取圖像
    pil_image = Image.open(image_path)
    original_size = pil_image.size
    print(f"📐 原始尺寸: {original_size[0]} x {original_size[1]}")

    # 保存原始圖像（用於對比）
    original_bgr = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

    # 建立預處理器
    preprocessor = TranscriptPreprocessor(config)

    # 執行預處理
    start_time = time.time()
    processed, metadata = await preprocessor.preprocess(pil_image)
    end_time = time.time()

    print(f"\n📊 處理結果:")
    print(f"  ⏱️  處理時間: {metadata['processing_time_ms']:.2f} ms")
    print(f"  🖼️  輸出尺寸: {processed.shape[1]} x {processed.shape[0]}")
    print(f"  🎨 輸出格式: {processed.shape}")
    print(f"  📦 數據類型: {processed.dtype}")
    print(f"  📈 值範圍: [{np.min(processed)}, {np.max(processed)}]")

    print(f"\n🔧 應用的處理步驟:")
    print(f"  ✓ 浮水印移除: {'是' if metadata['watermark_removed'] else '否'}")
    print(f"  ✓ 二值化: {'是' if metadata['binarization_applied'] else '否'}")
    if metadata.get('binarization_applied'):
        print(f"    方法: {metadata.get('binarization_method', 'N/A')}")

    # 保存處理後的圖像
    output_dir = project_root / "data" / "processed"
    output_dir.mkdir(exist_ok=True)

    # 保存處理後的圖像（使用智能壓縮）
    file_stem = Path(image_path).stem
    processed_path = output_dir / f"{file_stem}_processed.png"
    final_processed_path, processed_size = save_image_smart(
        processed,
        str(processed_path),
        max_size_mb=4.5,
        prefer_png=True  # 處理後的圖優先使用 PNG
    )
    print(f"\n✅ 處理後圖像已保存: {final_processed_path} ({processed_size:.2f} MB)")

    # 保存對比圖
    comparison_path = output_dir / f"{file_stem}_comparison.png"
    save_comparison_image(original_bgr, processed, str(comparison_path))

    return processed, metadata


async def process_pdf_file(pdf_path: str, config: PreprocessConfig):
    """
    處理 PDF 文件（提取第一頁作為圖像）

    Args:
        pdf_path: PDF 文件路徑
        config: 預處理配置
    """
    print(f"\n{'='*60}")
    print(f"處理 PDF: {Path(pdf_path).name}")
    print(f"{'='*60}")

    try:
        import fitz  # PyMuPDF
    except ImportError:
        print("❌ 錯誤: 需要安裝 PyMuPDF")
        print("   請執行: pip install PyMuPDF")
        return None, None

    # 打開 PDF
    doc = fitz.open(pdf_path)
    print(f"📄 PDF 頁數: {len(doc)}")

    # 提取第一頁
    page = doc[0]

    # 渲染為圖像 (300 DPI)
    mat = fitz.Matrix(300/72, 300/72)  # 300 DPI
    pix = page.get_pixmap(matrix=mat)

    # 轉換為 PIL Image
    img_data = pix.tobytes("png")
    from io import BytesIO
    pil_image = Image.open(BytesIO(img_data))

    print(f"📐 提取圖像尺寸: {pil_image.size[0]} x {pil_image.size[1]}")

    # 保存原始圖像（用於對比）
    original_bgr = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

    # 建立預處理器
    preprocessor = TranscriptPreprocessor(config)

    # 執行預處理
    start_time = time.time()
    processed, metadata = await preprocessor.preprocess(pil_image)
    end_time = time.time()

    print(f"\n📊 處理結果:")
    print(f"  ⏱️  處理時間: {metadata['processing_time_ms']:.2f} ms")
    print(f"  🖼️  輸出尺寸: {processed.shape[1]} x {processed.shape[0]}")
    print(f"  🎨 輸出格式: {processed.shape}")
    print(f"  📦 數據類型: {processed.dtype}")
    print(f"  📈 值範圍: [{np.min(processed)}, {np.max(processed)}]")

    print(f"\n🔧 應用的處理步驟:")
    print(f"  ✓ 浮水印移除: {'是' if metadata['watermark_removed'] else '否'}")
    print(f"  ✓ 二值化: {'是' if metadata['binarization_applied'] else '否'}")
    if metadata.get('binarization_applied'):
        print(f"    方法: {metadata.get('binarization_method', 'N/A')}")

    # 保存處理後的圖像
    output_dir = project_root / "data" / "processed"
    output_dir.mkdir(exist_ok=True)

    # 保存處理後的圖像（使用智能壓縮）
    file_stem = Path(pdf_path).stem
    processed_path = output_dir / f"{file_stem}_page1_processed.png"
    final_processed_path, processed_size = save_image_smart(
        processed,
        str(processed_path),
        max_size_mb=4.5,
        prefer_png=True  # 處理後的圖優先使用 PNG
    )
    print(f"\n✅ 處理後圖像已保存: {final_processed_path} ({processed_size:.2f} MB)")

    # 保存對比圖
    comparison_path = output_dir / f"{file_stem}_page1_comparison.png"
    save_comparison_image(original_bgr, processed, str(comparison_path))

    doc.close()

    return processed, metadata


async def main():
    """主函數"""
    print("="*60)
    print("謄本文件預處理測試")
    print("="*60)

    # 配置 1: 完整預處理（移除浮水印 + 二值化 + 去噪）
    config_full = PreprocessConfig(
        enable_watermark_removal=True,
        enable_binarization=True,
        enable_denoising=True,
        binarization_method="gaussian",
        target_dpi=1500
    )

    # 配置 2: 僅移除浮水印
    config_watermark_only = PreprocessConfig(
        enable_watermark_removal=True,
        enable_binarization=False,
        enable_denoising=False,
        target_dpi=1500
    )

    # 配置 3: 僅二值化
    config_binarization_only = PreprocessConfig(
        enable_watermark_removal=False,
        enable_binarization=True,
        enable_denoising=False,
        binarization_method="sauvola",
        target_dpi=1500
    )

    data_dir = project_root / "data"

    # 測試文件
    test_files = [
        ("建物謄本.jpg", "image"),
        ("建物土地謄本-杭州南路一段.pdf", "pdf")
    ]

    # 測試配置
    test_configs = [
        ("完整預處理", config_full),
        ("僅移除浮水印", config_watermark_only),
        ("僅二值化(Sauvola)", config_binarization_only)
    ]

    for file_name, file_type in test_files:
        file_path = data_dir / file_name

        if not file_path.exists():
            print(f"⚠️  文件不存在: {file_path}")
            continue

        # 使用完整預處理配置測試
        print(f"\n\n{'#'*60}")
        print(f"測試文件: {file_name}")
        print(f"{'#'*60}")

        if file_type == "image":
            await process_image_file(str(file_path), config_full)
        else:
            await process_pdf_file(str(file_path), config_full)

    print(f"\n\n{'='*60}")
    print("✅ 所有測試完成！")
    print(f"{'='*60}")
    print(f"\n📁 處理結果保存在: {project_root / 'data' / 'processed'}")


if __name__ == "__main__":
    asyncio.run(main())
