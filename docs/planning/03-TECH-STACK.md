# AI Document Intelligence Demo - 技術棧選型文檔

## 1. 技術選型總覽

### 1.1 完整技術棧

```
前端層
├── Framework: Next.js 14 (App Router)
├── Language: TypeScript 5+
├── UI Library: React 18
├── Styling: Tailwind CSS 3
├── Components: shadcn/ui
├── State: React Query / SWR
├── HTTP Client: Axios
└── Deployment: Vercel

後端層
├── Runtime: Python 3.11+
├── Framework: FastAPI
├── Language: Python
├── ORM: SQLAlchemy 2.0
├── Migration: Alembic
├── Database: PostgreSQL 14+
├── File Upload: python-multipart
├── Storage: AWS S3 / Cloudflare R2
├── ASGI Server: Uvicorn
└── Deployment: Railway / Render

AI 服務層
├── LLM: OpenAI GPT-4 / Anthropic Claude
├── OCR: AWS Textract / pytesseract
├── PDF Processing: PyPDF2 / pdfplumber
└── Vector DB: (未來擴展)

基礎設施
├── Database: PostgreSQL (Railway/Render 託管)
├── Storage: S3 / Cloudflare R2
├── CDN: Vercel Edge Network
└── Monitoring: Sentry (可選)
```

---

## 2. 前端技術選型

### 2.1 Next.js 14（App Router）

**選擇理由：**

✅ **優點**
- React 官方推薦的全棧框架
- App Router 提供更好的 DX
- 內建 API Routes（可選用）
- 自動程式碼分割
- 圖片優化（next/image）
- Vercel 一鍵部署
- TypeScript 原生支援

**替代方案對比：**

| 方案 | 優點 | 缺點 | 評分 |
|------|------|------|------|
| **Next.js** | 全棧、SEO、快速開發 | 學習曲線稍陡 | ⭐⭐⭐⭐⭐ |
| Vite + React | 極快的開發體驗 | 需自行配置路由 | ⭐⭐⭐⭐ |
| Create React App | 簡單易用 | 已不再維護 | ⭐⭐⭐ |

**安裝指令：**
```bash
npx create-next-app@latest frontend \
  --typescript \
  --tailwind \
  --app \
  --src-dir \
  --import-alias "@/*"
```

---

### 2.2 Tailwind CSS

**選擇理由：**

✅ **優點**
- Utility-first，開發速度快
- 與 Next.js 整合良好
- 響應式設計簡單
- 打包後 CSS 體積小
- shadcn/ui 基於 Tailwind

**替代方案對比：**

| 方案 | 優點 | 缺點 | 評分 |
|------|------|------|------|
| **Tailwind CSS** | 快速、靈活、現代 | 類名較長 | ⭐⭐⭐⭐⭐ |
| CSS Modules | 作用域隔離 | 開發速度慢 | ⭐⭐⭐ |
| Styled Components | CSS-in-JS | 效能開銷 | ⭐⭐⭐ |

**配置範例：**
```js
// tailwind.config.js
module.exports = {
  content: [
    './src/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        primary: '#3b82f6',
      },
    },
  },
  plugins: [require('@tailwindcss/forms')],
};
```

---

### 2.3 shadcn/ui

**選擇理由：**

✅ **優點**
- 高品質 React 元件
- 基於 Radix UI（無障礙友好）
- 程式碼可完全客製化（非 npm 套件）
- 與 Tailwind 完美整合
- TypeScript 原生支援

**安裝指令：**
```bash
npx shadcn-ui@latest init
npx shadcn-ui@latest add button card input badge dialog
```

**替代方案對比：**

| 方案 | 優點 | 缺點 | 評分 |
|------|------|------|------|
| **shadcn/ui** | 客製化、現代、免費 | 需手動安裝元件 | ⭐⭐⭐⭐⭐ |
| Material-UI | 元件豐富 | 打包體積大 | ⭐⭐⭐⭐ |
| Ant Design | 企業級 | 設計風格固定 | ⭐⭐⭐⭐ |
| Chakra UI | 簡單易用 | 客製化較難 | ⭐⭐⭐⭐ |

---

### 2.4 React Query / SWR

**選擇理由：**

✅ **優點**
- 自動快取管理
- 背景自動重新獲取
- 樂觀更新
- 輪詢支援（處理狀態輪詢）
- TypeScript 支援佳

**推薦：React Query（TanStack Query）**

**安裝指令：**
```bash
npm install @tanstack/react-query
```

**使用範例：**
```tsx
const { data, isLoading } = useQuery({
  queryKey: ['document', documentId],
  queryFn: () => getDocument(documentId),
  refetchInterval: (data) => {
    return data?.status === 'processing' ? 2000 : false;
  },
});
```

**替代方案對比：**

| 方案 | 優點 | 缺點 | 評分 |
|------|------|------|------|
| **React Query** | 功能強大、社群大 | 稍複雜 | ⭐⭐⭐⭐⭐ |
| SWR | 輕量、簡單 | 功能較少 | ⭐⭐⭐⭐ |
| Redux Toolkit | 狀態管理全面 | 過度設計（本專案） | ⭐⭐⭐ |

---

## 3. 後端技術選型

### 3.1 Python + FastAPI

**選擇理由：**

✅ **優點**
- AI/ML 生態系統最強大（OpenAI、LangChain、pytesseract）
- FastAPI 效能優異（基於 Starlette + Pydantic）
- 自動生成 OpenAPI/Swagger 文檔
- 原生 async/await 支援
- 類型提示（Type Hints）提供良好開發體驗
- PDF/圖片處理工具豐富
- 部署簡單（Uvicorn + Docker）

**替代方案對比：**

| 方案 | 優點 | 缺點 | 評分 |
|------|------|------|------|
| **FastAPI** | AI生態、效能佳、現代化 | 前後端語言不統一 | ⭐⭐⭐⭐⭐ |
| Django + DRF | 功能完整、管理後台 | 較重量級 | ⭐⭐⭐⭐ |
| Flask | 輕量、靈活 | 需手動配置多 | ⭐⭐⭐ |
| Node.js + Express | JS 全棧 | AI 生態較弱 | ⭐⭐⭐⭐ |

**專案結構：**
```
backend/
├── app/
│   ├── main.py              # FastAPI 入口
│   ├── config.py            # 配置管理
│   ├── database.py          # 資料庫連接
│   ├── models/              # SQLAlchemy Models
│   │   ├── __init__.py
│   │   ├── document.py
│   │   └── ai_result.py
│   ├── schemas/             # Pydantic Schemas
│   │   ├── __init__.py
│   │   ├── document.py
│   │   └── ai_result.py
│   ├── api/                 # API 路由
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── documents.py
│   │       └── chat.py
│   ├── services/            # 業務邏輯
│   │   ├── __init__.py
│   │   ├── document_processor.py
│   │   ├── upload.py
│   │   └── chat.py
│   ├── lib/                 # 第三方整合
│   │   ├── __init__.py
│   │   ├── ai_service.py
│   │   ├── ocr_service.py
│   │   └── s3_service.py
│   └── prompts/             # AI Prompts
│       ├── __init__.py
│       ├── classification.py
│       └── extraction.py
├── alembic/                 # 資料庫遷移
│   └── versions/
├── alembic.ini
├── requirements.txt
└── pyproject.toml
```

---

### 3.2 SQLAlchemy + Alembic

**選擇理由：**

✅ **優點**
- Python ORM 標準，生態成熟
- SQLAlchemy 2.0 支援 async
- 類型提示良好（配合 Pydantic）
- 強大的查詢 API
- Alembic 自動生成 migration
- 支援複雜關聯與 JSONB

**安裝指令：**
```bash
pip install sqlalchemy alembic asyncpg psycopg2-binary
alembic init alembic
```

**Model 範例：**
```python
from sqlalchemy import Column, String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base
import uuid

class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_name = Column(String, nullable=False)
    file_url = Column(String, nullable=False)
    status = Column(String, default="uploaded")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

**替代方案對比：**

| 方案 | 優點 | 缺點 | 評分 |
|------|------|------|------|
| **SQLAlchemy** | 成熟、功能強、async | 學習曲線稍陡 | ⭐⭐⭐⭐⭐ |
| Tortoise ORM | 類似 Django ORM | 社群較小 | ⭐⭐⭐⭐ |
| Peewee | 輕量、簡單 | 功能較少 | ⭐⭐⭐ |
| Django ORM | 易用、成熟 | 綁定 Django | ⭐⭐⭐⭐ |

---

### 3.3 PostgreSQL

**選擇理由：**

✅ **優點**
- 開源、成熟、穩定
- 支援 JSONB（適合儲存 AI 結果）
- GIN 索引加速 JSON 查詢
- Railway/Render 免費提供
- 與 Prisma 整合良好

**替代方案對比：**

| 方案 | 優點 | 缺點 | 評分 |
|------|------|------|------|
| **PostgreSQL** | 功能強大、JSONB 支援 | 稍複雜 | ⭐⭐⭐⭐⭐ |
| MySQL | 簡單、流行 | JSON 支援較弱 | ⭐⭐⭐⭐ |
| MongoDB | NoSQL、彈性 | 無 schema 易亂 | ⭐⭐⭐ |
| SQLite | 零配置 | 不適合生產環境 | ⭐⭐ |

---

## 4. AI 服務選型

### 4.1 LLM 模型選擇

#### **推薦方案：OpenAI GPT-4o**

✅ **優點**
- 繁體中文理解能力強
- JSON mode（強制 JSON 輸出）
- API 穩定、文檔完整
- 社群支援好
- 價格合理

**定價（2026-03）：**
- GPT-4o: $5 / 1M input tokens
- GPT-4o-mini: $0.15 / 1M input tokens

**使用建議：**
- 文件分類：GPT-4o-mini
- 欄位抽取：GPT-4o
- 摘要生成：GPT-4o-mini
- 問答對話：GPT-4o

**安裝指令：**
```bash
npm install openai
```

**使用範例：**
```typescript
import OpenAI from 'openai';

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

const response = await openai.chat.completions.create({
  model: 'gpt-4o',
  messages: [{ role: 'user', content: prompt }],
  temperature: 0,
  response_format: { type: 'json_object' },
});
```

---

#### **備用方案：Anthropic Claude 3.5 Sonnet**

✅ **優點**
- 長文本處理能力強（200K context）
- 指令遵循能力極佳
- 安全性高（較少幻覺）

❌ **缺點**
- 繁體中文支援稍弱於 GPT-4
- 價格較高

**定價：**
- Claude 3.5 Sonnet: $3 / 1M input tokens
- Claude 3.5 Haiku: $1 / 1M input tokens

**安裝指令：**
```bash
npm install @anthropic-ai/sdk
```

---

**對比總結：**

| 模型 | 繁中支援 | 價格 | 速度 | 推薦度 |
|------|----------|------|------|--------|
| **GPT-4o** | ⭐⭐⭐⭐⭐ | 中 | 快 | ⭐⭐⭐⭐⭐ |
| GPT-4o-mini | ⭐⭐⭐⭐ | 低 | 極快 | ⭐⭐⭐⭐⭐ |
| Claude 3.5 Sonnet | ⭐⭐⭐⭐ | 中 | 中 | ⭐⭐⭐⭐ |
| Claude 3.5 Haiku | ⭐⭐⭐⭐ | 低 | 快 | ⭐⭐⭐⭐ |

**最終建議：OpenAI GPT-4o 系列**

---

### 4.2 OCR 服務選擇

#### **推薦方案：AWS Textract**

✅ **優點**
- 準確率高（尤其繁體中文）
- 支援表格、表單辨識
- 可辨識手寫字
- 按用量計費，無最低消費

**定價：**
- 每頁（單頁 PDF/圖片）: $0.0015

**安裝指令：**
```bash
pip install boto3
```

**使用範例：**
```python
import boto3

client = boto3.client('textract', region_name='us-east-1')

response = client.detect_document_text(
    Document={'Bytes': file_bytes}
)

# 提取文字
text_lines = []
for block in response['Blocks']:
    if block['BlockType'] == 'LINE':
        text_lines.append(block['Text'])

text = '\n'.join(text_lines)
```

---

#### **備用方案：pytesseract（開源免費）**

✅ **優點**
- 完全免費
- 可離線運作
- 支援繁體中文
- Python 原生整合良好

❌ **缺點**
- 準確率略低於商用方案
- 需安裝 Tesseract OCR 引擎

**安裝指令：**
```bash
# 安裝 Tesseract 引擎
# macOS
brew install tesseract tesseract-lang

# Ubuntu
sudo apt-get install tesseract-ocr tesseract-ocr-chi-tra

# Python 套件
pip install pytesseract pillow pdf2image
```

**使用範例：**
```python
import pytesseract
from PIL import Image

# 開啟圖片
image = Image.open("document.jpg")

# OCR 辨識（繁體中文）
text = pytesseract.image_to_string(image, lang='chi_tra')
print(text)
```

---

**對比總結：**

| OCR 服務 | 準確率 | 價格 | 速度 | 推薦度 |
|----------|--------|------|------|--------|
| **AWS Textract** | ⭐⭐⭐⭐⭐ | 低 | 快 | ⭐⭐⭐⭐⭐ |
| Google Document AI | ⭐⭐⭐⭐⭐ | 中 | 快 | ⭐⭐⭐⭐ |
| Azure Document Intelligence | ⭐⭐⭐⭐ | 中 | 中 | ⭐⭐⭐⭐ |
| pytesseract | ⭐⭐⭐ | 免費 | 中 | ⭐⭐⭐⭐ |

**最終建議：AWS Textract（正式）+ pytesseract（開發測試）**

---

## 5. 檔案儲存選型

### 5.1 Cloudflare R2（推薦）

✅ **優點**
- **零出站費用**（S3 最大痛點）
- S3 相容 API（無縫切換）
- 免費額度：10GB 儲存 + 1M 請求/月
- 速度快（Cloudflare CDN）

**定價：**
- 儲存：$0.015/GB/月
- 上傳：免費
- 下載：**免費**（關鍵！）

**設定範例：**
```python
import boto3
from botocore.config import Config

s3_client = boto3.client(
    's3',
    endpoint_url=f'https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com',
    aws_access_key_id=R2_ACCESS_KEY,
    aws_secret_access_key=R2_SECRET_KEY,
    config=Config(signature_version='s3v4'),
    region_name='auto'
)

# 上傳檔案
s3_client.upload_fileobj(
    file_object,
    'bucket-name',
    'file-key.pdf'
)
```

---

### 5.2 AWS S3（備用）

✅ **優點**
- 成熟穩定
- 整合生態完整
- Textract 同一帳號免費傳輸

❌ **缺點**
- 出站流量費用高
- 設定較複雜

**定價：**
- 儲存：$0.023/GB/月
- 請求：$0.0004/1000 次
- 出站流量：$0.09/GB（痛點！）

---

**對比總結：**

| 儲存方案 | 儲存成本 | 下載成本 | 速度 | 推薦度 |
|----------|----------|----------|------|--------|
| **Cloudflare R2** | 低 | 免費 | 快 | ⭐⭐⭐⭐⭐ |
| AWS S3 | 低 | 高 | 快 | ⭐⭐⭐⭐ |
| Google Cloud Storage | 中 | 中 | 快 | ⭐⭐⭐ |

**最終建議：Cloudflare R2**

---

## 6. 部署方案

### 6.1 前端部署：Vercel

✅ **優點**
- Next.js 官方推薦
- 零配置部署
- 自動 HTTPS
- 全球 CDN
- 免費額度充足

**免費額度：**
- 100GB 流量/月
- 無限專案
- 自動 CI/CD

**部署指令：**
```bash
cd frontend
vercel --prod
```

---

### 6.2 後端部署：Railway

✅ **優點**
- 支援 Python 3.11+
- 內建 PostgreSQL
- 簡單易用
- 免費 $5/月額度
- 自動偵測 requirements.txt

**免費額度：**
- $5 credit/月
- 512MB RAM
- 1GB Storage

**部署指令：**
```bash
cd backend
# 確保有 requirements.txt 和 Procfile
railway up

# 或透過 GitHub 自動部署
# Railway 會自動偵測 Python 專案
```

**Procfile 範例：**
```
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

---

#### **備用方案：Render**

✅ **優點**
- 完全免費方案
- 支援 PostgreSQL
- 自動部署

❌ **缺點**
- 閒置後冷啟動慢（30 秒）

**免費額度：**
- 750 小時/月
- 512MB RAM
- PostgreSQL 1GB

---

**對比總結：**

| 部署方案 | 價格 | 效能 | 易用性 | 推薦度 |
|----------|------|------|--------|--------|
| **Vercel (前端)** | 免費 | 極快 | 極易 | ⭐⭐⭐⭐⭐ |
| **Railway (後端)** | $5/月 | 快 | 易 | ⭐⭐⭐⭐⭐ |
| Render (後端) | 免費 | 中 | 易 | ⭐⭐⭐⭐ |

---

## 7. 開發工具

### 7.1 必備工具

| 工具 | 用途 | 推薦度 |
|------|------|--------|
| **VS Code** | IDE | ⭐⭐⭐⭐⭐ |
| **Postman** | API 測試 | ⭐⭐⭐⭐⭐ |
| **Prisma Studio** | 資料庫 GUI | ⭐⭐⭐⭐⭐ |
| **Git** | 版本控制 | ⭐⭐⭐⭐⭐ |
| **Docker** | 本地資料庫 | ⭐⭐⭐⭐ |
| **pnpm** | 套件管理（可選） | ⭐⭐⭐⭐ |

### 7.2 VS Code 擴充套件

```json
{
  "recommendations": [
    "dbaeumer.vscode-eslint",
    "esbenp.prettier-vscode",
    "prisma.prisma",
    "bradlc.vscode-tailwindcss",
    "ms-vscode.vscode-typescript-next"
  ]
}
```

---

## 8. 成本估算（MVP 階段）

### 8.1 每月預估成本

| 項目 | 用量 | 成本 |
|------|------|------|
| **Vercel** (前端) | 免費額度內 | $0 |
| **Railway** (後端 + DB) | 免費 $5 credit | $0 |
| **Cloudflare R2** | 10GB 儲存 + 1M 請求 | $0 |
| **AWS Textract** | 500 頁/月 | $0.75 |
| **OpenAI API** | 2M tokens/月 | $10 |
| **總計** | - | **~$10.75/月** |

**注意：** 正式環境成本會隨使用量增長。

---

## 9. 技術選型決策矩陣

### 9.1 評分標準

- **開發速度**：4 週時限，速度優先
- **成本**：MVP 預算有限
- **繁中支援**：台灣市場
- **生態成熟度**：降低風險
- **可擴展性**：未來成長空間

### 9.2 最終選型總表

| 層次 | 選型 | 評分 | 關鍵理由 |
|------|------|------|----------|
| 前端框架 | Next.js 14 | ⭐⭐⭐⭐⭐ | 全棧、快速、Vercel 部署 |
| UI 框架 | Tailwind + shadcn/ui | ⭐⭐⭐⭐⭐ | 開發速度極快 |
| 後端框架 | Python + FastAPI | ⭐⭐⭐⭐⭐ | AI 生態最強、現代化 |
| ORM | SQLAlchemy | ⭐⭐⭐⭐⭐ | Python 標準、功能強 |
| 資料庫 | PostgreSQL | ⭐⭐⭐⭐⭐ | JSONB 支援、成熟 |
| AI 模型 | OpenAI GPT-4o | ⭐⭐⭐⭐⭐ | 繁中支援最佳 |
| OCR | AWS Textract | ⭐⭐⭐⭐⭐ | 準確率高、價格合理 |
| 檔案儲存 | Cloudflare R2 | ⭐⭐⭐⭐⭐ | 零出站費用 |
| 部署 | Vercel + Railway | ⭐⭐⭐⭐⭐ | 免費、簡單 |

---

## 10. 技術風險評估

| 風險 | 機率 | 影響 | 緩解策略 |
|------|------|------|----------|
| OpenAI API 超支 | 低 | 中 | 設定用量告警、成本上限 |
| Textract 中文辨識不佳 | 低 | 高 | 準備 Tesseract.js 備案 |
| 免費額度不足 | 低 | 低 | 隨時可升級付費方案 |
| Railway 效能不足 | 低 | 中 | 可遷移至 Render/AWS |

---

## 11. 下一步行動

- [ ] 閱讀完所有技術文檔
- [ ] 確認 API Keys 已申請：
  - [ ] OpenAI API Key
  - [ ] AWS 帳號（Textract + S3）
  - [ ] Cloudflare 帳號（R2）
- [ ] 本地環境設定完成
- [ ] 開始 Week 1 Day 1 開發！

---

**文檔版本**: v1.0
**最後更新**: 2026-03-17
**負責人**: Tech Lead

**準備好了嗎？讓我們開始打造 AI 文件智能處理系統吧！🚀**
