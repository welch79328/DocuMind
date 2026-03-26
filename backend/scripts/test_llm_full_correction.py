"""
測試 LLM 全文修正效果

強制使用 full 策略，測試 LLM 能否修正複雜錯誤
"""

import asyncio
import sys
from pathlib import Path
from PIL import Image
import fitz
from io import BytesIO
import difflib
import os

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.lib.ocr_enhanced.preprocessor import TranscriptPreprocessor
from app.lib.ocr_enhanced.config import PreprocessConfig
from app.lib.ocr_enhanced.engine_manager import EngineManager
from app.lib.ocr_enhanced.postprocessor import TranscriptPostprocessor


# Ground Truth
GROUND_TRUTH = """土地登記第三類謄本（所有權個人全部）
中正區中正段三小段 0221-0000 地號

列印時間：民國108年04月09日17時09分
頁次：1

本謄本係網路申領之電子謄本，由申請人自行列印
謄本種類碼：L944V64QT3，可至 https://ep.land.nat.gov.tw 查驗本謄本之正確性

建成地政事務所 主任 曾錫雄
建成電腦字第084946號

資料管轄機關：臺北市建成地政事務所
謄本核發機關：臺北市建成地政事務所

土地標示部

登記日期：民國075年05月27日
登記原因：鑑界分割
地目：建
面積：153.00平方公尺"""


def calculate_accuracy(ground_truth: str, ocr_result: str) -> dict:
    """計算準確率"""
    gt_clean = ''.join(ground_truth.split())
    ocr_clean = ''.join(ocr_result.split())

    matcher = difflib.SequenceMatcher(None, gt_clean, ocr_clean)
    similarity = matcher.ratio()

    return {
        "accuracy": similarity * 100,
        "error_rate": (1 - similarity) * 100
    }


async def main():
    """主函數"""
    print("=" * 80)
    print("LLM 全文修正測試")
    print("強制使用 'full' 策略，測試最大修正能力")
    print("=" * 80)

    # 檢查 API 金鑰
    openai_key = os.getenv("OPENAI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    if openai_key:
        llm_provider = "openai"
        print(f"\n✓ 使用 OpenAI GPT-4o-mini")
    elif anthropic_key:
        llm_provider = "anthropic"
        print(f"\n✓ 使用 Anthropic Claude Haiku")
    else:
        print("\n❌ 錯誤: 需要 OPENAI_API_KEY 或 ANTHROPIC_API_KEY")
        return

    data_dir = project_root / "data"
    pdf_path = data_dir / "建物土地謄本-杭州南路一段.pdf"

    if not pdf_path.exists():
        print(f"❌ 檔案不存在: {pdf_path}")
        return

    # ========== 步驟 1: 提取 PDF ==========
    print(f"\n[1/4] 提取 PDF...")
    doc = fitz.open(str(pdf_path))
    page = doc[0]
    mat = fitz.Matrix(300/72, 300/72)
    pix = page.get_pixmap(matrix=mat)
    img_data = pix.tobytes("png")
    pil_image = Image.open(BytesIO(img_data))
    doc.close()
    print(f"  ✓ 完成")

    # ========== 步驟 2: 預處理 ==========
    print(f"\n[2/4] 預處理...")
    config = PreprocessConfig()
    preprocessor = TranscriptPreprocessor(config)
    processed, _ = await preprocessor.preprocess(pil_image)
    print(f"  ✓ 完成")

    # ========== 步驟 3: OCR ==========
    print(f"\n[3/4] OCR 辨識（Tesseract）...")
    engine_manager = EngineManager(engines=["tesseract"], parallel=False)
    raw_text, confidence, _ = await engine_manager.extract_text_multi_engine(processed)

    raw_portion = raw_text[:len(raw_text)//3]
    raw_acc = calculate_accuracy(GROUND_TRUTH, raw_portion)

    print(f"  ✓ 完成")
    print(f"     信心度: {confidence:.4f}")
    print(f"     準確率: {raw_acc['accuracy']:.2f}%")

    # ========== 步驟 4: LLM 全文修正 ==========
    print(f"\n[4/4] LLM 全文修正...")
    print(f"  策略: full（無論信心度，強制全文修正）")

    llm_postprocessor = TranscriptPostprocessor(
        enable_typo_fix=True,
        enable_format_correction=True,
        enable_llm=True,
        llm_provider=llm_provider,
        llm_strategy="full"  # 強制全文修正
    )

    try:
        # 注意：即使 confidence 很高，也會使用全文修正（因為 strategy="full"）
        llm_text, llm_stats = await llm_postprocessor.postprocess(raw_text, confidence)

        llm_portion = llm_text[:len(llm_text)//3]
        llm_acc = calculate_accuracy(GROUND_TRUTH, llm_portion)

        print(f"  ✓ 完成")
        print(f"     LLM 使用: {'是' if llm_stats['llm_used'] else '否'}")
        print(f"     估計成本: ${llm_stats['llm_cost']:.6f}")
        print(f"     準確率: {llm_acc['accuracy']:.2f}%")

    except Exception as e:
        print(f"  ❌ 失敗: {e}")
        import traceback
        traceback.print_exc()
        return

    # ========== 結果對比 ==========
    print(f"\n{'='*80}")
    print("準確率對比")
    print(f"{'='*80}")

    print(f"\n{'方案':<20} | {'準確率':>10} | {'提升':>10} | {'成本':>12}")
    print("-" * 80)
    print(f"{'原始 OCR':<20} | {raw_acc['accuracy']:>9.2f}% | {'-':>10} | {'$0':>12}")
    print(f"{'+ LLM 全文修正':<20} | {llm_acc['accuracy']:>9.2f}% | {llm_acc['accuracy']-raw_acc['accuracy']:>+9.2f}% | ${llm_stats['llm_cost']:>11.6f}")

    # ========== 文字對比 ==========
    print(f"\n{'='*80}")
    print("文字對比（前 300 字）")
    print(f"{'='*80}")

    print(f"\n【Ground Truth】")
    print(GROUND_TRUTH[:300])

    print(f"\n【原始 OCR】")
    print(raw_portion[:300])

    print(f"\n【LLM 全文修正】")
    print(llm_portion[:300])

    # ========== 詳細錯誤分析 ==========
    print(f"\n{'='*80}")
    print("詳細錯誤對比")
    print(f"{'='*80}")

    # 顯示逐行對比
    gt_lines = GROUND_TRUTH.split('\n')[:5]
    raw_lines = raw_portion.split('\n')[:5]
    llm_lines = llm_portion.split('\n')[:5]

    for i, (gt, raw, llm) in enumerate(zip(gt_lines, raw_lines, llm_lines), 1):
        print(f"\n第 {i} 行:")
        print(f"  標準: {gt}")
        print(f"  原始: {raw}")
        print(f"  修正: {llm}")
        if gt.strip() == llm.strip():
            print(f"  ✅ 完全正確")
        elif gt.strip() in llm or llm.strip() in gt:
            print(f"  ⚠️  部分正確")
        else:
            print(f"  ❌ 仍有錯誤")

    # ========== 最終結論 ==========
    print(f"\n{'='*80}")
    print("最終結論")
    print(f"{'='*80}")

    improvement = llm_acc['accuracy'] - raw_acc['accuracy']

    if improvement >= 10:
        print(f"\n🎉 顯著提升！準確率提升 {improvement:.1f} 個百分點")
        print(f"   從 {raw_acc['accuracy']:.1f}% 提升到 {llm_acc['accuracy']:.1f}%")
    elif improvement >= 5:
        print(f"\n✅ 有效提升！準確率提升 {improvement:.1f} 個百分點")
    elif improvement >= 0:
        print(f"\n⚠️  提升有限，僅 {improvement:.1f} 個百分點")
    else:
        print(f"\n❌ 準確率下降 {abs(improvement):.1f} 個百分點")
        print(f"   可能是 LLM 過度修正")

    print(f"\n成本分析:")
    print(f"  • 單份文件: ${llm_stats['llm_cost']:.6f}")
    print(f"  • 月處理 1000 份: ${llm_stats['llm_cost'] * 1000:.2f}")
    print(f"  • 月處理 5000 份: ${llm_stats['llm_cost'] * 5000:.2f}")

    if llm_acc['accuracy'] < 85:
        print(f"\n建議:")
        print(f"  1. 優化 LLM Prompt（加入更多台灣地政術語範例）")
        print(f"  2. 使用更強的模型（GPT-4o 而非 GPT-4o-mini）")
        print(f"  3. 更換更好的 OCR 引擎（Textract、Google Vision）")

    print(f"\n{'='*80}")


if __name__ == "__main__":
    asyncio.run(main())
