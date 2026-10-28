"""
Bedrock 供應商(bedrock-qwen-documind S1;acceptance.md A7 ③④⑤⑥⑩)

不連外:Bedrock 以 httpx.MockTransport 取代,另以 socket 封鎖確認沒有任何連線。

  A7 ③ 雲端關閉時 Bedrock 被擋(含直接建立類別)   → TestA7_3_CloudGuard
  A7 ④ model ID 帶 jp./global. 報錯                → TestA7_4_RegionLockedModelId
  A7 ⑤ flex;429/503/逾時只以 default 重送一次、不改送 OpenAI → TestA7_5_FlexThenDefaultOnce
  A7 ⑥ 影像 ≤3.75MB,超過時同尺寸 JPEG 重新編碼(單元層) → TestA7_6_ImageSizeLimit
  A7 ⑩ 成本表含 Qwen flex/default                  → TestA7_10_Pricing
"""

import base64
import io
import logging

import httpx
import pytest
from PIL import Image
from pydantic import SecretStr

from _llm_fakes import (
    ARN_BODY,
    FAKE_BEDROCK_KEY,
    BedrockRecorder,
    OpenAIRecorder,
    bedrock_ok,
    install_bedrock,
    install_openai,
    no_network,  # noqa: F401  (pytest fixture)
)
from _synthetic_images import noisy_png, synthetic_jpeg
from app.config import Settings, settings
from app.lib.llm_service.call_log import collect_llm_calls, llm_stage
from app.lib.llm_service.providers import (
    BEDROCK_MAX_IMAGE_BYTES,
    CLOUD_PROVIDERS,
    _PRICING,
    BedrockCallError,
    BedrockProvider,
    OpenAIProvider,
    create_provider,
)

ENDPOINT = "https://bedrock-runtime.ap-northeast-1.amazonaws.com/openai/v1/chat/completions"


@pytest.fixture
def bedrock(monkeypatch, no_network):
    return install_bedrock(monkeypatch, BedrockRecorder())


@pytest.fixture
def openai_must_not_be_called(monkeypatch):
    """任何 OpenAI 呼叫都會被記下;測試結束時斷言一次都沒有。"""
    recorder = install_openai(monkeypatch, OpenAIRecorder())
    yield recorder
    assert recorder.calls == [], f"不得改送 OpenAI,實際呼叫了 {len(recorder.calls)} 次"


def _image_from_url(url: str) -> Image.Image:
    header, _, b64 = url.partition(",")
    return Image.open(io.BytesIO(base64.b64decode(b64)))


# --------------------------------------------------------------------------- #
class TestA7_3_CloudGuard:
    def test_bedrock_is_a_cloud_provider(self):
        assert "bedrock" in CLOUD_PROVIDERS

    def test_create_provider_refuses_when_cloud_disabled(self, monkeypatch, no_network):
        monkeypatch.setattr(settings, "LLM_CLOUD_ENABLED", False)
        monkeypatch.setattr(settings, "BEDROCK_API_KEY", SecretStr(FAKE_BEDROCK_KEY))
        with pytest.raises(ValueError, match="個資不外送"):
            create_provider("bedrock")

    def test_direct_class_construction_is_refused_too(self, monkeypatch, no_network):
        """守衛在建構子裡:繞過 create_provider 直接 new 也擋得住(SR-2)"""
        monkeypatch.setattr(settings, "LLM_CLOUD_ENABLED", False)
        monkeypatch.setattr(settings, "BEDROCK_API_KEY", SecretStr(FAKE_BEDROCK_KEY))
        with pytest.raises(ValueError, match="個資不外送"):
            BedrockProvider()
        with pytest.raises(ValueError, match="個資不外送"):
            BedrockProvider(model="qwen.qwen3-vl-235b-a22b")

    def test_routing_to_bedrock_is_blocked_when_cloud_disabled(self, monkeypatch, no_network):
        """分流表指到 bedrock 也一樣被擋:帳單抽取建立 Provider 時就報錯,不會送出任何東西"""
        from app.lib.multi_type_ocr.bill_field_extractor import BillFieldExtractor

        recorder = install_bedrock(monkeypatch, BedrockRecorder())
        monkeypatch.setattr(settings, "LLM_CLOUD_ENABLED", False)
        monkeypatch.setattr(settings, "LLM_PROVIDER_BY_DOCUMENT_TYPE", {"bill": "bedrock"})
        with pytest.raises(ValueError, match="個資不外送"):
            BillFieldExtractor()._default_provider()
        assert recorder.requests == []

    def test_explicit_api_key_is_not_accepted(self, monkeypatch):
        monkeypatch.setattr(settings, "LLM_CLOUD_ENABLED", True)
        with pytest.raises(ValueError, match="只從設定"):
            create_provider("bedrock", api_key="sk-from-caller")


class TestA7_4_RegionLockedModelId:
    @pytest.mark.parametrize("model", [
        "jp.qwen.qwen3-vl-235b-a22b",
        "global.anthropic.claude-sonnet-5",
        "JP.qwen.qwen3-vl-235b-a22b",
        " global.qwen.qwen3-vl-235b-a22b",
    ])
    def test_cross_region_prefix_raises_on_construction(self, monkeypatch, model):
        monkeypatch.setattr(settings, "LLM_CLOUD_ENABLED", True)
        with pytest.raises(ValueError, match="跨區"):
            BedrockProvider(model=model)

    def test_cross_region_prefix_in_settings_raises_via_create_provider(self, monkeypatch):
        monkeypatch.setattr(settings, "LLM_CLOUD_ENABLED", True)
        monkeypatch.setattr(settings, "BEDROCK_MODEL", "jp.qwen.qwen3-vl-235b-a22b")
        with pytest.raises(ValueError, match="跨區"):
            create_provider("bedrock")

    def test_default_model_and_fixed_tokyo_endpoint(self, monkeypatch):
        monkeypatch.setattr(settings, "LLM_CLOUD_ENABLED", True)
        provider = create_provider("bedrock")
        assert provider.model == "qwen.qwen3-vl-235b-a22b"
        assert BedrockProvider.ENDPOINT == (
            "https://bedrock-runtime.ap-northeast-1.amazonaws.com/openai/v1"
        )


# --------------------------------------------------------------------------- #
class TestA7_5_FlexThenDefaultOnce:
    async def test_request_carries_flex_model_endpoint_and_bearer(self, bedrock, openai_must_not_be_called):
        text = await create_provider("bedrock").call("hello", max_tokens=50, temperature=0.1)
        assert text == "{}"
        assert len(bedrock.requests) == 1
        request = bedrock.requests[0]
        assert str(request.url) == ENDPOINT
        assert request.headers["authorization"] == f"Bearer {FAKE_BEDROCK_KEY}"
        body = bedrock.bodies[0]
        assert body["service_tier"] == "flex"
        assert body["model"] == "qwen.qwen3-vl-235b-a22b"
        assert body["max_tokens"] == 50
        assert body["messages"][0]["content"] == "hello"

    @pytest.mark.parametrize("first_failure, category", [
        ((429, {"message": "Too many requests"}), "rate_limited"),
        ((503, {"message": "Service unavailable"}), "unavailable"),
        (httpx.ReadTimeout("read timed out"), "timeout"),
    ])
    async def test_retryable_failure_resends_once_with_default(
        self, monkeypatch, no_network, openai_must_not_be_called, first_failure, category
    ):
        recorder = install_bedrock(
            monkeypatch, BedrockRecorder([first_failure, bedrock_ok("ok", tier="default")])
        )
        with collect_llm_calls() as calls, llm_stage("extraction"):
            text = await create_provider("bedrock").call("hello")

        assert text == "ok"
        assert [b["service_tier"] for b in recorder.bodies] == ["flex", "default"]
        assert {b["model"] for b in recorder.bodies} == {"qwen.qwen3-vl-235b-a22b"}
        assert {str(r.url) for r in recorder.requests} == {ENDPOINT}
        assert calls == [
            {"stage": "extraction", "provider": "bedrock", "model": "qwen.qwen3-vl-235b-a22b",
             "requested_service_tier": "flex", "service_tier": None, "ok": False, "error": category},
            {"stage": "extraction", "provider": "bedrock", "model": "qwen.qwen3-vl-235b-a22b",
             "requested_service_tier": "default", "service_tier": "default", "ok": True, "error": None},
        ]

    async def test_second_failure_raises_after_exactly_two_requests(
        self, monkeypatch, no_network, openai_must_not_be_called
    ):
        recorder = install_bedrock(monkeypatch, BedrockRecorder([
            (429, {"message": "slow down"}),
            (503, {"message": "unavailable"}),
            bedrock_ok("must not be reached"),
        ]))
        with pytest.raises(BedrockCallError) as exc:
            await create_provider("bedrock").call("hello")
        assert exc.value.category == "unavailable"
        assert [b["service_tier"] for b in recorder.bodies] == ["flex", "default"]

    @pytest.mark.parametrize("status", [400, 401, 403, 500])
    async def test_other_errors_are_not_retried(
        self, monkeypatch, no_network, openai_must_not_be_called, status
    ):
        recorder = install_bedrock(monkeypatch, BedrockRecorder([(status, ARN_BODY)]))
        with pytest.raises(BedrockCallError):
            await create_provider("bedrock").call("hello")
        assert len(recorder.requests) == 1
        assert recorder.bodies[0]["service_tier"] == "flex"

    async def test_failure_degrades_extraction_and_never_reaches_openai(
        self, monkeypatch, no_network, openai_must_not_be_called
    ):
        """兩次都失敗 → 帳單抽取走既有降級(規則結果),OpenAI 一次都沒被叫"""
        from app.lib.multi_type_ocr.bill_field_extractor import BillFieldExtractor

        recorder = install_bedrock(monkeypatch, BedrockRecorder([
            httpx.ReadTimeout("t1"), httpx.ReadTimeout("t2"),
        ]))
        monkeypatch.setattr(settings, "LLM_PROVIDER_BY_DOCUMENT_TYPE", {"bill": "bedrock"})
        result = await BillFieldExtractor().extract(
            "戶號: 01-2345-6789", image_data="QUJD", use_llm_fallback=True
        )
        assert len(recorder.requests) == 2
        assert result["account_no"] is not None            # 規則結果保留
        assert result["llm_used_for_extraction"] is False

    def test_timeout_and_retry_budget_are_explicit(self):
        """SR-9:逾時 ≤120 秒;用 httpx(不會自動重試),不經會自己重試的 OpenAI SDK"""
        import inspect

        from app.lib.llm_service import providers

        assert 0 < providers.BEDROCK_TIMEOUT_SECONDS <= 120
        source = inspect.getsource(BedrockProvider)
        assert "AsyncOpenAI" not in source
        assert "httpx.AsyncClient" in source

    async def test_error_message_never_contains_aws_body(self, monkeypatch, no_network, caplog):
        install_bedrock(monkeypatch, BedrockRecorder([(403, ARN_BODY)]))
        with caplog.at_level(logging.DEBUG):
            with pytest.raises(BedrockCallError) as exc:
                await create_provider("bedrock").call("hello")
        assert "arn:" not in str(exc.value)
        assert "123456789012" not in str(exc.value)
        assert "arn:aws" not in caplog.text

    async def test_key_is_never_logged(self, monkeypatch, no_network, caplog):
        install_bedrock(monkeypatch, BedrockRecorder([(429, {}), bedrock_ok()]))
        with caplog.at_level(logging.DEBUG):
            provider = create_provider("bedrock")
            await provider.call("hello")
        assert FAKE_BEDROCK_KEY not in caplog.text
        assert FAKE_BEDROCK_KEY not in repr(settings)
        assert FAKE_BEDROCK_KEY not in repr(vars(provider))

    async def test_missing_key_fails_without_sending(self, monkeypatch, no_network):
        recorder = install_bedrock(monkeypatch, BedrockRecorder())
        monkeypatch.setattr(settings, "BEDROCK_API_KEY", None)
        with collect_llm_calls() as calls:
            with pytest.raises(BedrockCallError) as exc:
                await create_provider("bedrock").call("hello")
        assert exc.value.category == "missing_credentials"
        assert recorder.requests == []
        assert calls[0]["error"] == "missing_credentials"

    def test_key_setting_has_no_default_value(self):
        assert Settings.model_fields["BEDROCK_API_KEY"].default is None


# --------------------------------------------------------------------------- #
class TestA7_6_ImageSizeLimit:
    async def test_small_image_is_sent_exactly_as_the_openai_route_builds_it(self, bedrock):
        b64 = base64.b64encode(synthetic_jpeg(800, 600)).decode()
        await create_provider("bedrock").call("看圖", image_data=b64)
        sent = bedrock.bodies[0]["messages"][0]["content"]
        assert sent == OpenAIProvider._build_content("看圖", b64)

    async def test_oversized_image_is_reencoded_as_same_size_jpeg_q92(self, bedrock):
        png = noisy_png(1200, 1100)
        assert len(png) > BEDROCK_MAX_IMAGE_BYTES, "前置條件:測試影像必須超過 3.75MB"
        await create_provider("bedrock").call("看圖", image_data=base64.b64encode(png).decode())

        url = bedrock.bodies[0]["messages"][0]["content"][1]["image_url"]["url"]
        assert url.startswith("data:image/jpeg;base64,")
        raw = base64.b64decode(url.partition(",")[2])
        assert len(raw) <= BEDROCK_MAX_IMAGE_BYTES
        sent = Image.open(io.BytesIO(raw))
        assert sent.format == "JPEG"
        assert sent.size == (1200, 1100)

    async def test_image_that_cannot_fit_is_rejected_without_resizing(self, monkeypatch, bedrock):
        from app.lib.llm_service import providers

        monkeypatch.setattr(providers, "BEDROCK_MAX_IMAGE_BYTES", 10_000)
        with collect_llm_calls() as calls:
            with pytest.raises(BedrockCallError) as exc:
                await create_provider("bedrock").call(
                    "看圖", image_data=base64.b64encode(noisy_png(300, 300)).decode()
                )
        assert exc.value.category == "image_too_large"
        assert bedrock.requests == []
        assert calls[0]["error"] == "image_too_large"


# --------------------------------------------------------------------------- #
class TestA7_10_Pricing:
    def test_qwen_flex_and_default_prices(self):
        assert _PRICING["qwen.qwen3-vl-235b-a22b#flex"] == (0.32, 1.61)
        assert _PRICING["qwen.qwen3-vl-235b-a22b"] == (0.64, 3.22)

    @pytest.mark.parametrize("tier, expected", [
        ("flex", 1000 * 0.32 / 1e6 + 100 * 1.61 / 1e6),
        ("default", 1000 * 0.64 / 1e6 + 100 * 3.22 / 1e6),
    ])
    async def test_cost_follows_the_tier_reported_by_the_api(self, monkeypatch, no_network, tier, expected):
        install_bedrock(monkeypatch, BedrockRecorder([bedrock_ok(tier=tier)]))
        provider = create_provider("bedrock")
        await provider.call("hello")
        assert provider.stats["estimated_cost"] == pytest.approx(expected)
        assert provider.stats["llm_calls"] == 1


class TestA7_8_ErrorCategoryOnly:
    """llm_calls 的 error 只放類別:就算有人把原始訊息傳進來,也只會記成 error(F7)"""

    def test_raw_message_is_replaced_by_generic_category(self):
        from app.lib.llm_service.call_log import record_llm_call

        with collect_llm_calls() as calls:
            record_llm_call(provider="bedrock", model="m", ok=False,
                            error=ARN_BODY["error"]["message"])
            record_llm_call(provider="bedrock", model="m", ok=False, error="http_403")
            record_llm_call(provider="bedrock", model="m", ok=False, error="http_4031 arn:aws")
        assert [c["error"] for c in calls] == ["error", "http_403", "error"]

    def test_exceptions_are_classified_without_reading_their_message(self):
        import asyncio

        from app.lib.llm_service.call_log import classify_llm_error

        class FakeStatusError(Exception):
            status_code = 403

        class APITimeoutError(Exception):
            pass

        assert classify_llm_error(FakeStatusError(ARN_BODY["error"]["message"])) == "http_403"
        assert classify_llm_error(APITimeoutError("x")) == "timeout"
        assert classify_llm_error(asyncio.TimeoutError()) == "timeout"
        assert classify_llm_error(RuntimeError("arn:aws:iam::123456789012:user/x")) == "error"
        assert classify_llm_error(BedrockCallError("rate_limited", 429, True)) == "rate_limited"
