"""OCR 併發閘門:頁面可重疊,引擎執行不可。

## 為什麼需要這道閘門

2026-09-03 盤查:單 uvicorn worker、無 `--limit-concurrency`、程式碼無 Semaphore。
而單頁 OCR 峰值實測 1141–1778 MB,backend 容器可用約 1695 MB
(上限 2048 − 應用程式本身約 353)。**兩個請求同時進來就會把容器 OOM 掉**,
而在此之前沒有任何機制擋著——當時只是因為沒有實際流量才沒出事。

## 為什麼閘門放在 EngineManager 而不是 API 層

記憶體是被**引擎執行**吃掉的。放在 EngineManager,同一份文件的多頁併發、
與不同使用者的併發請求,都受同一個上限約束;放在 API 層只擋得住後者。

## 為什麼頁面仍要併發

4 頁謄本實測 151s,其中 LLM 佔 24.6s/頁(98s,65%)。LLM 在遠端算,
本機只是等 HTTP——那 98 秒是排隊等網路,不是在用記憶體。讓頁面重疊後
該段降到約 25s(取最慢者),而 OCR 仍由閘門序列化。
"""

import asyncio

import numpy as np
import pytest

from app.config import settings
from app.lib.ocr_enhanced import engine_manager as em_mod
from app.lib.ocr_enhanced.engine_manager import EngineManager

IMG = np.zeros((4, 4, 3), dtype="uint8")


def _reset_gate():
    """閘門是行程層級狀態,測試間要清掉,否則會共用前一個測試的迴圈"""
    em_mod._ocr_gate = None
    em_mod._ocr_gate_limit = -1


class TestEngineExecutionIsSerialised:
    def _manager_with_probe(self, monkeypatch, tracker):
        em = EngineManager(engines=["paddleocr"], parallel=False)

        async def fake(_img):
            tracker["live"] += 1
            tracker["peak"] = max(tracker["peak"], tracker["live"])
            await asyncio.sleep(0.05)
            tracker["live"] -= 1
            raise RuntimeError("fake engine")   # 走失敗路徑即可,只看併發數

        monkeypatch.setattr(em, "_run_paddleocr", fake)
        return em

    def test_only_one_engine_run_at_a_time(self, monkeypatch):
        """五頁同時進來,同一瞬間最多只有一頁在跑引擎"""
        _reset_gate()
        monkeypatch.setattr(settings, "OCR_MAX_CONCURRENT", 1)
        tracker = {"live": 0, "peak": 0}

        async def run():
            em = self._manager_with_probe(monkeypatch, tracker)
            await asyncio.gather(*(em.extract_text_multi_engine(IMG) for _ in range(5)))

        asyncio.run(run())
        assert tracker["peak"] == 1, (
            f"同時有 {tracker['peak']} 頁在跑引擎——閘門沒生效,容器會 OOM"
        )

    def test_limit_is_configurable(self, monkeypatch):
        """換大機器時調高上限要真的生效"""
        _reset_gate()
        monkeypatch.setattr(settings, "OCR_MAX_CONCURRENT", 3)
        tracker = {"live": 0, "peak": 0}

        async def run():
            em = self._manager_with_probe(monkeypatch, tracker)
            await asyncio.gather(*(em.extract_text_multi_engine(IMG) for _ in range(6)))

        asyncio.run(run())
        assert tracker["peak"] == 3, f"上限設 3,實際峰值 {tracker['peak']}"

    def test_gate_is_released_when_engine_raises(self, monkeypatch):
        """引擎拋例外時閘門必須釋放,否則第一次失敗就永久卡死整個服務"""
        _reset_gate()
        monkeypatch.setattr(settings, "OCR_MAX_CONCURRENT", 1)
        tracker = {"live": 0, "peak": 0}

        async def run():
            em = self._manager_with_probe(monkeypatch, tracker)
            for _ in range(3):
                await asyncio.wait_for(em.extract_text_multi_engine(IMG), timeout=2)

        asyncio.run(run())   # 逾時即代表閘門沒釋放


class TestPagesStillOverlap:
    """閘門不得把頁面層也序列化——那會讓 LLM 的網路等待又接回去。"""

    def test_page_gate_allows_overlap(self, monkeypatch):
        monkeypatch.setattr(settings, "OCR_MAX_CONCURRENT_PAGES", 4)
        tracker = {"live": 0, "peak": 0}

        async def fake_page():
            tracker["live"] += 1
            tracker["peak"] = max(tracker["peak"], tracker["live"])
            await asyncio.sleep(0.05)      # 模擬 LLM 的網路等待
            tracker["live"] -= 1

        async def run():
            gate = asyncio.Semaphore(settings.OCR_MAX_CONCURRENT_PAGES)

            async def one():
                async with gate:
                    await fake_page()

            await asyncio.gather(*(one() for _ in range(4)))

        asyncio.run(run())
        assert tracker["peak"] > 1, "頁面沒有重疊,LLM 的網路等待會被串接起來"


class TestSettingsAreSane:
    def test_ocr_concurrency_is_at_least_one(self):
        assert settings.OCR_MAX_CONCURRENT >= 1

    def test_page_concurrency_is_at_least_ocr_concurrency(self):
        """頁面上限低於 OCR 上限沒有意義——OCR 永遠吃不滿"""
        assert settings.OCR_MAX_CONCURRENT_PAGES >= settings.OCR_MAX_CONCURRENT
