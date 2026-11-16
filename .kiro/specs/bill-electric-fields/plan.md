# 帳單多回電費 4 欄（address、period_start、period_end、kwh）— 計畫

要什麼：`document_type=bill` 的回應在 `document_fields` 多回 `address`、`period_start`、`period_end`、`kwh` 四欄，給 AIChatbot「電費分攤」用；既有 `amount`、`date`、`account_no` 不退步。
怎樣算做到：AIChatbot 的 10 張合成電費單送正式機，依 `acceptance.md` 凍結清單 E1–E8 判定通過；INTEGRATION.md 同步到新版本。

做到什麼就收：10 張合成電費單在正式機新版本跑完 3 次、結果交業主與 AIChatbot，`acceptance.md` E1–E8 每項有判定，`followups.md` 每項有去處。

狀態：**2026-11-16 業主核可**（「核可計畫」）。Q6 現值未量、送正式機授權尚未明答，送正式機前再問。本計畫**未經審查**（沒有派 plan-verifier）；**未查業界做法**，目標形態以第一原理推導。

---

## 0. 交核可前先答三題（驗收廣度）

| 問題 | 答 |
|---|---|
| 每項幾組資料 × 幾種輸入 × 重複幾次 | 使用者層（E1–E4）：AIChatbot 合成電費單 10 張 × 改後 3 次、改前 1 次。回歸（E5）：既有帳單樣本 5 張（電 1、水 2、負向 2）× 改前 1 次、改後 3 次。共 2 組資料（可用的全用，見 `acceptance.md`「廣度」）|
| 輸入誰寫的 | 10 張與正確值由 AIChatbot 提供（不是實作者）；5 張既有樣本是公開樣張，真值 2026-10-28 凍結 |
| 跟改前比了嗎 | 會。同 10 張、同 5 張，先用正式機現行版本跑 1 次（程式在本機改好、部署前），部署後跑 3 次 |

## 1. 目標正本定位

無上層目標。查過：`docs/planning/`（無電費欄位）、`.kiro/specs/`（`receipt-and-repair-items` 的 R1–R3 規定帳單直讀與文字層路徑，本片沿用、不改）、`docs/planning/followups.md`（無相關項）、grep `kwh|period_start|period_end` 於 `backend/` 0 筆（正對照 `account_no` 9 筆）。
目標文件：本線 `acceptance.md`（凍結規則與清單）。
碰到的既有裁定：`receipt-and-repair-items` R3「有文字層的帳單、合約 PDF 維持現行文字層路徑」——本片**不改路徑**，只在文字層路徑加規則（見 §4 D2）。

## 2. 目標（設計方法第 1 步）

AIChatbot 要拿一張電費單，自動把「哪個電號、哪個地址、哪段期間、用了幾度、要繳多少」加進對的房客帳單。成功＝6 欄讀對；讀不準就明說（null 或列 `needs_confirmation`），**錯值不能帶著高信心度回去**——期間錯了會加進錯的那期帳單（AIChatbot 規則 1）。規則逐條見 `acceptance.md` R1–R12。

## 3. 目標形態（第一原理，未查業界做法）

1. **同一份單、不論檔案型態，回同樣 6 個鍵、同樣格式**：照片、掃描 PDF、電子 PDF 三種輸入結果一致；格式由伺服器驗，不靠呼叫端再驗。
2. **格式在伺服器正規化**：日期一律 `YYYY-MM-DD`（民國轉西元），數字字串，地址單行。
3. **驗不過就不回值**：不合格式、迄日早於起日、地址含網址或 `@` 等，回 null 並列待確認，不把壞值交出去。
4. **待確認的語意清楚**：「讀到但沒把握」列 `needs_confirmation`；「單上沒有或讀不到」回 null。
5. **既有欄位行為不退步**，其他類型帳單（水費等）不受新欄位拖累（不因為沒有度數就整份進複核）。

## 4. 差距與路徑

### 現況（設計方法第 3 步）

| 路徑 | 什麼時候走 | 現在回什麼 | 依據 |
|---|---|---|---|
| 直讀（Bedrock Qwen） | 照片、沒有文字層的 PDF（正式機 `DIRECT_READ_DOCUMENT_TYPES` 含 `bill`） | 3 欄；不確定的值**保留**、信心 0.5 | `direct_read_processor.py` `BillDirectReadProcessor.build_prompt`、`_field_confidence` |
| 文字層規則 | 有文字層的 PDF | 3 欄 regex；`account_no` 標籤只認「戶號／用戶號／帳號」，**台電印「電號」抓不到** | `bill_field_extractor.py` `PATTERNS` |
| 文字層 + 模型補 | 不會發生：AIChatbot 送 `enable_llm=false`，且文字層路徑不給圖 | — | AIChatbot `rag-orchestrator/services/documind_client.py` `"enable_llm": "false"`；`analyze_service.py` `AnalyzeService._extract_fields_for_text_layer` 傳 `image_data=None` |

**關鍵事實**：AIChatbot 一律送 `enable_llm=false`，所以合成 PDF 若有文字層，**只會走規則，模型完全不參與**；JPG 一律走直讀。兩條路都要做。

### 路徑（設計方法第 4 步）

| 步 | 內容 | 服務哪一點 |
|---|---|---|
| D1 直讀提示詞 | `BillDirectReadProcessor` 讀 6 欄：加 `address`（用電地址，不取通訊地址）、`period_start`／`period_end`（計費期間）、`kwh`（本期計費度數總數）；`account_no` 提示加「電號」 | 目標形態 1；R1–R5 |
| D2 文字層規則 | `BillFieldExtractor.PATTERNS` 加 4 欄標籤規則（用電地址、計費期間、計費度數），`account_no` 加「電號」標籤。沿用現有「欄位＝標籤規則」機制，不另立特規 | 目標形態 1；R1–R5、R11 |
| D3 共用正規化與驗證 | 新模組一處、兩條路共用：期間用既有 `parse_date` 轉 `YYYY-MM-DD`、驗 迄 ≥ 起；`kwh` 數字字串 >0、≤30 字；`address` 收成單行、≤80 字、含網址／`@`／冒號即判不過。驗不過 ⇒ 值 null、列 `needs_confirmation` | 目標形態 2、3；R6、R7 |
| D4 待確認與評分 | 新 4 欄：讀到但不確定或驗不過 ⇒ 列 `needs_confirmation`；模型回 null ⇒ 值 null、不列、不放進 `field_confidences`（理由見「我改動的地方」C3）。既有 3 欄計分規則不變 | 目標形態 4、5；R8 |
| D5 規格文件 | `docs/api/INTEGRATION.md` §3.3 寫 6 欄、格式、null 與待確認語意；版本 2.12.1 → **2.13.0**（新增鍵） | R12 |
| D6 單元測試 | 只跑新增與改到的：`test_direct_read.py`、`test_bill_processor.py`、`test_bill_edges.py`、`test_text_layer_path.py`、新正規化模組的測試（依據：改了 `BillDirectReadProcessor`、`BillFieldExtractor.PATTERNS`、新模組）。全套只在部署前跑一次，失敗 id 與基線比 | R12 |
| D7 部署 | **業主自己部署**（正式機寫入，我不做）；我寫部署步驟與還原步驟 | — |
| D8 線上驗收 | 見 §6 量測表 | E1–E8 |

**不做**：兩段計費期間的回法（AIChatbot 規則 5 說「請先告訴我們」，見 R10）；換模型；改其他文件類型；改 `date` 的語意（AIChatbot 說「照現在的樣子保留」）。

## 5. 待決問題（擋核可或擋驗收，不由我選）

| ID | 問題 | 問誰 | 擋什麼 | 我暫時的預設 |
|---|---|---|---|---|
| Q1 | 規則 1「沒把握就給 null」：模型讀到值但說不確定時，你要 **(X) 值改 null＋列 `needs_confirmation`**，還是 **(Y) 保留值＋列 `needs_confirmation`**（現行做法）？同一條要不要也套到既有 `amount`、`date`、`account_no`？ | AIChatbot（經業主） | 擋 D3、D4 寫法 | 無；要答才寫 |
| Q2 | 規則 3「完全讀不出來時給 `llm_used_for_extraction: false`」與現行語意衝突（這個欄位指「有沒有叫模型補欄位」：電子 PDF 規則讀完是 `false`；照片直讀成功、什麼都沒讀到是 `true`）。建議 AIChatbot 改用「6 欄全 null」判斷，不改這個欄位的語意 | AIChatbot | 擋 R9 寫法 | 不改欄位語意（上回已回覆，等確認） |
| Q3 | 規則 1、規則 4 貼上時被截斷（「給錯值比給 nul 物件…」「例："1」），請重貼全文 | AIChatbot | 擋凍結 | — |
| Q4 | 驗收「6 欄要讀對」：讀不準而回 null 並列 `needs_confirmation` 的欄位，算**過**還是**不過**？通過門檻是 60/60（10 張 × 6 欄）還是別的數？ | AIChatbot（經業主） | 擋 E1 判定 | 先照最嚴：只有「值相符且沒列待確認」算對；另外分開報「null＋有列」「錯值」兩數 |
| Q5 | 10 張合成檔（PDF、JPG 原檔）與每張正確值，請 AIChatbot 寄來 | AIChatbot | 擋 §6 全部量測 | — |
| Q6 | 終點現值未量：正式機現行版本在這 10 張上的 3 欄正確率要等檔案到才能量。**你要接受「現值未量」先核可**，還是等檔案到、量完再核可？ | 業主 | 擋核可 | — |

## 6. 量測（每批寫答哪個決定、成本）

| 批 | 跑什麼 | 回答的決定 | 會改變下一步的結果 | 成本（估） |
|---|---|---|---|---|
| M0 | 檔案到後，本機 `has_text_layer` 檢查 10 張 PDF 有沒有文字層（不送正式機） | D2 是不是主路徑 | PDF 都有文字層 ⇒ D2 規則的準確度決定 PDF 結果，先在本機用文字層驗 D2 | 數秒，0 次模型呼叫 |
| M1 | 本機單元測試＋本機以 10 張的文字層跑 D2（不送模型） | D2 規則能不能讀對文字層 | 任一張文字層讀錯 ⇒ 修規則；改不動（版式差太多）⇒ 停下交業主（是否改走直讀＝推翻 R3，業主裁定） | 數秒 |
| M2 改前 | 程式改好、**部署前**，正式機現行版本：10 張＋5 張各送 1 次，一次一份、送前查容器記憶體 | E5 的改前值、E1 的現值 | — （給改後對照） | 15 份 × 約 10–30 秒（未逐份計時；依 2026-10-29 帳單直讀 18 頁無 OOM）；直讀約 15–20 次 Bedrock 呼叫 |
| M3 改後 | 業主部署後，正式機新版本：10 張＋5 張各 3 次，一次一份 | E1–E8 判定 | E5 既有 3 欄掉超過 20 個百分點 ⇒ 停、交業主決定要不要還原；錯值（E2）≥1 ⇒ 報業主與 AIChatbot，修或接受由業主定 | 45 份 × 約 10–30 秒；約 45–60 次 Bedrock 呼叫 |

全部送正式機的批次**都會寫正式環境**：檔案上傳 S3（`uploads/ocr_others`，`acl="public-read"`）、低信心的進複核佇列（不含圖）。輸入只用合成檔與公開樣張，不送真實房客的單。M2、M3 送正式機**需要業主授權**，請在核可時一併答（見確認版）。

## 7. 終點指標

目標文件＝本線 `acceptance.md`。

| 量法 | 現值 | 本片預期 | 前兩片 |
|---|---|---|---|
| 10 張 × 6 欄讀對數（E1） | **現值未量**：新 4 欄現行版本不回（＝0/40，依 grep 0 筆）；既有 3 欄（30 格）要等檔案到跑 M2 | 新 4 欄由 0 升；既有 3 欄不掉 | 本線第一片，無前片 |
| 錯值數（E2，值錯且沒列待確認） | 現值未量（同上） | 0 | 同上 |
| 既有 5 張樣本 3 欄（E5） | 2026-10-29 直讀版 14/15 × 3 次（`docs/testing/qwen-direct-read-20261029.md`「帳單 3 欄」）。這是舊版本的紀錄，現行版本未重量，**不當現值**；M2 量 | 不掉 | 同上 |

量現值的步驟：拿到 10 張後跑 M2（正式機現行版本、一次一份、各 1 次），輸出存 `~/jgb-archive/bill-electric-fields-20261116/runs/before/`。

## 8. 風險條件

| 條件 | 這次碰到嗎 | 處理 |
|---|---|---|
| 序列化／API 回應改變 | 是：bill 的 `document_fields` 多 4 個鍵；值格式新規則 | 只增不減，既有鍵不改名；INTEGRATION 升 2.13.0；jgb2 不用 bill（jgb2 只在 `HandoverPhotoAnalyzeService.php` 呼叫 DocuMind） |
| 上線 | 是 | 業主部署；正式機是 bind mount＋`--reload` |
| 對外寫入 | 是：M2、M3 寫 S3 與複核佇列 | 需業主授權；只送合成與公開樣張 |
| 資安 | 否：不動認證、憑證、權限。地址欄位的「不含網址、`@`、冒號」是格式驗證，屬 AIChatbot 下游防護的配合，不改 DocuMind 安全邊界 | 一般寫入 |
| 記憶體 | 正式機 2 GiB，多頁掃描連送會 OOM | 一次一份、送前查記憶體，超過 1.8 GiB 先停、請業主重建 |

## 9. 還原

改動集中在一個 commit（程式＋測試＋文件）。還原＝`git revert` 該 commit，業主在正式機拉回前一版（`--reload` 自動生效）。回應只是少 4 個鍵，AIChatbot 端讀不到鍵時照其規則當 null。

## 10. 用量回報

收案時報實際子代理 token（預計 0，不派代理）與 Bedrock 呼叫次數。

## 11. 時程

核可後約 2–3 個工作天寫完程式與本機驗證；線上驗收等 Q5 的檔案到、業主部署。對 AIChatbot 給的日期由業主定。
