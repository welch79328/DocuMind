"""引擎必須能只靠設定切換,四種文件類型行為一致。

需求 3.6:「引擎選擇 SHALL 可由設定調整,且變更引擎組態不需修改程式碼」。

2026-08-25 之前 contract_processor 寫死 engines=["tesseract"],
是唯一改設定也切不動的類型——而合約正是最需要比較引擎的類型。

切換語法有坑:OCR_ENGINES 是 List[str],pydantic 只吃 JSON。
  OCR_ENGINES='["tesseract"]'        ✓
  OCR_ENGINES='tesseract'            ✗ SettingsError,應用程式直接起不來
"""

import importlib

import pytest

from app.config import settings
from app.lib.ocr_enhanced.config import EngineConfig, validate_engine_config

PROCESSORS = [
    ("app.lib.multi_type_ocr.contract_processor", "ContractProcessor"),
    ("app.lib.multi_type_ocr.transcript_processor", "TranscriptProcessor"),
    ("app.lib.multi_type_ocr.bill_processor", "BillProcessor"),
]


def _engines_of(path, name):
    cls = getattr(importlib.import_module(path), name)
    return list(cls().engine_manager.engines)


class TestAllProcessorsFollowSetting:
    @pytest.mark.parametrize("engines", [
        ["tesseract"],
        ["paddleocr"],
        ["paddleocr", "tesseract"],
    ])
    def test_every_processor_follows_ocr_engines(self, monkeypatch, engines):
        """三種處理器都要跟隨設定;任一個寫死就會在此失敗"""
        monkeypatch.setattr(settings, "OCR_ENGINES", engines)
        got = {name: _engines_of(path, name) for path, name in PROCESSORS}
        wrong = {n: e for n, e in got.items() if e != engines}
        assert not wrong, f"這些處理器沒跟隨 OCR_ENGINES={engines}:{wrong}"

    def test_processors_agree_with_each_other(self, monkeypatch):
        """同一份設定下三者必須一致,否則同一批文件會被不同引擎處理"""
        monkeypatch.setattr(settings, "OCR_ENGINES", ["tesseract"])
        got = [_engines_of(p, n) for p, n in PROCESSORS]
        assert got[0] == got[1] == got[2], f"處理器之間不一致:{got}"


class TestValidEnginesMatchesImplementation:
    """驗證清單不得列出實作不支援的引擎——那會靜默地什麼都不做。

    engine_manager.extract_text_multi_engine 只對 paddleocr / tesseract 建 task。
    若 valid_engines 放行 textract,設定會通過驗證但 tasks 為空,
    使用者拿到空結果卻沒有任何錯誤訊息。
    """

    IMPLEMENTED = {"paddleocr", "tesseract"}

    def test_valid_engines_are_all_implemented(self):
        from app.lib.ocr_enhanced import config as cfg
        import inspect

        src = inspect.getsource(cfg.validate_engine_config)
        listed = set()
        for engine in ["paddleocr", "tesseract", "textract", "paddleocr_vl", "qwen_vl"]:
            if f'"{engine}"' in src.split("valid_engines")[1].split("]")[0]:
                listed.add(engine)
        extra = listed - self.IMPLEMENTED
        assert not extra, (
            f"valid_engines 列了實作不支援的引擎 {sorted(extra)}——"
            "設定會通過驗證但不產生任何 OCR task,使用者拿到空結果且無錯誤訊息"
        )

    def test_unimplemented_engine_is_rejected(self):
        """設一個沒實作的引擎必須被擋下,不能靜默通過"""
        with pytest.raises(ValueError):
            validate_engine_config(EngineConfig(engines=["textract"]))
