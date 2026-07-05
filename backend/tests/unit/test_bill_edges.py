"""
帳單抽取邊界測試(任務 11.3)

驗證多種帳單格式(水費/管理費)、金額/日期(西元/民國)格式、缺漏案例。

對應需求: 3.1, 3.2, 3.4
"""

import pytest

from app.lib.multi_type_ocr.bill_field_extractor import BillFieldExtractor


@pytest.fixture
def ext():
    return BillFieldExtractor()


class TestBillFormats:
    async def test_water_bill(self, ext):
        text = "台北自來水事業處\n用戶號: 12-345678\n應繳金額: 320 元\n繳費期限: 2026/04/10"
        r = await ext.extract(text)
        assert r["account_no"] == "12-345678"
        assert r["amount"] == "320"
        assert r["date"] == "2026/04/10"

    async def test_management_fee(self, ext):
        text = "社區管理費通知\n戶號: A-1201\n本期應繳: 3,500\n繳費日期: 2026-05-01"
        r = await ext.extract(text)
        assert r["account_no"] == "A-1201"
        assert r["amount"] == "3,500"
        assert r["date"] == "2026-05-01"

    async def test_amount_with_currency_prefix(self, ext):
        text = "金額: NT$ 1,880\n戶號: 999\n日期: 2026/01/01"
        r = await ext.extract(text)
        assert r["amount"] == "1,880"

    async def test_minguo_date(self, ext):
        # 民國年格式(產品需支援民國/西元雙格式)
        text = "戶號: 555\n金額: 700\n繳費期限: 民國115年3月15日"
        r = await ext.extract(text)
        assert r["date"] is not None
        assert "115" in r["date"]


class TestMissingCases:
    async def test_all_missing(self, ext):
        r = await ext.extract("這是一張沒有關鍵欄位的文件")
        assert set(r["needs_confirmation"]) == {"amount", "date", "account_no"}
        assert r["llm_used_for_extraction"] is False

    async def test_partial_missing(self, ext):
        text = "戶號: 777"  # 缺金額與日期
        r = await ext.extract(text)
        assert "amount" in r["needs_confirmation"]
        assert "date" in r["needs_confirmation"]
        assert "account_no" not in r["needs_confirmation"]

    async def test_extraction_confidence_reflects_fill(self, ext):
        full = "戶號: 1\n金額: 100\n日期: 2026/01/01"
        partial = "戶號: 1"
        assert (await ext.extract(full))["extraction_confidence"] > \
               (await ext.extract(partial))["extraction_confidence"]
