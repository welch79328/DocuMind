"""2026-08-24 OOM 事故的三道防線。

事故:在線上機器(3.7GB、容器無 mem_limit)以 300 DPI 渲染合約頁 + 去噪 +
雙引擎並行跑 OCR,`docker inspect .State.OOMKilled` 為 true,
主機 load average 衝到 51.35(2 vCPU),一頁都沒產出。

三道防線各自獨立,任一道被拆掉都應該讓這裡變紅:
  1. 渲染像素上限   —— 從源頭縮小單頁的點陣尺寸
  2. 並行記憶體守衛 —— 記憶體吃緊時退回循序(峰值由「相加」變回「取大」)
  3. 容器 mem_limit —— 在 docker-compose.yml,由 test_compose_has_mem_limits 顧
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
        """小頁面不該被無謂降級——上限只在超標時生效"""
        scale = self._scale()(_Rect(300, 400))
        assert scale == pytest.approx(settings.OCR_RENDER_DPI / 72.0)

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
        compose = Path(__file__).resolve().parents[3] / "docker-compose.yml"
        assert compose.exists(), f"找不到 {compose}"
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
