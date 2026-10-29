# document_fields 固定帶鍵 — 計畫（片 F1）

> 狀態：**已核可**（業主 2026-10-29「選項二」，含部署授權；OQ1 選項二，標「選項一」的範圍不做）。規則與驗收清單：同目錄 `acceptance.md`（核可後凍結）。原文與量測：`raw/`。

## 終點指標（目標文件＝本片 `acceptance.md`；本線第一片，沒有前兩片）

| 量法 | 現值（`35210a0`，`raw/replay-before-summary.json`，鍵路徑巢狀展開） | 本片預期 |
|---|---|---|
| 存檔 348 份回應中，`document_fields` 缺了頁面上有的鍵路徑的份數（C2 (a)） | 128 份：謄本 18/18、合約 24/24、點交 39/39、帳單 21/63、修繕 23/137、收據 3/67 | 0 |
| 有值欄位與存檔不同的份數（C2 (b)） | 0（現行程式重算與存檔 348 份完全相同，作為工具正對照） | 0 |

C3（線上 6 份）是機制項：只確認部署後線上程式與本機相同，不另作終點量法；終點以 C2 兩列為準。

## 1. 目標

站內幫手：「看不出損壞的照片（plain.jpg），回應裡沒有 damaged_items 這個欄位，不是回 []」「希望固定回 []，判斷起來比較單純」。業主選「B 全部」：所有文件類型的 `document_fields` 都固定帶鍵，空值照實回。成功＝下游讀 `document_fields` 時，每個資料欄位一定在，用值判斷有沒有內容（規則見 `acceptance.md` R1–R4）。

## 2. 目標形態（業界與第一原理）

- **OpenAI Structured Outputs 固定帶鍵、空值用 null**（渲染原文 `raw/openai-structured-outputs.txt` 第 669、671、718 行）：「All fields must be required」「To use Structured Outputs, all fields or function parameters must be specified as required.」「Although all fields must be required (and the model will return a value for each parameter), it is possible to emulate an optional parameter by using a union type with null.」
- **Google Document AI 不同：值無法取得時欄位不出現**（`raw/google-docai-document.txt` 第 1957 行，`normalizedValue`）：「Optional. Normalized entity value. Absent if the extracted value could not be converted or the type (for example, address) is not supported for certain parsers.」
- **Azure Document Intelligence：未查完**（`raw/azure-di-analyze-response.txt` 渲染全文沒有談缺值欄位怎麼表示）。
- **自家先例**：謄本固定格式 `transcript_records`（對接規格 2.4.0）已採「鍵一律存在、沒印回 `null`／`[]`」。
- **第一原理**：鍵一定在，下游只要判斷值是否為空；鍵可能不在，就得同時處理「沒鍵」與「空值」，站內幫手就是被這個差異誤導。
- 結論：目標形態是「每類型的資料欄位鍵固定、空值照實回」；OpenAI 這樣做，Google Document AI 不同（省略），由業主選定此形態。

## 3. 差距（現況）

- `backend/app/services/analyze_service.py` 的 `_merge_fill_missing`：只在值非空時寫入鍵（`if is_missing and value not in (None, "", [])`），各頁都空的鍵（含巢狀子鍵）不進 `document_fields`。
- 頁面層多數類型已固定鍵（存檔實測：帳單 7 鍵、收據 5 鍵、點交 8 鍵、謄本 37 鍵各只有 1 種組合；修繕現行成功與降級都帶 4 鍵）。**例外是合約**：`contract_field_extractor.py` `_build_result` 只在讀到租賃欄位時才加 `rental_terms`（註解「只有當至少有一個租賃欄位被提取時才添加 rental_terms」），直讀路徑也呼叫它；存檔合約頁 100 頁中 40 頁沒有 `rental_terms`。
- 謄本 `_attach_full_transcripts`／`_attach_transcript_records`：解析或建構失敗時省略 `transcripts`／`transcript_records`。
- `validation_warnings` 只在型別檢查不過時加入頁面（`processor.py` `_apply_field_validation`）。
- 同一合併函式另被複核判定（`app/api/v1/analyze.py` `_apply_confidence_gating`，只讀 `field_confidences` 與 `_scored_fields_from_pages`，不受影響）與問答 context（`AnalyzeService` 的 `extracted_data`，`ai_service.py` 以 `json.dumps` 放進提示詞，會多出空值鍵）使用。前端不讀 `document_fields`（攻擊者 grep 驗證，正對照 `structured_data` 命中 5 檔）。
- 對接規格現行寫法：§2（`35210a0`）「`document_fields` 不帶值為空的鍵」、§3.1「（`document_fields` 裡該鍵不出現）」、§3.2「有租賃欄位時的 `rental_terms`」、§3.1.2／§3.1.3「解析失敗時省略此鍵」「建構失敗時只省略此鍵」、§3.3.1「`document_fields` 裡該鍵不出現（與其他類型相同）」、§3.4／§3.5 要求讀 `pages[0].structured_data`。

## 4. 路徑（一片）

| 範圍項目 | 服務哪個目標 |
|---|---|
| `_merge_fill_missing`：鍵不在 `target` 時，不論值是否為空都寫入；已在且為空時，用後頁非空值補（現行規則不變） | R1、R2 |
| 問答 context：送進提示詞前去掉空值鍵（遞迴），維持與改前相同的有值欄位 | R2 |
| （僅選項一）`ContractFieldExtractor._build_result` 與 `contract_processor.py` 例外降級路徑一律帶 `rental_terms`（子欄沒讀到為 `null`）；謄本解析／建構失敗時 `transcripts`／`transcript_records` 設為 `null`，`docs/api/transcript_records.schema.json` 頂層改允許 `null`（見「推翻卡 OQ1」） | R1 |
| 單元測試 C1 ①–⑨；既有測試斷言因本片而改的逐條列出 | R1、R2 |
| `docs/api/INTEGRATION.md` 升 2.7.0，改 §2、§3.1、§3.1.2、§3.1.3、§3.2、§3.3.1、§3.4、§3.5 與 `validation_warnings` 說明（C4） | R3 |
| 謄本線上驗收基準 `backend/data/transcript_samples/expected/*.json` 由存檔重算更新（C5） | R2（避免下次線上驗收誤報差異） |
| 部署：本機 commit、push 後，線上機 `git pull --ff-only`（bind mount＋`--reload`，不需重建容器）；線上機目前 `b36a5ec`，與 main 之間只差文件 commit（`a89d076`、`35210a0`） | R4 |

相關但不在本次範圍：為每類型另立 JSON Schema 文件；`validation_warnings` 改為一律帶（它是警示通道，不是資料欄位；列為共同例外）。

## 推翻卡（本片推翻現行規格寫法）

- (a) 推翻什麼：`docs/api/INTEGRATION.md` §3.1「「原文空白」與「讀不到」在值上都是 `null`（`document_fields` 裡該鍵不出現）」；§3.3.1「值為 `null` 的欄位只出現在 `pages[].structured_data`；`document_fields` 裡該鍵不出現（與其他類型相同）」；§2（`35210a0`）「`document_fields` 不帶值為空的鍵」；選項一另推翻 §3.2「有租賃欄位時的 `rental_terms`」與 §3.1.2／§3.1.3 失敗時省略。
- (b) 原本為了解決什麼：查不到刻意省略空值的理由。查過：`git log -S "該鍵不出現"`（`48dc2ab`、`b36a5ec`，都是描述合併結果，沒寫理由）；`_merge_page_structured_data`／`_merge_fill_missing` docstring（目的是「不用後面頁的殘值覆蓋前面已抽到的值」）；`35210a0` 是本 session 依業主選 A 補寫的現況描述。`rental_terms` 條件出現：程式註解只寫做法，沒寫理由；推測是讓非租約合約不顯示租賃區塊（C 級，未查到出處）。謄本失敗省略：docstring「解析失敗只記 log、省略此鍵：這是附加資訊，不能讓既有回應跟著失敗」——改成 `null` 仍不讓回應失敗，此理由不受影響。
- (c) 新依據：站內幫手實測回報（A：來信原文，業主轉貼）；OpenAI Structured Outputs 固定帶鍵（A：渲染原文）；自家 `transcript_records` 先例（A：規格 2.4.0）；Google Document AI 反例（A：渲染原文）。
- (d) 拿掉什麼、用什麼補：拿掉「鍵不在＝空」這個訊號；替代是值本身（`null`／`[]`／`""`），`field_confidences` 照舊分辨「原文空白」與「讀不到」。已知消費端：站內幫手＝AIChatbot（`rag-orchestrator/services/documind_client.py`；攻擊代理讀本機 checkout `c4603e13`：收據、修繕照片讀 `pages[0].structured_data`，按路徑取值時 `None` 與缺鍵都算空，C）；jgb2 `HandoverPhotoAnalyzeService.php` `firstStructuredData`（先讀 `pages[0].structured_data`）、`Transcript/ParserExtractor.php`（`wt-mobile-s3d-before` 分支，以 `document_fields` 為主）——主持人查證（jgb2 `dev1`、`dev8` checkout）：前者 `HandoverPhotoAnalyzeService.php:276` 用 `?? null`，後者 `ParserExtractor.php:151` 用 `isset && is_array`、`sanitizeDocumentFields` 用 `isset`／`unset`，`null` 與缺鍵處理結果相同（A，限本機 checkout；線上部署版本未查）；前端不讀 `document_fields`。
- (e) 數據：無使用數據；唯一證據是一家下游的來信需求。
- (f) 維持現況：不改程式，站內幫手讀 `pages[0].structured_data`（照片）或把缺鍵當空值；好處是零改動，代價是多頁文件只能讀 `document_fields`，仍有「缺鍵」與「空值」兩種情形。
- (g) 反向攻擊：見下方。
- 依規則第 2 條，(b) 查不到、(e) 無時推薦應為維持現況；**業主已在看過「維持 A」選項後選「B 全部」**（2026-10-29），本卡記錄取捨，不再推薦。

### 攻擊結果（通用代理，唯讀；主持人查證後處置）

| # | 發現 | 主持人查證 | 處置 |
|---|---|---|---|
| F1 P2 | 合約 `rental_terms` 條件出現，「兩種讀法結果相同」不成立 | 讀 `contract_field_extractor.py` 第 380–382 行與直讀 `to_structured` 確認 | FIX：改列業主開放題 OQ1，計畫寫兩案 |
| F2 P2 | 判分用頂層 JSON 比對，修好巢狀後合約會被誤判不通過 | 確認舊 `replay.py` 為頂層比對 | FIX：`replay.py` 改鍵路徑巢狀展開，判分改寫 |
| F3 P2 | 合約現值 0/24 量錯 | 新 `replay.py` 重跑：24/24 | FIX：終點表改 128 份 |
| F4 P3 | 規格其他段落（§3.2、§3.1.2／§3.1.3、`validation_warnings`）漏列 | grep 確認 | FIX：列入路徑與 C4 |
| F5 P3 | 消費端不只站內幫手（jgb2） | 屬實：jgb2 `dev1/app/Services/HandoverPhotoAnalyzeService.php:271-279` 以 `?? null` 讀 `pages[0].structured_data`；`dev8/app/Services/Transcript/ParserExtractor.php:151` 以 `isset && is_array` 讀 `document_fields`，`sanitizeDocumentFields`（:167-）全用 `isset`／`unset` | FIX：(d) 補列 |
| F6 P3 | C3 綁模型輸出值，可能誤觸回退 | 存檔三輪有翻轉（攻擊者實測） | FIX：C3 只判鍵 |
| F7 P3 | 在線上機 revert 會分岔 | — | FIX：回退改為本機 revert、push、線上 pull |
| F8 P4 | 謄本線上驗收腳本分不出缺鍵與 null | 讀第 85 行確認 | DEFER：不在本片；回歸由 C1 擋 |
| 待查 | 站內幫手是否以「鍵在不在」判斷 | 第二位攻擊代理讀 AIChatbot 本機 checkout：按路徑取值、`None` 與缺鍵同視（C）；線上部署版本未查 | 收案回信時請對方確認；我方改後鍵一定在，若對方用 `'k' in obj` 會判成「有」，回信寫明改用值判斷 |

## 推翻卡 OQ1 選項一（另一個推翻項，獨立一題）

- (a) 推翻什麼：`docs/api/INTEGRATION.md` §3.2「有租賃欄位時的 `rental_terms`」（程式 `contract_field_extractor.py` `_build_result`「只有當至少有一個租賃欄位被提取時才添加 rental_terms」）；§3.1.2「解析失敗時省略此鍵」、§3.1.3「建構失敗時只省略此鍵」（程式 `analyze_service.py` `_attach_full_transcripts`／`_attach_transcript_records`）。
- (b) 原本為了解決什麼：`rental_terms` 條件出現——查不到。查過：程式註解（只寫做法）、引入 commit `74f90a8`（沒寫理由）、前端（`OcrTestView.vue` 沒有租賃區塊，所以「不顯示租賃區塊」的推測沒有程式依據；攻擊代理查證）。謄本失敗省略——docstring「解析失敗只記 log、省略此鍵：這是附加資訊，不能讓既有回應跟著失敗」；改 `null` 同樣不讓回應失敗。
- (c) 新依據：與主卡相同（站內幫手來信、OpenAI 原文、`transcript_records` 先例；皆 A）。
- (d) 拿掉什麼、用什麼補：拿掉「有 `rental_terms` 鍵＝至少讀到一個租賃欄位」，可用 `rental_terms` 子欄是否有值完全還原（它本來就不是租約判斷，規格 §3.2 寫明租約以原文關鍵詞判定）；拿掉「`transcripts` 鍵不在＝解析失敗」，改由值 `null` 表示。已知消費端（攻擊代理讀本機 checkout，C）：站內幫手即 AIChatbot（`rag-orchestrator/services/documind_client.py`），讀 `rental_terms.*` 時 `None` 與缺鍵都算空，`transcript_records` 用 `_require(..., list)`，`null` 與缺鍵都回失敗；jgb2 沒有讀 `rental_terms`，`transcript_records` 用 `isset && is_array`。
- (e) 數據：無。
- (f) 維持現況（＝選項二）：好處是不動合約抽取器與謄本附加、不碰下列攻擊發現的風險；代價是非租約合約的 `document_fields`（與頁面）仍沒有 `rental_terms`，謄本解析失敗時 `transcripts`／`transcript_records` 仍不出現，規格要把這兩處寫成固定鍵的例外。
- (g) 反向攻擊（通用代理，唯讀，只攻擊選項一；主持人查證）：

| # | 發現 | 主持人查證 | 若選選項一的處置 |
|---|---|---|---|
| O1 P3 | `contract_processor.py` `extract_fields` 例外降級另組結果、不經 `_build_result`，仍沒有 `rental_terms`；規格 §3.2 範例即此形狀 | 屬實：`contract_processor.py:306-326` 的 `except` 回傳 `contract_metadata`／`parties`／`financial_terms`，第 300–330 行 `rental_terms` 0 次 | 降級路徑一併改、C1⑦ 加此路徑、C4 加範例 |
| O2 P3 | `docs/api/transcript_records.schema.json` 頂層 `"type": "array"`，改 `null` 會與公開 Schema 衝突 | 屬實：`transcript_records.schema.json:6` 為 `"type": "array"` | Schema 改 `["array","null"]`，列入 R3／C4 |
| O3 P3 | 多引擎共識開啟時，非租約合約多出 14 個租賃鍵進評分，`needs_confirmation` 11→25 項（本機模擬）；共識預設關閉（`config.py` `OCR_CONSENSUS_ENABLED=False`），線上實際值未查 | 預設值屬實：`config.py:282`；11→25 為攻擊代理本機模擬（C），主持人未重跑；線上實際值未查 | 違反 R2 的風險；若選選項一，須另行處理（見「OQ1 與 R2」） |
| O4 P4 | 主卡 (d) 原寫「非租約判斷改看 `rental_terms` 子欄是否全 null」，與規格 §3.2 原則相反 | 讀規格確認 | 已從主卡刪除 |
| O5 P4 | 選項一還會讓 `test_direct_read.py`（`"rental_terms" not in structured`）、`test_transcript_full_parser.py`（`df == {"owner": "x"}`）變紅 | 屬實：`test_direct_read.py:647`、`test_transcript_full_parser.py:206` | 列入 C1⑨ |
| O6 P4 | 前端複核畫面與 OCR 測試頁會多出空列（既有的 `[object Object]` 顯示缺陷多一列） | 複核畫面屬實：`frontend/src/views/reviewRows.ts:16-34` 取頁面頂層鍵、以 `String()` 顯示；OCR 測試頁未查 | 只影響內部畫面顯示 |

- **OQ1 與 R2**（收尾審查指出）：選項一會讓非租約合約的問答 context 多出 `rental_terms: {}`，共識開啟時評分欄位也會變，兩者都違反 R2，目前驗收清單擋不到。選選項一時，須先修訂計畫（問答 context 去掉改前不存在的空 dict、共識攤平排除全 `null` 區塊並加測試，或業主明示放寬 R2）並重新送審，本片不直接執行選項一。
- 推薦：依「推翻現況的建議」第 2 條（(b) 查不到、(e) 無），**推薦選項二**，並先取得數據：站內幫手實際是否串合約、是否需要非租約合約也帶 `rental_terms`（請對方回信確認）。選項一列為選項，不推薦。

## 執行（每一次都寫回答的決定與成本）

| 執行 | 回答的決定 | 會改變下一步的結果 | 規模與理由 | 成本（來源） |
|---|---|---|---|---|
| 本機 pytest 全套 | 改動有沒有弄壞既有行為 | 有紅燈 ⇒ 修或停 | 全套（便宜、決定性） | 約 1 分鐘（T1 實測 1777 個測試） |
| C2 存檔重算 | R1、R2 在 6 類真實回應上是否成立 | 任一份不符 ⇒ 修，不部署 | 全部 348 份，屬「終點量測（收案重量）」時機；本機、不花模型費 | 約 10 秒（改前實跑），0 次模型呼叫 |
| C3 線上實測 | 部署後線上程式是否與本機相同；頁面改動（選項一）是否上線 | 不符 ⇒ 回退 | 6 份：照片 2（無損、有標籤）、收據 1（`null`）、文字層謄本 1、文字層合約 2（租約、非租約）；每種空值與每個改動點各一 | 6 場 × 每場約 0.3–3.2 秒，合計約 20 秒（來源：T2 存檔 `~/jgb-archive/qwen-direct-read-20261029/t2/after1/` 的 `elapsed`——P04 3.11 秒、漢堡王發票 1.78 秒；S2 存檔謄本 08 伺服器 0.27 秒；合成照片與文字層合約比照同類）；Qwen 3 次、OpenAI 0 次（文字層皆 `enable_llm=false`）；皆不跑本機 OCR；線上複核佇列最多多 6 筆 |
| 謄本線上驗收全套 | 不跑 | — | 圖片範本會跑本機 OCR、有 OOM 風險；C2 已用存檔重算涵蓋 8 份範本的合併 | — |

## 回退

本機 `git revert` 本片 commit 並 push，線上機 `git pull --ff-only`，`--reload` 自動生效（不在線上機直接 revert，避免與 origin 分岔）。

## 權限（核可題）

本片部署與回退要寫入線上機（`54.248.201.66`），需業主授權；C3 會在線上複核佇列新增最多 6 筆（ID 記入收案紀錄）。

## 停點

- C1 或 C2 不通過、修不好 ⇒ 不部署，回報業主。
- C3 鍵不符 ⇒ 回退並回報。

## 用量報告

收案時報子代理 token 合計與模型呼叫次數。送審前已用：攻擊代理 177,839＋207,305 tokens、計畫審查 95,305 tokens。
