# Tech - 技術棧與開發規範

## 技術架構

### 架構模式

**前後端分離 + 容器化部署**

```
前端 (Vue 3) ←→ Nginx ←→ 後端 (FastAPI) ←→ PostgreSQL
                                ↓
                        AI/OCR 服務 (OpenAI, Tesseract)
```

## 技術棧

### 後端 (Backend)

**核心框架**:
- **FastAPI 0.115+**: 現代化 Python Web 框架
- **Python 3.11+**: 語言版本
- **Uvicorn**: ASGI 伺服器

**資料庫**:
- **PostgreSQL 14+**: 主資料庫
- **SQLAlchemy 2.0**: ORM 框架
- **Alembic**: 資料庫遷移工具

**AI & OCR 服務**:
- **OpenAI GPT-4o / GPT-4o-mini**: LLM 服務
- **Anthropic Claude 3.5 Sonnet**: 備選 LLM
- **Tesseract OCR**: 免費 OCR 引擎（繁體中文 `chi_tra`）
- **PaddleOCR**: 針對中文優化的 OCR
- **AWS Textract**: 雲端 OCR 服務（選用）
- **PyMuPDF (fitz)**: PDF 處理

**儲存**:
- **本地檔案系統**: 開發與 Demo 使用
- **Cloudflare R2 / AWS S3**: 雲端儲存（選用）

### 前端 (Frontend)

**核心框架**:
- **Vue 3.4+**: 使用 Composition API
- **TypeScript 5.3+**: 類型安全
- **Vite 5.1+**: 建構工具

**UI & 樣式**:
- **Tailwind CSS 3.4**: CSS 框架
- **原生 HTML/CSS**: 無額外 UI 庫

**狀態管理 & 資料獲取**:
- **Pinia 2.1**: 狀態管理
- **@tanstack/vue-query 5.28**: 資料獲取與快取
- **axios 1.6**: HTTP 客戶端

**路由**:
- **Vue Router 4.2**: 前端路由

### 部署 & DevOps

**容器化**:
- **Docker**: 容器技術
- **Docker Compose**: 多容器編排
- **Nginx**: 反向代理與靜態資源伺服

**部署平台**:
- **Railway / Render**: 後端與資料庫（MVP）
- **Vercel**: 前端靜態資源（備選）
- **本地 Docker**: 開發與測試

## 架構設計原則

### 後端架構

**分層架構**:
```
API Layer (FastAPI Routes)
    ↓
Service Layer (Business Logic)
    ↓
Library Layer (AI, OCR, Storage)
    ↓
Data Layer (SQLAlchemy Models)
```

**關鍵設計模式**:
- **策略模式**: 文件類型處理器（`ocr_enhanced/` 套件）
- **工廠模式**: OCR 引擎管理器
- **依賴注入**: FastAPI Depends 機制

**目錄組織**:
```
backend/app/
├── main.py              # FastAPI 應用入口
├── config.py            # 應用配置（Pydantic Settings）
├── database.py          # 資料庫連線
├── api/v1/              # API 路由（版本化）
├── models/              # SQLAlchemy 資料模型
├── schemas/             # Pydantic 資料驗證 Schema
├── services/            # 業務邏輯層
├── lib/                 # 函式庫層
│   ├── ocr_enhanced/    # OCR 增強處理套件
│   ├── ocr_service.py   # 基礎 OCR 服務
│   ├── ai_service.py    # AI 服務（分類、提取、摘要）
│   └── storage_service.py # 檔案儲存服務
└── prompts/             # LLM Prompt 模板
```

### 前端架構

**元件組織**:
```
frontend/src/
├── main.ts              # 應用入口
├── App.vue              # 根元件
├── views/               # 頁面元件（路由對應）
├── components/          # 可重用元件（暫未使用）
├── services/            # API 服務層
├── router/              # 路由配置
├── types/               # TypeScript 類型定義
└── assets/              # 靜態資源
```

**命名規範**:
- **Views**: `PascalCase` + `View` 後綴 (例: `OcrTestView.vue`)
- **Components**: `PascalCase` (例: `DocumentCard.vue`)
- **Services**: `camelCase` + `.ts` (例: `api.ts`)

## OCR 增強套件設計

### 核心概念

`backend/app/lib/ocr_enhanced/` 提供**模組化、可擴展的 OCR 處理流程**：

```
預處理 → OCR 引擎 → 規則後處理 → LLM 後處理（可選）
```

### 模組職責

| 模組 | 檔案 | 職責 |
|------|------|------|
| 配置 | `config.py` | 預處理、引擎、後處理參數 |
| 預處理器 | `preprocessor.py` | 去浮水印、二值化、去噪 |
| 引擎管理器 | `engine_manager.py` | 多引擎融合、重試邏輯 |
| 規則後處理器 | `postprocessor.py` | 錯別字修正、格式校正 |
| LLM 後處理器 | `llm_postprocessor.py` | 視覺修正、智能校正 |
| 品質評估器 | `quality_assessor.py` | 信心度評估、重試決策 |

### 可擴展性設計

**新增文件類型處理器**:
1. 繼承 `DocumentProcessor` 基類（未來實作）
2. 實作 `preprocess()`, `postprocess()` 方法
3. 在配置中註冊新類型

**新增 OCR 引擎**:
1. 在 `engine_manager.py` 新增引擎函數
2. 更新 `config.py` 的引擎列表
3. 無需修改其他模組

## API 設計規範

### RESTful 原則

**端點命名**:
- 使用複數名詞: `/api/v1/documents`
- 版本化: `/api/v1/`
- 小寫與連字符: `/api/v1/ocr-test`（但允許例外 `/api/v1/ocr/test`）

**HTTP 方法語意**:
- `GET`: 查詢資源
- `POST`: 建立資源或執行操作
- `PUT`: 完整更新
- `PATCH`: 部分更新
- `DELETE`: 刪除資源

**回應格式**:
- 成功: 返回資料或狀態物件
- 錯誤: 使用 HTTP 狀態碼 + `{"detail": "錯誤訊息"}`

### 文檔化

- **OpenAPI/Swagger**: 自動生成於 `/api/docs`
- **ReDoc**: 替代文檔於 `/api/redoc`
- **語言**: 繁體中文（使用 FastAPI docstring）

## 編碼規範

### Python (Backend)

**風格**:
- **PEP 8**: 基本風格指南
- **型別提示**: 使用 Type Hints（`str`, `int`, `Optional[str]`）
- **Docstrings**: Google Style 或簡潔繁中註解

**命名**:
- **模組/檔案**: `snake_case.py`
- **類別**: `PascalCase`
- **函數/變數**: `snake_case`
- **常數**: `UPPER_SNAKE_CASE`

**範例**:
```python
async def process_document(
    document_id: UUID,
    document_type: str = "transcript"
) -> DocumentResponse:
    """處理文件並返回結果"""
    ...
```

### TypeScript (Frontend)

**風格**:
- **Composition API**: 優先使用 `<script setup>`
- **型別優先**: 避免 `any`，使用明確型別

**命名**:
- **檔案**: `camelCase.ts` 或 `PascalCase.vue`
- **介面**: `PascalCase` + `I` 前綴（選用）
- **變數**: `camelCase`
- **常數**: `UPPER_SNAKE_CASE`

**範例**:
```typescript
interface DocumentResponse {
  file_name: string
  total_pages: number
  pages: PageResult[]
}

const uploadDocument = async (file: File): Promise<DocumentResponse> => {
  ...
}
```

## 環境配置

### 環境變數

**配置來源**: `.env` 檔案（使用 `pydantic-settings`）

**關鍵配置**:
- `OCR_SERVICE`: 選擇 OCR 引擎（`tesseract` / `paddleocr` / `textract`）
- `STORAGE_TYPE`: 儲存方式（`local` / `s3`）
- `OPENAI_API_KEY`: LLM 服務金鑰（可選，未設定則跳過 LLM 修正）

### Docker 設定

**服務組成**:
- `backend`: Python FastAPI (Port 8000)
- `frontend`: Vue 3 + Nginx (Port 3000)
- `postgres`: PostgreSQL 14 (Port 5432)

**網路**:
- 前端透過 Nginx 代理請求到後端（`/api/*` → `http://backend:8000/api/*`）

## 測試策略

### 單元測試

**工具**: pytest + pytest-asyncio

**覆蓋範圍**:
- OCR 增強套件各模組
- 服務層業務邏輯
- 資料驗證 Schema

### 整合測試

**測試內容**:
- 端到端 OCR 流程（上傳 → 處理 → 結果）
- API 端點正確性
- 資料庫操作

### 測試資料

**位置**: `backend/data/` 與 `data/`
- `backend/data/`: 範例文件（謄本、合約）
- `data/contracts/`: 11 份真實合約樣本

## 效能考量

### 後端最佳化

- **非同步處理**: FastAPI async/await
- **資料庫連線池**: SQLAlchemy engine pool
- **OCR 處理**: 支援並行多頁處理

### 前端最佳化

- **Vite 建構**: 快速 HMR 與打包
- **Vue Query**: 自動資料快取與背景重新獲取
- **Lazy Loading**: 路由層級程式碼分割

## 安全性

### MVP 階段實作

- ✅ 檔案類型驗證（MIME type）
- ✅ 檔案大小限制（10MB）
- ✅ SQL Injection 防護（SQLAlchemy ORM）
- ✅ CORS 配置（限定前端來源）

### 未來加強

- 🔐 JWT 認證與授權
- 🔐 Rate Limiting（API 請求頻率限制）
- 🔐 檔案存取權限控管
- 🔐 敏感資料脫敏處理

## 成本最佳化策略

### OCR 成本

- **免費方案**: Tesseract / PaddleOCR（本地運算）
- **付費方案**: AWS Textract（~$1.5/1000 頁）
- **智能選擇**: 根據文件複雜度動態選擇引擎

### LLM 成本

- **智能策略**: OCR 信心度 < 85% 才使用 LLM
- **模型選擇**: 簡單任務用 GPT-4o-mini，複雜任務用 GPT-4o
- **視覺修正成本**: $0.02-0.03/頁

### 儲存成本

- **本地儲存**: 開發與 Demo 免費
- **R2/S3**: 免費額度內使用（< 10GB）

## 開發工具

### 推薦 IDE

- **VS Code**: 前後端通用
- **PyCharm**: Python 專用（選用）

### 必裝擴充套件

- Vue 相關: Vue - Official (Volar)
- Python 相關: Python, Pylance
- 通用: ESLint, Prettier, Docker

## 技術債務與改進方向

### 已知技術債

- 前端缺少可重用元件（目前直接寫在 View 中）
- 缺少完整的錯誤處理與日誌系統
- 測試覆蓋率不足（目標 80%）
- API 版本化不完整（僅有 v1）

### 改進方向

- 引入 Celery 進行背景任務處理（長文件）
- 加入監控系統（Prometheus + Grafana）
- 前端元件庫化（提取共用元件）
- E2E 測試（Playwright / Cypress）
