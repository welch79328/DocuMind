"""OpenAI 模型必須在所有解析點一致。

2026-09-01 業主定案統一使用 gpt-4o-mini。難點不在改值,在於**同一個模型有五個
各自獨立的解析點**,漏掉任一個就會出現「設定寫 A、實際跑 B」:

    settings.OPENAI_MODEL              config.py
    settings.OPENAI_MODEL_MINI         config.py(分類/摘要/問答用)
    OpenAIProvider.__init__ 的後備     providers.py,model=None 時
    create_provider("openai")          providers.py,讀 settings
    LLMService._get_default_model()    llm_service.py,舊路徑的預設

本檔的存在是為了讓「只改了其中幾個」立刻失敗。

註:曾就「高風險欄位抽取用小模型」提出反對(小模型較易產出語法合法但數值錯誤
的值,正是需求 2 點名的靜默污染)。業主評估後決定統一,記錄於此;
待任務 3.3 基準線產出後可實測降級代價再議。**本測試只驗一致性,不驗選型。**
"""

import pytest

from app.config import settings
from app.lib.llm_service.llm_service import LLMService
from app.lib.llm_service.providers import OpenAIProvider, _PRICING, create_provider

DUMMY_KEY = "sk-test-not-a-real-key"


def _resolution_points():
    """會解析出「主模型」的所有路徑。

    ⚠️ 不含 OPENAI_MODEL_MINI。第一版把它放進來,是因為 2026-09-01 業主決定
    「統一 gpt-4o-mini」時兩者剛好相同。2026-09-03 改為分工之後
    (主路徑 gpt-5.6-terra 做校正與欄位抽取,MINI gpt-5.6-luna 做分類/摘要/問答),
    兩者**本來就該不同**,再要求它們一致是錯的前提。

    MINI 另由 TestConfiguredModelsHavePrices 確保它有價格。
    """
    return {
        "settings.OPENAI_MODEL": settings.OPENAI_MODEL,
        "OpenAIProvider 後備": OpenAIProvider(model=None, api_key=DUMMY_KEY).model,
        "create_provider('openai')": create_provider("openai", api_key=DUMMY_KEY).model,
        "LLMService 預設": LLMService(provider="openai", api_key=DUMMY_KEY).model,
    }


class TestAllResolutionPointsAgree:
    def test_every_point_resolves_to_the_same_model(self):
        """主模型的四個解析點必須一致;漏改任一個就在此失敗。

        難點不在改值,在於同一個模型有多個各自獨立的解析點
        (settings 預設、Provider 後備、create_provider、LLMService 預設),
        漏掉任一個就會出現「設定寫 A、實際跑 B」。
        """
        points = _resolution_points()
        distinct = set(points.values())
        assert len(distinct) == 1, (
            f"OpenAI 主模型解析不一致,出現 {sorted(distinct)}:{points}"
        )

    def test_mini_is_allowed_to_differ_from_main(self):
        """MINI 與主模型分工,不要求相同——但兩者都必須有值。

        釘住這件事,是因為第一版誤把它們綁在一起,
        導致 2026-09-03 改為分工後測試誤報。
        """
        assert settings.OPENAI_MODEL and settings.OPENAI_MODEL_MINI

    def test_resolved_model_has_a_price_entry(self):
        """模型必須在 _PRICING 有對應,否則成本記錄會靜默用 _DEFAULT_PRICE"""
        model = settings.OPENAI_MODEL
        assert model in _PRICING, (
            f"{model} 不在 _PRICING 裡,成本統計會落到 _DEFAULT_PRICE 而不報錯"
        )


class TestPricingTableIsCorrect:
    """價格表的錯誤不會讓任何東西壞掉,只會讓成本報告失真——所以要測。"""

    # 官方單價(每 1M token,input/output),2026-09-01 查證
    EXPECTED = {
        "claude-opus-5": (5.00, 25.00),
        "claude-sonnet-5": (2.00, 10.00),
        "claude-haiku-4-5": (1.00, 5.00),
    }

    @pytest.mark.parametrize("model,expected", EXPECTED.items())
    def test_claude_prices_match_official(self, model, expected):
        """claude-sonnet-5 曾被填成 3.00/15.00(Sonnet 4.6 的價),高估 50%"""
        assert _PRICING[model] == expected, (
            f"{model} 價格為 {_PRICING[model]},應為 {expected}"
        )
