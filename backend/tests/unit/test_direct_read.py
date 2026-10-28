"""
Qwen 直讀(收據、帳單、合約)與修繕 damaged_items——計畫 receipt-and-repair-items T1

驗收對照(`.kiro/specs/receipt-and-repair-items/acceptance.md` B8):
  ① 直讀路徑不呼叫 OCR 引擎            TestNoOcr
  ② 影像、PDF 送出長邊 2000、≤3.75MB   TestImageSentToModel
  ③ 文字層帳單、合約 PDF 不走直讀       TestTextLayerStaysOnTextPath
  ④ 未列入設定的帳單、合約走舊流程       TestUnlistedFallsBackToOcr
  ⑤ 收據 PDF(有、沒有文字層)都直讀      TestReceipt.test_receipt_pdf_*
  ⑥ receipt 回傳鍵                      TestReceipt.test_receipt_keys
  ⑦ 不確定或金額格式不過 → 待確認含 amount TestReceipt.test_*amount*
  ⑧ receipt 必要欄位不含 account_no      TestReceipt.test_required_fields_exclude_account_no
  ⑨ 無標籤日期可被接受                   TestDateParsing、TestReceipt.test_unlabeled_date_*
  ⑩ 合約回應鍵與舊版相同並含新鍵          TestContract
  ⑪ damaged_items                       TestRepairDamagedItems
  ⑫ classify 回 receipt                  TestClassifyReceipt
  ⑬ 謄本路徑不變                         TestTranscriptUnchanged
  ⑮ enable_llm=false 仍直讀              TestEnableLlmIgnored
全部不連外:Bedrock 以 httpx.MockTransport 取代,socket 另行封死。
"""

from __future__ import annotations

import base64
import io
import json
import os

import fitz
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from _llm_fakes import BedrockRecorder, bedrock_ok, install_bedrock, no_network  # noqa: F401 (fixture)
from app.config import Settings, settings
from app.database import get_db
from app.lib.multi_type_ocr.bill_processor import BillProcessor
from app.lib.multi_type_ocr.direct_read_processor import (
    BillDirectReadProcessor,
    ContractDirectReadProcessor,
    ReceiptDirectReadProcessor,
    is_valid_amount,
    is_valid_date,
    parse_date,
)
from app.lib.multi_type_ocr.repair_photo_processor import RepairPhotoProcessor
from app.lib.multi_type_ocr.transcript_processor import TranscriptProcessor
from app.main import app
from app.services.analyze_service import AnalyzeService

QWEN = "qwen.qwen3-vl-235b-a22b"
BEDROCK_LIMIT = 3_750_000
ALL_ROUTED = {"receipt": "bedrock", "bill": "bedrock", "contract": "bedrock",
              "repair_photo": "bedrock"}


# --------------------------------------------------------------------------- #
# 共用
# --------------------------------------------------------------------------- #
@pytest.fixture
def ocr_calls(monkeypatch):
    """OCR 引擎與預處理一被呼叫就記下來並失敗:直讀路徑必須完全碰不到它們。"""
    from app.lib.ocr_enhanced.engine_manager import EngineManager

    calls = []

    async def _boom(self, *args, **kwargs):
        calls.append("engine")
        raise AssertionError("直讀路徑不應呼叫 OCR 引擎")

    monkeypatch.setattr(EngineManager, "extract_text_multi_engine", _boom)
    return calls


@pytest.fixture(autouse=True)
def _app_stubs(monkeypatch, feedback_session, no_network):
    app.dependency_overrides[get_db] = lambda: feedback_session

    async def _no_upload(self, *args, **kwargs):
        return None

    monkeypatch.setattr(AnalyzeService, "_upload_to_s3", _no_upload)
    monkeypatch.setattr(AnalyzeService, "_record_usage", lambda self, **kwargs: None)
    monkeypatch.setattr(settings, "LLM_PROVIDER_BY_DOCUMENT_TYPE", dict(ALL_ROUTED))
    yield
    app.dependency_overrides.pop(get_db, None)


def _enable(monkeypatch, *types):
    monkeypatch.setattr(settings, "DIRECT_READ_DOCUMENT_TYPES", list(types))


def _jpeg(size=(1200, 800), color="white") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG")
    return buf.getvalue()


def _noisy_jpeg(size) -> bytes:
    """亂數雜訊 JPEG:壓縮率最差,用來逼出 3.75MB 的邊界。"""
    image = Image.frombytes("RGB", size, os.urandom(size[0] * size[1] * 3))
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def _scanned_pdf(pages=1, page_size=(595, 842)) -> bytes:
    """沒有文字層的 PDF:每頁只放一張圖。"""
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page(width=page_size[0], height=page_size[1])
        page.insert_image(page.rect, stream=_jpeg((900, 1200), "lightgray"))
    data = doc.tobytes()
    doc.close()
    return data


def _text_layer_pdf(text="Receipt total 588 TWD issued 2026-10-12 " * 8, pages=1) -> bytes:
    doc = fitz.open()
    for _ in range(pages):
        page = doc.new_page()
        page.insert_textbox(fitz.Rect(50, 50, 550, 750), text, fontsize=10)
    data = doc.tobytes()
    doc.close()
    return data


def _field(value, certain=True):
    return {"value": value, "certain": certain}


def _receipt_reply(amount="588", date="2026-10-12 14:35:20", amount_certain=True, date_certain=True):
    return json.dumps({
        "amount": _field(amount, amount_certain),
        "date": _field(date, date_certain),
    }, ensure_ascii=False)


def _bill_reply():
    return json.dumps({
        "amount": _field("1,280"), "date": _field("115/11/05"), "account_no": _field("01-2345-6789"),
    }, ensure_ascii=False)


def _contract_reply(lease=True):
    return json.dumps({
        "is_lease": lease,
        "fields": {
            "contract_number": _field("A-001"),
            "party_a": _field("王大明"), "party_b": _field("李小華"),
            "contract_amount": _field("240000"),
            "date_start": _field("115年1月1日"), "date_end": _field("115年12月31日"),
            "monthly_rent": _field("20,000"), "deposit": _field("40,000"),
            "rental_address": _field("台北市中正區某路1號"), "tenant_name": _field("李小華"),
        },
    }, ensure_ascii=False)


def _post(files, document_type, enable_llm="true"):
    with TestClient(app) as client:
        return client.post(
            "/api/v1/analyze", files=files,
            data={"document_type": document_type, "enable_llm": enable_llm},
        )


def _image_file(name="x.jpg", data=None):
    return [("file", (name, data or _jpeg(), "image/jpeg"))]


def _pdf_file(data, name="x.pdf"):
    return [("file", (name, data, "application/pdf"))]


def _sent_images(recorder):
    """Bedrock 請求裡實際送出的影像(解碼後的位元組)。"""
    images = []
    for body in recorder.bodies:
        for part in body["messages"][0]["content"]:
            if isinstance(part, dict) and part.get("type") == "image_url":
                url = part["image_url"]["url"]
                images.append(base64.b64decode(url.split(",", 1)[1]))
    return images


def _install(monkeypatch, reply):
    return install_bedrock(monkeypatch, BedrockRecorder(default=bedrock_ok(reply)))


def _assert_direct_read_page(page):
    assert page["ocr_raw"] is None
    assert page["llm_calls"], "直讀頁必須有 llm_calls"
    assert all(c["stage"] == "direct_read" and c["provider"] == "bedrock" for c in page["llm_calls"])
    assert page["llm_calls"][-1]["ok"] is True


# --------------------------------------------------------------------------- #
# ① 不呼叫 OCR 引擎
# --------------------------------------------------------------------------- #
class TestNoOcr:
    @pytest.mark.parametrize("document_type,reply", [
        ("receipt", _receipt_reply()), ("bill", _bill_reply()), ("contract", _contract_reply()),
    ])
    def test_image_never_calls_ocr_engine(self, monkeypatch, ocr_calls, document_type, reply):
        _enable(monkeypatch, "receipt", "bill", "contract")
        _install(monkeypatch, reply)
        response = _post(_image_file(), document_type)
        assert response.status_code == 200, response.text
        assert ocr_calls == []
        _assert_direct_read_page(response.json()["pages"][0])

    @pytest.mark.parametrize("document_type,reply", [
        ("receipt", _receipt_reply()), ("bill", _bill_reply()), ("contract", _contract_reply()),
    ])
    def test_scanned_pdf_never_calls_ocr_engine(self, monkeypatch, ocr_calls, document_type, reply):
        _enable(monkeypatch, "receipt", "bill", "contract")
        recorder = _install(monkeypatch, reply)
        response = _post(_pdf_file(_scanned_pdf(pages=2)), document_type)
        assert response.status_code == 200, response.text
        body = response.json()
        assert ocr_calls == []
        assert body["total_pages"] == 2 and len(recorder.requests) == 2
        for page in body["pages"]:
            _assert_direct_read_page(page)

    def test_direct_read_never_constructs_ocr_processor(self, monkeypatch):
        """連處理器都不建(建 BillProcessor 會載入 OCR 引擎管理器)"""
        _enable(monkeypatch, "bill")
        _install(monkeypatch, _bill_reply())

        def _boom(self, *a, **k):
            raise AssertionError("不應建立 OCR 型處理器")

        monkeypatch.setattr(BillProcessor, "__init__", _boom)
        assert _post(_image_file(), "bill").status_code == 200


# --------------------------------------------------------------------------- #
# ② 送出的影像
# --------------------------------------------------------------------------- #
class TestImageSentToModel:
    def test_large_photo_is_sent_at_long_edge_2000(self, monkeypatch):
        _enable(monkeypatch, "receipt")
        recorder = _install(monkeypatch, _receipt_reply())
        assert _post(_image_file(data=_jpeg((4000, 3000))), "receipt").status_code == 200
        (sent,) = _sent_images(recorder)
        image = Image.open(io.BytesIO(sent))
        assert image.format == "JPEG"
        assert max(image.size) == 2000
        assert image.size == (2000, 1500)
        assert len(sent) <= BEDROCK_LIMIT

    def test_noisy_photo_stays_under_bedrock_limit_without_shrinking(self, monkeypatch):
        _enable(monkeypatch, "bill")
        recorder = _install(monkeypatch, _bill_reply())
        assert _post(_image_file(data=_noisy_jpeg((3000, 2250))), "bill").status_code == 200
        (sent,) = _sent_images(recorder)
        assert len(sent) <= BEDROCK_LIMIT
        assert max(Image.open(io.BytesIO(sent)).size) == 2000

    def test_small_image_is_not_upscaled(self, monkeypatch):
        _enable(monkeypatch, "receipt")
        recorder = _install(monkeypatch, _receipt_reply())
        _post(_image_file(data=_jpeg((800, 600))), "receipt")
        (sent,) = _sent_images(recorder)
        assert Image.open(io.BytesIO(sent)).size == (800, 600)

    def test_jpeg_quality_is_92(self, monkeypatch):
        """沿用 Bedrock 重新編碼品質常數:同一張圖以 92 編碼的結果與送出的位元組逐位元相同"""
        from app.lib.multi_type_ocr.direct_read_processor import prepare_direct_read_image

        source = _jpeg((1500, 1000), "tan")
        sent = prepare_direct_read_image(source)
        expected = io.BytesIO()
        Image.open(io.BytesIO(source)).convert("RGB").save(expected, format="JPEG", quality=92)
        assert sent == expected.getvalue()

    @pytest.mark.parametrize("page_size", [(595, 842), (842, 595), (300, 300)])
    def test_pdf_pages_rendered_at_long_edge_2000(self, monkeypatch, page_size):
        _enable(monkeypatch, "contract")
        recorder = _install(monkeypatch, _contract_reply())
        assert _post(_pdf_file(_scanned_pdf(pages=2, page_size=page_size)), "contract").status_code == 200
        sent = _sent_images(recorder)
        assert len(sent) == 2
        for data in sent:
            assert max(Image.open(io.BytesIO(data)).size) == 2000
            assert len(data) <= BEDROCK_LIMIT

    def test_png_with_alpha_is_flattened_to_white(self, monkeypatch):
        _enable(monkeypatch, "receipt")
        recorder = _install(monkeypatch, _receipt_reply())
        buf = io.BytesIO()
        Image.new("RGBA", (400, 300), (0, 0, 0, 0)).save(buf, format="PNG")
        _post([("file", ("x.png", buf.getvalue(), "image/png"))], "receipt")
        (sent,) = _sent_images(recorder)
        assert Image.open(io.BytesIO(sent)).getpixel((10, 10))[0] > 240


# --------------------------------------------------------------------------- #
# ③ 文字層維持
# --------------------------------------------------------------------------- #
class TestTextLayerStaysOnTextPath:
    @pytest.mark.parametrize("document_type", ["bill", "contract"])
    def test_text_layer_pdf_is_not_direct_read(self, monkeypatch, ocr_calls, document_type):
        _enable(monkeypatch, "receipt", "bill", "contract")
        recorder = _install(monkeypatch, "{}")
        response = _post(_pdf_file(_text_layer_pdf()), document_type, enable_llm="false")
        assert response.status_code == 200, response.text
        page = response.json()["pages"][0]
        assert recorder.requests == []
        assert page["llm_calls"] == []
        assert page["ocr_raw"]["text"].startswith("Receipt total 588")
        assert page["ocr_raw"]["confidence"] == 1.0
        assert ocr_calls == []

    def test_text_layer_path_result_identical_with_and_without_setting(self, monkeypatch):
        """B4 的本機版:同一份文字層合約 PDF,開關前後 ocr_raw 與 structured_data 逐一相同"""
        pdf = _text_layer_pdf("Lease contract party A Wang party B Li monthly rent 20000 " * 4)

        def run():
            response = _post(_pdf_file(pdf), "contract", enable_llm="false")
            assert response.status_code == 200, response.text
            page = response.json()["pages"][0]
            return page["ocr_raw"], page["structured_data"], page["llm_calls"]

        monkeypatch.setattr(settings, "DIRECT_READ_DOCUMENT_TYPES", [])
        before = run()
        _enable(monkeypatch, "receipt", "bill", "contract")
        after = run()
        assert before == after
        assert after[2] == []


# --------------------------------------------------------------------------- #
# ④ 未列入 → 舊流程
# --------------------------------------------------------------------------- #
class TestUnlistedFallsBackToOcr:
    @pytest.fixture
    def old_pipeline(self, monkeypatch):
        """以替身取代本機 OCR,並記下被呼叫的次數"""
        calls = []
        from app.lib.multi_type_ocr.contract_processor import ContractProcessor

        for cls, text in ((BillProcessor, "戶號: 01-2345-6789"), (ContractProcessor, "合約編號: A-001")):
            async def _pre(self, image):
                return image

            async def _ocr(self, image, _text=text):
                calls.append(text)
                return _text, 0.95

            monkeypatch.setattr(cls, "preprocess", _pre)
            monkeypatch.setattr(cls, "extract_text", _ocr)
        return calls

    @pytest.mark.parametrize("listed", [(), ("receipt",), ("contract",)])
    def test_unlisted_bill_uses_old_pipeline(self, monkeypatch, old_pipeline, listed):
        _enable(monkeypatch, *listed)
        recorder = _install(monkeypatch, "{}")
        response = _post(_image_file(), "bill", enable_llm="false")
        assert response.status_code == 200, response.text
        page = response.json()["pages"][0]
        assert old_pipeline, "舊流程的 OCR 應該被呼叫"
        assert page["ocr_raw"] is not None
        assert all(c["stage"] != "direct_read" for c in page["llm_calls"])
        assert recorder.requests == []

    @pytest.mark.parametrize("listed", [(), ("receipt",), ("bill",)])
    def test_unlisted_contract_uses_old_pipeline(self, monkeypatch, old_pipeline, listed):
        _enable(monkeypatch, *listed)
        response = _post(_image_file(), "contract", enable_llm="false")
        assert response.status_code == 200, response.text
        assert old_pipeline
        assert response.json()["pages"][0]["ocr_raw"]["text"] == "合約編號: A-001"

    def test_default_setting_is_empty(self):
        assert Settings().DIRECT_READ_DOCUMENT_TYPES == []


# --------------------------------------------------------------------------- #
# 設定
# --------------------------------------------------------------------------- #
class TestSetting:
    def test_parses_json_from_env(self, monkeypatch):
        monkeypatch.setenv("DIRECT_READ_DOCUMENT_TYPES", '["Receipt", "bill"]')
        assert Settings().DIRECT_READ_DOCUMENT_TYPES == ["receipt", "bill"]

    @pytest.mark.parametrize("bad", [["transcript"], ["bil"], ["repair_photo"]])
    def test_unknown_or_transcript_rejected(self, bad):
        with pytest.raises(ValueError):
            Settings(DIRECT_READ_DOCUMENT_TYPES=bad)


# --------------------------------------------------------------------------- #
# 收據 ⑤⑥⑦⑧⑨
# --------------------------------------------------------------------------- #
class TestReceipt:
    def test_unlisted_receipt_is_unsupported(self, monkeypatch):
        _enable(monkeypatch)
        response = _post(_image_file(), "receipt")
        assert response.status_code == 400
        body = response.json()
        assert body["error_code"] == "UNSUPPORTED_DOCUMENT_TYPE"
        assert "receipt" not in body["detail"].split("支援的類型：")[1]

    def test_listed_receipt_appears_in_supported_types(self, monkeypatch):
        _enable(monkeypatch, "receipt")
        response = _post(_image_file(), "invoice")
        assert "receipt" in response.json()["detail"]

    def test_receipt_keys(self, monkeypatch):
        _enable(monkeypatch, "receipt")
        _install(monkeypatch, _receipt_reply())
        response = _post(_image_file(), "receipt")
        assert response.status_code == 200, response.text
        data = response.json()
        structured = data["pages"][0]["structured_data"]
        assert {"amount", "date", "field_confidences", "needs_confirmation"} <= set(structured)
        assert "account_no" not in structured
        assert structured["amount"] == "588"          # 原始字串
        assert structured["date"] == "2026-10-12 14:35:20"
        assert structured["field_confidences"] == {"amount": 0.9, "date": 0.9}
        assert structured["needs_confirmation"] == []
        assert data["document_fields"]["amount"] == "588"
        assert data["needs_review"] is False
        _assert_direct_read_page(data["pages"][0])
        assert data["pages"][0]["llm_calls"][0]["model"] == QWEN

    def test_receipt_pdf_without_text_layer_is_direct_read(self, monkeypatch, ocr_calls):
        _enable(monkeypatch, "receipt")
        recorder = _install(monkeypatch, _receipt_reply())
        response = _post(_pdf_file(_scanned_pdf()), "receipt")
        assert response.status_code == 200, response.text
        _assert_direct_read_page(response.json()["pages"][0])
        assert len(recorder.requests) == 1 and ocr_calls == []

    def test_receipt_pdf_with_text_layer_is_direct_read(self, monkeypatch, ocr_calls):
        """收據沒有文字層路徑可走:有文字層的 PDF 一樣整頁交模型讀"""
        _enable(monkeypatch, "receipt")
        recorder = _install(monkeypatch, _receipt_reply())
        response = _post(_pdf_file(_text_layer_pdf()), "receipt")
        assert response.status_code == 200, response.text
        page = response.json()["pages"][0]
        _assert_direct_read_page(page)
        assert len(recorder.requests) == 1 and ocr_calls == []
        assert max(Image.open(io.BytesIO(_sent_images(recorder)[0])).size) == 2000

    @pytest.mark.parametrize("reply_kwargs", [
        {"amount_certain": False},                # 模型說不確定(分不出總計)
        {"amount": "三千五"},                       # 非數字
        {"amount": "2,350 / 明細金額"},             # 夾帶說明文字
        {"amount": None},                         # 沒讀到
    ])
    def test_uncertain_or_invalid_amount_needs_confirmation(self, monkeypatch, reply_kwargs):
        _enable(monkeypatch, "receipt")
        _install(monkeypatch, _receipt_reply(**reply_kwargs))
        response = _post(_image_file(), "receipt")
        assert response.status_code == 200, response.text
        data = response.json()
        structured = data["pages"][0]["structured_data"]
        assert "amount" in structured["needs_confirmation"]
        assert "date" not in structured["needs_confirmation"]
        assert structured["field_confidences"]["amount"] < settings.OCR_QUALITY_THRESHOLD
        assert structured["field_confidences"]["date"] == 0.9
        # 閘控:進複核
        assert data["needs_review"] is True
        assert data["review_item_id"]
        assert "amount" in data["document_fields"]["needs_confirmation"]

    def test_uncertain_amount_gets_confidence_0_5_and_invalid_gets_0_5(self):
        processor = ReceiptDirectReadProcessor()
        uncertain = processor.to_structured(json.loads(_receipt_reply(amount_certain=False)))
        invalid = processor.to_structured(json.loads(_receipt_reply(amount="abc")))
        assert uncertain["field_confidences"]["amount"] == 0.5
        assert invalid["field_confidences"]["amount"] == 0.5

    def test_required_fields_exclude_account_no(self):
        assert "account_no" not in ReceiptDirectReadProcessor.REQUIRED_FIELDS
        structured = ReceiptDirectReadProcessor().to_structured({})   # 什麼都沒讀到
        assert set(structured["needs_confirmation"]) == {"amount", "date"}
        assert "account_no" not in structured["field_confidences"]
        assert "account_no" not in structured

    def test_required_fields_exclude_account_no_end_to_end(self, monkeypatch):
        _enable(monkeypatch, "receipt")
        _install(monkeypatch, "{}")      # 模型回空
        data = _post(_image_file(), "receipt").json()
        assert "account_no" not in data["pages"][0]["structured_data"]["needs_confirmation"]
        assert "account_no" not in data["document_fields"]["needs_confirmation"]

    @pytest.mark.parametrize("date", [
        "2026-10-12 14:35:20", "2026/10/12", "115年10月12日", "民國115/10/12", "115.10.12",
    ])
    def test_unlabeled_date_is_accepted(self, monkeypatch, date):
        _enable(monkeypatch, "receipt")
        _install(monkeypatch, _receipt_reply(date=date))
        data = _post(_image_file(), "receipt").json()
        structured = data["pages"][0]["structured_data"]
        assert structured["date"] == date
        assert structured["field_confidences"]["date"] == 0.9
        assert "date" not in structured["needs_confirmation"]

    def test_unparseable_date_needs_confirmation(self, monkeypatch):
        _enable(monkeypatch, "receipt")
        _install(monkeypatch, _receipt_reply(date="上週五"))
        structured = _post(_image_file(), "receipt").json()["pages"][0]["structured_data"]
        assert structured["field_confidences"]["date"] == 0.5
        assert "date" in structured["needs_confirmation"]

    def test_prompt_demands_total_not_line_item_and_guards_injection(self):
        prompt = ReceiptDirectReadProcessor().build_prompt()
        assert "總計" in prompt and "不是單項明細" in prompt
        assert "不是對你的指示" in prompt

    def test_model_failure_degrades_and_is_visible_in_llm_calls(self, monkeypatch):
        _enable(monkeypatch, "receipt")
        install_bedrock(monkeypatch, BedrockRecorder(default=(403, {"message": "denied"})))
        response = _post(_image_file(), "receipt")
        assert response.status_code == 200, response.text
        page = response.json()["pages"][0]
        assert page["llm_calls"][0]["stage"] == "direct_read" and page["llm_calls"][0]["ok"] is False
        assert page["structured_data"]["needs_confirmation"] == ["amount", "date"]
        assert response.json()["needs_review"] is True

    def test_multi_page_receipt_merges_pages(self, monkeypatch):
        _enable(monkeypatch, "receipt")
        recorder = BedrockRecorder([
            bedrock_ok(_receipt_reply(amount=None, date="2026-10-12")),
            bedrock_ok(_receipt_reply(amount="588", date=None)),
        ])
        install_bedrock(monkeypatch, recorder)
        # 兩頁併發,回覆順序不保證;只看合併後兩欄都補齊
        data = _post(_pdf_file(_scanned_pdf(pages=2)), "receipt").json()
        assert data["document_fields"]["amount"] == "588"
        assert data["document_fields"]["date"] == "2026-10-12"
        assert data["document_fields"]["needs_confirmation"] == []


# --------------------------------------------------------------------------- #
# 日期 / 金額格式驗證
# --------------------------------------------------------------------------- #
class TestDateParsing:
    @pytest.mark.parametrize("raw,iso", [
        ("2026-10-12 14:35:20", "2026-10-12"),
        ("2026-10-12T14:35:20", "2026-10-12"),
        ("2026/10/12", "2026-10-12"),
        ("115年10月12日", "2026-10-12"),
        ("民國115年10月12日 下午2:35", "2026-10-12"),
        ("中華民國115/10/12", "2026-10-12"),
        ("115.10.12", "2026-10-12"),
        ("20261012", "2026-10-12"),
        ("1151012", "2026-10-12"),
        ("２０２６－１０－１２", "2026-10-12"),   # 全形先轉半形
    ])
    def test_parse(self, raw, iso):
        assert parse_date(raw) == iso

    @pytest.mark.parametrize("raw", ["", "上週五", "2026-13-01", "2026-02-30", "115年13月1日", "abc 14:35"])
    def test_rejects(self, raw):
        assert is_valid_date(raw) is False

    @pytest.mark.parametrize("raw,ok", [
        ("588", True), ("1,280", True), ("NT$ 2,350", True), ("$588.50", True), ("1,280元", True),
        ("５８８", True), ("abc", False), ("", False), ("12-34", False), ("588 / 明細", False),
        ("三千五", False),
    ])
    def test_amount(self, raw, ok):
        assert is_valid_amount(raw) is ok


# --------------------------------------------------------------------------- #
# 帳單
# --------------------------------------------------------------------------- #
OLD_BILL_KEYS = {
    "amount", "date", "account_no", "field_confidences", "needs_confirmation",
    "extraction_confidence", "llm_used_for_extraction",
}


class TestBill:
    def test_bill_keys_identical_to_old_pipeline(self, monkeypatch):
        _enable(monkeypatch, "bill")
        _install(monkeypatch, _bill_reply())
        data = _post(_image_file(), "bill").json()
        structured = data["pages"][0]["structured_data"]
        assert set(structured) == OLD_BILL_KEYS
        assert structured["amount"] == "1,280" and structured["account_no"] == "01-2345-6789"
        assert structured["llm_used_for_extraction"] is True
        assert set(structured["field_confidences"]) == {"amount", "date", "account_no"}
        assert data["needs_review"] is False

    def test_bill_missing_account_no_goes_to_needs_confirmation(self, monkeypatch):
        _enable(monkeypatch, "bill")
        reply = json.dumps({"amount": _field("1280"), "date": _field("2026-11-05")})
        _install(monkeypatch, reply)
        data = _post(_image_file(), "bill").json()
        assert data["pages"][0]["structured_data"]["needs_confirmation"] == ["account_no"]
        assert data["needs_review"] is True


# --------------------------------------------------------------------------- #
# 合約 ⑩
# --------------------------------------------------------------------------- #
OLD_CONTRACT_KEYS = {
    "contract_metadata", "parties", "financial_terms", "rental_terms",
    "extraction_confidence", "llm_used_for_extraction",
}


class TestContract:
    def test_contract_keys_preserved_plus_new_keys(self, monkeypatch):
        _enable(monkeypatch, "contract")
        _install(monkeypatch, _contract_reply())
        data = _post(_image_file(), "contract").json()
        structured = data["pages"][0]["structured_data"]
        assert set(structured) == OLD_CONTRACT_KEYS | {"field_confidences", "needs_confirmation"}
        assert set(structured["contract_metadata"]) == {"contract_number", "signing_date", "effective_date"}
        assert set(structured["parties"]) == {"party_a", "party_b", "party_a_address", "party_b_address"}
        assert set(structured["financial_terms"]) == {
            "contract_amount", "currency", "payment_method", "payment_deadline",
        }
        assert structured["parties"]["party_b"] == "李小華"
        assert structured["rental_terms"]["monthly_rent"] == "20,000"
        assert structured["financial_terms"]["currency"] == "TWD"
        assert structured["llm_used_for_extraction"] is True
        assert structured["needs_confirmation"] == []
        assert structured["field_confidences"]["party_a"] == 0.9
        assert data["needs_review"] is False

    def test_contract_keys_match_old_extractor_output(self):
        """鍵集合與舊版規則抽取器的輸出逐鍵相同(舊版有租賃欄位時含 rental_terms)"""
        import asyncio

        from app.lib.multi_type_ocr.contract_field_extractor import ContractFieldExtractor

        old = asyncio.run(ContractFieldExtractor().extract("租賃契約 月租金：20,000元 押金：40,000元"))
        new = ContractDirectReadProcessor().to_structured(json.loads(_contract_reply()))
        assert set(old) <= set(new)
        for key in ("contract_metadata", "parties", "financial_terms", "rental_terms"):
            assert set(old[key]) == set(new[key])

    def test_contract_without_rental_fields_omits_rental_terms(self):
        reply = json.loads(_contract_reply(lease=False))
        reply["fields"] = {k: v for k, v in reply["fields"].items()
                           if k in ("contract_number", "party_a", "party_b", "contract_amount")}
        structured = ContractDirectReadProcessor().to_structured(reply)
        assert "rental_terms" not in structured
        assert structured["needs_confirmation"] == []     # 通用合約不要求租賃欄位

    def test_uncertain_or_missing_required_field_needs_confirmation(self):
        reply = json.loads(_contract_reply())
        reply["fields"]["monthly_rent"]["certain"] = False
        reply["fields"]["deposit"] = _field(None)
        structured = ContractDirectReadProcessor().to_structured(reply)
        assert structured["needs_confirmation"] == ["deposit", "monthly_rent"]
        assert structured["field_confidences"]["monthly_rent"] == 0.5
        assert structured["field_confidences"]["deposit"] == 0.0

    def test_multi_page_contract_is_merged_with_existing_merge(self, monkeypatch):
        _enable(monkeypatch, "contract")
        page1 = json.loads(_contract_reply())
        page1["fields"] = {k: v for k, v in page1["fields"].items() if k in ("contract_number", "party_a", "party_b")}
        page2 = json.loads(_contract_reply())
        page2["fields"] = {k: v for k, v in page2["fields"].items() if k not in ("contract_number", "party_a", "party_b")}

        def reply(request):
            import httpx
            body = json.loads(request.content)
            # 依序回:第一個請求是第 1 頁
            index = len(recorder.requests) - 1
            return httpx.Response(200, json=bedrock_ok(json.dumps([page1, page2][index]))[1])

        recorder = BedrockRecorder(default=reply)
        install_bedrock(monkeypatch, recorder)
        # 以單頁併發度 1 讓請求順序固定
        monkeypatch.setattr(settings, "OCR_MAX_CONCURRENT_PAGES", 1)
        data = _post(_pdf_file(_scanned_pdf(pages=2)), "contract").json()
        merged = data["document_fields"]
        assert merged["parties"]["party_a"] == "王大明"
        assert merged["rental_terms"]["monthly_rent"] == "20,000"
        assert merged["needs_confirmation"] == []
        assert data["needs_review"] is False

    def test_few_shot_does_not_break_prompt(self):
        assert "contract_number" in ContractDirectReadProcessor().build_prompt()


# --------------------------------------------------------------------------- #
# ⑮ enable_llm=false 仍直讀
# --------------------------------------------------------------------------- #
class TestEnableLlmIgnored:
    @pytest.mark.parametrize("document_type,reply", [
        ("receipt", _receipt_reply()), ("bill", _bill_reply()), ("contract", _contract_reply()),
    ])
    @pytest.mark.parametrize("enable_llm", ["false", "true"])
    def test_enable_llm_has_no_effect(self, monkeypatch, ocr_calls, document_type, reply, enable_llm):
        _enable(monkeypatch, "receipt", "bill", "contract")
        recorder = _install(monkeypatch, reply)
        response = _post(_image_file(), document_type, enable_llm=enable_llm)
        assert response.status_code == 200, response.text
        assert len(recorder.requests) == 1
        _assert_direct_read_page(response.json()["pages"][0])
        assert ocr_calls == []

    def test_scanned_pdf_with_enable_llm_false_still_direct_read(self, monkeypatch):
        _enable(monkeypatch, "bill")
        recorder = _install(monkeypatch, _bill_reply())
        response = _post(_pdf_file(_scanned_pdf()), "bill", enable_llm="false")
        assert len(recorder.requests) == 1
        _assert_direct_read_page(response.json()["pages"][0])


# --------------------------------------------------------------------------- #
# ⑪ damaged_items
# --------------------------------------------------------------------------- #
class _FakeProvider:
    def __init__(self, reply):
        self.reply, self.prompts = reply, []

    async def call(self, prompt, image_data=None, few_shot=None, **kwargs):
        self.prompts.append(prompt)
        return self.reply


class TestRepairDamagedItems:
    @pytest.mark.asyncio
    async def test_damaged_items_in_output(self):
        provider = _FakeProvider(json.dumps({
            "defect_labels": ["漏水"], "damaged_items": ["水龍頭", "洗手台"],
            "description": "水龍頭漏水", "confidence": 0.9,
        }, ensure_ascii=False))
        result = await RepairPhotoProcessor(provider=provider).understand("QUJD")
        assert result["damaged_items"] == ["水龍頭", "洗手台"]
        assert result["defect_labels"] == ["漏水"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("raw,expected", [
        ("紗窗", ["紗窗"]), (None, []), ({"a": 1}, []), ([" 馬桶 ", "", 3, None, {"x": 1}], ["馬桶", "3"]),
    ])
    async def test_damaged_items_is_always_a_string_list(self, raw, expected):
        provider = _FakeProvider(json.dumps({"defect_labels": [], "damaged_items": raw, "confidence": 1}))
        result = await RepairPhotoProcessor(provider=provider).understand("QUJD")
        assert result["damaged_items"] == expected

    @pytest.mark.asyncio
    async def test_missing_key_and_failure_give_empty_list(self):
        absent = await RepairPhotoProcessor(provider=_FakeProvider("{}")).understand("QUJD")
        assert absent["damaged_items"] == []

        class _Broken:
            async def call(self, *a, **k):
                raise RuntimeError("boom")

        failed = await RepairPhotoProcessor(provider=_Broken()).understand("QUJD")
        assert failed == {"defect_labels": [], "damaged_items": [], "description": "", "confidence": 0.0}

    @pytest.mark.asyncio
    async def test_prompt_adds_damaged_items_and_keeps_defect_labels_example(self):
        provider = _FakeProvider("{}")
        await RepairPhotoProcessor(provider=provider).understand("QUJD")
        prompt = provider.prompts[0]
        assert "damaged_items" in prompt
        # D-7:既有範例文字一字不動
        assert "- defect_labels: 瑕疵標籤陣列(如 漏水、壁癌、龜裂、設備損壞)\n" in prompt

    def test_endpoint_returns_damaged_items(self, monkeypatch):
        recorder = _install(monkeypatch, json.dumps({
            "defect_labels": ["設備損壞"], "damaged_items": ["紗窗"],
            "description": "紗窗破洞", "confidence": 0.95,
        }, ensure_ascii=False))
        response = _post(_image_file(), "repair_photo")
        assert response.status_code == 200, response.text
        page = response.json()["pages"][0]
        assert page["structured_data"]["damaged_items"] == ["紗窗"]
        assert page["structured_data"]["defect_labels"] == ["設備損壞"]
        assert page["llm_calls"][0]["stage"] == "photo_understanding"
        assert len(recorder.requests) == 1


# --------------------------------------------------------------------------- #
# ⑫ classify
# --------------------------------------------------------------------------- #
class TestClassifyReceipt:
    @pytest.fixture
    def ocr_text(self, monkeypatch):
        from app.lib.ocr_enhanced.document_classifier import DocumentClassifier

        holder = {"text": ""}
        monkeypatch.setattr(DocumentClassifier, "_extract_text", lambda self, image: holder["text"])
        return holder

    def _classify(self):
        with TestClient(app) as client:
            return client.post("/api/v1/classify", files=_image_file()).json()

    @pytest.mark.parametrize("text", [
        "統一發票 電子發票證明聯 發票號碼 AB-12345678 總計 588",
        "收據 茲收到 王小明 交來 修繕費用",
        "電子發票證明聯\n2026-10-12 14:35:20\n總計 588",
    ])
    def test_receipt_wording_returns_receipt(self, ocr_text, text):
        ocr_text["text"] = text
        result = self._classify()
        assert result["suggested_document_type"] == "receipt"
        assert result["confidence"] > 0

    @pytest.mark.parametrize("text,expected", [
        ("土地登記第二類謄本 建物標示部 所有權部", "transcript"),
        ("房屋租賃契約書 出租人 承租人 月租金 押金", "contract"),
        ("電費繳費通知單 本期應繳 戶號", None),
    ])
    def test_other_types_unchanged(self, ocr_text, text, expected):
        ocr_text["text"] = text
        assert self._classify()["suggested_document_type"] == expected

    def test_lease_that_mentions_receipt_once_stays_contract(self, ocr_text):
        ocr_text["text"] = "房屋租賃契約 出租人 承租人 月租金 押金 出租人應開立收據"
        assert self._classify()["suggested_document_type"] == "contract"


# --------------------------------------------------------------------------- #
# ⑬ 謄本不變
# --------------------------------------------------------------------------- #
class TestTranscriptUnchanged:
    def test_transcript_cannot_be_direct_read(self):
        with pytest.raises(ValueError):
            Settings(DIRECT_READ_DOCUMENT_TYPES=["transcript"])

    def test_transcript_still_goes_through_local_ocr(self, monkeypatch):
        _enable(monkeypatch, "receipt", "bill", "contract")
        recorder = _install(monkeypatch, "{}")
        seen = []

        async def _pre(self, image):
            return image

        async def _ocr(self, image):
            seen.append("ocr")
            return "土地登記第二類謄本", 0.95

        monkeypatch.setattr(TranscriptProcessor, "preprocess", _pre)
        monkeypatch.setattr(TranscriptProcessor, "extract_text", _ocr)
        response = _post(_image_file(), "transcript", enable_llm="false")
        assert response.status_code == 200, response.text
        page = response.json()["pages"][0]
        assert seen == ["ocr"]
        assert page["ocr_raw"]["text"] == "土地登記第二類謄本"
        assert all(c["stage"] != "direct_read" for c in page["llm_calls"])
        assert recorder.requests == []


# --------------------------------------------------------------------------- #
# 登記處
# --------------------------------------------------------------------------- #
class TestRegistration:
    def test_receipt_registered_everywhere(self):
        from app.config import LLM_ROUTABLE_DOCUMENT_TYPES
        from app.lib.document_types import DocumentType, TYPE_ALLOWED_EXTENSIONS, normalize_document_type
        from app.lib.multi_type_ocr.processor_factory import ProcessorFactory
        from app.lib.multi_type_ocr.types import DocumentTypeEnum
        from app.services.analyze_service import S3_PATH_MAP
        from typing import get_args

        assert normalize_document_type("receipt") == DocumentType.RECEIPT
        assert TYPE_ALLOWED_EXTENSIONS[DocumentType.RECEIPT] == {".jpg", ".jpeg", ".png", ".pdf"}
        assert "receipt" in ProcessorFactory.supported_types()
        assert isinstance(ProcessorFactory.get_processor("receipt"), ReceiptDirectReadProcessor)
        assert "receipt" in LLM_ROUTABLE_DOCUMENT_TYPES
        assert "receipt" in get_args(DocumentTypeEnum)
        assert "receipt" in S3_PATH_MAP

    def test_receipt_can_route_to_bedrock(self, monkeypatch):
        from app.lib.llm_service.routing import provider_name_for

        monkeypatch.setattr(settings, "LLM_PROVIDER_BY_DOCUMENT_TYPE", {"receipt": "bedrock"})
        assert provider_name_for("receipt", None) == "bedrock"

    def test_receipt_rejects_unsupported_extension(self, monkeypatch):
        _enable(monkeypatch, "receipt")
        response = _post([("file", ("x.docx", b"x", "application/octet-stream"))], "receipt")
        assert response.status_code == 400
        assert response.json()["error_code"] == "UNSUPPORTED_FILE_TYPE"


class TestDirectReadFailureFlag:
    """直讀呼叫失敗時,帳單、合約的 llm_used_for_extraction 為 False(INTEGRATION §2.4、§3)。"""

    def test_bill_and_contract_failure_sets_flag_false(self):
        from app.lib.multi_type_ocr.direct_read_processor import (
            BillDirectReadProcessor,
            ContractDirectReadProcessor,
        )

        for proc in (BillDirectReadProcessor(), ContractDirectReadProcessor()):
            assert proc.empty_structured()["llm_used_for_extraction"] is False
            assert proc.to_structured({})["llm_used_for_extraction"] is True

    def test_receipt_failure_has_no_flag(self):
        from app.lib.multi_type_ocr.direct_read_processor import ReceiptDirectReadProcessor

        empty = ReceiptDirectReadProcessor().empty_structured()
        assert "llm_used_for_extraction" not in empty
        assert set(empty["needs_confirmation"]) == {"amount", "date"}
