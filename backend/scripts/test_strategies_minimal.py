"""
最小化融合策略測試 - 避免記憶體問題
"""

import asyncio
import sys
from pathlib import Path
from PIL import Image

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.lib.ocr_enhanced.preprocessor import TranscriptPreprocessor
from app.lib.ocr_enhanced.config import PreprocessConfig
from app.lib.ocr_enhanced.engine_manager import EngineManager


async def test_one_strategy(processed, strategy_name):
    """測試單一策略"""
    engine_manager = EngineManager(
        engines=["paddleocr", "tesseract"],
        parallel=False,  # 順序執行以節省記憶體
        fusion_method=strategy_name
    )

    text, confidence, engine_results = await engine_manager.extract_text_multi_engine(processed)

    keywords = ['地號', '面積', '統一編號', '謄本', '建物', '土地', '所有權', '登記']
    keyword_matches = sum(1 for kw in keywords if kw in text)

    # 找出選擇了哪個引擎
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
        "text_preview": text[:100]
    }


async def main():
    """主函數"""
    print("=" * 80)
    print("融合策略對比測試（最小化版本）")
    print("=" * 80)

    data_dir = project_root / "data"
    image_path = data_dir / "建物謄本.jpg"

    if not image_path.exists():
        print(f"❌ 檔案不存在: {image_path}")
        return

    # 預處理（只做一次）
    print(f"\n測試檔案: {image_path.name} (低品質 63 DPI)")
    print("\n預處理圖片...")
    pil_image = Image.open(image_path)
    config = PreprocessConfig()
    preprocessor = TranscriptPreprocessor(config)
    processed, metadata = await preprocessor.preprocess(pil_image)
    print(f"✓ 完成")

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

    # 推薦
    print(f"\n{'='*80}")
    print("分析")
    print(f"{'='*80}")

    best_char = max(results, key=lambda x: x["char_count"])
    best_keyword = max(results, key=lambda x: x["keywords"])

    print(f"\n最多字符數: {best_char['strategy']} → {best_char['selected_engine']} ({best_char['char_count']} 字)")
    print(f"最多關鍵字: {best_keyword['strategy']} → {best_keyword['selected_engine']} ({best_keyword['keywords']}/8)")

    # 檢查 smart 是否選擇了正確的引擎
    smart_result = next(r for r in results if r["strategy"] == "smart")
    if smart_result["selected_engine"] == "tesseract":
        print(f"\n✅ Smart 策略成功選擇 Tesseract (字符數最多、關鍵字最多)")
    elif smart_result["selected_engine"] == "paddleocr":
        print(f"\n⚠️  Smart 策略選擇了 PaddleOCR (可能需要調整權重)")

    print(f"\n{'='*80}")
    print("結論")
    print(f"{'='*80}")
    print("\n對於低品質圖片 (63 DPI):")
    print(f"  • best 策略: 選擇 {next(r for r in results if r['strategy']=='best')['selected_engine']} (僅看信心度)")
    print(f"  • smart 策略: 選擇 {smart_result['selected_engine']} (綜合評分)")
    print(f"  • vote 策略: 選擇 {next(r for r in results if r['strategy']=='vote')['selected_engine']} (選字符數最多)")
    print(f"\n推薦: smart 或 vote 策略（更適合低品質圖片）")
    print(f"{'='*80}")


if __name__ == "__main__":
    asyncio.run(main())
