"""2026-08-24 OOM 事故的防線(2026-09-04 由三道增為四道)。

事故:在線上機器(3.7GB、容器無 mem_limit)以 300 DPI 渲染合約頁 + 去噪 +
雙引擎並行跑 OCR,`docker inspect .State.OOMKilled` 為 true,
主機 load average 衝到 51.35(2 vCPU),一頁都沒產出。

四道防線各自獨立,任一道被拆掉都應該讓這裡變紅:
  1. 渲染像素上限   —— 從源頭縮小單頁的點陣尺寸(PDF 路徑)
  2. 並行記憶體守衛 —— 記憶體吃緊時退回循序(峰值由「相加」變回「取大」)
  3. 容器 mem_limit —— 在 docker-compose.yml,由 test_compose_has_mem_limits 顧
  4. 影像像素上限   —— 上傳影像(非 PDF)進 OCR 前的點陣上限,2026-09-04 補
                       在此之前影像路徑完全沒有上限:analyze_service 對非 PDF
                       走 `page_bytes = file_contents`,原檔直接進解碼
"""

import asyncio
import re
from pathlib import Path

import pytest

from app.config import settings
from app.lib.ocr_enhanced import memory_guard
from app.lib.ocr_enhanced.engine_manager import EngineManager


class _Rect:
    def __init__(self, width, height):
        self.width = width
        self.height = height


A4 = _Rect(595, 842)        # point


class TestRenderScale:
    """防線 1:單頁渲染不得超過像素上限。"""

    def _scale(self):
        from app.services.analyze_service import _render_scale
        return _render_scale

    def test_a4_is_capped(self):
        """A4 在 300 DPI 是 8.7M 像素,必須被壓到上限以內"""
        scale = self._scale()(A4)
        pixels = (A4.width * scale) * (A4.height * scale)
        assert pixels <= settings.OCR_MAX_RENDER_PIXELS * 1.001, (
            f"A4 渲染出 {pixels/1e6:.2f}M 像素,超過上限 "
            f"{settings.OCR_MAX_RENDER_PIXELS/1e6:.2f}M"
        )

    def test_a4_actually_shrank(self):
        """壓縮必須真的發生——若上限被調到大於 8.7M,這條會提醒你"""
        scale = self._scale()(A4)
        assert scale < settings.OCR_RENDER_DPI / 72.0, (
            "A4 未被縮小,像素上限形同虛設"
        )

    def test_small_page_keeps_full_dpi(self):
        """小頁面不該被無謂降級——上限只在超標時生效。

        頁面尺寸刻意選在 300 DPI 下仍低於上限之處(150×300 pt → 625×1250
        ≈ 0.78M 像素)。若日後把上限調得更低,這裡要跟著換更小的頁面,
        否則測的就不再是「小頁面不降級」而是「上限有沒有生效」——
        下方的前置斷言會直接告訴你該換了(2026-08-24 已因此換過兩次)。
        """
        small = _Rect(150, 300)
        full = settings.OCR_RENDER_DPI / 72.0
        assert (small.width * full) * (small.height * full) < settings.OCR_MAX_RENDER_PIXELS, (
            "測試用的頁面在目前上限下已不算小,請改用更小的尺寸"
        )
        assert self._scale()(small) == pytest.approx(full)

    # 2026-08-24 於線上容器實測峰值 RSS(單頁、單引擎、循序,**文字密集的內文頁**):
    #   3.0M → >1626 MB ✗   2.0M → >1503 MB ✗   1.5M → >1454 MB ✗
    #   1.25M → 1453 MB ✓(餘裕僅 106MB)      1.0M → 1323 MB ✓(餘裕 236MB)
    # 可用空間 = 容器上限 2048MB − 應用程式本身 489MB ≈ 1559MB
    #
    # ⚠️ 這個常數先後錯過兩次(4M、2M),兩次都是拿只有 5 行的**封面頁**校準的。
    # 記憶體主要由文字密度決定,不是像素數。要調高請先用內文頁重測。
    MEASURED_SAFE_MAX_PIXELS = 1_000_000

    def test_cap_is_within_the_measured_safe_ceiling(self):
        """上限不得高於實測裝得下的值。

        原本設 4_000_000 是用推算的(「A4 降到 203 DPI 應該夠」),實測不夠。
        有人想調高時,請先在目標機器上重測峰值 RSS 再改這裡的常數。
        """
        assert 0 < settings.OCR_MAX_RENDER_PIXELS <= self.MEASURED_SAFE_MAX_PIXELS, (
            f"OCR_MAX_RENDER_PIXELS={settings.OCR_MAX_RENDER_PIXELS} 高於實測安全值 "
            f"{self.MEASURED_SAFE_MAX_PIXELS};4.0M 已實測會超出容器可用記憶體"
        )

    def test_cap_can_be_disabled(self):
        """上限設 0 時退回純 DPI 行為(留給大機器)"""
        from app.services import analyze_service

        original = settings.OCR_MAX_RENDER_PIXELS
        try:
            settings.OCR_MAX_RENDER_PIXELS = 0
            assert analyze_service._render_scale(A4) == pytest.approx(
                settings.OCR_RENDER_DPI / 72.0
            )
        finally:
            settings.OCR_MAX_RENDER_PIXELS = original


class TestMemoryGuard:
    """防線 2:記憶體不足時不得並行。"""

    def test_refuses_parallel_when_memory_is_low(self, monkeypatch):
        """可用 200MB、門檻 1024MB → 不准並行"""
        monkeypatch.setattr(memory_guard, "available_mb", lambda: 200)
        assert memory_guard.parallel_is_safe(1024) is False

    def test_allows_parallel_when_memory_is_ample(self, monkeypatch):
        monkeypatch.setattr(memory_guard, "available_mb", lambda: 4096)
        assert memory_guard.parallel_is_safe(1024) is True

    def test_allows_parallel_when_detection_fails(self, monkeypatch):
        """偵測不到時維持既有行為,不要因為讀不到 /proc 就讓所有人變慢"""
        monkeypatch.setattr(memory_guard, "available_mb", lambda: None)
        assert memory_guard.parallel_is_safe(1024) is True

    def test_threshold_zero_disables_the_guard(self, monkeypatch):
        monkeypatch.setattr(memory_guard, "available_mb", lambda: 1)
        assert memory_guard.parallel_is_safe(0) is True

    @pytest.mark.skipif(not __import__("sys").platform.startswith("linux"),
                        reason="生產環境是 Linux 容器;macOS 無 SC_AVPHYS_PAGES,"
                               "守衛在該平台刻意退回允許並行(見 memory_guard 說明)")
    def test_available_mb_works_on_linux(self):
        """Linux 上必須偵測得到,否則守衛在生產環境等於沒作用"""
        avail = memory_guard.available_mb()
        assert avail is not None and avail > 0

    def test_falls_back_safely_when_platform_lacks_detection(self):
        """偵測不到時的行為必須是明確的:允許並行,不得拋例外"""
        assert memory_guard.parallel_is_safe(1024) in (True, False)


class TestEngineManagerHonoursGuard:
    """防線 2 的接線:守衛說不行,EngineManager 就必須真的走循序。"""

    @staticmethod
    def _manager():
        em = EngineManager(engines=["paddleocr", "tesseract"], parallel=True)
        return em

    def _run(self, monkeypatch, guard_verdict):
        """以假引擎記錄實際執行序,回傳 (是否並行, 呼叫順序)"""
        import app.lib.ocr_enhanced.memory_guard as mg

        monkeypatch.setattr(mg, "parallel_is_safe", lambda _mb: guard_verdict)

        em = self._manager()
        order = []
        gathered = {"used": False}

        async def fake_engine(tag, delay):
            order.append(f"{tag}:start")
            await asyncio.sleep(delay)
            order.append(f"{tag}:end")
            raise RuntimeError("fake")   # 走失敗路徑即可,我們只看執行序

        monkeypatch.setattr(em, "_run_paddleocr",
                            lambda img: fake_engine("paddle", 0.05))
        monkeypatch.setattr(em, "_run_tesseract",
                            lambda img: fake_engine("tess", 0.0))

        real_gather = asyncio.gather

        def spy_gather(*a, **k):
            gathered["used"] = True
            return real_gather(*a, **k)

        monkeypatch.setattr(asyncio, "gather", spy_gather)

        import numpy as np
        asyncio.run(em.extract_text_multi_engine(np.zeros((4, 4, 3), dtype="uint8")))
        return gathered["used"], order

    def test_falls_back_to_sequential_when_guard_refuses(self, monkeypatch):
        used_gather, order = self._run(monkeypatch, guard_verdict=False)
        assert used_gather is False, "守衛拒絕並行,卻仍走了 asyncio.gather"
        assert order == ["paddle:start", "paddle:end", "tess:start", "tess:end"], (
            f"應為循序執行,實際順序:{order}"
        )

    def test_runs_parallel_when_guard_allows(self, monkeypatch):
        used_gather, order = self._run(monkeypatch, guard_verdict=True)
        assert used_gather is True, "守衛允許並行,卻沒走 asyncio.gather"
        assert order[:2] == ["paddle:start", "tess:start"], (
            f"並行時兩引擎應先後啟動再結束,實際順序:{order}"
        )


class TestComposeHasMemLimits:
    """防線 3:容器必須有記憶體上限,否則一個容器能吃垮整台。"""

    REQUIRED = {"ai-doc-postgres", "ai-doc-backend",
                "ai-doc-frontend", "ai-doc-nginx"}

    def test_every_container_has_a_mem_limit(self):
        # parents[3] 在本機是 repo 根;容器裡只掛了 ./backend:/app,repo 根不存在,
        # docker-compose.yml 本來就不在容器內(2026-08-24 於線上實測)。
        # 因此:認得出是 repo 佈局才斷言,認不出就跳過——不是靜默放行,
        # 而是「這個環境看不到那個檔案」。
        repo_root = Path(__file__).resolve().parents[3]
        looks_like_repo = (repo_root / "backend").is_dir() or (repo_root / ".git").exists()
        compose = repo_root / "docker-compose.yml"

        if not looks_like_repo:
            pytest.skip("非 repo 佈局(容器內只掛 ./backend),看不到 docker-compose.yml")

        assert compose.exists(), (
            f"這是 repo 佈局卻找不到 {compose}——compose 檔被移除或改名了"
        )
        text = compose.read_text(encoding="utf-8")

        found = {}
        current = None
        for line in text.splitlines():
            name = re.match(r"\s*container_name:\s*(\S+)", line)
            if name:
                current = name.group(1)
                continue
            lim = re.match(r"\s*mem_limit:\s*(\S+)", line)
            if lim and current:
                found[current] = lim.group(1)
                current = None

        missing = self.REQUIRED - found.keys()
        assert not missing, (
            f"這些容器沒有 mem_limit,可吃光主機記憶體:{sorted(missing)}"
        )


class TestImagePixelCap:
    """防線 4:上傳影像進 OCR 前必須被縮到 OCR_MAX_IMAGE_PIXELS 以內。

    斷言刻意落在 **analyze() 實際收到的影像尺寸** 上,而不是 _cap_image_pixels()
    的回傳值——後者是被測函式自己說的話。process() 在縮圖之後還會存一份 PNG
    並轉 base64,那兩個消費者拿到的必須也是縮過的,所以這裡連 original_image
    一起驗。
    """

    CAP_KEY = "OCR_MAX_IMAGE_PIXELS"

    @staticmethod
    def _png_bytes(width: int, height: int) -> bytes:
        """產一張指定尺寸的 PNG。用雜訊而非純色——純色 PNG 會被壓到極小,
        且某些路徑對單色影像有捷徑,測不到真實行為。"""
        import io

        import numpy as np
        from PIL import Image

        rng = np.random.default_rng(seed=1234)
        arr = rng.integers(0, 256, size=(height, width, 3), dtype="uint8")
        buf = io.BytesIO()
        Image.fromarray(arr).save(buf, format="PNG")
        return buf.getvalue()

    @staticmethod
    def _processor():
        """最小的具體 DocumentProcessor:記下 analyze() 收到的影像尺寸。"""
        from app.lib.multi_type_ocr.processor import DocumentProcessor

        class _Recording(DocumentProcessor):
            def __init__(self):
                self.seen_size = None

            async def analyze(self, image, image_data=None,
                              enable_llm=False, few_shot=None):
                self.seen_size = image.size
                return {}

        return _Recording()

    async def _run(self, width, height):
        proc = self._processor()
        result = await proc.process(
            file_contents=self._png_bytes(width, height),
            filename="test.png",
            page_number=1,
            total_pages=1,
            enable_llm=False,
        )
        return proc, result

    async def test_oversized_image_is_capped(self):
        """超過上限的影像,下游收到的必須已經縮到上限以內"""
        cap = settings.OCR_MAX_IMAGE_PIXELS
        # 前置斷言:測試輸入必須真的超標,否則測到的是「不縮圖」而非「縮圖」
        assert 2000 * 1500 > cap, (
            f"測試影像 3.0M 像素未超過上限 {cap};上限被調高了,請換更大的測試影像"
        )

        proc, _ = await self._run(2000, 1500)
        seen_pixels = proc.seen_size[0] * proc.seen_size[1]
        assert seen_pixels <= cap, (
            f"analyze() 收到 {seen_pixels/1e6:.2f}M 像素,超過上限 {cap/1e6:.2f}M"
        )

    async def test_aspect_ratio_is_preserved(self):
        """縮圖不得變形——4:3 進去必須還是 4:3 出來"""
        proc, _ = await self._run(2000, 1500)
        w, h = proc.seen_size
        assert abs((w / h) - (2000 / 1500)) < 0.01, f"長寬比跑掉了:{w}x{h}"

    async def test_small_image_is_untouched(self):
        """未超標的影像不得被無謂處理——上限只在超標時生效"""
        cap = settings.OCR_MAX_IMAGE_PIXELS
        assert 400 * 300 < cap, "測試影像已不算小,請換更小的尺寸"

        proc, _ = await self._run(400, 300)
        assert proc.seen_size == (400, 300), (
            f"小影像被動了:400x300 → {proc.seen_size}"
        )

    async def test_original_image_reflects_the_cap(self):
        """回傳的 original_image base64 也必須是縮過的。

        它會整份進記憶體、進 API 回應、進 VLM 的請求;若這裡還是原尺寸,
        縮圖省下的記憶體會在這一步全部吐回去。
        """
        import base64
        import io

        from PIL import Image

        _, result = await self._run(2000, 1500)
        raw = result["original_image"].split("base64,", 1)[-1]
        with Image.open(io.BytesIO(base64.b64decode(raw))) as img:
            pixels = img.size[0] * img.size[1]
        assert pixels <= settings.OCR_MAX_IMAGE_PIXELS, (
            f"original_image 有 {pixels/1e6:.2f}M 像素,沒有跟著縮"
        )

    async def test_cap_can_be_disabled(self):
        """上限設 0 時停用縮圖(與 OCR_MAX_RENDER_PIXELS 的 0 語意一致)"""
        original = settings.OCR_MAX_IMAGE_PIXELS
        try:
            settings.OCR_MAX_IMAGE_PIXELS = 0
            proc, _ = await self._run(2000, 1500)
            assert proc.seen_size == (2000, 1500), (
                f"上限已停用卻仍縮圖:{proc.seen_size}"
            )
        finally:
            settings.OCR_MAX_IMAGE_PIXELS = original

    # 影像路徑的記憶體剖面與 PDF 不同(多一份 PNG 重新編碼 + base64 的 1.33 倍),
    # 但初值是**承接** PDF 路徑的實測值,不是影像自己量出來的。在影像路徑有自己的
    # 實測數字之前,安全上界沿用同一個值——要調高請先用
    # `scripts/measure_ocr_memory.py <影像檔>` 實測,不要沿用 PDF 那張表。
    INHERITED_SAFE_MAX_PIXELS = 1_000_000

    def test_cap_is_within_the_inherited_safe_ceiling(self):
        assert 0 < settings.OCR_MAX_IMAGE_PIXELS <= self.INHERITED_SAFE_MAX_PIXELS, (
            f"OCR_MAX_IMAGE_PIXELS={settings.OCR_MAX_IMAGE_PIXELS} 高於承接自 PDF "
            f"路徑的安全值 {self.INHERITED_SAFE_MAX_PIXELS};影像路徑另有 PNG 重新"
            f"編碼與 base64 放大的成本,調高前請以影像實測"
        )

    def test_image_cap_is_a_separate_knob_from_the_pdf_cap(self):
        """兩個常數必須各自獨立存在。

        合併成一個會讓 PDF 的校準表(用內文頁量的)被套到剖面不同的影像路徑上,
        且任一邊要調就會動到另一邊。
        """
        assert hasattr(settings, "OCR_MAX_IMAGE_PIXELS")
        assert hasattr(settings, "OCR_MAX_RENDER_PIXELS")
        assert (
            type(settings).model_fields["OCR_MAX_IMAGE_PIXELS"]
            is not type(settings).model_fields["OCR_MAX_RENDER_PIXELS"]
        ), "兩個上限被指向同一個設定欄位"
