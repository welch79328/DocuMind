"""
送 LLM 的影像與給 OCR 的影像(bedrock-qwen-documind S1;acceptance.md A7 ⑥⑦,R7)

  A7 ⑥ Bedrock 請求的影像與 openai 路由送出的影像尺寸相同,且 ≤3.75MB
       (超過時以同尺寸 JPEG 重新編碼);影像與 PDF 兩條路都測
       → TestA7_6_BedrockImageMatchesOpenAIRoute
  A7 ⑦ 不論路由為何,給 OCR 的影像與 openai 路由送出的影像都與切換前逐位元相同
       (影像與 PDF 兩條路;影像含 12MP 與 ≥24MP 的 JPEG)
       → TestA7_7_ImagesUnchangedFromBeforeTheSwitch

「切換前」的基準 GOLDEN 是在**改程式之前**(HEAD ee72216)用同一組合成影像跑出來的:
OCR 輸入取 (尺寸, sha256(mode + size + 像素)),LLM 影像取 sha256(送進 Provider 的
base64 字串)。環境 Python 3.11、Pillow 11.0.0、PyMuPDF 1.24.13、numpy 1.26.4
(與 requirements.txt 釘的版本相同)。換了這幾個套件的版本,基準可能要重擷取——
那時請先在未改動的程式上重跑擷取,不要直接改成新值。
"""

import base64
import hashlib
import io

import pytest
from PIL import Image

from _llm_fakes import (
    ALL_FOUR_BEDROCK,
    BedrockRecorder,
    bedrock_ok,
    install_bedrock,
    no_network,  # noqa: F401  (pytest fixture)
)
from _synthetic_images import noisy_png, pdf_from_jpeg, synthetic_jpeg
from app.config import settings
from app.lib.llm_service.providers import (
    BEDROCK_MAX_IMAGE_BYTES,
    BedrockProvider,
    OpenAIProvider,
)
from app.lib.multi_type_ocr.bill_processor import BillProcessor
from app.lib.multi_type_ocr.contract_processor import ContractProcessor
from app.lib.multi_type_ocr.repair_photo_processor import RepairPhotoProcessor
from app.services.analyze_service import AnalyzeService

GOLDEN = {
    "bill_12mp": (
        (1154, 866),
        "395de992203da1c7aa186305d3bb68e71623ac200f461302e428bdc620542c7e",
        "1573572562adfe37d9d1dcb8034e9f2d92b801eff8377255db245919ae873da0",
    ),
    "bill_24mp": (
        (1224, 816),
        "623f7299e5371a723054b8ea873feeeb1a2b3bcb8e1fac9a9c7b3582a277af18",
        "7bd995405472672c81962f757f78febba72145a481f0dfd9e7838903a6736e76",
    ),
    "bill_pdf": (
        (840, 1189),
        "0c26b12f5c24f75dbdb10d4e8e85dcab5bcf317b6845a9052ef89e96f8283ee1",
        "3ce641b34d67c4b0c263bb3866690c4fb2dbc4e84b91e217b89cb1993880d5ce",
    ),
    "contract_pdf": (
        (840, 1189),
        "0c26b12f5c24f75dbdb10d4e8e85dcab5bcf317b6845a9052ef89e96f8283ee1",
        "3ce641b34d67c4b0c263bb3866690c4fb2dbc4e84b91e217b89cb1993880d5ce",
    ),
    "repair_12mp": (
        None,
        None,
        "1573572562adfe37d9d1dcb8034e9f2d92b801eff8377255db245919ae873da0",
    ),
}

ROUTINGS = {"openai": {}, "bedrock": ALL_FOUR_BEDROCK}


def _digest_image(image: Image.Image) -> str:
    return hashlib.sha256(
        image.mode.encode() + repr(image.size).encode() + image.tobytes()
    ).hexdigest()


def _digest_str(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


@pytest.fixture(scope="module")
def inputs():
    return {
        "jpeg_12mp": synthetic_jpeg(4000, 3000),
        "jpeg_24mp": synthetic_jpeg(6000, 4000),
        "pdf": pdf_from_jpeg(synthetic_jpeg(2480, 3508)),
    }


class Capture:
    """記下給 OCR 的影像、送進 Provider 的影像字串,以及 Bedrock 實際送出的請求。"""

    def __init__(self, monkeypatch, ocr_text: str):
        self.ocr = []
        self.provider_images = []     # (provider 名稱, 送進 Provider.call 的 image_data)
        self.bedrock = install_bedrock(monkeypatch, BedrockRecorder(default=bedrock_ok("{}")))

        async def _pre(_self, image):
            self.ocr.append(image.copy())
            return image

        async def _ocr(_self, image):
            return ocr_text, 0.95     # 高信心:不觸發校正,只看抽取送的影像

        for cls in (BillProcessor, ContractProcessor):
            monkeypatch.setattr(cls, "preprocess", _pre)
            monkeypatch.setattr(cls, "extract_text", _ocr)

        async def _openai_call(_self, prompt, image_data=None, **kwargs):
            if image_data:
                self.provider_images.append(("openai", image_data))
            return "{}"

        real_bedrock_call = BedrockProvider.call

        async def _bedrock_call(_self, prompt, image_data=None, **kwargs):
            if image_data:
                self.provider_images.append(("bedrock", image_data))
            return await real_bedrock_call(_self, prompt, image_data=image_data, **kwargs)

        monkeypatch.setattr(OpenAIProvider, "call", _openai_call)
        monkeypatch.setattr(BedrockProvider, "call", _bedrock_call)

    def bedrock_image(self, index: int = 0) -> bytes:
        url = self.bedrock.bodies[index]["messages"][0]["content"][1]["image_url"]["url"]
        return base64.b64decode(url.partition(",")[2])


async def _run(case: str, data: bytes):
    if case.startswith("bill_") and case != "bill_pdf":
        await BillProcessor().process(data, "x.jpg", 1, 1, True)
    elif case == "bill_pdf":
        await AnalyzeService()._process_ocr(data, "x.pdf", "bill", True, None)
    elif case == "contract_pdf":
        await AnalyzeService()._process_ocr(data, "x.pdf", "contract", True, None)
    elif case == "repair_12mp":
        await RepairPhotoProcessor().process(data, "x.jpg", 1, 1, True)


CASES = {
    "bill_12mp": ("jpeg_12mp", "戶號: 01-2345-6789"),
    "bill_24mp": ("jpeg_24mp", "戶號: 01-2345-6789"),
    "bill_pdf": ("pdf", "戶號: 01-2345-6789"),
    "contract_pdf": ("pdf", "付款方式：轉帳"),
    "repair_12mp": ("jpeg_12mp", ""),
}


# --------------------------------------------------------------------------- #
class TestA7_7_ImagesUnchangedFromBeforeTheSwitch:
    @pytest.mark.parametrize("routing", sorted(ROUTINGS))
    @pytest.mark.parametrize("case", sorted(CASES))
    async def test_ocr_input_and_llm_image_match_pre_switch_golden(
        self, monkeypatch, no_network, inputs, case, routing
    ):
        monkeypatch.setattr(settings, "LLM_PROVIDER_BY_DOCUMENT_TYPE", dict(ROUTINGS[routing]))
        input_key, ocr_text = CASES[case]
        capture = Capture(monkeypatch, ocr_text)

        await _run(case, inputs[input_key])

        size, ocr_digest, llm_digest = GOLDEN[case]
        if ocr_digest is not None:
            assert len(capture.ocr) == 1, "OCR 應恰好收到一張影像"
            assert capture.ocr[0].size == size
            assert _digest_image(capture.ocr[0]) == ocr_digest, "給 OCR 的影像與切換前不同"
        else:
            assert capture.ocr == []          # 照片走影像理解,不跑 OCR

        assert len(capture.provider_images) == 1, "LLM 應恰好收到一張影像"
        provider, image_data = capture.provider_images[0]
        assert provider == routing
        assert _digest_str(image_data) == llm_digest, "送進 LLM 的影像與切換前不同"


# --------------------------------------------------------------------------- #
class TestA7_6_BedrockImageMatchesOpenAIRoute:
    @pytest.mark.parametrize("case", ["bill_12mp", "bill_24mp", "bill_pdf", "contract_pdf", "repair_12mp"])
    async def test_bedrock_receives_the_same_image_as_the_openai_route(
        self, monkeypatch, no_network, inputs, case
    ):
        """≤3.75MB 時不重新編碼:Bedrock 請求裡的影像就是 openai 路由那一份,逐位元相同"""
        input_key, ocr_text = CASES[case]

        monkeypatch.setattr(settings, "LLM_PROVIDER_BY_DOCUMENT_TYPE", {})
        openai_capture = Capture(monkeypatch, ocr_text)
        await _run(case, inputs[input_key])
        openai_bytes = base64.b64decode(openai_capture.provider_images[0][1])

        monkeypatch.setattr(settings, "LLM_PROVIDER_BY_DOCUMENT_TYPE", dict(ALL_FOUR_BEDROCK))
        bedrock_capture = Capture(monkeypatch, ocr_text)
        await _run(case, inputs[input_key])
        sent = bedrock_capture.bedrock_image()

        assert len(sent) <= BEDROCK_MAX_IMAGE_BYTES
        assert sent == openai_bytes
        assert Image.open(io.BytesIO(sent)).size == Image.open(io.BytesIO(openai_bytes)).size

    @pytest.mark.parametrize("path", ["image", "pdf"])
    async def test_oversized_page_is_reencoded_same_size_under_limit(
        self, monkeypatch, no_network, path
    ):
        """影像超過 3.75MB:Bedrock 收到同尺寸 JPEG 且 ≤3.75MB;openai 路由仍是原本的 PNG。

        正式環境的像素上限(1M)下 PNG 到不了 3.75MB,這裡把上限調到 1.6M、
        用幾乎不能壓縮的影像才做得出超過上限的頁面;兩個路由用同一組設定。
        """
        monkeypatch.setattr(settings, "OCR_MAX_IMAGE_PIXELS", 1_600_000)
        monkeypatch.setattr(settings, "OCR_MAX_RENDER_PIXELS", 1_600_000)
        # A4 直式比例:PDF 路徑整頁都是雜訊,不留白邊(白邊很好壓縮)
        noisy = Image.open(io.BytesIO(noisy_png(1060, 1500)))
        buf = io.BytesIO()
        noisy.save(buf, format="JPEG", quality=95)
        data = buf.getvalue() if path == "image" else pdf_from_jpeg(buf.getvalue())

        async def run():
            if path == "image":
                await BillProcessor().process(data, "x.jpg", 1, 1, True)
            else:
                await AnalyzeService()._process_ocr(data, "x.pdf", "bill", True, None)

        monkeypatch.setattr(settings, "LLM_PROVIDER_BY_DOCUMENT_TYPE", {})
        openai_capture = Capture(monkeypatch, "戶號: 01-2345-6789")
        await run()
        openai_bytes = base64.b64decode(openai_capture.provider_images[0][1])
        assert len(openai_bytes) > BEDROCK_MAX_IMAGE_BYTES, "前置條件:openai 路由的影像必須超過 3.75MB"
        openai_ocr = _digest_image(openai_capture.ocr[0])

        monkeypatch.setattr(settings, "LLM_PROVIDER_BY_DOCUMENT_TYPE", {"bill": "bedrock"})
        bedrock_capture = Capture(monkeypatch, "戶號: 01-2345-6789")
        await run()
        sent = bedrock_capture.bedrock_image()

        assert len(sent) <= BEDROCK_MAX_IMAGE_BYTES
        sent_image = Image.open(io.BytesIO(sent))
        assert sent_image.format == "JPEG"
        assert sent_image.size == Image.open(io.BytesIO(openai_bytes)).size
        # 重新編碼只發生在 Bedrock 請求裡:送進 Provider 的影像與 OCR 輸入都沒變
        assert bedrock_capture.provider_images[0][1] == openai_capture.provider_images[0][1]
        assert _digest_image(bedrock_capture.ocr[0]) == openai_ocr
