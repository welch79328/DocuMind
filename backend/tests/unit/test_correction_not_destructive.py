"""LLM 校正不得吃掉原文。

2026-09-03 線上實測:一份謄本的 p1,OCR 讀出 1600 字,校正後變成 **0 字**
——整頁文字靜默消失,而回應仍是 HTTP 200、llm_used=True、cost=$0.04。
對照該頁的文字層真值(1326 字),等於 CER 100%。

校正的職責是修正字元,不是刪除內容。輸出遠短於輸入時幾乎必然是
模型回了空值、拒絕、或截斷。

判準刻意寬鬆(只擋「明顯壞掉」),因為誤擋會讓正常校正失效。
實測正常校正的長度變化落在 -7% 到 +4%:p2 491→477、p3 1859→1735、p4 462→479。
"""

import pytest

from app.lib.ocr_enhanced.postprocessor import _reject_destructive_correction as guard

ORIGINAL = "土地登記第二類謄本" * 20   # 180 字


class TestBlocksDestructiveResults:
    @pytest.mark.parametrize("bad", ["", "   ", "\n", None, 123, [], {}])
    def test_empty_or_non_string_falls_back(self, bad):
        assert guard(ORIGINAL, bad) == ORIGINAL

    def test_the_real_defect_is_blocked(self):
        """線上實際發生的:1600 字 → 0 字"""
        original = "字" * 1600
        assert guard(original, "") == original

    def test_severely_truncated_falls_back(self):
        """疑似截斷:輸出不到原文一半"""
        assert guard(ORIGINAL, ORIGINAL[:50]) == ORIGINAL


class TestDoesNotBlockNormalCorrections:
    """誤擋會讓校正整個失效——這幾條是實測過的正常長度變化。"""

    @pytest.mark.parametrize("before,after", [
        (491, 477),    # p2 實測 −2.9%
        (1859, 1735),  # p3 實測 −6.7%
        (462, 479),    # p4 實測 +3.7%
    ])
    def test_measured_real_corrections_pass(self, before, after):
        original, corrected = "字" * before, "正" * after
        assert guard(original, corrected) == corrected

    def test_exactly_half_is_allowed(self):
        """界線是「短於一半」,剛好一半不擋——避免邊界誤判"""
        original = "字" * 100
        corrected = "正" * 50
        assert guard(original, corrected) == corrected

    def test_longer_output_passes(self):
        """校正可能補回 OCR 漏掉的字,變長是正常的"""
        assert guard(ORIGINAL, ORIGINAL + "補充") == ORIGINAL + "補充"

    def test_empty_original_does_not_crash(self):
        """OCR 本來就沒讀到東西時,不得因除以零之類的問題爆掉"""
        assert guard("", "校正後有字") == "校正後有字"
