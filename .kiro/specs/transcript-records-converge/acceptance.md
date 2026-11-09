# 謄本輸出收斂＋欄位位置——規則與驗收清單（2026-11-09 核可凍結）

狀態：2026-11-09 業主核可，凍結；之後收窄要重新核可。計畫見同目錄 `plan.md`。
量測檔一律在 `~/jgb-archive/transcript-photo-fullparse-eval-20261109/runs/`（以下簡寫 `runs/`），檔首有指令、執行時間、受測物版本。

## 1. 規則（業主原話 → 可檢查條件）

業主原話全部出自 2026-11-09 本 session 對話；AskUserQuestion 的題目與選項文字照錄。新格式由 `/api/v1/analyze` 新增的表單參數 `transcript_format`（暫名，唯一合法值 `"v2"`）取得，以下稱「帶參數」；不帶參數＝現在的回應（名稱可改，見「我改動的地方」）。

| ID | 可檢查條件 | 業主原話（出處） | 讀法註記（收窄／放寬／擇一） | 業主確認於 |
|---|---|---|---|---|
| R0 | 前置：先改正誤導文件，再規劃規格。`docs/README.md`、`docs/api/INTEGRATION.md` 2.8.1、`docs/planning/transcript-status.md`、`docs/testing/transcript-online-acceptance.md`、評估報告 `docs/testing/transcript-photo-fullparse-eval-20261109.md` 的修正已完成（業主選「現在 commit」，已 commit `49faf53`，分支 `transcript-converge`） | 「先更新錯誤誤導文件 在規劃規格」 | 要不要先 commit 交業主決定（commit 不在授權內） | 2026-11-09 業主核可確認版（AskUserQuestion「核可」） |
| R1 | 帶參數時，`document_fields.transcript_records` 每張謄本＝不帶參數時該張的值，再把全文讀不到、而規則（25 欄／6 種清單）有值的格補上。補法限：(a) 單值欄位只在整份回應只有 1 張謄本時補；(b) 清單只在該張對應陣列是空的時整組補，且只取 `transcript_id` 等於該張編號（或清單沒有 `transcript_id`、且只有 1 張）的項目；(c) 全文已有值的格不覆蓋；(d) 鍵名以「日期」結尾的格，值須含年、月、日三段數字才補。對應表見計畫 §3 S1 | 「DocuMind 謄本輸出收斂」（選項描述「讓下游只讀一處：transcript_records 在全文讀不到時用規則抽的值補上」）；「我要做」；第四題（11-09）選「帶參數換格式」（描述「/analyze 加一個參數（名稱再定）；不帶＝現在的回傳完全不變，帶了＝transcript_records 換成補值＋每值旁邊有位置。同一份回應只有一種謄本結構。這和你先前選的「收斂結果放新鍵」不同：不加新鍵，改成帶參數才換格式」）（取代先前「收斂結果放新鍵」） | **收窄**：(a)(b) 對不到哪一張就不補（照片多張時單值欄位不補）；規則沒有對應鍵的格補不了。**擇一（技術判斷）**：(c) 兩邊都有值以全文為準；(d) 擋規則切壞的值（原型量到 `建築完成日期`＝「民國」1 例） | 2026-11-09 業主核可確認版（AskUserQuestion「核可」） |
| R2 | 不帶參數的回應不變：`document_fields` 的每一個鍵（含 `transcript_records`、25 欄、6 種清單、`transcripts`、`field_confidences`、`needs_confirmation`、`needs_review`）在電子 PDF 與照片上改前改後逐位元相同；其他文件類型與 `/analyze/batch` 不受影響 | 第二題選項描述「AIChatbot 正式機完全不受影響」；「只改 DocuMind＋交規格」；第四題描述「不帶＝現在的回傳完全不變」 | **放寬**：業主只講 AIChatbot；jgb2 staging 也讀這些鍵（`TranscriptFieldMapper.php`），一併不變 | 2026-11-09 業主核可確認版（AskUserQuestion「核可」） |
| R3 | 不新增信心度、來源或任何標記欄位 | 「這次不附任何標記」 | 比最早選項描述的「每個值附信心度」**窄**：業主已改選，依據 2026-11-09 實驗（`runs/linescore_result.txt`） | 2026-11-09 業主核可確認版（AskUserQuestion「核可」） |
| R4 | 位置只附在帶參數的 `transcript_records`，放在每個值旁邊：每個有值的葉子寫成 `{"value": <原值>, "position": {"page": 1 起算, "box": [x0,y0,x1,y1] 0～1 比例, "unit": "ratio"}}`；找不到位置時 `position` 給 `null`；沒有值的葉子照舊是 `null`。程式判斷的 `判定`、`部是否印出` 不是謄本上印的值，維持原樣不包 | 早先選「併進來一起做」（JGB 需求原文：「能不能在回傳的每一筆結果裡加上位置資訊？建議格式如下…"position": { "page": 1, "box": [x0, y0, x1, y1], "unit": "ratio" }…找不到位置的欄位可以不給，或給 null」）；第二題選「只附在收斂結果」；第三題（2026-11-09）選「照 JGB 放每個值旁邊」；第四題選「帶參數換格式」 | **擇一（技術判斷）**：值的鍵名用 `value`（JGB 沒給，與 `position` 同用英文）；找不到給 `null`，不省略；`判定`、`部是否印出` 不包（見「我改動的地方」） | 2026-11-09 業主核可確認版（AskUserQuestion「核可」） |
| R5 | R4 對電子 PDF 與照片／掃描都做：電子 PDF 框到值本身；照片／掃描框到值所在的那一行 | 「電子 PDF＋照片都做」（選項描述「電子 PDF 框到『值』本身…照片、掃描框到『那一行』…讀不到的值沒有位置」） | — | 2026-11-09 業主核可確認版（AskUserQuestion「核可」） |
| R6 | 規格公告五種舊格式棄用：不帶參數時回的 25 欄、6 種清單、`transcripts`、`transcript_records`（舊形狀）、`pages[].structured_data` 的 25 欄與清單（只限謄本）；寫明下游改帶參數、移除條件（下游都改帶參數並經業主確認後，另開一片把預設改成新格式並拿掉舊格式）；本線不移除、不改預設 | 「下游改完後棄用移除」＋「本線只公告棄用」；第二題選項描述「舊的四種（含現在的 transcript_records）一起公告棄用」；第五題題目把舊格式定義為「document_fields 裡的 25 欄、6 種清單、transcripts，和每頁 pages[].structured_data 裡的 25 欄與清單」 | 比「棄用移除」**窄**：實際移除另開一片，業主已選。**放寬**：四種→五種，多 `pages[].structured_data` 的 25 欄與清單，依第五題定義；**只限 `document_type=transcript`**（合約、帳單等也用 `structured_data`，不在棄用範圍） | 2026-11-09 業主核可確認版（AskUserQuestion「核可」） |
| R8 | 帶參數時，回應不含舊格式：`document_fields` 不含 25 欄、6 種清單、`transcripts`；每頁 `pages[].structured_data` 只拿掉舊欄位（`TranscriptFieldExtractor.KEY_FIELDS` 的 25 欄＋`analyze_service._LIST_DETAIL_KEYS` 的 6 種清單），其餘鍵全留（含 `validation_warnings` 等旗標）；`structured_data` 本來是 `null` 的頁照舊；每頁其他內容（全文、頁碼等）照回；`document_fields` 的 `field_confidences`、`needs_confirmation` 與回應頂層的 `needs_review`、`field_confidences` 與不帶參數相同；`review_item_id` 是否為 `null` 與不帶參數相同；複核佇列存的內容與不帶參數相同 | 第四題描述「同一份回應只有一種謄本結構」；第五題（2026-11-09）「帶了 transcript_format=v2 的回應，舊格式要不要一起回？舊格式指 document_fields 裡的 25 欄、6 種清單、transcripts，和每頁 pages[].structured_data 裡的 25 欄與清單」選「都不回」（描述「帶參數只拿得到新的 transcript_records；每頁的全文、頁碼等照回，只拿掉 structured_data 裡的舊欄位。就是你選的「同一份回應只有一種謄本結構」。我會加一項驗收，確認複核佇列不受影響」） | 依第五題選項原文「只拿掉 structured_data 裡的舊欄位」：拿掉的鍵以既有常數界定（`KEY_FIELDS` 25 欄＋`_LIST_DETAIL_KEYS` 6 種清單），其餘全留；第 6 輪收尾審查後業主重新核可 | 2026-11-09 第 6 輪收尾審查後業主重新核可（AskUserQuestion「改成只拿掉舊欄位」） |
| R7 | 更新對接規格，並擬一段給 JGB 的說明；轉不轉、何時轉由業主決定 | 「等等驗證完回提供給 JGB 規格再讓他們調整」；「只改 DocuMind＋交規格」 | 「驗證完」讀成本線收案 verifier 通過後才交（規格要寫的是做出來的樣子，先交會與實作不符） | 2026-11-09 業主核可確認版（AskUserQuestion「核可」） |

## 2. 驗收清單

照片評分一律以「同頁文字層走同一條路的輸出」為標準答案；多張謄本依編號對齊（`proto_fill.py` 的 `sheet_keys`）。

**照片受測路徑（C1–C4、C6、C7 照片部分，固定）**：`~/jgb-archive/transcript-photo-fullparse-eval-20261109/measure_s1.py`，與 `analyze_service` 對 OCR 頁的處理相同：每頁 `TranscriptProcessor.analyze`（只把 `preprocess`／`extract_text` 換成回傳已存 OCR 文字 `runs/A/<頁>.txt` 與各行分數平均；其餘照跑：`postprocess`（`TranscriptPostprocessor`，`enable_llm=False`）→ `extract_fields` → `_apply_consensus`／`_apply_correction_confidences`／`_apply_field_validation`）→ `_merge_page_structured_data(pages)` → `_attach_full_transcripts(document_fields, pages, "transcript")`。改前＝`ab38a55` 跑這條路的 `transcript_records`；改後＝實作後同一條路、帶參數回的 `transcript_records`（還原 `value` 後評分，不再呼叫原型 `fill`）。電子路徑：`extract_text_layer_pages` → `AnalyzeService._extract_fields_for_text_layer` → 同上合併與組裝（C5、C6 另以本機 HTTP 再驗）。

| # | 規則 | 驗收項目 | 觀察點 | 證據型態 |
|---|---|---|---|---|
| C1 | R1 | 照片 15 頁（各頁單獨送）帶參數 `transcript_records` 葉值 816 格（還原 `value` 後）：讀對 ≥ 167、錯值 ≤ 7、標準答案沒有而多出的值＝0；**每一個錯值都要與同一份文件不帶參數時舊欄位的值相同**（補值不新增錯，只把舊欄位已有的錯帶進來），有任何一個不同即不過 | 上方「照片受測路徑」 | 評分腳本輸出（改前、改後並列，逐格列錯值與「舊欄位有同值」） |
| C2 | R1 | 照片依文件合併 5 份（D1–D5）帶參數葉值 703 格：讀對 ≥ 101、錯值 ≤ 2、多出＝0，錯值同樣須與舊欄位值相同 | 同 C1 | 同 C1 |
| C3 | R1 | 只讀帶參數的 `transcript_records` 取 jgb2 表單 8 格（15 頁中各頁單獨送，7 個建物頁共 26 格，取法照 jgb2 `TranscriptFieldMapper`）：讀對 ≥ 9/26、錯 0。`runs/s1_prodpath.txt` 裡「5 份合併」的 8 格列不採用：評分腳本把多張的層次接在一起取第 2–4 筆，照片與答案張數不同時會錯位（D3 照片 4 張、答案 3 張），不代表 jgb2 取法 | 同 C1 | 評分腳本輸出 |
| C4 | R1 | 帶參數的 `判定`（他項權利／限制登記／信託，15 頁 45 格）：與標準答案相同 ≥ 40/45；與標準答案不同的格只能是「無法判定」——評分腳本逐格列出不同的格並計「判定不同且非無法判定」，須＝0 | 同 C1 | 評分腳本輸出 |
| C5 | R1、R2 | 電子 PDF 5 份（17 頁）整份送入：帶參數的 `transcript_records` 把每個 `{"value","position"}` 還原成 `value` 後，與不帶參數的 `transcript_records` 逐位元相同 | 本機 `/api/v1/analyze`（真實 HTTP） | diff（應為空） |
| C6 | R2、R8 | 電子 5 份＋照片 15 頁：不帶參數時改前、改後 `document_fields` 逐位元相同；帶參數時，`document_fields` 中 `transcript_records` 以外的鍵與不帶參數時去掉 25 欄、6 種清單、`transcripts` 後逐位元相同；`pages[]` 每頁除 `structured_data` 拿掉舊欄位外與不帶參數逐位元相同（留下的鍵值也相同）；回應頂層其他鍵相同 | 電子用本機 HTTP；照片用 C1 同一段組裝 | diff（應為空） |
| C7 | R2 | AIChatbot `origin/main` 的 `documind_client.extract_deed_fields` 對改前、改後（不帶參數）回應的輸出相同（電子 5 份＋照片 15 頁） | 本機呼叫該函式 | 指令輸出 |
| C8 | R1、R2、R4 | 帶參數的 `transcript_records` 每張謄本還原 `value` 後通過 `docs/api/transcript_records.schema.json`；包裝後的每個葉子不是 `null` 就是恰有 `value`、`position` 兩鍵的物件，`position` 不是 `null` 就是 `{page, box, unit}` 且 `page` 為 ≥1 整數、`box` 4 個 0～1 數字、`unit`＝`"ratio"` | 驗證腳本 | 指令輸出 |
| C9 | R3、R8 | 不帶參數：鍵集合改前改後相同。帶參數：`document_fields` 鍵集合＝不帶參數的鍵集合 −｛25 欄、6 種清單、`transcripts`｝，沒有新增鍵；每頁 `structured_data` 的鍵＝不帶參數同頁的鍵減去 25 欄與 6 種清單（單元測試含一頁帶 `validation_warnings`，帶參數後仍在）；`transcript_records` 內的鍵＝既有鍵＋葉子的 `value`、`position`（無信心度、來源類）。參數值不是 `"v2"` ⇒ 400、`error_code`＝`INVALID_TRANSCRIPT_FORMAT`；`document_type` 不是 `transcript` 時帶參數 ⇒ 回應與不帶相同 | 回應 JSON 鍵集合 diff＋本機 HTTP | diff＋指令輸出 |
| C10 | R4、R5 | 電子 PDF（帶參數）：每個 `position` 非 null 的值，用 PyMuPDF 取 `box` 範圍內文字，正規化後與該 `value` 相同的比例 ≥ 95%；有值的葉子中 `position` 非 null 的比例 ≥ 95% | 本機回應＋原 PDF | 驗證腳本輸出（逐格對／錯／null） |
| C11 | R4、R5 | 照片：用劣化時記下的頁面四角（`images/degraded/*.json`），把同一格在電子 PDF 上的值框投影到照片座標；照片回的行框包含投影後值框中心點的比例 ≥ 90%；有值路徑中有位置的比例照實報 | 本機回應＋四角 | 驗證腳本輸出 |
| C12 | R4、R5 | 展示項（不作宣稱依據、不擋收案；位置的使用者層宣稱由 C10、C11 承擔）：照片在原圖上畫出回傳的 `position` 框，3 張（3 種劣化各 1、來自 3 份不同文件）截圖給業主看 | 標註後截圖 | PNG（`shot-annotate`） |
| C13 | R6、R7、R8 | `INTEGRATION.md` 升 2.9.0：寫明參數 `transcript_format`、帶參數時 `transcript_records` 的形狀與 `position` 格式、帶參數時不回的舊格式（含每頁 `structured_data` 的 25 欄與清單）、五種舊格式棄用（只限謄本）與移除條件、照片 `needs_confirmation` 抓不到 OCR 讀錯；新增帶參數格式的 schema；附給 JGB 的說明草稿 | 文件 | 文件 diff＋grep（與新規格相反的舊陳述 0 命中，含同義改寫；正對照命中） |
| C15 | R2、R8 | 複核佇列不受影響：同一份低信心照片（D3、D4、D5 各 1 頁，本機）帶與不帶參數各送一次，`needs_review`、`field_confidences` 相同，兩個複核項目的 `original_result` 逐位元相同（帶參數那份的 `pages[].structured_data` 仍是完整舊欄位）；3 份都沒產生複核項目 ⇒ 不過，另換低信心頁重跑 | 本機 `/api/v1/analyze`＋本機 DB `review_queue` | diff（應為空） |
| C14 | R1–R5 | 線上確認（業主同意才做，會寫入正式機複核佇列）：部署後送電子 PDF 3 份（D1、D2、D3）＋照片 3 張（3 種劣化各 1、來自 D3、D4、D5），C5、C6、C10、C11 的判定在線上回應成立 | 線上 `/api/v1/analyze`（帶與不帶參數各送） | 回應 JSON＋判定輸出 |

## 3. 門檻（跑前定）

C1–C4 的數字＝原型 `proto_fill.fill`（含日期通則 (d)、「屬於該張」照 R1(b)，sha1 `0625ac32f1c4`）放在上方「照片受測路徑」上量到的值（`runs/s1_prodpath.txt`，2026-11-09 10:58，受測物 `ab38a55`，檔首有指令；各單位改前／改後 `document_fields` 存 `runs/s1_prodpath/`）。受測路徑與正式程式相同、只差補值函式，所以正式實作低於門檻表示實作與對應表不符。C1 的「錯值須與舊欄位值相同」是硬條件：原型 7 個不等於答案的格全部與舊欄位同值（含後處理把「黃**」讀成「黃」2 例）。C10 95%、C11 90% 為主會話提議、無業界依據：電子逐字框是精確資料，低於 95% 表示對位邏輯有系統性錯誤；照片行框受 OCR 斷行影響，留 10% 空間。

## 廣度

| 項目 | 類型 | 資料組（用／可用） | 不同輸入數 | 重複次數 | 輸入撰寫者 | 改前對照 |
|---|---|---|---|---|---|---|
| C1–C4 照片補值 | 使用者層 | 5／5 份真實電子謄本做成的照片 | 15 頁（3 種劣化各 5）＋5 份整份合併 | 1（OCR 文字固定、組裝程式決定性） | 劣化規格由看不到實作的代理依真實拍照情境寫成、2026-11-09 凍結；主會話照規格產圖；實作者（executor）不碰輸入 | 同一批輸入，改前 `ab38a55` |
| C10、C11 位置 | 使用者層 | 5／5 份 | 電子 17 頁；照片 15 頁 | 1 | 同上 | 改前沒有位置 |
| C14 線上 | 使用者層 | 5／5 份（電子 D1–D3、照片 D3–D5） | 6 | 1 | 同上 | 線上改前版本 |
| C5–C9、C13、C15 | 機制項 | — | — | — | — | — |
| C12 截圖 | 展示項（不作宣稱） | — | — | — | — | — |
| 收案 verifier | 使用者層 | 5 份 | 另產 ≥10 張沒出現過的劣化照（不同亂數種子、換頁、換劣化類型） | 1 | verifier 自產 | 改前 `ab38a55` |

C14 達下限（資料組 5／5、輸入 6 ≥ 5）；不再加量的理由：線上 OCR 每頁 15–24 秒、多頁連送會 OOM（`transcript-status.md` §5「線上機規格」列），每份都寫進正式機複核佇列。
上位驗收方式：無。目標正本 `docs/planning/transcript-status.md` 沒有規定本線的量法；`.kiro/specs/transcript-full-parse/acceptance.md` 的「電子檔 0 遺失」由 C5、C6 逐位元不變承接。

## 我改動的地方

| 業主原話（出處） | 我改成什麼 | 理由 |
|---|---|---|
| 「transcript_records 在全文讀不到時用規則抽的值補上」 | 多張謄本時單值欄位不補；清單只在空陣列時整組補；全文有值不覆蓋；日期鍵要有年月日數字 | 對不到哪一張就不猜；逐筆合併會錯位；全文錯得少；擋掉規則切壞的值 |
| 同上（「規則抽的值」） | **我加的**：`類型` 由 `building_number`／`land_number` 有無推定（1 張且為 null 時） | 這不是規則抽到的值，是推出來的；沒有類型就不知道該建建物還是土地的骨架，後面所有補值都做不了 |
| 同上 | **我加的**：`謄本.編號` 由 `building_number`／`land_number` 補（1 張且為 null 時） | 屬規則抽的值，但補到頁首；清單要靠編號對到哪一張 |
| 同上 | **我加的**：`標示部` 整個是 null 時建固定鍵骨架（清單鍵 `[]`、其餘 null） | 不建就沒有格可補；骨架鍵與 `transcript_records` 固定鍵相同（C8 驗 schema） |
| 同上 | **我加的**：補值後用既有 `_verdicts` 重算 `判定` | 不重算，補進的他項權利不會反映到判定；實測 35→40/45，與答案不同的 5 格全是「無法判定」（C4 守） |
| 同上 | **排除**：`section`／`subsection` 不補到 `謄本.段`／`小段` | 已知遇平鎮區等會切錯（`transcript-status.md` §5） |
| 同上 | **排除**：`print_date` 不補到 `謄本.列印時間` | 規則只到日、records 到分，格式不同，補進去會變成另一種值 |
| 同上 | **排除**：`seizure_mark` 不補 | 限制登記判定只依原文的部，規則標記不能改判定（說錯「無」會直接改變判斷，`transcript-status.md` §2 判定列） |
| 「AIChatbot 正式機完全不受影響」 | 加上 jgb2 staging 也不受影響（R2 範圍放寬） | jgb2 staging 讀同一批鍵 |
| JGB「每一筆結果裡加上位置資訊」「找不到位置的欄位可以不給，或給 null」（業主 2026-11-09 裁：照 JGB 放每個值旁邊） | 值的鍵名用 `value`（我取的）；找不到一律給 `null`；`判定`、`部是否印出` 不包 | JGB 只給了 `position` 的格式；給 `null` 才分得出「有值沒位置」與「沒值」；判定與部是否印出是程式判斷，謄本上沒有對應的位置 |
| 同上 | 帶參數時 `transcript_records` 每個值多包一層，jgb2 staging 已寫好的 mapper 改帶參數時要改取 `value` | 業主裁定的代價，照實寫進規格與給 JGB 的說明 |
| 「電子 PDF＋照片都做」 | 照片框到行、不框到字 | PaddleOCR 只回行框；以字數比例切字框是估計值，不宣稱精確（業主選項描述同此） |
| 「/analyze 加一個參數（名稱再定）」 | 參數名 `transcript_format`、唯一合法值 `"v2"`，我取的；其他值回 400；非謄本類型帶了忽略 | 業主說名稱再定；值用版本號，之後再改格式可加 `"v3"`；錯值明確報錯比默默忽略好查 |
| 同上 | 只加在 `/analyze`，不加 `/analyze/batch` | 批次端點預設點交照片、規格沒有謄本批次用法；要加請說 |
| 「本線只公告棄用」 | 移除條件我寫成「AIChatbot 與 jgb2 都改帶參數，並經業主確認」，移除方式＝另開一片把預設改成新格式並拿掉舊格式；不訂固定日期 | 已知下游只有兩家；與 Azure／Google 的固定日期不同（計畫偏離 D4） |
| 「等等驗證完回提供給 JGB 規格」 | 「驗證完」＝本線收案 verifier 通過 | 規格描述的是做出來的樣子 |
| 「電子 PDF＋照片都做」 | 真實掃描件不驗（非目標） | 手上沒有真實掃描樣本；掃描與照片走同一條 OCR 路徑；`transcript-status.md` §1 定案掃描件排在升級機器之後 |
| 第五題「我會加一項驗收，確認複核佇列不受影響」 | **我加的**：轉格式放在信心度攔截之後，對整份結果深拷貝再轉（C15 驗） | 攔截讀每頁 `structured_data`、複核佇列存同一份 `pages`（`analyze.py:162`、`:190-195`）；先轉會讓複核畫面變空 |
| 第二題「舊的四種」＋第五題的舊格式定義 | 棄用清單從四種放寬成五種，多每頁 `structured_data` 的 25 欄與清單；只限謄本 | 業主第五題把它算進舊格式；其他文件類型不在本線 |
| C10 95%、C11 90% 門檻、C14 線上確認 | 我加的 | 門檻無業界依據（§3）；線上確認會寫入複核佇列，需你同意 |

## 核可後更正（2026-11-09，S1 驗收中）

本節只增不改上方凍結內容；與上方衝突時以本節為準。

| ID | 更正 | 業主確認於 | 理由與證據 |
|---|---|---|---|
| AM-1 | **C8 改驗「帶參數格式 schema」**：與 `docs/api/transcript_records.schema.json` 相同，唯 `標示部.層次[].層次`、`標示部.層次[].面積`、`標示部.附屬建物[].用途`、`標示部.附屬建物[].面積` 可為 `null`（規則讀得到面積、配不上名稱時照補、名稱給 `null`，同清單 `floors`「名稱沒配上時 `level` 為 `null`、`area` 照給」）。舊 schema 不改；帶參數格式 schema 檔在 S4 交付，S1 由驗收腳本以同一規則衍生。C1–C3 門檻不變。**放寬**：比原 C8「通過現有 schema」寬 | 2026-11-09 業主選「補，名稱空就給 null」（AskUserQuestion） | 照片實測照現有 schema 整組不補時 C1 167→162、C2 101→96、C3 9→6/26（`scratchpad/converge/transcript_records.allornone.py` 版實跑）；D3p5 5 層面積讀對、名稱全為 null |
| AM-2 | 補進的 `所有權部`、`他項權利部` 筆與新建 `標示部` 骨架，陣列鍵給 `[]`（`管理者`、`相關他項權利登記次序`、`前次移轉現值` 等，與建構器同一規則 `_blank_entry`）；補進的 `共有部分` 筆帶齊固定鍵（`坐落`、`其他登記事項`，`_blank_shared_part`） | 技術修正，不改業主規則（使形狀符合 R4「還原後形狀與現有相同」） | 原型與第一版實作給 `null`／缺鍵，照片 C8 有 11 頁不過；修正後只剩 AM-1 的情形 |
| AM-3 | **C10 判定細節（S2）**：(1)「`box` 範圍內文字」＝該頁 `rawdict` 逐字框中心點落在 `box` 內的字元，依原順序串接；(2)「正規化」＝`normalize_for_matching` 後去掉所有空白；(3)「相同」＝正規化後字串相同，`value` 是數字時 `to_number(框內文字)` 等於 `value` 也算相同（**放寬**：框到「1,426.05」算與 1426.05 相同）。(4) R4/R5 在電子檔的處理：對不到值本身 ⇒ `position: null`（不給近似框）；`謄本.頁數`（頁次出現次數）⇒ `null`；電子檔上補進的值 ⇒ `null`（補值定位屬 S3）；頁首標籤字與其他登記事項子標籤當值時框該標籤字；值跨頁只框第一頁那幾段；單頁對位任一步不一致 ⇒ 該頁 `null` | 2026-11-09 業主核可 S2 並選「轉成數字相等就算對」（AskUserQuestion） | 凍結 C10 沒定義框內與正規化；不放寬數字時，帶千分位或小數尾 0 的值（例 `1,426.05平方公尺` → 1426.05）都會算成不相同；`plan-s2.md` §1、§7 |
