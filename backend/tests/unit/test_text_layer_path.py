"""含文字層的 PDF 必須略過 OCR,而且仍要拿到欄位。

2026-09-03 實測(4 頁電子謄本,線上):

    走 OCR      85s,字元錯誤率 14.5%
    走文字層    <1s,**逐字精確**

快 85 倍且零錯誤——文字層就是產生該 PDF 的原始字串,不是辨識結果。
台灣的網路申領電子謄本一律含文字層。

兩個原本的限制,本檔各釘一條:
  1. 這條路原本只給 contract,謄本用不到(而謄本的 OCR 錯誤率更高)
  2. extract_text_layer_pages 只給文字,structured_data 是 None
     ——少了補抽取,使用者會拿到完美的文字卻一個欄位都沒有
"""

import inspect

import pytest

from app.lib.pdf_text_layer import has_text_layer
from app.services import analyze_service as svc


class TestTextLayerAppliesToAllTypes:
    def test_branch_is_not_restricted_to_contract(self):
        """原本的條件含 document_type == "contract",謄本因此走不到"""
        src = inspect.getsource(svc)
        marker = 'if is_pdf and has_text_layer(file_contents):'
        assert marker in src, (
            "文字層分支被改動——它必須對所有文件類型生效,"
            "謄本的 OCR 錯誤率(14.5%)高於合約,受益更大"
        )
        assert 'document_type == "contract" and has_text_layer' not in src, (
            "文字層分支又被限制成只給合約"
        )


class TestFieldsAreStillExtracted:
    def test_helper_exists(self):
        assert hasattr(svc.AnalyzeService if hasattr(svc, "AnalyzeService") else svc,
                       "_extract_fields_for_text_layer") or \
               "_extract_fields_for_text_layer" in inspect.getsource(svc), (
            "走文字層時沒有補欄位抽取——使用者會拿到完美文字卻沒有任何欄位"
        )

    def test_branch_calls_the_helper(self):
        src = inspect.getsource(svc)
        i = src.index("if is_pdf and has_text_layer(file_contents):")
        window = src[i:i + 800]
        assert "_extract_fields_for_text_layer" in window, (
            "文字層分支未呼叫欄位抽取,會直接回傳 structured_data=None"
        )


class TestDetectionIsConservative:
    """誤判成本不對稱:把掃描件誤判為有文字層 → 拿到空字串;
    把電子檔誤判為掃描件 → 只是慢一點。所以判定要保守。"""

    def test_scanned_pdf_without_text_returns_false(self):
        """無法開啟或無文字時必須回 False(降級走 OCR),不得拋例外"""
        assert has_text_layer(b"not a pdf at all") is False

    def test_empty_input_returns_false(self):
        assert has_text_layer(b"") is False

    def test_threshold_rejects_trivial_text(self):
        """掃描件可能夾帶少量浮水印文字,門檻要擋掉"""
        from app.lib.pdf_text_layer import _MIN_TEXT_CHARS
        assert _MIN_TEXT_CHARS >= 20
