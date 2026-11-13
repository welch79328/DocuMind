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
│   ├── transcript_records.schema.json    # 謄本固定輸出格式的 JSON Schema（不帶參數，已棄用）
│   └── transcript_records_v2.schema.json # 謄本帶參數格式 transcript_format=v2 的 JSON Schema
│
├── planning/
│   ├── 03-TECH-STACK.md                  # 技術棧現況
│   ├── transcript-status.md              # 謄本解析現況、決策、待辦
│   └── followups.md                      # 之後再做清單
│
├── testing/
│   ├── transcript-online-acceptance.md   # 謄本驗收範本、跑法、線上結果
│   ├── bedrock-vlm-eval-20261023.md      # 紀錄：Bedrock 東京視覺模型 vs 線上
│   ├── bedrock-qwen-switch-20261028.md   # 紀錄：帳單／照片／合約改走 Bedrock Qwen3 VL（flex）
│   ├── qwen-direct-read-20261029.md      # 紀錄：收據、帳單、合約改 Qwen 直讀
│   ├── document-fields-fixed-keys-20261029.md  # 紀錄：document_fields 固定帶鍵
│   ├── amount-string-type-20261029.md    # 紀錄：模型補值一律回字串
│   ├── transcript-photo-fullparse-eval-20261109.md  # 紀錄：照片／掃描謄本全文解析評估
│   ├── transcript-v2-20261109.md         # 紀錄：謄本帶參數格式本機實測（補值、位置）
│   ├── transcript-v2-online-20261111.md  # 紀錄：謄本帶參數格式正式機部署與線上確認
│   ├── transcript-v2-jgb-gaps-20261111.md  # 紀錄：謄本帶參數格式補 JGB 回報的 4 項缺口
│   ├── contract-v2-positions-20261113.md # 紀錄：合約帶參數格式電子 PDF 值位置
│   └── handover-v2-accuracy-20261113.md  # 紀錄：點交照片 v2 新舊品項準確率比較
│
├── tools/                                 # 行銷版 PDF 產生腳本
├── DEPLOYMENT.md                          # 部署指南；§0.5 線上機實況
├── DEV_WORKFLOW.md                        # 本機與線上的分工
├── ANNOTATION_GUIDE.md                    # 標註資料存放與版控規範
├── OCR_FLOW_FOR_MARKETING.md              # 行銷版辨識流程說明
```

---

## 📚 平台層規格閱讀順序

| 順序 | 文件 | 說明 | 預估閱讀時間 |
|------|------|------|--------------|
| 1️⃣ | [platform/README.md](./platform/README.md) | 總覽、三條原則、現在卡在哪裡 | 8 分鐘 |
| 2️⃣ | [platform/01-DATA-INVENTORY.md](./platform/01-DATA-INVENTORY.md) | 資料源實查清冊（全部推導的起點） | 25 分鐘 |
| 3️⃣ | [platform/02-V1-SCOPE.md](./platform/02-V1-SCOPE.md) | 範圍、硬約束、三件待拍板 | 15 分鐘 |
| 4️⃣ | [platform/03-FUNCTIONAL-SPEC.md](./platform/03-FUNCTIONAL-SPEC.md) | F1–F10 功能規格 | 30 分鐘 |
| 5️⃣ | [platform/04-REFUSAL-SPEC.md](./platform/04-REFUSAL-SPEC.md) | 拒答規格與 36 題測試集 | 20 分鐘 |
| 6️⃣ | [platform/05-PREREQUISITES-AND-ACCEPTANCE.md](./platform/05-PREREQUISITES-AND-ACCEPTANCE.md) | P0 前置、非功能需求、驗收 | 20 分鐘 |

DocuMind 本身的文件見 [README.md](./README.md)；DocuMind 是平台未來的一塊配件，不在平台第一版範圍內。
