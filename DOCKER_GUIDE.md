# 🐳 Docker 使用指南

完整的 Docker 部署與開發指南。

---

## 📋 目錄

1. [快速開始](#快速開始)
2. [服務架構](#服務架構)
3. [環境變數配置](#環境變數配置)
4. [常用命令](#常用命令)
5. [開發工作流](#開發工作流)
6. [故障排除](#故障排除)
7. [生產部署](#生產部署)

---

## 🚀 快速開始

### 前置需求

- Docker 20.10+
- Docker Compose 2.0+

檢查版本：
```bash
docker --version
docker-compose --version
```

### 一鍵啟動

```bash
# 1. Clone 專案
git clone <repo-url>
cd AIDemo

# 2. 複製環境變數範本
cp .env.docker.example .env

# 3. 編輯 .env 填入 API Keys
nano .env  # 或使用你喜歡的編輯器

# 4. 初始化並啟動（包含資料庫遷移）
make init
```

等待服務啟動完成後，訪問：
- 🔗 **API 文檔**: http://localhost:8000/api/docs
- 📊 **後端 API**: http://localhost:8000

---

## 🏗️ 服務架構

Docker Compose 啟動以下服務：

```
┌─────────────────────────────────────────┐
│           Docker Network                │
│                                         │
│  ┌──────────────┐   ┌──────────────┐  │
│  │   Backend    │   │  PostgreSQL  │  │
│  │  (FastAPI)   │◄──│   Database   │  │
│  │  Port: 8000  │   │  Port: 5432  │  │
│  └──────────────┘   └──────────────┘  │
│         │                               │
│         │                               │
│  ┌──────────────┐                      │
│  │   Frontend   │  (可選，未來開發)    │
│  │  (Next.js)   │                      │
│  │  Port: 3000  │                      │
│  └──────────────┘                      │
└─────────────────────────────────────────┘
```

### 服務說明

#### 1. **postgres** - PostgreSQL 資料庫
- **映像**: `postgres:14-alpine`
- **端口**: 5432
- **數據持久化**: `postgres_data` volume
- **健康檢查**: 每 10 秒檢查一次

#### 2. **backend** - FastAPI 後端
- **映像**: 自訂構建 (Python 3.11)
- **端口**: 8000
- **依賴**: postgres (等待資料庫健康)
- **自動重載**: 開發模式支援代碼熱重載

#### 3. **frontend** - Next.js 前端（可選）
- **映像**: 自訂構建 (Node 18)
- **端口**: 3000
- **狀態**: 目前已註解，待前端開發完成後啟用

---

## ⚙️ 環境變數配置

### 必填變數

```bash
# OpenAI API（必須）
OPENAI_API_KEY=sk-...

# AWS S3 或 Cloudflare R2（必須）
S3_BUCKET=your-bucket-name
S3_ACCESS_KEY=your-access-key
S3_SECRET_KEY=your-secret-key
```

### 選填變數

```bash
# AWS Textract（如果使用 Textract OCR）
AWS_ACCESS_KEY_ID=your-aws-key
AWS_SECRET_ACCESS_KEY=your-aws-secret

# Cloudflare R2（如果使用 R2）
S3_ENDPOINT_URL=https://ACCOUNT_ID.r2.cloudflarestorage.com

# Anthropic Claude（備用 AI 模型）
ANTHROPIC_API_KEY=sk-ant-...

# OCR 服務選擇
OCR_SERVICE=pytesseract  # 或 "textract"
```

---

## 🔧 常用命令

### Makefile 命令（推薦）

```bash
# 查看所有可用命令
make help

# 服務管理
make up          # 啟動所有服務
make down        # 停止所有服務
make restart     # 重啟所有服務
make ps          # 查看服務狀態

# 日誌查看
make logs        # 查看所有服務日誌
make logs-be     # 只看後端日誌
make logs-db     # 只看資料庫日誌

# 進入容器
make shell-be    # 進入後端容器 shell
make shell-db    # 進入 PostgreSQL shell

# 資料庫操作
make migrate              # 執行資料庫遷移
make migrate-create       # 創建新遷移

# 清理
make clean       # 停止並刪除所有容器和數據（⚠️ 慎用）

# 開發
make dev         # 構建並啟動（前台模式，看日誌）
make init        # 首次初始化專案
```

### Docker Compose 原生命令

```bash
# 啟動服務
docker-compose up -d              # 背景模式
docker-compose up                 # 前台模式（看日誌）

# 停止服務
docker-compose down               # 停止並刪除容器
docker-compose down -v            # 同時刪除 volumes（數據）

# 查看狀態
docker-compose ps                 # 查看服務狀態
docker-compose logs -f backend    # 查看後端日誌
docker-compose logs -f postgres   # 查看資料庫日誌

# 重啟服務
docker-compose restart            # 重啟所有服務
docker-compose restart backend    # 只重啟後端

# 進入容器
docker-compose exec backend sh    # 進入後端容器
docker-compose exec postgres psql -U postgres -d ai_doc_demo  # 進入資料庫
```

---

## 💻 開發工作流

### 1. 首次啟動

```bash
# 初始化專案（自動處理所有設置）
make init
```

這會自動：
1. 複製 `.env.docker.example` 到 `.env`（如果不存在）
2. 構建 Docker 映像
3. 啟動所有服務
4. 等待資料庫就緒
5. 執行資料庫遷移

### 2. 日常開發

```bash
# 啟動服務
make up

# 查看日誌（實時）
make logs

# 修改程式碼後，後端會自動重載（Hot Reload）

# 停止服務
make down
```

### 3. 資料庫操作

```bash
# 修改 models 後，創建新遷移
make migrate-create
# 輸入遷移訊息，例如：Add user_id field

# 應用遷移
make migrate

# 進入資料庫查看資料
make shell-db
# 在 psql 中:
\dt                 # 列出所有表
\d documents        # 查看 documents 表結構
SELECT * FROM documents LIMIT 5;  # 查詢數據
\q                  # 退出
```

### 4. 程式碼更新後重啟

```bash
# 如果更新了 requirements.txt 或 Dockerfile
docker-compose build backend
docker-compose up -d backend

# 或使用 make
make build
make restart
```

### 5. 除錯模式

```bash
# 進入後端容器
make shell-be

# 在容器內執行 Python
python
>>> from app.database import engine
>>> from app.models import Document
>>> # 執行除錯程式碼
```

---

## 🐛 故障排除

### 問題 1: 端口已被占用

**錯誤訊息:**
```
Error: bind: address already in use
```

**解決方案:**
```bash
# 查看哪個程式占用端口
lsof -i :8000  # 或 :5432

# 停止該程式，或修改 docker-compose.yml 中的端口映射
```

### 問題 2: 資料庫連接失敗

**錯誤訊息:**
```
could not connect to server: Connection refused
```

**解決方案:**
```bash
# 檢查資料庫是否運行
docker-compose ps

# 查看資料庫日誌
make logs-db

# 重啟資料庫
docker-compose restart postgres

# 等待 5-10 秒讓資料庫完全啟動
```

### 問題 3: 遷移失敗

**錯誤訊息:**
```
Target database is not up to date
```

**解決方案:**
```bash
# 進入後端容器
make shell-be

# 查看當前遷移狀態
alembic current

# 查看所有遷移
alembic history

# 強制升級到最新版本
alembic upgrade head
```

### 問題 4: 環境變數未生效

**檢查步驟:**
```bash
# 1. 確認 .env 文件存在
ls -la .env

# 2. 檢查容器內的環境變數
docker-compose exec backend env | grep OPENAI

# 3. 重啟服務讓環境變數生效
make restart
```

### 問題 5: 容器無法啟動

```bash
# 查看詳細錯誤訊息
docker-compose logs backend

# 檢查容器狀態
docker-compose ps

# 重新構建並啟動
docker-compose build --no-cache backend
docker-compose up -d backend
```

---

## 🚀 生產部署

### 使用 Docker Compose 部署

```bash
# 1. 準備生產環境變數
cp .env.docker.example .env.production

# 2. 編輯生產配置
nano .env.production
# 設置：
# - DEBUG=false
# - 生產資料庫 URL
# - 真實的 API Keys

# 3. 使用生產配置啟動
docker-compose --env-file .env.production up -d

# 4. 執行遷移
docker-compose exec backend alembic upgrade head
```

### 使用 Docker Swarm / Kubernetes

詳見 `docs/deployment/` 目錄（待補充）

---

## 📊 監控與日誌

### 查看資源使用

```bash
# 查看容器資源使用情況
docker stats

# 只看特定容器
docker stats ai-doc-backend ai-doc-postgres
```

### 日誌管理

```bash
# 查看最近 100 行日誌
docker-compose logs --tail=100 backend

# 查看特定時間範圍日誌
docker-compose logs --since 2024-01-01 backend

# 保存日誌到文件
docker-compose logs backend > backend.log
```

---

## 🧹 清理與維護

### 清理未使用的資源

```bash
# 清理停止的容器
docker container prune

# 清理未使用的映像
docker image prune

# 清理未使用的 volumes
docker volume prune

# 全部清理（⚠️ 慎用）
docker system prune -a --volumes
```

### 備份資料庫

```bash
# 匯出資料庫
docker-compose exec postgres pg_dump -U postgres ai_doc_demo > backup.sql

# 恢復資料庫
cat backup.sql | docker-compose exec -T postgres psql -U postgres ai_doc_demo
```

---

## 📚 延伸閱讀

- [Docker 官方文檔](https://docs.docker.com/)
- [Docker Compose 文檔](https://docs.docker.com/compose/)
- [FastAPI Docker 部署](https://fastapi.tiangolo.com/deployment/docker/)
- [PostgreSQL Docker 官方映像](https://hub.docker.com/_/postgres)

---

**最後更新**: 2026-03-19
**維護者**: Development Team
