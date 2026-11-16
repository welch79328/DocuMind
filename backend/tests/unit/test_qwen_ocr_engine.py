"""
OCR 引擎 qwen(transcript-qwen-read,plan §5、acceptance A7)

不連外:Bedrock 以 httpx.MockTransport 取代(_llm_fakes.install_bedrock),
另以 socket 封鎖(no_network)確認沒有任何連線。

  解析、座標夾值                        → TestParse
  兩種全文接法                          → TestLayouts
  信心度                                → TestEngineResult
  送出內容、llm_calls stage=ocr_read    → TestRunQwen
  Bedrock 失敗 → ("",0.0,[]),不退回本機 OCR(R6、A7) → TestFailureNeverFallsBack
  LLM_CLOUD_ENABLED=false 不外送        → TestCloudGuard
  qwen 不進 OCR 閘門、有自己的上限       → TestGates
  設定與設定衝突                         → TestConfig
"""

import asyncio
import base64
import io
import json
import logging
from types import SimpleNamespace

import httpx
import numpy as np
import pytest
from PIL import Image

from _llm_fakes import (
    ARN_BODY,
    FAKE_BEDROCK_KEY,
    BedrockRecorder,
    bedrock_ok,
    install_bedrock,
    no_network,  # noqa: F401  (pytest fixture)
)
from app.config import Settings, settings
from app.config_conflicts import check_setting_conflicts
from app.lib.llm_service.call_log import STAGE_OCR_READ, collect_llm_calls
from app.lib.ocr_enhanced import engine_manager as em_mod
from app.lib.ocr_enhanced.config import EngineConfig, validate_engine_config
from app.lib.ocr_enhanced.engine_manager import (
    QWEN_OCR_CONFIDENCE,
    QWEN_OCR_PROMPT,
    EngineManager,
    QwenOcrError,
    _encode_qwen_image,
    build_qwen_engine_result,
)
from app.lib.ocr_enhanced.qwen_layout import (
    build_full_text,
    full_text_variants,
    join_text,
    parse_qwen_lines,
    rebuild_text,
)

# 2026-11-09 評估 C2 的 prompt 原文(run_qwen_grounded.py PROMPT),逐字釘住
EVAL_C2_PROMPT = (
    "這是一頁台灣不動產登記謄本的照片或掃描影像。請找出頁面上印的每一段文字（一個文字片段＝同一行中連續、沒有大空白隔開的字），"
    "依閱讀順序逐段輸出，每段一行 JSON：{\"bbox_2d\": [x1, y1, x2, y2], \"text\": \"...\"}，座標用 0–1000 的相對座標（相對整張圖）。\n"
    "- 同一行左右兩欄是兩段，各自輸出。\n- 文字照原文逐字抄，冒號、星號、括號、「(空白)」照抄，不補字、不改寫。\n"
    "- 浮水印底紋、印章、QR code 不要輸出。\n只輸出 JSON 行，不要任何說明。"
)

BGR = np.full((40, 60, 3), 255, dtype=np.uint8)

SEGMENTS = "\n".join([
    '{"bbox_2d": [100, 100, 300, 140], "text": "土地標示部"}',
    '{"bbox_2d": [100, 200, 260, 240], "text": "地號：0123-0000"}',
    '{"bbox_2d": [600, 200, 760, 240], "text": "面積：*****100.00平方公尺"}',
])


def _reset_gates():
    em_mod._ocr_gate = None
    em_mod._ocr_gate_limit = -1
    em_mod._qwen_gate = None
    em_mod._qwen_gate_limit = -1
    em_mod._qwen_gate_loop = None


@pytest.fixture(autouse=True)
def _fresh_gates():
    _reset_gates()
    yield
    _reset_gates()


@pytest.fixture
def no_local_ocr(monkeypatch):
    """任何本機 OCR(PaddleOCR 載入或執行、tesseract)被呼叫就記下;測試結束斷言一次都沒有。"""
    called = []

    async def _boom_async(self, _img):
        called.append("run")
        raise AssertionError("不得退回本機 OCR")

    def _boom_sync(self):
        called.append("ensure_paddleocr")
        raise AssertionError("不得載入 PaddleOCR")

    monkeypatch.setattr(EngineManager, "_run_paddleocr", _boom_async)
    monkeypatch.setattr(EngineManager, "_run_tesseract", _boom_async)
    monkeypatch.setattr(EngineManager, "_ensure_paddleocr", _boom_sync)
    yield called
    assert called == [], f"qwen 失敗時退回了本機 OCR:{called}"


# --------------------------------------------------------------------------- #
# 解析
# --------------------------------------------------------------------------- #
class TestParse:
    def test_normal_segments_become_ratio_boxes_in_reply_order(self):
        lines = parse_qwen_lines(SEGMENTS)
        assert lines == [
            {"text": "土地標示部", "box": [0.1, 0.1, 0.3, 0.14]},
            {"text": "地號：0123-0000", "box": [0.1, 0.2, 0.26, 0.24]},
            {"text": "面積：*****100.00平方公尺", "box": [0.6, 0.2, 0.76, 0.24]},
        ]

    def test_explanation_and_markdown_fence_are_ignored(self):
        raw = "好的,以下是結果:\n```json\n" + SEGMENTS + "\n```\n以上共三段。"
        assert [l["text"] for l in parse_qwen_lines(raw)] == [
            "土地標示部", "地號：0123-0000", "面積：*****100.00平方公尺",
        ]

    def test_broken_json_segment_is_skipped_others_kept(self):
        raw = (
            '{"bbox_2d": [1, 2, 3, 4], "text": "好"}\n'
            '{"bbox_2d": [1, 2, 3, 4], "text": "壞" ,,}\n'
            '{"bbox_2d": [1, 2, 3], "text": "三個座標"}\n'
            '{"bbox_2d": [1, "x", 3, 4], "text": "座標不是數字"}\n'
            '{"bbox_2d": [5, 6, 7, 8], "text": "也好"}'
        )
        assert [l["text"] for l in parse_qwen_lines(raw)] == ["好", "也好"]

    def test_braces_inside_text_are_kept(self):
        # 2026-11-16 S1:整頁一段、內文抄到 `{` 時,舊正規式 [^{}]* 整頁 0 段
        raw = (
            '{"bbox_2d": [0, 0, 1000, 1000], "text": "建號：{19998-000\\n面積}:12.00"}\n'
            '{"bbox_2d": [5, 6, 7, 8], "text": "下一段"}'
        )
        assert [l["text"] for l in parse_qwen_lines(raw)] == [
            "建號：{19998-000\n面積}:12.00", "下一段",
        ]

    def test_wrapped_segments_are_found(self):
        raw = '{"lines": [{"bbox_2d": [1, 2, 3, 4], "text": "包在裡面"}]}'
        assert [l["text"] for l in parse_qwen_lines(raw)] == ["包在裡面"]

    @pytest.mark.parametrize("bbox_json", ['"1234"', "1234", "null", '{"a": 1}'])
    def test_bbox_not_a_list_is_skipped(self, bbox_json):
        assert parse_qwen_lines('{"bbox_2d": ' + bbox_json + ', "text": "怪"}') == []

    @pytest.mark.parametrize("text_json", ['""', '"   "', "null", "123", '["a"]'])
    def test_empty_or_non_string_text_is_skipped(self, text_json):
        raw = '{"bbox_2d": [1, 2, 3, 4], "text": ' + text_json + "}"
        assert parse_qwen_lines(raw) == []

    def test_missing_text_is_skipped(self):
        assert parse_qwen_lines('{"bbox_2d": [1, 2, 3, 4]}') == []

    def test_text_is_kept_verbatim(self):
        lines = parse_qwen_lines('{"bbox_2d": [1, 2, 3, 4], "text": " (空白) "}')
        assert lines[0]["text"] == " (空白) "

    def test_out_of_range_coordinates_are_clamped(self):
        lines = parse_qwen_lines('{"bbox_2d": [-50, -1, 1200, 1000.5], "text": "越界"}')
        assert lines[0]["box"] == [0.0, 0.0, 1.0, 1.0]

    def test_reversed_corners_are_ordered(self):
        lines = parse_qwen_lines('{"bbox_2d": [800, 900, 200, 100], "text": "反了"}')
        assert lines[0]["box"] == [0.2, 0.1, 0.8, 0.9]

    @pytest.mark.parametrize("coords", ["[NaN, 1, 2, 3]", "[1, Infinity, 2, 3]", "[1, 2, 3, " + "9" * 400 + "]"])
    def test_non_finite_coordinates_are_skipped(self, coords):
        assert parse_qwen_lines('{"bbox_2d": ' + coords + ', "text": "怪"}') == []

    @pytest.mark.parametrize("raw", [None, "", "沒有任何 JSON", "{}", '[{"text": "沒框"}]'])
    def test_nothing_parsable_gives_empty_list(self, raw):
        assert parse_qwen_lines(raw) == []


# --------------------------------------------------------------------------- #
# 全文接法
# --------------------------------------------------------------------------- #
class TestLayouts:
    def test_join_is_reply_order_one_segment_per_line(self):
        lines = parse_qwen_lines(SEGMENTS)
        assert join_text(lines) == "土地標示部\n地號：0123-0000\n面積：*****100.00平方公尺"

    def test_rebuild_puts_same_row_segments_on_one_line_with_indent(self):
        lines = parse_qwen_lines(SEGMENTS)
        text = rebuild_text(lines)
        rows = text.split("\n")
        assert len(rows) == 2
        assert rows[0].strip() == "土地標示部"
        assert rows[1].lstrip().startswith("地號：0123-0000")
        assert rows[1].endswith("面積：*****100.00平方公尺")
        # 兩欄之間至少兩個空白;左欄起點 x=0.1 → 有縮排
        assert "  面積" in rows[1]
        assert rows[0].startswith(" ") and rows[1].startswith(" ")

    def test_rebuild_matches_eval_reference_output(self):
        """與評估 rebuild_only.rebuild() 同一份輸入的輸出(手算釘住)"""
        lines = [
            {"text": "甲乙", "box": [0.0, 0.0, 0.1, 0.05]},
            {"text": "丙", "box": [0.2, 0.0, 0.25, 0.05]},
            {"text": "丁戊", "box": [0.1, 0.1, 0.2, 0.15]},
        ]
        # unit = median(0.1/4, 0.05/2, 0.1/4) = 0.025;丙 col=8、丁戊 col=4
        assert rebuild_text(lines) == "甲乙    丙\n    丁戊"

    def test_rebuild_does_not_mutate_input_order(self):
        lines = parse_qwen_lines(SEGMENTS)[::-1]
        before = [l["text"] for l in lines]
        rebuild_text(lines)
        assert [l["text"] for l in lines] == before

    def test_rebuild_survives_zero_width_boxes(self):
        lines = [
            {"text": "甲", "box": [1.0, 0.1, 1.0, 0.2]},
            {"text": "乙", "box": [1.0, 0.1, 1.0, 0.2]},
        ]
        assert rebuild_text(lines) == "甲  乙"

    def test_empty_lines_give_empty_text(self):
        assert rebuild_text([]) == "" and join_text([]) == ""

    def test_variants_from_same_lines(self):
        lines = parse_qwen_lines(SEGMENTS)
        variants = full_text_variants(lines)
        assert variants == {"rebuild": rebuild_text(lines), "join": join_text(lines)}

    def test_unknown_layout_is_rejected(self):
        with pytest.raises(ValueError):
            build_full_text(parse_qwen_lines(SEGMENTS), "fancy")


# --------------------------------------------------------------------------- #
# 引擎結果與信心度
# --------------------------------------------------------------------------- #
class TestEngineResult:
    def test_lines_give_fixed_confidence(self):
        lines = parse_qwen_lines(SEGMENTS)
        result = build_qwen_engine_result(lines, "join", 123)
        assert result == {
            "engine": "qwen",
            "text": join_text(lines),
            "confidence": QWEN_OCR_CONFIDENCE,
            "processing_time_ms": 123,
            "lines": lines,
        }
        assert QWEN_OCR_CONFIDENCE == 0.9

    def test_zero_segments_give_empty_text_and_zero_confidence(self):
        result = build_qwen_engine_result([], "rebuild", 5)
        assert result["text"] == "" and result["confidence"] == 0.0 and result["lines"] == []


# --------------------------------------------------------------------------- #
# 影像編碼
# --------------------------------------------------------------------------- #
def _decode_data_uri(uri: str) -> Image.Image:
    assert uri.startswith("data:image/jpeg;base64,")
    return Image.open(io.BytesIO(base64.b64decode(uri.split(",", 1)[1])))


class TestImageEncoding:
    def test_bgr_is_sent_as_rgb_jpeg(self):
        bgr = np.zeros((50, 80, 3), dtype=np.uint8)
        bgr[:, :, 2] = 255                       # BGR 的紅
        img = _decode_data_uri(_encode_qwen_image(bgr))
        assert img.format == "JPEG" and img.mode == "RGB" and img.size == (80, 50)
        r, g, b = img.getpixel((40, 25))
        assert r > 200 and g < 60 and b < 60

    def test_gray_and_bgra_are_accepted(self):
        assert _decode_data_uri(_encode_qwen_image(np.full((30, 30), 128, np.uint8))).mode == "RGB"
        assert _decode_data_uri(_encode_qwen_image(np.zeros((30, 30, 4), np.uint8))).mode == "RGB"

    def test_long_edge_is_capped_at_2000(self):
        img = _decode_data_uri(_encode_qwen_image(np.zeros((1500, 3000, 3), np.uint8)))
        assert max(img.size) == 2000


# --------------------------------------------------------------------------- #
# 正常呼叫
# --------------------------------------------------------------------------- #
class TestRunQwen:
    @pytest.fixture
    def bedrock(self, monkeypatch, no_network):
        return install_bedrock(monkeypatch, BedrockRecorder(default=bedrock_ok(SEGMENTS)))

    def test_prompt_is_eval_c2_verbatim(self):
        assert QWEN_OCR_PROMPT == EVAL_C2_PROMPT

    async def test_request_carries_prompt_image_and_limits(self, monkeypatch, bedrock, no_local_ocr):
        monkeypatch.setattr(settings, "QWEN_OCR_TEXT_LAYOUT", "join")
        em = EngineManager(engines=["qwen"])
        text, confidence, results = await em.extract_text_multi_engine(BGR)

        assert len(bedrock.requests) == 1
        body = bedrock.bodies[0]
        assert body["model"] == "qwen.qwen3-vl-235b-a22b"
        assert body["max_tokens"] == 8000
        assert body["temperature"] == 0.0
        content = body["messages"][0]["content"]
        assert content[0] == {"type": "text", "text": EVAL_C2_PROMPT}
        assert content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")

        lines = parse_qwen_lines(SEGMENTS)
        assert text == join_text(lines)
        assert confidence == 0.9
        assert results == [{
            "engine": "qwen", "text": join_text(lines), "confidence": 0.9,
            "processing_time_ms": results[0]["processing_time_ms"], "lines": lines,
        }]

    @pytest.mark.parametrize("layout", ["rebuild", "join"])
    async def test_text_follows_layout_setting(self, monkeypatch, bedrock, layout):
        monkeypatch.setattr(settings, "QWEN_OCR_TEXT_LAYOUT", layout)
        text, _c, results = await EngineManager(engines=["qwen"]).extract_text_multi_engine(BGR)
        assert text == build_full_text(parse_qwen_lines(SEGMENTS), layout)
        assert results[0]["lines"] == parse_qwen_lines(SEGMENTS)   # 行框兩種接法都一樣

    async def test_llm_calls_records_stage_ocr_read(self, bedrock):
        with collect_llm_calls() as calls:
            await EngineManager(engines=["qwen"]).extract_text_multi_engine(BGR)
        assert STAGE_OCR_READ == "ocr_read"
        assert [(c["stage"], c["provider"], c["model"], c["ok"]) for c in calls] == [
            ("ocr_read", "bedrock", "qwen.qwen3-vl-235b-a22b", True)
        ]


# --------------------------------------------------------------------------- #
# 失敗:空結果、不退回本機 OCR(R6、A7)
# --------------------------------------------------------------------------- #
class TestFailureNeverFallsBack:
    async def _run(self, monkeypatch, replies, default=None):
        recorder = install_bedrock(monkeypatch, BedrockRecorder(replies=replies, default=default))
        with collect_llm_calls() as calls:
            out = await EngineManager(engines=["qwen"]).extract_text_multi_engine(BGR)
        return out, recorder, calls

    async def test_http_error_gives_empty_page(self, monkeypatch, no_network, no_local_ocr):
        out, recorder, calls = await self._run(monkeypatch, [(403, ARN_BODY)])
        assert out == ("", 0.0, [])
        assert len(recorder.requests) == 1
        assert [(c["stage"], c["ok"], c["error"]) for c in calls] == [("ocr_read", False, "http_403")]

    async def test_timeout_twice_gives_empty_page(self, monkeypatch, no_network, no_local_ocr):
        timeout = httpx.ReadTimeout("slow")
        out, recorder, calls = await self._run(monkeypatch, [timeout, timeout])
        assert out == ("", 0.0, [])
        assert [c["requested_service_tier"] for c in calls] == ["flex", "default"]
        assert all(c["stage"] == "ocr_read" and c["error"] == "timeout" for c in calls)

    async def test_invalid_response_gives_empty_page(self, monkeypatch, no_network, no_local_ocr):
        out, _r, _c = await self._run(monkeypatch, [(200, {"unexpected": True})])
        assert out == ("", 0.0, [])

    @pytest.mark.parametrize("content", ["", "抱歉,我看不清楚。", '{"bbox_2d": [1,2,3,4], "text": ""}'])
    async def test_zero_segments_gives_empty_page(self, monkeypatch, no_network, no_local_ocr, content):
        out, _r, _c = await self._run(monkeypatch, [], default=bedrock_ok(content))
        assert out == ("", 0.0, [])

    async def test_missing_key_gives_empty_page_without_sending(self, monkeypatch, no_network, no_local_ocr):
        recorder = install_bedrock(monkeypatch, BedrockRecorder())
        monkeypatch.setattr(settings, "BEDROCK_API_KEY", None)
        out = await EngineManager(engines=["qwen"]).extract_text_multi_engine(BGR)
        assert out == ("", 0.0, []) and recorder.requests == []

    async def test_run_qwen_raises_category_only(self, monkeypatch, no_network):
        install_bedrock(monkeypatch, BedrockRecorder(replies=[(403, ARN_BODY)]))
        with pytest.raises(QwenOcrError) as excinfo:
            await EngineManager(engines=["qwen"])._run_qwen(BGR)
        assert excinfo.value.category == "http_403"
        assert excinfo.value.__cause__ is None and excinfo.value.__suppress_context__

    async def test_logs_and_prints_never_contain_reply_or_aws_body(
        self, monkeypatch, no_network, caplog, capsys
    ):
        secret_text = "所有權人:王小明 身分證 A123456789"
        replies = [(403, ARN_BODY)]
        install_bedrock(monkeypatch, BedrockRecorder(replies=replies))
        caplog.set_level(logging.DEBUG)
        await EngineManager(engines=["qwen"]).extract_text_multi_engine(BGR)
        # 第二種失敗:模型回了內容但 0 段
        _reset_gates()
        install_bedrock(monkeypatch, BedrockRecorder(default=bedrock_ok(secret_text)))
        await EngineManager(engines=["qwen"]).extract_text_multi_engine(BGR)

        printed = capsys.readouterr()
        everything = caplog.text + printed.out + printed.err
        assert "arn:aws" not in everything
        assert "王小明" not in everything and "A123456789" not in everything
        assert FAKE_BEDROCK_KEY not in everything
        assert "base64" not in everything
        assert "http_403" in everything and "no_segments" in everything

    async def test_qwen_failure_in_mixed_mode_keeps_local_result(self, monkeypatch, no_network):
        """混用時 qwen 失敗只是少一個候選,本機引擎的結果照用(不是退回,是本來就有跑)"""
        install_bedrock(monkeypatch, BedrockRecorder(replies=[(500, {})]))
        em = EngineManager(engines=["paddleocr", "qwen"], parallel=False)

        async def fake_paddle(_img):
            return {"engine": "paddleocr", "text": "本機", "confidence": 0.8,
                    "processing_time_ms": 1, "lines": None}

        monkeypatch.setattr(em, "_run_paddleocr", fake_paddle)
        text, conf, results = await em.extract_text_multi_engine(BGR)
        assert (text, conf) == ("本機", 0.8) and [r["engine"] for r in results] == ["paddleocr"]


# --------------------------------------------------------------------------- #
# 個資閘門:LLM_CLOUD_ENABLED=false 不外送
# --------------------------------------------------------------------------- #
class TestCloudGuard:
    async def test_cloud_disabled_sends_nothing_and_returns_empty(
        self, monkeypatch, no_network, no_local_ocr, caplog
    ):
        recorder = install_bedrock(monkeypatch, BedrockRecorder(default=bedrock_ok(SEGMENTS)))
        monkeypatch.setattr(settings, "LLM_CLOUD_ENABLED", False)
        encoded = []
        monkeypatch.setattr(em_mod, "_encode_qwen_image", lambda img: encoded.append(1) or "x")
        caplog.set_level(logging.WARNING)
        with collect_llm_calls() as calls:
            out = await EngineManager(engines=["qwen"]).extract_text_multi_engine(BGR)
        assert out == ("", 0.0, [])
        assert recorder.requests == [], "雲端關閉時不得送出任何請求"
        assert encoded == [], "雲端關閉時連影像都不該編碼"
        assert calls == []
        assert "cloud_disabled" in caplog.text


# --------------------------------------------------------------------------- #
# 閘門
# --------------------------------------------------------------------------- #
class TestGates:
    async def test_qwen_only_never_touches_ocr_gate(self, monkeypatch, no_network, no_local_ocr):
        install_bedrock(monkeypatch, BedrockRecorder(default=bedrock_ok(SEGMENTS)))

        def _forbidden():
            raise AssertionError("qwen-only 不得進 PaddleOCR 的記憶體閘門")

        monkeypatch.setattr(em_mod, "_get_ocr_gate", _forbidden)
        text, conf, _ = await EngineManager(engines=["qwen"]).extract_text_multi_engine(BGR)
        assert text and conf == 0.9

    async def test_qwen_concurrency_is_capped_by_its_own_setting(self, monkeypatch):
        monkeypatch.setattr(settings, "OCR_MAX_CONCURRENT", 1)
        monkeypatch.setattr(settings, "QWEN_OCR_MAX_CONCURRENT", 2)
        tracker = {"live": 0, "peak": 0}

        async def fake_qwen(_img):
            tracker["live"] += 1
            tracker["peak"] = max(tracker["peak"], tracker["live"])
            await asyncio.sleep(0.05)
            tracker["live"] -= 1
            raise QwenOcrError("fake")

        em = EngineManager(engines=["qwen"])
        monkeypatch.setattr(em, "_run_qwen", fake_qwen)
        await asyncio.gather(*(em.extract_text_multi_engine(BGR) for _ in range(6)))
        assert tracker["peak"] == 2, f"上限 2,實際峰值 {tracker['peak']}"

    async def test_default_qwen_limit_is_four_and_exceeds_ocr_gate(self, monkeypatch):
        monkeypatch.setattr(settings, "OCR_MAX_CONCURRENT", 1)
        tracker = {"live": 0, "peak": 0}

        async def fake_qwen(_img):
            tracker["live"] += 1
            tracker["peak"] = max(tracker["peak"], tracker["live"])
            await asyncio.sleep(0.05)
            tracker["live"] -= 1
            raise QwenOcrError("fake")

        em = EngineManager(engines=["qwen"])
        monkeypatch.setattr(em, "_run_qwen", fake_qwen)
        await asyncio.gather(*(em.extract_text_multi_engine(BGR) for _ in range(8)))
        assert settings.QWEN_OCR_MAX_CONCURRENT == 4 and tracker["peak"] == 4

    async def test_mixed_local_engines_stay_behind_ocr_gate_qwen_does_not(self, monkeypatch):
        monkeypatch.setattr(settings, "OCR_MAX_CONCURRENT", 1)
        monkeypatch.setattr(settings, "QWEN_OCR_MAX_CONCURRENT", 4)
        paddle = {"live": 0, "peak": 0}
        qwen = {"live": 0, "peak": 0}

        def probe(tracker, engine):
            async def run(_img):
                tracker["live"] += 1
                tracker["peak"] = max(tracker["peak"], tracker["live"])
                await asyncio.sleep(0.05)
                tracker["live"] -= 1
                return {"engine": engine, "text": engine, "confidence": 0.5,
                        "processing_time_ms": 1, "lines": None}
            return run

        em = EngineManager(engines=["paddleocr", "tesseract", "qwen"], parallel=False)
        monkeypatch.setattr(em, "_run_paddleocr", probe(paddle, "paddleocr"))
        monkeypatch.setattr(em, "_run_tesseract", probe(paddle, "tesseract"))
        monkeypatch.setattr(em, "_run_qwen", probe(qwen, "qwen"))
        outs = await asyncio.gather(*(em.extract_text_multi_engine(BGR) for _ in range(3)))
        assert paddle["peak"] == 1, "本機引擎必須照舊受 OCR 閘門約束"
        assert qwen["peak"] == 3, "qwen 不得被 OCR 閘門序列化"
        assert all([r["engine"] for r in out[2]] == ["paddleocr", "tesseract", "qwen"] for out in outs)

    async def test_mixed_mode_enters_ocr_gate(self, monkeypatch):
        entered = []
        real = em_mod._get_ocr_gate

        def counting():
            entered.append(1)
            return real()

        monkeypatch.setattr(em_mod, "_get_ocr_gate", counting)

        async def ok(engine):
            async def run(_img):
                return {"engine": engine, "text": engine, "confidence": 0.5,
                        "processing_time_ms": 1, "lines": None}
            return run

        em = EngineManager(engines=["paddleocr", "qwen"])
        monkeypatch.setattr(em, "_run_paddleocr", await ok("paddleocr"))
        monkeypatch.setattr(em, "_run_qwen", await ok("qwen"))
        await em.extract_text_multi_engine(BGR)
        assert entered == [1]

    def test_gate_is_rebuilt_per_event_loop(self, monkeypatch):
        async def grab():
            return em_mod._get_qwen_gate()

        first = asyncio.run(grab())
        second = asyncio.run(grab())
        assert first is not second


# --------------------------------------------------------------------------- #
# 設定
# --------------------------------------------------------------------------- #
class TestConfig:
    def test_defaults(self):
        assert Settings.model_fields["OCR_ENGINES"].default == ["paddleocr", "tesseract"]
        assert Settings.model_fields["QWEN_OCR_MAX_CONCURRENT"].default == 4
        assert Settings.model_fields["QWEN_OCR_TEXT_LAYOUT"].default == "join"

    def test_env_can_select_qwen_only(self, monkeypatch):
        monkeypatch.setenv("OCR_ENGINES", '["qwen"]')
        monkeypatch.setenv("QWEN_OCR_TEXT_LAYOUT", "rebuild")
        s = Settings(_env_file=None)
        assert s.OCR_ENGINES == ["qwen"] and s.QWEN_OCR_TEXT_LAYOUT == "rebuild"

    def test_unknown_layout_is_rejected_at_startup(self, monkeypatch):
        monkeypatch.setenv("QWEN_OCR_TEXT_LAYOUT", "fancy")
        with pytest.raises(Exception):
            Settings(_env_file=None)

    def test_engine_config_accepts_qwen(self):
        validate_engine_config(EngineConfig(engines=["qwen"]))
        validate_engine_config(EngineConfig(engines=["paddleocr", "qwen"]))
        with pytest.raises(ValueError):
            validate_engine_config(EngineConfig(engines=["qwen_vl"]))

    @staticmethod
    def _s(**kw):
        base = dict(OCR_ENGINES=["paddleocr"], LLM_CLOUD_ENABLED=True)
        base.update(kw)
        return SimpleNamespace(**base)

    def test_conflict_when_qwen_but_cloud_disabled(self):
        warnings = check_setting_conflicts(self._s(OCR_ENGINES=["qwen"], LLM_CLOUD_ENABLED=False))
        assert len(warnings) == 1
        assert "qwen" in warnings[0] and "LLM_CLOUD_ENABLED=false" in warnings[0]

    @pytest.mark.parametrize("engines,cloud", [
        (["qwen"], True),
        (["paddleocr"], False),
        (["paddleocr", "tesseract"], False),
    ])
    def test_no_conflict_otherwise(self, engines, cloud):
        assert check_setting_conflicts(self._s(OCR_ENGINES=engines, LLM_CLOUD_ENABLED=cloud)) == []

    def test_conflict_is_logged_at_startup(self, caplog):
        from app.config_conflicts import log_setting_conflicts

        caplog.set_level(logging.WARNING)
        log_setting_conflicts(self._s(OCR_ENGINES=["qwen"], LLM_CLOUD_ENABLED=False))
        assert "qwen" in caplog.text and caplog.records[-1].levelno == logging.WARNING

    def test_paddleocr_preload_is_skipped_for_qwen_only(self):
        """main.py 預載條件是 `"paddleocr" in settings.OCR_ENGINES`;qwen-only 不預載"""
        import inspect

        from app import main

        src = inspect.getsource(main.lifespan)
        assert '"paddleocr" in settings.OCR_ENGINES' in src
