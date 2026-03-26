"""
比較不同融合策略效果

測試 best, smart, vote 三種策略在不同品質圖片上的表現
"""

import asyncio
import sys
from pathlib import Path
from PIL import Image
import time

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.lib.ocr_enhanced.preprocessor import TranscriptPreprocessor
from app.lib.ocr_enhanced.config import PreprocessConfig
from app.lib.ocr_enhanced.engine_manager import EngineManager


async def test_strategies(image_path: str, image_desc: str):
    """測試所有融合策略"""
    print(f"\n{'='*80}")
    print(f"測試檔案: {Path(image_path).name}")
    print(f"描述: {image_desc}")
    print(f"{'='*80}")

    # 預處理圖片
    print("\n預處理圖片...")
    pil_image = Image.open(image_path)
    config = PreprocessConfig()
    preprocessor = TranscriptPreprocessor(config)
    processed, metadata = await preprocessor.preprocess(pil_image)
    print(f"✓ 完成 ({metadata['processing_time_ms']:.2f} ms)")

    strategies = ["best", "smart", "vote"]
    results = {}

    keywords = ['地號', '面積', '統一編號', '謄本', '建物', '土地', '所有權', '登記']

    # 測試每種策略
    for strategy in strategies:
        print(f"\n測試策略: {strategy}")

        engine_manager = EngineManager(
            engines=["paddleocr", "tesseract"],
            parallel=True,
            fusion_method=strategy
        )

        start = time.time()
        text, confidence, engine_results = await engine_manager.extract_text_multi_engine(processed)
        elapsed = (time.time() - start) * 1000

        keyword_matches = sum(1 for kw in keywords if kw in text)

        # 判斷選擇了哪個引擎
        selected_engine = "unknown"
        for r in engine_results:
            if r["text"] == text:
                selected_engine = r["engine"]
                break

        results[strategy] = {
            "text": text,
            "confidence": confidence,
            "char_count": len(text),
            "keywords": keyword_matches,
            "time_ms": elapsed,
            "selected_engine": selected_engine,
            "engine_results": engine_results
        }

        print(f"  ✓ 選擇: {selected_engine}")
        print(f"  ✓ 字符數: {len(text)}")
        print(f"  ✓ 關鍵字: {keyword_matches}/{len(keywords)}")
        print(f"  ✓ 信心度: {confidence:.4f}")

    # 結果對比
    print(f"\n{'='*80}")
    print("策略對比")
    print(f"{'='*80}")

    print(f"\n{'策略':<10} | {'選擇引擎':<12} | {'字符數':>8} | {'關鍵字':>8} | {'信心度':>10}")
    print("-" * 80)

    for strategy in strategies:
        r = results[strategy]
        print(f"{strategy:<10} | {r['selected_engine']:<12} | {r['char_count']:>8} | "
              f"{r['keywords']:>2}/{len(keywords)} | {r['confidence']:>10.4f}")

    # 推薦最佳策略
    print(f"\n{'='*80}")
    print("分析與推薦")
    print(f"{'='*80}")

    # 找出字符數最多的策略
    best_char_strategy = max(strategies, key=lambda s: results[s]["char_count"])
    # 找出關鍵字最多的策略
    best_keyword_strategy = max(strategies, key=lambda s: results[s]["keywords"])
    # 找出信心度最高的策略
    best_conf_strategy = max(strategies, key=lambda s: results[s]["confidence"])

    print(f"\n最多字符數: {best_char_strategy} ({results[best_char_strategy]['char_count']} 字)")
    print(f"最多關鍵字: {best_keyword_strategy} ({results[best_keyword_strategy]['keywords']}/{len(keywords)})")
    print(f"最高信心度: {best_conf_strategy} ({results[best_conf_strategy]['confidence']:.4f})")

    # 綜合推薦
    if best_char_strategy == best_keyword_strategy:
        print(f"\n🎯 推薦策略: {best_char_strategy} (字符數與關鍵字均最佳)")
    else:
        print(f"\n🎯 推薦策略: smart (綜合平衡)")

    # 顯示各引擎原始結果
    print(f"\n{'='*80}")
    print("各引擎原始結果")
    print(f"{'='*80}")

    # 使用第一個策略的 engine_results（都相同）
    for r in results["best"]["engine_results"]:
        kw_count = sum(1 for kw in keywords if kw in r["text"])
        print(f"\n{r['engine'].upper()}:")
        print(f"  字符數: {len(r['text'])}")
        print(f"  關鍵字: {kw_count}/{len(keywords)}")
        print(f"  信心度: {r['confidence']:.4f}")
        print(f"  時間: {r['processing_time_ms']:.0f} ms")

    return results


async def main():
    """主函數"""
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 24 + "融合策略對比測試" + " " * 24 + "║")
    print("╚" + "=" * 78 + "╝")

    data_dir = project_root / "data"

    test_files = [
        ("建物謄本.jpg", "低品質 JPG (63 DPI)"),
        ("建物土地謄本-杭州南路一段.pdf", "高品質 PDF (300 DPI)")
    ]

    all_results = {}

    for file_name, desc in test_files:
        file_path = data_dir / file_name

        if not file_path.exists():
            print(f"\n⚠️  檔案不存在: {file_path}")
            continue

        # PDF 需要先轉換
        if file_name.endswith('.pdf'):
            import fitz
            doc = fitz.open(str(file_path))
            page = doc[0]
            mat = fitz.Matrix(300/72, 300/72)
            pix = page.get_pixmap(matrix=mat)

            from io import BytesIO
            img_data = pix.tobytes("png")
            temp_path = data_dir / "temp_strategy_test.png"
            with open(temp_path, 'wb') as f:
                f.write(img_data)

            image_path = str(temp_path)
            doc.close()
        else:
            image_path = str(file_path)

        try:
            results = await test_strategies(image_path, desc)
            all_results[file_name] = results
        except Exception as e:
            print(f"\n❌ 測試失敗: {e}")
            import traceback
            traceback.print_exc()

        # 清理臨時檔案
        if file_name.endswith('.pdf'):
            temp_path.unlink()

    # 最終總結
    print(f"\n\n{'='*80}")
    print("最終總結")
    print(f"{'='*80}")

    for file_name, results in all_results.items():
        print(f"\n📄 {file_name}")

        # 找出最佳策略
        best_strategy = max(
            results.keys(),
            key=lambda s: (results[s]["keywords"], results[s]["char_count"])
        )

        print(f"  推薦策略: {best_strategy}")
        print(f"  選擇引擎: {results[best_strategy]['selected_engine']}")
        print(f"  字符數: {results[best_strategy]['char_count']}")
        print(f"  關鍵字: {results[best_strategy]['keywords']}/8")

    print(f"\n{'='*80}")
    print("結論")
    print(f"{'='*80}")
    print("\n✅ Smart 策略已實作完成")
    print("   - 綜合考慮字符數(40%)、關鍵字(35%)、信心度(25%)")
    print("   - 適應不同品質的圖片")
    print("   - 避免信心度高但辨識少的陷阱")
    print(f"\n{'='*80}")


if __name__ == "__main__":
    asyncio.run(main())
