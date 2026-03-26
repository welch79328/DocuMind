"""
Application configuration
"""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application settings"""

    # App Settings
    APP_NAME: str = "AI Document Intelligence"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/ai_doc_demo"

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:3001"]

    # AWS / S3
    S3_BUCKET: str = ""
    S3_REGION: str = "us-east-1"
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_ENDPOINT_URL: str | None = None  # For Cloudflare R2

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_MODEL_MINI: str = "gpt-4o-mini"

    # Anthropic Claude (Optional)
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-3-5-sonnet-20241022"

    # AWS Textract
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"

    # OCR Service Selection
    OCR_SERVICE: str = "textract"  # or "pytesseract"

    # OCR Enhancement Settings
    OCR_ENHANCED_MODE: bool = False                         # 是否啟用增強模式
    OCR_MULTI_ENGINE: bool = False                          # 是否啟用多引擎融合
    OCR_ENGINES: List[str] = ["paddleocr", "tesseract"]     # 使用的引擎列表
    OCR_QUALITY_THRESHOLD: float = 60.0                     # 品質閾值(0-100)
    OCR_MAX_RETRIES: int = 3                                # 最大重試次數
    OCR_WATERMARK_REMOVAL: bool = True                      # 是否移除浮水印
    OCR_POSTPROCESSING: bool = True                         # 是否啟用後處理
    OCR_PDF_DPI: int = 300                                  # PDF 轉圖像 DPI
    OCR_BINARIZATION_METHOD: str = "gaussian"               # 二值化方法 (gaussian/mean/sauvola)
    OCR_FUSION_METHOD: str = "best"                         # 融合方法 (best/weighted/vote)
    OCR_PADDLEOCR_LANG: str = "chinese_cht"                 # PaddleOCR 語言
    OCR_TESSERACT_LANG: str = "chi_tra"                     # Tesseract 語言

    # File Upload
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_MIME_TYPES: List[str] = [
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/jpg"
    ]

    # Server
    PORT: int = 8000

    # Storage Configuration
    STORAGE_TYPE: str = "local"  # "local" or "s3"
    LOCAL_STORAGE_PATH: str = "/app/uploads"  # Path for local storage

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
