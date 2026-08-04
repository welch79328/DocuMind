"""
欄位層共識解析測試(任務 6.1 / 6.4)

共識機制以「多引擎結果是否一致」作為信心度訊號,取代對單一模型自評信心度的
信任。生成式模型的誤判會產出語法合法但數值錯誤的內容,傳統規則檢查無法攔截,
唯有交叉比對才能揭露。

四種情境:全一致 / 部分不一致 / 全不一致 / 單候選。

對應需求: 4.1, 4.2, 4.4, 4.5
"""

import pytest

from app.lib.multi_type_ocr.field_consensus import (
    DEFAULT_DISAGREE_PENALTY,
    FieldConsensusResolver,
    field_candidate_from_extraction,
)


def _candidate(engine, fields, confidences=None, default_conf=0.9):
    return {
        "engine": engine,
        "fields": fields,
        "field_confidences": confidences or {k: default_conf for k in fields},
        "extraction_method": "regex",
    }


@pytest.fixture
def resolver():
    return FieldConsensusResolver()


# --------------------------------------------------------------------------- #
# 情境 1:全部一致
# --------------------------------------------------------------------------- #
class TestAllAgree:
    def test_agreed_value_adopted(self, resolver):
        result = resolver.resolve([
            _candidate("paddleocr", {"land_number": "0221-0000"}, {"land_number": 0.91}),
            _candidate("tesseract", {"land_number": "0221-0000"}, {"land_number": 0.78}),
        ])

        assert result["fields"]["land_number"] == "0221-0000"
        assert result["agreements"]["land_number"]["agreed"] is True
        assert result["consensus_available"] is True

    def test_confidence_takes_conservative_minimum(self, resolver):
        result = resolver.resolve([
            _candidate("paddleocr", {"land_number": "0221-0000"}, {"land_number": 0.91}),
            _candidate("tesseract", {"land_number": "0221-0000"}, {"land_number": 0.78}),
        ])

        assert result["field_confidences"]["land_number"] == 0.78

    def test_format_variants_still_count_as_agreed(self, resolver):
        """正規化後相等即為一致,格式差異不得使不一致率虛高"""
        result = resolver.resolve([
            _candidate("paddleocr", {"area": "153.00"}),
            _candidate("tesseract", {"area": "153"}),
        ])

        assert result["agreements"]["area"]["agreed"] is True
        assert result["field_confidences"]["area"] == 0.9

    def test_agreed_value_comes_from_highest_confidence_candidate(self, resolver):
        result = resolver.resolve([
            _candidate("paddleocr", {"area": "153.00平方公尺"}, {"area": 0.6}),
            _candidate("tesseract", {"area": "153"}, {"area": 0.95}),
        ])

        assert result["fields"]["area"] == "153"


# --------------------------------------------------------------------------- #
# 情境 2 / 3:部分不一致與全不一致
# --------------------------------------------------------------------------- #
class TestDisagreement:
    def test_disagreed_field_confidence_is_penalised(self, resolver):
        result = resolver.resolve([
            _candidate("paddleocr", {"land_number": "0221-0000"}, {"land_number": 0.91}),
            _candidate("tesseract", {"land_number": "0221-0001"}, {"land_number": 0.88}),
        ])

        assert result["agreements"]["land_number"]["agreed"] is False
        assert result["field_confidences"]["land_number"] == DEFAULT_DISAGREE_PENALTY

    def test_disagreed_value_taken_from_highest_confidence(self, resolver):
        result = resolver.resolve([
            _candidate("paddleocr", {"owner": "王小明"}, {"owner": 0.91}),
            _candidate("tesseract", {"owner": "王大明"}, {"owner": 0.55}),
        ])

        assert result["fields"]["owner"] == "王小明"

    def test_penalty_never_raises_an_already_low_confidence(self, resolver):
        """壓低只能往下:原本就低於懲罰值的信心度不得被抬高"""
        result = resolver.resolve([
            _candidate("paddleocr", {"owner": "王小明"}, {"owner": 0.12}),
            _candidate("tesseract", {"owner": "王大明"}, {"owner": 0.10}),
        ])

        assert result["field_confidences"]["owner"] == 0.12

    def test_partial_disagreement_leaves_agreed_fields_intact(self, resolver):
        result = resolver.resolve([
            _candidate(
                "paddleocr",
                {"land_number": "0221-0000", "area": "153.00"},
                {"land_number": 0.91, "area": 0.88},
            ),
            _candidate(
                "tesseract",
                {"land_number": "0221-0001", "area": "153"},
                {"land_number": 0.90, "area": 0.86},
            ),
        ])

        assert result["field_confidences"]["land_number"] == DEFAULT_DISAGREE_PENALTY
        assert result["field_confidences"]["area"] == 0.86
        assert result["agreements"]["area"]["agreed"] is True

    def test_all_fields_disagree(self, resolver):
        result = resolver.resolve([
            _candidate("paddleocr", {"land_number": "0221-0000", "owner": "王小明"}),
            _candidate("tesseract", {"land_number": "0221-0001", "owner": "王大明"}),
        ])

        assert all(not a["agreed"] for a in result["agreements"].values())
        assert all(
            c == DEFAULT_DISAGREE_PENALTY for c in result["field_confidences"].values()
        )

    def test_one_sided_extraction_counts_as_disagreement(self, resolver):
        """一個引擎抽到、另一個沒抽到 → 不一致(保守方向)"""
        result = resolver.resolve([
            _candidate("paddleocr", {"owner": "王小明"}, {"owner": 0.91}),
            _candidate("tesseract", {"owner": None}, {"owner": 0.0}),
        ])

        assert result["agreements"]["owner"]["agreed"] is False
        assert result["fields"]["owner"] == "王小明"

    def test_field_missing_from_one_candidate_is_handled(self, resolver):
        result = resolver.resolve([
            _candidate("paddleocr", {"land_number": "0221-0000", "owner": "王小明"}),
            _candidate("tesseract", {"land_number": "0221-0000"}),
        ])

        assert result["agreements"]["owner"]["agreed"] is False
        assert result["agreements"]["land_number"]["agreed"] is True

    def test_three_candidates_require_unanimity(self, resolver):
        result = resolver.resolve([
            _candidate("paddleocr", {"area": "153"}),
            _candidate("tesseract", {"area": "153.00"}),
            _candidate("paddleocr_vl", {"area": "158"}),
        ])

        assert result["agreements"]["area"]["agreed"] is False


# --------------------------------------------------------------------------- #
# 情境 4:單一候選
# --------------------------------------------------------------------------- #
class TestSingleCandidate:
    def test_marks_consensus_unavailable(self, resolver):
        result = resolver.resolve([
            _candidate("tesseract", {"land_number": "0221-0000"}, {"land_number": 0.95}),
        ])

        assert result["consensus_available"] is False

    def test_falls_back_to_single_engine_confidence(self, resolver):
        result = resolver.resolve([
            _candidate("tesseract", {"land_number": "0221-0000"}, {"land_number": 0.95}),
        ])

        assert result["field_confidences"]["land_number"] == 0.95
        assert result["fields"]["land_number"] == "0221-0000"

    def test_does_not_claim_agreement(self, resolver):
        """單一候選無從比對,不得偽報為已達成共識"""
        result = resolver.resolve([
            _candidate("tesseract", {"land_number": "0221-0000"}, {"land_number": 0.95}),
        ])

        assert result["agreements"]["land_number"]["agreed"] is False

    def test_empty_candidate_list(self, resolver):
        result = resolver.resolve([])

        assert result["consensus_available"] is False
        assert result["fields"] == {}
        assert result["field_confidences"] == {}
        assert result["agreements"] == {}


# --------------------------------------------------------------------------- #
# 保留各引擎原始值(需求 4.4)
# --------------------------------------------------------------------------- #
class TestEngineValuesPreserved:
    def test_raw_values_kept_for_review(self, resolver):
        result = resolver.resolve([
            _candidate("paddleocr", {"land_number": "0221-0000"}),
            _candidate("tesseract", {"land_number": "0221-OOOO"}),
        ])

        assert result["agreements"]["land_number"]["engine_values"] == {
            "paddleocr": "0221-0000",
            "tesseract": "0221-OOOO",
        }

    def test_raw_values_are_not_normalised(self, resolver):
        """複核時需看到引擎實際輸出,不能只看正規化後的樣子"""
        result = resolver.resolve([
            _candidate("paddleocr", {"area": "153.00平方公尺"}),
            _candidate("tesseract", {"area": "153"}),
        ])

        values = result["agreements"]["area"]["engine_values"]
        assert values["paddleocr"] == "153.00平方公尺"
        assert values["tesseract"] == "153"


# --------------------------------------------------------------------------- #
# 可設定的懲罰值
# --------------------------------------------------------------------------- #
class TestConfigurablePenalty:
    def test_custom_penalty_applied(self):
        resolver = FieldConsensusResolver(disagree_penalty=0.05)
        result = resolver.resolve([
            _candidate("paddleocr", {"owner": "王小明"}),
            _candidate("tesseract", {"owner": "王大明"}),
        ])

        assert result["field_confidences"]["owner"] == 0.05

    def test_normalize_is_exposed(self, resolver):
        assert resolver.normalize("area", "153.00平方公尺") == pytest.approx(153.0)


# --------------------------------------------------------------------------- #
# 由既有抽取結果組出候選(兩種輸出形狀)
# --------------------------------------------------------------------------- #
class TestCandidateFromExtraction:
    def test_flat_extraction_with_field_confidences(self):
        """謄本 / 帳單:扁平輸出且帶 field_confidences"""
        candidate = field_candidate_from_extraction("paddleocr", {
            "land_number": "0221-0000",
            "area": "153",
            "field_confidences": {"land_number": 0.9, "area": 0.4},
            "needs_confirmation": ["area"],
            "extraction_confidence": 0.65,
            "llm_used_for_extraction": False,
        })

        assert candidate["engine"] == "paddleocr"
        assert candidate["fields"] == {"land_number": "0221-0000", "area": "153"}
        assert candidate["field_confidences"] == {"land_number": 0.9, "area": 0.4}
        assert candidate["extraction_method"] == "regex"

    def test_nested_extraction_flattened(self):
        """合約:巢狀輸出且僅有整體 extraction_confidence"""
        candidate = field_candidate_from_extraction("tesseract", {
            "contract_metadata": {"contract_number": "A-001", "signing_date": None},
            "parties": {"party_a": "甲公司", "party_b": "乙公司"},
            "financial_terms": {"contract_amount": "1530000", "currency": "TWD"},
            "extraction_confidence": 0.7,
            "llm_used_for_extraction": False,
        })

        assert candidate["fields"]["contract_number"] == "A-001"
        assert candidate["fields"]["party_a"] == "甲公司"
        assert candidate["fields"]["contract_amount"] == "1530000"
        # 無逐欄位信心度時,以整體信心度作為每個欄位的信心度
        assert candidate["field_confidences"]["party_a"] == 0.7

    def test_meta_keys_never_become_fields(self):
        candidate = field_candidate_from_extraction("paddleocr", {
            "area": "153",
            "field_confidences": {"area": 0.9},
            "needs_confirmation": ["area"],
            "extraction_confidence": 0.9,
            "llm_used_for_extraction": True,
        })

        assert set(candidate["fields"]) == {"area"}

    def test_empty_extraction(self):
        candidate = field_candidate_from_extraction("tesseract", {})
        assert candidate["fields"] == {}
        assert candidate["field_confidences"] == {}

    def test_resolver_consumes_built_candidates(self, resolver):
        left = field_candidate_from_extraction("paddleocr", {
            "contract_metadata": {"contract_number": "A-001"},
            "extraction_confidence": 0.8,
        })
        right = field_candidate_from_extraction("tesseract", {
            "contract_metadata": {"contract_number": "A-OO1"},
            "extraction_confidence": 0.7,
        })

        result = resolver.resolve([left, right])

        # A-OO1 的 O 為 OCR 誤判,正規化後與 A-001 一致
        assert result["agreements"]["contract_number"]["agreed"] is True
        assert result["field_confidences"]["contract_number"] == 0.7
