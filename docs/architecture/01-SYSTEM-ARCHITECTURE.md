# AI Document Intelligence Demo - 系統架構設計

## 1. 系統架構總覽

### 1.1 架構圖

```
┌─────────────────────────────────────────────────────────────┐
│                         使用者介面層                           │
│                    (Frontend - React/Next.js)               │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ 上傳頁面  │  │ 結果頁面  │  │ 問答頁面  │  │ 記錄頁面  │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ HTTPS/REST API
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                        API 閘道層                            │
│                   (Backend - Python/FastAPI)                │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │  檔案上傳     │  │  文件處理     │  │  問答服務     │    │
│  │  Upload API  │  │  Process API │  │  Chat API    │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐                       │
│  │  記錄建立     │  │  文件查詢     │                       │
│  │  Record API  │  │  Query API   │                       │
│  └──────────────┘  └──────────────┘                       │
└─────────────────────────────────────────────────────────────┘
              │               │               │
              │               │               │
              ▼               ▼               ▼
┌─────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│   檔案儲存層     │ │   AI 處理層       │ │   資料庫層        │
│                 │ │                  │ │                  │
│  ┌───────────┐  │ │  ┌────────────┐ │ │  ┌────────────┐  │
│  │    S3     │  │ │  │ OCR Service│ │ │  │ PostgreSQL │  │
│  │ Cloudflare│  │ │  │  (Textract)│ │ │  │            │  │
│  │    R2     │  │ │  └────────────┘ │ │  │ documents  │  │
│  └───────────┘  │ │                  │ │  │ ocr_results│  │
│                 │ │  ┌────────────┐ │ │  │ ai_results │  │
│  原始文件       │ │  │ AI Service │ │ │  │ records    │  │
│  OCR 結果       │ │  │  (OpenAI/  │ │ │  └────────────┘  │
│                 │ │  │   Claude)  │ │ │                  │
│                 │ │  └────────────┘ │ │                  │
│                 │ │                  │ │                  │
│                 │ │  • 文件分類      │ │                  │
│                 │ │  • 欄位抽取      │ │                  │
│                 │ │  • 摘要生成      │ │                  │
│                 │ │  • 風險檢測      │ │                  │
│                 │ │  • 問答對話      │ │                  │
└─────────────────┘ └──────────────────┘ └──────────────────┘
```

### 1.2 技術棧選擇

| 層次 | 技術選型 | 理由 |
|------|----------|------|
| **前端** | Next.js 14 (App Router) | React 框架，支援 SSR/SSG，開發效率高 |
| **UI 框架** | Tailwind CSS + shadcn/ui | 快速開發，元件豐富 |
| **後端** | Python + FastAPI | AI 生態最強，開發效率高 |
| **資料庫** | PostgreSQL | 關聯式資料庫，支援 JSON 欄位 |
| **ORM** | SQLAlchemy | Python 標準 ORM，功能強大 |
| **檔案儲存** | Cloudflare R2 / AWS S3 | 穩定可靠，成本合理 |
| **OCR** | AWS Textract / pytesseract | Textract 準確率高，pytesseract 免費 |
| **AI** | OpenAI GPT-4 / Claude 3.5 Sonnet | 抽取能力強，API 穩定 |
| **部署** | Vercel (前端) + Railway (後端) | 快速部署，免費額度足夠 Demo |

## 2. 核心流程設計

### 2.1 文件上傳處理流程

```
使用者上傳檔案
    ↓
前端驗證（格式、大小）
    ↓
POST /api/documents/upload
    ↓
後端接收檔案
    ↓
儲存至 S3/R2（原始檔案）
    ↓
寫入 documents 資料表（status: uploaded）
    ↓
返回 document_id 給前端
    ↓
前端自動觸發 POST /api/documents/{id}/process
    ↓
背景任務開始處理
```

### 2.2 AI 處理流程（核心）

```
接收 process 請求
    ↓
更新 status: processing
    ↓
┌─────────────────────────────────────┐
│ Step 1: OCR 處理                     │
│ - 從 S3 下載檔案                      │
│ - 調用 OCR 服務（Textract/Tesseract）│
│ - 取得文字內容                        │
│ - 儲存至 document_ocr_results         │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ Step 2: AI 文件分類                  │
│ - 將 OCR 文字送至 AI                 │
│ - Prompt: "判斷文件類型"              │
│ - 返回: doc_type + confidence        │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ Step 3: AI 欄位抽取                  │
│ - 根據 doc_type 選擇抽取模板          │
│ - Prompt: "抽取租約欄位" (示例)        │
│ - 返回: JSON 格式欄位                 │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ Step 4: AI 摘要生成 (P1)             │
│ - Prompt: "生成文件摘要"              │
│ - 返回: 3-5 行摘要文字                │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ Step 5: 風險檢測 (P2)                │
│ - 檢查缺失欄位                        │
│ - 檢查異常值                          │
│ - 返回: risks[] 陣列                  │
└─────────────────────────────────────┘
    ↓
儲存所有結果至 document_ai_results
    ↓
更新 status: completed
    ↓
前端輪詢或 WebSocket 通知結果
```

### 2.3 AI 問答流程

```
使用者提問
    ↓
POST /api/documents/{id}/chat
    ↓
後端載入文件上下文：
  - OCR 原文
  - 已抽取欄位
  - 文件摘要
    ↓
組合 Prompt：
  "基於以下文件內容回答問題：
   [文件內容]
   [已抽取欄位]

   問題：{user_question}"
    ↓
調用 AI API
    ↓
返回答案給前端
    ↓
（可選）儲存問答記錄至 document_chat_logs
```

### 2.4 一鍵建檔流程（P2）

```
使用者點擊「建立記錄」
    ↓
前端發送 POST /api/documents/{id}/create-record
    ↓
後端載入 extracted_data
    ↓
根據 doc_type 建立對應記錄：
  - lease → leases 表
  - repair_quote → repair_quotes 表
  - id_card → tenants 表
    ↓
寫入 created_records 表（關聯來源文件）
    ↓
返回 record_id
    ↓
前端跳轉至記錄詳情頁
```

## 3. 資料流設計

### 3.1 上傳階段

```
File (binary)
  → Frontend (FormData)
    → Backend API
      → S3/R2 (原始檔案 URL)
        → Database (documents 表)
```

### 3.2 處理階段

```
Document ID
  → S3/R2 (下載檔案)
    → OCR Service (文字)
      → Database (ocr_results 表)
        → AI Service (分類 + 抽取)
          → Database (ai_results 表)
```

### 3.3 查詢階段

```
Document ID
  → Database (JOIN documents + ai_results)
    → Frontend (顯示結果)
```

## 4. API 設計概覽

### 4.1 核心 API 端點

| 端點 | 方法 | 功能 | 優先級 |
|------|------|------|--------|
| `/api/documents/upload` | POST | 上傳檔案 | P0 |
| `/api/documents/:id/process` | POST | 觸發 AI 處理 | P0 |
| `/api/documents/:id` | GET | 取得文件與結果 | P0 |
| `/api/documents` | GET | 列出所有文件 | P0 |
| `/api/documents/:id/chat` | POST | AI 問答 | P1 |
| `/api/documents/:id/create-record` | POST | 建立系統記錄 | P2 |
| `/api/records/:id` | GET | 查詢建立的記錄 | P2 |

## 5. 資料庫設計概覽

### 5.1 核心資料表

```sql
documents (文件表)
  - id (UUID, PK)
  - file_name
  - file_url
  - mime_type
  - file_size
  - status (uploaded/processing/completed/failed)
  - created_at

document_ocr_results (OCR 結果表)
  - id (UUID, PK)
  - document_id (FK)
  - raw_text
  - page_count
  - ocr_confidence
  - created_at

document_ai_results (AI 處理結果表)
  - id (UUID, PK)
  - document_id (FK)
  - doc_type (lease_contract/repair_quote/id_card/unknown)
  - confidence
  - summary (TEXT)
  - risks (JSONB)
  - extracted_data (JSONB)
  - created_at

created_records (建立的記錄表 - P2)
  - id (UUID, PK)
  - source_document_id (FK)
  - record_type (lease/repair_quote/tenant)
  - payload (JSONB)
  - created_at

document_chat_logs (問答記錄表 - 可選)
  - id (UUID, PK)
  - document_id (FK)
  - question
  - answer
  - created_at
```

## 6. 安全性設計

### 6.1 檔案上傳安全

- ✅ 檔案格式白名單驗證
- ✅ 檔案大小限制（10MB）
- ✅ 檔案名稱過濾（防止路徑遍歷）
- ✅ 使用 UUID 作為儲存檔名
- ✅ Content-Type 驗證

### 6.2 API 安全（MVP 簡化版）

- ⚠️ MVP 階段不做完整身份驗證
- ✅ CORS 設定
- ✅ Rate Limiting（防止濫用）
- ✅ 檔案存取需經過後端 API（不直接暴露 S3 URL）

### 6.3 AI 安全

- ✅ Prompt Injection 防護（輸入過濾）
- ✅ 輸出驗證（確保返回 JSON 格式）
- ✅ AI API Key 存放於環境變數

## 7. 錯誤處理策略

### 7.1 上傳錯誤

| 錯誤情境 | HTTP 狀態碼 | 處理方式 |
|---------|------------|---------|
| 檔案格式不支援 | 400 | 返回錯誤訊息，前端顯示 |
| 檔案過大 | 413 | 返回錯誤訊息，前端顯示 |
| S3 上傳失敗 | 500 | 重試 3 次，失敗後返回錯誤 |
| 資料庫寫入失敗 | 500 | Rollback，刪除已上傳檔案 |

### 7.2 處理錯誤

| 錯誤情境 | 處理方式 |
|---------|---------|
| OCR 失敗 | 更新 status: failed，記錄錯誤訊息 |
| AI 分類失敗 | 標記為 unknown，保留 OCR 結果 |
| AI 抽取失敗 | 返回空欄位，顯示摘要 |
| 網路逾時 | 重試 2 次，最終標記失敗 |

### 7.3 問答錯誤

| 錯誤情境 | 處理方式 |
|---------|---------|
| 文件未處理完成 | 返回 425 Too Early |
| AI API 失敗 | 返回「目前無法回答，請稍後再試」 |
| 無法找到答案 | 返回「此文件中未找到相關資訊」 |

## 8. 效能優化策略

### 8.1 檔案處理優化

- ✅ 使用背景任務處理（避免阻塞 API）
- ✅ 前端輪詢狀態（每 2 秒查詢一次）
- ⚠️ 暫不實作 WebSocket（MVP 簡化）

### 8.2 AI 調用優化

- ✅ OCR 結果快取（避免重複處理）
- ✅ AI 結果快取（避免重複抽取）
- ✅ 批次處理（未來）

### 8.3 資料庫優化

- ✅ 在 document_id 建立索引
- ✅ 在 status 建立索引
- ✅ JSONB 欄位使用 GIN 索引（查詢優化）

## 9. 部署架構

### 9.1 MVP 部署方案

```
前端: Vercel
  - Next.js 自動部署
  - CDN 加速
  - 環境變數管理

後端: Railway / Render
  - Node.js 自動部署
  - PostgreSQL 資料庫
  - 環境變數管理

儲存: Cloudflare R2 / AWS S3
  - 檔案儲存
  - 公開 URL 存取

AI 服務: OpenAI / Anthropic API
  - API Key 管理
  - 用量監控
```

### 9.2 環境變數

```bash
# Backend
DATABASE_URL=postgresql://...
S3_BUCKET=ai-doc-demo
S3_REGION=us-east-1
S3_ACCESS_KEY=...
S3_SECRET_KEY=...
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
OCR_SERVICE=textract  # or tesseract
AWS_TEXTRACT_REGION=us-east-1

# Frontend
NEXT_PUBLIC_API_URL=https://api.example.com
```

## 10. 監控與除錯

### 10.1 日誌記錄

- ✅ API 請求日誌
- ✅ AI 調用日誌（request + response）
- ✅ 錯誤日誌（含 stack trace）
- ✅ 處理時間日誌

### 10.2 除錯工具

- ✅ 保留 OCR 原文（供除錯）
- ✅ 保留 AI 原始回應（供除錯）
- ✅ 顯示處理時間（供優化）

## 11. 擴展性考量

### 11.1 未來可擴展方向

1. **多用戶支援**：加入 user_id 欄位
2. **批次處理**：加入任務佇列（Bull/Redis）
3. **即時通知**：加入 WebSocket
4. **更多文件類型**：擴展 doc_type 與模板
5. **工作流整合**：與正式系統對接

### 11.2 架構演進路徑

```
MVP (單體應用)
  ↓
加入任務佇列
  ↓
微服務拆分（OCR 服務、AI 服務）
  ↓
加入快取層（Redis）
  ↓
分散式部署
```

## 12. 開發環境建置

### 12.1 本地開發需求

- Node.js 18+
- PostgreSQL 14+
- Docker (可選，用於 PostgreSQL)
- Git

### 12.2 專案結構

```
ai-doc-demo/
├── frontend/           # Next.js 專案
│   ├── src/
│   │   ├── app/        # App Router 頁面
│   │   ├── components/ # React 元件
│   │   └── lib/        # 工具函式
│   └── package.json
│
├── backend/            # Python FastAPI 專案
│   ├── app/
│   │   ├── main.py     # FastAPI 入口
│   │   ├── api/        # API 路由
│   │   ├── models/     # SQLAlchemy Models
│   │   ├── schemas/    # Pydantic Schemas
│   │   ├── services/   # 業務邏輯
│   │   └── lib/        # OCR、AI 整合
│   ├── alembic/        # 資料庫遷移
│   └── requirements.txt
│
└── docs/               # 文件
    ├── architecture/
    ├── api/
    ├── database/
    └── planning/
```

---

**文檔版本**: v1.0
**最後更新**: 2026-03-17
**負責人**: Architecture Team
