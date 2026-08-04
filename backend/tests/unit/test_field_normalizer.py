"""
欄位值正規化測試(任務 5.1 / 5.2)

正規化決定共識機制中「一致」的判準,兩個方向的失效都很貴,故兩者都必須驗:

- **正規化不足** → `153.00` 與 `153` 被誤判為不一致,不一致率虛高、複核佇列塞爆
- **過度正規化** → `0221-0000` 與 `0221-0001` 被誤判為一致,真實錯誤被掩蓋(更危險)

對應需求: 4.1, 4.2
"""

import pytest

from app.lib.multi_type_ocr.field_normalizer import (
    FieldNormalizer,
    field_type_of,
    normalize,
    values_agree,
)


# --------------------------------------------------------------------------- #
# 型別對應
# --------------------------------------------------------------------------- #
class TestFieldTypeMapping:
    @pytest.mark.parametrize("field,expected", [
        ("land_number", "identifier"),
        ("building_number", "identifier"),
        ("area", "number"),
        ("contract_amount", "number"),
        ("register_date", "date"),
        ("signing_date", "date"),
        ("effective_date", "date"),
        ("rights_scope", "enum"),
        ("owner", "person"),
    ])
    def test_designated_fields(self, field, expected):
        assert field_type_of(field) == expected

    def test_unlisted_field_defaults_to_string(self):
        assert field_type_of("some_future_field") == "string"

    def test_default_string_normalization_strips_edges(self):
        assert normalize("some_future_field", "  文字  ") == "文字"
        assert values_agree("some_future_field", " 文字 ", "文字") is True
        assert values_agree("some_future_field", "文字A", "文字B") is False


# --------------------------------------------------------------------------- #
# 識別碼
# --------------------------------------------------------------------------- #
class TestIdentifier:
    @pytest.mark.parametrize("variant", [
        "0221-0000",
        "0221-OOOO",      # O 誤判為 0
        "0221-0000 ",     # 尾端空白
        " 0221 - 0000",   # 內含空白
        "０２２１－００００",  # 全形
        "0221–0000",      # 連字號變體(en dash)
        "0221—0000",      # em dash
    ])
    def test_format_variants_agree(self, variant):
        assert values_agree("land_number", "0221-0000", variant) is True

    def test_lowercase_l_and_uppercase_i_map_to_one(self):
        assert values_agree("land_number", "1234-1111", "l234-IIII") is True

    @pytest.mark.parametrize("other", ["0221-0001", "0222-0000", "0221-000"])
    def test_real_differences_stay_disagreed(self, other):
        assert values_agree("land_number", "0221-0000", other) is False

    def test_building_number_uses_same_rules(self):
        assert values_agree("building_number", "01391-000", "０１３９１－０００") is True
        assert values_agree("building_number", "01391-000", "01391-001") is False


# --------------------------------------------------------------------------- #
# 數值
# --------------------------------------------------------------------------- #
class TestNumber:
    @pytest.mark.parametrize("variant", [
        "153", "153.0", "153.00", "153.00平方公尺", " 153 ", "１５３", 153, 153.0,
    ])
    def test_format_variants_agree(self, variant):
        assert values_agree("area", "153.00", variant) is True

    def test_thousands_separator_removed(self):
        assert values_agree("contract_amount", "1,530,000", "1530000") is True

    def test_currency_symbols_removed(self):
        assert values_agree("contract_amount", "NT$1,530,000", "1530000") is True
        assert values_agree("contract_amount", "1530000元", "1530000") is True

    def test_chinese_numerals_converted(self):
        assert values_agree("contract_amount", "一百五十三萬元", "1530000") is True
        assert values_agree("contract_amount", "壹佰伍拾參萬", "1530000") is True
        assert values_agree("contract_amount", "十五", "15") is True

    def test_tolerance_absorbs_rounding_noise(self):
        assert values_agree("area", "153.00", "153.005") is True

    @pytest.mark.parametrize("other", ["154", "153.02", "1530", "15.3"])
    def test_real_differences_stay_disagreed(self, other):
        assert values_agree("area", "153.00", other) is False

    def test_unparseable_number_disagrees_with_value(self):
        assert values_agree("area", "153", "待補") is False

    def test_normalize_returns_float(self):
        assert normalize("area", "153.00平方公尺") == pytest.approx(153.0)


# --------------------------------------------------------------------------- #
# 日期
# --------------------------------------------------------------------------- #
class TestDate:
    @pytest.mark.parametrize("variant", [
        "民國075年05月27日",
        "民國75年5月27日",
        "075/05/27",
        "75.05.27",
        "0750527",
        "1986-05-27",
        "1986/05/27",
    ])
    def test_roc_and_gregorian_variants_agree(self, variant):
        assert values_agree("register_date", "民國075年05月27日", variant) is True

    def test_bare_three_digit_year_treated_as_roc(self):
        assert normalize("register_date", "114年09月26日") == "2025-09-26"

    def test_four_digit_year_treated_as_gregorian(self):
        assert normalize("signing_date", "2026-08-04") == "2026-08-04"

    @pytest.mark.parametrize("other", [
        "民國075年05月28日", "民國075年06月27日", "民國076年05月27日",
    ])
    def test_real_differences_stay_disagreed(self, other):
        assert values_agree("register_date", "民國075年05月27日", other) is False

    def test_unparseable_date_falls_back_to_string_comparison(self):
        assert values_agree("signing_date", "簽約當日", " 簽約當日 ") is True
        assert values_agree("signing_date", "簽約當日", "交屋當日") is False


# --------------------------------------------------------------------------- #
# 列舉字串與人名
# --------------------------------------------------------------------------- #
class TestEnumAndPerson:
    @pytest.mark.parametrize("variant", ["全部", "全 部", "全　部", " 全部 "])
    def test_enum_whitespace_and_fullwidth_unified(self, variant):
        assert values_agree("rights_scope", "全部", variant) is True

    def test_enum_real_difference_disagrees(self):
        assert values_agree("rights_scope", "全部", "持分二分之一") is False

    @pytest.mark.parametrize("variant", ["王小明", "王 小明", "王‧小明", "王・小明"])
    def test_person_whitespace_and_punctuation_stripped(self, variant):
        assert values_agree("owner", "王小明", variant) is True

    def test_person_real_difference_disagrees(self):
        assert values_agree("owner", "王小明", "王大明") is False

    def test_person_keeps_latin_names_distinguishable(self):
        assert values_agree("owner", "John Smith", "JohnSmith") is True
        assert values_agree("owner", "John Smith", "Jane Smith") is False


# --------------------------------------------------------------------------- #
# 邊界情況
# --------------------------------------------------------------------------- #
class TestBoundaries:
    def test_both_absent_counts_as_agreed(self):
        assert values_agree("area", None, None) is True
        assert values_agree("land_number", None, "") is True
        assert values_agree("owner", "  ", None) is True

    @pytest.mark.parametrize("field,value", [
        ("area", "153"), ("land_number", "0221-0000"), ("owner", "王小明"),
    ])
    def test_one_sided_missing_counts_as_disagreed(self, field, value):
        """單邊缺值即為不一致——保守方向,寧可觸發複核"""
        assert values_agree(field, value, None) is False
        assert values_agree(field, None, value) is False

    def test_normalize_absent_returns_none(self):
        assert normalize("area", None) is None
        assert normalize("owner", "   ") is None

    def test_list_values_normalized_elementwise(self):
        assert values_agree(
            "additional_numbers", ["0932-0000", "0933-0000"], ["０９３２－００００", "0933-OOOO"]
        ) is True
        assert values_agree(
            "additional_numbers", ["0932-0000"], ["0932-0001"]
        ) is False

    def test_pure_functions_have_no_shared_state(self):
        """同一輸入重複呼叫結果恆等,且不依賴既有後處理器內部狀態"""
        assert normalize("area", "153.00") == normalize("area", "153.00")
        assert normalize("land_number", "0221-OOOO") == normalize("land_number", "0221-0000")


# --------------------------------------------------------------------------- #
# 類別包裝(供共識解析器注入)
# --------------------------------------------------------------------------- #
class TestFieldNormalizerClass:
    def test_class_delegates_to_pure_functions(self):
        normalizer = FieldNormalizer()
        assert normalizer.normalize("area", "153.00平方公尺") == pytest.approx(153.0)
        assert normalizer.values_agree("land_number", "0221-0000", "0221-OOOO") is True
        assert normalizer.field_type_of("owner") == "person"

    def test_class_is_stateless(self):
        a, b = FieldNormalizer(), FieldNormalizer()
        assert a.normalize("area", "153") == b.normalize("area", "153.00")
