"""多引擎並行預設的守衛測試。

2026-08-24 業主定案:`parallel` 由 False 改為預設 True。
依據為線上 2 vCPU / 3.7GB 同一份謄本實測——循序 36.7s、並行 31.7s(省 13.6%),
辨識結果不變。本檔的存在是為了讓「改回 False」或「接錯設定」立刻失敗,
而不是等到效能退步才有人發現。
"""

import pytest

from app.config import settings
from app.lib.ocr_enhanced.config import EngineConfig
from app.lib.ocr_enhanced.engine_manager import EngineManager


class TestParallelDefault:
    def test_setting_defaults_to_parallel(self):
        """設定層預設為並行;有人改回 False 時此處失敗"""
        assert settings.OCR_PARALLEL_ENGINES is True

    def test_engine_manager_constructor_defaults_to_parallel(self):
        """未指定 parallel 時採並行;建構子預設被改回 False 時此處失敗"""
        assert EngineManager().parallel is True

    def test_engine_config_dataclass_matches_manager(self):
        """EngineConfig 與 EngineManager 的預設須一致,否則兩條路徑行為分歧"""
        assert EngineConfig().parallel is EngineManager().parallel


class TestProcessorWiring:
    """處理器必須讀 OCR_PARALLEL_ENGINES,不是寫死、也不是讀別的旗標。

    以 monkeypatch 把設定翻成 False 後重建處理器:若仍為 True,
    代表接線接錯或被寫死——這是本檔最實質的一條。
    """

    @pytest.mark.parametrize("import_path,cls_name", [
        ("app.lib.multi_type_ocr.transcript_processor", "TranscriptProcessor"),
        ("app.lib.multi_type_ocr.bill_processor", "BillProcessor"),
    ])
    def test_processor_follows_setting(self, monkeypatch, import_path, cls_name):
        import importlib

        cls = getattr(importlib.import_module(import_path), cls_name)

        monkeypatch.setattr(settings, "OCR_PARALLEL_ENGINES", True)
        assert cls().engine_manager.parallel is True

        monkeypatch.setattr(settings, "OCR_PARALLEL_ENGINES", False)
        assert cls().engine_manager.parallel is False, (
            f"{cls_name} 未跟隨 OCR_PARALLEL_ENGINES —— 接線接錯或被寫死"
        )

    def test_not_wired_to_retired_flag(self, monkeypatch):
        """OCR_MULTI_ENGINE 已停用;翻動它不得再影響任何處理器"""
        from app.lib.multi_type_ocr.transcript_processor import TranscriptProcessor

        monkeypatch.setattr(settings, "OCR_PARALLEL_ENGINES", True)
        monkeypatch.setattr(settings, "OCR_MULTI_ENGINE", False)
        assert TranscriptProcessor().engine_manager.parallel is True
