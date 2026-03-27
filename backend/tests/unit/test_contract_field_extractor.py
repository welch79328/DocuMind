"""
測試合約欄位提取器

驗收標準 (Task 8.3):
- 測試標準格式合約提取所有欄位
- 測試部分欄位缺失的情況
- 測試信心度計算準確性
- 測試邊界情況(空文字、亂碼等)
- 測試覆蓋率 ≥ 85%
"""

import pytest
from app.lib.multi_type_ocr.contract_field_extractor import ContractFieldExtractor


class TestContractFieldExtractorStructure:
    """測試 ContractFieldExtractor 基本結構"""

    def test_extractor_can_be_instantiated(self):
        """驗證可以實例化提取器"""
        extractor = ContractFieldExtractor()
        assert extractor is not None

    def test_extractor_has_extract_method(self):
        """驗證有 extract 方法"""
        extractor = ContractFieldExtractor()
        assert hasattr(extractor, 'extract')
        assert callable(extractor.extract)


class TestFullFieldExtraction:
    """測試完整欄位提取"""

    @pytest.mark.asyncio
    async def test_extract_all_fields_from_standard_contract(self):
        """測試從標準格式合約提取所有欄位"""
        extractor = ContractFieldExtractor()

        # 標準格式合約文字
        contract_text = """
        合約書

        合約編號：ABC-2026-001
        簽訂日期：2026年3月26日
        生效日期：2026年4月1日

        甲方：台灣科技股份有限公司
        甲方地址：台北市信義區忠孝東路五段100號

        乙方：全球資訊有限公司
        乙方地址：新北市板橋區文化路二段50號

        合約金額：新台幣 1,000,000 元
        幣別：新台幣 (TWD)
        付款方式：銀行轉帳
        付款期限：2026年4月30日前
        """

        result = await extractor.extract(contract_text)

        # 驗證結果結構
        assert "contract_metadata" in result
        assert "parties" in result
        assert "financial_terms" in result
        assert "extraction_confidence" in result

        # 驗證 metadata 欄位
        assert result["contract_metadata"]["contract_number"] == "ABC-2026-001"
        assert "2026年3月26日" in result["contract_metadata"]["signing_date"]
        assert result["contract_metadata"]["effective_date"] is not None

        # 驗證雙方資訊
        assert "台灣科技股份有限公司" in result["parties"]["party_a"]
        assert "全球資訊有限公司" in result["parties"]["party_b"]
        assert result["parties"]["party_a_address"] is not None
        assert result["parties"]["party_b_address"] is not None

        # 驗證財務條款
        assert result["financial_terms"]["contract_amount"] is not None
        assert result["financial_terms"]["currency"] is not None
        assert result["financial_terms"]["payment_method"] is not None

        # 驗證信心度
        assert result["extraction_confidence"] >= 0.7
        assert result["extraction_confidence"] <= 1.0

    @pytest.mark.asyncio
    async def test_extract_with_roc_date_format(self):
        """測試民國年日期格式"""
        extractor = ContractFieldExtractor()

        contract_text = """
        簽訂日期：中華民國 115 年 3 月 26 日
        合約編號：TEST-001
        甲方：測試公司
        """

        result = await extractor.extract(contract_text)

        # 應該能提取民國年日期
        assert result["contract_metadata"]["signing_date"] is not None


class TestPartialFieldExtraction:
    """測試部分欄位缺失的情況"""

    @pytest.mark.asyncio
    async def test_extract_with_minimal_fields(self):
        """測試只有最少欄位的合約"""
        extractor = ContractFieldExtractor()

        contract_text = """
        合約編號：MIN-001
        甲方：公司A
        乙方：公司B
        """

        result = await extractor.extract(contract_text)

        # 驗證有提取到的欄位
        assert result["contract_metadata"]["contract_number"] == "MIN-001"
        assert result["parties"]["party_a"] is not None
        assert result["parties"]["party_b"] is not None

        # 驗證未提取到的欄位返回 None
        assert result["contract_metadata"]["signing_date"] is None
        assert result["contract_metadata"]["effective_date"] is None
        assert result["financial_terms"]["contract_amount"] is None

        # 信心度應該較低（因為缺少很多欄位）
        assert result["extraction_confidence"] < 0.7

    @pytest.mark.asyncio
    async def test_extract_missing_critical_fields(self):
        """測試缺少關鍵欄位的情況"""
        extractor = ContractFieldExtractor()

        contract_text = """
        付款方式：銀行轉帳
        付款期限：2026年5月1日
        """

        result = await extractor.extract(contract_text)

        # 缺少關鍵欄位，信心度應該很低
        assert result["extraction_confidence"] < 0.5

        # 非關鍵欄位應該有提取到
        assert result["financial_terms"]["payment_method"] is not None


class TestConfidenceCalculation:
    """測試信心度計算"""

    @pytest.mark.asyncio
    async def test_confidence_high_when_all_fields_present(self):
        """測試所有欄位都存在時信心度高"""
        extractor = ContractFieldExtractor()

        contract_text = """
        合約編號：FULL-001
        簽訂日期：2026年3月26日
        甲方：公司A
        乙方：公司B
        合約金額：新台幣 500,000 元
        付款方式：現金
        """

        result = await extractor.extract(contract_text)

        # 大部分欄位都有，信心度應該高
        assert result["extraction_confidence"] >= 0.7

    @pytest.mark.asyncio
    async def test_confidence_low_when_few_fields_present(self):
        """測試只有少數欄位時信心度低"""
        extractor = ContractFieldExtractor()

        contract_text = """
        付款方式：轉帳
        """

        result = await extractor.extract(contract_text)

        # 只有一個欄位，信心度應該很低
        assert result["extraction_confidence"] < 0.3

    @pytest.mark.asyncio
    async def test_confidence_weighted_by_field_importance(self):
        """測試信心度計算考慮欄位重要性"""
        extractor = ContractFieldExtractor()

        # 只有關鍵欄位
        critical_fields_text = """
        合約編號：CRIT-001
        甲方：公司A
        乙方：公司B
        合約金額：新台幣 1,000,000 元
        """

        # 只有次要欄位
        minor_fields_text = """
        付款方式：銀行轉帳
        付款期限：2026年5月1日
        幣別：新台幣
        """

        result_critical = await extractor.extract(critical_fields_text)
        result_minor = await extractor.extract(minor_fields_text)

        # 關鍵欄位的信心度應該高於次要欄位
        assert result_critical["extraction_confidence"] > result_minor["extraction_confidence"]


class TestEdgeCases:
    """測試邊界情況"""

    @pytest.mark.asyncio
    async def test_extract_from_empty_text(self):
        """測試空文字"""
        extractor = ContractFieldExtractor()

        result = await extractor.extract("")

        # 應該返回所有欄位為 None
        assert result["contract_metadata"]["contract_number"] is None
        assert result["parties"]["party_a"] is None
        assert result["extraction_confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_extract_from_garbage_text(self):
        """測試亂碼文字"""
        extractor = ContractFieldExtractor()

        garbage_text = "@@##$%^&*()_+{}|:<>?~`"

        result = await extractor.extract(garbage_text)

        # 應該無法提取任何欄位
        assert result["extraction_confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_extract_with_multiple_matches(self):
        """測試文字中有多個匹配的情況（應取第一個）"""
        extractor = ContractFieldExtractor()

        contract_text = """
        合約編號：FIRST-001
        合約編號：SECOND-002
        """

        result = await extractor.extract(contract_text)

        # 應該取第一個匹配
        assert result["contract_metadata"]["contract_number"] == "FIRST-001"

    @pytest.mark.asyncio
    async def test_extract_without_image_data(self):
        """測試不提供圖像資料（只用正則提取）"""
        extractor = ContractFieldExtractor()

        contract_text = """
        合約編號：NO-IMG-001
        甲方：公司A
        """

        # 不傳入 image_data 參數
        result = await extractor.extract(contract_text, image_data=None)

        # 應該正常提取
        assert result["contract_metadata"]["contract_number"] == "NO-IMG-001"


class TestResultStructure:
    """測試返回結果結構"""

    @pytest.mark.asyncio
    async def test_result_has_all_required_keys(self):
        """驗證結果包含所有必要的鍵"""
        extractor = ContractFieldExtractor()

        result = await extractor.extract("測試文字")

        # 驗證頂層鍵
        required_keys = ["contract_metadata", "parties", "financial_terms", "extraction_confidence"]
        for key in required_keys:
            assert key in result

    @pytest.mark.asyncio
    async def test_contract_metadata_structure(self):
        """驗證 contract_metadata 結構"""
        extractor = ContractFieldExtractor()

        result = await extractor.extract("測試")

        metadata = result["contract_metadata"]
        assert "contract_number" in metadata
        assert "signing_date" in metadata
        assert "effective_date" in metadata

    @pytest.mark.asyncio
    async def test_parties_structure(self):
        """驗證 parties 結構"""
        extractor = ContractFieldExtractor()

        result = await extractor.extract("測試")

        parties = result["parties"]
        assert "party_a" in parties
        assert "party_b" in parties
        assert "party_a_address" in parties
        assert "party_b_address" in parties

    @pytest.mark.asyncio
    async def test_financial_terms_structure(self):
        """驗證 financial_terms 結構"""
        extractor = ContractFieldExtractor()

        result = await extractor.extract("測試")

        financial = result["financial_terms"]
        assert "contract_amount" in financial
        assert "currency" in financial
        assert "payment_method" in financial
        assert "payment_deadline" in financial

    @pytest.mark.asyncio
    async def test_missing_fields_are_none_not_omitted(self):
        """驗證缺失欄位返回 None 而非省略"""
        extractor = ContractFieldExtractor()

        result = await extractor.extract("合約編號：TEST-001")

        # 即使未提取到，欄位也應該存在且為 None
        assert result["contract_metadata"]["signing_date"] is None
        assert result["parties"]["party_a"] is None
        assert result["financial_terms"]["contract_amount"] is None


class TestRegexExtraction:
    """測試正則表達式提取邏輯"""

    @pytest.mark.asyncio
    async def test_extract_contract_number_variations(self):
        """測試合約編號的不同格式"""
        extractor = ContractFieldExtractor()

        variations = [
            ("合約編號：ABC-001", "ABC-001"),
            ("合約字號：XYZ-123", "XYZ-123"),
            ("Contract No.: DEF-456", "DEF-456"),
        ]

        for text, expected in variations:
            result = await extractor.extract(text)
            assert result["contract_metadata"]["contract_number"] == expected

    @pytest.mark.asyncio
    async def test_extract_amount_with_comma_separators(self):
        """測試含千分位逗號的金額"""
        extractor = ContractFieldExtractor()

        contract_text = "合約金額：新台幣 12,345,678 元"

        result = await extractor.extract(contract_text)

        # 應該能提取到金額（可能包含或不包含逗號）
        assert result["financial_terms"]["contract_amount"] is not None
        assert "12" in result["financial_terms"]["contract_amount"]

    @pytest.mark.asyncio
    async def test_extract_multiline_contract(self):
        """測試多行合約文字"""
        extractor = ContractFieldExtractor()

        contract_text = """
        合約書

        第一條 合約編號：MULTI-001
        第二條 甲方：多行測試公司
        第三條 乙方：合約範例企業
        """

        result = await extractor.extract(contract_text)

        # 應該能跨行提取
        assert result["contract_metadata"]["contract_number"] == "MULTI-001"
        assert result["parties"]["party_a"] is not None


class TestLLMExtraction:
    """測試 LLM 視覺提取功能（Task 9.1）"""

    @pytest.mark.asyncio
    async def test_extract_with_llm_method_exists(self):
        """驗證 _extract_with_llm 方法存在"""
        from unittest.mock import AsyncMock

        extractor = ContractFieldExtractor()

        # 驗證方法存在
        assert hasattr(extractor, '_extract_with_llm')
        assert callable(extractor._extract_with_llm)

    @pytest.mark.asyncio
    async def test_llm_extraction_with_low_confidence(self):
        """測試當正則提取信心度低時啟用 LLM"""
        from unittest.mock import AsyncMock, patch

        extractor = ContractFieldExtractor()

        # 模擬 LLM 返回結果
        mock_llm_fields = {
            "contract_number": "LLM-001",
            "party_a": "LLM 提取的公司A",
            "party_b": "LLM 提取的公司B",
            "contract_amount": "500000",
        }

        extractor._extract_with_llm = AsyncMock(return_value=mock_llm_fields)

        # 只有很少欄位的文字（正則提取信心度低）
        poor_quality_text = "付款方式：轉帳"

        result = await extractor.extract(
            text=poor_quality_text,
            image_data="fake_base64_image",
            use_llm_fallback=True
        )

        # 驗證 LLM 被調用
        extractor._extract_with_llm.assert_called_once()

        # 驗證 LLM 提取的欄位出現在結果中
        assert result["contract_metadata"]["contract_number"] == "LLM-001"

    @pytest.mark.asyncio
    async def test_llm_not_called_when_confidence_high(self):
        """測試當正則提取信心度高時不調用 LLM"""
        from unittest.mock import AsyncMock

        extractor = ContractFieldExtractor()
        extractor._extract_with_llm = AsyncMock()

        # 完整的合約文字（正則提取信心度高）
        complete_text = """
        合約編號：HIGH-001
        甲方：公司A
        乙方：公司B
        合約金額：新台幣 1,000,000 元
        """

        result = await extractor.extract(
            text=complete_text,
            image_data="fake_base64_image",
            use_llm_fallback=True
        )

        # 信心度高，不應調用 LLM
        extractor._extract_with_llm.assert_not_called()

    @pytest.mark.asyncio
    async def test_llm_disabled_by_default(self):
        """測試 LLM 預設不啟用"""
        from unittest.mock import AsyncMock

        extractor = ContractFieldExtractor()
        extractor._extract_with_llm = AsyncMock()

        poor_text = "付款方式：轉帳"

        # use_llm_fallback=False（預設）
        result = await extractor.extract(text=poor_text, image_data="fake_image")

        # 不應調用 LLM
        extractor._extract_with_llm.assert_not_called()

    @pytest.mark.asyncio
    async def test_llm_extraction_handles_errors_gracefully(self):
        """測試 LLM 提取失敗時降級到正則結果"""
        from unittest.mock import AsyncMock

        extractor = ContractFieldExtractor()

        # 模擬 LLM 拋出異常
        extractor._extract_with_llm = AsyncMock(side_effect=Exception("LLM API 錯誤"))

        poor_text = "合約編號：REGEX-001"

        # 即使 LLM 失敗，也應該返回正則結果
        result = await extractor.extract(
            text=poor_text,
            image_data="fake_image",
            use_llm_fallback=True
        )

        # 應該有正則提取的結果
        assert result["contract_metadata"]["contract_number"] == "REGEX-001"

        # 信心度低但不應該崩潰
        assert result["extraction_confidence"] >= 0.0


class TestFieldMerging:
    """測試欄位合併邏輯（Task 9.2）"""

    @pytest.mark.asyncio
    async def test_merge_fields_method_exists(self):
        """驗證 _merge_fields 方法存在"""
        extractor = ContractFieldExtractor()

        assert hasattr(extractor, '_merge_fields')
        assert callable(extractor._merge_fields)

    @pytest.mark.asyncio
    async def test_merge_fields_llm_overrides_regex(self):
        """測試 LLM 欄位覆蓋正則欄位"""
        extractor = ContractFieldExtractor()

        regex_fields = {
            "contract_number": "REGEX-001",
            "party_a": "正則公司A",
            "party_b": None,  # 正則未提取到
        }

        llm_fields = {
            "contract_number": "LLM-001",  # 覆蓋正則
            "party_b": "LLM公司B",  # LLM 提取到了
        }

        merged = extractor._merge_fields(regex_fields, llm_fields)

        # LLM 提取的欄位應該覆蓋正則
        assert merged["contract_number"] == "LLM-001"

        # LLM 提取到的欄位應該存在
        assert merged["party_b"] == "LLM公司B"

        # 正則提取但 LLM 未提取的欄位應該保留
        assert merged["party_a"] == "正則公司A"

    @pytest.mark.asyncio
    async def test_merge_fields_preserves_regex_when_llm_none(self):
        """測試 LLM 欄位為 None 時保留正則結果"""
        extractor = ContractFieldExtractor()

        regex_fields = {
            "contract_number": "REGEX-001",
            "party_a": "正則公司A",
        }

        llm_fields = {
            "contract_number": None,  # LLM 未提取到
            "party_a": None,
        }

        merged = extractor._merge_fields(regex_fields, llm_fields)

        # 應該保留正則結果
        assert merged["contract_number"] == "REGEX-001"
        assert merged["party_a"] == "正則公司A"

    @pytest.mark.asyncio
    async def test_merge_fields_handles_empty_llm_results(self):
        """測試 LLM 返回空結果時的處理"""
        extractor = ContractFieldExtractor()

        regex_fields = {
            "contract_number": "REGEX-001",
            "party_a": "公司A",
        }

        llm_fields = {}  # LLM 完全失敗，返回空字典

        merged = extractor._merge_fields(regex_fields, llm_fields)

        # 應該完全保留正則結果
        assert merged["contract_number"] == "REGEX-001"
        assert merged["party_a"] == "公司A"
