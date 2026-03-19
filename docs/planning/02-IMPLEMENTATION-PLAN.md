# AI Document Intelligence Demo - 開發實施計劃

## 1. 專案時程總覽

### 1.1 整體規劃

**總開發時間：4 週（28 天）**

| 週次 | 時間 | 重點工作 | 交付物 | 狀態 |
|------|------|----------|--------|------|
| Week 1 | Day 1-7 | 基礎建設 | 上傳、儲存、OCR 整合 | 待開始 |
| Week 2 | Day 8-14 | AI 核心功能 | 分類、抽取、結果頁 | 待開始 |
| Week 3 | Day 15-21 | AI 增強功能 | 摘要、問答 | 待開始 |
| Week 4 | Day 22-28 | 優化與整合 | 風險檢測、建檔、Demo 演練 | 待開始 |

---

## 2. Week 1：基礎建設（Day 1-7）

### 2.1 目標

建立專案骨架，完成檔案上傳與 OCR 處理流程。

### 2.2 詳細任務

#### Day 1-2：專案初始化

**後端（Python + FastAPI + SQLAlchemy）**

- [ ] 初始化 Python 專案
  ```bash
  mkdir backend && cd backend
  python -m venv venv
  source venv/bin/activate  # macOS/Linux
  # venv\Scripts\activate   # Windows
  ```

- [ ] 安裝依賴
  ```bash
  pip install fastapi uvicorn[standard] sqlalchemy alembic psycopg2-binary
  pip install python-multipart python-dotenv pydantic-settings
  pip install openai boto3 pytesseract pillow
  pip freeze > requirements.txt
  ```

- [ ] 建立專案結構
  ```
  backend/
  ├── app/
  │   ├── __init__.py
  │   ├── main.py
  │   ├── config.py
  │   ├── database.py
  │   ├── models/
  │   ├── schemas/
  │   ├── api/
  │   ├── services/
  │   ├── lib/
  │   └── prompts/
  ├── alembic/
  │   └── versions/
  ├── alembic.ini
  └── requirements.txt
  ```

- [ ] 設定 Alembic
  ```bash
  alembic init alembic
  ```

- [ ] 編寫 SQLAlchemy Models（參考資料庫設計文檔）

- [ ] 建立資料庫並執行 migration
  ```bash
  alembic revision --autogenerate -m "Initial migration"
  alembic upgrade head
  ```

**前端（Vue 3 + Vite）**

- [ ] 初始化 Vue 3 專案
  ```bash
  npm create vite@latest frontend -- --template vue-ts
  cd frontend
  npm install
  ```

- [ ] 安裝依賴
  ```bash
  npm install vue-router@4 pinia axios @tanstack/vue-query
  npm install -D tailwindcss postcss autoprefixer
  npx tailwindcss init -p
  ```

- [ ] 設定 Tailwind CSS
  ```javascript
  // tailwind.config.js
  export default {
    content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
    theme: { extend: {} },
    plugins: [],
  }
  ```

- [ ] 建立專案結構（參考前端設計文檔）
  ```
  frontend/src/
  ├── main.ts
  ├── App.vue
  ├── router/
  ├── views/
  ├── components/
  ├── services/
  ├── types/
  └── assets/
  ```

**檢查點：**
- ✅ 專案可成功啟動（前後端）
- ✅ 資料庫連線成功
- ✅ 基本路由可訪問

---

#### Day 3-4：檔案上傳功能

**後端**

- [ ] 整合 S3/Cloudflare R2 (已包含在 requirements.txt)
  ```bash
  # 已安裝 boto3
  ```

- [ ] 實作檔案上傳 Service
  ```python
  # app/lib/s3_client.py
  - upload_to_s3()
  - validate_file()
  - generate_file_name()
  ```

- [ ] 實作上傳 API
  ```python
  # app/api/v1/documents.py
  @router.post("/upload")
  async def upload_document(file: UploadFile = File(...)):
      pass
  ```

- [ ] 實作檔案驗證
  - 檔案格式驗證（PDF/JPG/PNG）
  - 檔案大小驗證（< 10MB）
  ```python
  ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
  MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
  ```

**前端**

- [ ] 實作上傳頁面 UI
  ```vue
  <!-- src/views/UploadView.vue -->
  <template>
    <div class="upload-container">
      <FileUploader @file-selected="handleUpload" />
    </div>
  </template>
  ```

- [ ] 實作 FileUploader 元件
  ```vue
  <!-- src/components/upload/FileUploader.vue -->
  <template>
    - 拖拽上傳區域
    - 檔案選擇按鈕
    - 上傳進度條
    - 錯誤提示
  </template>
  ```

- [ ] 整合上傳 API
  ```typescript
  // src/services/api.ts
  export async function uploadDocument(file: File) {
    const formData = new FormData()
    formData.append('file', file)
    return axios.post('/api/v1/documents/upload', formData)
  }
  ```

**檢查點：**
- ✅ 可成功上傳檔案至 S3
- ✅ 檔案資訊寫入資料庫
- ✅ 前端可顯示上傳狀態
- ✅ 錯誤處理正常運作

---

#### Day 5-7：OCR 整合

**後端**

- [ ] 選擇 OCR 方案並整合 (已包含在 requirements.txt)
  - **方案 A（推薦）**: AWS Textract (boto3)
  - **方案 B（備用）**: pytesseract

- [ ] 實作 OCR Service
  ```python
  # app/lib/ocr_client.py
  async def extract_text(file_path: str) -> dict:
      # 使用 AWS Textract 或 pytesseract
      pass

  async def extract_text_from_pdf(pdf_path: str) -> str:
      pass

  async def extract_text_from_image(image_path: str) -> str:
      pass
  ```

- [ ] 實作處理 API
  ```python
  # app/api/v1/documents.py
  @router.post("/{document_id}/process")
  async def process_document(document_id: UUID, db: Session = Depends(get_db)):
      pass
  ```

- [ ] 實作背景任務處理
  ```python
  # app/services/document_service.py
  async def process_document(document_id: UUID, db: Session):
      # 1. 下載文件
      # 2. 執行 OCR
      # 3. 儲存 OCR 結果
      # 4. 執行 AI 處理
      pass
  ```

**前端**

- [ ] 實作文件列表頁
  ```vue
  <!-- src/views/HomeView.vue -->
  <template>
    <div>
      <DocumentList :documents="documents" />
      <StatusFilter @filter="handleFilter" />
    </div>
  </template>
  ```

- [ ] 實作文件詳情頁基本架構
  ```vue
  <!-- src/views/DocumentView.vue -->
  <template>
    <div>
      <ProcessingLoader v-if="document.status === 'processing'" />
      <DocumentDetails v-else :document="document" />
    </div>
  </template>
  ```

- [ ] 實作 ProcessingLoader 元件
  ```vue
  <!-- src/components/document/ProcessingLoader.vue -->
  <template>
    <div class="loading-spinner">
      <span>處理中...</span>
    </div>
  </template>
  ```

**檢查點：**
- ✅ OCR 可成功辨識文字
- ✅ OCR 結果儲存至資料庫
- ✅ 前端可輪詢處理狀態
- ✅ 多頁 PDF 可正確處理

**Week 1 交付物：**
- ✅ 完整的上傳流程
- ✅ OCR 處理功能
- ✅ 基本前端頁面

---

## 3. Week 2：AI 核心功能（Day 8-14）

### 3.1 目標

實作 AI 文件分類與欄位抽取，完成核心展示功能。

### 3.2 詳細任務

#### Day 8-9：AI 整合與文件分類

**後端**

- [ ] AI SDK 已安裝 (已包含在 requirements.txt)
  - **方案 A**: OpenAI (openai)
  - **方案 B**: Anthropic Claude (anthropic)

- [ ] 建立 Prompt 檔案
  ```python
  # app/prompts/classification.py
  CLASSIFICATION_PROMPT = """
  你是一個專業的文件分類助手...
  {ocr_text}
  """
  ```

- [ ] 實作 AI Service
  ```python
  # app/lib/ai_client.py
  from openai import AsyncOpenAI

  client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

  async def classify_document(ocr_text: str) -> dict:
      response = await client.chat.completions.create(
          model="gpt-4o-mini",
          messages=[{"role": "user", "content": prompt}],
          response_format={"type": "json_object"}
      )
      return json.loads(response.choices[0].message.content)
  ```

- [ ] 整合至處理流程
  ```python
  # app/services/document_service.py
  async def process_document(document_id: UUID, db: Session):
      # 1. runOCR()
      # 2. classifyDocument()
      # 3. saveAIResult()
  ```

**測試**

- [ ] 準備 3 類測試文件各 2 份
- [ ] 測試分類準確率
- [ ] 調整 Prompt 直到準確率 > 85%

**檢查點：**
- ✅ AI 可正確分類 3 類文件
- ✅ 返回信心度分數
- ✅ unknown 類型可正確識別

---

#### Day 10-12：欄位抽取

**後端**

- [ ] 建立抽取 Prompts
  ```python
  # app/prompts/extraction.py
  LEASE_CONTRACT_PROMPT = """..."""
  REPAIR_QUOTE_PROMPT = """..."""
  ID_CARD_PROMPT = """..."""
  ```

- [ ] 實作抽取邏輯
  ```python
  # app/lib/ai_client.py
  async def extract_fields(doc_type: str, ocr_text: str) -> dict:
      prompt_map = {
          "lease_contract": LEASE_CONTRACT_PROMPT,
          "repair_quote": REPAIR_QUOTE_PROMPT,
          "id_card": ID_CARD_PROMPT
      }
      # 調用 OpenAI API
      return extracted_data
  ```

- [ ] 整合至處理流程
  ```python
  async def process_document(document_id: UUID, db: Session):
      # 1. runOCR()
      # 2. classifyDocument()
      # 3. extractFields()      # 新增
      # 4. saveAIResult()
  ```

- [ ] 實作欄位驗證
  ```python
  # app/services/validation.py
  def validate_date_format(date_str: str) -> bool:
      pass

  def validate_amount(amount: Union[int, float]) -> bool:
      pass
  ```

**前端**

- [ ] 實作 ExtractedFields 元件
  ```vue
  <!-- src/components/result/ExtractedFields.vue -->
  <template>
    <div class="fields-list">
      <div v-for="(value, key) in fields" :key="key">
        <label>{{ fieldLabels[key] }}</label>
        <input v-model="fields[key]" @blur="handleSave" />
      </div>
    </div>
  </template>
  ```

- [ ] 實作欄位標籤對應
  ```typescript
  // src/lib/constants.ts
  export const fieldLabels = {
    lease_contract: {
      landlord_name: '出租人姓名',
      tenant_name: '承租人姓名',
      rent: '月租金',
      // ...
    },
    // ...
  }
  ```

**測試**

- [ ] 測試 3 類文件抽取準確率
- [ ] 優化 Prompt
- [ ] 測試邊界案例（缺失欄位、格式異常）

**檢查點：**
- ✅ 欄位抽取準確率 > 75%
- ✅ JSON 格式正確
- ✅ 前端可正確顯示欄位
- ✅ 編輯功能正常運作

---

#### Day 13-14：結果頁完善

**前端**

- [ ] 完善文件詳情頁
  ```typescript
  // app/documents/[id]/page.tsx
  - 文件資訊區
  - 分類結果顯示
  - 抽取欄位顯示
  - 操作按鈕區
  ```

- [ ] 實作狀態標籤元件
  ```typescript
  // components/document/StatusBadge.tsx
  // components/document/DocumentTypeBadge.tsx
  // components/result/ConfidenceScore.tsx
  ```

- [ ] 實作文件卡片元件
  ```typescript
  // components/document/DocumentCard.tsx
  - 用於列表頁
  ```

- [ ] 優化 UI/UX
  - 載入動畫
  - 錯誤提示
  - 成功訊息

**後端**

- [ ] 實作查詢 API
  ```typescript
  GET /api/documents
  GET /api/documents/:id
  ```

- [ ] 加入分頁功能
- [ ] 加入篩選功能（狀態、類型）

**檢查點：**
- ✅ 完整的處理流程可運作
- ✅ 結果頁顯示正常
- ✅ 文件列表可篩選

**Week 2 交付物：**
- ✅ AI 分類功能
- ✅ AI 欄位抽取功能
- ✅ 完整的結果展示頁

---

## 4. Week 3：AI 增強功能（Day 15-21）

### 4.1 目標

實作 AI 摘要與問答功能，提升展示亮點。

### 4.2 詳細任務

#### Day 15-16：AI 摘要生成

**後端**

- [ ] 建立摘要 Prompt
  ```typescript
  // src/prompts/summary.ts
  ```

- [ ] 實作摘要生成邏輯
  ```typescript
  // src/lib/ai.service.ts
  - generateSummary(docType, extractedData, ocrText)
  ```

- [ ] 整合至處理流程
  ```typescript
  processDocument() {
    1. runOCR()
    2. classifyDocument()
    3. extractFields()
    4. generateSummary()    // 新增
    5. saveAIResult()
  }
  ```

**前端**

- [ ] 實作 AISummary 元件
  ```typescript
  // components/result/AISummary.tsx
  ```

- [ ] 整合至詳情頁
  ```typescript
  // app/documents/[id]/page.tsx
  <AISummary summary={aiResult.summary} />
  ```

**檢查點：**
- ✅ 摘要生成正常
- ✅ 摘要品質良好（人工評分 > 4.0）
- ✅ 前端顯示美觀

---

#### Day 17-19：AI 問答功能

**後端**

- [ ] 建立問答 Prompt
  ```typescript
  // src/prompts/chat.ts
  ```

- [ ] 實作問答 API
  ```typescript
  POST /api/documents/:id/chat
  ```

- [ ] 實作問答邏輯
  ```typescript
  // src/services/chat.service.ts
  - answerQuestion(documentId, question)
  - buildContext()
  - formatAnswer()
  ```

- [ ] 實作問答記錄儲存（可選）
  ```typescript
  // 寫入 document_chat_logs 表
  ```

**前端**

- [ ] 實作 ChatInterface 元件
  ```typescript
  // components/chat/ChatInterface.tsx
  - 問題輸入框
  - 訊息列表
  - 建議問題
  ```

- [ ] 實作 MessageBubble 元件
  ```typescript
  // components/chat/MessageBubble.tsx
  ```

- [ ] 整合至詳情頁
  ```typescript
  // app/documents/[id]/page.tsx
  <ChatInterface documentId={documentId} />
  ```

**測試**

- [ ] 準備 10 個測試問題
- [ ] 測試回答品質
- [ ] 優化 Prompt

**檢查點：**
- ✅ 問答功能可運作
- ✅ 回答品質良好
- ✅ UI 流暢易用

---

#### Day 20-21：功能優化與測試

**後端**

- [ ] 優化 AI 處理效能
  - 並行處理（OCR + 分類）
  - 快取機制

- [ ] 錯誤處理完善
  - AI API 失敗重試
  - 逾時處理
  - 錯誤訊息優化

- [ ] 日誌記錄
  ```typescript
  - 記錄 AI 調用次數
  - 記錄處理時間
  - 記錄錯誤情況
  ```

**前端**

- [ ] UI/UX 優化
  - 載入動畫優化
  - 錯誤提示優化
  - 響應式設計調整

- [ ] 性能優化
  - React Query 快取策略
  - 圖片懶加載

**整合測試**

- [ ] 端到端測試完整流程
- [ ] 多種文件類型測試
- [ ] 邊界情況測試

**檢查點：**
- ✅ 完整流程穩定運作
- ✅ 錯誤處理完善
- ✅ UI/UX 流暢

**Week 3 交付物：**
- ✅ AI 摘要功能
- ✅ AI 問答功能
- ✅ 優化的使用者體驗

---

## 5. Week 4：優化與整合（Day 22-28）

### 5.1 目標

完成進階功能，準備 Demo 展示。

### 5.2 詳細任務

#### Day 22-23：風險檢測（P2）

**後端**

- [ ] 建立風險檢測 Prompt
  ```typescript
  // src/prompts/risk_detection.ts
  ```

- [ ] 實作風險檢測邏輯
  ```typescript
  // src/lib/ai.service.ts
  - detectRisks(docType, extractedData)
  ```

- [ ] 整合至處理流程
  ```typescript
  processDocument() {
    ...
    5. detectRisks()        // 新增
    6. saveAIResult()
  }
  ```

**前端**

- [ ] 實作 RiskAlerts 元件
  ```typescript
  // components/result/RiskAlerts.tsx
  ```

**檢查點：**
- ✅ 風險檢測可運作
- ✅ 前端顯示美觀

---

#### Day 24-25：一鍵建檔功能（P2）

**後端**

- [ ] 實作建檔 API
  ```typescript
  POST /api/documents/:id/create-record
  ```

- [ ] 實作建檔邏輯
  ```typescript
  // src/services/record.service.ts
  - createLeaseRecord()
  - createRepairQuoteRecord()
  - createTenantRecord()
  ```

- [ ] 實作記錄查詢 API
  ```typescript
  GET /api/records/:id
  ```

**前端**

- [ ] 加入建檔按鈕
  ```typescript
  // app/documents/[id]/page.tsx
  <Button onClick={handleCreateRecord}>
    建立系統記錄
  </Button>
  ```

- [ ] 實作記錄詳情頁
  ```typescript
  // app/records/[id]/page.tsx
  ```

**檢查點：**
- ✅ 可成功建立記錄
- ✅ 記錄可查詢

---

#### Day 26：Demo 準備

**測試文件準備**

- [ ] 準備 Demo 文件各 3 份
  - 租賃合約 x 3
  - 報價單 x 3
  - 身分證 x 3（脫敏）

- [ ] 測試所有流程
- [ ] 記錄測試結果

**Demo 腳本**

- [ ] 編寫 Demo 腳本（參考 MVP 文檔）
- [ ] 練習演示流程
- [ ] 準備備用方案（離線 Demo）

**環境部署**

- [ ] 使用 Docker Compose 部署
  ```bash
  # 設定環境變數
  cp .env.docker.example .env
  # 編輯 .env 填入 API Keys

  # 啟動所有服務
  make init
  # 或手動啟動
  docker-compose up -d
  ```

- [ ] 或分別部署前後端
  - **前端**: 部署至 Vercel/Netlify
    ```bash
    cd frontend
    npm run build
    # 部署 dist 目錄
    ```

  - **後端**: 部署至 Railway/Render
    ```bash
    # 確保有 requirements.txt 和 Procfile
    # Railway 會自動偵測並部署
    ```

- [ ] 設定環境變數
- [ ] 測試正式環境

**檢查點：**
- ✅ 正式環境可訪問
- ✅ Demo 文件準備完成
- ✅ 演示流程熟練

---

#### Day 27-28：最終優化與測試

**最終檢查**

- [ ] 功能檢查清單
  - [ ] 上傳功能
  - [ ] OCR 處理
  - [ ] AI 分類
  - [ ] 欄位抽取
  - [ ] 摘要生成
  - [ ] 問答功能
  - [ ] 風險檢測（P2）
  - [ ] 建檔功能（P2）

- [ ] UI/UX 檢查
  - [ ] 響應式設計
  - [ ] 載入狀態
  - [ ] 錯誤提示
  - [ ] 成功訊息

- [ ] 效能檢查
  - [ ] 上傳速度
  - [ ] 處理速度
  - [ ] 頁面載入速度

**文件整理**

- [ ] 更新 README.md
- [ ] 編寫部署文檔
- [ ] 編寫 API 文檔

**Demo 彩排**

- [ ] 完整演示 1-2 次
- [ ] 記錄問題並修正
- [ ] 準備應答腳本

**檢查點：**
- ✅ 所有功能正常運作
- ✅ Demo 準備完成
- ✅ 文件齊全

**Week 4 交付物：**
- ✅ 完整的 MVP 產品
- ✅ 部署至正式環境
- ✅ Demo 展示準備完成

---

## 6. 風險管理

### 6.1 高風險項目

| 風險 | 影響 | 機率 | 緩解方案 |
|------|------|------|---------|
| OCR 準確率不足 | 高 | 中 | 準備 2 種 OCR 方案，測試後選最佳 |
| AI 抽取準確率低 | 高 | 中 | 持續優化 Prompt，準備人工修正機制 |
| 開發時間不足 | 中 | 中 | 優先完成 P0 功能，P2 可後補 |
| API 成本超支 | 低 | 低 | 監控用量，設定預算告警 |
| 部署環境問題 | 中 | 低 | 提前 1 週部署測試環境 |

### 6.2 應對策略

**時間不足：**
1. Week 3 結束時評估進度
2. 如進度落後，砍掉 P2 功能
3. 確保 P0 + P1 穩定運作

**準確率不足：**
1. 準備 Few-shot 範例
2. 提供人工修正介面
3. Demo 時選擇準確率高的文件

---

## 7. 每日檢查清單

### 7.1 每日站會（15 分鐘）

- 昨天完成了什麼？
- 今天計劃做什麼？
- 有什麼阻礙？

### 7.2 每日下班前

- [ ] 提交程式碼至 Git
- [ ] 更新進度至專案看板
- [ ] 記錄遇到的問題

### 7.3 每週五

- [ ] 週報總結
- [ ] Demo 功能給團隊
- [ ] 下週計劃確認

---

## 8. 開發工具與環境

### 8.1 必備工具

- **IDE**: VS Code (推薦安裝 Python、Vue 擴展)
- **API 測試**: Postman / Insomnia / FastAPI Swagger UI
- **資料庫工具**: pgAdmin / TablePlus / DBeaver
- **版本控制**: Git + GitHub
- **專案管理**: GitHub Projects / Notion
- **容器化**: Docker + Docker Compose

### 8.2 開發環境設定

```bash
# 安裝 Python 3.11+
python --version  # 確認版本 >= 3.11

# 安裝 Node.js 18+ (前端)
nvm install 18
nvm use 18

# 安裝 Docker（推薦）
brew install docker  # macOS
# 或下載 Docker Desktop

# 使用 Docker 啟動所有服務
make init

# 或本地開發（不使用 Docker）
# 後端
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload

# 前端
cd frontend
npm install
npm run dev
```

### 8.3 環境變數範例

```bash
# backend/.env（本地開發）
DATABASE_URL="postgresql://postgres:postgres@localhost:5432/ai_doc_demo"
S3_BUCKET="ai-doc-demo-uploads"
S3_REGION="us-east-1"
S3_ACCESS_KEY="..."
S3_SECRET_KEY="..."
S3_ENDPOINT_URL=""  # Cloudflare R2
OPENAI_API_KEY="sk-..."
OPENAI_MODEL="gpt-4o"
OPENAI_MODEL_MINI="gpt-4o-mini"
OCR_SERVICE="pytesseract"  # or "textract"
PORT=8000

# frontend/.env（本地開發）
VITE_API_URL=http://localhost:8000
VITE_APP_TITLE=AI Document Intelligence

# Docker 環境變數請參考 .env.docker.example
```

---

## 9. Git 工作流程

### 9.1 分支策略

```
main          # 正式環境
  └── develop # 開發環境
       ├── feature/upload
       ├── feature/ocr
       ├── feature/ai-classification
       └── feature/ai-extraction
```

### 9.2 Commit 規範

```
feat: 新增功能
fix: 修復 Bug
docs: 文件更新
style: 程式碼格式
refactor: 重構
test: 測試
chore: 建置工具或輔助工具變動
```

---

## 10. 成功標準

### 10.1 MVP 成功定義

- [ ] 可上傳 3 類文件
- [ ] AI 分類準確率 > 85%
- [ ] 欄位抽取可用率 > 75%
- [ ] AI 問答可回答 3 個問題
- [ ] 完整 Demo 流程 < 10 分鐘
- [ ] 正式環境穩定運作

### 10.2 Demo 成功標準

- [ ] 評審可成功上傳文件
- [ ] AI 處理結果正確
- [ ] UI/UX 流暢美觀
- [ ] 無明顯 Bug
- [ ] 回答問題清楚

---

**文檔版本**: v1.0
**最後更新**: 2026-03-17
**專案經理**: Implementation Team

**下一步行動**: 閱讀技術棧選型文檔，然後開始 Day 1 任務！
