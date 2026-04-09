# Structure - 專案結構與組織規範

## 專案根目錄組織

```
DocuMind/
├── backend/              # Python FastAPI 後端
├── frontend/             # Vue 3 前端
├── data/                 # 測試資料（合約範例，gitignored）
├── docs/                 # 技術文件
├── .kiro/                # Kiro 規格驅動開發
├── docker-compose.yml    # Docker 編排
├── Makefile              # 開發工具腳本
├── .env                  # 環境變數（gitignored）
└── README.md             # 專案說明
```

### 根目錄檔案說明

- **`docker-compose.yml`**: 定義 backend, frontend, postgres 三個服務
- **`Makefile`**: 提供快捷命令（`make up`, `make logs`, `make migrate`）
- **`.env`**: 統一環境配置（Docker 與本地共用）
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
│   ├── api/                # API 路由層（按版本組織）
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── documents.py    # 文件管理 API
│   │       ├── chat.py         # 智能對話 API
│   │       └── ocr_test.py     # OCR 測試 API
│   │
│   ├── models/             # SQLAlchemy 資料模型（對應資料表）
│   │   ├── document.py         # Document 表
│   │   ├── ocr_result.py       # DocumentOcrResult 表
│   │   ├── ai_result.py        # DocumentAiResult 表
│   │   ├── chat_log.py         # ChatLog 表
│   │   └── created_record.py   # CreatedRecord 表
│   │
│   ├── schemas/            # Pydantic Schemas（資料驗證與序列化）
│   │   ├── document.py         # DocumentResponse, DocumentListResponse
│   │   ├── ai_result.py        # AIResultResponse
│   │   └── chat.py             # ChatRequest, ChatResponse
│   │
│   ├── services/           # 業務邏輯層（Service Layer）
│   │   ├── document_service.py # 文件處理業務邏輯
│   │   └── chat_service.py     # 對話業務邏輯
│   │
│   ├── lib/                # 函式庫層（Library Layer）
│   │   ├── ocr_enhanced/       # OCR 增強處理套件（模組化）
│   │   │   ├── __init__.py
│   │   │   ├── config.py           # 預處理、引擎、後處理配置
│   │   │   ├── types.py            # 共用型別定義
│   │   │   ├── preprocessor.py     # 圖像預處理（去浮水印、二值化）
│   │   │   ├── engine_manager.py   # OCR 引擎管理（多引擎融合）
│   │   │   ├── postprocessor.py    # 規則後處理（錯別字、格式）
│   │   │   ├── llm_postprocessor.py # LLM 後處理（LLM 文字校正）
│   │   │   ├── quality_assessor.py # 品質評估與重試決策
│   │   │   ├── typo_dict.py        # 錯別字對照表
│   │   │   └── image_utils.py      # 圖像工具函數
│   │   │
│   │   ├── ocr_service.py      # 基礎 OCR 服務（Tesseract, PaddleOCR, Textract）
│   │   ├── ai_service.py       # AI 服務（分類、提取、摘要）
│   │   ├── storage_service.py  # 檔案儲存服務（本地 / S3）
│   │   └── s3_service.py       # S3 整合（已棄用，改用 storage_service）
│   │
│   └── prompts/            # LLM Prompt 模板
│       ├── classification.py   # 文件分類 Prompt
│       ├── extraction.py       # 欄位提取 Prompt
│       ├── summary.py          # 摘要生成 Prompt
│       └── qa.py               # 問答 Prompt
│
├── alembic/                # 資料庫遷移
│   └── versions/           # 遷移腳本
│
├── data/                   # 測試資料（建物謄本範例）
│   ├── 建物謄本.jpg
│   └── 建物土地謄本-杭州南路一段.pdf
│
├── tests/                  # 單元測試（gitignored）
├── tests_all/              # 整合測試（gitignored）
├── scripts/                # 工具腳本（gitignored）
├── requirements.txt        # Python 依賴
└── Dockerfile              # 後端 Docker 映像
```

### 分層職責

| 層級 | 目錄 | 職責 | 範例 |
|------|------|------|------|
| **API 層** | `api/v1/` | HTTP 請求處理、參數驗證、路由 | `ocr_test.py` 處理 `/api/v1/ocr/test` |
| **Service 層** | `services/` | 業務邏輯、流程編排、錯誤處理 | `document_service.py` 協調 OCR + AI 流程 |
| **Library 層** | `lib/` | 可重用函式庫、外部服務整合 | `ocr_enhanced/` 提供 OCR 處理 pipeline |
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
│   ├── App.vue              # 根元件
│   │
│   ├── views/               # 頁面元件（路由對應）
│   │   ├── HomeView.vue         # 首頁
│   │   ├── UploadView.vue       # 文件上傳頁
│   │   ├── DocumentView.vue     # 文件結果頁
│   │   └── OcrTestView.vue      # OCR 測試驗證頁
│   │
│   ├── components/          # 可重用元件（目前未使用）
│   │
│   ├── services/            # API 服務層
│   │   └── api.ts               # HTTP 客戶端（axios）
│   │
│   ├── router/              # Vue Router 配置
│   │   └── index.ts             # 路由定義
│   │
│   ├── types/               # TypeScript 類型定義
│   │   └── document.ts          # Document 相關型別
│   │
│   └── assets/              # 靜態資源
│       └── (CSS, images)
│
├── public/                  # 公開靜態資源
├── index.html               # HTML 模板
├── package.json             # npm 依賴
├── vite.config.ts           # Vite 配置
├── tailwind.config.js       # Tailwind CSS 配置
├── tsconfig.json            # TypeScript 配置
└── Dockerfile               # 前端 Docker 映像（Nginx）
```

### 路由組織

**路由模式**: Hash Mode (`createWebHashHistory`)

**路由定義**:
```typescript
{
  path: '/',              // 首頁
  path: '/upload',        // 上傳頁
  path: '/document/:id',  // 文件結果頁
  path: '/ocr-test'       // OCR 測試頁
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
└── image_utils.py           # 圖像工具函數
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
EngineManager (OCR 引擎)
    ├─ Tesseract
    ├─ PaddleOCR
    └─ 多引擎融合
    ↓
TranscriptPostprocessor (後處理)
    ├─ 規則修正（錯別字、格式）
    └─ LLM 修正（可選，LLM 文字校正）
    ↓
最終結果
```

### 擴展性設計

**新增文件類型處理器**（未來）:
1. 在 `ocr_enhanced/processors/` 新增處理器
   ```python
   class ContractProcessor:
       def preprocess(self, image): ...
       def postprocess(self, text): ...
   ```
2. 註冊到配置或工廠

**新增 OCR 引擎**:
1. 在 `engine_manager.py` 新增引擎函數
   ```python
   async def _extract_with_new_engine(self, image): ...
   ```
2. 加入 `engines` 列表

## 資料庫結構

### 資料表組織

```
documents           # 文件基本資訊
    ├── id (PK)
    ├── file_name, file_url, mime_type, file_size
    ├── status, error_message
    └── created_at, updated_at

document_ocr_results  # OCR 辨識結果
    ├── id (PK)
    ├── document_id (FK → documents)
    ├── raw_text, page_count
    ├── ocr_service, processing_time
    └── created_at

document_ai_results   # AI 處理結果
    ├── id (PK)
    ├── document_id (FK → documents)
    ├── doc_type, confidence
    ├── summary, extracted_data (JSON)
    ├── ai_model, processing_time
    └── created_at

chat_logs            # 對話記錄
    ├── id (PK)
    ├── document_id (FK → documents)
    ├── question, answer
    └── created_at

created_records      # 建立的系統記錄
    ├── id (PK)
    ├── document_id (FK → documents)
    ├── record_type, record_data (JSON)
    └── created_at
```

### 關聯關係

- `Document` 1:1 `DocumentOcrResult`
- `Document` 1:1 `DocumentAiResult`
- `Document` 1:N `ChatLog`
- `Document` 1:N `CreatedRecord`

## 文檔結構 (docs/)

### 目錄組織

```
docs/
├── README.md                # 文件導航
├── planning/                # 規劃文件
│   ├── 01-MVP-SCOPE.md
│   ├── 02-IMPLEMENTATION-PLAN.md
│   └── 03-TECH-STACK.md
├── architecture/            # 架構設計
│   └── 01-SYSTEM-ARCHITECTURE.md
├── database/                # 資料庫設計
│   └── 01-DATABASE-DESIGN.md
├── api/                     # API 規格
│   └── 01-API-SPECIFICATION.md
├── frontend/                # 前端設計
│   └── 01-FRONTEND-DESIGN.md
└── ai/                      # AI 設計
    └── 01-AI-PROMPT-DESIGN.md
```

## Kiro 規格結構 (.kiro/)

### 目錄組織

```
.kiro/
├── steering/                # 專案級指導文檔
│   ├── product.md              # 產品定位與原則
│   ├── tech.md                 # 技術棧與開發規範
│   └── structure.md            # 專案結構（本文件）
│
├── specs/                   # 功能級規格文檔
│   ├── document-ocr-enhancement/     # 謄本 OCR 增強
│   │   ├── spec.json
│   │   ├── requirements.md
│   │   ├── design.md
│   │   └── tasks.md
│   └── multi-document-type-ocr/      # 多文件類型 OCR
│       ├── spec.json
│       └── requirements.md
│
└── settings/                # Kiro 系統設定
    ├── rules/                  # 規範與原則
    │   └── ears-format.md         # EARS 需求格式
    └── templates/              # 模板檔案
        └── specs/
            ├── init.json
            ├── requirements.md
            └── ...
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

  if settings.OCR_SERVICE == "tesseract":
      ...
  ```

### 前端配置

**環境變數** (透過 Vite):
- `import.meta.env.VITE_API_URL`（未來可能使用）
- 目前使用硬編碼 API URL（`/api/v1/`）

## 測試組織

### 後端測試

```
backend/
├── tests/                   # 單元測試（gitignored）
│   ├── test_preprocessor.py
│   ├── test_engine_manager.py
│   └── ...
│
└── tests_all/               # 整合測試（gitignored）
    ├── test_ocr_pipeline.py
    └── test_api_endpoints.py
```

**執行**:
```bash
pytest tests/           # 單元測試
pytest tests_all/       # 整合測試
```

### 前端測試

目前未實作測試框架（未來可使用 Vitest + Testing Library）

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
- `backend/data/temp_*.png`

**保留項目**:
- `backend/data/` (範例謄本，文檔引用)
- `.kiro/` (專案規格)

## 部署結構

### Docker Compose 服務

```yaml
services:
  backend:
    ports: 8000 (內部)
    depends_on: postgres

  frontend:
    ports: 3000 (外部)
    nginx 代理 /api/* → backend:8000

  postgres:
    ports: 5432 (內部), 5433 (外部映射)
    volume: pgdata
```

### 檔案對應

- **後端代碼**: `./backend` → `/app` (容器內)
- **前端代碼**: `./frontend` → `/app` (容器內)
- **上傳檔案**: 本地 `./uploads` 或雲端 S3/R2

## 總結：檔案放置原則

| 類型 | 位置 | 範例 |
|------|------|------|
| API 路由 | `backend/app/api/v1/` | `ocr_test.py` |
| 業務邏輯 | `backend/app/services/` | `document_service.py` |
| 可重用函式庫 | `backend/app/lib/` | `ocr_enhanced/`, `storage_service.py` |
| 資料模型 | `backend/app/models/` | `document.py` |
| LLM Prompt | `backend/app/prompts/` | `extraction.py` |
| 前端頁面 | `frontend/src/views/` | `OcrTestView.vue` |
| 測試資料 | `backend/data/`, `data/` | `建物謄本.jpg`, `contracts/` |
| 技術文件 | `docs/` | `01-MVP-SCOPE.md` |
| 功能規格 | `.kiro/specs/<feature>/` | `requirements.md`, `design.md` |
