# DocuMind 技術文件總覽

> 只列現行文件。2026-03 的 MVP 規劃稿（租約／報價單／身分證、Next.js、Railway）已於 2026-10-15 刪除，要追溯請看 git 歷史。

## 📋 文件導航

### 0. 租管問答平台（平台層規格）

> 建立在 JGB 既有資料之上的問答平台。**DocuMind 是它未來的一塊配件**，
> 以下規格不涵蓋 DocuMind 本身。

| 文件 | 說明 | 狀態 |
|------|------|------|
| [platform/README.md](./platform/README.md) | 平台規格總覽、前提與作廢條件 | ✅ 現行 |
| [platform/01-DATA-INVENTORY.md](./platform/01-DATA-INVENTORY.md) | 資料源實查清冊：12 能用 / 2 已建表未啟用 / 11 不能信 / 13 不存在 | ✅ 現行 v2.0 |
| [platform/02-V1-SCOPE.md](./platform/02-V1-SCOPE.md) | 第一版範圍、五條硬約束、**三件待拍板** | ✅ 現行 v2.0 |
| [platform/03-FUNCTIONAL-SPEC.md](./platform/03-FUNCTIONAL-SPEC.md) | F1–F10 逐項功能規格（F6 暫停） | ✅ 現行 v2.0 |
| [platform/04-REFUSAL-SPEC.md](./platform/04-REFUSAL-SPEC.md) | 四種回應狀態、拒答規格與 36 題測試集 | ✅ 現行 v2.0 |
| [platform/05-PREREQUISITES-AND-ACCEPTANCE.md](./platform/05-PREREQUISITES-AND-ACCEPTANCE.md) | 三項 P0 前置、非功能需求、驗收標準、下線程序 | ✅ 現行 v2.0 |

---

### 1. 對外串接

| 文件 | 說明 |
|------|------|
| [api/INTEGRATION.md](./api/INTEGRATION.md) | **對外串接規格**：端點、欄位、錯誤碼、實測速度與準確率 |
| [api/transcript_records.schema.json](./api/transcript_records.schema.json) | 謄本固定輸出格式 `transcript_records` 的 JSON Schema（INTEGRATION §3.1.3） |

### 2. 謄本

| 文件 | 說明 |
|------|------|
| [planning/transcript-status.md](./planning/transcript-status.md) | 謄本解析現況、決策紀錄、待辦與待決 |
| [testing/transcript-online-acceptance.md](./testing/transcript-online-acceptance.md) | 謄本驗收範本、跑法、線上實測結果、已知限制 |

各版的計畫與驗收清單在 `.kiro/specs/transcript-*/acceptance.md`。

### 3. 技術與部署

| 文件 | 說明 |
|------|------|
| [planning/03-TECH-STACK.md](./planning/03-TECH-STACK.md) | 技術棧現況：前後端、LLM 模型分工、OCR 路徑 |
| [DEPLOYMENT.md](./DEPLOYMENT.md) | 部署指南與建議規格；§0.5 為線上機實況 |
| [DEV_WORKFLOW.md](./DEV_WORKFLOW.md) | 本機與線上的分工（PaddleOCR 本機跑不起來） |
| [ANNOTATION_GUIDE.md](./ANNOTATION_GUIDE.md) | 標註資料存放與版控規範 |
| [frontend/01-FRONTEND-DESIGN.md](./frontend/01-FRONTEND-DESIGN.md) | 前端（Vue 3 + Vite）頁面與元件 |

### 4. 對外說明

| 文件 | 說明 |
|------|------|
| [OCR_FLOW_FOR_MARKETING.md](./OCR_FLOW_FOR_MARKETING.md) | 行銷、業務用的辨識流程說明；PDF 版由 [tools/](./tools/README.md) 產生 |

設計意圖以 `.kiro/specs/<feature>/` 的 design.md、research.md 為準；程式碼只代表目前做到哪。
