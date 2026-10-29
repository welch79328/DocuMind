# 計畫：模型補值一律回字串（對接規格 2.8.0）

規則與凍結驗收清單：同目錄 `acceptance.md`（規則 R1–R5、清單 C1–C4）。本計畫是一片；目標文件＝該凍結清單（沒有上層目標正本）。

## 終點指標

| 指標 | 現值 | 本片預期 | 前兩片 |
|---|---|---|---|
| 探針 `TOTAL_NUMERIC`（模擬模型回數字時，回應裡數字型別的欄位值個數） | **10**（受測物 `b0a18dc`，2026-10-29 13:31；指令與輸出存 `~/jgb-archive/amount-string-type-20261029/probe-before.txt`：帳單 2、帳單小數 1、謄本 2、合約 5） | 0 | 本目標第一片，沒有前片 |

線上存檔佐證問題真實存在（不是現值、只說明來源）：2026-10-28～29 線上回應中，帳單 `amount` 23 筆、合約金額欄位 12 筆為數字，全部出自**直讀上線前**影像走 OCR 後的模型補值。

**哪些路徑現在會走到模型補值**（決定 C3 能驗什麼）：

- 模型補值兩個入口都要有影像才呼叫模型：`field_extraction_base.py:90`（`if use_llm_fallback and needs and image_data`）、`contract_field_extractor.py:188-193`（`and image_data`）。
- 文字層 PDF 一律不給影像：`analyze_service.py:459-463`（`image_data=None, # 文字層無需影像`），所以文字層 PDF **不會**走到模型補值。
- 線上設定 `DIRECT_READ_DOCUMENT_TYPES=["receipt","bill","contract"]`（`docs/DEPLOYMENT.md:30`）：帳單、合約的影像與掃描 PDF 改走直讀（`analyze_service.py:520-527`），直讀本來就回字串。
- 結論：**線上目前只有謄本影像與掃描 PDF（`enable_llm=true`）會走到模型補值**；帳單、合約的補值路徑只在直讀關閉時才會走到——程式預設 `DIRECT_READ_DOCUMENT_TYPES=[]`（`config.py`），線上若關掉直讀或另起一套部署就會走到。帳單、合約這條由 C1、C2 在本機涵蓋，線上無法覆蓋。

## 1. 目標

- 對接方拿到的欄位值型別固定：同一欄位不會這次是字串、下次是數字（R1）。線上目前會碰到的是謄本影像；帳單、合約在直讀關閉的設定下會碰到（見終點段）。
- 規格已寫明合約值是字串（§3.2「`月租金：２５，０００元` 回 `25,000`」）、收據 `amount` 是「原始字串」（§3.3.1）；程式在模型補值時違反了規格。

## 2. 目標形態（業界）

原文存 `.kiro/specs/document-fields-fixed-keys/raw/`（上一片以 web-drive 渲染取得）：

- Google Document AI `Document.Entity`：`mentionText` 型別是 `string`，「Text value of the entity」；正規化的型別值另放 `normalizedValue`（`moneyValue`、`integerValue`、`floatValue`…），且「Money/Currency type (moneyValue) is in the ISO 4217 text format」。→ **讀到的文字值固定為字串，有型別的值另放一個欄位**。
- OpenAI Structured Outputs：「Supported types: String, Number, Boolean, Integer, Object, Array, Enum, anyOf」，「In addition to specifying the type of a property…」。→ **每個欄位都宣告型別**；`anyOf` 允許一個欄位接受多種型別，所以這份原文不支持「只能一種」。
- Azure Document Intelligence：已存的回應頁沒有欄位值型別段落，**未查完**。

目標形態：文字值欄位一律字串（依 Google `mentionText`）；同一欄位不在字串與數字間浮動，是第一原理推導（對接方每次寫兩套判斷的成本），查無業界逐字對應。另給有型別的數值欄位（像 Google `normalizedValue`）屬「相關但不在本次範圍」：目前沒有對接方提出需求（AIChatbot 收據自己把字串轉整數，`parse_receipt_amount`）。

## 3. 差距

- 模型補值的值有兩個入口直接寫入、不轉型別：
  - `RegexFieldExtractor.extract`（`field_extraction_base.py`，帳單與謄本共用）：`fields[key] = value`。
  - `ContractFieldExtractor._merge_fields`（`contract_field_extractor.py`）：`merged[field_name] = llm_value`。
- 直讀（`direct_read_processor.py` `_read_field`）已一律 `str(value)`；規則抽取來自文字；共識比對只走規則路徑（`_resolve_consensus` 固定 `enable_llm=False`）。這三條不用改。
- 下游會不會壞：
  - 型別檢查 `validate_field_value` 本來就先 `str(value)`；信心度計算只看 `is not None`。轉型別後結果相同（R3，C1⑦ 驗）。
  - 已知對接方：AIChatbot 只讀收據（直讀，本來就是字串）；jgb2 dev1／dev8 只讀點交照片與謄本（`HandoverPhotoAnalyzeService.php`、`Transcript/ParserExtractor.php`），沒有讀帳單、合約金額。謄本欄位本來就是字串，改後只是不會再偶爾出現數字。
  - 本專案前端 `OcrTestView.vue` 用 `Number(contract_amount)` 顯示；`"25000"` 照樣可轉。

## 4. 路徑（一片）

1. 在 `field_extraction_base.py` 加 `llm_value_as_text(value)`（R2 的轉換），兩個入口在「是否採用」判斷之後呼叫；採用條件本身不改（R3）。
2. 單元測試 `backend/tests/unit/test_llm_value_as_text.py`（C1）。
3. `docs/api/INTEGRATION.md` 升 2.8.0（C4）。
4. 本機跑全套 `tests/unit` 與探針（C1、C2）→ commit、push → 線上 `git pull --ff-only`（bind mount 加 `--reload` 生效）→ C3（謄本影像 2 份）。
5. 收案驗證員（全新，依 `acceptance.md`）→ 收案紀錄 `docs/testing/amount-string-type-20261029.md`，同時更新 `docs/README.md` 索引。

非目標：有型別的數值欄位（上面第 2 節）；改提示詞要求模型回字串（會改變模型行為，得重新評估讀值品質）；模型回 `true`／`false`、物件、陣列的處理；`OcrTestView.vue` 對 `"25,000"` 這種帶千分位字串顯示 `NaN`（改前就有，另列觀察）；OpenAPI 版本號 `1.0.0`。

推翻檢查：不是推翻項。規格（§3.2、§3.3.1）本來就寫字串，本片是讓程式符合現行規格，不改任何裁決或產品規則。

## 每次執行

| 執行 | 回答的決定 | 規模與理由 | 成本（跑前估） |
|---|---|---|---|
| 全套 `tests/unit` | 便宜且決定性，每次改動照跑 | 全套 | 約 1 分鐘（上一片實測），不呼叫模型 |
| 探針 C2 | 終點指標是否到 0；不是 0 ⇒ 不部署 | 4 組，涵蓋兩個入口與三類 | 數秒，不呼叫模型 |
| 線上 C3 | 部署後的線上程式在唯一走得到的補值路徑（謄本影像）上正常、沒有數字型別；有錯誤或數字 ⇒ 回退 | 2 份 repo 內謄本影像 `05_ntpc_land_mortgage.jpg`、`04_kcg_apartment_shared.jpg`：上次線上實測這兩份都走到 `extraction`（`~/jgb-archive/bedrock-qwen-switch-20261028/s2/after1/transcript/05_ntpc_land_mortgage.json`、`s2/extra/transcript/04_kcg_apartment_shared.json`）；帳單、合約線上走不到（見終點段），不送 | 每份約 17–20 秒（同上兩檔 `stats.total_time_ms` 16940、19730），Qwen 各 1 次（同上兩檔 `llm_calls` 各一筆 `extraction`），共 2 次；依線上機規則一次一份 |
| 收案驗證員 | 依規定，結果是否 CONFIRMED | 1 次 | 約 10–15 萬 tokens（上一片同類實測） |

## 回退

本機 `git revert <commit>` → push → 線上 `git pull --ff-only`。只改值的型別，回退後回到 `b0a18dc` 的行為。

## 停點

- C2 不是 0、全套單元測試有新失敗 ⇒ 不部署，修正後重跑。
- C3 出現數字型別，或線上錯誤 ⇒ 立即回退（含在部署授權內），回報業主。
- 驗證員 REFUTED ⇒ 依規定處置，不自行宣布完成。

## 用量回報

收案時回報子代理 tokens 實際總數與 Qwen 呼叫次數。

## 待業主核可

- 核可本計畫（含 R1 放寬到所有模型補值欄位、依「通用處理」裁定）。
- 授權部署線上機與必要時回退。
