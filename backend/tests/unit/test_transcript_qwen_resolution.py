"""謄本在引擎只有 qwen 時,送讀字的影像長邊 2000(PDF 頁與照片都是)。

2026-11-19 惠文路謄本第 1 頁:1.0M 像素上限下(880×1138)qwen 的行框上下偏移中位
0.33–0.37 行;長邊 2000 降到 0.15–0.19 行。拿掉這兩處,v2 位置框會回到對不準該行。
"""

import io

import numpy as np
import pytest
from PIL import Image

from app.config import settings
from app.services.analyze_service import _page_render_scale, _render_scale


class _Rect:
    def __init__(self, width, height):
        self.width = width
        self.height = height


A4 = _Rect(595, 842)  # point


@pytest.fixture
def engines(monkeypatch):
    def _set(value):
        monkeypatch.setattr(settings, "OCR_ENGINES", value)
    return _set


class TestPdfPageRender:
    def test_transcript_qwen_only_renders_long_edge_2000(self, engines):
        engines(["qwen"])
        scale = _page_render_scale(A4, "transcript", direct_read=False)
        assert round(842 * scale) == 2000
        # 正對照:同一頁走 1.0M 上限時長邊遠小於 2000
        assert 842 * _render_scale(A4) < 1500

    def test_transcript_with_paddleocr_keeps_pixel_cap(self, engines):
        engines(["paddleocr", "qwen"])
        assert _page_render_scale(A4, "transcript", False) == _render_scale(A4)

    def test_other_types_unchanged(self, engines):
        engines(["qwen"])
        assert _page_render_scale(A4, "contract", False) == _render_scale(A4)
        assert round(842 * _page_render_scale(A4, "bill", True)) == 2000  # 直讀照舊


def _png(width, height):
    arr = np.random.default_rng(7).integers(0, 256, size=(height, width, 3), dtype="uint8")
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


async def _seen_size(engine_list, width, height):
    from app.lib.multi_type_ocr.transcript_processor import TranscriptProcessor

    proc = TranscriptProcessor()
    proc.engine_manager.engines = engine_list
    seen = {}

    async def _analyze(image, image_data=None, enable_llm=False, few_shot=None):
        seen["size"] = image.size
        return {}

    proc.analyze = _analyze
    await proc.process(
        file_contents=_png(width, height), filename="t.png",
        page_number=1, total_pages=1, enable_llm=False,
    )
    return seen["size"]


class TestPhoto:
    async def test_qwen_only_photo_long_edge_2000(self):
        assert await _seen_size(["qwen"], 4000, 3000) == (2000, 1500)

    async def test_qwen_only_small_photo_untouched(self):
        assert await _seen_size(["qwen"], 1200, 900) == (1200, 900)

    async def test_paddleocr_photo_keeps_pixel_cap(self):
        w, h = await _seen_size(["paddleocr"], 4000, 3000)
        assert w * h <= settings.OCR_MAX_IMAGE_PIXELS
