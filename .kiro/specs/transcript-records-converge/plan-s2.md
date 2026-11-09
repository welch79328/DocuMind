# S2 電子 PDF 位置——片計畫（2026-11-09 業主核可）

本片是 `plan.md` program envelope 的 S2（envelope 與 S1 於 2026-11-09 業主核可）。規則與驗收清單照 `acceptance.md`（凍結＋檔尾「核可後更正」），本片不改規則；本檔只寫做法、量法與本片才要定的細節。量測檔目錄 `~/jgb-archive/transcript-photo-fullparse-eval-20261109/`（簡寫 `E/`）。

## 0. 目標正本定位

目標正本：`docs/planning/transcript-status.md`。
- 碰到的原則（§1）：「電子謄本上印的每一項都要解析出來、而且讀對」——本片在帶參數的 `transcript_records` 每個值旁附電子檔位置，不改值；「修法一律通用，不打特規」——字元位置以「逐字正規化」對回原文，不列字元清單（`memory/general-fix-not-local-patch.md`）。
- 碰到的待辦列（§5）：無新增；本片服務 envelope §3 S2 列「JGB 欄位位置需求」。
- 已知偏離：目標正本沒有編號的已知偏離；本片不屬過渡修正。
- 終點的目標文件：`acceptance.md`（envelope §5 已點名）。

風險觸發：資料／序列化格式（帶參數回應的 `position` 從一律 `null` 變成有值）＋跨元件驗收（AIChatbot 正式機、jgb2 staging 讀不帶參數的回應，必須不變）→ 送審前派 plan-verifier、收案前 verifier（envelope 收案 verifier 在 S1～S3 後一次，見 §6）。
審查紀錄：第 1 輪 REVISE `~/jgb-archive/transcript-photo-fullparse-eval-20261109/reviews/plan-review-s2-round1-20261109.md`（7 項全 FIX）；第 2 輪 REVISE `…/reviews/plan-review-s2-round2-20261109.md`（4 項全 FIX，本版，新準備期）；收尾審查第 3 輪 READY `…/reviews/plan-review-s2-round3-20261109.md`

## 1. 本片承接的規則與驗收項（不改，只引用）

| 規則／驗收 | 本片怎麼承接 |
|---|---|
| R4 | 帶參數時每個有值葉子 `{"value", "position"}`；`position`＝`{"page": 1 起算, "box": [x0,y0,x1,y1] 0～1 比例, "unit": "ratio"}`；找不到給 `null`（對不到值本身時一律 `null`，不給近似框）；`判定`、`部是否印出` 不包 |
| R5 | 電子 PDF 框到「值」本身（不是整行、不是標籤＋值） |
| R2 | 不帶參數，回應一個字都不變 |
| C10 | 電子 5 份帶參數：(a) `position` 非 null 的值，框內文字正規化後與 `value` 相同 ≥95%；(b) 有值葉子中 `position` 非 null ≥95% |
| C1～C4 | S1 已達門檻；本片改的解析器電子、照片共用，收案時照片重量（§4） |
| C5、C6、C7、C8、C9 | S1 已驗；本片改動後電子、照片都重跑（§4），值、鍵、不帶參數回應都不能變 |

**C10「正規化後相同」本片的判定定義**（凍結清單沒寫細節；寫成 `acceptance.md`「核可後更正」AM-3，業主確認於「待確認」，連同 S2 確認頁 `confirm-s2.md` 交業主）：
- 框內文字＝該頁 `rawdict` 逐字框中，**中心點落在 `box` 內**的字元，依原順序串接。
- 正規化＝`normalize_for_matching` 後去掉所有空白。
- 相同＝正規化後字串相同；`value` 是數字時，`to_number(框內文字)` 等於 `value`（`to_number` 是建構器把原文轉成數字的同一個函式，例：框到「1,426.05」→ 1426.05）。

## 2. 目標 → 目標形態 → 差距 → 路徑

**目標**：JGB 拿到每個值時能在原檔上找到它（JGB 原文：「能不能在回傳的每一筆結果裡加上位置資訊？…找不到位置的欄位可以不給，或給 null」）；電子檔框到值本身（R5）。

**目標形態**：沿用 envelope §2「每個值附位置」的業界原文（Azure `boundingRegions` 頁碼＋多邊形、Google `pageAnchor`、AWS `PageNumber`＋`Geometry`，三家位置都跟值放在同一物件；原文存 `~/jgb-archive/documind-output-converge-20261109/sources/`）。三家原文只寫到「位置與值放在同一物件、是哪一頁偵測到的」，沒有寫位置怎麼產生。本片「**位置在解析當下記下**」是第一原理推導，查無業界對應：同一個字串在謄本裡常重複出現（日期、「全部」、權利範圍），事後拿值搜全文無法判斷是哪一處（下方差距 2 的實測）。

**差距**（2026-11-09 本機探查，腳本與輸出見括號）：
1. 文字層與逐字框對得上：5 份 17 頁，`get_text()` 去換行後的字元序列逐字等於 `rawdict` 字元序列 17/17；逐字做 `normalize_for_matching` 再串接，等於整段正規化 17/17；這 17 頁沒有正規化後長度會變的字元（`E/probe_s2_chars.py` 輸出 `E/runs/probe_s2_chars.txt`；`E/probe_pdf_lines.py`：一對一 17/17、25352 字）。
2. 事後搜尋定不了位：740 個有值葉子中，原文字串在整份文字出現 2 次以上的 513 個、0 次的 44 個（跨行接起來的值）、恰 1 次的只有 172 個（`E/probe_s2_trace.py` 輸出 `E/runs/probe_s2_trace.txt`）。
3. 解析器 `transcript_full_parser.parse_with_ledger` 逐行處理，每個值來自「某頁某行、標籤之後到下一個標籤之前」的一段，再經 `clean()`（去補位星號、收空白）；續行把下一行接到上一個值後面。目前只記帳目 (頁, 行, 去處)，沒記值在行內的字元位置。
4. 建構器 `build_with_trace` 已記「原文路徑 → 輸出路徑 → 方式」；輸出值有幾種是原文的轉換：數字（`to_number`）、權利範圍（`to_share`）、年月拆開（`split_year_month`）、地段拆開（`split_district`）、地號拆開（`split_lots`）、其他登記事項拆三段（`split_other_item`）、子標籤當值（`其他登記事項子項`）。兩個值沒有一般 trace：`類型`（11 個，5 份共 11 張）取自抬頭印出的「土地／建物」字樣（`transcript_records._sheet_type` 以 `re.match(r"\s*(土地|建物)", title)` 讀抬頭；後備為編號類型或部名，也是印出的字），可從抬頭定位；`謄本.頁數`（6 個）是頁首「頁次」標籤出現的次數（`_header` 內 `out["頁數"] = len(vals)`），是計數，謄本上沒有印成這個數。
5. API 層手上有上傳原檔 bytes（`app/api/v1/analyze.py` `contents`）；重新開檔取 `rawdict` 每份中位 13–35 ms（`E/time_s2_rawdict.py` 輸出 `E/runs/time_s2_rawdict.txt`，各 3 次取中位）。

**路徑**（本片做法）：
1. **解析器可選記位置**：`parse_with_ledger(pages, track=False)`。`track=True` 時，每個值與標籤以 `str` 子類（`Located`，多一個屬性 `spans: [(頁, 行, 起, 迄)]`，欄位以正規化後該行的字元索引計）放進結果；`clean()`、續行接字時重新算出 spans（接字＝兩段 spans 相加）。`track=False`（預設，現有所有呼叫）行為與輸出完全不變。`Located` 是 `str`，`json.dumps`、`deepcopy` 結果與一般字串相同（本機已試：`json.dumps` 輸出 `"abc"`、`deepcopy` 保留 spans）。
2. **輸出值對到原文片段**：沿 `build_with_trace` 的 trace，取原文 `Located` 的 spans，再依輸出值找它在原文中的那一段——
   - 輸出值（正規化、去空白）是原文（正規化、去空白）的子字串 → 框那一段（拆開類、權利範圍、字串原樣都走這條）；
   - 輸出值是數字 → 框原文中被 `to_number` 取到的那個數字記號；
   - 方式是「標籤」（`謄本.查驗碼標籤`，輸出值是頁首標籤字，如「謄本種類碼」）或「子標籤當值」（`其他登記事項子項`）→ 框該標籤的 spans（解析器 `track=True` 時標籤——含 dict 鍵——也是 `Located`，帶 spans）；
   - 方式是「配對」（一個輸出值的 trace 記了兩個來源，`transcript_records._pair` 兩個 `sh.mark`）→ 每個來源都依上面規則比對，取第一個對得到的；
   - `類型` → 框抬頭（`謄本種類` 原文）中「土地／建物」那兩個字（同「子字串」規則）；
   - `謄本.頁數`（計數，謄本上沒有印成這個數）→ `position: null`；
   - 以上都對不到 → `position: null`（不給近似框，R4、R5）。
   - 對照探查 `E/runs/probe_s2_trace.txt` 各類（740 個有值葉子）：原文子字串 662 個 → 子字串規則；「數字」15、「共有部分」1（面積）→ 數字記號規則；「配對」30 → 兩來源比對；「標籤」11、「其他登記事項子項」4 → 標籤 spans；`類型`（no_trace）11 → 抬頭子字串；「頁數」6 → `null`。照路徑設計上 `null` 只有 6 個，E6a 上限 (740−6)/740＝99.2%；實際落到「對不到」的個數由 C10 照實報。
3. **字元位置換成框**：正規化行字元索引 → 原文字元索引（逐字正規化累計長度，處理長度會變的字元，不列字元清單）→ `rawdict` 逐字框 → 同一頁的字框取外接矩形，除以頁寬高得 0～1 比例；`page`＝該值第一段所在頁。值跨頁時只框第一頁那幾段。任一步對不上（例：該頁逐字正規化串接不等於整段正規化、字元數不等）→ 該頁所有值 `position: null`，不猜。值跨頁時 `position` 只有一個 `page`，所以只框第一頁那幾段（列 §7、AM-3）。
4. **接上 S1 的轉換**：`apply_transcript_format(result, file_contents=None)`。帶參數、電子 PDF（各頁 `text_layer` 為 true）時，API 層把 `contents` 傳入；轉換內以各頁文字 `track=True` 重新解析、重建 records，**重建出的 records（去掉 spans 後）必須與 `result` 裡的 `transcript_records` 相同**，不同就整份 `position` 維持 `null`（不讓位置對到另一份解析）。取得位置後再補值（S1 `fill_from_rules`）與包裝；補進的值在電子檔上本片給 `null`（C5 已驗電子 5 份補值 0 處；照片補值定位是 S3）。
5. **不動**：`analyze_service`、`extract_text_layer_pages`、OCR、複核佇列、不帶參數的任何路徑。envelope §3 原寫「`extract_text_layer_pages` 另存逐字框」，本片改為在轉換時從原檔重取（理由：`analyze_service`、`extract_text_layer_pages` 不碰；代價每份中位 13–35 ms，只在帶參數時發生；列於 §7）。解析器 `parse_with_ledger` 是電子、照片、帶與不帶參數共用的函式，`track=False` 預設輸出必須不變，由 §4 的照片與電子不帶參數改前改後 diff 承接。

## 3. 範圍與擁有者

| 項目 | 檔案 | 擁有者 |
|---|---|---|
| 解析器可選記位置 | `backend/app/lib/multi_type_ocr/transcript_full_parser.py` | executor |
| 位置組裝（trace → 片段 → 框）與 `apply_transcript_format` 接上 | `backend/app/lib/multi_type_ocr/transcript_records.py`，必要時新檔 `transcript_positions.py` | executor |
| API 傳原檔 | `backend/app/api/v1/analyze.py`（只改第 8 步那兩行） | executor |
| 單元測試 | `backend/tests/unit/test_transcript_positions.py`（新）；`test_transcript_full_parser*.py` 加 `track=False` 輸出不變 | executor |
| C10 驗證腳本、重跑 C5～C9 | `E/check_s2_c10.py`（新，跑前凍結 sha1 寫入報告）、`E/check_s2_http.py`（由 `check_s1_http.py` 複製，只改 position 斷言：電子不再要求全為 `null`、改查非 null 者形狀合 R4——`page` 整數 ≥1、`box` 4 個 0～1 數字且 x0≤x1、y0≤y1、`unit`＝`"ratio"`；照片仍要求全為 `null`；其餘斷言不變；sha1 `54e443b578f4`，2026-11-09 已凍結） | 主會話 |

**前提**：S1 已完成（`E/runs/s1_impl.txt` C1～C4、`E/runs/s1_http.txt` C5～C9 263 PASS 0 FAIL、`E/runs/s1_c15.txt` C15 0 FAIL），但未 commit（AUTO 不含 commit 權）。

**回滾**（S2 單獨還原、保留 S1）：開工前已把 S1 狀態存成基準 `~/jgb-archive/transcript-photo-fullparse-eval-20261109/baseline_s1/`（`SHA1SUMS` 列 6 個檔：`analyze.py`、`transcript_records.py`、`test_api_backward_compat.py`、`test_transcript_format_v2.py` 為 S1 版；`transcript_full_parser.py`、`test_transcript_full_parser.py` 為 HEAD 原檔；另存 S1 照片輸出 `baseline_s1/s1_impl_out/`）。S2 會碰的 repo 檔＝這 6 個＋新增檔；executor 碰到清單外的既有檔須先停、回報主會話（主會話補進基準再續）。還原步驟：(1) `cd ~/jgb-archive/transcript-photo-fullparse-eval-20261109/baseline_s1 && shasum -c SHA1SUMS` 確認基準未變；(2) 把 6 個檔複製回 repo 同路徑；(3) 刪 S2 新增檔（`transcript_positions.py`、`test_transcript_positions.py`，若有；以 `git status --porcelain` 對照開工前的未追蹤清單：`.claude/`、`.kiro/specs/transcript-records-converge/`、`backend/tests/unit/test_transcript_format_v2.py`）；(4) repo 內 6 檔 `shasum` 與 `SHA1SUMS` 相同，跑單元測試全套，失敗清單與 S1 時的 18 個逐項相同（S1 時清單存 `baseline_s1/fail_s1.txt`）。業主若決定先 commit S1，回滾改為 `git checkout <S1 commit> -- <S2 碰的檔>`＋刪 S2 新增檔。

非目標：照片位置（S3）、補進值的定位（S3）、規格與 schema 文字（S4）、改 `analyze_service`／OCR、信心度。

## 4. 每次執行（測試選擇）

| 執行 | 回答的決定 | 改變下一步的結果 | 規模與理由 | 成本（跑前估，附來源） |
|---|---|---|---|---|
| 單元測試全套 | 便宜決定性檢查 | 新增紅 ⇒ 不送驗收；既有 18 個失敗（本機無 PaddleOCR 的合約 OCR 3 個等，與 S1 前相同）不算 | 全套 | 53 秒（2026-11-09 本機實跑）；0 模型呼叫 |
| C10 電子 5 份 | 位置框得對不對、夠不夠多 | (a) 或 (b) <95% ⇒ 停，看逐格錯例決定修或交業主 | 5 份 17 頁全部（電子檔是主要用途，全部 740 個值） | 5 份 × 40–72 ms＋重取框中位 13–35 ms（`E/runs/time_s2_rawdict.txt`）＋HTTP 往返；0 模型呼叫 |
| 重跑 C5～C9 電子（`check_s2_http.py`，HTTP，改前 :18086＝`49faf53`、改後 :18085） | 解析器與轉換改動有沒有改到值、鍵、不帶參數回應 | 任何 FAIL ⇒ 停 | 電子 5 份全部：本片改 `parse_with_ledger`（電子、照片共用）、`apply_transcript_format`（帶參數） | 2026-11-09 `check_s1_http.py` 全段實跑約 1 分鐘內；0 模型呼叫 |
| 照片不帶參數改前改後 diff（C6 前半、照片 C7） | 解析器改動有沒有改到照片不帶參數的 `document_fields`（R2） | 任一份 `改前` 與 `baseline_s1/s1_impl_out/` 不逐位元相同 ⇒ 停 | 照片 15 頁＋5 份合併（全部 20 單位；`parse_with_ledger` 對每份都跑，判不出哪份不受影響）；照片 C7 用 `check_s1_http.py` 照片段 | `measure_s1_impl.py` 2026-11-09 實跑約 1 秒＋比對；0 模型呼叫 |
| C1～C4 收案重量（照片，終點） | 照片終點有沒有退（「終點指標」收案重量） | 任一低於門檻或錯值不再全與舊欄位同值 ⇒ 停 | 15 頁＋5 份合併，同 S1（`measure_s1_impl.py`） | 同上 1 秒；0 模型呼叫 |
| 照片帶參數 `position` 全為 `null` | 本片不碰照片位置（S3） | 有非 null ⇒ 停 | 同上 20 單位，與上一列同一次執行 | 同上 |

不跑：C15（本片不碰攔截、佇列與 API 第 7 步；轉換仍在攔截之後、對深拷貝做，`analyze.py` 第 7、8 步）、OCR（照片用已存 OCR 文字）。

## 5. 終點指標（目標文件＝`acceptance.md`）

受測物：DocuMind `49faf53`＋未提交 S1（`transcript_records.py` sha1 `982a8038f523`）。同一目標前兩片：S1（E1 73→167、E2 62→101、E3 0→9、E4 35→40、E5 0/5；`E/runs/s1_impl.txt`，2026-11-09 11:3x 實跑），前一片無。

| 指標 | 現值（S1 後，`982a8038f523`） | S1 實際變化 | S2 預期 | 現值來源 |
|---|---|---|---|---|
| E1 照片 15 頁葉值讀對（816）（C1） | 167 | 73→167 | 不變（≥167） | `E/runs/s1_impl.txt` 第 3 行 |
| E1a 照片 15 頁錯值（C1） | 7，全與舊欄位同值 | 0→7 | 不變（≤7 且全同值） | 同上第 3、12–19 行 |
| E1b 照片 15 頁多出值（C1） | 0 | 0→0 | 0 | 同上第 3 行 |
| E2 照片合併 5 份讀對（703）（C2） | 101 | 62→101 | 不變（≥101） | 同上第 20 行 |
| E2a 照片合併錯值（C2） | 2，全與舊欄位同值 | 0→2 | 不變（≤2 且全同值） | 同上第 20 行起「補進且不等於答案的格」 |
| E2b 照片合併多出值（C2） | 0 | 0→0 | 0 | 同上第 20 行 |
| E3 jgb2 8 格（26）（C3） | 讀對 9、錯 0 | 0→9、錯 0→0 | 不變（≥9、錯 0） | 同上第 4 行 |
| E4 判定讀對（45）（C4） | 40；判定不同且非無法判定 0 | 35→40；0→0 | 不變（≥40；0） | 同上第 5 行 |
| E5 電子帶參數與不帶參數不同份數（C5） | 0/5 | 參數不存在→0/5 | 0/5 | 同上末行 |
| E6 電子位置吻合率（C10 a） | 沒有位置（`position` 一律 `null`） | 不適用（前提片） | ≥95% | `transcript_records._wrap` 一律 `"position": None`；`E/runs/s1_http.txt` 各「position 全為 null」列 |
| E6a 電子有值葉子有位置比例（C10 b） | 0% | 不適用（前提片） | ≥95%（照 §2 路徑設計上限 99.2%＝(740−6)/740，6 個 `頁數` 給 null） | 同上 |
| E7 照片行框包含率（C11） | 沒有位置 | 不適用 | 不變（S3） | 同上 |

同一目標前兩片：S1（上表「S1 實際變化」欄）；S1 之前無。斷路器不適用（S1 有變化）。

## 6. 收案與驗證

本片完成條件：§4 全部執行通過、C10 (a)(b) ≥95%、單元測試無新增紅。之後接 S3；envelope 的收案 verifier 在 S1～S3 完成後一次跑（envelope §1、§4「收案 verifier」列），verifier 另寫 ≥10 個未出現過的輸入（換資料組也換說法）。

## 7. 我改動的地方（相對 envelope 與凍結清單）

| 原文（出處） | 本片改成 | 理由 |
|---|---|---|
| envelope §3 S2「`extract_text_layer_pages` 另存每行逐字框（內部，不出現在回應）」（`plan.md` §3） | 不改 `extract_text_layer_pages`；帶參數時在轉換裡從原檔重取逐字框 | `analyze_service` 與取文字不碰；代價每份中位 13–35 ms，只在帶參數時 |
| C10「用 PyMuPDF 取 `box` 範圍內文字，正規化後與該 `value` 相同」（`acceptance.md` C10；沒定義怎樣算框內、怎樣正規化） | 框內＝字框中心點落在框內的字；正規化＝`normalize_for_matching`＋去空白；數字值以 `to_number(框內文字)` 等於值算相同（AM-3） | **擇一＋放寬**：數字比對是放寬（框到「1,426.05」算與 1426.05 相同）；不放寬時每個帶千分位或小數尾 0 的數字都會算錯，見確認頁問題 |
| R4「找不到位置時 `position` 給 `null`」（`acceptance.md` R4） | `謄本.頁數`（頁次出現次數，謄本上沒有印成這個數）給 `null`；電子檔上補進的值本片給 `null`（電子 5 份補值 0 處，C5） | 頁數無印出位置；補值定位屬 S3 |
| R5「電子 PDF 框到值本身」（`acceptance.md` R5） | 值是印出的標籤字（`謄本.查驗碼標籤`、其他登記事項子標籤）時框該標籤字；值跨頁時只框第一頁那幾段；單頁對位任一步不一致時整頁 `null` | `position` 只有一個 `page`；不一致時不猜 |

## 8. 用量回報

本片已用：主會話探查，子代理 0。送審後補 plan-verifier token；執行後補 executor token。模型費用 0（不呼叫模型）。
