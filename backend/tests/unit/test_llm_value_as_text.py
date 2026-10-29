"""模型補值一律回字串(2.8.0,.kiro/specs/amount-string-type C1)

非直讀路徑的模型補值會回 JSON 數字(線上存檔:帳單 amount 714、合約 deposit 50000),
同一欄位在字串與數字間浮動。改為寫進欄位前一律轉字串;採用條件、信心度、待確認不變。
"""
import asyncio
import sys

import pytest

sys.path.insert(0, "backend")

from app.config import settings
from app.lib.multi_type_ocr import contract_field_extractor, field_extraction_base
from app.lib.multi_type_ocr.bill_field_extractor import BillFieldExtractor
from app.lib.multi_type_ocr.contract_field_extractor import ContractFieldExtractor
from app.lib.multi_type_ocr.field_extraction_base import llm_value_as_text
from app.lib.multi_type_ocr.transcript_field_extractor import TranscriptFieldExtractor

_META = {"field_confidences", "extraction_confidence", "confidence"}


class FakeProvider:
    def __init__(self, reply: str):
        self.reply = reply

    async def call(self, *args, **kwargs):
        return self.reply


def numeric_values(data, prefix=""):
    """巢狀 dict 裡數字型別(int/float,非 bool)的欄位值;信心度類的鍵本來就是數字,跳過。"""
    out = []
    for key, value in (data or {}).items():
        if key in _META:
            continue
        if isinstance(value, dict):
            out += numeric_values(value, f"{prefix}{key}.")
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            out.append(f"{prefix}{key}")
    return out


def run_bill(reply: str):
    extractor = BillFieldExtractor(provider=FakeProvider(reply))
    return asyncio.run(extractor.extract("台電繳費通知", image_data="x", use_llm_fallback=True))


def run_transcript(reply: str):
    extractor = TranscriptFieldExtractor(provider=FakeProvider(reply))
    return asyncio.run(extractor.extract("建物登記第二類謄本", image_data="x", use_llm_fallback=True))


def run_contract(llm_fields, monkeypatch):
    monkeypatch.setattr(settings, "LLM_CLOUD_ENABLED", True)
    extractor = ContractFieldExtractor()

    async def fake_llm(text, image_data):
        return dict(llm_fields)

    extractor._extract_with_llm = fake_llm
    extractor._llm_provider_name = lambda: "bedrock"
    return asyncio.run(
        extractor.extract("房屋租賃契約書 出租人 承租人 押金", image_data="x", use_llm_fallback=True)
    )


class TestConversion:
    @pytest.mark.parametrize("value,expected", [
        (714, "714"),
        (12345678, "12345678"),
        (0, "0"),
        (25000.0, "25000"),
        (1234.5, "1234.5"),
        (45.67, "45.67"),
    ])
    def test_numbers_become_strings(self, value, expected):
        assert llm_value_as_text(value) == expected

    @pytest.mark.parametrize("value", ["714", "25,000", "", None, True, False, {"a": 1}, [1, 2]])
    def test_non_numbers_unchanged(self, value):
        assert llm_value_as_text(value) is value


class TestBill:
    def test_numeric_amount_and_account_no_become_strings(self):
        """C1①"""
        result = run_bill('{"amount": 714, "date": "115/10/12", "account_no": 12345678}')
        assert result["amount"] == "714"
        assert result["account_no"] == "12345678"
        assert numeric_values(result) == []

    def test_float_amount(self):
        """C1②"""
        assert run_bill('{"amount": 1234.5, "date": null, "account_no": null}')["amount"] == "1234.5"
        assert run_bill('{"amount": 25000.0, "date": null, "account_no": null}')["amount"] == "25000"

    def test_zero_amount_still_not_adopted(self):
        """C1⑤:帳單採用條件是值為真,0 照舊不採用"""
        result = run_bill('{"amount": 0, "date": null, "account_no": null}')
        assert result["amount"] is None
        assert "amount" in result["needs_confirmation"]

    def test_string_values_unchanged(self):
        """C1⑥"""
        result = run_bill('{"amount": "1,234", "date": "115/10/12", "account_no": "01-2345-67"}')
        assert result["amount"] == "1,234"
        assert result["date"] == "115/10/12"
        assert result["account_no"] == "01-2345-67"


class TestTranscript:
    def test_numeric_area_and_floors_become_strings(self):
        """C1③"""
        result = run_transcript('{"area": 45.67, "total_floors": 12}')
        assert result["area"] == "45.67"
        assert result["total_floors"] == "12"
        assert numeric_values(result) == []


class TestContract:
    def test_numeric_amounts_become_strings_including_zero(self, monkeypatch):
        """C1④:合約採用條件是非 None、非 "",0 本來就採用 ⇒ "0" """
        result = run_contract({
            "contract_amount": 25000.0, "monthly_rent": 25000, "deposit": 50000,
            "management_fee": 1500, "parking_fee": 0, "party_a": "王小明",
        }, monkeypatch)
        assert result["financial_terms"]["contract_amount"] == "25000"
        assert result["rental_terms"]["monthly_rent"] == "25000"
        assert result["rental_terms"]["deposit"] == "50000"
        assert result["rental_terms"]["management_fee"] == "1500"
        assert result["rental_terms"]["parking_fee"] == "0"
        assert result["parties"]["party_a"] == "王小明"
        assert numeric_values(result) == []


class TestOnlyTypeChanges:
    """C1⑦:同一輸入,改後與「不轉型別」(改前行為)比,只有值的型別不同。"""

    @staticmethod
    def _as_text_everywhere(data):
        if isinstance(data, dict):
            return {
                k: (v if k in _META else TestOnlyTypeChanges._as_text_everywhere(v))
                for k, v in data.items()
            }
        return llm_value_as_text(data)

    def _old(self, monkeypatch):
        identity = lambda v: v  # noqa: E731
        monkeypatch.setattr(field_extraction_base, "llm_value_as_text", identity)
        monkeypatch.setattr(contract_field_extractor, "llm_value_as_text", identity)

    def test_bill(self, monkeypatch):
        reply = '{"amount": 714, "date": "115/10/12", "account_no": 12345678}'
        new = run_bill(reply)
        self._old(monkeypatch)
        old = run_bill(reply)
        assert numeric_values(old)  # 正對照:改前確實帶數字
        assert new == self._as_text_everywhere(old)

    def test_transcript(self, monkeypatch):
        reply = '{"area": 45.67, "total_floors": 12}'
        new = run_transcript(reply)
        self._old(monkeypatch)
        old = run_transcript(reply)
        assert numeric_values(old)
        assert new == self._as_text_everywhere(old)

    def test_contract(self, monkeypatch):
        fields = {"contract_amount": 25000.0, "monthly_rent": 25000, "deposit": 50000,
                  "management_fee": 1500, "parking_fee": 0}
        new = run_contract(fields, monkeypatch)
        self._old(monkeypatch)
        old = run_contract(fields, monkeypatch)
        assert numeric_values(old)
        assert new == self._as_text_everywhere(old)
