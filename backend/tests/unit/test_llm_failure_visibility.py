"""
測試「LLM 沒用到」與「LLM 失敗了」在回應裡分得出來(2026-09-09)

背景:一把失效的 OpenAI key 會讓每一次校正都拋例外,而降級後的回應是
llm_used=False、cost=0、HTTP 200——與「信心度夠高所以沒用 LLM」逐鍵相同。
下游無從分辨,於是那把 key 壞了多久都沒人知道。

驗收標準:
- LLM 呼叫失敗 → skipped_reason 為 "provider_error",且帶回錯誤訊息
- 信心度足夠   → "high_confidence"
- 設定停用     → "disabled"
- 三者互不相同(這正是這個修正的重點)
"""

import pytest

from app.lib.ocr_enhanced.postprocessor import TranscriptPostprocessor


class _ExplodingLLM:
    """模擬憑證失效:任何呼叫都炸掉"""

    stats = {"estimated_cost": 0.0}
    last_result = None

    async def correct_full_text(self, *args, **kwargs):
        raise RuntimeError("Incorrect API key provided")

    async def correct_fields(self, *args, **kwargs):
        raise RuntimeError("Incorrect API key provided")


def _postprocessor(**kwargs) -> TranscriptPostprocessor:
    p = TranscriptPostprocessor(enable_llm=False, **kwargs)
    return p


class TestLlmFailureIsDistinguishable:

    @pytest.mark.asyncio
    async def test_provider_error_is_reported(self):
        """LLM 掛掉時必須說是掛掉,不能假裝沒用到"""
        p = _postprocessor()
        p.enable_llm = True
        p.llm_processor = _ExplodingLLM()

        result = await p._apply_llm_correction("土地登記謄本", 0.5, None)

        assert result["used"] is False
        assert result["skipped_reason"] == "provider_error"
        assert "Incorrect API key" in result["error"]
        # 降級不得吃掉原文
        assert result["text"] == "土地登記謄本"

    @pytest.mark.asyncio
    async def test_high_confidence_is_not_an_error(self):
        """信心度夠高而跳過,是正常路徑,不能與失敗混為一談"""
        p = _postprocessor()
        p.enable_llm = True
        p.llm_processor = _ExplodingLLM()

        result = await p._apply_llm_correction("土地登記謄本", 0.99, None)

        assert result["used"] is False
        assert result["skipped_reason"] == "high_confidence"
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_disabled_is_its_own_reason(self):
        """設定停用也是正常路徑,且與信心度足夠不同因"""
        p = _postprocessor(llm_strategy="none")
        p.enable_llm = True
        p.llm_processor = _ExplodingLLM()

        result = await p._apply_llm_correction("土地登記謄本", 0.5, None)

        assert result["used"] is False
        assert result["skipped_reason"] == "disabled"

    @pytest.mark.asyncio
    async def test_three_reasons_are_all_different(self):
        """這個測試才是重點:三種情況以前回傳一模一樣的東西"""
        reasons = set()
        for strategy, conf in [("auto", 0.5), ("auto", 0.99), ("none", 0.5)]:
            p = _postprocessor(llm_strategy=strategy)
            p.enable_llm = True
            p.llm_processor = _ExplodingLLM()
            r = await p._apply_llm_correction("土地登記謄本", conf, None)
            reasons.add(r["skipped_reason"])
        assert reasons == {"provider_error", "high_confidence", "disabled"}
