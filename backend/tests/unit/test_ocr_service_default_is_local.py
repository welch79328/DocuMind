"""`OCR_SERVICE` 預設值必須是不外送的本地引擎。

2026-08-24 盤查發現:`config.py` 的 `OCR_SERVICE` 原預設為 `"textract"`,
而 `lib/ocr_service.py` 的分派會據此呼叫 AWS Textract——boto3 client 是接好的,
AWS 金鑰在 `.env`,而 `.env` 不進版控。等於「文件不外送」這件事被擋在一個
換台機器就會消失的檔案上:任何沒設此鍵的部署,一開機就會把文件送去 AWS 並計費。

本檔的存在是為了讓「把預設改回雲端服務」立刻失敗。
要用 Textract 是可以的,但必須顯式設定,不能是預設。
"""

from app.config import Settings, settings

# 會把文件內容送出本機的分派值
_REMOTE_SERVICES = {"textract"}


class TestOcrServiceDefault:
    def test_default_is_not_a_remote_service(self):
        """類別預設不得是雲端服務;改回 textract 時此處失敗"""
        default = Settings.model_fields["OCR_SERVICE"].default
        assert default not in _REMOTE_SERVICES, (
            f"OCR_SERVICE 預設為 {default!r} —— 未設定此鍵的部署會把文件送出本機"
        )

    def test_default_is_a_value_the_dispatcher_accepts(self):
        """預設值必須是分派器認得的,否則未設定時會直接 ValueError"""
        from app.lib import ocr_service  # noqa: F401  確認模組可載入

        default = Settings.model_fields["OCR_SERVICE"].default
        assert default in {"textract", "paddleocr", "pytesseract"}

    def test_current_effective_value_is_local(self):
        """實際生效值(含 .env 覆寫)也不得是雲端服務"""
        assert settings.OCR_SERVICE not in _REMOTE_SERVICES
