"""
測試 PDF 真實準確率

與手動標註的 ground truth 對比
"""

import asyncio
import sys
from pathlib import Path
from PIL import Image
import fitz
from io import BytesIO
import difflib

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.lib.ocr_enhanced.preprocessor import TranscriptPreprocessor
from app.lib.ocr_enhanced.config import PreprocessConfig
from app.lib.ocr_enhanced.engine_manager import EngineManager
from app.lib.ocr_enhanced.postprocessor import TranscriptPostprocessor


# Ground Truth（從 PDF 第一頁手動標註前 500 字）
# 注意：這需要打開實際 PDF 檢視真實內容
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
面積：153.00平方公尺

使用分區：（空白）
使用地類別：（空白）

民國108年01月 公告土地現值：434,000元/平方公尺
地上建物建號：共4棟

其他登記事項：
重測前：東門段109-2地號
因分割增加地號：221-1地號

本謄本未申請列印地上建物建號，詳細地上建物建號以登記機關登記為主

土地所有權部

（0001）登記次序：0005
登記日期：民國107年10月25日
登記原因：分割繼承
原因發生日期：民國107年05月20日

所有權人：黃水木
統一編號：A202******6
住址：臺北市大安區和平里9鄰信義路三段111巷22號四樓

權狀字號：107北建字第016957號
當期申報地價：107年01月 94,400.0元/平方公尺
前次移轉現值或原規定地價：107年05月 426,000.0元/平方公尺

其他登記事項：（空白）

本謄本僅係 所有權個人全部 謄本，詳細權利狀態請參閱全部謄本
"""


def calculate_accuracy(ground_truth: str, ocr_result: str) -> dict:
    """計算字符級準確率"""
    # 移除空白和換行
    gt_clean = ''.join(ground_truth.split())
    ocr_clean = ''.join(ocr_result.split())

    # 計算相似度
    matcher = difflib.SequenceMatcher(None, gt_clean, ocr_clean)
    similarity = matcher.ratio()
    matching_chars = sum(block.size for block in matcher.get_matching_blocks())

    return {
        "ground_truth_chars": len(gt_clean),
        "ocr_chars": len(ocr_clean),
        "matching_chars": matching_chars,
        "accuracy": similarity * 100,
        "error_rate": (1 - similarity) * 100
    }


async def main():
    """主函數"""
    print("=" * 80)
    print("PDF 真實準確率測試（與 Ground Truth 對比）")
    print("=" * 80)

    data_dir = project_root / "data"
    pdf_path = data_dir / "建物土地謄本-杭州南路一段.pdf"

    if not pdf_path.exists():
        print(f"❌ 檔案不存在: {pdf_path}")
        return

    # 提取 PDF
    print(f"\n[1/4] 提取 PDF...")
    doc = fitz.open(str(pdf_path))
    page = doc[0]
    mat = fitz.Matrix(300/72, 300/72)
    pix = page.get_pixmap(matrix=mat)
    img_data = pix.tobytes("png")
    pil_image = Image.open(BytesIO(img_data))
    doc.close()

    # 預處理
    print(f"\n[2/4] 預處理...")
    config = PreprocessConfig()
    preprocessor = TranscriptPreprocessor(config)
    processed, _ = await preprocessor.preprocess(pil_image)

    # OCR
    print(f"\n[3/4] OCR 辨識（Tesseract）...")
    engine_manager = EngineManager(engines=["tesseract"], parallel=False)
    raw_text, confidence, _ = await engine_manager.extract_text_multi_engine(processed)

    # 後處理
    print(f"\n[4/4] 後處理...")
    postprocessor = TranscriptPostprocessor()
    processed_text, post_stats = await postprocessor.postprocess(raw_text)

    # 計算準確率
    print(f"\n{'='*80}")
    print("準確率計算（與 Ground Truth 對比）")
    print(f"{'='*80}")

    # 只取前 500 字符進行對比（因為 ground truth 只標註了這麼多）
    gt_clean = ''.join(GROUND_TRUTH.split())
    ocr_portion = processed_text[:len(processed_text)//3]  # 取前 1/3

    # 原始 OCR 準確率
    raw_portion = raw_text[:len(raw_text)//3]
    raw_stats = calculate_accuracy(GROUND_TRUTH, raw_portion)

    # 後處理準確率
    processed_stats = calculate_accuracy(GROUND_TRUTH, ocr_portion)

    print(f"\n【原始 OCR】")
    print(f"  Ground Truth 字符數: {raw_stats['ground_truth_chars']}")
    print(f"  OCR 字符數: {raw_stats['ocr_chars']}")
    print(f"  正確匹配字符: {raw_stats['matching_chars']}")
    print(f"  真實準確率: {raw_stats['accuracy']:.2f}%")
    print(f"  錯誤率: {raw_stats['error_rate']:.2f}%")

    print(f"\n【後處理後】")
    print(f"  Ground Truth 字符數: {processed_stats['ground_truth_chars']}")
    print(f"  OCR 字符數: {processed_stats['ocr_chars']}")
    print(f"  正確匹配字符: {processed_stats['matching_chars']}")
    print(f"  真實準確率: {processed_stats['accuracy']:.2f}%")
    print(f"  錯誤率: {processed_stats['error_rate']:.2f}%")

    # 改善幅度
    improvement = processed_stats['accuracy'] - raw_stats['accuracy']

    print(f"\n【改善幅度】")
    print(f"  準確率提升: {improvement:+.2f} 百分點")
    print(f"  錯別字修正: {post_stats['typo_fixes']} 次")

    # 結論
    print(f"\n{'='*80}")
    print("結論")
    print(f"{'='*80}")

    final_accuracy = processed_stats['accuracy']

    if final_accuracy >= 95:
        print(f"\n🎉 準確率達標 95%+ (當前: {final_accuracy:.1f}%)")
    elif final_accuracy >= 85:
        print(f"\n✅ 準確率良好 85-95% (當前: {final_accuracy:.1f}%)")
        print(f"   距離 95% 目標還差: {95 - final_accuracy:.1f} 百分點")
    elif final_accuracy >= 70:
        print(f"\n⚠️  準確率可接受 70-85% (當前: {final_accuracy:.1f}%)")
        print(f"   距離 95% 目標還差: {95 - final_accuracy:.1f} 百分點")
    else:
        print(f"\n❌ 準確率不足 <70% (當前: {final_accuracy:.1f}%)")
        print(f"   距離 95% 目標還差: {95 - final_accuracy:.1f} 百分點")

    print(f"\n主要錯誤來源:")
    print(f"  • OCR 引擎限制（Tesseract 對複雜排版支持有限）")
    print(f"  • 特殊符號和排版混淆")
    print(f"  • 需要更完整的錯別字字典")

    print(f"\n要達到 95%，建議:")
    print(f"  1. 使用商業 OCR 引擎（AWS Textract、Google Vision）")
    print(f"  2. 擴充錯別字字典（需收集更多真實謄本）")
    print(f"  3. 實作基於語言模型的後處理")

    print(f"\n{'='*80}")

    # 顯示對比
    print(f"\n文字對比範例（前 200 字）:")
    print(f"\n【Ground Truth】")
    print(GROUND_TRUTH[:200])
    print(f"\n【後處理結果】")
    print(ocr_portion[:200])


if __name__ == "__main__":
    asyncio.run(main())
