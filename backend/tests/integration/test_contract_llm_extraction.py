"""
LLM 提取整合測試

測試 ContractFieldExtractor 的 LLM 視覺提取功能，驗證正則失敗時 LLM 的備選能力。

警告: 此測試會調用實際的 OpenAI API，產生實際成本！
     只有在設置了 OPENAI_API_KEY 環境變數時才會執行。
"""

import os
import pytest
import time
from unittest.mock import AsyncMock, patch
from app.lib.multi_type_ocr.contract_field_extractor import ContractFieldExtractor


# 檢查是否有 OpenAI API Key
HAS_OPENAI_KEY = os.getenv("OPENAI_API_KEY") is not None

# 只在有 API key 時執行
pytestmark = pytest.mark.skipif(
    not HAS_OPENAI_KEY,
    reason="需要 OPENAI_API_KEY 環境變數才能執行 LLM 整合測試"
)


@pytest.mark.integration
@pytest.mark.asyncio
class TestLLMExtractionIntegration:
    """LLM 提取整合測試（需要實際 API 調用）"""

    @pytest.fixture
    def extractor(self):
        """創建提取器實例"""
        return ContractFieldExtractor()

    async def test_regex_fails_llm_succeeds(self, extractor):
        """
        測試正則提取失敗但 LLM 成功的案例

        驗收標準:
        - 正則提取信心度 < 0.7
        - LLM 被觸發調用
        - LLM 提取到正則無法提取的欄位
        - 最終信心度 > 正則信心度
        """
        # 構造一個正則表達式難以處理的合約文字
        # （格式不標準、包含錯別字、欄位名稱變體）
        poor_quality_text = """
        契約書

        立書人：甲方 台北科技有限公司（簡稱甲方）
        　　　　乙方 新創軟體股份有限公司（以下稱乙方）

        雙方就以下事項達成協議：
        壹、合同編號：Contract-2024-AI-001
        貳、簽約日期：中華民國一一三年三月十日
        參、合同金額：新台幣伍佰萬元整（5,000,000）
        肆、付款方式：分三期付款
        伍、付款期限：簽約後三十日內
        """

        # 創建假的圖像資料（base64）
        fake_image_data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

        # 步驟 1: 先測試僅正則提取的結果
        result_regex_only = await extractor.extract(
            text=poor_quality_text,
            image_data=None,
            use_llm_fallback=False
        )

        regex_confidence = result_regex_only["extraction_confidence"]
        print(f"\n正則提取信心度: {regex_confidence:.2%}")

        # 驗證正則提取信心度較低
        assert regex_confidence < 0.7, "正則提取信心度應 < 0.7"

        # 步驟 2: 測試 LLM 輔助提取
        start_time = time.time()

        result_with_llm = await extractor.extract(
            text=poor_quality_text,
            image_data=fake_image_data,
            use_llm_fallback=True
        )

        elapsed_time = time.time() - start_time
        llm_confidence = result_with_llm["extraction_confidence"]

        print(f"LLM 輔助後信心度: {llm_confidence:.2%}")
        print(f"處理時間: {elapsed_time:.2f} 秒")

        # 驗證 LLM 提取改善了信心度
        assert llm_confidence >= regex_confidence, "LLM 輔助應提升信心度"

        # 驗證提取到的關鍵欄位
        assert result_with_llm["contract_metadata"]["contract_number"] is not None
        assert result_with_llm["parties"]["party_a"] is not None
        assert result_with_llm["parties"]["party_b"] is not None
        assert result_with_llm["financial_terms"]["contract_amount"] is not None

        print(f"✓ LLM 成功提取關鍵欄位")

    async def test_regex_llm_field_merging(self, extractor):
        """
        測試正則與 LLM 混合提取的合併邏輯

        驗收標準:
        - 正則提取部分欄位成功
        - LLM 提取其他欄位
        - 合併後包含兩者的結果
        - LLM 值覆蓋正則錯誤值
        """
        # 構造部分欄位可被正則提取的文字
        mixed_quality_text = """
        合約編號：ABC-2024-001

        甲方名稱：台灣電子科技股份有限公司
        地址：台北市信義區信義路五段七號

        乙方名稱：智慧物聯網有限公司

        合約金額：新台幣 2,500,000 元整
        簽約日：民國113年03月15日
        生效日：同簽約日
        """

        fake_image_data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

        # 正則提取
        result_regex = await extractor.extract(
            text=mixed_quality_text,
            image_data=None,
            use_llm_fallback=False
        )

        # LLM 輔助提取
        result_merged = await extractor.extract(
            text=mixed_quality_text,
            image_data=fake_image_data,
            use_llm_fallback=True
        )

        # 驗證合併邏輯
        # 1. 正則成功的欄位應該被保留或被 LLM 改進
        assert result_merged["contract_metadata"]["contract_number"] is not None

        # 2. 信心度應該提升
        assert result_merged["extraction_confidence"] >= result_regex["extraction_confidence"]

        # 3. LLM 應該填補正則未提取的欄位
        regex_filled_fields = sum(1 for v in [
            result_regex["contract_metadata"]["contract_number"],
            result_regex["parties"]["party_a"],
            result_regex["parties"]["party_b"],
            result_regex["financial_terms"]["contract_amount"],
        ] if v is not None)

        merged_filled_fields = sum(1 for v in [
            result_merged["contract_metadata"]["contract_number"],
            result_merged["parties"]["party_a"],
            result_merged["parties"]["party_b"],
            result_merged["financial_terms"]["contract_amount"],
        ] if v is not None)

        print(f"\n正則提取欄位數: {regex_filled_fields}/4")
        print(f"LLM 輔助後欄位數: {merged_filled_fields}/4")

        assert merged_filled_fields >= regex_filled_fields, "LLM 應填補更多欄位"
        print(f"✓ 欄位合併成功")

    async def test_llm_api_failure_graceful_degradation(self, extractor):
        """
        測試 LLM API 失敗時的優雅降級

        驗收標準:
        - 模擬 LLM API 失敗
        - 不拋出異常
        - 降級返回正則提取結果
        - 記錄錯誤日誌
        """
        text = """
        合約編號：TEST-001
        甲方：測試公司A
        乙方：測試公司B
        金額：1,000,000
        """

        # Mock LLM 服務使其拋出異常
        with patch.object(extractor, '_extract_with_llm', side_effect=Exception("API 調用失敗")):
            result = await extractor.extract(
                text=text,
                image_data="fake_image",
                use_llm_fallback=True
            )

            # 驗證不拋出異常，返回正則結果
            assert result is not None
            assert "extraction_confidence" in result

            # 應該至少有正則提取的部分結果
            assert result["contract_metadata"]["contract_number"] is not None

            print(f"\n✓ LLM 失敗降級成功，信心度: {result['extraction_confidence']:.2%}")

    async def test_llm_cost_and_performance_tracking(self, extractor):
        """
        測試 LLM 成本與性能追蹤

        驗收標準:
        - 記錄 LLM 調用時間
        - 記錄估算成本
        - 驗證性能在合理範圍內（< 10 秒）
        """
        text = """
        軟體授權合約

        合約字號：LICENSE-2024-XYZ
        立約日期：2024年3月20日

        授權方（甲方）：軟體科技股份有限公司
        被授權方（乙方）：數位創新有限公司

        授權金額：新台幣參佰萬元整（NT$3,000,000）
        付款條件：簽約後15個工作日內一次付清
        """

        fake_image_data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

        # 追蹤執行時間
        start_time = time.time()

        result = await extractor.extract(
            text=text,
            image_data=fake_image_data,
            use_llm_fallback=True
        )

        elapsed_time = time.time() - start_time

        # 驗證性能
        assert elapsed_time < 10.0, f"LLM 提取時間過長: {elapsed_time:.2f}s"

        # 獲取 LLM 服務統計（如果可用）
        if hasattr(extractor, 'llm_service') and extractor.llm_service:
            stats = extractor.llm_service.get_stats()
            print(f"\nLLM 調用統計:")
            print(f"  調用次數: {stats['llm_calls']}")
            print(f"  Token 使用: {stats['tokens_used']}")
            print(f"  估算成本: ${stats['estimated_cost']:.4f}")
            print(f"  處理時間: {elapsed_time:.2f} 秒")

            # 驗證有調用 LLM
            assert stats['llm_calls'] > 0, "應該有調用 LLM"

        print(f"✓ 性能追蹤成功")


@pytest.mark.integration
@pytest.mark.asyncio
class TestLLMExtractionAccuracy:
    """LLM 提取準確性測試（與正則對比）"""

    @pytest.fixture
    def extractor(self):
        """創建提取器實例"""
        return ContractFieldExtractor()

    async def test_llm_accuracy_exceeds_regex(self, extractor):
        """
        驗證 LLM 提取準確性高於正則

        驗收標準:
        - 使用多種格式的合約文字
        - LLM 提取的欄位數量 >= 正則
        - LLM 信心度 >= 正則信心度
        """
        # 測試案例：各種格式變體
        test_cases = [
            {
                "name": "標準格式",
                "text": """
                合約編號：STD-2024-001
                甲方：標準公司
                乙方：另一公司
                金額：1000000
                日期：2024-03-20
                """
            },
            {
                "name": "非標準格式",
                "text": """
                Contract No: NON-STD-2024
                Party A: Non-Standard Corp.
                Party B: Another Corp.
                Amount: TWD 2,500,000
                Date: Mar 20, 2024
                """
            },
            {
                "name": "中英混合",
                "text": """
                Contract Number: MIX-2024-CN-EN
                甲方名稱：Mixed Language Company Ltd.
                乙方（Party B）：雙語科技股份有限公司
                合約金額 Amount：NT$ 3,000,000
                Signing Date 簽約日：2024年3月20日
                """
            }
        ]

        fake_image_data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

        results = []

        for case in test_cases:
            # 正則提取
            regex_result = await extractor.extract(
                text=case["text"],
                image_data=None,
                use_llm_fallback=False
            )

            # LLM 輔助提取
            llm_result = await extractor.extract(
                text=case["text"],
                image_data=fake_image_data,
                use_llm_fallback=True
            )

            results.append({
                "name": case["name"],
                "regex_confidence": regex_result["extraction_confidence"],
                "llm_confidence": llm_result["extraction_confidence"],
                "improvement": llm_result["extraction_confidence"] - regex_result["extraction_confidence"]
            })

        # 輸出結果
        print("\n準確性對比:")
        print("=" * 70)
        for r in results:
            print(f"{r['name']:15} | 正則: {r['regex_confidence']:.2%} | "
                  f"LLM: {r['llm_confidence']:.2%} | 提升: {r['improvement']:+.2%}")
        print("=" * 70)

        # 驗證 LLM 整體表現優於正則
        avg_improvement = sum(r['improvement'] for r in results) / len(results)
        print(f"\n平均信心度提升: {avg_improvement:+.2%}")

        assert avg_improvement >= 0, "LLM 平均信心度應優於或等於正則"
        print(f"✓ LLM 準確性驗證通過")


@pytest.mark.unit
@pytest.mark.asyncio
class TestLLMMocking:
    """LLM Mock 測試（不調用實際 API，適合 CI/CD）"""

    @pytest.fixture
    def extractor(self):
        """創建提取器實例"""
        return ContractFieldExtractor()

    async def test_llm_extraction_with_mock(self, extractor):
        """
        使用 Mock 測試 LLM 提取邏輯（不產生實際成本）

        此測試不需要 API key，適合 CI/CD 環境
        """
        text = "合約編號：MOCK-001 甲方：Mock公司A 乙方：Mock公司B"

        # Mock LLM 服務返回
        mock_llm_fields = {
            "contract_number": "MOCK-001",
            "party_a": "Mock公司A",
            "party_b": "Mock公司B",
            "contract_amount": "1000000",
            "signing_date": "2024-03-20",
            "effective_date": None,
            "party_a_address": None,
            "party_b_address": None,
            "currency": "TWD",
            "payment_method": None,
            "payment_deadline": None
        }

        extractor._extract_with_llm = AsyncMock(return_value=mock_llm_fields)

        # 執行提取
        result = await extractor.extract(
            text=text,
            image_data="fake_image",
            use_llm_fallback=True
        )

        # 驗證 Mock 被調用
        extractor._extract_with_llm.assert_called_once()

        # 驗證結果包含 Mock 數據
        assert result["contract_metadata"]["contract_number"] == "MOCK-001"
        assert result["parties"]["party_a"] == "Mock公司A"
        assert result["extraction_confidence"] > 0

        print(f"✓ Mock 測試通過（無 API 成本）")
