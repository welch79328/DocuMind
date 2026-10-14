# DocuMind - AI Document Intelligence

> 台灣不動產文件（謄本、合約、帳單、修繕／點交照片）的辨識與欄位抽取服務，以 API 供 JGB 等系統串接

[![GitHub](https://img.shields.io/badge/GitHub-DocuMind-blue?logo=github)](https://github.com/welch79328/DocuMind)
[![Python](https://img.shields.io/badge/Python-3.11+-green?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-teal?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Vue](https://img.shields.io/badge/Vue-3.4+-brightgreen?logo=vue.js)](https://vuejs.org/)

## 📖 專案簡介

上傳 PDF 或圖片，回傳結構化欄位。電子 PDF（如網路申領的電子謄本）直接讀文字層、不經 OCR；
掃描件與照片走本地 OCR（PaddleOCR + Tesseract），必要時由 LLM 校正；信心不足的欄位進人工複核佇列。

### 支援的文件類型

| `document_type` | 文件 |
|---|---|
| `transcript` | 建物／土地謄本（謄本上印的每一項都解析，另有固定輸出格式 `transcript_records`） |
| `contract` | 合約（含租約） |
| `bill` | 帳單（水電、管理費等） |
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
| [部署](./docs/DEPLOYMENT.md) | 部署指南；§0.5 為線上機實況 |
| [前端設計](./docs/frontend/01-FRONTEND-DESIGN.md) | 頁面設計、元件規格 |

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

- **OCR**: PaddleOCR（ONNX Runtime）+ Tesseract，本地執行；含文字層的 PDF 不經 OCR
- **LLM**: OpenAI（模型分工見 `docs/planning/03-TECH-STACK.md`）
- **儲存**: 預設本機（`STORAGE_TYPE=local`）

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
cp .env.docker.example .env
# 編輯 .env，填入你的 API Keys

# 3. 啟動所有服務（包含資料庫）
make init

# 或手動啟動
docker-compose up -d
```

**訪問應用：**
- 🎨 **前端**: http://localhost:3000
- 🔗 **API 文檔**: http://localhost:8003/api/docs
- 📊 **後端 API**: http://localhost:8003
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
- Python 3.11+
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

#### 3. 設定前端 (Vue 3)

```bash
cd frontend
npm install

# 啟動前端
npm run dev
```

#### 4. 訪問應用

- **前端**: http://localhost:3000
- **後端 API**: http://localhost:8003/api
- **API 文檔**: http://localhost:8003/api/docs

---

## 📋 環境變數

### 快速設定（推薦）

**Docker 部署只需一個檔案：**

```bash
# 1. 複製範例檔案
cp .env.example .env

# 2. 編輯設定（最小配置）
nano .env

# 只需填入以下內容即可啟動：
STORAGE_TYPE=local          # 本地儲存（無需 S3）
OCR_SERVICE=pytesseract     # 免費 OCR
OPENAI_API_KEY=             # 留空（無法使用 AI 功能）

# 3. 啟動服務
docker-compose up -d
```

**完整功能需要 OpenAI API Key：**
```bash
OPENAI_API_KEY=sk-proj-xxxxxxxx  # 取得：https://platform.openai.com/api-keys
```

**詳細說明請參考：[ENV_GUIDE.md](./ENV_GUIDE.md)**

---

### 環境變數檔案說明

| 檔案 | 用途 | 是否必需 |
|------|------|---------|
| `.env` | Docker 部署的唯一配置檔 | ✅ 必需 |
| `.env.example` | 範例檔案 | 📄 參考 |

---

## 📂 專案結構

```
DocuMind/
├── frontend/                 # Vue 3 前端
│   ├── src/
│   │   ├── views/           # 頁面組件
│   │   ├── components/      # Vue 元件
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
