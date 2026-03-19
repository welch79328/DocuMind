# AI Document Intelligence Demo - 技術文件總覽

## 📋 文件導航

### 1. 規劃文件 (Planning)

| 文件 | 說明 | 狀態 |
|------|------|------|
| [01-MVP-SCOPE.md](./planning/01-MVP-SCOPE.md) | MVP 範圍定義、功能優先級、成功標準 | ✅ 完成 |
| [02-IMPLEMENTATION-PLAN.md](./planning/02-IMPLEMENTATION-PLAN.md) | 4 週詳細開發計劃、每日任務清單 | ✅ 完成 |
| [03-TECH-STACK.md](./planning/03-TECH-STACK.md) | 技術棧選型、成本估算、風險評估 | ✅ 完成 |

### 2. 系統架構 (Architecture)

| 文件 | 說明 | 狀態 |
|------|------|------|
| [01-SYSTEM-ARCHITECTURE.md](./architecture/01-SYSTEM-ARCHITECTURE.md) | 系統架構圖、核心流程、資料流設計 | ✅ 完成 |

### 3. 資料庫設計 (Database)

| 文件 | 說明 | 狀態 |
|------|------|------|
| [01-DATABASE-DESIGN.md](./database/01-DATABASE-DESIGN.md) | 資料表結構、Prisma Schema、查詢範例 | ✅ 完成 |

### 4. API 規格 (API)

| 文件 | 說明 | 狀態 |
|------|------|------|
| [01-API-SPECIFICATION.md](./api/01-API-SPECIFICATION.md) | REST API 端點、請求/回應格式、錯誤處理 | ✅ 完成 |

### 5. 前端設計 (Frontend)

| 文件 | 說明 | 狀態 |
|------|------|------|
| [01-FRONTEND-DESIGN.md](./frontend/01-FRONTEND-DESIGN.md) | 頁面設計、元件規格、UI/UX 流程 | ✅ 完成 |

### 6. AI 設計 (AI)

| 文件 | 說明 | 狀態 |
|------|------|------|
| [01-AI-PROMPT-DESIGN.md](./ai/01-AI-PROMPT-DESIGN.md) | AI Prompt 模板、模型選擇、優化技巧 | ✅ 完成 |

---

## 🚀 快速開始

### 推薦閱讀順序

如果你是第一次閱讀這些文件，建議按以下順序：

1. **[MVP 範圍定義](./planning/01-MVP-SCOPE.md)** - 了解要做什麼
2. **[系統架構設計](./architecture/01-SYSTEM-ARCHITECTURE.md)** - 了解怎麼做
3. **[技術棧選型](./planning/03-TECH-STACK.md)** - 了解用什麼做
4. **[開發實施計劃](./planning/02-IMPLEMENTATION-PLAN.md)** - 了解何時做
5. **[資料庫設計](./database/01-DATABASE-DESIGN.md)** - 資料結構
6. **[API 規格](./api/01-API-SPECIFICATION.md)** - 接口設計
7. **[前端設計](./frontend/01-FRONTEND-DESIGN.md)** - UI 實作
8. **[AI Prompt 設計](./ai/01-AI-PROMPT-DESIGN.md)** - AI 核心邏輯

---

## 📊 專案概覽

### 核心功能

✅ **文件上傳** - 支援 PDF/JPG/PNG，最大 10MB
✅ **OCR 處理** - AWS Textract 文字辨識
✅ **AI 分類** - 自動識別 3 類文件（租約/報價單/身分證）
✅ **欄位抽取** - AI 自動抽取關鍵欄位
✅ **AI 摘要** - 生成 3-5 行文件摘要
✅ **AI 問答** - 針對文件內容問答
⏳ **風險檢測** - 識別缺失欄位與異常值（P2）
⏳ **一鍵建檔** - 建立系統記錄（P2）

### 技術棧

**前端：**
- Next.js 14 (App Router)
- TypeScript
- Tailwind CSS
- shadcn/ui
- React Query

**後端：**
- Node.js + Express
- TypeScript
- Prisma ORM
- PostgreSQL

**AI 服務：**
- OpenAI GPT-4o / GPT-4o-mini
- AWS Textract

**基礎設施：**
- Cloudflare R2（檔案儲存）
- Vercel（前端部署）
- Railway（後端部署）

### 時程規劃

**總時長：4 週**

- **Week 1**：基礎建設（上傳、儲存、OCR）
- **Week 2**：AI 核心（分類、抽取、結果頁）
- **Week 3**：AI 增強（摘要、問答）
- **Week 4**：優化整合（風險、建檔、Demo）

---

## 📁 專案結構

```
ai-doc-demo/
├── frontend/                 # Next.js 前端專案
│   ├── src/
│   │   ├── app/             # App Router 頁面
│   │   ├── components/      # React 元件
│   │   ├── lib/             # 工具函式
│   │   └── types/           # TypeScript 型別
│   └── package.json
│
├── backend/                  # Node.js 後端專案
│   ├── src/
│   │   ├── routes/          # API 路由
│   │   ├── services/        # 業務邏輯
│   │   ├── lib/             # 第三方整合（AI、OCR、S3）
│   │   ├── prompts/         # AI Prompts
│   │   └── middleware/      # 中介層
│   ├── prisma/
│   │   └── schema.prisma    # 資料庫 Schema
│   └── package.json
│
└── docs/                     # 技術文件（本目錄）
    ├── README.md            # 總覽（本文件）
    ├── planning/            # 規劃文件
    ├── architecture/        # 架構設計
    ├── database/            # 資料庫設計
    ├── api/                 # API 規格
    ├── frontend/            # 前端設計
    └── ai/                  # AI 設計
```

---

## 🎯 MVP 成功標準

### 功能指標

- [ ] 可上傳 3 類文件（租約、報價單、身分證）
- [ ] AI 分類準確率 > 85%
- [ ] 欄位抽取可用率 > 75%
- [ ] AI 問答可回答基本問題
- [ ] 完整 Demo 流程 < 10 分鐘

### 技術指標

- [ ] 文件上傳成功率 > 95%
- [ ] OCR 成功率 > 90%
- [ ] AI 響應時間 < 10 秒
- [ ] 單文件處理時間 < 30 秒

### Demo 展示指標

- [ ] 評審可成功上傳並處理文件
- [ ] AI 結果準確可用
- [ ] UI/UX 流暢美觀
- [ ] 無明顯 Bug

---

## 💡 關鍵特色

### 1. AI 核心能力

- **文件理解**：不只是 OCR，而是真正理解文件內容
- **結構化抽取**：將非結構化文件轉為可用資料
- **自然語言問答**：像人一樣理解並回答文件問題

### 2. 產品體驗

- **一鍵上傳**：拖拽即可，無需複雜操作
- **自動處理**：上傳後全自動完成分析
- **即時反饋**：處理狀態即時顯示
- **可編輯修正**：AI 結果可人工調整

### 3. 技術亮點

- **TypeScript 全棧**：前後端型別安全
- **AI 驅動**：OpenAI GPT-4 系列強大能力
- **現代架構**：Next.js 14 + Prisma + PostgreSQL
- **雲端原生**：一鍵部署至 Vercel + Railway

---

## 📝 開發檢查清單

### 開始前準備

- [ ] 閱讀所有技術文件
- [ ] 申請所需 API Keys：
  - [ ] OpenAI API Key
  - [ ] AWS 帳號（Textract + S3）
  - [ ] Cloudflare 帳號（R2）
- [ ] 設定本地開發環境
- [ ] 準備測試文件（3 類各 3 份）

### Week 1 檢查點

- [ ] 專案架構建立完成
- [ ] 檔案上傳功能正常
- [ ] OCR 處理可運作
- [ ] 資料庫可正常讀寫

### Week 2 檢查點

- [ ] AI 分類功能完成
- [ ] 欄位抽取準確率達標
- [ ] 結果頁面顯示正常
- [ ] 前後端整合完成

### Week 3 檢查點

- [ ] AI 摘要功能完成
- [ ] 問答功能可運作
- [ ] UI/UX 優化完成
- [ ] 整合測試通過

### Week 4 檢查點

- [ ] 風險檢測完成（P2）
- [ ] 建檔功能完成（P2）
- [ ] 部署至正式環境
- [ ] Demo 準備完成

---

## 🔧 常見問題

### Q1: 為什麼選擇 OpenAI 而不是其他 AI？

**A:** OpenAI GPT-4 系列對繁體中文支援最好，且有 JSON mode 可強制結構化輸出，最適合本專案需求。

### Q2: 為什麼用 PostgreSQL 而不是 MongoDB？

**A:** PostgreSQL 的 JSONB 功能兼具關聯式資料庫的穩定性與 NoSQL 的靈活性，最適合儲存 AI 抽取結果。

### Q3: 4 週能完成嗎？

**A:** 可以！我們已將功能分為 P0（必做）、P1（加分）、P2（亮點）三個優先級。即使時間不足，也能確保核心功能完成。

### Q4: 成本會很高嗎？

**A:** MVP 階段預估每月 $10-15 美元，主要是 OpenAI API 費用。Vercel、Railway、Cloudflare R2 都有免費額度。

### Q5: 如何確保 AI 準確率？

**A:**
1. 持續優化 Prompt
2. 準備 Few-shot 範例
3. 提供人工修正介面
4. Demo 時選擇測試良好的文件

---

## 📚 延伸閱讀

### 官方文檔

- [Next.js 文檔](https://nextjs.org/docs)
- [Prisma 文檔](https://www.prisma.io/docs)
- [OpenAI API 文檔](https://platform.openai.com/docs)
- [AWS Textract 文檔](https://docs.aws.amazon.com/textract/)
- [shadcn/ui 文檔](https://ui.shadcn.com/)

### 相關資源

- [Tailwind CSS 速查表](https://tailwindcomponents.com/cheatsheet/)
- [TypeScript 速查表](https://www.typescriptlang.org/cheatsheets)
- [React Query 教學](https://tanstack.com/query/latest/docs/react/overview)

---

## 📞 聯絡資訊

**專案負責人：** Development Team
**文檔版本：** v1.0
**最後更新：** 2026-03-17

---

## 🎉 準備好了嗎？

現在你已經擁有完整的技術文件！

**下一步：**
1. ✅ 詳細閱讀每份文件
2. ✅ 準備開發環境
3. ✅ 申請必要的 API Keys
4. ✅ 開始 Week 1 Day 1 的開發！

**讓我們一起打造這個 AI 文件智能處理系統吧！🚀**
