"""
測試 LLM 後處理完整方案

規則修正 + LLM 智能修正
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


# Ground Truth（手動標註）
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
    print("LLM 後處理完整方案測試")
    print("規則修正 + LLM 智能修正")
    print("=" * 80)

    # 檢查 API 金鑰（優先使用 OpenAI，次選 Anthropic）
    openai_key = os.getenv("OPENAI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    if openai_key:
        llm_provider = "openai"
        print(f"\n✓ 偵測到 OpenAI API 金鑰，將使用 GPT-4o-mini")
    elif anthropic_key:
        llm_provider = "anthropic"
        print(f"\n✓ 偵測到 Anthropic API 金鑰，將使用 Claude Haiku")
    else:
        print("\n❌ 錯誤: 未設定 OPENAI_API_KEY 或 ANTHROPIC_API_KEY 環境變數")
        print("\n請在 .env 檔案中設定其中一個:")
        print("  OPENAI_API_KEY=your-api-key")
        print("  ANTHROPIC_API_KEY=your-api-key")
        return

    data_dir = project_root / "data"
    pdf_path = data_dir / "建物土地謄本-杭州南路一段.pdf"

    if not pdf_path.exists():
        print(f"❌ 檔案不存在: {pdf_path}")
        return

    # ========== 步驟 1: 提取 PDF ==========
    print(f"\n[1/5] 提取 PDF...")
    doc = fitz.open(str(pdf_path))
    page = doc[0]
    mat = fitz.Matrix(300/72, 300/72)
    pix = page.get_pixmap(matrix=mat)
    img_data = pix.tobytes("png")
    pil_image = Image.open(BytesIO(img_data))
    doc.close()
    print(f"  ✓ 完成")

    # ========== 步驟 2: 預處理 ==========
    print(f"\n[2/5] 預處理...")
    config = PreprocessConfig()
    preprocessor = TranscriptPreprocessor(config)
    processed, _ = await preprocessor.preprocess(pil_image)
    print(f"  ✓ 完成")

    # ========== 步驟 3: OCR ==========
    print(f"\n[3/5] OCR 辨識（Tesseract）...")
    engine_manager = EngineManager(engines=["tesseract"], parallel=False)
    raw_text, confidence, _ = await engine_manager.extract_text_multi_engine(processed)

    raw_portion = raw_text[:len(raw_text)//3]
    raw_acc = calculate_accuracy(GROUND_TRUTH, raw_portion)

    print(f"  ✓ 完成")
    print(f"     信心度: {confidence:.4f}")
    print(f"     準確率: {raw_acc['accuracy']:.2f}%")

    # ========== 步驟 4: 規則後處理 ==========
    print(f"\n[4/5] 規則後處理...")
    rule_postprocessor = TranscriptPostprocessor(
        enable_typo_fix=True,
        enable_format_correction=True,
        enable_llm=False
    )
    rule_text, rule_stats = await rule_postprocessor.postprocess(raw_text, confidence)

    rule_portion = rule_text[:len(rule_text)//3]
    rule_acc = calculate_accuracy(GROUND_TRUTH, rule_portion)

    print(f"  ✓ 完成")
    print(f"     錯別字修正: {rule_stats['typo_fixes']} 次")
    print(f"     準確率: {rule_acc['accuracy']:.2f}%")

    # ========== 步驟 5: LLM 後處理 ==========
    print(f"\n[5/5] LLM 智能後處理...")
    print(f"  策略: auto（根據信心度 {confidence:.4f} 決定）")

    if confidence < 0.6:
        print(f"  → 低信心度 (<0.6)，使用全文修正")
    elif confidence < 0.8:
        print(f"  → 中信心度 (0.6-0.8)，使用欄位修正")
    else:
        print(f"  → 高信心度 (>0.8)，不使用 LLM")

    llm_postprocessor = TranscriptPostprocessor(
        enable_typo_fix=True,
        enable_format_correction=True,
        enable_llm=True,
        llm_provider=llm_provider,  # 使用偵測到的提供商
        llm_strategy="auto"  # 智能策略
    )

    try:
        llm_text, llm_stats = await llm_postprocessor.postprocess(raw_text, confidence)

        llm_portion = llm_text[:len(llm_text)//3]
        llm_acc = calculate_accuracy(GROUND_TRUTH, llm_portion)

        print(f"  ✓ 完成")
        print(f"     LLM 使用: {'是' if llm_stats['llm_used'] else '否'}")
        print(f"     估計成本: ${llm_stats['llm_cost']:.6f}")
        print(f"     準確率: {llm_acc['accuracy']:.2f}%")

    except Exception as e:
        print(f"  ❌ 失敗: {e}")
        llm_text = rule_text
        llm_stats = rule_stats
        llm_acc = rule_acc

    # ========== 結果對比 ==========
    print(f"\n{'='*80}")
    print("準確率對比")
    print(f"{'='*80}")

    print(f"\n{'方案':<20} | {'準確率':>10} | {'提升':>10} | {'成本':>12}")
    print("-" * 80)
    print(f"{'原始 OCR':<20} | {raw_acc['accuracy']:>9.2f}% | {'-':>10} | {'$0':>12}")
    print(f"{'+ 規則後處理':<20} | {rule_acc['accuracy']:>9.2f}% | {rule_acc['accuracy']-raw_acc['accuracy']:>+9.2f}% | {'$0':>12}")

    if llm_stats.get('llm_used'):
        print(f"{'+ LLM 後處理':<20} | {llm_acc['accuracy']:>9.2f}% | {llm_acc['accuracy']-raw_acc['accuracy']:>+9.2f}% | ${llm_stats['llm_cost']:>11.6f}")
    else:
        print(f"{'+ LLM 後處理':<20} | {'-':>10} | {'-':>10} | {'未使用':>12}")

    # ========== 文字對比 ==========
    print(f"\n{'='*80}")
    print("文字對比（前 200 字）")
    print(f"{'='*80}")

    print(f"\n【Ground Truth】")
    print(GROUND_TRUTH[:200])

    print(f"\n【原始 OCR】")
    print(raw_portion[:200])

    print(f"\n【規則後處理】")
    print(rule_portion[:200])

    if llm_stats.get('llm_used'):
        print(f"\n【LLM 後處理】")
        print(llm_portion[:200])

    # ========== 最終結論 ==========
    print(f"\n{'='*80}")
    print("最終結論")
    print(f"{'='*80}")

    final_accuracy = llm_acc['accuracy'] if llm_stats.get('llm_used') else rule_acc['accuracy']
    improvement = final_accuracy - raw_acc['accuracy']

    if final_accuracy >= 75:
        print(f"\n🎉 成功！準確率達 {final_accuracy:.1f}%")
        print(f"   從 {raw_acc['accuracy']:.1f}% 提升到 {final_accuracy:.1f}% (+{improvement:.1f}%)")
    elif final_accuracy >= 65:
        print(f"\n✅ 良好！準確率 {final_accuracy:.1f}%")
        print(f"   提升了 {improvement:.1f} 個百分點")
    else:
        print(f"\n⚠️  仍需優化，準確率 {final_accuracy:.1f}%")

    if llm_stats.get('llm_used'):
        print(f"\n成本分析:")
        print(f"  • 單份文件成本: ${llm_stats['llm_cost']:.6f}")
        print(f"  • 月處理 1000 份: ${llm_stats['llm_cost'] * 1000:.2f}")
        print(f"  • 月處理 5000 份: ${llm_stats['llm_cost'] * 5000:.2f}")

    print(f"\n距離 95% 目標還差: {95 - final_accuracy:.1f} 百分點")

    print(f"\n{'='*80}")


if __name__ == "__main__":
    asyncio.run(main())
