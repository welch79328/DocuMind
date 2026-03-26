"""
計算 OCR 真實準確率

手動標註 ground truth 並與 OCR 結果對比
"""

import difflib
from pathlib import Path

# 手動標註的 Ground Truth（從圖片上看到的實際內容）
GROUND_TRUTH = """建物登記第二類謄本（建號全部）
三重區文化北段 01391-000建號

列印時間：民國111年09月26日13時00分
頁次：1

本謄本係網路申領之電子謄本，由臺北智能自行列印
本種類碼：GN2D7JC6FQ3
請至 https://ep.land.nat.gov.tw查驗本謄本之正確性
其他登記事項：第307187號
資料管轄機關：臺北市建成地政事務所 謄本核發機關：臺北市建成地政事務所

******************** 建物標示部 ********************

登記日期：民國087年10月10日                    登記原因：建築改良物所有權第一次登記
建物門牌：無編釘門牌 0931-0000 0932-0000 0933-0000 0934-0000
主要用途：住宅
主要建材：
層 次：10層
建築完成日期：民國094年10月01日
其他登記事項：（一般登記事項）登記原因：增建・增建面積：地面層6 2 - 1 9平方公
          尺。增建日期：***年**月**日。登記日期：民國1 0 0 0 5 - 0 0 0建號

******************** 建物所有權部 ********************

（0001）登記次序：0003
登記日期：民國105年10月20日                    登記原因：買賣
原因發生日期：民國105年10月05日
所有權人：***
統一編號：C1********
住 址：臺北市***區***路***巷***號***樓之***號之1 1 9 0 7 2 1 5號
權利範圍：1 0 5 平方公尺第0 1 2 4 1 2號
建物坪數標示部登記次序：0003-000
其他登記事項：（空白）

（0002）登記次序：0004
登記日期：民國105年10月20日                    登記原因：買賣
原因發生日期：民國105年10月05日
所有權人：***
統一編號：C2********
住 址：臺北市***區***路***巷***號***樓之***號之1 1 9 0 7 2 1 5號
權利範圍：1 0 5 平方公尺第0 1 2 4 1 3號
建物坪數標示部登記次序：0003-000
其他登記事項：（空白）

（0003）登記次序：0005
登記日期：民國105年10月20日                    登記原因：買賣
原因發生日期：民國105年10月05日
所有權人：***
統一編號：C1********
住 址：臺北市***區***路***巷***號***樓之2 1號宏路段7 5 1 0 3號七十二號之二
權利範圍：******3.5之2 1**********
建物坪數標示部登記次序：1 0 5 平方公尺第0 1 2 4 1 4號
其他登記事項：（空白）

******************** 建物他項權利部 ********************
"""

# OCR 預處理後的結果
OCR_RESULT = """01391-0003
ot香驗本樁本正籍性
建新北市星年地事播所
09凈1車0站00
屆面批
基樂完我日批
記原因日嫌班埔建前面私出地面店日2活現9平方基
華物有部
民國在心時年北月0日
度智仁畢工的鄰仁二路1
10巷731
5號
E
電012412號
蛋記原因
民國在心華1的月的時日
華在二點1
年英國年有日
藍記原因
民購北5年北月心8
宇帶02414號
建物他預耀利部"""

# OCR 原始結果
OCR_ORIGINAL = """（種主部
是年於
種物標不部
09$1-0000
3932-0000
民國心華年心是的式其
建物所有部
18巷7室15號
年北的月型的日
良爾年功月的日
華隆市七寧區智仁平士日鄰七二路工1
第的
國在西年本的月包部日
1捲子號二十三樓力三
第心12414號
利部"""


def calculate_character_accuracy(ground_truth: str, ocr_result: str) -> dict:
    """
    計算字符級準確率

    使用編輯距離（Levenshtein distance）計算
    """
    # 移除空白和換行以便比較
    gt_clean = ''.join(ground_truth.split())
    ocr_clean = ''.join(ocr_result.split())

    # 計算編輯距離
    matcher = difflib.SequenceMatcher(None, gt_clean, ocr_clean)
    similarity = matcher.ratio()

    # 計算匹配的字符數
    matching_chars = sum(block.size for block in matcher.get_matching_blocks())

    return {
        "ground_truth_chars": len(gt_clean),
        "ocr_chars": len(ocr_clean),
        "matching_chars": matching_chars,
        "accuracy": similarity * 100,
        "error_rate": (1 - similarity) * 100
    }


def find_matching_keywords(ground_truth: str, ocr_result: str, keywords: list) -> dict:
    """檢查關鍵字是否正確辨識"""
    results = {}
    for keyword in keywords:
        in_gt = keyword in ground_truth
        in_ocr = keyword in ocr_result
        results[keyword] = {
            "in_ground_truth": in_gt,
            "in_ocr": in_ocr,
            "correct": in_gt and in_ocr
        }
    return results


def analyze_ocr_quality():
    """分析 OCR 品質"""
    print("=" * 80)
    print("OCR 辨識準確率分析")
    print("=" * 80)

    # 計算原始 OCR 的準確率
    print("\n【原始 OCR（無預處理）】")
    print("─" * 80)
    original_stats = calculate_character_accuracy(GROUND_TRUTH, OCR_ORIGINAL)
    print(f"Ground Truth 字符數: {original_stats['ground_truth_chars']}")
    print(f"OCR 辨識字符數: {original_stats['ocr_chars']}")
    print(f"正確匹配字符數: {original_stats['matching_chars']}")
    print(f"字符準確率: {original_stats['accuracy']:.2f}%")
    print(f"錯誤率: {original_stats['error_rate']:.2f}%")

    # 計算預處理後 OCR 的準確率
    print("\n【預處理後 OCR】")
    print("─" * 80)
    enhanced_stats = calculate_character_accuracy(GROUND_TRUTH, OCR_RESULT)
    print(f"Ground Truth 字符數: {enhanced_stats['ground_truth_chars']}")
    print(f"OCR 辨識字符數: {enhanced_stats['ocr_chars']}")
    print(f"正確匹配字符數: {enhanced_stats['matching_chars']}")
    print(f"字符準確率: {enhanced_stats['accuracy']:.2f}%")
    print(f"錯誤率: {enhanced_stats['error_rate']:.2f}%")

    # 計算改進幅度
    print("\n【改進幅度】")
    print("─" * 80)
    accuracy_improvement = enhanced_stats['accuracy'] - original_stats['accuracy']
    print(f"準確率提升: {accuracy_improvement:+.2f} 百分點")
    print(f"相對提升: {(accuracy_improvement / original_stats['accuracy'] * 100):+.1f}%")

    # 關鍵字檢測
    keywords = ['建物', '謄本', '登記', '地號', '面積', '所有權', '統一編號', '權利範圍']

    print("\n【關鍵字辨識】")
    print("─" * 80)

    original_kw = find_matching_keywords(GROUND_TRUTH, OCR_ORIGINAL, keywords)
    enhanced_kw = find_matching_keywords(GROUND_TRUTH, OCR_RESULT, keywords)

    print(f"{'關鍵字':<12} {'原始OCR':>10} {'預處理後':>10} {'改進':>8}")
    print("─" * 50)

    original_correct = 0
    enhanced_correct = 0

    for kw in keywords:
        orig_status = "✓" if original_kw[kw]['correct'] else "✗"
        enh_status = "✓" if enhanced_kw[kw]['correct'] else "✗"
        improved = ""

        if enhanced_kw[kw]['correct'] and not original_kw[kw]['correct']:
            improved = "⬆"
        elif original_kw[kw]['correct'] and not enhanced_kw[kw]['correct']:
            improved = "⬇"

        print(f"{kw:<12} {orig_status:>10} {enh_status:>10} {improved:>8}")

        if original_kw[kw]['correct']:
            original_correct += 1
        if enhanced_kw[kw]['correct']:
            enhanced_correct += 1

    print("─" * 50)
    print(f"{'正確數':<12} {original_correct:>10} {enhanced_correct:>10}")
    print(f"{'正確率':<12} {original_correct/len(keywords)*100:>9.1f}% {enhanced_correct/len(keywords)*100:>9.1f}%")

    # 分析主要錯誤類型
    print("\n【主要錯誤類型】")
    print("─" * 80)
    print("原始 OCR 錯誤:")
    print("  • 完全無法辨識標題和標點符號")
    print("  • 數字辨識錯誤 (0931 → 09$1)")
    print("  • 大量錯別字 (建物 → 種物)")
    print("  • 結構混亂，無法區分區塊")

    print("\n預處理後 OCR 錯誤:")
    print("  • 部分數字辨識錯誤 (01391-000 → 01391-0003)")
    print("  • 仍有錯別字 (驗證 → 香驗)")
    print("  • 複雜內容辨識不完整")
    print("  • 浮水印影響仍存在")

    # 估算距離完美辨識的差距
    print("\n【距離完美辨識的差距】")
    print("─" * 80)
    print(f"目前準確率: {enhanced_stats['accuracy']:.2f}%")
    print(f"目標準確率: 95.0% (業界標準)")
    print(f"差距: {95.0 - enhanced_stats['accuracy']:.2f} 百分點")
    print(f"錯誤字符數: {enhanced_stats['ground_truth_chars'] - enhanced_stats['matching_chars']}")
    print(f"需要修正的字符數: ~{int((1 - enhanced_stats['accuracy']/100) * enhanced_stats['ground_truth_chars'])}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    analyze_ocr_quality()
