"""共識信心度不得套用在 LLM 改過的值上。

## 這條防線在防什麼

共識(步驟 3b)算在**未經 LLM** 的候選上;LLM 全文校正(步驟 4)之後,
欄位值可能已經不是任何一個引擎讀到的東西。原本 `_apply_consensus` 只讀
`field_confidences`、不讀 `agreements`,於是:

    兩引擎都讀出 1,500  → 共識信心度 0.98
    LLM 校正把值改成 15,000
    最終信心度仍是高分 → 高於門檻 0.8 → **放行**

那正是需求 2 點名的「語法合法但數值錯誤」的靜默污染,也是整份規格最想擋的東西。

## 這條防線不能做的事

不能把「LLM 只是換了表示法」誤判成竄改。全形轉半形、補千分位、民國紀年換西元,
都是正規化差異而非改值——比對一律走 `values_agree`(共識判定 `agreed` 用的同一支),
下面的測試把這幾種都涵蓋了。
"""

import pytest

from app.config import settings
from app.lib.multi_type_ocr.processor import OcrDocumentProcessor as P

PENALTY = settings.OCR_CONSENSUS_DISAGREE_PENALTY
THRESHOLD = settings.OCR_QUALITY_THRESHOLD


def consensus(field, conf, engine_values, agreed=True):
    return {
        "field_confidences": {field: conf},
        "agreements": {
            field: {"value": next(iter(engine_values.values())),
                    "confidence": conf, "agreed": agreed,
                    "engine_values": engine_values},
        },
    }


class TestLlmAlteredValueLosesConsensusBacking:
    def test_altered_value_is_capped_at_penalty(self):
        """兩引擎都讀 1,500、LLM 改成 15,000 → 不得沿用 0.98"""
        data = {"contract_amount": "15,000",
                "field_confidences": {"contract_amount": 0.92}}
        out = P._apply_consensus(
            data, consensus("contract_amount", 0.98,
                            {"paddleocr": "1,500", "tesseract": "1,500"}))
        got = out["field_confidences"]["contract_amount"]
        assert got <= PENALTY, f"被 LLM 改過的值仍拿到 {got},未被壓低"

    def test_altered_value_is_actually_blocked(self):
        """壓低之後必須真的低於攔截門檻,否則等於沒擋"""
        data = {"contract_amount": "15,000",
                "field_confidences": {"contract_amount": 0.92}}
        out = P._apply_consensus(
            data, consensus("contract_amount", 0.98,
                            {"paddleocr": "1,500", "tesseract": "1,500"}))
        assert out["field_confidences"]["contract_amount"] < THRESHOLD

    def test_value_matching_one_engine_keeps_consensus(self):
        """值與其中一個引擎相符 → 有 OCR 證據支持,不該被罰"""
        data = {"contract_amount": "1,500",
                "field_confidences": {"contract_amount": 0.92}}
        out = P._apply_consensus(
            data, consensus("contract_amount", 0.98,
                            {"paddleocr": "1,500", "tesseract": "1,500"}))
        assert out["field_confidences"]["contract_amount"] == pytest.approx(0.92)


class TestFormattingIsNotTampering:
    """LLM 換表示法不是改值——誤判成竄改會讓正常文件大量進複核。"""

    @pytest.mark.parametrize("engine_value,final_value,why", [
        ("1500",        "1,500",       "補千分位"),
        ("１５００",      "1500",        "全形轉半形"),
        (" 1500 ",      "1500",        "去除空白"),
    ])
    def test_normalized_equivalents_keep_confidence(self, engine_value, final_value, why):
        data = {"contract_amount": final_value,
                "field_confidences": {"contract_amount": 0.92}}
        out = P._apply_consensus(
            data, consensus("contract_amount", 0.98,
                            {"paddleocr": engine_value, "tesseract": engine_value}))
        got = out["field_confidences"]["contract_amount"]
        assert got == pytest.approx(0.92), f"{why} 被誤判為竄改(得到 {got})"


class TestInvariantsPreserved:
    def test_never_raises_confidence(self):
        """核心不變量:共識只能收緊,不得放寬——即使值相符也一樣"""
        data = {"contract_amount": "1,500",
                "field_confidences": {"contract_amount": 0.40}}
        out = P._apply_consensus(
            data, consensus("contract_amount", 0.98,
                            {"paddleocr": "1,500", "tesseract": "1,500"}))
        assert out["field_confidences"]["contract_amount"] == pytest.approx(0.40)

    def test_missing_agreements_falls_back_to_old_behaviour(self):
        """沒有 agreements 時(舊結構/單候選)行為不變,不得拋錯"""
        out = P._apply_consensus(
            {"contract_amount": "9,999",
             "field_confidences": {"contract_amount": 0.92}},
            {"field_confidences": {"contract_amount": 0.98}})
        assert out["field_confidences"]["contract_amount"] == pytest.approx(0.92)

    def test_field_nested_under_fields_key(self):
        """欄位收在 fields 底下時也要找得到,否則會誤罰"""
        data = {"fields": {"contract_amount": "1,500"},
                "field_confidences": {"contract_amount": 0.92}}
        out = P._apply_consensus(
            data, consensus("contract_amount", 0.98,
                            {"paddleocr": "1,500", "tesseract": "1,500"}))
        assert out["field_confidences"]["contract_amount"] == pytest.approx(0.92)
