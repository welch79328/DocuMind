"""
Application configuration
"""

from pydantic_settings import BaseSettings
from typing import List, Optional


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
    S3_ENDPOINT_URL: Optional[str] = None  # For Cloudflare R2
    S3_CDN_URL: Optional[str] = None  # CloudFront CDN URL

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_MODEL_MINI: str = "gpt-4o-mini"

    # Anthropic Claude (Optional)
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-3-5-sonnet-20241022"

    # LLM Provider(可插拔:本地優先、雲端可選)
    LLM_PROVIDER: str = "openai"          # openai / anthropic / local_qwen
    LLM_CLOUD_ENABLED: bool = True        # 隱私硬需求時設 false,禁止載入雲端 Provider
    LOCAL_QWEN_ENDPOINT: str = ""         # 本地 / EC2 vLLM 端點(LLM_PROVIDER=local_qwen 時必填)

    # 雙模態 LLM 校正(ocr-vlm-consensus 需求 2);預設關閉,校正行為與現行一致
    LLM_DUAL_MODAL_ENABLED: bool = False  # 啟用後校正才同時送出頁面影像
    LLM_FIELD_CONFIDENCE_ENABLED: bool = False  # 啟用後校正才附帶欄位級信心度

    # AWS Textract
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"

    # OCR Service Selection —— 舊路徑 `lib/ocr_service.py` 的分派鍵。
    # 這條路徑由 `services/document_service.py` 使用(/api/v1/documents),
    # 與 `lib/ocr_enhanced` 的 OCR_ENGINES 是**兩條各自獨立的 OCR 路徑**,別搞混。
    #
    # ⚠️ 預設值 2026-08-24 由 "textract" 改為 "pytesseract"。
    # 原預設會讓**任何沒設此鍵的部署一開機就呼叫 AWS Textract**——計費,
    # 且文件內容送出到 AWS。boto3 client 是接好的(`ocr_service.py` 的
    # `extract_text_with_textract`),AWS 金鑰也在 `.env` 裡,而 `.env` 不進版控,
    # 等於把「不外送」這件事擋在一個換台機器就會消失的檔案上。
    # 改為本地引擎後,未設定時的行為是安全的;要用 Textract 請顯式設定。
    # (本機與線上的 .env 本來就都設 pytesseract,故實際行為不變。)
    OCR_SERVICE: str = "pytesseract"  # textract / paddleocr / pytesseract

    # OCR Enhancement Settings
    OCR_ENHANCED_MODE: bool = False                         # 是否啟用增強模式
    # 保留供既有 .env 相容;**已不再接線至任何執行路徑**。
    # 引擎數量實際由 OCR_ENGINES 決定,此旗標名為「多引擎融合」卻只控制併發,
    # 2026-08-24 拆分為 OCR_PARALLEL_ENGINES 後不再被讀取。
    OCR_MULTI_ENGINE: bool = False                          # (已停用,見上)

    # 是否讓多個 OCR 引擎並行執行(asyncio.gather + to_thread)。
    # 2026-08-24 於線上 2 vCPU / 3.7GB 實測(同一份謄本):
    #   循序  36.7s
    #   並行  31.7s   ← 省 13.6%,辨識結果不變
    # 理論值應省 47%(max(19.6, 17.1) ≈ 19.6s),差距來自 2 vCPU 的核心爭搶;
    # 四核以上機器增益會明顯更大。
    # ⚠️ 代價:並行時兩引擎同時常駐,峰值記憶體為兩者之和而非最大值。
    #    該機 RAM 僅 3.7GB(建議值的一半),換更小機器前需重新評估。
    OCR_PARALLEL_ENGINES: bool = True                       # 多引擎並行執行

    # 並行的記憶體門檻:可用記憶體低於此值時,即使 OCR_PARALLEL_ENGINES=True
    # 也自動退回循序執行(慢一點,但不會把整台吃垮)。
    # 2026-08-24 實測:300 DPI 合約頁 + 去噪 + 雙引擎並行,在 3.7GB 的機器上
    # 觸發 OOM(docker inspect .State.OOMKilled = true),load average 衝到 51.35。
    # 並行的代價是峰值記憶體從「兩引擎取大」變成「兩引擎相加」,機器小就撐不住。
    # 設為 0 可停用此保護(不建議)。
    OCR_PARALLEL_MIN_AVAILABLE_MB: int = 1024               # 並行所需的最低可用記憶體

    # 單頁渲染的像素上限。PDF 原以固定 300 DPI 渲染,A4 即 2480×3508 ≈ 8.7M 像素,
    # 是 OOM 的主要來源之一。超過此上限時自動降低 DPI(等比例縮),
    # 不改變頁數、不丟棄內容。設為 0 可停用此上限(不建議)。
    #
    # ⚠️ 1.0M 是實測值。2026-08-24 於線上容器實測
    # (backend 上限 2048MB、應用程式本身佔 489MB → 可用約 1559MB),
    # 單頁 / 單引擎 / 循序,**在文字密集的內文頁上**:
    #
    #   像素上限   解析度    峰值 RSS    行數   信心度    結果
    #   3.0M      176 DPI   >1626 MB    —      —       ✗ 中止
    #   2.0M      144 DPI   >1503 MB    —      —       ✗ 中止
    #   1.5M      125 DPI   >1454 MB    —      —       ✗ 中止
    #   1.25M     114 DPI    1453 MB    33    0.9837   ✓ 但餘裕僅約 106MB
    #   1.0M      102 DPI    1323 MB    33    0.9826   ✓ 餘裕約 236MB
    #
    # 另一份合約交叉驗證(1.0M):36 行 / 0.9899(1359MB)、35 行 / 0.9826(1328MB)。
    #
    # 兩個關鍵事實,調整此值前務必先讀:
    #
    # 1. **記憶體主要由文字密度決定,不是像素數。** 光載入 PaddleOCR 引擎就佔
    #    701 MB(尚未辨識);辨識階段再疊上去的量隨文字區塊數成長。
    #    先前設 4M 再改 2M,都是拿只有 5 行的封面頁(1354MB)校準的——校準樣本
    #    選錯,把密集頁的需求低估了。**校準一定要用內文頁。**
    #
    # 2. **提高解析度換不到品質。** 102 DPI 與 114 DPI 在同一頁上行數相同(33)、
    #    信心度 0.9826 vs 0.9837,差異在雜訊範圍內;而 0.98 已高於謄本基準的 0.927。
    #    這條管線的瓶頸不在解析度。
    OCR_MAX_RENDER_PIXELS: int = 1_000_000                  # A4 約 102 DPI
    OCR_RENDER_DPI: int = 300                               # 目標 DPI,受上方像素上限約束
    OCR_ENGINES: List[str] = ["paddleocr", "tesseract"]     # 使用的引擎列表
    OCR_QUALITY_THRESHOLD: float = 0.8                      # 信心度門檻(0-1),低於此值進入人工複核
    OCR_MAX_RETRIES: int = 3                                # 最大重試次數
    OCR_ENABLE_PP_STRUCTURE: bool = False                  # 謄本 PP-Structure 版面解析增強(預設關,PoC 後評估)

    # Fine-tune 決策門檻(Phase 3;僅決策,不執行訓練)
    FINETUNE_MIN_SAMPLES: int = 200                        # 訓練池樣本量門檻
    FINETUNE_TARGET_ACCURACY: float = 0.9                  # 欄位準確率目標(低於此且停滯才評估微調)

    # 基準測試(ocr-vlm-consensus 需求 1)
    BASELINE_MIN_SAMPLES: int = 30                         # 低於此樣本數拒絕標記為正式基準線
    OCR_WATERMARK_REMOVAL: bool = True                      # 是否移除浮水印
    OCR_POSTPROCESSING: bool = True                         # 是否啟用後處理
    OCR_PDF_DPI: int = 300                                  # PDF 轉圖像 DPI
    OCR_BINARIZATION_METHOD: str = "gaussian"               # 二值化方法 (gaussian/mean/sauvola)
    OCR_FUSION_METHOD: str = "best"                         # 融合方法 (best/weighted/vote/smart/cross_check)

    # 欄位層共識信心度(ocr-vlm-consensus 需求 4);預設關閉,行為與現行一致
    OCR_CONSENSUS_ENABLED: bool = False                     # 啟用後才走多引擎候選比對
    OCR_CONSENSUS_DISAGREE_PENALTY: float = 0.3             # 不一致時的信心度上限(0-1)
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
