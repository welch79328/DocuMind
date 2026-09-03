"""欄位型別合理性檢查——攔截「語法合法但填錯欄位」的值。

2026-09-03 線上實測一份謄本,系統回傳:

    "building_number": "過溝段00004-000",
    "area": "0555-0000",          ← 地號被填進面積欄位
    "field_confidences": { "area": 0.8 }

錯值帶著 0.8 的信心度,而攔截門檻正是 0.8。該頁只因**整體**信心度 0.320
才被拖進複核——運氣,不是機制。

field_normalizer 擋不住,因為它是為比對設計的寬鬆正規化:
    normalize_number("0555-0000") → 555.0

本檔同時把那個事實釘住(見 TestNormalizerIsNotAValidator),
因為 values_agree 用的是同一支——`area="0555-0000"` 與 `area="555"`
在共識比對裡會被判定為一致,那是共識機制的既有隱憂。
"""

import pytest

from app.config import settings
from app.lib.multi_type_ocr.field_normalizer import normalize_number
from app.lib.multi_type_ocr.field_validator import validate_field_value, validate_fields
from app.lib.multi_type_ocr.processor import OcrDocumentProcessor as P

PENALTY = settings.OCR_CONSENSUS_DISAGREE_PENALTY
THRESHOLD = settings.OCR_QUALITY_THRESHOLD


class TestCatchesTheRealDefect:
    def test_land_number_in_area_is_rejected(self):
        """線上實際發生的那一個"""
        assert validate_field_value("area", "0555-0000") is not None

    def test_building_number_in_amount_is_rejected(self):
        assert validate_field_value("contract_amount", "過溝段00004-000") is not None

    def test_rejected_value_falls_below_the_gate(self):
        """壓低之後必須真的低於攔截門檻,否則等於沒擋"""
        out = P._apply_field_validation({
            "area": "0555-0000",
            "field_confidences": {"area": 0.8},
        })
        assert out["field_confidences"]["area"] < THRESHOLD

    def test_reason_is_recorded_for_the_reviewer(self):
        """複核的人要知道看哪一欄、為什麼——只壓分數不說原因等於把問題丟給人猜"""
        out = P._apply_field_validation({
            "area": "0555-0000", "field_confidences": {"area": 0.8},
        })
        assert "area" in out["needs_confirmation"]
        assert "area" in out["validation_warnings"]


class TestDoesNotFlagLegitimateValues:
    """誤判的代價是把正常文件推進人工複核——比漏抓更常見也更貴。"""

    @pytest.mark.parametrize("field,value", [
        ("area", "3,406.98"),
        ("area", "1924.86平方公尺"),
        ("contract_amount", "5,000,000"),
        ("contract_amount", "新台幣伍佰萬元整"),
        ("land_number", "竹田鄉過溝段0555-0000地號"),
        ("building_number", "00004-000"),
        ("owner", "林順員"),
        ("rights_scope", "全部"),
        ("signing_date", "113年3月10日"),
        ("signing_date", "民國113年3月10日"),
        ("signing_date", "2024-03-10"),
    ])
    def test_valid_value_passes(self, field, value):
        assert validate_field_value(field, value) is None, (
            f"{field}={value!r} 被誤判為不合理"
        )

    @pytest.mark.parametrize("absent", [None, "", "   ", "N/A", "無"])
    def test_absent_values_are_not_errors(self, absent):
        """沒抽到不是型別錯誤,那是 needs_confirmation 的職責"""
        assert validate_field_value("area", absent) is None

    def test_real_page_one_passes_entirely(self):
        """線上實際回傳的正常頁面不得有任何警告"""
        assert validate_fields({
            "land_number": "竹田鄉過溝段0555-0000地號",
            "area": "3,406.98",
            "rights_scope": "全部",
            "owner": "林順員",
            "building_number": None,
        }) == {}


class TestOnlyTightens:
    """與共識同一不變量:新訊號只能收緊攔截,不得放寬。"""

    def test_never_raises_an_already_lower_confidence(self):
        out = P._apply_field_validation({
            "area": "0555-0000",
            "field_confidences": {"area": 0.05},
        })
        assert out["field_confidences"]["area"] == pytest.approx(0.05)

    def test_untouched_fields_keep_their_confidence(self):
        out = P._apply_field_validation({
            "area": "0555-0000", "owner": "林順員",
            "field_confidences": {"area": 0.8, "owner": 0.9},
        })
        assert out["field_confidences"]["owner"] == pytest.approx(0.9)

    def test_clean_data_is_returned_unchanged(self):
        data = {"area": "3,406.98", "field_confidences": {"area": 0.9}}
        assert P._apply_field_validation(dict(data)) == data


class TestNormalizerIsNotAValidator:
    """釘住「為什麼不能只靠 field_normalizer」——它是比對用的,不是驗證用的。"""

    @pytest.mark.parametrize("value,parsed_as", [
        ("0555-0000", 555.0),
        ("00004-000", 4.0),
    ])
    def test_normalizer_silently_parses_identifiers_as_numbers(self, value, parsed_as):
        """這不是缺陷回報,是把現況釘住:normalize_number 不會拒絕識別碼。

        它同時代表 values_agree 會把 area="0555-0000" 與 area="555" 判為一致
        ——共識機制的既有隱憂,見 gap-analysis。
        """
        assert normalize_number(value) == parsed_as
        # 而驗證器必須擋下同一個值
        assert validate_field_value("area", value) is not None
