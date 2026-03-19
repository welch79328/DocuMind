# 🚀 Docker 快速開始

5 分鐘內啟動整個專案！

---

## ⚡ 超快速啟動（3 步驟）

```bash
# 1️⃣ 設定環境變數
cp .env.docker.example .env
nano .env  # 填入你的 OPENAI_API_KEY

# 2️⃣ 一鍵啟動
make init

# 3️⃣ 訪問 API
open http://localhost:8000/api/docs
```

就這麼簡單！✨

---

## 📋 常用命令速查表

### 🎬 啟動與停止

```bash
make up          # ▶️  啟動所有服務
make down        # ⏹️  停止所有服務
make restart     # 🔄 重啟所有服務
make ps          # 📊 查看服務狀態
```

### 📝 查看日誌

```bash
make logs        # 📄 查看所有日誌
make logs-be     # 🔍 只看後端日誌
make logs-db     # 🔍 只看資料庫日誌
```

### 🐚 進入容器

```bash
make shell-be    # 💻 進入後端容器
make shell-db    # 🗄️ 進入資料庫
```

### 🗄️ 資料庫操作

```bash
make migrate              # ⬆️ 執行遷移
make migrate-create       # ➕ 創建新遷移
```

### 🧹 清理

```bash
make clean       # 🗑️ 刪除所有容器和數據（⚠️ 慎用）
```

---

## 🔑 必填環境變數

編輯 `.env` 文件，至少填入以下變數：

```bash
# 必須
OPENAI_API_KEY=sk-...

# 必須（文件儲存）
S3_BUCKET=your-bucket-name
S3_ACCESS_KEY=your-access-key
S3_SECRET_KEY=your-secret-key

# 選填（如果使用 AWS Textract）
AWS_ACCESS_KEY_ID=your-aws-key
AWS_SECRET_ACCESS_KEY=your-aws-secret
```

---

## 🌐 訪問點

啟動後可訪問：

- 🔗 **API 文檔（Swagger）**: http://localhost:8000/api/docs
- 📖 **API 文檔（ReDoc）**: http://localhost:8000/api/redoc
- 🏥 **健康檢查**: http://localhost:8000/api/health
- 🗄️ **PostgreSQL**: `localhost:5432`
  - 用戶名: `postgres`
  - 密碼: `postgres`
  - 資料庫: `ai_doc_demo`

---

## 🐛 快速故障排除

### 問題：端口被占用

```bash
# 查看誰占用了端口
lsof -i :8000

# 停止該程式或修改端口
```

### 問題：資料庫連接失敗

```bash
# 重啟資料庫
docker-compose restart postgres

# 等待 10 秒
sleep 10

# 再次嘗試
make migrate
```

### 問題：環境變數沒生效

```bash
# 檢查 .env 文件
cat .env

# 重啟服務
make restart
```

### 問題：想重新開始

```bash
# 完全清理並重新初始化
make clean
make init
```

---

## 📚 更多資訊

- 📖 **完整指南**: 查看 `DOCKER_GUIDE.md`
- 🎯 **專案文檔**: 查看 `README.md`
- 🔧 **遷移總結**: 查看 `MIGRATION_SUMMARY.md`

---

## 🎉 快速測試 API

啟動服務後，測試 API：

```bash
# 健康檢查
curl http://localhost:8000/api/health

# 查看 API 文檔
open http://localhost:8000/api/docs
```

---

**提示**: 所有 `make` 命令都可以用 `docker-compose` 替代。
例如：`make up` = `docker-compose up -d`

輸入 `make help` 查看所有可用命令！
