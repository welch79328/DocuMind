"""
帳單電費 4 欄(address、period_start、period_end、kwh):共用正規化模組與文字層規則。

規則出處:.kiro/specs/bill-electric-fields/acceptance.md R1–R11。
直讀路徑的端點測試在 test_direct_read.py TestBill。
"""

import pytest

from app.lib.multi_type_ocr.bill_electric_fields import (
    normalize_address,
    normalize_kwh,
    resolve_electric_fields,
)
from app.lib.multi_type_ocr.bill_field_extractor import BillFieldExtractor

ELECTRIC = ("address", "period_start", "period_end", "kwh")


def _raw(**kw):
    base = {k: (None, True) for k in ELECTRIC}
    base.update(kw)
    return base


class TestNormalizeAddress:
    def test_keeps_original_text(self):
        assert normalize_address("臺北市中正區AV測試路100號") == "臺北市中正區AV測試路100號"

    def test_collapses_to_single_line(self):
        assert normalize_address("臺北市中正區\nAV測試路 100號") == "臺北市中正區 AV測試路 100號"

    @pytest.mark.parametrize("bad", [
        "臺北市中正區 https://x.example", "www.example.com", "a@b", "地址:臺北市", "地址：臺北市",
        "臺" * 81,
    ])
    def test_rejects_forbidden_or_too_long(self, bad):
        assert normalize_address(bad) is None


class TestNormalizeKwh:
    @pytest.mark.parametrize("raw,expected", [
        ("812", "812"), ("812 度", "812"), ("1,234", "1,234"), ("12.5kWh", "12.5"), ("８１２", "812"),
    ])
    def test_valid(self, raw, expected):
        assert normalize_kwh(raw) == expected

    @pytest.mark.parametrize("bad", ["0", "八百", "12,34", "-5", "1" * 31, ""])
    def test_invalid(self, bad):
        assert normalize_kwh(bad) is None


class TestResolve:
    def test_all_null_is_not_flagged(self):
        """水費、管理費單沒有電費欄位:值 null、不列待確認、不進信心度(否則每張都進複核)"""
        values, confidences, needs = resolve_electric_fields(_raw())
        assert values == {k: None for k in ELECTRIC}
        assert confidences == {} and needs == []

    def test_full_read_roc_dates(self):
        values, confidences, needs = resolve_electric_fields(_raw(
            address=("臺北市中正區AV測試路100號", True),
            period_start=("115/09/15", True), period_end=("115/11/14", True),
            kwh=("812", True),
        ))
        assert values == {
            "address": "臺北市中正區AV測試路100號",
            "period_start": "2026-09-15", "period_end": "2026-11-14", "kwh": "812",
        }
        assert needs == [] and set(confidences) == set(ELECTRIC)

    def test_uncertain_keeps_value_and_flags(self):
        values, _, needs = resolve_electric_fields(_raw(kwh=("812", False)))
        assert values["kwh"] == "812" and needs == ["kwh"]

    def test_end_before_start_nulls_both(self):
        values, _, needs = resolve_electric_fields(_raw(
            period_start=("115/11/14", True), period_end=("115/09/15", True),
        ))
        assert values["period_start"] is None and values["period_end"] is None
        assert needs == ["period_start", "period_end"]

    def test_unparseable_date_nulls_that_end(self):
        values, _, needs = resolve_electric_fields(_raw(
            period_start=("九月中", True), period_end=("115/11/14", True),
        ))
        assert values["period_start"] is None and values["period_end"] == "2026-11-14"
        assert needs == ["period_start"]

    def test_only_one_end_flags_both(self):
        values, _, needs = resolve_electric_fields(_raw(period_start=("115/09/15", True)))
        assert values["period_start"] == "2026-09-15" and values["period_end"] is None
        assert sorted(needs) == ["period_end", "period_start"]

    def test_multiple_periods_nulls_and_flags(self):
        values, _, needs = resolve_electric_fields(
            _raw(period_start=("115/09/15", True), period_end=("115/11/14", True)),
            multiple_periods=True,
        )
        assert values["period_start"] is None and values["period_end"] is None
        assert needs == ["period_start", "period_end"]


# --------------------------------------------------------------------------- #
# 文字層規則(有文字層的 PDF;AIChatbot 送 enable_llm=false,只走這條)
# --------------------------------------------------------------------------- #
TAIPOWER_TEXT = (
    "台灣電力公司 電費通知單\n"
    "電號 99-01-2345-67-8\n"
    "用電地址 臺北市中正區AV測試路100號\n"
    "通訊地址 臺北市大安區別的路1號\n"
    "計費期間 115/09/15 至 115/11/14\n"
    "本期用電度數 812 度\n"
    "應繳總金額 3,456 元\n"
    "繳費期限 115/12/05\n"
    "本期指針 12345 上期指針 11533\n"
)


@pytest.fixture
def ext():
    return BillFieldExtractor()


class TestTextLayerRules:
    async def test_taipower_bill_six_fields(self, ext):
        r = await ext.extract(TAIPOWER_TEXT)
        assert r["account_no"] == "99-01-2345-67-8"
        assert r["address"] == "臺北市中正區AV測試路100號"
        assert r["period_start"] == "2026-09-15"
        assert r["period_end"] == "2026-11-14"
        assert r["kwh"] == "812"
        assert r["amount"] == "3,456"
        assert r["needs_confirmation"] == []
        assert r["llm_used_for_extraction"] is False

    async def test_fullwidth_and_label_on_own_line(self, ext):
        text = "電號：99-02-3456-78-9\n用電地址：\n臺北市中正區AV測試路200號\n計費期間：115/09/15～115/11/14\n計費度數：640\n"
        r = await ext.extract(text)
        assert r["account_no"] == "99-02-3456-78-9"
        assert r["address"] == "臺北市中正區AV測試路200號"
        assert (r["period_start"], r["period_end"]) == ("2026-09-15", "2026-11-14")
        assert r["kwh"] == "640"

    async def test_water_bill_electric_keys_null_not_flagged(self, ext):
        text = "台北自來水事業處\n用戶號: 12-345678\n應繳金額: 320 元\n繳費期限: 2026/04/10"
        r = await ext.extract(text)
        assert all(k in r and r[k] is None for k in ELECTRIC)
        assert r["needs_confirmation"] == []
        assert not set(ELECTRIC) & set(r["field_confidences"])

    async def test_two_billing_periods_null_and_flagged(self, ext):
        text = TAIPOWER_TEXT + "計費期間 115/07/15 至 115/09/14(補收)\n"
        r = await ext.extract(text)
        assert r["period_start"] is None and r["period_end"] is None
        assert {"period_start", "period_end"} <= set(r["needs_confirmation"])

    async def test_meter_reading_is_not_kwh(self, ext):
        r = await ext.extract("本期指針 12345 上期指針 11533\n")
        assert r["kwh"] is None
