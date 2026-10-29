# document_fields 固定帶鍵 — 規則與驗收清單

> 狀態：**已核可、凍結**（業主 2026-10-29「選項二」，含部署授權）；本檔即判定標準。OQ1 裁定選項二：標「選項一」的條件（C1⑦⑧⑩、C3 的合約 `rental_terms` 鍵）不適用。計畫正文：同目錄 `plan.md`。

## 規則（業主原話 → 可檢查條件）

| ID | 可檢查條件 | 原話（2026-10-29） | 讀法註記 |
|---|---|---|---|
| R1 | 所有文件類型（`transcript`、`contract`、`bill`、`receipt`、`repair_photo`、`handover_photo`）的 `document_fields`：該類型的每個資料欄位（含巢狀子欄位）一定有鍵；沒有值時回空值本身（`null`、`[]` 或 `""`） | 業主「B 全部」；所選選項原文：「所有文件類型的 `document_fields` 都固定帶鍵，空值照實回 `null`、`[]` 或 `""`」；站內幫手來信「希望固定回 []，判斷起來比較單純」 | **OQ1（待業主裁定，推翻卡見 plan.md）**：「固定的鍵」是哪一組。前提更正：業主所選選項原文寫「只改一處合併邏輯就涵蓋全部類型」，這不成立——合約 `rental_terms` 只在讀到租賃欄位時才出現在頁面上，要固定它得另改合約抽取器與謄本附加兩處。選項一＝每類型的完整資料欄位：合約 `rental_terms` 一律帶（沒讀到租賃欄位時子欄全 `null`），謄本 `transcripts`／`transcript_records` 解析失敗時回 `null`；選項二＝只保留各頁 `structured_data` 實際有的鍵（合約非租約仍沒有 `rental_terms`、謄本失敗仍省略），即這兩處維持現況。依「推翻現況的建議」第 2 條（無數據），推薦選項二並取得數據（站內幫手是否串合約、如何判斷非租約）。兩案共同例外：`validation_warnings`（警示，只在型別檢查不過時出現）、合併時刻意移除的中繼鍵 `has_building_evidence`／`share_slots`、所有頁都沒有 `structured_data` 時 `document_fields` 為 `null` |
| R2 | 有值的欄位，彙整結果與改前逐一相同（跨頁「只填補缺值」、清單串接、待確認與信心度重算都不變）；問答功能送給模型的欄位只含有值的欄位，與改前相同 | 隱含於所選選項（只說固定帶鍵，未說改值） | 主持人補：本片只增加空值的鍵 |
| R3 | 規格文件與程式同步：`docs/api/INTEGRATION.md` 寫明 `document_fields` 固定帶鍵與共同例外；刪去與此相反的現行說法 | 業主 2026-10-28 定案「規格文件 和實際程式 都調整」，本片沿用 | 只改描述此行為的段落；版本升 2.7.0 |
| R4 | 線上部署後，線上回應符合 R1 | 「B 全部」之後的部署 | 部署與回退需業主授權，列在核可題 |

## 驗收清單

| # | 項目 | 規則 | 觀察點 | 證據 | 通過條件 |
|---|---|---|---|---|---|
| C1 | 機制項（本機 pytest） | R1、R2 | 測試輸出 | pytest 輸出 | 全綠，含：①單頁全空值時鍵存在、值為頁面的空值（`[]`、`""`、`null` 各一）；②多頁時前頁空值、後頁有值 ⇒ 取後頁值；③前頁有值、後頁空值 ⇒ 保留前頁值；④`has_building_evidence`、`share_slots` 仍不出現；⑤巢狀（合約 `parties`、`rental_terms`）內的空值子鍵保留；⑥問答 context 去掉值為 `null`、`""`、`[]` 的葉（保留 dict，含空 dict），選項二下與改前逐字相同；⑦（選項一）非租約合約的頁面與 `document_fields` 都有 `rental_terms`、子欄全 `null`，OCR 與直讀兩條路徑各一；⑧（選項一）謄本全文解析／固定格式建構失敗時 `transcripts`／`transcript_records` 為 `null`；⑨改前通過的單元測試改後仍通過；斷言因本片而改的逐條列出（已知僅選項一會改：`test_transcript_records.py` 建構失敗斷言「鍵不出現」、`test_direct_read.py` `"rental_terms" not in structured`、`test_transcript_full_parser.py` `df == {"owner": "x"}`）；⑩（選項一）合約例外降級路徑（`contract_processor.py` `extract_fields`）同樣帶 `rental_terms` |
| C2 | 存檔回應重算（本機） | R1、R2 | 用新程式對線上已存的 348 份回應（謄本 18、合約 24、帳單 63、收據 67、修繕 137、點交 39；`~/jgb-archive/bedrock-qwen-switch-20261028/`、`~/jgb-archive/qwen-direct-read-20261029/`）的 `pages` 重算 `document_fields`，對照存檔值；腳本 `raw/replay.py` | 重算輸出檔 | 鍵路徑巢狀展開（`field_confidences` 整包視為一個值）。每一份：(a) 各頁 `structured_data` 的鍵路徑（扣中繼鍵）全在新結果；(b) 存檔裡有的鍵路徑，新值與存檔值相同；(c) 新增的鍵路徑，值都是空值（`null`、`""`、`[]`、`{}`）。任一份不符即不通過。存檔頁面是舊程式產生的，C2 不涵蓋選項一對頁面的改動（由 C1⑦⑧、C3 涵蓋） |
| C3 | 線上實測（只判鍵，不判模型讀出的值） | R1、R4 | 部署後送線上 `/api/v1/analyze`，6 份：主持人合成的無損照片、P04、漢堡王電子發票、文字層謄本 08、文字層租約（T2 用過的公開範本）、主持人合成的文字層非租約合約（後三份 `enable_llm=false`） | 存檔回應 | 每份 `document_fields` 符合 C2 的 (a)(c)，且該類型的資料欄位鍵全在（照片 4 鍵；收據 `amount`、`date`；合約含 `rental_terms` 及其子欄位〔選項一〕）；文字層謄本 08 與租約的有值欄位與部署前同檔存檔相同 |
| C4 | 文件 | R3 | 對 `docs/api/INTEGRATION.md` grep | grep 輸出 | ①「該鍵不出現」「不帶值為空的鍵」「省略此鍵」「有租賃欄位時」及同義寫法，不再以「`document_fields` 缺鍵」的意思出現（`validation_warnings` 例外段除外）；正對照：同指令命中新寫法「固定帶鍵」；②版本行為 2.7.0 並說明本次改變；③§3.4、§3.5 不再要求讀 `pages[0].structured_data` 才能拿到固定鍵 |
| C5 | 謄本線上驗收基準 | R2 | `backend/data/transcript_samples/expected/*.json` | diff | 8 份基準以 `~/jgb-archive/bedrock-qwen-switch-20261028/s2/after1/transcript_acceptance/` 的存檔頁面用新程式重算更新；與舊基準比只多出空值的鍵 |

## 判分

- 空值＝`None`、`""`、`[]`（C2 (c) 另含 `{}`）。「相同」＝ JSON 序列化（鍵排序）後相等。
- C2 的 (b) 包含彙整後重算的 `needs_confirmation`、`extraction_confidence`、`field_confidences`、謄本 `transcripts`／`transcript_records`。

## 廣度

| 項目 | 類型 | 資料組（用／可用） | 不同輸入數 | 重複次數 | 輸入撰寫者 | 改前對照 |
|---|---|---|---|---|---|---|
| C1–C5 | 機制項 | — | — | — | — | — |

上位驗收方式：無。

- 本片只改回應的鍵是否出現，不改辨識內容，沒有使用者層成效宣稱，全部是機制項。
- C2 涵蓋 6 類、348 份線上真實回應；C3 確認部署後的線上程式與本機相同，並補 C2 涵蓋不到的頁面改動。

## 業主裁定（核可時）

| 問題 | 業主裁定（2026-10-29） |
|---|---|
| OQ1：固定的鍵是哪一組 | 「選項二」：只保留各頁 `structured_data` 實際有的鍵；非租約合約的 `rental_terms`、謄本解析失敗時的 `transcripts`／`transcript_records` 維持現況（主持人推薦，等級 C） |
| 部署 | 「選項二」即核可並授權部署線上機（主持人在選項說明中寫明「你回『選項二』，就代表核可這個做法，也同意我部署到線上機」） |
