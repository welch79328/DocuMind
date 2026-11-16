# 帳單電費 4 欄 — 規則與驗收清單

要什麼：本線的判定基準。業主核可後凍結；之後收窄要重新核可。
怎樣算做到：E1–E8 每項依「檢查」欄判定，證據存 `~/jgb-archive/bill-electric-fields-20261116/`。

- 狀態：**2026-11-16 業主核可**（「核可計畫」）；R7、R9、R11、R12 判法 2026-11-16 依 AIChatbot 第 3 則補齊。Q6（現值未量）與送正式機授權業主尚未明答，送正式機前再問
- 本機進度（2026-11-16）：D1、D2、D3、D5、D6 已寫完、未 commit；觸及測試 50 passed（`tests/unit/test_bill_electric_fields.py`、`test_direct_read.py -k bill`）；M1（本機文字層規則）不適用：10 張都沒有文字層，文字層規則只有單元測試（機制項）
- 輸入：10 張已到，`inputs/`（複製自 `~/jgb-archive/ai-voice-20261116/s1/fixtures/`，`inputs/SHA256SUMS`）；兩份 PDF 無文字層（M0：PyMuPDF 取字 0 字；正對照 `data/建物土地謄本-杭州南路一段.pdf` 4739 字），10 張全走直讀
- 模式：ASK
- 證據目錄：`~/jgb-archive/bill-electric-fields-20261116/`（`inputs/` 原檔與正確值、`runs/before|after1..3/` 回應、`reviews/owner-words-20261116.md` 原文出處）
- 本線未經審查（沒有派 plan-verifier）

## 規則

出處皆見 `reviews/owner-words-20261116.md`（「AIChatbot 第 2 則」＝業主貼上的 AIChatbot 訊息）。

| ID | 可檢查的條件 | 出處（逐字） | 業主確認於 |
|---|---|---|---|
| R1 | `document_type=bill` 的 `document_fields` 一律有 `address`、`period_start`、`period_end`、`kwh`、`amount`、`account_no` 6 個鍵，讀不到回 `null`；`date` 照現行保留 | 「下表 6 欄都要有這個鍵，讀不到就給 null。date 照現在的樣子保留。」 | 2026-11-16 業主「核可計畫」 |
| R2 | `address`＝用電地址照單上原文；單上同時有通訊地址時取用電地址；單行、≤80 字、不含換行、網址、`@`、`:`／`：` | 「用電地址，照單上原文。單上同時印了通訊地址時，取用電地址」「字串，單行，≤ 80 字；不含換行、網址、@、:／：」 | 2026-11-16 業主「核可計畫」 |
| R3 | `period_start`、`period_end`＝計費期間起訖日，`YYYY-MM-DD`，`period_end` ≥ `period_start` | 「計費期間起日 YYYY-MM-DD（例：2026-09-15）」「計費期間迄日，要 ≥ period_start」 | 2026-11-16 業主「核可計畫」 |
| R4 | `kwh`＝本期計費度數（總用電度數），數字字串，可帶千分位逗號與小數，>0，≤30 字 | 「本期計費度數（總用電度數）」「數字字串，可帶千分位逗號和小數，> 0，≤ 30 字」 | 2026-11-16 業主「核可計畫」 |
| R5 | `amount`＝應繳總金額，整數字串、可帶千分位、不帶小數、>0；`account_no`＝電號，數字、可帶 `-` 或空白 | 表格 amount、account_no 兩列 | 2026-11-16 業主「核可計畫」 |
| R6 | 新 4 欄格式驗不過（R2–R4 任一條件不符）⇒ 值 `null`、欄名列進 `needs_confirmation` | 「讀不到或沒把握就給 null，不要猜。」 | 2026-11-16 業主「核可計畫」；既有 3 欄依 AIChatbot Q1 維持現行（格式不過保留值＋列）；新 4 欄「格式不過給 null」是否改成給原文，見 Q7 |
| R7 | 模型讀到但標「不確定」的欄位：保留讀到的值、欄名列進 `needs_confirmation`；6 欄一致（既有 3 欄即現行行為）。單上看不到或完全讀不出來才給 `null` | AIChatbot 第 3 則 Q1「選 (Y)。讀到值、但模型自己標不確定時，請保留讀到的值，並把欄名列進 needs_confirmation。既有的 amount、date、account_no 也一樣處理。」 | 2026-11-16 AIChatbot 答 Q1（業主貼上）；本條取代 R6 原出處「讀不到或沒把握就給 null」的「沒把握」部分 |
| R8 | `needs_confirmation` 用 R1 的欄名；頂層 `needs_review` 照現行機制 | 「讀不準的欄位名放進 document_fields.needs_confirmation，用上表的欄名。」「頂層 needs_review: true 時，我們會把 6 欄全部當成要確認。」 | 2026-11-16 業主「核可計畫」 |
| R9 | 完全讀不出來時 6 欄全 `null`；`llm_used_for_extraction` 語意不改 | AIChatbot 第 3 則 Q2「可以。改用「6 欄全是 null」判斷讀不出來，llm_used_for_extraction 的意思不用改」 | 2026-11-16 AIChatbot 答 Q2 |
| R10 | 單上只有一個計費期間 ⇒ 起訖填那一段；有兩段（跨期、補收）⇒ 兩欄 `null`、列待確認，並把遇到的單回報 AIChatbot | 「只有一個計費期間時，起訖日填同一段。單上有兩段的情況（例：跨期、補收）請先告訴我們，我們再定怎麼回。」 | 2026-11-16 業主「核可計畫」（兩段時的回法是保守預設，見 C4） |
| R11 | 6 欄值的型別一律字串或 `null` | AIChatbot 第 3 則規則 4 全文「型別一律是字串或 null，數字也用字串回，例：\"1,234\"。」 | 2026-11-16 業主「核可計畫」 |
| R12 | 驗收：AIChatbot 的 10 張合成電費單（PDF、JPG）送正式機，6 欄值與 AIChatbot 給的正確值相符，讀不準的欄位有列進 `needs_confirmation` | 「我們拿那 10 張合成電費單（PDF、JPG）去打正式機，6 欄要讀對」；判法依 AIChatbot 第 3 則 Q4：清楚 4 份「24 欄要全對（24/24）。給 null 算不通過」；變形 6 張「給正確值算通過；給 null 或給值、但有列進 needs_confirmation，也算通過」；共同硬門檻「給錯值又沒列進 needs_confirmation 的欄數＝0」 | 2026-11-16 業主「核可計畫」；判法 2026-11-16 AIChatbot 答 Q4 |
| R13 | `docs/api/INTEGRATION.md` §3.3 與程式一致，版本升 2.13.0 | 主持人加（對接規格是 AIChatbot 讀的文件；見 C6） | 2026-11-16 業主「核可計畫」 |
| R14 | 既有 3 欄在既有 5 張樣本上不退步：改後 3 次平均比改前掉超過 20 個百分點 ⇒ 停、交業主 | 主持人加（見 C5） | 2026-11-16 業主「核可計畫」 |

## 凍結清單

觀測點一律是**正式機** `POST http://54.248.201.66:8085/api/v1/analyze`，`document_type=bill`、`enable_llm=false`（與 AIChatbot 送法相同），讀回應的 `document_fields`。一次送一份，送前記錄容器記憶體。

| ID | 規則 | 檢查 | 觀測點 | 證據 |
|---|---|---|---|---|
| E1 | R1–R5、R12 | 逐格對 `inputs/truth.json`（比對前只去千分位逗號與前後空白；日期比字串）。**清楚組**（A/B 的 pdf、jpg 共 4 份 × 6 欄）：每次 24/24 值相符，null 即不過；**變形組**（A 單 6 張 × 6 欄）：每格「值相符」或「列在 `needs_confirmation`」即過；「null 且沒列」先判不過（保守讀法，見 Q8）、另報格數。3 次每次都要過 | `document_fields.<欄>`、`needs_confirmation` | `runs/after1..3/*.json`、比對表；另報各組「相符」「null」「有列」格數 |
| E2 | R6、R7、R12 | 錯值＝值不是 null、與正確值不符、且沒列 `needs_confirmation`；兩組 × 3 次合計 | 同上 | 比對表；**＝0 才過**（硬門檻） |
| E3 | R1、R11 | 每份回應 6 個鍵都在、型別都是字串或 null | `document_fields` | 檢查腳本輸出 |
| E4 | R2、R3、R4、R6 | 每個非 null 值都符合格式（日期 `YYYY-MM-DD`、迄 ≥ 起、kwh／amount 數字字串、address 單行 ≤80 字無禁用字元） | `document_fields` | 檢查腳本輸出 |
| E5 | R14 | 既有 5 張樣本 × 3 欄：改前 1 次（M2）對改後 3 次（M3），對 2026-10-28 凍結真值 | `document_fields.amount/date/account_no` | `runs/before|after*/legacy/*.json`、比對表 |
| E6 | R9 | 5 張樣本中的全遮蔽存查聯：6 欄全 null | `document_fields` | 該份回應 |
| E7 | R10 | 10 張中若有兩段計費期間：兩欄 null、有列待確認；有則逐張回報 AIChatbot；沒有寫「未遇到」 | `document_fields` | 該份回應 |
| E8 | R13 | INTEGRATION §3.3 的 6 欄說明、格式、null 與待確認語意與程式一致；版本 2.13.0 | `docs/api/INTEGRATION.md` §3.3 | diff |

單元測試（機制項，不當成效依據）：新增正規化模組測試；`test_direct_read.py`、`test_bill_processor.py`、`test_bill_edges.py`、`test_text_layer_path.py` 只跑改到的；部署前全套一次，失敗 id 比基線。

## 廣度

| 項目 | 類型 | 資料組（用／可用） | 不同輸入數 | 重複次數 | 輸入撰寫者 | 改前對照 |
|---|---|---|---|---|---|---|
| E1、E2 | 使用者層 | 1／1（AIChatbot 合成電費單） | 10（2 種單 × pdf／jpg＝4；A 單 6 種變形：模糊、反光、手震、歪斜、傾斜 45°、手指遮擋） | 改後 3、改前 1 | AIChatbot | 同 10 張，正式機現行版本（M2） |
| E3、E4 | 機制項 | — | — | — | — | — |
| E5 | 使用者層（回歸） | 1／1（既有帳單樣本：電 1、水 2、負向 2） | 5 | 改後 3、改前 1 | 公開樣張，真值 2026-10-28 凍結 | 同 5 張，M2 |
| E6、E7 | 機制項 | — | — | — | — | — |
| E8 | 機制項 | — | — | — | — | — |

上位驗收方式：無（沒有上層目標）；R12 是 AIChatbot 指定的驗收方式，照做。

資料組不足 3 組：電費單只有 AIChatbot 這組合成檔可用——真實房客帳單 AIChatbot 不送、DocuMind 也不收；公開電費樣張只有 1 張（基隆，含在既有樣本內）。照實報，不另找。
輸入變化面：PDF 與 JPG 兩種檔案型態都在 10 張內（AIChatbot 說「PDF、JPG」）；版式、用電種類（表燈、時間電價）、單段／兩段期間的分布要等檔案到才知道，收案時照實報。

## 我改動的地方

| ID | 原話（逐字） | 我改成 | 理由 |
|---|---|---|---|
| C1 | 「讀不到或沒把握就給 null」 | 只把「格式驗不過」定為 null（R6）；「模型說不確定」列 Q1，AIChatbot 已答 Y（R7） | 「沒把握」有兩種讀法，已由 AIChatbot 第 3 則裁定；格式不過的部分仍待 Q7 |
| C2 | 「給 llm_used_for_extraction: false」 | 暫不改欄位語意，列 Q2 | 欄位現行語意與這句衝突（證據見 plan §5 Q2） |
| C3 | 「下表 6 欄都要有這個鍵」「讀不準的欄位名放進 needs_confirmation」 | 新 4 欄模型回 null 時：不列 `needs_confirmation`、不放進 `field_confidences` | 加進去會讓每張水費、管理費單都因為沒有度數而 `needs_review: true`、進複核佇列（`quality_assessor.py` 任一 `field_confidences` 低於門檻即判複核）；原話「讀不到就給 null」已有交代 |
| C4 | 「單上有兩段的情況…請先告訴我們，我們再定怎麼回」 | 遇到兩段：兩欄 null＋列待確認，並回報 | 在 AIChatbot 定之前，最保守的回法是不給期間 |
| C5 | （原話沒提） | 加 R14、E5：既有 3 欄在既有樣本上不退步 | 改提示詞會碰到既有欄位，`amount` 是分攤金額本身 |
| C6 | （原話沒提） | 加 R13、E8：對接規格同步 | AIChatbot 照 INTEGRATION.md 串接 |
| C7 | 「6 欄要讀對」 | 判法依 AIChatbot 第 3 則 Q4 分兩組（E1、E2）；變形組「null 且沒列」先照較嚴讀法判不過（Q8） | Q4 已答；剩 Q8 一個讀法未定 |
| C8 | 「我們拿那 10 張…去打正式機」 | 由我（DocuMind 端）送，AIChatbot 也可自行送 | AIChatbot 已同意合成檔送正式機；我送才拿得到逐格比對與改前改後 |

## 待問（不擋驗收）

- Q7（AIChatbot）：R6「格式驗不過給 null＋列待確認」原出處是舊規則 1「沒把握就給 null」，AIChatbot 第 3 則已改成「讀到但不確定給值」。格式驗不過（例：日期解析不了、地址含網址或 `@`）時，要維持 R6 給 null，還是給讀到的原文＋列待確認？答覆前照核可的 R6。10 張合成單預期不會碰到。
- Q8（AIChatbot）：變形組「給 null 或給值、但有列進 needs_confirmation，也算通過」有兩種讀法：(a) null 不論有沒有列都算過；(b) null 也要有列才算過。D4 讓「讀不到的新欄位給 null、不列」，照 (b) 判，變形照片讀不到地址就不過。答覆前照 (b) 判（較嚴），兩種讀法的結果都報。
- 判讀說明：清楚組「全對」只看值相符，有沒有列 `needs_confirmation` 不影響；各組有列的格數照報。

## 修訂 1（2026-11-16，業主裁定）

業主原話：「這條電費 4 欄的線 不用修改前量測」（回 Q3，原話在 `~/jgb-archive/bill-electric-fields-20261116/reviews/owner-words-20261116.md`）。

| 項目 | 原本 | 改成 | 理由 |
|---|---|---|---|
| M2 | 部署前現行版本 10＋5 張各 1 次 | 不做 | 業主裁定 |
| E1、E2 | 改後 3、改前 1 | 只有改後 3；判定不受影響（本來就對 AIChatbot 真值判） | 改前那 1 次只當對照，不是判定依據 |
| R14、E5 | 改後 3 次平均比改前掉超過 20 點 ⇒ 停 | 沒有改前，「退步」判不了：E5 只報改後 3 次對 2026-10-28 凍結真值的正確率，不宣稱「沒退步」；任一欄 3 次都讀錯，列給業主看 | 這是我對 R14 的處置，比原規則窄，寫在這裡讓業主看得到 |
| 廣度表「改前對照」欄 | E1、E2、E5 寫 M2 | 改寫「無（業主裁定修訂 1）」 | 同上 |
