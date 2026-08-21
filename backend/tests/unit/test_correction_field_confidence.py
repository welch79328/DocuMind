"""
校正階段的欄位級信心度測試(ocr-vlm-consensus 任務 8.4)

驗收標準:
- 校正後輸出各欄位信心度
- 雙模態、純文字降級、模型拒絕三路徑皆有測試
- (「與基準對照,欄位準確率未退步」須待任務 3.3 首次正式基準,見報告)

對應需求: 2.2
"""

import base64

import pytest

from app.config import settings
from app.lib.multi_type_ocr.processor import OcrDocumentProcessor
from app.lib.ocr_enhanced.dual_modal_corrector import (
    CONFIDENCE_MARKER,
    DualModalCorrector,
    build_confidence_instruction,
    build_correction_prompt,
    split_confidence_block,
)

VALID_B64 = base64.b64encode(b"fake-png-bytes").decode()
OCR_TEXT = "中焉區中班息三小旋 o221-oooo 地號"
LABELS = {"land_number": "地號", "owner": "所有權人"}

CORRECTED = "中正區中正段三小段 0221-0000 地號"
WITH_CONFIDENCE = (
    f'{CORRECTED}\n{CONFIDENCE_MARKER}\n'
    '{"land_number": 0.92, "owner": 0.4}'
)


class _FakeProvider:
    def __init__(self, response: str = CORRECTED):
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


@pytest.fixture
def confidence_on(monkeypatch):
    monkeypatch.setattr(settings, "LLM_FIELD_CONFIDENCE_ENABLED", True)


@pytest.fixture
def confidence_off(monkeypatch):
    monkeypatch.setattr(settings, "LLM_FIELD_CONFIDENCE_ENABLED", False)


@pytest.fixture
def dual_on(monkeypatch):
    monkeypatch.setattr(settings, "LLM_DUAL_MODAL_ENABLED", True)


@pytest.fixture
def dual_off(monkeypatch):
    monkeypatch.setattr(settings, "LLM_DUAL_MODAL_ENABLED", False)


# ====================================================================== #
# 解析
# ====================================================================== #
class TestSplitConfidenceBlock:
    def test_splits_text_and_confidences(self):
        text, confidences = split_confidence_block(WITH_CONFIDENCE)
        assert text == CORRECTED
        assert confidences == {"land_number": 0.92, "owner": 0.4}

    def test_no_marker_means_everything_is_text(self):
        text, confidences = split_confidence_block(CORRECTED)
        assert text == CORRECTED
        assert confidences == {}

    def test_invalid_json_reports_nothing_rather_than_guessing(self):
        """信心度回報若靠猜,整套低信心攔截就失去意義"""
        text, confidences = split_confidence_block(
            f"{CORRECTED}\n{CONFIDENCE_MARKER}\n{{壞掉的 JSON"
        )
        assert text == CORRECTED
        assert confidences == {}

    def test_marker_without_json_reports_nothing(self):
        text, confidences = split_confidence_block(f"{CORRECTED}\n{CONFIDENCE_MARKER}\n")
        assert text == CORRECTED
        assert confidences == {}

    def test_values_are_clamped_to_unit_range(self):
        """模型偶爾回百分比或超界值,放行會讓下游門檻判斷失準"""
        _, confidences = split_confidence_block(
            f'x\n{CONFIDENCE_MARKER}\n{{"a": 95, "b": -3, "c": 0.5}}'
        )
        assert confidences == {"a": 1.0, "b": 0.0, "c": 0.5}

    def test_non_numeric_values_are_dropped(self):
        _, confidences = split_confidence_block(
            f'x\n{CONFIDENCE_MARKER}\n{{"a": "高", "b": null, "c": true, "d": 0.7}}'
        )
        assert confidences == {"d": 0.7}


# ====================================================================== #
# 提示詞
# ====================================================================== #
class TestPrompt:
    def test_no_labels_means_prompt_unchanged(self):
        """未索取信心度時提示詞與 8.3 版本逐字相同"""
        assert build_correction_prompt(OCR_TEXT, has_image=False) == \
            build_correction_prompt(OCR_TEXT, has_image=False, field_labels=None)

    def test_labels_add_the_confidence_section(self):
        prompt = build_correction_prompt(OCR_TEXT, has_image=True, field_labels=LABELS)
        assert CONFIDENCE_MARKER in prompt
        assert "地號" in prompt and "所有權人" in prompt

    def test_instruction_caps_inferred_fields(self):
        """只憑上下文推測的欄位不得回報高信心度"""
        instruction = build_confidence_instruction(LABELS)
        assert "0.5" in instruction
        assert "找不到該欄位時,信心度填 0.0" in instruction


# ====================================================================== #
# 三條路徑
# ====================================================================== #
class TestThreePaths:
    @pytest.mark.asyncio
    async def test_dual_modal_returns_field_confidences(self, dual_on, confidence_on):
        provider = _FakeProvider(WITH_CONFIDENCE)
        result = await DualModalCorrector(provider).correct(
            OCR_TEXT, image_data=VALID_B64, field_labels=LABELS
        )

        assert result["modality"] == "dual"
        assert result["field_confidences"] == {"land_number": 0.92, "owner": 0.4}
        assert result["text"] == CORRECTED

    @pytest.mark.asyncio
    async def test_text_only_degradation_still_returns_confidences(
        self, dual_on, confidence_on
    ):
        """降級為純文字不代表放棄信心度回報"""
        provider = _FakeProvider(WITH_CONFIDENCE)
        result = await DualModalCorrector(provider).correct(
            OCR_TEXT, image_data=None, field_labels=LABELS
        )

        assert result["modality"] == "text_only"
        assert result["degraded_reason"] is not None
        assert result["field_confidences"]["land_number"] == 0.92

    @pytest.mark.asyncio
    async def test_refusal_reports_no_confidence(self, dual_off, confidence_on):
        """模型拒絕時保留原文,且不得附帶任何信心度——那會是憑空的數字"""
        provider = _FakeProvider("抱歉，我無法處理這份文件。")
        result = await DualModalCorrector(provider).correct(
            OCR_TEXT, field_labels=LABELS
        )

        assert result["refused"] is True
        assert result["text"] == OCR_TEXT
        assert result["field_confidences"] == {}


class TestGating:
    @pytest.mark.asyncio
    async def test_disabled_flag_requests_no_confidence(self, dual_off, confidence_off):
        provider = _FakeProvider(WITH_CONFIDENCE)
        result = await DualModalCorrector(provider).correct(
            OCR_TEXT, field_labels=LABELS
        )

        assert CONFIDENCE_MARKER not in provider.calls[0]["prompt"]
        assert result["field_confidences"] == {}
        # 未索取時整段回應即正文,不做切分
        assert result["text"] == WITH_CONFIDENCE

    @pytest.mark.asyncio
    async def test_no_labels_requests_no_confidence(self, dual_off, confidence_on):
        """沒有欄位清單就沒有東西可回報——請模型自行決定欄位等於放任它編"""
        provider = _FakeProvider(CORRECTED)
        result = await DualModalCorrector(provider).correct(OCR_TEXT, field_labels=None)

        assert CONFIDENCE_MARKER not in provider.calls[0]["prompt"]
        assert result["field_confidences"] == {}

    @pytest.mark.asyncio
    async def test_unrequested_fields_are_not_trusted(self, dual_off, confidence_on):
        """模型自行加碼的欄位不採信"""
        provider = _FakeProvider(
            f'{CORRECTED}\n{CONFIDENCE_MARKER}\n'
            '{"land_number": 0.9, "made_up_field": 0.99}'
        )
        result = await DualModalCorrector(provider).correct(
            OCR_TEXT, field_labels=LABELS
        )

        assert result["field_confidences"] == {"land_number": 0.9}


# ====================================================================== #
# 併入既有信心度:只能收緊,不得放寬
# ====================================================================== #
class TestMergeOnlyTightens:
    def test_lower_correction_confidence_wins(self):
        merged = OcrDocumentProcessor._apply_correction_confidences(
            {"field_confidences": {"land_number": 0.9}},
            {"land_number": 0.3},
        )
        assert merged["field_confidences"]["land_number"] == 0.3

    def test_higher_correction_confidence_cannot_raise(self):
        """模型自評不可用來抬高——本規格的核心論點正是自評不可信"""
        merged = OcrDocumentProcessor._apply_correction_confidences(
            {"field_confidences": {"land_number": 0.3}},
            {"land_number": 0.95},
        )
        assert merged["field_confidences"]["land_number"] == 0.3

    def test_new_field_is_added_as_is(self):
        merged = OcrDocumentProcessor._apply_correction_confidences(
            {"field_confidences": {"owner": 0.8}},
            {"land_number": 0.6},
        )
        assert merged["field_confidences"] == {"owner": 0.8, "land_number": 0.6}

    def test_no_correction_confidences_leaves_data_untouched(self):
        original = {"field_confidences": {"owner": 0.8}}
        assert OcrDocumentProcessor._apply_correction_confidences(original, None) is original
        assert OcrDocumentProcessor._apply_correction_confidences(original, {}) is original

    def test_missing_structured_data_is_safe(self):
        assert OcrDocumentProcessor._apply_correction_confidences(None, {"a": 0.1}) is None
