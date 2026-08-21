"""
設定開關與回滾驗證(ocr-vlm-consensus 任務 10.3)

驗收標準:
- 所有新設定預設為關閉
- 關閉狀態下的辨識結果與現行版本一致
- 設定改回關閉即完成回滾,不需重新部署
- 設定衝突組合(如啟用共識但僅單一引擎)於啟動時提出警告

對應需求: 4.7, 6.6
"""

import base64

import pytest

from app.config import Settings, settings
from app.config_conflicts import check_setting_conflicts, log_setting_conflicts
from app.lib.ocr_enhanced.dual_modal_corrector import (
    CONFIDENCE_MARKER,
    DualModalCorrector,
)

VALID_B64 = base64.b64encode(b"fake-png-bytes").decode()
OCR_TEXT = "中焉區中班息三小旋 o221-oooo 地號"
LABELS = {"land_number": "地號"}

# 本規格新增的所有開關,與其必須的預設值
NEW_TOGGLES = {
    "OCR_CONSENSUS_ENABLED": False,
    "LLM_DUAL_MODAL_ENABLED": False,
    "LLM_FIELD_CONFIDENCE_ENABLED": False,
}


class _FakeProvider:
    def __init__(self, response: str):
        self.response = response
        self.calls: list[dict] = []
        self.stats = {
            "llm_calls": 0, "tokens_used": 0, "prompt_tokens": 0,
            "completion_tokens": 0, "estimated_cost": 0.0,
        }

    async def call(self, prompt, image_data=None, few_shot=None, **kwargs):
        self.calls.append({"prompt": prompt, "image_data": image_data})
        self.stats["llm_calls"] += 1
        return self.response


class TestAllNewTogglesDefaultOff:
    @pytest.mark.parametrize("name,expected", sorted(NEW_TOGGLES.items()))
    def test_default_value_is_off(self, name, expected):
        """讀 Settings 類別的預設,而非當前程序的 settings 實例
        ——實例可能已被環境變數或其他測試改過"""
        assert Settings.model_fields[name].default is expected

    def test_no_new_toggle_is_missing_from_this_list(self):
        """新增開關卻忘了列進來,這條會提醒補上並確認其預設"""
        suspects = {
            name for name in Settings.model_fields
            if ("CONSENSUS" in name or "DUAL_MODAL" in name
                or "CASCADE" in name or "FIELD_CONFIDENCE" in name)
            and Settings.model_fields[name].annotation is bool
        }
        assert suspects == set(NEW_TOGGLES)


class TestOffMeansIdenticalBehaviour:
    @pytest.mark.asyncio
    async def test_dual_modal_off_sends_no_image(self, monkeypatch):
        monkeypatch.setattr(settings, "LLM_DUAL_MODAL_ENABLED", False)
        provider = _FakeProvider("校正後全文")

        result = await DualModalCorrector(provider).correct(
            OCR_TEXT, image_data=VALID_B64
        )

        assert provider.calls[0]["image_data"] is None
        assert result["modality"] == "text_only"
        assert result["degraded_reason"] is None  # 關閉不算降級

    @pytest.mark.asyncio
    async def test_field_confidence_off_leaves_prompt_untouched(self, monkeypatch):
        """關閉時提示詞不含信心度區塊,校正輸出即整段回應"""
        monkeypatch.setattr(settings, "LLM_DUAL_MODAL_ENABLED", False)
        monkeypatch.setattr(settings, "LLM_FIELD_CONFIDENCE_ENABLED", False)
        raw = f'校正後全文\n{CONFIDENCE_MARKER}\n{{"land_number": 0.9}}'
        provider = _FakeProvider(raw)

        result = await DualModalCorrector(provider).correct(
            OCR_TEXT, field_labels=LABELS
        )

        assert CONFIDENCE_MARKER not in provider.calls[0]["prompt"]
        assert result["field_confidences"] == {}
        assert result["text"] == raw


class TestRollbackIsConfigOnly:
    """設定改回關閉即完成回滾,不需重新部署"""

    @pytest.mark.asyncio
    async def test_toggle_on_then_off_within_one_process(self, monkeypatch):
        """同一個程序內開了再關,行為必須回到關閉時的樣子"""
        provider = _FakeProvider("校正後全文")
        corrector = DualModalCorrector(provider)

        monkeypatch.setattr(settings, "LLM_DUAL_MODAL_ENABLED", True)
        on = await corrector.correct(OCR_TEXT, image_data=VALID_B64)
        assert on["modality"] == "dual"
        assert provider.calls[-1]["image_data"] == VALID_B64

        monkeypatch.setattr(settings, "LLM_DUAL_MODAL_ENABLED", False)
        off = await corrector.correct(OCR_TEXT, image_data=VALID_B64)
        assert off["modality"] == "text_only"
        assert provider.calls[-1]["image_data"] is None

    @pytest.mark.asyncio
    async def test_no_reimport_or_restart_needed(self, monkeypatch):
        """設定於呼叫當下讀取,不是在 import 期固定下來
        ——若在 import 期快取,回滾就得重啟服務"""
        provider = _FakeProvider("校正後全文")
        corrector = DualModalCorrector(provider)

        monkeypatch.setattr(settings, "LLM_FIELD_CONFIDENCE_ENABLED", True)
        monkeypatch.setattr(settings, "LLM_DUAL_MODAL_ENABLED", False)
        await corrector.correct(OCR_TEXT, field_labels=LABELS)
        assert CONFIDENCE_MARKER in provider.calls[-1]["prompt"]

        monkeypatch.setattr(settings, "LLM_FIELD_CONFIDENCE_ENABLED", False)
        await corrector.correct(OCR_TEXT, field_labels=LABELS)
        assert CONFIDENCE_MARKER not in provider.calls[-1]["prompt"]


class TestSettingConflictWarnings:
    def test_all_defaults_produce_no_warning(self):
        """預設全關的組合不得吵人,否則警告會被當雜訊忽略"""
        assert check_setting_conflicts(Settings()) == []

    def test_consensus_with_single_engine_warns(self, monkeypatch):
        monkeypatch.setattr(settings, "OCR_CONSENSUS_ENABLED", True)
        monkeypatch.setattr(settings, "OCR_ENGINES", ["paddleocr"])

        warnings = check_setting_conflicts(settings)
        assert len(warnings) == 1
        assert "consensus_available=False" in warnings[0]

    def test_consensus_with_two_engines_is_fine(self, monkeypatch):
        monkeypatch.setattr(settings, "OCR_CONSENSUS_ENABLED", True)
        monkeypatch.setattr(settings, "OCR_ENGINES", ["paddleocr", "tesseract"])
        assert check_setting_conflicts(settings) == []

    def test_dual_modal_with_cloud_warns_about_image_egress(self, monkeypatch):
        monkeypatch.setattr(settings, "LLM_DUAL_MODAL_ENABLED", True)
        monkeypatch.setattr(settings, "LLM_CLOUD_ENABLED", True)
        monkeypatch.setattr(settings, "LLM_FIELD_CONFIDENCE_ENABLED", False)

        warnings = check_setting_conflicts(settings)
        assert any("頁面影像" in w for w in warnings)

    def test_dual_modal_local_only_is_fine(self, monkeypatch):
        monkeypatch.setattr(settings, "LLM_DUAL_MODAL_ENABLED", True)
        monkeypatch.setattr(settings, "LLM_CLOUD_ENABLED", False)
        monkeypatch.setattr(settings, "LLM_FIELD_CONFIDENCE_ENABLED", False)
        monkeypatch.setattr(settings, "OCR_CONSENSUS_ENABLED", False)
        assert check_setting_conflicts(settings) == []

    def test_field_confidence_without_dual_modal_warns(self, monkeypatch):
        monkeypatch.setattr(settings, "LLM_FIELD_CONFIDENCE_ENABLED", True)
        monkeypatch.setattr(settings, "LLM_DUAL_MODAL_ENABLED", False)

        warnings = check_setting_conflicts(settings)
        assert any("看不到原圖" in w for w in warnings)

    def test_cascade_warns_until_measured(self):
        class _Stub:
            CASCADE_ENABLED = True

        warnings = check_setting_conflicts(_Stub())
        assert any("觸發率" in w for w in warnings)

    def test_multiple_conflicts_all_reported(self, monkeypatch):
        """不得只報第一個就收手,否則修完一個又冒一個"""
        monkeypatch.setattr(settings, "OCR_CONSENSUS_ENABLED", True)
        monkeypatch.setattr(settings, "OCR_ENGINES", ["paddleocr"])
        monkeypatch.setattr(settings, "LLM_DUAL_MODAL_ENABLED", True)
        monkeypatch.setattr(settings, "LLM_CLOUD_ENABLED", True)

        assert len(check_setting_conflicts(settings)) >= 2

    def test_missing_attribute_does_not_crash(self):
        """舊設定物件缺少新欄位時只能沉默,不能讓服務起不來"""
        assert check_setting_conflicts(object()) == []


class TestWarningsAreLoggedAtStartup:
    def test_log_setting_conflicts_emits_warning(self, monkeypatch, caplog):
        monkeypatch.setattr(settings, "OCR_CONSENSUS_ENABLED", True)
        monkeypatch.setattr(settings, "OCR_ENGINES", ["paddleocr"])

        with caplog.at_level("WARNING", logger="app.config_conflicts"):
            returned = log_setting_conflicts(settings)

        assert len(returned) == 1
        assert "設定衝突" in caplog.text

    @pytest.mark.asyncio
    async def test_startup_actually_runs_the_check(self, monkeypatch, caplog):
        """警告必須真的在服務啟動時觸發,不是有函式就算數"""
        from app.main import app, lifespan

        monkeypatch.setattr(settings, "OCR_CONSENSUS_ENABLED", True)
        monkeypatch.setattr(settings, "OCR_ENGINES", ["paddleocr"])

        with caplog.at_level("WARNING", logger="app.config_conflicts"):
            async with lifespan(app):
                pass

        assert "設定衝突" in caplog.text

    @pytest.mark.asyncio
    async def test_app_own_lifespan_runs_the_check(self, monkeypatch, caplog):
        """走 app 自己的 lifespan_context——直接呼叫 lifespan() 只證明函式對,
        證明不了它有掛上 app(FastAPI 一定有預設 lifespan_context,不能只斷言非 None)"""
        from app.main import app

        monkeypatch.setattr(settings, "OCR_CONSENSUS_ENABLED", True)
        monkeypatch.setattr(settings, "OCR_ENGINES", ["paddleocr"])

        with caplog.at_level("WARNING", logger="app.config_conflicts"):
            async with app.router.lifespan_context(app):
                pass

        assert "設定衝突" in caplog.text
