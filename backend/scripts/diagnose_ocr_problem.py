"""
診斷 OCR 問題根源

找出為什麼準確率這麼低
"""

import asyncio
import sys
from pathlib import Path
from PIL import Image
import numpy as np
import cv2

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.lib.ocr_enhanced.preprocessor import TranscriptPreprocessor
from app.lib.ocr_enhanced.config import PreprocessConfig


async def diagnose_image_quality(image_path: str):
    """診斷圖片品質問題"""
    print("=" * 80)
    print(f"診斷圖片: {Path(image_path).name}")
    print("=" * 80)

    image = Image.open(image_path)
    img_array = np.array(image)

    # 轉換為 BGR
    if len(img_array.shape) == 3:
        img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
    else:
        img_bgr = img_array

    print(f"\n【基本資訊】")
    print(f"  尺寸: {image.size[0]} x {image.size[1]} px")
    print(f"  總像素: {image.size[0] * image.size[1]:,}")
    print(f"  色彩模式: {image.mode}")

    # 估算 DPI（假設是 A4 紙）
    # A4 = 210mm x 297mm
    width_mm = 210
    height_mm = 297
    estimated_dpi_w = (image.size[0] / width_mm) * 25.4
    estimated_dpi_h = (image.size[1] / height_mm) * 25.4
    avg_dpi = (estimated_dpi_w + estimated_dpi_h) / 2

    print(f"\n【解析度分析】")
    print(f"  估算 DPI (假設A4): {avg_dpi:.1f}")
    if avg_dpi < 200:
        print(f"  ❌ 警告: DPI 過低！建議 ≥300 DPI")
        print(f"  當前品質: 極差 - 無法清晰辨識小字")
    elif avg_dpi < 300:
        print(f"  ⚠️  警告: DPI 偏低，建議提升到 300+")
        print(f"  當前品質: 普通 - 可辨識但不理想")
    else:
        print(f"  ✅ DPI 良好")

    # 分析圖片清晰度（使用 Laplacian 方差）
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY) if len(img_bgr.shape) == 3 else img_bgr
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()

    print(f"\n【清晰度分析】")
    print(f"  Laplacian 方差: {laplacian_var:.2f}")
    if laplacian_var < 100:
        print(f"  ❌ 圖片模糊！建議重新掃描")
    elif laplacian_var < 500:
        print(f"  ⚠️  清晰度一般")
    else:
        print(f"  ✅ 圖片清晰")

    # 分析對比度
    min_val = gray.min()
    max_val = gray.max()
    contrast = max_val - min_val

    print(f"\n【對比度分析】")
    print(f"  灰階範圍: {min_val} - {max_val}")
    print(f"  對比度: {contrast}")
    if contrast < 100:
        print(f"  ❌ 對比度過低！")
    elif contrast < 150:
        print(f"  ⚠️  對比度偏低")
    else:
        print(f"  ✅ 對比度良好")

    # 分析浮水印干擾
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)

    # 檢測紅色區域
    lower_red1 = np.array([0, 30, 30])
    upper_red1 = np.array([15, 255, 255])
    lower_red2 = np.array([155, 30, 30])
    upper_red2 = np.array([179, 255, 255])

    mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
    red_mask = cv2.bitwise_or(mask1, mask2)

    red_pixels = np.sum(red_mask > 0)
    total_pixels = red_mask.size
    red_percentage = (red_pixels / total_pixels) * 100

    print(f"\n【浮水印干擾分析】")
    print(f"  紅色像素佔比: {red_percentage:.2f}%")
    if red_percentage > 10:
        print(f"  ❌ 嚴重浮水印干擾！")
    elif red_percentage > 3:
        print(f"  ⚠️  有浮水印干擾")
    else:
        print(f"  ✅ 浮水印干擾輕微")

    # 文字大小估算
    # 使用邊緣檢測找文字區域
    edges = cv2.Canny(gray, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if contours:
        heights = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if 5 < h < 100 and 5 < w < 200:  # 過濾明顯的雜訊
                heights.append(h)

        if heights:
            avg_text_height = np.median(heights)
            print(f"\n【文字大小分析】")
            print(f"  估算文字高度: {avg_text_height:.1f} px")
            if avg_text_height < 15:
                print(f"  ❌ 文字太小！OCR 難以辨識")
                print(f"  建議: 提升解析度或放大圖片")
            elif avg_text_height < 25:
                print(f"  ⚠️  文字偏小")
            else:
                print(f"  ✅ 文字大小適中")

    # 綜合評估
    print(f"\n{'='*80}")
    print("【診斷結論】")
    print("=" * 80)

    issues = []
    if avg_dpi < 200:
        issues.append("❌ 解析度過低（當前 ~{:.0f} DPI，建議 ≥300 DPI）".format(avg_dpi))
    if laplacian_var < 100:
        issues.append("❌ 圖片模糊")
    if contrast < 100:
        issues.append("❌ 對比度不足")
    if red_percentage > 10:
        issues.append("❌ 嚴重浮水印干擾")

    if issues:
        print("\n發現以下問題:")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")

        print(f"\n根本原因: 這張圖片品質太差，不適合直接 OCR！")
        print(f"           即使是最先進的 OCR 引擎也難以準確辨識。")
    else:
        print("\n✅ 圖片品質良好，問題可能出在 OCR 引擎配置")

    return {
        "dpi": avg_dpi,
        "sharpness": laplacian_var,
        "contrast": contrast,
        "watermark_pct": red_percentage
    }


async def test_extreme_preprocessing(image_path: str):
    """測試極端預處理策略"""
    print(f"\n\n{'='*80}")
    print("測試極端預處理策略")
    print("=" * 80)

    from paddleocr import PaddleOCR
    import time

    image = Image.open(image_path)

    strategies = [
        ("策略1: 極度放大 (5倍) + 浮水印移除", {
            "enable_watermark_removal": True,
            "enable_binarization": False,
            "enable_denoising": False,
            "target_dpi": 5000  # 極度放大
        }),
        ("策略2: 對比度增強 + 浮水印移除", "contrast"),
        ("策略3: Tesseract (可能更適合低品質圖片)", "tesseract"),
    ]

    ocr = PaddleOCR(use_angle_cls=True, lang='chinese_cht', use_gpu=False, show_log=False)

    for strategy_name, strategy_config in strategies:
        print(f"\n{'─'*80}")
        print(strategy_name)
        print(f"{'─'*80}")

        if strategy_name.startswith("策略1"):
            config = PreprocessConfig(**strategy_config)
            preprocessor = TranscriptPreprocessor(config)
            processed, _ = await preprocessor.preprocess(image)

            # 轉換為 RGB
            if len(processed.shape) == 2:
                img_rgb = cv2.cvtColor(processed, cv2.COLOR_GRAY2RGB)
            else:
                img_rgb = cv2.cvtColor(processed, cv2.COLOR_BGR2RGB)

        elif strategy_name.startswith("策略2"):
            # 對比度增強
            img_array = np.array(image)

            # 轉換為 LAB 色彩空間
            img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)

            # 分離通道
            l, a, b = cv2.split(lab)

            # 對 L 通道應用 CLAHE（對比度限制自適應直方圖均衡化）
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            l_enhanced = clahe.apply(l)

            # 合併通道
            lab_enhanced = cv2.merge([l_enhanced, a, b])

            # 轉回 BGR
            img_enhanced = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)

            # 移除浮水印
            config = PreprocessConfig(
                enable_watermark_removal=True,
                enable_binarization=False,
                enable_denoising=False,
                target_dpi=3000
            )
            preprocessor = TranscriptPreprocessor(config)

            # 轉換為 PIL Image
            img_pil = Image.fromarray(cv2.cvtColor(img_enhanced, cv2.COLOR_BGR2RGB))
            processed, _ = await preprocessor.preprocess(img_pil)

            # 轉換為 RGB
            if len(processed.shape) == 2:
                img_rgb = cv2.cvtColor(processed, cv2.COLOR_GRAY2RGB)
            else:
                img_rgb = cv2.cvtColor(processed, cv2.COLOR_BGR2RGB)

        elif strategy_name.startswith("策略3"):
            # 使用 Tesseract
            import pytesseract

            # 極度放大
            config = PreprocessConfig(
                enable_watermark_removal=True,
                enable_binarization=False,
                enable_denoising=False,
                target_dpi=5000
            )
            preprocessor = TranscriptPreprocessor(config)
            processed, _ = await preprocessor.preprocess(image)

            # 轉換為 PIL Image
            img_pil = Image.fromarray(processed)

            start_time = time.time()
            text = pytesseract.image_to_string(img_pil, lang="chi_tra", config="--psm 6")
            ocr_time = (time.time() - start_time) * 1000

            print(f"⏱️  OCR 時間: {ocr_time:.2f} ms")
            print(f"📝 辨識字符數: {len(text)}")
            print(f"\n文字預覽 (前 200 字):")
            print(text[:200])
            continue

        # PaddleOCR 辨識
        start_time = time.time()
        result = ocr.ocr(img_rgb, cls=True)
        ocr_time = (time.time() - start_time) * 1000

        text_lines = []
        if result and result[0]:
            for line in result[0]:
                text_content = line[1][0]
                text_lines.append(text_content)

        text = "\n".join(text_lines)

        print(f"⏱️  OCR 時間: {ocr_time:.2f} ms")
        print(f"📝 辨識字符數: {len(text)}")
        print(f"\n文字預覽 (前 200 字):")
        print(text[:200])


async def main():
    """主函數"""
    data_dir = project_root / "data"

    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 25 + "OCR 失敗診斷報告" + " " * 25 + "║")
    print("╚" + "=" * 78 + "╝")

    # 診斷兩個檔案
    test_files = [
        ("建物謄本.jpg", "低解析度 JPG"),
        ("建物土地謄本-杭州南路一段.pdf", "高解析度 PDF")
    ]

    for file_name, desc in test_files:
        file_path = data_dir / file_name

        if not file_path.exists():
            continue

        print(f"\n\n")
        print("┌" + "─" * 78 + "┐")
        print(f"│ 檔案: {file_name:<70} │")
        print(f"│ 類型: {desc:<70} │")
        print("└" + "─" * 78 + "┘")

        if file_name.endswith('.pdf'):
            # 提取 PDF 第一頁
            import fitz
            doc = fitz.open(str(file_path))
            page = doc[0]
            mat = fitz.Matrix(300/72, 300/72)
            pix = page.get_pixmap(matrix=mat)

            from io import BytesIO
            img_data = pix.tobytes("png")
            temp_path = data_dir / "temp_pdf_page.png"
            with open(temp_path, 'wb') as f:
                f.write(img_data)

            await diagnose_image_quality(str(temp_path))
            doc.close()
            temp_path.unlink()
        else:
            await diagnose_image_quality(str(file_path))

    # 測試極端策略（僅針對 JPG）
    jpg_path = data_dir / "建物謄本.jpg"
    if jpg_path.exists():
        await test_extreme_preprocessing(str(jpg_path))

    print(f"\n\n{'='*80}")
    print("診斷完成")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
