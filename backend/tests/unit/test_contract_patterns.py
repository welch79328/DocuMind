"""
測試合約正則表達式模式庫

驗收標準 (Task 7.2):
- 每個正則表達式至少 3 個測試案例
- 測試正常匹配與邊界情況
- 測試繁體中文、英文、混合格式
- 測試民國年與西元年轉換
- 測試覆蓋率 100%
"""

import pytest
import re
from app.lib.multi_type_ocr.contract_patterns import PATTERNS


class TestContractNumberPatterns:
    """測試合約編號模式"""

    def test_contract_number_chinese_format(self):
        """測試中文格式的合約編號"""
        text = "合約編號：ABC-2026-001"
        pattern = PATTERNS["contract_number"][0]
        match = re.search(pattern, text)
        assert match is not None
        assert match.group(1) == "ABC-2026-001"

    def test_contract_number_english_format(self):
        """測試英文格式的合約編號"""
        text = "Contract No.: XYZ-2026-123"
        pattern = PATTERNS["contract_number"][1]
        match = re.search(pattern, text)
        assert match is not None
        assert match.group(1) == "XYZ-2026-123"

    def test_contract_number_with_variation(self):
        """測試合約字號變體"""
        text = "合約字號: TEST-001"
        pattern = PATTERNS["contract_number"][0]
        match = re.search(pattern, text)
        assert match is not None
        assert match.group(1) == "TEST-001"

    def test_contract_number_no_match(self):
        """測試無法匹配的情況"""
        text = "這是一份合約"
        results = []
        for pattern in PATTERNS["contract_number"]:
            match = re.search(pattern, text)
            if match:
                results.append(match.group(1))
        assert len(results) == 0


class TestSigningDatePatterns:
    """測試簽訂日期模式"""

    def test_signing_date_roc_format(self):
        """測試民國年格式"""
        text = "簽訂日期：中華民國 115 年 3 月 26 日"
        pattern = PATTERNS["signing_date"][1]
        match = re.search(pattern, text)
        assert match is not None
        assert match.group(1) == "115"
        assert match.group(2) == "3"
        assert match.group(3) == "26"

    def test_signing_date_western_format(self):
        """測試西元年格式"""
        text = "簽訂日期：2026年3月26日"
        pattern = PATTERNS["signing_date"][0]
        match = re.search(pattern, text)
        assert match is not None
        assert "2026年3月26日" in match.group(0)

    def test_signing_date_effective_date(self):
        """測試生效日期格式"""
        text = "生效日期：2026年4月1日"
        pattern = PATTERNS["effective_date"][0]
        match = re.search(pattern, text)
        assert match is not None

    def test_signing_date_compact_roc_format(self):
        """測試緊湊型民國年格式（無空格）"""
        text = "立約日期：中華民國115年3月26日"
        pattern = PATTERNS["signing_date"][2]
        match = re.search(pattern, text)
        assert match is not None


class TestPartyPatterns:
    """測試雙方資訊模式"""

    def test_party_a_standard_format(self):
        """測試甲方標準格式"""
        text = "甲方：台灣科技股份有限公司"
        pattern = PATTERNS["party_a"][0]
        match = re.search(pattern, text)
        assert match is not None
        assert "台灣科技股份有限公司" in match.group(1)

    def test_party_b_standard_format(self):
        """測試乙方標準格式"""
        text = "乙方：全球資訊有限公司"
        pattern = PATTERNS["party_b"][0]
        match = re.search(pattern, text)
        assert match is not None
        assert "全球資訊有限公司" in match.group(1)

    def test_party_with_representative(self):
        """測試含代表人的格式"""
        text = "立合約書人：台灣企業股份有限公司（以下簡稱甲方）"
        pattern = PATTERNS["party_a"][1]
        match = re.search(pattern, text)
        assert match is not None
        assert "台灣企業股份有限公司" in match.group(1)

    def test_party_address_format(self):
        """測試地址格式"""
        text = "甲方地址：台北市信義區忠孝東路五段100號"
        pattern = PATTERNS["party_a_address"][0]
        match = re.search(pattern, text)
        assert match is not None


class TestFinancialTermsPatterns:
    """測試財務條款模式"""

    def test_contract_amount_with_currency(self):
        """測試含幣別的金額格式"""
        text = "合約金額：新台幣 1,000,000 元"
        pattern = PATTERNS["contract_amount"][0]
        match = re.search(pattern, text)
        assert match is not None

    def test_contract_amount_simple_format(self):
        """測試簡單金額格式"""
        text = "總價：500,000元整"
        pattern = PATTERNS["contract_amount"][1]
        match = re.search(pattern, text)
        assert match is not None

    def test_contract_amount_english_currency(self):
        """測試英文幣別"""
        text = "Total Amount: TWD 2,500,000"
        pattern = PATTERNS["contract_amount"][2]
        match = re.search(pattern, text)
        assert match is not None

    def test_currency_extraction(self):
        """測試幣別提取"""
        text = "幣別：新台幣 (TWD)"
        pattern = PATTERNS["currency"][0]
        match = re.search(pattern, text)
        assert match is not None

    def test_payment_method_format(self):
        """測試付款方式"""
        text = "付款方式：銀行轉帳"
        pattern = PATTERNS["payment_method"][0]
        match = re.search(pattern, text)
        assert match is not None

    def test_payment_deadline_format(self):
        """測試付款期限"""
        text = "付款期限：2026年4月30日前"
        pattern = PATTERNS["payment_deadline"][0]
        match = re.search(pattern, text)
        assert match is not None


class TestPatternCoverage:
    """測試模式庫完整性"""

    def test_all_required_fields_present(self):
        """驗證所有必要欄位都存在於模式庫"""
        required_fields = [
            "contract_number",
            "signing_date",
            "effective_date",
            "party_a",
            "party_b",
            "party_a_address",
            "party_b_address",
            "contract_amount",
            "currency",
            "payment_method",
            "payment_deadline",
        ]

        for field in required_fields:
            assert field in PATTERNS, f"缺少必要欄位: {field}"

    def test_each_field_has_multiple_patterns(self):
        """驗證每個欄位至少有 2 個正則表達式變體"""
        for field_name, patterns in PATTERNS.items():
            assert isinstance(patterns, list), f"{field_name} 應該是列表"
            assert len(patterns) >= 2, f"{field_name} 應該至少有 2 個模式變體"

    def test_patterns_are_valid_regex(self):
        """驗證所有模式都是有效的正則表達式"""
        for field_name, patterns in PATTERNS.items():
            for i, pattern in enumerate(patterns):
                try:
                    re.compile(pattern)
                except re.error as e:
                    pytest.fail(f"{field_name}[{i}] 正則表達式無效: {e}")


class TestEdgeCases:
    """測試邊界情況"""

    def test_multiple_colons(self):
        """測試多種冒號格式（中文、英文）"""
        text1 = "合約編號：ABC-001"
        text2 = "合約編號: ABC-001"
        pattern = PATTERNS["contract_number"][0]

        assert re.search(pattern, text1) is not None
        assert re.search(pattern, text2) is not None

    def test_whitespace_variations(self):
        """測試不同空白字元"""
        text1 = "甲方：公司A"
        text2 = "甲方： 公司A"
        text3 = "甲方:  公司A"
        pattern = PATTERNS["party_a"][0]

        for text in [text1, text2, text3]:
            assert re.search(pattern, text) is not None

    def test_amount_with_commas(self):
        """測試含千分位逗號的金額"""
        text = "合約金額：新台幣 12,345,678 元"
        pattern = PATTERNS["contract_amount"][0]
        match = re.search(pattern, text)
        assert match is not None

    def test_multiline_text(self):
        """測試多行文字中的欄位提取"""
        text = """
        合約書

        合約編號：TEST-2026-001
        簽訂日期：2026年3月26日

        甲方：台灣公司
        乙方：全球公司
        """

        # 測試能在多行文字中找到欄位
        assert re.search(PATTERNS["contract_number"][0], text) is not None
        assert re.search(PATTERNS["signing_date"][0], text) is not None
        assert re.search(PATTERNS["party_a"][0], text) is not None
        assert re.search(PATTERNS["party_b"][0], text) is not None
