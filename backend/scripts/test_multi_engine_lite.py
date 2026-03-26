"""
輕量級多引擎 OCR 融合測試

驗證任務 5.1, 5.2, 5.3 的實作（僅測試 JPG）
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


async def main():
    """主函數"""
    print("=" * 80)
    print("多引擎 OCR 融合測試 (輕量版)")
    print("Task 5.1 + 5.2 + 5.3 驗收")
    print("=" * 80)

    data_dir = project_root / "data"
    image_path = data_dir / "建物謄本.jpg"

    if not image_path.exists():
        print(f"❌ 檔案不存在: {image_path}")
        return

    print(f"\n測試檔案: {image_path.name}")

    # 讀取並預處理圖片
    print("\n[1/4] 預處理圖片...")
    pil_image = Image.open(image_path)
    config = PreprocessConfig()
    preprocessor = TranscriptPreprocessor(config)
    processed, metadata = await preprocessor.preprocess(pil_image)
    print(f"  ✓ 預處理完成 ({metadata['processing_time_ms']:.2f} ms)")

    # 測試 PaddleOCR
    print("\n[2/4] 測試 PaddleOCR...")
    engine_paddle = EngineManager(engines=["paddleocr"], parallel=False)
    start = time.time()
    text_paddle, conf_paddle, results_paddle = await engine_paddle.extract_text_multi_engine(processed)
    time_paddle = (time.time() - start) * 1000
    print(f"  ✓ 字符數: {len(text_paddle)}, 信心度: {conf_paddle:.4f}, 時間: {time_paddle:.2f} ms")

    # 測試 Tesseract
    print("\n[3/4] 測試 Tesseract...")
    engine_tess = EngineManager(engines=["tesseract"], parallel=False)
    start = time.time()
    text_tess, conf_tess, results_tess = await engine_tess.extract_text_multi_engine(processed)
    time_tess = (time.time() - start) * 1000
    print(f"  ✓ 字符數: {len(text_tess)}, 信心度: {conf_tess:.4f}, 時間: {time_tess:.2f} ms")

    # 測試多引擎融合
    print("\n[4/4] 測試多引擎融合（並行）...")
    engine_multi = EngineManager(engines=["paddleocr", "tesseract"], parallel=True, fusion_method="best")
    start = time.time()
    text_multi, conf_multi, results_multi = await engine_multi.extract_text_multi_engine(processed)
    time_multi = (time.time() - start) * 1000
    print(f"  ✓ 字符數: {len(text_multi)}, 信心度: {conf_multi:.4f}, 時間: {time_multi:.2f} ms")

    # 結果對比
    print("\n" + "=" * 80)
    print("結果對比")
    print("=" * 80)

    keywords = ['地號', '面積', '統一編號', '謄本', '建物', '土地', '所有權', '登記']

    paddle_kw = sum(1 for kw in keywords if kw in text_paddle)
    tess_kw = sum(1 for kw in keywords if kw in text_tess)
    multi_kw = sum(1 for kw in keywords if kw in text_multi)

    print(f"\n{'引擎':<15} | {'字符數':>8} | {'關鍵字':>8} | {'信心度':>10} | {'時間(ms)':>10}")
    print("-" * 80)
    print(f"{'PaddleOCR':<15} | {len(text_paddle):>8} | {paddle_kw:>2}/{len(keywords)} | {conf_paddle:>10.4f} | {time_paddle:>10.2f}")
    print(f"{'Tesseract':<15} | {len(text_tess):>8} | {tess_kw:>2}/{len(keywords)} | {conf_tess:>10.4f} | {time_tess:>10.2f}")
    print(f"{'多引擎融合':<15} | {len(text_multi):>8} | {multi_kw:>2}/{len(keywords)} | {conf_multi:>10.4f} | {time_multi:>10.2f}")

    # 顯示各引擎詳細結果
    print("\n各引擎詳細結果:")
    for result in results_multi:
        print(f"  • {result['engine']:12s}: 字符數={len(result['text']):4d}, "
              f"信心度={result['confidence']:.4f}, 時間={result['processing_time_ms']:.0f}ms")

    # 選擇了哪個引擎
    selected = max(results_multi, key=lambda r: r["confidence"])
    print(f"\n融合策略選擇: {selected['engine']} (信心度 {selected['confidence']:.4f})")

    # 性能分析
    print("\n" + "=" * 80)
    print("性能分析")
    print("=" * 80)

    theoretical_max = max(time_paddle, time_tess)
    speedup = (time_paddle + time_tess) / time_multi if time_multi > 0 else 0

    print(f"\nPaddleOCR: {time_paddle:.2f} ms")
    print(f"Tesseract: {time_tess:.2f} ms")
    print(f"並行執行: {time_multi:.2f} ms (理論最大: {theoretical_max:.2f} ms)")
    print(f"並行加速比: {speedup:.2f}x")

    if time_multi < theoretical_max * 1.5:
        print("✅ 並行執行效能達標 (< 最慢引擎 1.5 倍)")
    else:
        print("⚠️  並行執行效能未達標")

    # 驗收標準
    print("\n" + "=" * 80)
    print("驗收標準檢查")
    print("=" * 80)

    checks = [
        ("Task 5.1: PaddleOCR 適配器", len(text_paddle) > 0),
        ("Task 5.2: Tesseract 適配器", len(text_tess) > 0),
        ("Task 5.3: 多引擎融合", len(text_multi) > 0),
        ("並行處理實作", len(results_multi) == 2),
        ("信心度標準化 (0-1)", 0 <= conf_multi <= 1),
        ("融合策略 (best)", text_multi == selected["text"]),
    ]

    all_passed = True
    for name, passed in checks:
        status = "✅" if passed else "❌"
        print(f"  {status} {name}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 80)
    if all_passed:
        print("🎉 所有驗收標準通過！任務 5.1, 5.2, 5.3 完成")
    else:
        print("⚠️  部分驗收標準未通過")
    print("=" * 80)

    # 文字預覽
    print(f"\n融合結果預覽 (前 200 字):")
    print(text_multi[:200])


if __name__ == "__main__":
    asyncio.run(main())
