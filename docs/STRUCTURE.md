# 📂 文檔結構總覽

## 目錄樹

```
docs/
├── README.md                              # 📖 文檔導航（從這裡開始）
│
├── platform/                              # 🏢 租管問答平台規格（平台層，非 DocuMind）
│   ├── README.md                         # 平台規格總覽、前提與作廢條件
│   ├── 01-DATA-INVENTORY.md              # 資料源實查清冊 12/2/11/13
│   ├── 02-V1-SCOPE.md                    # 第一版範圍、五條硬約束、三件待拍板
│   ├── 03-FUNCTIONAL-SPEC.md             # F1–F10 功能規格（F6 暫停）
│   ├── 04-REFUSAL-SPEC.md                # 四種回應狀態、拒答規格與 36 題測試集
│   └── 05-PREREQUISITES-AND-ACCEPTANCE.md # 三項 P0 前置、非功能需求、驗收與下線程序
│
├── api/                                   # 🔌 對外串接
│   ├── INTEGRATION.md                    # 對外串接規格（端點、欄位、錯誤碼、實測數據）
│   └── transcript_records.schema.json    # 謄本固定輸出格式的 JSON Schema
│
├── planning/
│   ├── 03-TECH-STACK.md                  # 技術棧現況
│   └── transcript-status.md              # 謄本解析現況、決策、待辦
│
├── testing/
│   └── transcript-online-acceptance.md   # 謄本驗收範本、跑法、線上結果
│
├── frontend/
│   └── 01-FRONTEND-DESIGN.md             # 前端（Vue 3 + Vite）頁面與元件
│
├── tools/                                 # 行銷版 PDF 產生腳本
├── DEPLOYMENT.md                          # 部署指南；§0.5 線上機實況
├── DEV_WORKFLOW.md                        # 本機與線上的分工
├── ANNOTATION_GUIDE.md                    # 標註資料存放與版控規範
├── OCR_FLOW_FOR_MARKETING.md              # 行銷版辨識流程說明
└── OCR系統-圖片文字辨識流程說明.pdf        # 上一份的 PDF 版
```

---

## 📚 平台層規格閱讀順序（目前唯一在推進的規格）

| 順序 | 文件 | 說明 | 預估閱讀時間 |
|------|------|------|--------------|
| 1️⃣ | [platform/README.md](./platform/README.md) | 總覽、三條原則、現在卡在哪裡 | 8 分鐘 |
| 2️⃣ | [platform/01-DATA-INVENTORY.md](./platform/01-DATA-INVENTORY.md) | 資料源實查清冊（全部推導的起點） | 25 分鐘 |
| 3️⃣ | [platform/02-V1-SCOPE.md](./platform/02-V1-SCOPE.md) | 範圍、硬約束、三件待拍板 | 15 分鐘 |
| 4️⃣ | [platform/03-FUNCTIONAL-SPEC.md](./platform/03-FUNCTIONAL-SPEC.md) | F1–F10 功能規格 | 30 分鐘 |
| 5️⃣ | [platform/04-REFUSAL-SPEC.md](./platform/04-REFUSAL-SPEC.md) | 拒答規格與 36 題測試集 | 20 分鐘 |
| 6️⃣ | [platform/05-PREREQUISITES-AND-ACCEPTANCE.md](./platform/05-PREREQUISITES-AND-ACCEPTANCE.md) | P0 前置、非功能需求、驗收 | 20 分鐘 |

DocuMind 本身的文件見 [README.md](./README.md)；DocuMind 是平台未來的一塊配件，不在平台第一版範圍內。
