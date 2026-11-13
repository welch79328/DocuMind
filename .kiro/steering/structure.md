# Structure - 專案結構與組織規範

## 專案根目錄組織

```
DocuMind/
├── backend/              # Python FastAPI 後端
├── frontend/             # Vue 3 前端
├── data/                 # 測試資料（合約範例，gitignored）
├── docs/                 # 技術文件
├── nginx/                # 反向代理設定
├── .kiro/                # Kiro 規格驅動開發
├── docker-compose.yml    # Docker 編排
├── Makefile              # 開發工具腳本
├── .env                  # 環境變數（gitignored）
└── README.md             # 專案說明
```

### 根目錄檔案說明

- **`docker-compose.yml`**: 定義 backend、frontend、postgres、nginx 四個服務
- **`Makefile`**: 提供快捷命令（`make up`, `make logs`, `make migrate`）
- **`.env`**: Docker 部署的環境配置（在 `backend/` 下直接跑 uvicorn 時讀 `backend/.env`）
- **`data/`**: 存放測試資料，不納入版控
  - `data/contracts/`: 11 份合約 PDF 範例

## 後端結構 (backend/)

### 目錄樹

```
backend/
├── app/                     # 應用程式碼
│   ├── main.py             # FastAPI 應用入口，路由註冊
│   ├── config.py           # Pydantic Settings 配置
│   ├── database.py         # SQLAlchemy 連線與 Session
│   │
│   ├── api/v1/             # API 路由層
│   │   ├── analyze.py          # /analyze、/analyze/batch、/usage（主要串接端點）
│   │   ├── classify.py         # 文件類型建議
│   │   ├── review.py           # 人工複核佇列
│   │   ├── samples.py          # 校正樣本
│   │   ├── evaluation.py       # 評估與基準測試
│   │   ├── ocr_test.py         # OCR 測試頁後端
│   │   ├── documents.py        # 舊文件管理 API（不列在 API 文件）
│   │   └── chat.py             # 舊對話 API（不列在 API 文件）
│   │
│   ├── models/             # SQLAlchemy 資料模型（見「資料庫結構」）
│   ├── schemas/            # Pydantic Schemas（analyze、document、ai_result、chat）
│   ├── services/           # 業務邏輯層（analyze_service.py 為主流程）
│   │
│   ├── lib/                # 函式庫層
│   │   ├── multi_type_ocr/     # 各文件類型處理器（ProcessorFactory、OCR／影像理解／直讀）
│   │   ├── llm_service/        # LLM Provider（OpenAI、Anthropic、本地 Qwen、Bedrock）與依文件類型分流
│   │   ├── ocr_enhanced/       # OCR 處理套件（預處理、引擎、規則與 LLM 後處理）
│   │   ├── pdf_text_layer.py   # PDF 文字層讀取
│   │   ├── document_types.py   # 文件類型列舉
│   │   ├── ocr_service.py      # 舊 /documents 路徑的 OCR（OCR_SERVICE）
│   │   ├── ai_service.py       # AI 服務（分類、提取、摘要）
│   │   ├── storage_service.py  # 檔案儲存服務（本地 / S3）
│   │   └── s3_service.py       # S3 上傳下載（storage_service 的 S3 實作）
│   │
│   └── prompts/            # LLM Prompt 模板
│
├── alembic/versions/       # 資料庫遷移腳本
├── data/                   # 範例文件（謄本範例、transcript_samples/）
├── tests/                  # pytest（unit/、integration/）
├── tests_all/              # OCR 增強套件與基準測試
├── scripts/                # 工具腳本
├── requirements.txt        # Python 依賴
└── Dockerfile              # 後端 Docker 映像
```

### 分層職責

| 層級 | 目錄 | 職責 | 範例 |
|------|------|------|------|
| **API 層** | `api/v1/` | HTTP 請求處理、參數驗證、路由 | `analyze.py` 處理 `/api/v1/analyze` |
| **Service 層** | `services/` | 業務邏輯、流程編排、錯誤處理 | `analyze_service.py` 協調 OCR／直讀、欄位抽取與複核 |
| **Library 層** | `lib/` | 可重用函式庫、外部服務整合 | `multi_type_ocr/` 依文件類型處理 |
| **Data 層** | `models/` | 資料模型、資料庫操作 | `document.py` 定義 Document 資料表 |

### 命名規範

**檔案命名**:
- 模組: `snake_case.py`
- 測試: `test_*.py`

**類別命名**:
- Model: 單數名詞 `Document`, `DocumentOcrResult`
- Schema: 描述性 + Response/Request 後綴，例如 `DocumentResponse`
- Service: 名詞 + Service，例如 `DocumentService`

**函數命名**:
- 動詞開頭: `get_document()`, `process_document()`, `upload_file()`
- 非同步: 使用 `async def`

## 前端結構 (frontend/)

### 目錄樹

```
frontend/
├── src/
│   ├── main.ts              # Vue 應用入口
│   ├── App.vue              # 根元件（導航列）
│   │
│   ├── views/               # 頁面元件（路由對應）
│   │   ├── HomeView.vue         # 首頁
│   │   ├── UploadView.vue       # 文件上傳頁
│   │   ├── DocumentView.vue     # 文件結果頁
│   │   ├── OcrTestView.vue      # OCR 測試驗證頁
│   │   ├── ReviewQueueView.vue  # 複核佇列
│   │   └── ReviewCorrectView.vue # 複核校正
│   │
│   ├── components/          # 可重用元件（FieldConfirmation.vue）
│   ├── composables/         # 組合式函式（useFieldConfirmation.ts）
│   ├── services/            # API 服務層
│   │   └── api.ts               # HTTP 客戶端（axios，baseURL `/api`）
│   ├── router/              # Vue Router 配置
│   │   └── index.ts             # 路由定義
│   ├── types/               # TypeScript 類型定義（document、review、confirmation）
│   └── assets/              # 靜態資源（main.css）
│
├── index.html               # HTML 模板
├── package.json             # npm 依賴
├── vite.config.ts           # Vite 配置（含 vitest 設定）
├── tailwind.config.js       # Tailwind CSS 配置
├── tsconfig.json            # TypeScript 配置
├── nginx.conf               # 映像內 Nginx 設定
└── Dockerfile               # 前端 Docker 映像（Nginx）
```

### 路由組織

**路由模式**: HTML5 History Mode (`createWebHistory`)

**路由定義**:
```typescript
{
  path: '/',              // 首頁
  path: '/upload',        // 上傳頁
  path: '/document/:id',  // 文件結果頁
  path: '/ocr-test',      // OCR 測試頁
  path: '/review',        // 複核佇列
  path: '/review/:id'     // 複核校正
}
```

### 元件命名規範

- **Views**: `PascalCase` + `View` 後綴 (例: `OcrTestView.vue`)
- **Components**: `PascalCase` (例: `DocumentCard.vue`)
- **單檔元件結構**:
  ```vue
  <script setup lang="ts">
  // TypeScript 邏輯
  </script>

  <template>
  <!-- HTML 模板 -->
  </template>

  <style scoped>
  /* 元件樣式 */
  </style>
  ```

## OCR 增強套件結構 (backend/app/lib/ocr_enhanced/)

### 模組化設計

```
ocr_enhanced/
├── __init__.py              # 套件入口，匯出主要類別
├── config.py                # 配置類別（PreprocessConfig, EngineConfig, PostprocessConfig）
├── types.py                 # 型別定義（OCRResult, ProcessingStats）
│
├── preprocessor.py          # TranscriptPreprocessor - 圖像預處理
├── engine_manager.py        # EngineManager - OCR 引擎管理
├── postprocessor.py         # TranscriptPostprocessor - 後處理協調器
├── llm_postprocessor.py     # LLMPostprocessor - LLM LLM 文字校正
├── quality_assessor.py      # QualityAssessor - 品質評估
│
├── typo_dict.py             # 錯別字對照表（台灣地政用語）
├── image_utils.py           # 圖像工具函數
├── memory_guard.py          # 可用記憶體偵測（並行守衛）
├── dual_modal_corrector.py  # 雙模態校正（LLM_DUAL_MODAL_ENABLED）
├── document_classifier.py   # 文件類型建議
├── field_extractor.py       # 謄本欄位正則抽取
└── pp_structure.py          # PP-Structure 版面解析（預設關）
```

### 處理流程

```
原始圖片
    ↓
TranscriptPreprocessor (預處理)
    ├─ 去浮水印
    ├─ 二值化
    ├─ 去噪
    └─ 解析度提升
    ↓
EngineManager (OCR 引擎，清單取自 OCR_ENGINES)
    ├─ PaddleOCR（ONNX Runtime）
    └─ Tesseract
    ↓
TranscriptPostprocessor (後處理)
    ├─ 規則修正（錯別字、格式）
    └─ LLM 修正（可選，LLM 文字校正）
    ↓
最終結果
```

### 擴展性設計

**新增文件類型處理器**:
1. 在 `multi_type_ocr/` 繼承 `OcrDocumentProcessor`、`ImageUnderstandingProcessor` 或 `DirectReadProcessor`
2. 以 `ProcessorFactory.register_processor()` 註冊

**新增 OCR 引擎**:
1. 在 `engine_manager.py` 新增引擎函數
   ```python
   async def _extract_with_new_engine(self, image): ...
   ```
2. 加入 `engines` 列表

## 資料庫結構

### 資料表組織

模型在 `backend/app/models/`，遷移在 `backend/alembic/versions/`。

```
documents             # 文件基本資訊
    ├── id (PK)
    ├── file_name, file_url, mime_type, file_size
    ├── status, error_message
    └── created_at, updated_at

document_ocr_results  # OCR 辨識結果
    ├── id (PK)
    ├── document_id (FK → documents)
    ├── raw_text, page_count, ocr_confidence
    ├── ocr_service, processing_time
    └── created_at

document_ai_results   # AI 處理結果
    ├── id (PK)
    ├── document_id (FK → documents)
    ├── doc_type, confidence
    ├── summary, risks (JSONB), extracted_data (JSONB)
    ├── ai_model, processing_time
    └── created_at

document_chat_logs    # 對話記錄
    ├── id (PK)
    ├── document_id (FK → documents)
    ├── question, answer, ai_model, response_time
    └── created_at

created_records       # 建立的系統記錄
    ├── id (PK)
    ├── source_document_id (FK → documents)
    ├── record_type, payload (JSONB)
    └── created_at

api_usage_logs        # API 用量記錄（ApiUsageLog）
review_queue_items    # 人工複核佇列（ReviewQueueItem）
correction_samples    # 校正樣本（CorrectionSample）
evaluation_records    # 評估紀錄（EvaluationRecord）
```

### 關聯關係

- `Document` 1:N `DocumentOcrResult`
- `Document` 1:N `DocumentAiResult`
- `Document` 1:N `DocumentChatLog`
- `Document` 1:N `CreatedRecord`

## 文檔結構 (docs/)

`docs/` 的目錄與每份文件的用途見 `docs/STRUCTURE.md`，導航見 `docs/README.md`。

## Kiro 規格結構 (.kiro/)

### 目錄組織

```
.kiro/
├── steering/                # 專案級指導文檔
│   ├── product.md              # 產品定位與原則
│   ├── tech.md                 # 技術棧與開發規範
│   └── structure.md            # 專案結構（本文件）
│
├── specs/                   # 功能級規格文檔，每個功能一個目錄
│   └── <feature>/              # spec.json、requirements.md、design.md、tasks.md 等
│
└── settings/                # Kiro 系統設定
    ├── rules/                  # 規範與原則（ears-format.md 等）
    └── templates/specs/        # 規格模板
```

### Specs 與 Steering 的關係

- **Steering**: 專案整體的記憶與原則，所有功能共用
- **Specs**: 單一功能的完整規格，獨立演進

## 導入與命名空間

### 後端導入慣例

**絕對導入** (推薦):
```python
from app.models.document import Document
from app.lib.ocr_enhanced.preprocessor import TranscriptPreprocessor
from app.config import settings
```

**相對導入** (模組內):
```python
# 在 app/lib/ocr_enhanced/postprocessor.py 中
from .llm_postprocessor import LLMPostprocessor
from .types import OCRResult
```

### 前端導入慣例

**使用 `@` 別名** (對應 `src/`):
```typescript
import { api } from '@/services/api'
import type { Document } from '@/types/document'
```

## 配置管理模式

### 後端配置

**集中式配置** (`app/config.py`):
- 使用 `pydantic-settings` 從 `.env` 讀取
- 所有配置透過 `settings` 單例存取
- 範例:
  ```python
  from app.config import settings

  if "paddleocr" in settings.OCR_ENGINES:
      ...
  ```

### 前端配置

**環境變數** (透過 Vite):
- `services/api.ts` 的 axios baseURL 為 `import.meta.env.VITE_API_URL || '/api'`，請求路徑寫 `/v1/...`
- `OcrTestView.vue` 直接以 `fetch('/api/v1/ocr/test?...')` 呼叫
- 本機開發由 Vite 把 `/api` 轉給 `http://localhost:8000`（`vite.config.ts`）

## 測試組織

### 後端測試

```
backend/
├── tests/                   # pytest（納入版控）
│   ├── unit/                    # 單元測試（test_analyze_*.py 等）
│   ├── integration/             # 整合測試
│   └── conftest.py
│
└── tests_all/               # OCR 增強套件與基準測試（納入版控）
```

**執行**:
```bash
cd backend
pytest tests/
```

### 前端測試

vitest（`vite.config.ts` 的 `test` 區塊，jsdom），測試檔為 `src/**/*.spec.ts`：

```bash
cd frontend
npm test
```

## 版本控制與 .gitignore

### 排除項目

**開發產物**:
- `__pycache__/`, `*.pyc`, `venv/`, `node_modules/`
- `frontend/dist/`, `.vite/`

**環境配置**:
- `.env`, `.env.local`

**測試資料**:
- `/data/` (根目錄，合約範例)
- `/tests/` (根目錄)

**保留項目**:
- `backend/data/` (範例謄本，文檔引用)
- `.kiro/` (專案規格)

## 部署結構

### Docker Compose 服務

```yaml
services:
  postgres:
    ports: 5432 (內部), 5433 (外部映射)
    volume: postgres_data

  backend:
    ports: 8000 (內部，不對外)
    depends_on: postgres

  frontend:
    Vue 建置後的靜態檔，由映像內 Nginx 提供（內部 80，不對外）

  nginx:
    ports: 8085 (外部) → 80
    /api/* → backend:8000，其餘 → frontend
```

### 檔案對應

- **後端代碼**: `./backend` → `/app` (容器內，`uvicorn --reload`)
- **前端代碼**: 建置進映像，不掛載
- **上傳檔案**: 本地 `./uploads` → `/app/uploads` 或雲端 S3/R2
- **標註資料**: `./data` → `/app/data`（唯讀）

## 總結：檔案放置原則

| 類型 | 位置 | 範例 |
|------|------|------|
| API 路由 | `backend/app/api/v1/` | `analyze.py` |
| 業務邏輯 | `backend/app/services/` | `analyze_service.py` |
| 可重用函式庫 | `backend/app/lib/` | `multi_type_ocr/`, `ocr_enhanced/`, `storage_service.py` |
| 資料模型 | `backend/app/models/` | `document.py` |
| LLM Prompt | `backend/app/prompts/` | `extraction.py` |
| 前端頁面 | `frontend/src/views/` | `OcrTestView.vue` |
| 測試資料 | `backend/data/`, `data/` | `建物謄本.jpg`, `contracts/` |
| 技術文件 | `docs/` | `api/INTEGRATION.md` |
| 功能規格 | `.kiro/specs/<feature>/` | `requirements.md`, `design.md` |
