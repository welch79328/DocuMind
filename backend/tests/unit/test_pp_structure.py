"""
測試 PP-Structure 版面解析增強骨架(任務 10.3)

PP-Structure 為謄本增強「選項」,預設關閉、不阻塞主線:
- 預設停用時不觸發、回 None
- 啟用但 PP-Structure 未安裝時優雅降級(不 crash)
- 可經設定切換

對應需求: 2.1
"""

import numpy as np
import pytest

from app.config import settings
from app.lib.ocr_enhanced.pp_structure import PPStructureEnhancer


class TestToggle:
    def test_disabled_by_default(self):
        assert PPStructureEnhancer().is_enabled() is False

    def test_enable_via_settings(self, monkeypatch):
        monkeypatch.setattr(settings, "OCR_ENABLE_PP_STRUCTURE", True)
        assert PPStructureEnhancer().is_enabled() is True


class TestDegrade:
    async def test_returns_none_when_disabled(self):
        img = np.zeros((30, 30, 3), dtype=np.uint8)
        assert await PPStructureEnhancer().parse_layout(img) is None

    async def test_degrades_gracefully_when_unavailable(self, monkeypatch):
        # 啟用但 PP-Structure 未安裝 → 降級回 None,不 crash(不阻塞主線)
        monkeypatch.setattr(settings, "OCR_ENABLE_PP_STRUCTURE", True)
        img = np.zeros((30, 30, 3), dtype=np.uint8)
        result = await PPStructureEnhancer().parse_layout(img)
        assert result is None
