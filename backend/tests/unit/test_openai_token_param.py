"""OpenAI 輸出上限參數必須依模型家族選鍵名。

2026-09-03 事故:模型從 gpt-4o-mini 換成 gpt-5.6-terra 後,每一次 LLM 呼叫都以

    400 invalid_request_error
    Unsupported parameter: 'max_tokens' is not supported with this model.
    Use 'max_completion_tokens' instead.

失敗。而降級設計讓它**靜默退回正則結果**——HTTP 200、llm_pages_used=0、
estimated_cost=$0,API 回應裡完全看不出 LLM 從未成功跑過。只有翻日誌才找得到。

判斷方向刻意是「舊模型用舊鍵」而非「新模型用新鍵」:新模型會一直出,
舊模型清單是封閉的。預設走新鍵,漏掉的新模型才不會壞。
"""

import pytest

from app.config import settings
from app.lib.llm_service.providers import _PRICING, openai_call_kwargs


class TestKeyNameByModelFamily:
    @pytest.mark.parametrize("model", [
        "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna",
        "gpt-5.5", "gpt-5.4", "gpt-5-nano",
    ])
    def test_gpt5_family_uses_max_completion_tokens(self, model):
        assert openai_call_kwargs(model, 2048) == {"max_completion_tokens": 2048}

    @pytest.mark.parametrize("model", ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo", "o3-mini"])
    def test_legacy_family_keeps_max_tokens(self, model):
        assert openai_call_kwargs(model, 2048) == {"max_tokens": 2048}

    def test_unknown_model_defaults_to_the_new_key(self):
        """未知模型走新鍵——新模型會一直出,預設猜新的才不會壞"""
        assert openai_call_kwargs("gpt-7-something", 2048) == {
            "max_completion_tokens": 2048
        }

    def test_configured_model_produces_exactly_one_key(self):
        """實際設定的模型必須產出恰好一個鍵,兩個都傳會被 API 拒絕"""
        kwargs = openai_call_kwargs(settings.OPENAI_MODEL, 2048)
        assert len(kwargs) == 1
        assert set(kwargs) <= {"max_tokens", "max_completion_tokens"}


class TestTemperatureIsDroppedForNewModels:
    """GPT-5 只接受預設 temperature(1);傳任何值都是 400。

    2026-09-03 修完 max_tokens 重跑,數字一模一樣——因為後面還排著 temperature。
    這條就是為了讓「還有下一個不支援的參數」不會再靠翻日誌才發現。
    """

    @pytest.mark.parametrize("model", ["gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"])
    def test_gpt5_never_receives_temperature(self, model):
        for temp in (0.0, 0.1, 0.3, 1.0):
            assert "temperature" not in openai_call_kwargs(model, 2048, temp), (
                f"{model} 收到 temperature={temp},API 會回 400 unsupported_value"
            )

    @pytest.mark.parametrize("model", ["gpt-4o", "gpt-4o-mini"])
    def test_legacy_still_receives_temperature(self, model):
        """舊模型的既有行為不得改變——temperature=0 是抽取任務要的確定性"""
        assert openai_call_kwargs(model, 2048, 0.0)["temperature"] == 0.0

    def test_omitted_args_produce_no_keys(self):
        """兩個參數都不給時回傳空 dict,呼叫端可安全展開"""
        assert openai_call_kwargs("gpt-5.6-terra") == {}


class TestConfiguredModelsHavePrices:
    """模型不在 _PRICING 時會靜默用 _DEFAULT_PRICE(0.15/0.60),成本嚴重失真。"""

    @pytest.mark.parametrize("attr", ["OPENAI_MODEL", "OPENAI_MODEL_MINI"])
    def test_configured_model_is_priced(self, attr):
        """只驗本機設定的模型——線上可能設別的,故另有下面那條"""
        model = getattr(settings, attr)
        assert model in _PRICING, (
            f"{attr}={model} 不在 _PRICING;成本統計會落到 _DEFAULT_PRICE 而不報錯"
        )

    # 這些是 openai_token_limit_kwargs 明確支援的模型;任何一個能被設定,
    # 就必須有價格。只驗 settings 當下的值不夠——本機與線上設的常常不同,
    # 2026-09-03 就是本機 gpt-4o-mini、線上 gpt-5.6-terra,
    # 只驗 settings 的版本無法察覺線上模型缺價。
    @pytest.mark.parametrize("model", [
        "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna",
        "gpt-5.5", "gpt-5.4", "gpt-5-nano",
        "gpt-4o", "gpt-4o-mini",
    ])
    def test_every_supported_model_is_priced(self, model):
        assert model in _PRICING, (
            f"{model} 可被設定卻沒有價格,成本統計會靜默落到 _DEFAULT_PRICE"
        )
