"""
回應裡的 llm_calls(bedrock-qwen-documind S1;acceptance.md A7 ⑧)

  A7 ⑧ 以 FastAPI TestClient 打 /api/v1/analyze 與 /api/v1/analyze/batch,讀經
       response_model 序列化後的 JSON:每頁都有 llm_calls,內容(階段、供應商、模型、
       實際等級、錯誤類別)正確,錯誤字串不含 ARN

真的跑 AnalyzeService 與各處理器;只替換 OCR 引擎(回固定文字)、S3 上傳、用量記錄
與兩個 LLM 供應商的網路層。OcrPageResult 是 extra="ignore",沒宣告 llm_calls 的話
欄位會在序列化時被丟掉——所以一定要讀 HTTP 回應的 JSON,不能只看服務層的 dict。
"""

import io
import re

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from _llm_fakes import (
    ALL_FOUR_BEDROCK,
    ARN_BODY,
    BedrockRecorder,
    OpenAIRecorder,
    bedrock_ok,
    install_bedrock,
    install_openai,
    no_network,  # noqa: F401  (pytest fixture)
)
from app.config import settings
from app.database import get_db
from app.lib.multi_type_ocr.bill_processor import BillProcessor
from app.lib.multi_type_ocr.transcript_processor import TranscriptProcessor
from app.main import app
from app.services.analyze_service import AnalyzeService

QWEN = "qwen.qwen3-vl-235b-a22b"
CATEGORY = re.compile(r"^(timeout|rate_limited|unavailable|connection_error|invalid_response|"
                      r"missing_credentials|image_too_large|error|http_\d{3})$")


@pytest.fixture(autouse=True)
def _app_stubs(monkeypatch, feedback_session, no_network):
    app.dependency_overrides[get_db] = lambda: feedback_session

    async def _no_upload(self, *args, **kwargs):
        return None

    monkeypatch.setattr(AnalyzeService, "_upload_to_s3", _no_upload)
    monkeypatch.setattr(AnalyzeService, "_record_usage", lambda self, **kwargs: None)

    for cls, text in ((BillProcessor, "戶號: 01-2345-6789"), (TranscriptProcessor, "土地登記第二類謄本")):
        async def _pre(self, image):
            return image

        async def _ocr(self, image, _text=text):
            return _text, 0.5            # 低信心:觸發校正與補欄位

        monkeypatch.setattr(cls, "preprocess", _pre)
        monkeypatch.setattr(cls, "extract_text", _ocr)
    yield
    app.dependency_overrides.pop(get_db, None)


def _jpeg(color="white") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (320, 240), color).save(buf, format="JPEG")
    return buf.getvalue()


def _post(path, files, document_type):
    with TestClient(app) as client:
        return client.post(path, files=files, data={"document_type": document_type, "enable_llm": "true"})


def _assert_no_arn(response):
    text = response.text
    assert "arn:" not in text
    assert "123456789012" not in text
    assert "app-jgb-ai-cs-bedrock" not in text


def _assert_entry_shape(entry):
    assert set(entry) == {
        "stage", "provider", "model", "requested_service_tier", "service_tier", "ok", "error",
    }
    if entry["ok"]:
        assert entry["error"] is None
    else:
        assert CATEGORY.match(entry["error"]), entry["error"]


class TestA7_8_AnalyzeEndpoint:
    def test_bill_on_bedrock_records_flex_retry_and_success(self, monkeypatch):
        """校正:flex 被限流 → default 成功;抽取:flex 成功。三筆都要出現在 JSON 裡"""
        monkeypatch.setattr(settings, "LLM_PROVIDER_BY_DOCUMENT_TYPE", {"bill": "bedrock"})
        recorder = install_bedrock(monkeypatch, BedrockRecorder([
            (429, {"message": "throttled"}),
            bedrock_ok("戶號: 01-2345-6789 校正後", tier="default"),
            bedrock_ok('{"amount": "980"}', tier="flex"),
        ]))
        openai = install_openai(monkeypatch, OpenAIRecorder())

        response = _post("/api/v1/analyze", [("file", ("bill.jpg", _jpeg(), "image/jpeg"))], "bill")

        assert response.status_code == 200, response.text
        page = response.json()["pages"][0]
        assert page["llm_calls"] == [
            {"stage": "correction", "provider": "bedrock", "model": QWEN,
             "requested_service_tier": "flex", "service_tier": None, "ok": False, "error": "rate_limited"},
            {"stage": "correction", "provider": "bedrock", "model": QWEN,
             "requested_service_tier": "default", "service_tier": "default", "ok": True, "error": None},
            {"stage": "extraction", "provider": "bedrock", "model": QWEN,
             "requested_service_tier": "flex", "service_tier": "flex", "ok": True, "error": None},
        ]
        assert page["structured_data"]["llm_used_for_extraction"] is True
        assert [b["service_tier"] for b in recorder.bodies] == ["flex", "default", "flex"]
        assert openai.calls == []

    def test_aws_denial_is_reported_as_category_without_arn(self, monkeypatch):
        monkeypatch.setattr(settings, "LLM_PROVIDER_BY_DOCUMENT_TYPE", {"repair_photo": "bedrock"})
        install_bedrock(monkeypatch, BedrockRecorder(default=(403, ARN_BODY)))
        install_openai(monkeypatch, OpenAIRecorder())

        response = _post("/api/v1/analyze", [("file", ("crack.jpg", _jpeg("gray"), "image/jpeg"))],
                         "repair_photo")

        assert response.status_code == 200, response.text
        page = response.json()["pages"][0]
        assert page["llm_calls"] == [
            {"stage": "photo_understanding", "provider": "bedrock", "model": QWEN,
             "requested_service_tier": "flex", "service_tier": None, "ok": False, "error": "http_403"},
        ]
        _assert_no_arn(response)

    def test_bill_extraction_failure_is_visible(self, monkeypatch):
        monkeypatch.setattr(settings, "LLM_PROVIDER_BY_DOCUMENT_TYPE", {"bill": "bedrock"})
        install_bedrock(monkeypatch, BedrockRecorder(default=(403, ARN_BODY)))

        response = _post("/api/v1/analyze", [("file", ("bill.jpg", _jpeg(), "image/jpeg"))], "bill")

        page = response.json()["pages"][0]
        assert [(c["stage"], c["ok"], c["error"]) for c in page["llm_calls"]] == [
            ("correction", False, "http_403"),
            ("extraction", False, "http_403"),
        ]
        assert page["structured_data"]["llm_used_for_extraction"] is False
        # 校正段把例外字串放進 stats.llm_error:那裡也不得出現 ARN
        _assert_no_arn(response)

    def test_transcript_stays_on_openai_in_the_response(self, monkeypatch):
        monkeypatch.setattr(settings, "LLM_PROVIDER_BY_DOCUMENT_TYPE", dict(ALL_FOUR_BEDROCK))
        bedrock = install_bedrock(monkeypatch, BedrockRecorder())
        install_openai(monkeypatch, OpenAIRecorder())

        response = _post("/api/v1/analyze", [("file", ("t.jpg", _jpeg(), "image/jpeg"))], "transcript")

        page = response.json()["pages"][0]
        assert [(c["stage"], c["provider"], c["model"], c["service_tier"], c["ok"])
                for c in page["llm_calls"]] == [
            ("correction", "openai", settings.OPENAI_MODEL, "default", True),
            ("extraction", "openai", settings.OPENAI_MODEL, "default", True),
        ]
        assert bedrock.requests == []

    def test_default_routing_records_openai(self, monkeypatch):
        install_openai(monkeypatch, OpenAIRecorder())
        response = _post("/api/v1/analyze", [("file", ("bill.jpg", _jpeg(), "image/jpeg"))], "bill")
        page = response.json()["pages"][0]
        assert {(c["provider"], c["model"]) for c in page["llm_calls"]} == {("openai", settings.OPENAI_MODEL)}
        for entry in page["llm_calls"]:
            _assert_entry_shape(entry)

    def test_every_page_has_llm_calls_even_without_llm(self, monkeypatch):
        install_openai(monkeypatch, OpenAIRecorder())
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/analyze",
                files=[("file", ("bill.jpg", _jpeg(), "image/jpeg"))],
                data={"document_type": "bill", "enable_llm": "false"},
            )
        assert response.json()["pages"][0]["llm_calls"] == []


class TestA7_8_BatchEndpoint:
    def test_handover_batch_pages_carry_llm_calls(self, monkeypatch):
        monkeypatch.setattr(settings, "LLM_PROVIDER_BY_DOCUMENT_TYPE", {"handover_photo": "bedrock"})

        def reply(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=bedrock_ok('{"space": "客廳"}', tier="flex")[1])

        install_bedrock(monkeypatch, BedrockRecorder(default=reply))
        install_openai(monkeypatch, OpenAIRecorder())

        files = [("files", (f"p{i}.jpg", _jpeg(), "image/jpeg")) for i in range(3)]
        response = _post("/api/v1/analyze/batch", files, "handover_photo")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["succeeded"] == 3
        for item in body["results"]:
            calls = item["result"]["pages"][0]["llm_calls"]
            assert calls == [
                {"stage": "photo_understanding", "provider": "bedrock", "model": QWEN,
                 "requested_service_tier": "flex", "service_tier": "flex", "ok": True, "error": None},
            ]

    def test_batch_timeout_then_default_and_denial_without_arn(self, monkeypatch):
        """一張逾時後改 default 成功、一張被拒(403 帶 ARN):兩種都要正確呈現,且不外露 ARN"""
        monkeypatch.setattr(settings, "LLM_PROVIDER_BY_DOCUMENT_TYPE", {"handover_photo": "bedrock"})
        monkeypatch.setattr("app.api.v1.analyze.BATCH_MAX_CONCURRENT", 1)   # 依序處理,回覆才對得上
        install_bedrock(monkeypatch, BedrockRecorder([
            httpx.ReadTimeout("timed out"),
            bedrock_ok('{"space": "臥室"}', tier="default"),
            (403, ARN_BODY),
        ]))

        files = [("files", (f"p{i}.jpg", _jpeg(), "image/jpeg")) for i in range(2)]
        response = _post("/api/v1/analyze/batch", files, "handover_photo")

        results = response.json()["results"]
        first = results[0]["result"]["pages"][0]["llm_calls"]
        second = results[1]["result"]["pages"][0]["llm_calls"]
        assert [(c["requested_service_tier"], c["service_tier"], c["ok"], c["error"]) for c in first] == [
            ("flex", None, False, "timeout"),
            ("default", "default", True, None),
        ]
        assert [(c["requested_service_tier"], c["ok"], c["error"]) for c in second] == [
            ("flex", False, "http_403"),
        ]
        for entry in first + second:
            _assert_entry_shape(entry)
        _assert_no_arn(response)


class TestA7_8_TextLayerPath:
    def test_text_layer_pdf_pages_also_carry_llm_calls(self, monkeypatch):
        """含文字層的 PDF 不走 OCR、也沒有影像可送 LLM:每頁仍有 llm_calls,內容為 []"""
        import fitz

        monkeypatch.setattr(settings, "LLM_PROVIDER_BY_DOCUMENT_TYPE", dict(ALL_FOUR_BEDROCK))
        bedrock = install_bedrock(monkeypatch, BedrockRecorder())
        install_openai(monkeypatch, OpenAIRecorder())
        doc = fitz.open()
        for _ in range(2):
            doc.new_page().insert_text((72, 72), "Contract No: ABC-2026-001 Payment by transfer " * 2)
        pdf = doc.tobytes()
        doc.close()

        response = _post("/api/v1/analyze", [("file", ("c.pdf", pdf, "application/pdf"))], "contract")

        assert response.status_code == 200, response.text
        pages = response.json()["pages"]
        assert len(pages) == 2
        assert [p["llm_calls"] for p in pages] == [[], []]
        assert bedrock.requests == []
