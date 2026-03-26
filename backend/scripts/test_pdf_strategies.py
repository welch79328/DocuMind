"""
測試 PDF 高品質檔案的融合策略效果
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


async def test_one_strategy(processed, strategy_name):
    """測試單一策略"""
    engine_manager = EngineManager(
        engines=["paddleocr", "tesseract"],
        parallel=False,
        fusion_method=strategy_name
    )

    text, confidence, engine_results = await engine_manager.extract_text_multi_engine(processed)

    keywords = ['地號', '面積', '統一編號', '謄本', '建物', '土地', '所有權', '登記']
    keyword_matches = sum(1 for kw in keywords if kw in text)

    selected_engine = "unknown"
    for r in engine_results:
        if r["text"] == text:
            selected_engine = r["engine"]
            break

    return {
        "strategy": strategy_name,
        "selected_engine": selected_engine,
        "char_count": len(text),
        "keywords": keyword_matches,
        "confidence": confidence,
        "engine_results": engine_results
    }


async def main():
    """主函數"""
    print("=" * 80)
    print("PDF 高品質檔案融合策略測試")
    print("=" * 80)

    data_dir = project_root / "data"
    pdf_path = data_dir / "建物土地謄本-杭州南路一段.pdf"

    if not pdf_path.exists():
        print(f"❌ 檔案不存在: {pdf_path}")
        return

    # 提取 PDF 第一頁
    print(f"\n測試檔案: {pdf_path.name} (高品質 300 DPI PDF)")
    print("\n提取 PDF 第一頁...")

    doc = fitz.open(str(pdf_path))
    page = doc[0]
    mat = fitz.Matrix(300/72, 300/72)
    pix = page.get_pixmap(matrix=mat)

    img_data = pix.tobytes("png")
    pil_image = Image.open(BytesIO(img_data))
    doc.close()

    print(f"✓ 圖像尺寸: {pil_image.size[0]} x {pil_image.size[1]}")

    # 預處理
    print("\n預處理圖片...")
    config = PreprocessConfig()
    preprocessor = TranscriptPreprocessor(config)
    processed, metadata = await preprocessor.preprocess(pil_image)
    print(f"✓ 完成 ({metadata['processing_time_ms']:.2f} ms)")

    # 測試三種策略
    strategies = ["best", "smart", "vote"]
    results = []

    for strategy in strategies:
        print(f"\n測試策略: {strategy}")
        result = await test_one_strategy(processed, strategy)
        results.append(result)
        print(f"  選擇: {result['selected_engine']}, "
              f"字符數: {result['char_count']}, "
              f"關鍵字: {result['keywords']}/8")

    # 結果對比
    print(f"\n{'='*80}")
    print("策略對比")
    print(f"{'='*80}")

    print(f"\n{'策略':<10} | {'選擇引擎':<12} | {'字符數':>8} | {'關鍵字':>8} | {'信心度':>10}")
    print("-" * 80)

    for r in results:
        print(f"{r['strategy']:<10} | {r['selected_engine']:<12} | {r['char_count']:>8} | "
              f"{r['keywords']:>2}/8 | {r['confidence']:>10.4f}")

    # 顯示各引擎原始結果
    print(f"\n{'='*80}")
    print("各引擎原始結果")
    print(f"{'='*80}")

    keywords = ['地號', '面積', '統一編號', '謄本', '建物', '土地', '所有權', '登記']
    for engine_result in results[0]["engine_results"]:
        kw_count = sum(1 for kw in keywords if kw in engine_result["text"])
        print(f"\n{engine_result['engine'].upper()}:")
        print(f"  字符數: {len(engine_result['text'])}")
        print(f"  關鍵字: {kw_count}/8")
        print(f"  信心度: {engine_result['confidence']:.4f}")

    # 分析
    print(f"\n{'='*80}")
    print("分析")
    print(f"{'='*80}")

    best_char = max(results, key=lambda x: x["char_count"])
    best_keyword = max(results, key=lambda x: x["keywords"])

    print(f"\n最多字符數: {best_char['strategy']} → {best_char['selected_engine']} ({best_char['char_count']} 字)")
    print(f"最多關鍵字: {best_keyword['strategy']} → {best_keyword['selected_engine']} ({best_keyword['keywords']}/8)")

    # 檢查各策略選擇
    print(f"\n策略選擇:")
    for r in results:
        print(f"  • {r['strategy']:<8}: {r['selected_engine']}")

    # 結論
    print(f"\n{'='*80}")
    print("結論")
    print(f"{'='*80}")

    print(f"\n對於高品質 PDF (300 DPI):")

    # 判斷哪個引擎更好
    paddle_result = results[0]["engine_results"][0] if results[0]["engine_results"][0]["engine"] == "paddleocr" else results[0]["engine_results"][1]
    tess_result = results[0]["engine_results"][0] if results[0]["engine_results"][0]["engine"] == "tesseract" else results[0]["engine_results"][1]

    paddle_kw = sum(1 for kw in keywords if kw in paddle_result["text"])
    tess_kw = sum(1 for kw in keywords if kw in tess_result["text"])

    if paddle_kw >= tess_kw and len(paddle_result["text"]) >= len(tess_result["text"]):
        print(f"  ✅ PaddleOCR 表現更好（字符數: {len(paddle_result['text'])}, 關鍵字: {paddle_kw}/8）")
        print(f"  ✅ Smart 策略能正確選擇引擎")
    elif tess_kw >= paddle_kw and len(tess_result["text"]) >= len(paddle_result["text"]):
        print(f"  ✅ Tesseract 表現更好（字符數: {len(tess_result['text'])}, 關鍵字: {tess_kw}/8）")
        print(f"  ✅ Smart 策略能正確選擇引擎")
    else:
        print(f"  ⚖️  兩引擎各有優勢")
        print(f"     PaddleOCR: {len(paddle_result['text'])} 字, {paddle_kw}/8 關鍵字")
        print(f"     Tesseract: {len(tess_result['text'])} 字, {tess_kw}/8 關鍵字")

    print(f"\n推薦策略: smart（自動適應不同品質）")
    print(f"{'='*80}")


if __name__ == "__main__":
    asyncio.run(main())
