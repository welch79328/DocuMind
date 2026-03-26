"""
謄本 OCR 辨識效果測試

比較預處理前後的 OCR 辨識準確度
"""

import asyncio
import sys
import time
from pathlib import Path
from PIL import Image
import numpy as np
import cv2

# 添加專案根目錄到 Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.lib.ocr_enhanced.preprocessor import TranscriptPreprocessor
from app.lib.ocr_enhanced.config import PreprocessConfig


def save_comparison_result(original_text: str, enhanced_text: str, output_path: str):
    """保存 OCR 結果對比"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("OCR 辨識結果對比\n")
        f.write("=" * 80 + "\n\n")

        f.write("【原始圖片 OCR 結果】\n")
        f.write("-" * 80 + "\n")
        f.write(original_text)
        f.write("\n\n")

        f.write("【預處理後 OCR 結果】\n")
        f.write("-" * 80 + "\n")
        f.write(enhanced_text)
        f.write("\n\n")

        # 簡單統計
        f.write("=" * 80 + "\n")
        f.write("統計資訊\n")
        f.write("=" * 80 + "\n")
        f.write(f"原始字符數: {len(original_text)}\n")
        f.write(f"預處理後字符數: {len(enhanced_text)}\n")
        f.write(f"字符數增加: {len(enhanced_text) - len(original_text)}\n")

    print(f"✅ 對比結果已保存: {output_path}")


async def ocr_with_tesseract(image_path: str) -> tuple[str, float]:
    """使用 Tesseract OCR 辨識圖片"""
    try:
        import pytesseract
    except ImportError:
        raise ImportError("pytesseract 未安裝")

    # 讀取圖片
    if isinstance(image_path, str):
        image = Image.open(image_path)
    else:
        # 如果是 numpy array
        image = Image.fromarray(image_path)

    # 計時
    start_time = time.time()

    # OCR 辨識
    custom_config = r'--oem 1 --psm 6'
    text = pytesseract.image_to_string(image, lang="chi_tra", config=custom_config)

    # 計算處理時間
    processing_time = (time.time() - start_time) * 1000

    return text, processing_time


async def ocr_with_paddleocr(image_input) -> tuple[str, float]:
    """使用 PaddleOCR 辨識圖片"""
    try:
        from paddleocr import PaddleOCR
    except ImportError:
        raise ImportError("PaddleOCR 未安裝")

    # 初始化 PaddleOCR
    ocr = PaddleOCR(use_angle_cls=True, lang='chinese_cht', use_gpu=False, show_log=False)

    # 處理輸入
    if isinstance(image_input, str):
        # 文件路徑
        image = Image.open(image_input)
        img_array = np.array(image)
    elif isinstance(image_input, np.ndarray):
        # numpy array
        img_array = image_input
        # 確保是 RGB 格式
        if len(img_array.shape) == 2:
            # 灰階 -> RGB
            img_array = cv2.cvtColor(img_array, cv2.COLOR_GRAY2RGB)
        elif img_array.shape[2] == 3:
            # BGR -> RGB
            img_array = cv2.cvtColor(img_array, cv2.COLOR_BGR2RGB)
    else:
        # PIL Image
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


async def test_image_file(image_path: str, config: PreprocessConfig, ocr_engine: str = "paddleocr"):
    """測試圖片檔案的 OCR 效果"""
    print(f"\n{'='*80}")
    print(f"測試檔案: {Path(image_path).name}")
    print(f"OCR 引擎: {ocr_engine}")
    print(f"{'='*80}")

    # 讀取原始圖片
    pil_image = Image.open(image_path)
    original_size = pil_image.size
    print(f"\n📐 原始尺寸: {original_size[0]} x {original_size[1]}")

    # === 步驟 1: 原始圖片 OCR ===
    print(f"\n{'─'*80}")
    print("步驟 1: 原始圖片 OCR 辨識")
    print(f"{'─'*80}")

    if ocr_engine == "tesseract":
        original_text, original_time = await ocr_with_tesseract(image_path)
    else:
        original_text, original_time = await ocr_with_paddleocr(image_path)

    print(f"⏱️  處理時間: {original_time:.2f} ms")
    print(f"📝 辨識字符數: {len(original_text)}")
    print(f"📄 辨識結果預覽 (前 200 字):")
    print(original_text[:200])

    # === 步驟 2: 圖片預處理 ===
    print(f"\n{'─'*80}")
    print("步驟 2: 圖片預處理")
    print(f"{'─'*80}")

    preprocessor = TranscriptPreprocessor(config)
    processed, metadata = await preprocessor.preprocess(pil_image)

    print(f"⏱️  處理時間: {metadata['processing_time_ms']:.2f} ms")
    print(f"🖼️  輸出尺寸: {processed.shape[1]} x {processed.shape[0]}")
    print(f"✓ 浮水印移除: {'是' if metadata['watermark_removed'] else '否'}")
    print(f"✓ 二值化: {'是' if metadata['binarization_applied'] else '否'}")
    if metadata.get('binarization_applied'):
        print(f"  方法: {metadata.get('binarization_method', 'N/A')}")

    # === 步驟 3: 預處理後圖片 OCR ===
    print(f"\n{'─'*80}")
    print("步驟 3: 預處理後圖片 OCR 辨識")
    print(f"{'─'*80}")

    if ocr_engine == "tesseract":
        enhanced_text, enhanced_time = await ocr_with_tesseract(processed)
    else:
        enhanced_text, enhanced_time = await ocr_with_paddleocr(processed)

    print(f"⏱️  處理時間: {enhanced_time:.2f} ms")
    print(f"📝 辨識字符數: {len(enhanced_text)}")
    print(f"📄 辨識結果預覽 (前 200 字):")
    print(enhanced_text[:200])

    # === 步驟 4: 結果對比分析 ===
    print(f"\n{'='*80}")
    print("結果對比分析")
    print(f"{'='*80}")

    # 字符數對比
    char_diff = len(enhanced_text) - len(original_text)
    char_diff_pct = (char_diff / len(original_text) * 100) if len(original_text) > 0 else 0

    print(f"\n📊 字符數對比:")
    print(f"  原始: {len(original_text)} 字符")
    print(f"  預處理後: {len(enhanced_text)} 字符")
    print(f"  差異: {char_diff:+d} 字符 ({char_diff_pct:+.1f}%)")

    # 處理時間對比
    total_enhanced_time = metadata['processing_time_ms'] + enhanced_time
    time_overhead = total_enhanced_time - original_time
    time_overhead_pct = (time_overhead / original_time * 100) if original_time > 0 else 0

    print(f"\n⏱️  處理時間對比:")
    print(f"  原始 OCR: {original_time:.2f} ms")
    print(f"  預處理: {metadata['processing_time_ms']:.2f} ms")
    print(f"  預處理後 OCR: {enhanced_time:.2f} ms")
    print(f"  總時間: {total_enhanced_time:.2f} ms")
    print(f"  時間開銷: {time_overhead:+.2f} ms ({time_overhead_pct:+.1f}%)")

    # 關鍵字檢測
    keywords = ['地號', '面積', '統一編號', '謄本', '建物', '土地', '所有權', '登記']

    original_keywords = sum(1 for kw in keywords if kw in original_text)
    enhanced_keywords = sum(1 for kw in keywords if kw in enhanced_text)

    print(f"\n🔍 關鍵字檢測 ({len(keywords)} 個關鍵字):")
    print(f"  原始辨識到: {original_keywords}/{len(keywords)}")
    print(f"  預處理後辨識到: {enhanced_keywords}/{len(keywords)}")

    # 保存對比結果
    output_dir = project_root / "data" / "ocr_results"
    output_dir.mkdir(exist_ok=True, parents=True)

    file_stem = Path(image_path).stem
    comparison_file = output_dir / f"{file_stem}_{ocr_engine}_comparison.txt"
    save_comparison_result(original_text, enhanced_text, str(comparison_file))

    # 返回統計數據
    return {
        "file": Path(image_path).name,
        "original_chars": len(original_text),
        "enhanced_chars": len(enhanced_text),
        "char_diff": char_diff,
        "char_diff_pct": char_diff_pct,
        "original_time": original_time,
        "preprocessing_time": metadata['processing_time_ms'],
        "enhanced_ocr_time": enhanced_time,
        "total_enhanced_time": total_enhanced_time,
        "time_overhead": time_overhead,
        "time_overhead_pct": time_overhead_pct,
        "original_keywords": original_keywords,
        "enhanced_keywords": enhanced_keywords,
        "watermark_removed": metadata['watermark_removed'],
        "binarization_method": metadata.get('binarization_method', 'N/A')
    }


async def test_pdf_file(pdf_path: str, config: PreprocessConfig, ocr_engine: str = "paddleocr"):
    """測試 PDF 檔案的 OCR 效果（僅測試第一頁）"""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print("❌ 錯誤: 需要安裝 PyMuPDF")
        print("   請執行: pip install PyMuPDF")
        return None

    print(f"\n{'='*80}")
    print(f"測試 PDF: {Path(pdf_path).name} (第一頁)")
    print(f"OCR 引擎: {ocr_engine}")
    print(f"{'='*80}")

    # 打開 PDF 並提取第一頁為圖片
    doc = fitz.open(pdf_path)
    page = doc[0]

    # 渲染為圖像 (300 DPI)
    mat = fitz.Matrix(300/72, 300/72)
    pix = page.get_pixmap(matrix=mat)

    # 轉換為 PIL Image
    from io import BytesIO
    img_data = pix.tobytes("png")
    pil_image = Image.open(BytesIO(img_data))

    print(f"\n📐 提取圖像尺寸: {pil_image.size[0]} x {pil_image.size[1]}")

    # 轉換為 numpy array
    original_array = np.array(pil_image)

    # === 步驟 1: 原始圖片 OCR ===
    print(f"\n{'─'*80}")
    print("步驟 1: 原始圖片 OCR 辨識")
    print(f"{'─'*80}")

    if ocr_engine == "tesseract":
        original_text, original_time = await ocr_with_tesseract(pil_image)
    else:
        original_text, original_time = await ocr_with_paddleocr(original_array)

    print(f"⏱️  處理時間: {original_time:.2f} ms")
    print(f"📝 辨識字符數: {len(original_text)}")
    print(f"📄 辨識結果預覽 (前 200 字):")
    print(original_text[:200])

    # === 步驟 2: 圖片預處理 ===
    print(f"\n{'─'*80}")
    print("步驟 2: 圖片預處理")
    print(f"{'─'*80}")

    preprocessor = TranscriptPreprocessor(config)
    processed, metadata = await preprocessor.preprocess(pil_image)

    print(f"⏱️  處理時間: {metadata['processing_time_ms']:.2f} ms")
    print(f"🖼️  輸出尺寸: {processed.shape[1]} x {processed.shape[0]}")
    print(f"✓ 浮水印移除: {'是' if metadata['watermark_removed'] else '否'}")
    print(f"✓ 二值化: {'是' if metadata['binarization_applied'] else '否'}")

    # === 步驟 3: 預處理後圖片 OCR ===
    print(f"\n{'─'*80}")
    print("步驟 3: 預處理後圖片 OCR 辨識")
    print(f"{'─'*80}")

    if ocr_engine == "tesseract":
        enhanced_text, enhanced_time = await ocr_with_tesseract(processed)
    else:
        enhanced_text, enhanced_time = await ocr_with_paddleocr(processed)

    print(f"⏱️  處理時間: {enhanced_time:.2f} ms")
    print(f"📝 辨識字符數: {len(enhanced_text)}")
    print(f"📄 辨識結果預覽 (前 200 字):")
    print(enhanced_text[:200])

    # === 步驟 4: 結果對比分析 ===
    print(f"\n{'='*80}")
    print("結果對比分析")
    print(f"{'='*80}")

    # 字符數對比
    char_diff = len(enhanced_text) - len(original_text)
    char_diff_pct = (char_diff / len(original_text) * 100) if len(original_text) > 0 else 0

    print(f"\n📊 字符數對比:")
    print(f"  原始: {len(original_text)} 字符")
    print(f"  預處理後: {len(enhanced_text)} 字符")
    print(f"  差異: {char_diff:+d} 字符 ({char_diff_pct:+.1f}%)")

    # 處理時間對比
    total_enhanced_time = metadata['processing_time_ms'] + enhanced_time
    time_overhead = total_enhanced_time - original_time
    time_overhead_pct = (time_overhead / original_time * 100) if original_time > 0 else 0

    print(f"\n⏱️  處理時間對比:")
    print(f"  原始 OCR: {original_time:.2f} ms")
    print(f"  預處理: {metadata['processing_time_ms']:.2f} ms")
    print(f"  預處理後 OCR: {enhanced_time:.2f} ms")
    print(f"  總時間: {total_enhanced_time:.2f} ms")
    print(f"  時間開銷: {time_overhead:+.2f} ms ({time_overhead_pct:+.1f}%)")

    # 關鍵字檢測
    keywords = ['地號', '面積', '統一編號', '謄本', '建物', '土地', '所有權', '登記']

    original_keywords = sum(1 for kw in keywords if kw in original_text)
    enhanced_keywords = sum(1 for kw in keywords if kw in enhanced_text)

    print(f"\n🔍 關鍵字檢測 ({len(keywords)} 個關鍵字):")
    print(f"  原始辨識到: {original_keywords}/{len(keywords)}")
    print(f"  預處理後辨識到: {enhanced_keywords}/{len(keywords)}")

    # 保存對比結果
    output_dir = project_root / "data" / "ocr_results"
    output_dir.mkdir(exist_ok=True, parents=True)

    file_stem = Path(pdf_path).stem
    comparison_file = output_dir / f"{file_stem}_page1_{ocr_engine}_comparison.txt"
    save_comparison_result(original_text, enhanced_text, str(comparison_file))

    doc.close()

    # 返回統計數據
    return {
        "file": Path(pdf_path).name + " (第一頁)",
        "original_chars": len(original_text),
        "enhanced_chars": len(enhanced_text),
        "char_diff": char_diff,
        "char_diff_pct": char_diff_pct,
        "original_time": original_time,
        "preprocessing_time": metadata['processing_time_ms'],
        "enhanced_ocr_time": enhanced_time,
        "total_enhanced_time": total_enhanced_time,
        "time_overhead": time_overhead,
        "time_overhead_pct": time_overhead_pct,
        "original_keywords": original_keywords,
        "enhanced_keywords": enhanced_keywords,
        "watermark_removed": metadata['watermark_removed'],
        "binarization_method": metadata.get('binarization_method', 'N/A')
    }


async def main():
    """主函數"""
    print("=" * 80)
    print("謄本 OCR 辨識效果測試")
    print("=" * 80)

    # 預處理配置
    config = PreprocessConfig(
        enable_watermark_removal=True,
        enable_binarization=True,
        enable_denoising=True,
        binarization_method="gaussian",
        target_dpi=1500
    )

    # OCR 引擎選擇
    ocr_engine = "paddleocr"  # 可選: "paddleocr" 或 "tesseract"

    data_dir = project_root / "data"

    # 測試檔案
    test_files = [
        ("建物謄本.jpg", "image"),
        ("建物土地謄本-杭州南路一段.pdf", "pdf")
    ]

    results = []

    for file_name, file_type in test_files:
        file_path = data_dir / file_name

        if not file_path.exists():
            print(f"\n⚠️  檔案不存在: {file_path}")
            continue

        try:
            if file_type == "image":
                result = await test_image_file(str(file_path), config, ocr_engine)
            else:
                result = await test_pdf_file(str(file_path), config, ocr_engine)

            if result:
                results.append(result)
        except Exception as e:
            print(f"\n❌ 測試失敗: {e}")
            import traceback
            traceback.print_exc()

    # 生成總結報告
    if results:
        print(f"\n\n{'='*80}")
        print("總結報告")
        print(f"{'='*80}")

        for result in results:
            print(f"\n📄 {result['file']}")
            print(f"  字符數提升: {result['char_diff']:+d} ({result['char_diff_pct']:+.1f}%)")
            print(f"  關鍵字提升: {result['enhanced_keywords'] - result['original_keywords']:+d}")
            print(f"  時間開銷: {result['time_overhead']:+.2f} ms ({result['time_overhead_pct']:+.1f}%)")
            print(f"  預處理: 浮水印移除={result['watermark_removed']}, 二值化={result['binarization_method']}")

    print(f"\n\n{'='*80}")
    print("✅ 所有測試完成！")
    print(f"{'='*80}")
    print(f"\n📁 OCR 結果保存在: {project_root / 'data' / 'ocr_results'}")


if __name__ == "__main__":
    asyncio.run(main())
