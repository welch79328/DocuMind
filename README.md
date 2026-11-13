# DocuMind - AI Document Intelligence

> 台灣不動產文件（謄本、合約、帳單、收據、修繕／點交照片）的辨識與欄位抽取服務，以 API 供 JGB 等系統串接

[![GitHub](https://img.shields.io/badge/GitHub-DocuMind-blue?logo=github)](https://github.com/welch79328/DocuMind)
[![Python](https://img.shields.io/badge/Python-3.11+-green?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-teal?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Vue](https://img.shields.io/badge/Vue-3.4+-brightgreen?logo=vue.js)](https://vuejs.org/)

## 📖 專案簡介

上傳 PDF 或圖片，回傳結構化欄位。電子 PDF（如網路申領的電子謄本）直接讀文字層、不經 OCR；
謄本的掃描件與照片走本地 OCR，必要時由 LLM 校正；收據、帳單、合約的影像與掃描 PDF 在伺服器開啟「直讀」時整頁交視覺模型讀、不跑本地 OCR（線上已開啟）；
修繕、點交照片由視覺模型做影像理解。信心不足的欄位進人工複核佇列。

### 支援的文件類型

| `document_type` | 文件 |
|---|---|
| `transcript` | 建物／土地謄本（謄本上印的每一項都解析，另有固定輸出格式 `transcript_records`） |
| `contract` | 合約（含租約） |
| `bill` | 帳單（水電、管理費等） |
| `receipt` | 收據、發票（伺服器設定 `DIRECT_READ_DOCUMENT_TYPES` 列入 `receipt` 時才開放） |
| `repair_photo` | 修繕現場照片（影像理解） |
| `handover_photo` | 點交現場照片（影像理解） |

端點、欄位、錯誤碼與實測數據見 [`docs/api/INTEGRATION.md`](./docs/api/INTEGRATION.md)。

---

## 📚 技術文件

**完整技術文件請參考 [`docs/`](./docs/) 目錄**

### 文件清單

| 文件 | 說明 |
|------|------|
| [文件總覽](./docs/README.md) | 技術文件導航 |
| [API 對接規格](./docs/api/INTEGRATION.md) | 給外部系統的串接文件（端點、欄位、錯誤碼、實測數據） |
| [謄本現況](./docs/planning/transcript-status.md) | 謄本解析現況、決策、待辦 |
| [技術棧](./docs/planning/03-TECH-STACK.md) | 技術棧現況 |
| [部署](./docs/DEPLOYMENT.md) | 部署指南；§0.5 為線上機實況，§8 為關鍵環境變數 |

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
- **部署**: AWS EC2 單機 Docker Compose（frontend、backend、postgres、nginx；見 `docs/DEPLOYMENT.md` §0.5）

### AI 服務

- **OCR**: PaddleOCR（ONNX Runtime），本地執行；引擎清單由 `OCR_ENGINES` 設定，程式預設 `["paddleocr", "tesseract"]`，線上為 `["paddleocr"]`（見 `docs/DEPLOYMENT.md` §0.5）；含文字層的 PDF 不經 OCR
- **LLM**: 謄本走 OpenAI；帳單、收據、合約、修繕照片、點交照片線上走 Bedrock Qwen3 VL（flex），由分流表 `LLM_PROVIDER_BY_DOCUMENT_TYPE` 設定，程式預設 OpenAI（模型分工見 `docs/planning/03-TECH-STACK.md`）
- **儲存**: `STORAGE_TYPE`，程式預設 `local`；docker-compose 在 `.env` 沒設時帶 `s3`

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
cd DocuMind

# 2. 設定環境變數
cp .env.example .env
# 編輯 .env，填入你的 API Keys（鍵的說明見 docs/DEPLOYMENT.md §8）

# 3. 建置、啟動所有服務並執行資料庫遷移
make init

# 或手動啟動（backend 容器啟動時會自動執行 alembic upgrade head）
docker-compose up -d
```

**訪問應用**（compose 對外只開 nginx 與 PostgreSQL）：
- 🎨 **前端**: http://localhost:8085
- 🔗 **API 文檔**: http://localhost:8085/api/docs
- 📊 **後端 API**: http://localhost:8085/api
- 🗄️ **PostgreSQL**: localhost:5433

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
- Python 3.11（requirements 需要 3.11，系統若為較舊的 Python 請另裝）
- Node.js 18+ (前端)
- PostgreSQL 14+
- Git

**步驟：**

#### 1. Clone 專案

```bash
git clone <repo-url>
cd DocuMind
```

#### 2. 設定後端 (Python + FastAPI)

```bash
cd backend

# 創建虛擬環境
python3.11 -m venv venv

# 啟動虛擬環境
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

# 安裝依賴
pip install -r requirements.txt

# 設定環境變數（在 backend/ 下執行時讀的是 backend/.env）
cp ../.env.example .env
# 編輯 .env，填入必要的 API Keys；DATABASE_URL 預設 localhost:5432/ai_doc_demo

# 建立資料表（遷移檔已在 alembic/versions/）
alembic upgrade head

# 啟動後端
uvicorn app.main:app --reload --port 8000
```

#### 3. 設定前端 (Vue 3)

```bash
cd frontend
npm install

# 啟動前端（Vite 把 /api 轉給 http://localhost:8000）
npm run dev
```

#### 4. 訪問應用

- **前端**: http://localhost:3000
- **後端 API**: http://localhost:8000/api
- **API 文檔**: http://localhost:8000/api/docs

---

## 📋 環境變數

### 快速設定

**Docker 部署讀根目錄的 `.env`**（`docker-compose.yml` 以 `env_file` 整份帶進 backend 容器）：

```bash
# 1. 複製範例檔案
cp .env.example .env

# 2. 編輯設定
nano .env

# 本地儲存（docker-compose 在 .env 沒設 STORAGE_TYPE 時帶 s3）
STORAGE_TYPE=local

# LLM：程式預設所有類型都走 OpenAI
OPENAI_API_KEY=

# 3. 啟動服務（改過 .env 後也用這行重建容器）
docker-compose up -d
```

依文件類型改走 Bedrock（`LLM_PROVIDER_BY_DOCUMENT_TYPE`、`BEDROCK_API_KEY`）、開啟直讀（`DIRECT_READ_DOCUMENT_TYPES`）、OCR 引擎（`OCR_ENGINES`）等鍵的說明，見 [docs/DEPLOYMENT.md](./docs/DEPLOYMENT.md) §8；所有鍵與程式預設值在 `backend/app/config.py`。

---

### 環境變數檔案說明

| 檔案 | 用途 |
|------|------|
| `.env` | Docker 部署的設定檔（根目錄） |
| `backend/.env` | 在 `backend/` 下直接跑 uvicorn 時讀的設定檔 |
| `.env.example` | 範例檔案 |

---

## 📂 專案結構

```
DocuMind/
├── frontend/                 # Vue 3 前端
│   ├── src/
│   │   ├── views/           # 頁面組件
│   │   ├── components/      # Vue 元件
│   │   ├── composables/     # 組合式函式
│   │   ├── services/        # API 呼叫（axios）
│   │   ├── types/           # TypeScript 型別
│   │   ├── router/          # 路由設定
│   │   ├── assets/          # 靜態資源
│   │   └── main.ts          # 應用入口
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
├── nginx/                    # 反向代理設定（對外 8085）
├── docs/                     # 技術文件（導航見 docs/README.md）
│
└── README.md                # 本文件
```

---

## 🤝 貢獻指南

本專案暫不接受外部貢獻。

如有問題或建議，請聯絡專案負責人。

---

## 📄 授權

本專案為內部使用，未開放授權。
