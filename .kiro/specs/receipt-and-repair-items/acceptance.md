# Qwen 直讀（收據、帳單、合約）＋修繕物件欄位 — 規則與驗收清單

> 狀態：**已核可、凍結**（業主 2026-10-28「核可，開始 T1」，第 3 版）；核可後凍結，本檔即判定標準。計畫正文：同目錄 `plan.md`。

## 規則（業主原話 → 可檢查條件）

| ID | 可檢查條件 | 業主原話（2026-10-28） | 讀法註記 |
|---|---|---|---|
| R1 | 收據 `receipt`（新類型）、帳單 `bill`、合約 `contract` 的**影像與沒有文字層的 PDF**，由 Bedrock Qwen3 VL 直接讀圖抽欄位，不在線上機跑本機 OCR | 「所以? 不調整 ?」「規格文件 和實際程式 都調整」「Qwen 不就是 OCR 為什麼要 OCR+Qwen」「剛剛不就說要調整? 你有什麼問題？」 | 謄本不在範圍：主持人說明「謄本保留本機 OCR（模擬掃描 97% 對 91%）」後業主未反對；列非目標 |
| R2 | 直讀送給 Qwen 的影像長邊 2000 | 直讀解析度答「長邊 2000」 | **主持人補**：JPEG 品質 92、單張 ≤3.75MB，沿用現行 Bedrock 常數（`providers.py` 的重新編碼品質與上限） |
| R3 | 有文字層的帳單、合約 PDF 維持現行文字層路徑，行為不變 | 電子檔答「維持文字層路徑」 | **收窄到帳單、合約**：收據沒有文字抽取器、也沒有舊流程，收據的 PDF（不論有沒有文字層）一律走直讀 |
| R4 | `receipt` 回傳 `amount`（原始字串，取總計不取單項）、`date`、`field_confidences`、`needs_confirmation`；必要欄位不含戶號；認得無標籤的電子發票日期；分不出總計時 `amount` 進 `needs_confirmation`；接受 jpg、png、pdf | 收據欄位答「只回金額、日期」；業主轉貼給站內幫手的回覆第 1 點 | 總計的各種寫法由模型讀圖判斷，不以關鍵字清單實作（全域「通用處理」原則）；可收格式為主持人補 |
| R5 | `/api/v1/classify` 能回 `receipt` | 業主轉貼的回覆第 1 點末句 | — |
| R6 | `repair_photo` 回應新增 `damaged_items`（字串陣列，照片裡壞掉的物件，不綁 JGB 分類） | 業主轉貼的回覆第 2 點 | — |
| R7 | 品質只報不擋：同一批輸入，舊流程與新流程並列；帳單、合約任一類正確率掉超過 20 個百分點（改後 3 次平均對改前；合約改後 1 次），把那一類從直讀切回舊流程（只改設定）並回報業主；修繕照片 `defect_labels` 命中率掉超過 20 個百分點，回退提示詞程式並回報 | 主持人預設，已告知業主「要改請說」，業主未改 | 比照業主對模型切換的裁定（「只報不擋，差太多停下」「3 次平均」）。**收據收窄為只報、不切回**：收據沒有舊流程，切回等於撤掉已承諾的新類型 |
| R8 | 規格文件與程式同步：`docs/api/INTEGRATION.md`（`receipt`、`damaged_items`、直讀後的帳單與合約回應、classify 回 `receipt`）、`docs/planning/03-TECH-STACK.md` 與 `docs/DEPLOYMENT.md` 描述處理流程的段落（帳單、合約影像改直讀；收據新類型），與程式和線上設定一致 | 「規格文件 和實際程式 都調整」 | **收窄**：只改描述這次改變之行為的文件段落。「月成本 $15」是現行需求（`ocr-vlm-consensus/requirements.md` 5.5、`steering/product.md`），地端組態（`LLM_CLOUD_ENABLED=false`）仍是現行功能，都不在本片改；重訂上限屬另案，需業主裁定 |

## 驗收清單

直讀類（收據、帳單、合約的影像與掃描 PDF）每一份送出都計入；沒有 `llm_calls` 中 `stage=direct_read` 且 `provider=bedrock` 的一筆，或 `ocr_raw` 不是 null，該份判「機制不符」。

| # | 項目 | 規則 | 觀察點 | 證據 | 通過條件 |
|---|---|---|---|---|---|
| B1 | 收據：直讀、欄位齊、總計與日期 | R1、R2、R4 | 線上 `/api/v1/analyze`（`receipt`） | 每份的 `ocr_raw`、`llm_calls`、amount／date 對錯、`needs_confirmation` | 每一份機制符合；回傳鍵含 amount、date、field_confidences、needs_confirmation；品質照實報，並逐項報：無標籤日期的電子發票（站內幫手 588 那張）、總計不明或有明細表頭「金額」的手寫收據（站內幫手 2,350 那張）、指令注入文字的發票（860 那張） |
| B2 | 帳單：掃描件與照片改直讀，回應鍵與舊版相同 | R1、R2、R7 | 線上 `/api/v1/analyze`（`bill`） | 同上；改前改後並列 | 每一份機制符合；R7 停點照判 |
| B3 | 合約：掃描 PDF 逐頁直讀，回應鍵與舊版相同並新增 `field_confidences`／`needs_confirmation` | R1、R2、R7 | 線上 `/api/v1/analyze`（`contract`） | 同上；盲判改前改後 | 同 B2 |
| B4 | 文字層帳單、合約 PDF 不變 | R3 | 線上以 `enable_llm=false` 送 1 份文字層合約 PDF（主持人用 PyMuPDF 產生、內容為公開租約範本文字；B4 是機制項，輸入撰寫者不限）改前、改後各 1 次 | 兩份存檔回應 | `pages[].ocr_raw.text`、`structured_data` 的鍵與值逐一相同，兩次 `llm_calls` 皆為 `[]` |
| B5 | classify 認得收據 | R5 | 線上 `/api/v1/classify` | 收據、謄本、合約、帳單各 ≥5 張的建議類型 | 收據輸入中至少一半回 `receipt`；各類正確率照實報 |
| B6 | 修繕照片 `damaged_items` 與 `defect_labels` | R6、R7 | 線上 `/api/v1/analyze`（`repair_photo`） | 回應欄位；`damaged_items` 盲判；`defect_labels` 依評估判法（關鍵字命中、壁癌誤標數）改前改後並列 | `damaged_items` 欄位存在、正確率照實報；`defect_labels` R7 停點照判 |
| B7 | 直讀不吃 OCR 記憶體 | R1 | 直讀類實測期間每份送出前後 `docker stats` | 取樣紀錄 | 直讀類實測全程無 OOM；單份增量 <200 MiB |
| B8 | 機制項（本機 pytest） | R1–R6 | 測試輸出 | 見右 | 全綠，含：①直讀路徑不呼叫 OCR 引擎；②送出影像長邊 2000、≤3.75MB（影像、PDF 兩條路）；③文字層帳單、合約 PDF 不走直讀；④`DIRECT_READ_DOCUMENT_TYPES` 未列的帳單、合約走舊流程；⑤收據 PDF（有、沒有文字層各一）都走直讀；⑥receipt 回傳鍵；⑦模型回「不確定」或金額格式不過時 `needs_confirmation` 含 `amount`；⑧receipt 必要欄位不含 `account_no`；⑨無標籤日期（如 `2026-10-12 14:35:20`）可被接受；⑩合約回應鍵與舊版相同並含 `field_confidences`／`needs_confirmation`；⑪`damaged_items`；⑫classify 回 receipt；⑬謄本路徑不變；⑭改前通過的單元測試改後仍通過；⑮直讀類收到 `enable_llm=false` 仍呼叫 Qwen 直讀（D-9） |
| B9 | 文件 | R8 | 對 R8 列的三份文件 grep：①INTEGRATION 有 `receipt`、`damaged_items`、classify `receipt`，鍵名與程式回應相同；②三份文件中「帳單、合約影像先跑 OCR 再交 AI」的現況描述（含同義改寫），以及 INTEGRATION 的 `enable_llm` 說明列與「純 OCR，不花 LLM 成本」範例的舊說法，不再出現，正對照：同指令命中新的直讀描述；③DEPLOYMENT §0.5 的直讀設定與線上 `.env` 相同 | grep 輸出 | ①②T1 收案時成立；③T2 收案時成立 |

## 判分

- 收據、帳單：逐欄對標準答案（收據 amount、date；帳單 amount、date、account_no）。印的沒有的欄位記「無」，回空才算對。正確率＝對的欄數 ÷ 判分欄數。
- 合約、`damaged_items`：`blind-judge` 看原圖與輸出盲判（合約 A／B 不告知哪個是哪個）。
- `defect_labels`：評估 §3.5 的類別關鍵字命中（`~/jgb-archive/bedrock-vlm-eval-20261023/scripts/grade_samples.py` 的 `REPAIR`），非壁癌照片標「壁癌」的次數另報。
- R7：改後 3 次平均對改前（合約改後 1 次）。

## 廣度

| 項目 | 類型 | 資料組（用／可用） | 不同輸入數 | 重複次數 | 輸入撰寫者 | 改前對照 |
|---|---|---|---|---|---|---|
| B1 收據 | 使用者層 | 3：站內幫手合成收據 3 張；評估用 Commons 台灣收據 R01–R10；不看程式的代理另找 1 個公開來源 ≥3 張 | ≥16 | 改前 1、改後 3 | 站內幫手；評估時選圖；不看程式的代理 | 同一批送現行 `bill`（站內幫手現況會得到的結果） |
| B2 帳單 | 使用者層 | 2／2：S2 凍結的帳單 5 張＋台電教學圖 1 張（瓦斯、管理費查無公開樣張，見 S2 收集報告） | 6 | 改前沿用 S2 改後（3 次）、改後 3 | 不看程式的代理（S2 凍結） | S2 改後結果（`docs/testing/bedrock-qwen-switch-20261028.md`） |
| B3 合約 | 使用者層 | 1／1：`data/contracts/` 掃描合約（真實，無公開來源可補） | 5（S2 同 5 份） | 改前沿用 S2、改後 1 | 既有真實合約 | 同上 |
| B5 classify | 使用者層 | 4 類各取上列樣本＋謄本範本 | ≥20 | 1 | 同上 | 現行 classify（收據只會回 null） |
| B6 修繕 | 使用者層 | 3：Commons、Flickr、PickPik／PxHere（S2 凍結） | 21 | 改前沿用 S2 改後（3 次）、改後 3 | 不看程式的代理／評估時選圖 | `defect_labels`：S2 改後結果；`damaged_items`：無（新欄位） |
| B4、B7–B9 | 機制項 | — | — | — | — | — |

上位驗收方式：無。

- 合約只 5 份：其餘 6 份（4–16 頁）改前需跑本機 OCR，線上機會 OOM；改後另跑並照實報為「無對照」。
- 說法變化不適用：輸入是圖片。
- verifier 另找至少 10 個沒出現過的輸入（收據、帳單、合約、修繕各至少 2 個）在線上實跑。

## 業主裁定（核可時）

| 問題 | 業主裁定（2026-10-28） |
|---|---|
| 直讀類收到 `enable_llm=false` | 「照樣交 Qwen 讀，改文件」 |

