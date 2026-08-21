"""
合約信心度分母修正測試

原缺陷:`_calculate_confidence` 以**全部**欄位為分母,但 CRITICAL_FIELDS 10 個中
6 個、MINOR_FIELDS 15 個中 8 個是租賃專屬。通用合約即使每個欄位都抽對,
上限也只有 0.7×4/10 + 0.3×7/15 = 0.4200,永遠低於 CONFIDENCE_THRESHOLD 0.7
——必然被判低信心、必然觸發 LLM 輔助、必然進複核佇列。

修正:分母只計入這份合約適用的欄位。租賃合約分母維持全部欄位(行為不變),
只有通用合約的分母縮小。
"""

import pytest

from app.config import settings
from app.lib.multi_type_ocr.contract_field_extractor import ContractFieldExtractor

GENERAL_CONTRACT = """
合約編號：ABC-2026-001
簽訂日期：2026年3月26日
生效日期：2026年4月1日
甲方：台灣科技股份有限公司
甲方地址：台北市信義區信義路五段7號
乙方：全球資訊有限公司
乙方地址：新北市板橋區文化路一段100號
合約金額：新台幣 1,000,000 元
幣別：新台幣
付款方式：銀行轉帳
付款期限：2026年4月30日前
"""

LEASE_CONTRACT = """
房屋租賃契約書
合約編號：LEASE-2026-007
甲方：王大明
乙方：陳小華
出租人：王大明
承租人：陳小華
租賃標的：台北市大安區和平東路二段50號5樓
起租日：2026年4月1日
租期終止日：2027年3月31日
月租金：新台幣 30,000 元
押金：新台幣 60,000 元
"""


@pytest.fixture
def extractor():
    return ContractFieldExtractor()


class TestSubtypeDetection:
    def test_general_contract_is_not_a_lease(self, extractor):
        assert extractor.is_lease_contract(GENERAL_CONTRACT) is False

    def test_lease_contract_is_detected(self, extractor):
        assert extractor.is_lease_contract(LEASE_CONTRACT) is True

    @pytest.mark.parametrize(
        "marker", ["租賃", "承租人", "出租人", "月租金", "押金", "租期"]
    )
    def test_each_marker_alone_is_enough(self, extractor, marker):
        assert extractor.is_lease_contract(f"合約編號：X\n{marker}：Y") is True

    def test_empty_text_is_not_a_lease(self, extractor):
        assert extractor.is_lease_contract("") is False
        assert extractor.is_lease_contract(None) is False


class TestApplicableFieldSets:
    def test_general_contract_excludes_lease_fields(self, extractor):
        critical, minor = extractor._applicable_fields(GENERAL_CONTRACT)

        assert extractor.LEASE_CRITICAL_FIELDS.isdisjoint(critical)
        assert extractor.LEASE_MINOR_FIELDS.isdisjoint(minor)
        assert "contract_number" in critical
        assert "payment_method" in minor

    def test_lease_contract_keeps_every_field(self, extractor):
        critical, minor = extractor._applicable_fields(LEASE_CONTRACT)

        assert critical == extractor.CRITICAL_FIELDS
        assert minor == extractor.MINOR_FIELDS

    def test_lease_subsets_are_genuine_subsets(self, extractor):
        assert extractor.LEASE_CRITICAL_FIELDS <= extractor.CRITICAL_FIELDS
        assert extractor.LEASE_MINOR_FIELDS <= extractor.MINOR_FIELDS


class TestGeneralContractCanNowClearTheThreshold:
    @pytest.mark.asyncio
    async def test_fully_extracted_general_contract_passes(self, extractor):
        """這正是原缺陷所在:欄位全對卻永遠達不到門檻"""
        result = await extractor.extract(GENERAL_CONTRACT, use_llm_fallback=False)

        assert result["extraction_confidence"] >= extractor.CONFIDENCE_THRESHOLD

    @pytest.mark.asyncio
    async def test_theoretical_ceiling_is_now_reachable(self, extractor):
        """通用合約的理論上限必須是 1.0,不是 0.42"""
        critical, minor = extractor._applicable_fields(GENERAL_CONTRACT)
        perfect = {name: "值" for name in list(critical) + list(minor)}

        assert extractor._calculate_confidence(perfect, GENERAL_CONTRACT) == 1.0

    def test_old_denominator_would_have_capped_at_042(self, extractor):
        """釘住原缺陷的數字,避免有人把分母改回全部欄位而沒人發現"""
        general_critical = extractor.CRITICAL_FIELDS - extractor.LEASE_CRITICAL_FIELDS
        general_minor = extractor.MINOR_FIELDS - extractor.LEASE_MINOR_FIELDS
        old_ceiling = (
            0.7 * len(general_critical) / len(extractor.CRITICAL_FIELDS)
            + 0.3 * len(general_minor) / len(extractor.MINOR_FIELDS)
        )

        assert round(old_ceiling, 4) == 0.42
        assert old_ceiling < extractor.CONFIDENCE_THRESHOLD


class TestLeaseBehaviourUnchanged:
    @pytest.mark.asyncio
    async def test_lease_denominator_is_still_every_field(self, extractor):
        """只有通用合約的分母縮小;租賃分母維持現狀,信心度不得被順手放寬"""
        result = await extractor.extract(LEASE_CONTRACT, use_llm_fallback=False)

        critical, minor = extractor._applicable_fields(LEASE_CONTRACT)
        expected = extractor._calculate_confidence(
            {
                name: "值"
                for name in list(critical) + list(minor)
                if name in ("contract_number", "party_a", "party_b")
            },
            LEASE_CONTRACT,
        )
        # 不斷言確切值,只確認分母是全部欄位(與修正前同一組)
        assert len(critical) == len(extractor.CRITICAL_FIELDS)
        assert len(minor) == len(extractor.MINOR_FIELDS)
        assert result["extraction_confidence"] >= expected


class TestBadlyReadLeaseIsNotInflated:
    """最該攔截的時候不能放行"""

    @pytest.mark.asyncio
    async def test_garbled_lease_still_scores_low(self, extractor):
        """讀壞到連租賃關鍵詞都消失的文件,分母縮小也不該讓它過關
        ——租賃欄位同樣抽不到,分子一起變小"""
        garbled = "合約鍽號:???\n甲汸:???\n乙汸:???"
        result = await extractor.extract(garbled, use_llm_fallback=False)

        assert result["extraction_confidence"] < extractor.CONFIDENCE_THRESHOLD

    def test_detection_ignores_extraction_success(self, extractor):
        """判別看原始文字而非抽取結果。若改看抽取結果,
        一份讀壞的租約會因抽不到租賃欄位而被當通用合約,分母縮小、信心度虛高"""
        lease_text_no_fields_extractable = "本租賃契約由雙方簽訂,承租人應按月給付租金。"

        assert extractor.is_lease_contract(lease_text_no_fields_extractable) is True
        critical, _ = extractor._applicable_fields(lease_text_no_fields_extractable)
        assert critical == extractor.CRITICAL_FIELDS

    @pytest.mark.asyncio
    async def test_partial_general_contract_still_below_threshold(self, extractor):
        """只抽到一半的通用合約仍應低於門檻,不能因分母縮小就一律放行"""
        partial = "合約編號：ONLY-001\n甲方：某公司"
        result = await extractor.extract(partial, use_llm_fallback=False)

        assert result["extraction_confidence"] < extractor.CONFIDENCE_THRESHOLD


class TestLlmFallbackNoLongerAlwaysFires:
    @pytest.mark.asyncio
    async def test_good_general_contract_does_not_call_llm(
        self, extractor, monkeypatch
    ):
        """原缺陷的成本後果:每份通用合約都必然觸發 LLM 輔助"""
        monkeypatch.setattr(settings, "LLM_CLOUD_ENABLED", True)
        called = []

        async def _spy(text, image_data):
            called.append(text)
            return {}

        monkeypatch.setattr(extractor, "_extract_with_llm", _spy)

        result = await extractor.extract(
            GENERAL_CONTRACT, image_data="ZmFrZQ==", use_llm_fallback=True
        )

        assert called == []
        assert result["llm_used_for_extraction"] is False

    @pytest.mark.asyncio
    async def test_poor_contract_still_calls_llm(self, extractor, monkeypatch):
        """低信心時仍要觸發 LLM 輔助——修正不得順手把這條路徑關掉"""
        monkeypatch.setattr(settings, "LLM_CLOUD_ENABLED", True)
        called = []

        async def _spy(text, image_data):
            called.append(text)
            return {}

        monkeypatch.setattr(extractor, "_extract_with_llm", _spy)

        await extractor.extract(
            "合約編號：ONLY-001", image_data="ZmFrZQ==", use_llm_fallback=True
        )

        assert len(called) == 1
