# DocuMind - AI Document Intelligence

> 🧠 讓文件會思考 - 基於 AI 的智能文件處理系統，自動辨識、分類、抽取租賃文件資訊

[![GitHub](https://img.shields.io/badge/GitHub-DocuMind-blue?logo=github)](https://github.com/welch79328/DocuMind)
[![Python](https://img.shields.io/badge/Python-3.11+-green?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-teal?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Vue](https://img.shields.io/badge/Vue-3.4+-brightgreen?logo=vue.js)](https://vuejs.org/)

## 📖 專案簡介

本專案是一個 **MVP Demo**，旨在展示 AI 如何協助處理租賃/包租代管場景中的非結構化文件（PDF、圖片），將其轉換為可用的結構化資料。

### 核心功能

- 📤 **文件上傳** - 支援 PDF/JPG/PNG 格式
- 🔍 **OCR 辨識** - 自動提取文件文字
- 🤖 **AI 分類** - 自動識別文件類型（租約/報價單/身分證）
- 📋 **欄位抽取** - AI 自動抽取關鍵資訊
- 📝 **AI 摘要** - 生成文件摘要
- 💬 **AI 問答** - 針對文件內容進行對話
- ⚠️ **風險檢測** - 識別缺失欄位與異常值（P2）
- 📁 **一鍵建檔** - 建立系統記錄（P2）

---

## 🎯 專案目標

### 展示價值

- 驗證 AI 在租賃文件場景的應用潛力
- 展示「文件上傳 → AI 理解 → 自動建檔」的完整流程
- 提供可操作的 Demo 產品

### 非目標（MVP 階段）

- ❌ 批量文件處理
- ❌ 複雜權限管理
- ❌ 完整商業版功能
- ❌ 高可用性生產環境

---

## 📚 技術文件

**完整技術文件請參考 [`docs/`](./docs/) 目錄**

### 文件清單

| 文件 | 說明 |
|------|------|
| [文件總覽](./docs/README.md) | 技術文件導航 |
| [MVP 範圍](./docs/planning/01-MVP-SCOPE.md) | 功能範圍、成功標準 |
| [系統架構](./docs/architecture/01-SYSTEM-ARCHITECTURE.md) | 架構設計、核心流程 |
| [資料庫設計](./docs/database/01-DATABASE-DESIGN.md) | 資料表結構、Schema |
| [API 規格](./docs/api/01-API-SPECIFICATION.md) | REST API 接口文檔 |
| [前端設計](./docs/frontend/01-FRONTEND-DESIGN.md) | 頁面設計、元件規格 |
| [AI Prompt 設計](./docs/ai/01-AI-PROMPT-DESIGN.md) | AI Prompt 模板 |
| [開發實施計劃](./docs/planning/02-IMPLEMENTATION-PLAN.md) | 4 週開發計劃 |
| [技術棧選型](./docs/planning/03-TECH-STACK.md) | 技術選擇、成本估算 |

---

## 🛠️ 技術棧

### 前端

- **框架**: Vue 3 + Vite
- **語言**: TypeScript
- **UI**: Tailwind CSS
- **路由**: Vue Router 4
- **狀態管理**: Pinia + Vue Query
- **部署**: Nginx (Docker)

### 後端

- **框架**: Python + FastAPI
- **語言**: Python 3.11+
- **ORM**: SQLAlchemy + Alembic
- **資料庫**: PostgreSQL
- **部署**: Railway / Render

### AI 服務

- **LLM**: OpenAI GPT-4o / GPT-4o-mini
- **OCR**: AWS Textract / pytesseract
- **儲存**: Cloudflare R2

---

## 🚀 快速開始

### 選項 A: 使用 Docker（推薦）🐳

**環境需求：**
- Docker 20+
- Docker Compose 2+

**一鍵啟動：**

```bash
# 1. Clone 專案
git clone <repo-url>
cd AIDemo

# 2. 設定環境變數
cp .env.docker.example .env
# 編輯 .env，填入你的 API Keys

# 3. 啟動所有服務（包含資料庫）
make init

# 或手動啟動
docker-compose up -d
```

**訪問應用：**
- 🎨 **前端**: http://localhost:3000
- 🔗 **API 文檔**: http://localhost:8000/api/docs
- 📊 **後端 API**: http://localhost:8000
- 🗄️ **PostgreSQL**: localhost:5432

**常用命令：**
```bash
make up          # 啟動服務
make down        # 停止服務
make logs        # 查看日誌
make shell-be    # 進入後端容器
make shell-db    # 進入資料庫
make migrate     # 執行資料庫遷移
make clean       # 清理所有容器和數據
```

查看所有命令：`make help`

---

### 選項 B: 本地開發環境

**環境需求：**
- Python 3.11+
- Node.js 18+ (前端)
- PostgreSQL 14+
- Git

**步驟：**

#### 1. Clone 專案

```bash
git clone <repo-url>
cd AIDemo
```

#### 2. 設定後端 (Python + FastAPI)

```bash
cd backend

# 創建虛擬環境
python -m venv venv

# 啟動虛擬環境
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

# 安裝依賴
pip install -r requirements.txt

# 設定環境變數
cp .env.example .env
# 編輯 .env，填入必要的 API Keys

# 初始化資料庫
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head

# 啟動後端
uvicorn app.main:app --reload --port 8000
```

#### 3. 設定前端 (Next.js)

```bash
cd frontend
npm install

# 設定環境變數
cp .env.local.example .env.local
# 編輯 .env.local

# 啟動前端
npm run dev
```

#### 4. 訪問應用

- **前端**: http://localhost:3000
- **後端 API**: http://localhost:8000/api
- **API 文檔**: http://localhost:8000/api/docs

---

## 📋 環境變數

### 後端 (.env)

```bash
# 資料庫
DATABASE_URL="postgresql://postgres:postgres@localhost:5432/ai_doc_demo"

# AWS S3 / Cloudflare R2
S3_BUCKET="your-bucket-name"
S3_REGION="us-east-1"
S3_ACCESS_KEY="your-access-key"
S3_SECRET_KEY="your-secret-key"
S3_ENDPOINT_URL=""  # For Cloudflare R2

# OpenAI
OPENAI_API_KEY="sk-..."
OPENAI_MODEL="gpt-4o"
OPENAI_MODEL_MINI="gpt-4o-mini"

# AWS Textract
AWS_ACCESS_KEY_ID="your-aws-key"
AWS_SECRET_ACCESS_KEY="your-aws-secret"
AWS_REGION="us-east-1"

# OCR Service
OCR_SERVICE="textract"  # or "pytesseract"

# Server
PORT=8000
```

### 前端 (.env.local)

```bash
NEXT_PUBLIC_API_URL="http://localhost:8000/api"
```

---

## 📂 專案結構

```
AIDemo/
├── frontend/                 # Next.js 前端
│   ├── src/
│   │   ├── app/             # 頁面路由
│   │   ├── components/      # React 元件
│   │   ├── lib/             # 工具函式
│   │   └── types/           # TypeScript 型別
│   └── package.json
│
├── backend/                  # Python FastAPI 後端
│   ├── app/
│   │   ├── main.py          # FastAPI 入口
│   │   ├── api/             # API 路由
│   │   ├── models/          # SQLAlchemy Models
│   │   ├── schemas/         # Pydantic Schemas
│   │   ├── services/        # 業務邏輯
│   │   ├── lib/             # AI、OCR、S3 整合
│   │   └── prompts/         # AI Prompts
│   ├── alembic/             # 資料庫遷移
│   └── requirements.txt
│
├── docs/                     # 完整技術文件
│   ├── README.md            # 文件導航
│   ├── planning/            # 規劃文件
│   ├── architecture/        # 架構設計
│   ├── database/            # 資料庫設計
│   ├── api/                 # API 規格
│   ├── frontend/            # 前端設計
│   └── ai/                  # AI 設計
│
└── README.md                # 本文件
```

---

## 🎬 Demo 展示流程

### 場景一：租賃合約處理

1. 上傳租約 PDF
2. AI 自動辨識為「租賃合約」
3. 顯示抽取欄位：承租人、租金、租期等
4. 顯示 AI 摘要
5. 使用者提問：「這份租約的押金是多少？」
6. AI 回答：「押金為 50,000 元」
7. 點擊「建立租約記錄」

### 場景二：報價單處理

1. 上傳報價單圖片
2. AI 識別為「修繕報價單」
3. 顯示抽取欄位：廠商、金額、項目
4. 顯示 AI 摘要
5. 風險提醒：「缺少報價有效期限」

### 場景三：身分證處理

1. 上傳身分證照片（已脫敏）
2. AI 識別為「身分證」
3. 顯示抽取欄位：姓名、證號、生日
4. 使用者提問：「這個人幾歲？」
5. AI 回答：「根據出生日期推算，目前約 35 歲」

---

## ⏱️ 開發時程

### Week 1：基礎建設
- 專案初始化
- 檔案上傳功能
- OCR 整合

### Week 2：AI 核心
- AI 文件分類
- 欄位抽取
- 結果頁面

### Week 3：AI 增強
- AI 摘要生成
- AI 問答功能
- UI/UX 優化

### Week 4：優化整合
- 風險檢測（P2）
- 一鍵建檔（P2）
- 部署與 Demo 準備

---

## 📊 成功指標

### 功能指標

- ✅ 支援 3 類文件上傳與處理
- ✅ AI 分類準確率 > 85%
- ✅ 欄位抽取可用率 > 75%
- ✅ AI 問答可回答基本問題

### 技術指標

- ✅ 文件上傳成功率 > 95%
- ✅ OCR 成功率 > 90%
- ✅ AI 響應時間 < 10 秒
- ✅ 處理時間 < 30 秒/文件

---

## 💰 成本估算

### MVP 階段（每月）

| 項目 | 成本 |
|------|------|
| Vercel (前端) | $0（免費額度） |
| Railway (後端 + DB) | $0（免費額度） |
| Cloudflare R2 (儲存) | $0（免費額度） |
| AWS Textract (OCR) | ~$0.75（500 頁） |
| OpenAI API | ~$10（2M tokens） |
| **總計** | **~$10.75/月** |

---

## 🔒 安全性考量

### MVP 階段

- ✅ 檔案格式驗證
- ✅ 檔案大小限制
- ✅ API Rate Limiting
- ⚠️ 暫不實作用戶認證（Demo 用途）

### 未來版本

- 🔐 JWT 認證
- 🔐 檔案存取權限控管
- 🔐 資料加密
- 🔐 GDPR 合規

---

## 🐛 已知限制

- 僅支援繁體中文文件
- 單次上傳限制 10MB
- 不支援批量處理
- 不支援複雜表格深度解析
- OCR 準確率受文件品質影響

---

## 🤝 貢獻指南

本專案為 Demo 性質，暫不接受外部貢獻。

如有問題或建議，請聯絡專案負責人。

---

## 📄 授權

本專案為內部 Demo 使用，未開放授權。

---

## 📞 聯絡資訊

**專案負責人**: Development Team
**版本**: v1.0
**最後更新**: 2026-03-17

---

## 🎉 開始開發

1. ✅ 閱讀 [`docs/`](./docs/) 中的完整技術文件
2. ✅ 準備開發環境與 API Keys
3. ✅ 按照[開發實施計劃](./docs/planning/02-IMPLEMENTATION-PLAN.md)開始 Week 1
4. ✅ 享受打造 AI 產品的樂趣！

**祝開發順利！🚀**
