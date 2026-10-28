# Qwen 直讀（收據、帳單、合約）＋修繕物件欄位 — 計畫

> 狀態：**已核可、凍結**（業主 2026-10-28「核可，開始 T1」，第 3 版；收尾審查 REVISE 3 項已處置：D-9 經業主裁定、D-8 補授權、T1 前置改正，未再審）。規則 R1–R8 與凍結驗收清單在同目錄 `acceptance.md`，判定以該檔為準。
> 前置：`.kiro/specs/bedrock-qwen-documind/`（四類改走 Bedrock Qwen flex，`784dc09`，已上線）。

## 0. 業主原話與來源

業主原話（2026-10-28）：
1. 「所以? 不調整 ?」
2. 「規格文件 和實際程式 都調整」
3. 「Qwen 不就是 OCR 為什麼要 OCR+Qwen」
4. 「剛剛不就說要調整? 你有什麼問題？」
5. 直讀解析度：「長邊 2000」；電子檔：「維持文字層路徑」；收據欄位：「只回金額、日期」。
6. 站內幫手來信（業主轉貼）後，業主把主持人起草的回覆轉給對方，回覆承諾：新類型 `receipt`（amount、date、field_confidences、needs_confirmation，取總計、不含戶號、認得無標籤日期）、classify 加 `receipt`、修繕照片加 `damaged_items`。

前因：S2 實測中線上機 2 次 OOM（切換前、切換後各 1 次，都在帳單的本機 OCR），原因是本機 OCR（每頁約 0.7 GiB、用完不還、容器上限 2 GiB）。業主指出 Qwen 本身能讀字，不需要先跑本機 OCR。

## 1. 目標、目標形態、差距、路徑

**目標**：收據、帳單、合約的影像與掃描件由 Qwen 直接讀圖抽欄位，線上機不再為它們跑 OCR；收據成為新類型、修繕照片多回物件；規格文件同步（R1–R8）。

**目標形態**（不看現況，業界原文在 `raw/`）：
- Azure 收據模型（`raw/azure-receipt-model.txt` 第 88 行）：「The API extracts key information such as merchant name, merchant phone number, transaction date, tax, and transaction total and returns structured JSON data.」同行：「Receipts can be of various formats and quality including printed and handwritten receipts.」
- AWS Textract AnalyzeExpense（`raw/aws-textract-invoices-receipts.txt` 第 52 行）：「It automatically extracts data such as invoice or receipt date, invoice or receipt number, item prices, total amount, and payment terms.」第 84 行：收據上的「Total」對應標準欄位 `TOTAL` 並附「Confidence Score」。
- Google Document AI（`raw/google-docai-processors-list.txt` 第 706 行）：「Extract text and values from expense documents such as expense date, supplier name, total amount, and currency.」
- 三家都把「總額」「日期」當獨立的欄位回傳，這是本計畫收據欄位與「取總計不取單項」的依據。附信心度的原文只見 AWS（第 84 行「Confidence Score」），Azure、Google 這兩頁未見。三家服務內部怎麼做 OCR 不在原文範圍，本計畫不宣稱。
- 「同一個視覺模型直接讀圖、省掉本機 OCR」：第一原理推導（Qwen3 VL 讀圖本身就辨識文字；評估 §3.1 Qwen 只看圖讀謄本 96.2%），**查無業界對應**。

**差距**（依唯讀盤點，HEAD `784dc09`）：
- 帳單、合約走 `OcrDocumentProcessor.analyze`：本機 OCR → 規則 → 必要時 Qwen 補欄位；OCR 在線上機跑，造成 OOM。
- 沒有 `receipt` 類型；`/api/v1/classify` 只會回 `transcript`、`contract` 或 null（Tesseract 關鍵字）。
- 修繕照片只回 `defect_labels`、`description`、`confidence`。
- 合約回應沒有 `field_confidences`／`needs_confirmation`，閘控只看 OCR 信心度；合約的 few-shot 實際沒注入。
- 影像理解類（修繕、點交）已有「不跑 OCR、直接呼叫視覺模型」的處理器樣式（`ImageUnderstandingProcessor`），直讀可沿用。
- 文件：`docs/api/INTEGRATION.md` 沒有 `receipt`、`damaged_items`；`03-TECH-STACK.md` §2–§3、`DEPLOYMENT.md` §0.5／§3 描述帳單、合約影像「先 OCR 再交 AI」。「月成本 $15」與地端組態是現行需求與功能，不屬過時陳述，本片不改（R8 收窄）。

**路徑**：§4 兩片。偏離：
- 收據只回金額、日期，不回商家、稅額（業主裁定 R4）；三家業界模型會回，列「相關但不在本次範圍」。
- 謄本不改直讀：模擬掃描評估本機 OCR＋規則 97% 對 Qwen 只看圖 91%（評估 §3.3）。

## 2. 非目標（附理由）

- 謄本（理由見上）。
- 有文字層的 PDF（R3，業主裁定）。
- 點交照片（已是直讀）。
- 資安四項（業主：「現在在測試 之後解決」，記在 `docs/planning/transcript-status.md`）。
- 修繕照片另加 `error_code`：已回覆站內幫手以 `llm_calls` 區分失敗。
- 收據的商家名稱、稅額、單號（R4）。
- 線上機規格或容器記憶體上限（另列待辦，業主決定）。

## 3. 決策

| ID | 決策 | 理由 |
|---|---|---|
| D-1 | 新增直讀處理器（沿用 `ImageUnderstandingProcessor` 樣式）：影像以長邊 2000 縮放（無 OCR，可用 draft 縮小解碼）、PDF 逐頁以長邊 2000 渲染，JPEG 品質 92，送 Qwen 回 JSON | R1、R2；不跑 OCR 就沒有 OCR 記憶體峰值 |
| D-2 | 新設定 `DIRECT_READ_DOCUMENT_TYPES`（預設空）；列入的類型（`receipt`、`bill`、`contract`）才走直讀，未列入的走舊流程。`receipt` 沒有舊流程，不列入時回不支援 | R7 切回只改 `.env` 重建容器 |
| D-3 | 欄位信心度：模型對每欄回值與「確定／不確定」；不確定或格式驗證不過（金額非數字、日期解析失敗）給 0.5，其餘 0.9；低於門檻進 `needs_confirmation` | AWS 原文各欄附信心度（第 84 行）；DocuMind 下游靠 `needs_confirmation` 決定要不要人工確認。只靠模型自評不可靠，所以加格式驗證（第一原理，查無業界對應） |
| D-4 | 帳單、合約回應鍵與舊版相同（帳單 amount／date／account_no；合約 contract_metadata／parties／financial_terms／rental_terms），合約另加 `field_confidences`、`needs_confirmation` | 下游（jgb2、AIChatbot DSP-004 用 `rental_terms`）不用改 |
| D-5 | 多頁合約逐頁直讀，沿用 `_merge_page_structured_data` 彙整 | 與現行一致 |
| D-6 | classify 加 `receipt`：沿用現行分類器，加收據關鍵性質（統一發票、收據字樣等由規則判斷），對映到 `receipt` | R5；分類器本身是否改用模型不在本次範圍 |
| D-7 | 修繕照片提示詞加 `damaged_items`；`defect_labels` 的範例「（如 漏水、壁癌、龜裂、設備損壞）」保留不動 | S2 實測 Qwen 修繕命中 9.67/10，沒有證據需要動範例；只加新欄位，降低 `defect_labels` 回歸風險，並以 B6 改前改後確認 |
| D-9 | 直讀類（收據、帳單、合約的影像與掃描 PDF）收到 `enable_llm=false` 時照樣交 Qwen 讀；INTEGRATION 的 `enable_llm` 說明與「純 OCR，不花 LLM 成本」範例改正為「直讀類與照片類一律呼叫模型；`enable_llm` 只影響謄本與文字層 PDF」 | 業主 2026-10-28：「照樣交 Qwen 讀，改文件」；與修繕、點交照片現行行為一致，每頁約 $0.001 |
| D-8 | 列入本計畫核可的授權範圍：T1 commit＋push main；T2 線上 `git pull`、`.env` 加 `DIRECT_READ_DOCUMENT_TYPES`、`--force-recreate`；T2 步驟 4 文件 commit＋push；R7 觸發時的切回（帳單、合約改 `.env` 重建容器；修繕回退提示詞的程式變更、commit、push、線上 pull、重建容器）；T2 步驟 1 改前基準期間記憶體超過 1.8 GiB 時重建線上容器；T2 回滾時在主機 `git checkout <記下的 SHA>` 並重建容器 | 前一片的部署授權只涵蓋那次切換 |

## 4. 切片

### 程式封套
- 擁有者：主 session 統籌；T1 由 `executor` 實作（不涉憑證與守衛，沿用既有 Bedrock 供應商）；T2 部署與實測由主 session；收據補充樣本由不看程式的代理挑選；盲判用 `blind-judge`；結果由新開 `verifier` 驗。
- 停點：P0；線上連續 2 次 5xx；直讀類 OOM（違反 B7 前提，停下回報）；改前基準在舊流程上 OOM（依業主「慢送」裁定重建容器續跑，同一份第二次仍 OOM 就停、回報、該份照實報缺）；業主喊停。
- 用量報告：每片收案時回報子代理 tokens 實際加總（取自任務通知）與 Bedrock 實際花費；是回報，不是上限或停點。

### T1｜本機實作
- **成果**：D-1～D-7 完成，預設行為不變（`DIRECT_READ_DOCUMENT_TYPES` 空＝帳單、合約照舊；`receipt` 需列入才可用）；修繕回應多 `damaged_items`、classify 能回 `receipt`；B8、B9（機制部分）通過。
- **範圍**：D-1～D-7；新類型登記處（`DocumentType`、工廠、`TYPE_ALLOWED_EXTENSIONS`、`S3_PATH_MAP`、`LLM_ROUTABLE_DOCUMENT_TYPES`、`DocumentTypeEnum`、Form 說明、相關測試）；`receipt` 走 Bedrock（分流表可設）；INTEGRATION、03-TECH-STACK、DEPLOYMENT、`spec.json` 改正。
- **前置**：S2 收尾的文件與紀錄（`docs/DEPLOYMENT.md`、`docs/planning/03-TECH-STACK.md`、`docs/README.md`、`docs/testing/bedrock-qwen-switch-20261028.md`）已另行 commit；`docs/planning/transcript-status.md` 的待辦列不屬本片，也在 T1 開工前另行 commit。T1 開工時工作樹沒有其他片的改動（`.claude/` 為本機設定，不入版控，除外）。
- **驗收**：B8 ①–⑭；B9 ①②；本機單元測試全綠且改前通過的改後仍通過。
- **回滾**：不 commit 即丟棄；commit 後 `git revert`。
- **停點**：測試修 5 輪仍不過；verifier REFUTED 修後仍 REFUTED；INCONCLUSIVE 補證據重試一次仍 INCONCLUSIVE。
- **收尾**：verifier CONFIRMED 後 commit＋push main（D-8）。
- **用量報告**：同封套。

### T2｜線上部署與實測
- **前置**：T1 verifier CONFIRMED；收據補充樣本凍結；站內幫手 3 張合成收據到手（沒到手就照實報缺這組）。
- **步驟**：
  1. 改前：B4 的文字層合約 PDF 以 `enable_llm=false` 送 1 次存檔；收據各輸入送現行 `bill`（舊流程會跑本機 OCR：一次一份，每份送前查記憶體，超過 1.8 GiB 先重建容器，每份送前確認 `OOMKilled=false`）；帳單、合約、修繕沿用 S2 結果；classify 跑現行。
  2. 記下主機 SHA；`git pull --ff-only`（T1 已 push）；`.env` 加 `DIRECT_READ_DOCUMENT_TYPES=["receipt","bill","contract"]` 與分流 `receipt: bedrock`；`--force-recreate`；容器內印設定確認。
  3. 改後：B1–B7，直讀類每份送出前後看記憶體。
  4. 依最終設定（含 R7 切回）改文件的實際去向，commit＋push。
- **回滾**：`.env` 拿掉該類型重建容器；程式 `git checkout <記下的 SHA>`。
- **各批實跑的目的**：
  - B1 收據 ≥16 × 改前 1、改後 3：回答「站內幫手可不可以開始用 receipt」；改後 3 次是為了看 Qwen 每次輸出不同時的穩定性；結果只報（R7 收據收窄），讀者是業主與站內幫手。
  - B2 帳單 6 × 改後 3、B3 合約 5 × 改後 1：回答 R7「直讀要不要切回舊流程」；改前沿用 S2（同輸入、同版本 `784dc09`），全量重跑的依據是直讀改了這兩類的每一份影像請求；合約只 1 次是 OOM 前例下沿用前片做法。
  - B5 classify ≥20 × 1：回答「站內幫手能不能靠 classify 分出收據」；只報，讀者是站內幫手。
  - B4 文字層合約 1 份 × 改前 1、改後 1（`enable_llm=false`，規則抽取可重現）：回答「R3 有沒有被直讀波及」；結果不同就停下查原因。
  - B6 修繕 21 × 改後 3：回答 R7「提示詞加欄位有沒有讓 `defect_labels` 變差」，全量重跑的依據是提示詞改了每一份請求；`damaged_items` 只報，讀者是站內幫手。
- **執行估算**（估算，不是上限）：收據改前 ≥16 × 1 次走舊流程（本機 OCR 每份 12–30 秒，加上約每 2–3 份重建容器 1 分鐘，出處 `docs/testing/bedrock-qwen-switch-20261028.md` §1、§4）≈ 13 分；收據改後 ≥16 × 3 次 × 約 3–5 秒（評估 §3.7）≈ 4 分、Bedrock ≈ $0.06（評估 §3.8 約 $0.001／張）；B4 2 次 × 不到 1 秒；帳單 6 × 3 ≈ 2 分；合約 5 份共 13 頁 × 約 5 秒 ≈ 2 分；classify ≥20 × 約 5 秒 ≈ 2 分；修繕 21 × 3 ≈ 4 分；verifier 新輸入約 10 分。合計約 30 分、不到 1 美元。
- **停點**：同封套；R7 觸發的類型切回（修繕為回退提示詞程式）並回報。
- **用量報告**：同封套。

## 5. 終點表

目標文件：本目錄 `acceptance.md`（規則 R1–R8 與清單 B1–B9）。

| 項目 | 角色 | 現值（版本、出處） | T1 預期 | T2 預期 | 前兩片 |
|---|---|---|---|---|---|
| 收據、帳單、合約影像類請求跑本機 OCR 的比例 | 完成指標 | 帳單、合約 100%（`784dc09` 程式：`OcrDocumentProcessor`）；收據類型不存在 | 0（預設不變，是 T2 這一列的前置） | 100% → 0%（未被 R7 切回者） | 本目標無前片 |
| 直讀類實測期間 OOM 次數 | 完成指標 | 帳單、合約走舊流程時，S2 期間 OOM 2 次（`docs/testing/bedrock-qwen-switch-20261028.md`，`784dc09`） | 0（未部署） | 0 | 本目標無前片 |
| 收據 amount 正確率 | 只報（R7） | 現值未量：T2 步驟 1 量（站內幫手說現行規則 3 張都抓不到） | 0 | 未知 | 本目標無前片 |
| 收據回傳鍵含 amount、date、field_confidences、needs_confirmation（B1） | 完成指標 | 收據類型不存在（`784dc09`） | 0（未部署；本機測試 B8 ⑥ 先證） | 全部收據回應皆含 | 本目標無前片 |
| classify 對收據回 `receipt` 的比例（B5） | 完成指標（門檻：至少一半） | 0%：現行分類器只回 transcript／contract／null（`784dc09` `document_classifier.py`） | 0（未部署） | ≥50% | 本目標無前片 |
| 修繕回應含 `damaged_items`（B6） | 完成指標 | 0%（`784dc09` `repair_photo_processor.py` 只回 defect_labels／description／confidence） | 0（未部署） | 100% | 本目標無前片 |
| 帳單、合約、修繕 `defect_labels` 正確率 | 只報（R7） | S2 改後結果（`docs/testing/bedrock-qwen-switch-20261028.md`，`784dc09`） | 0 | 未知 | 本目標無前片 |

## 6. 驗證

T1、T2 各一次新開 `verifier`，附業主原話、本檔、`acceptance.md`。

## 7. 待查

- 站內幫手 3 張合成收據與預期值：需業主轉請對方提供。

## 8. 第一次 plan-verifier（2026-10-28，REVISE，11 項）處置

| 項目 | 處置 |
|---|---|
| 計分篩選會漏掉沒走直讀的請求 | FIX：每份都計入，缺 direct_read 或 `ocr_raw` 非 null 即機制不符 |
| D-7 拿掉範例沒驗、切不回 | FIX：範例保留不動；B6 加 `defect_labels` 改前改後；R7 寫明修繕回退程式 |
| S2 結果與 OOM 紀錄沒有存檔 | FIX：S2 收尾時寫 `docs/testing/bedrock-qwen-switch-20261028.md`（含指令、時間、版本），終點表與 B2、B3、B6 引用；「前兩片」改「本目標無前片」 |
| R4 三項行為沒驗 | FIX：B8 ⑦⑧⑨；B1 逐項報站內幫手三張 |
| 收據 R7 與 PDF 未定義 | FIX：R7 收據收窄為只報；R3 收窄到帳單、合約，收據 PDF 一律直讀；B8 ⑤ |
| R8 範圍不完整 | FIX：§1 差距列出 grep 的現行文件與紀錄例外 |
| 信心度宣稱超出原文 | FIX：改為只 AWS 有原文 |
| 原話第 4 句未引用、R2 補值未註 | FIX：R1 引用；R2 註明主持人補 |
| T2 各批缺目的與理由 | FIX：§4 T2「各批實跑的目的」 |
| push 未列、改前基準無 OOM 防護 | FIX：D-8 含 push；T2 步驟 1 加慢送防護；封套停點涵蓋舊流程 OOM |
| 缺用量報告 | FIX：封套、T1、T2 補 |

## 9. 第二次 plan-verifier（2026-10-28，REVISE，7 項）— 停止自動重送，逐項處置

| 項目 | 優先 | 處置 |
|---|---|---|
| R8 會改掉現行 $15 需求與地端組態說明 | P2 | 收窄：R8 只改描述本次行為改變的段落；$15 與地端組態不動，重訂上限另案 |
| R8 盤點不完整、T1 文件驗收無法判定 | P2 | 隨收窄消解：R8 只列三份文件；B9 拆成 ①②（T1）③（T2） |
| B4 無法判定 | P2 | 定 `enable_llm=false`、比對欄位、T2 步驟 1 加改前、補目的與估算 |
| 終點表缺 B1、B5、B6 門檻 | P2 | 補三列；B5 門檻「至少一半」 |
| 部署授權不完整 | P2 | D-8 補 T2 步驟 4 與 R7 切回（含修繕回退）的每一步 |
| 檔案擁有權衝突 | P2 | T1 前置：S2 收尾文件先另行 commit |
| 收據改前估算出處不對 | P2 wording-only | 另列舊流程每份時間，出處 S2 紀錄 |

## 10. 收尾審查（2026-10-28，REVISE，3 項）— 交業主

| 項目 | 處置 |
|---|---|
| 直讀類 `enable_llm=false` 行為未定義 | 業主裁定「照樣交 Qwen 讀，改文件」→ D-9、B8 ⑮、B9 ② |
| 部署授權缺改前重建與一般回滾 | D-8 補上 |
| T1 前置與 transcript-status 矛盾 | 改為該檔也在 T1 前另行 commit |

