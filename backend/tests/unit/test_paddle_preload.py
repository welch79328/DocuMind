"""
PaddleOCR 啟動預載(2026-09-21)

線上實測(t3.medium):當天第一個 OCR 請求 27.2 秒,之後同類請求 15.0–18.4 秒,
多出的約 12 秒是模型載入。改為啟動時在背景預載。

⚠️ 本檔的重點是併發那一組。預載在背景執行緒跑,完成前第一個請求就可能進來;
沒有建構鎖,兩邊會各建一份模型——單頁 OCR 峰值已達 1141–1778 MB、
容器上限 2 GB,兩份模型必然 OOM。那不是「慢一點」,是服務被殺掉。

這裡用假的 paddleocr 模組:建構子刻意放慢,讓競爭條件穩定重現。
"""

import sys
import threading
import time
import types
from unittest.mock import patch

import pytest

from app.lib.ocr_enhanced import engine_manager
from app.lib.ocr_enhanced.engine_manager import EngineManager, preload_paddleocr


@pytest.fixture(autouse=True)
def _reset_singleton():
    """單例是類別屬性,測試間必須清掉,否則後面的測試拿到前面的假物件"""
    EngineManager._paddleocr_instance = None
    yield
    EngineManager._paddleocr_instance = None


def _fake_paddleocr_module(build_seconds=0.0, fail=False):
    """回傳 (假模組, 建構次數計數器)"""
    calls = {"n": 0}
    lock = threading.Lock()

    class FakePaddleOCR:
        def __init__(self, **kwargs):
            with lock:
                calls["n"] += 1
            if build_seconds:
                time.sleep(build_seconds)
            if fail:
                raise OSError("模型檔損毀(測試用)")
            self.kwargs = kwargs

    module = types.ModuleType("paddleocr")
    module.PaddleOCR = FakePaddleOCR
    return module, calls


class TestConcurrentInitBuildsOnce:

    def test_preload_racing_with_requests_builds_one_model(self):
        """預載與 8 個請求同時搶初始化:只能建一份,且大家拿到同一份"""
        module, calls = _fake_paddleocr_module(build_seconds=0.3)
        results = []

        def request():
            results.append(EngineManager(engines=["paddleocr"])._ensure_paddleocr())

        with patch.dict(sys.modules, {"paddleocr": module}):
            threads = [threading.Thread(target=preload_paddleocr, args=("chinese_cht",))]
            threads += [threading.Thread(target=request) for _ in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10)

        assert calls["n"] == 1, f"模型被建了 {calls['n']} 份——線上會 OOM"
        assert len(results) == 8
        assert all(r is results[0] for r in results)
        assert EngineManager._paddleocr_instance is results[0]

    def test_request_after_preload_reuses_instance(self):
        """預載完成後的請求直接拿現成的,不再建構"""
        module, calls = _fake_paddleocr_module()
        with patch.dict(sys.modules, {"paddleocr": module}):
            preload_paddleocr("chinese_cht")
            first = EngineManager._paddleocr_instance
            got = EngineManager(engines=["paddleocr"])._ensure_paddleocr()
        assert calls["n"] == 1
        assert got is first

    def test_preload_uses_measured_parameters(self):
        """預載走的是同一個建構路徑,實測參數(ONNX、偵測邊長 960)不能因此遺失"""
        module, _ = _fake_paddleocr_module()
        with patch.dict(sys.modules, {"paddleocr": module}):
            preload_paddleocr("chinese_cht")
        kwargs = EngineManager._paddleocr_instance.kwargs
        assert kwargs["engine"] == "onnxruntime"
        assert kwargs["text_det_limit_side_len"] == 960
        assert kwargs["lang"] == "chinese_cht"


class TestPreloadFailsSoft:
    """預載失敗不得讓服務起不來:本機與測試環境根本沒裝 paddle"""

    def test_paddle_not_installed(self, caplog):
        with patch.dict(sys.modules, {"paddleocr": None}):   # import 會拋 ImportError
            preload_paddleocr("chinese_cht")                  # 不得拋出
        assert EngineManager._paddleocr_instance is None
        assert "預載失敗" in caplog.text

    def test_model_build_error(self, caplog):
        module, _ = _fake_paddleocr_module(fail=True)
        with patch.dict(sys.modules, {"paddleocr": module}):
            preload_paddleocr("chinese_cht")
        assert EngineManager._paddleocr_instance is None
        assert "預載失敗" in caplog.text

    def test_failed_preload_leaves_lazy_path_working(self):
        """預載失敗後,首次請求仍照舊惰性載入(並能在那時成功)"""
        with patch.dict(sys.modules, {"paddleocr": None}):
            preload_paddleocr("chinese_cht")
        module, calls = _fake_paddleocr_module()
        with patch.dict(sys.modules, {"paddleocr": module}):
            got = EngineManager(engines=["paddleocr"])._ensure_paddleocr()
        assert calls["n"] == 1
        assert got is EngineManager._paddleocr_instance


class TestLifespanWiring:
    """啟動流程只在開啟且使用 paddleocr 時預載,且不阻塞啟動"""

    def _run_lifespan(self, preload_enabled, engines):
        from fastapi.testclient import TestClient
        from app.main import app
        from app.config import settings

        called = threading.Event()
        with patch.object(settings, "OCR_PRELOAD_MODEL", preload_enabled), \
             patch.object(settings, "OCR_ENGINES", engines), \
             patch.object(engine_manager, "preload_paddleocr",
                          side_effect=lambda lang: called.set()):
            with TestClient(app):
                pass
            called.wait(timeout=2)
        return called.is_set()

    def test_preloads_when_enabled(self):
        assert self._run_lifespan(True, ["paddleocr"]) is True

    def test_skips_when_disabled(self):
        assert self._run_lifespan(False, ["paddleocr"]) is False

    def test_skips_when_paddle_not_an_engine(self):
        """線上若改成只用 tesseract,就不該去載一個用不到的模型"""
        assert self._run_lifespan(True, ["tesseract"]) is False

    def test_startup_not_blocked_by_slow_preload(self):
        """預載很慢(模擬 12 秒載入)時,啟動仍須立即完成"""
        from fastapi.testclient import TestClient
        from app.main import app
        from app.config import settings

        release = threading.Event()
        with patch.object(settings, "OCR_PRELOAD_MODEL", True), \
             patch.object(settings, "OCR_ENGINES", ["paddleocr"]), \
             patch.object(engine_manager, "preload_paddleocr",
                          side_effect=lambda lang: release.wait(timeout=5)):
            started = time.perf_counter()
            with TestClient(app) as client:
                elapsed = time.perf_counter() - started
                assert client.get("/api/health").status_code == 200
            release.set()
        assert elapsed < 1.0, f"啟動被預載卡住 {elapsed:.2f} 秒"
