# 環境變數設定指南

## 📁 專案的環境變數檔案結構

```
DocuMind/
├── .env                    # ✅ Docker 部署時的唯一配置檔（重要！）
├── .env.example            # 📄 範例檔案（給其他開發者參考）
├── backend/
│   ├── .env.example        # 📄 本地開發參考（Docker 部署時不使用）
│   └── .env.backup         # 💾 舊的備份檔案（可刪除）
└── frontend/
    ├── .env                # ✅ 前端設定
    └── .env.example        # 📄 前端範例

```

---

## 🎯 使用哪個 .env？

### Docker 部署（推薦）✅

**唯一需要的檔案：根目錄的 `.env`**

```bash
# 1. 複製範例檔案
cp .env.example .env

# 2. 編輯設定
nano .env

# 3. 啟動服務
docker-compose up -d
```

**為什麼？**
- `docker-compose.yml` 會讀取根目錄的 `.env`
- 透過 `environment:` 區塊注入到容器
- 優先級最高，會覆蓋所有其他設定

---

### 本地開發（不使用 Docker）

如果你想在本地直接執行（不用 Docker）：

**後端：**
```bash
cd backend
cp .env.example .env
nano .env
uvicorn app.main:app --reload
```

**前端：**
```bash
cd frontend
cp .env.example .env
nano .env
npm run dev
```

---

## ⚙️ 最小化配置（快速開始）

**只需配置這些就能啟動：**

```bash
# .env
STORAGE_TYPE=local          # 使用本地儲存（無需 S3）
OCR_SERVICE=pytesseract     # 使用免費 OCR
OPENAI_API_KEY=             # 留空（無法使用 AI 功能）
```

**可以測試：**
- ✅ 前端介面
- ✅ API 文檔
- ✅ 資料庫連線
- ❌ 文件上傳和 AI 處理（需要 OpenAI API Key）

---

## 🚀 完整配置（AI 功能）

**需要配置：**

```bash
# .env
STORAGE_TYPE=local
OCR_SERVICE=pytesseract
OPENAI_API_KEY=sk-proj-xxxxxxxx  # 👈 填入你的 OpenAI API Key
```

**可以測試：**
- ✅ 所有功能
- ✅ 文件上傳
- ✅ OCR 辨識
- ✅ AI 分類、欄位抽取、摘要、問答

**取得 OpenAI API Key：**
1. 前往 https://platform.openai.com/api-keys
2. 建立新的 API Key
3. 複製並填入 `.env`

---

## 🔄 切換儲存方式

### 本地儲存 → S3/Cloudflare R2

```bash
# 編輯 .env
STORAGE_TYPE=s3
S3_BUCKET=your-bucket-name
S3_ACCESS_KEY=your-access-key
S3_SECRET_KEY=your-secret-key
S3_ENDPOINT_URL=  # Cloudflare R2 endpoint

# 重啟服務
docker-compose restart backend
```

---

## 📊 環境變數優先級

在 Docker 環境中：

```
1. docker-compose.yml 的 environment:  ✅ 最高優先級
   ↓ (從根目錄 .env 讀取)
2. 容器內的環境變數
   ↓
3. backend/.env                        ❌ 不會被讀取
```

**重要：**
- 在 Docker 部署中，`backend/.env` 不會生效
- 所有設定都透過根目錄的 `.env` 傳遞

---

## 🧹 清理說明

### 可以刪除的檔案：

- `backend/.env.backup` - 舊的備份檔案
- `backend/.env` - 如果使用 Docker 部署

### 必須保留的檔案：

- `.env` - **唯一的配置檔案**（Docker 部署）
- `.env.example` - 範例檔案
- `backend/.env.example` - 文檔參考
- `frontend/.env` - 前端設定

---

## ❓ 常見問題

**Q: 我修改了 backend/.env 為什麼沒效果？**
A: Docker 部署時會被忽略。請修改根目錄的 `.env`。

**Q: 我需要同時修改多個 .env 嗎？**
A: 不需要！Docker 部署只需修改根目錄的 `.env`。

**Q: .env.example 有什麼用？**
A: 給其他開發者參考。當別人 clone 專案時，可以複製它來建立自己的 `.env`。

**Q: 如何確認我的設定被讀取了？**
```bash
# 查看容器內的環境變數
docker exec ai-doc-backend env | grep OPENAI_API_KEY
```

---

## 🎯 快速參考

### 啟動服務
```bash
docker-compose up -d
```

### 修改設定
```bash
nano .env                    # 修改設定
docker-compose restart       # 重啟所有服務
```

### 查看日誌
```bash
docker-compose logs -f backend
```

### 檢查環境變數
```bash
docker exec ai-doc-backend env
```

---

**更新日期：2026-03-19**
