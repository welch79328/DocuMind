# 合約 v2：電子 PDF 值位置（contract_format=v2）— 計畫（第 3 版）

> 狀態：第 3 版，業主 11/13 15:19 核可（模式 ASK）；規則與清單凍結在 `acceptance.md`，後續裁定在 `acceptance-amend-1.md`。程式 `fd9f6d9` 已於 15:37 部署。
> 證據目錄 E = `~/jgb-archive/contract-v2-positions-20261113/`
> 審查紀錄：`E/reviews/plan-review-20261113.md`

**做到什麼就收**：`contract_format=v2` 上正式機，§4 清單全部通過，fresh verifier CONFIRMED，給 AIChatbot 的上線通知稿交給業主（由業主送）。

## 0. 目標正本定位

無上層目標。查過：`docs/planning/`（`transcript-status.md`、`03-TECH-STACK.md`，只有謄本與直讀的現況）、`.kiro/specs/` 全部目錄的檔名與 `transcript-records-converge/plan.md` §2（謄本 v2 的目標形態，本片沿用它的業界原文）、`docs/api/INTEGRATION.md` §3.2（合約）。沒有一份文件寫合約位置的目標或量法。本片目標文件＝核可後的 `acceptance.md`。
本片不碰任何已知偏離；不新增 AI 決定權（文字層路徑不呼叫模型，見 §2 差距 3）。

風險觸發：序列化（API 回應新增格式）、上線（正式機部署）→ 派 plan-verifier；收案前派 verifier。

**並行的另一條線**：`.kiro/specs/handover-photo-v2/`（點交照片 v2，另一個 session，未核可）同樣改 `backend/app/api/v1/analyze.py`、`docs/api/INTEGRATION.md`，並打算部署同一台正式機。兩線的協調規則見 §5。

## 1. 業主原話與規則

業主原話逐字存 `E/reviews/owner-words-20261113.md`（由 session jsonl 抽出；含選項題的題目、選項說明與回答）。時間為台灣時間。

- 11/13 12:47「跟對方說不用等你上線」——已由 12:47 給 AIChatbot 的回覆稿處理（稿內「你們不用等我們上線」）；本片不承諾上線日期（非目標）。
- 11/13 14:49「不用決定日期 直接開發」——回覆我 14:37 那則（「第 2 題的上線時間要你定，這條線還沒開」，並問第 2 題怎麼回）：「不用決定日期」＝不給 AIChatbot 日期；「直接開發」＝現在開這條線。
- 11/13 14:50 選項題答「照原案只做電子檔 (Recommended)」；該選項說明逐字：「做 contract_format=v2，電子 PDF 框到值，直讀給 null。範圍最小、結果確定，但真實合約多半用不到。要用合成租約和範本補驗收資料。」
- 11/13 15:00 選項題答「有值就框出處 (Recommended)」；該選項說明逐字：「框出「這個值是從哪裡讀到的」，抽錯的也框。客人點了看得到錯在哪裡，可以自己改。這正是 AIChatbot 要的「值從哪裡讀到」。」

「原案」＝我 11/13 12:47 給 AIChatbot 的回覆稿第 1、2 點（逐字在同檔）。需求原始來源是 AIChatbot 11/13 兩則訊息（業主貼上）。

| ID | 可檢查的條件 | 出處 | 業主確認於 |
|---|---|---|---|
| R1 | `/analyze` 帶 `contract_format=v2` 且 `document_type=contract` 時，`document_fields.rental_terms` 的 `date_start`、`date_end`、`monthly_rent`、`deposit`、`rental_address`、`tenant_name` 六欄各包成 `{"value": 值, "position": {...} 或 null}`；`value` 與不帶參數時同一欄的值相同 | 原案「可以照謄本 v2 的格式附上值的位置，欄位是 date_start、date_end、monthly_rent、deposit、rental_address、tenant_name。用 contract_format=v2 開啟」 | 14:50「照原案只做電子檔」 |
| R2 | 電子 PDF（每頁 `pages[].text_layer` 為 true）中有值的欄位，`position`＝`{"page": 1 起算, "box": [x0,y0,x1,y1] 0～1 比例, "unit": "ratio"}`，框住抽出這個值的那段原文（判法見 C2）；值抽錯也框它的出處 | 選項說明「電子 PDF 框到值」；15:00「有值就框出處」 | 14:50、15:00 |
| R3 | 值是 null 時 `position` 為 null；有值但對不到原文時也給 null，不給近似框 | 原案「在原文找不到的值，position 給 null」 | 14:50 |
| R4 | 不是每頁都有文字層（照片、掃描 PDF，線上走直讀）時，六欄 `position` 一律 null | 原案「照片和掃描 PDF 目前走直讀，模型只回值、不回位置，這一類 position 會是 null」；選項說明「直讀給 null」 | 14:50 |
| R5 | 不帶 `contract_format` 的回應與改前相同 | 原案「不帶參數的回應不變」 | 14:50 |
| R6 | 部署到正式機（沒有測試機），上線後由業主通知 AIChatbot；不承諾日期 | 原案「我們沒有另外的測試機，上線後帶參數就能測」；14:49「不用決定日期」 | 14:49、14:50；部署授權待本計畫核可（§5） |
| R7 | `docs/api/INTEGRATION.md` 寫入 `contract_format=v2`，並寫明直讀的頁碼取法（依頁序第一個 `pages[].structured_data.rental_terms.<欄位>` 非 null、非空字串那頁的 `page_number`） | **我加的**（§8 第 1 條） | 待確認 |
| R8 | `contract_format` 不是 `v2` 回 400 `INVALID_CONTRACT_FORMAT`；`document_type` 不是 `contract` 時忽略這個參數 | **我加的**（§8 第 3 條），比照 `transcript_format` | 待確認 |

## 2. 設計

**目標**（R1～R4）：AIChatbot 點欄位旁的小字，在客人的合約上框出值是從哪裡讀到的；做不到的給 null，由對方只標頁碼。

**目標形態**：沿用謄本 v2 計畫 `.kiro/specs/transcript-records-converge/plan.md` §2 的業界原文（存 `~/jgb-archive/documind-output-converge-20261109/sources/`），三家都把位置跟值放在同一物件：Azure「Each region specifies the page number (1-indexed) and bounding polygon」（`azure-analyze-response.txt:124`）；Google「pageAnchor … Represents the provenance of this entity wrt. the location on the page」（`google-rest-document.txt:1944`）；AWS「PageNumber: The page number the value was detected on」（`aws-api-expensefield.txt:112-114`）＋ Geometry（`aws-api-expensedetection.txt:98-100`）。頁碼起點三家不同：Azure 1 起算（同上行）；Google PageRef 的 page 是「Index into the Document.pages element」（`google-rest-document.txt:2028`，0 起算）；AWS PageNumber「Valid Range: Minimum value of 0」（`aws-api-expensefield.txt:118`）。本片用 1 起算，理由是與謄本 v2 及 AIChatbot 要求的格式一致，不是業界共識。
「位置取自抽出值的那一次比對，不事後拿值搜全文」是第一原理（同一字串可能出現多次，例：押金與租金同額），查無業界對應，與謄本 S2 同。

**差距**（現況，`df41f2d`）：
1. 規則抽取 `ContractFieldExtractor._extract_with_regex`（`contract_field_extractor.py`）在 `normalize_for_matching` 後的全文上 `re.search`，只留 `match.group(...)`，比對位置丟掉。
2. 回應沒有任何合約位置；`contract_format` 在 `app/` 出現 0 處（正對照 `transcript_format` 11 處，`E/runs/current_e1e2.txt`）。
3. 文字層路徑不會呼叫模型：`_extract_fields_for_text_layer` 傳 `image_data=None`（`analyze_service.py` `_extract`），LLM 輔助的條件都要 `image_data`（`contract_field_extractor.py` `extract`）。所以電子 PDF 的值全是規則抽取，都有比對位置可記。
4. 直讀（`direct_read_processor.py` `ContractDirectReadProcessor`）只回 `value`／`certain`，沒有框。
5. 真實樣本：`data/contracts/` 11 份真實合約全是掃描檔（`E/runs/survey_contracts.txt`，NO-TEXT 11/11），本片位置用不上；電子合約只有合成檔與 jgb2 範本。業主已知此事並選原案（14:50）。

**路徑**：
1. 抽取器：`_extract_with_regex` 拆出 `_match_fields(text) -> {欄位: (值, 正規化文字上的 (起, 迄)) 或 None}`，`_extract_with_regex` 改成只取值。比對邏輯不變（同一 PATTERNS、同一順序、第一個命中即停）；起迄：單一捕獲組取 `group(1)` 去頭尾空白後的範圍，多捕獲組（民國年日期）取第一組起點到最後一組終點。
2. 新模組 `app/lib/multi_type_ocr/contract_positions.py` 的 `apply_contract_format(result, file_contents)`：深拷貝回應；`rental_terms` 存在時六欄包 `{value, position}`。position 只在下列全部成立時給：每頁 `text_layer` 為 true；以原檔重抽的文字層與 `pages[].ocr_raw.text` 逐頁相同；依頁序找第一個該欄非 null、非空字串的頁（與 `_merge_fill_missing` 同規則），在該頁重跑 `_match_fields` 得到的值與該頁、與 `document_fields` 的值三者相同；該頁幾何檢查通過（重用 `transcript_positions._page_geometries`／`_Geo`）。正規化位置 → 原文字元 → rawdict 字框，略過空白與換行，取外接矩形 ÷ 頁寬高。**跨行規則**：值的字元（不含空白）落在原文兩行以上（起迄之間含換行，例：民國年日期「中華民國113年」換行「1月1日」，樣式的 `\s*` 可跨過換行）⇒ position null，不給橫跨兩行的大框。任一不成立 → null。不改 `analyze_service.py`。
3. `app/api/v1/analyze.py`：新增 Form 參數 `contract_format`（R8 驗證），在信心度攔截之後（複核佇列存未轉換的回應，與謄本相同）對 `contract` 套用。
4. 文件：`INTEGRATION.md` 新增 contract_format=v2 一節、R7 直讀頁碼規則，版本號依 §5 協調規則取；`docs/testing/contract-v2-positions-<日期>.md` 紀錄。

偏離目標形態的取捨：照片、掃描檔不給框（R4，業主選原案）；只包六欄、其他合約欄位不包（AIChatbot 只要這六欄，原案也只列六欄）；跨行的值給 null，不像 Azure 那樣給多個區域（`azure-analyze-response.txt:124`「When elements aren't visually contiguous … described via an array of bounding regions」）——AIChatbot 指定的格式是單一 `box`，一個大框會框進不相干的字，違反 R3「不給近似框」；跨行值的數量在 C2 覆蓋率裡照實計入。

## 3. 範圍與非目標

範圍：路徑 1～4、單元測試 `backend/tests/unit/test_contract_v2_positions.py`、§4 驗收、部署。

非目標（附理由）：
- 照片、掃描 PDF 的框（AIChatbot 原訊息「照片框到整行」）：業主 14:50 選「只做電子檔」；線上走直讀沒有行框。記 followups C-F2。
- 直讀關閉時走 OCR 的照片路徑：線上直讀開啟（`docs/DEPLOYMENT.md:30`），用不到。記 followups C-F2。
- 電子合約抽取率（合成租約六欄只抽到 3 欄，範本 `tenant_name` 抽成「契約審閱權」）：位置照 R2 框出處，抽取品質另線。記 followups C-F1。
- 批次端點 `/analyze/batch`（§8 第 4 條）。
- `rental_terms` 不存在時不補空殼（不帶參數也沒有這個鍵）。
- 上線日期（14:49「不用決定日期」）。

## 4. 驗收清單（核可後凍結）

驗收資料（全部可用的文字層合約都用，§4 廣度表逐檔列出）：
- G1～G3（D-gen）：由**不讀本 repo 程式**的 `general-purpose` 代理產生的電子租賃合約，三組版型，各 5 份：G1 仿內政部「住宅租賃契約書範本」條列、G2 仿 jgb2 `gtb_contract_chinese.pdf` 版面、G3 一頁式簡約租約（甲方／乙方）。代理同時寫答案鍵（每份六欄照文件印的寫法）。說法變化每類至少一份：民國／西元日期、全形數字、中文大寫金額、含逗號與「新臺幣…元」、欄位落在第 2 頁以後、地址中間換行、民國日期中間換行、標籤換說法（承租人／乙方）。代理交 HTML，主會話用 PyMuPDF 轉成有文字層的 PDF（只做格式轉換、不改內容）；跑前把檔案 sha256 寫進 `E/runs/inputs-frozen.txt` 凍結。
- G4（範本）：`E/runs/survey_contracts.txt` 列出的 5 份文字層檔——`gtb_contract_chinese.pdf`（jgb2）、社宅「委託租賃契約書範本-3.1」「租賃契約書範本-3.1」「表單2.屋況及租屋安全檢核表-3.1」（jgb2 `resources/template/pdf-location/`）、`synthetic_service_contract.pdf`（既有合成服務合約）。範本多為空白欄，會抽到錯值（例：「契約審閱權」），正好驗 R2「抽錯也框出處」與 R3 null。
- D-old：`~/jgb-archive/qwen-direct-read-20261029/t2in/textlayer_lease.pdf`（既有合成租約）。
- D-scan：`E/inputs/scan_textlayer_lease.pdf`——把 D-old 以 200 dpi 轉成純影像 PDF（1 頁、文字層 0 字），不用真實客戶合約，所以只送合成內容到 Bedrock。

**C2 判法（跑前凍結）**：框內字＝該頁 rawdict 中字元框中心點落在 `box`（還原成點座標）內、且不是空白的字，依 rawdict 順序串接後套 `normalize_for_matching`；值同樣套 `normalize_for_matching` 並去空白。單一捕獲組欄位：兩者完全相同。日期欄位：兩者的數字序列相同，且框內字只含數字、「年月日民國西元中華」與 `./-`。不符即錯框。覆蓋率＝position 非 null 的欄位數 ÷ 值非 null 的欄位數（只算文字層檔）。

**本機執行不碰正式環境**：C1、C2、C9 的本機 TestClient 執行一律以 monkeypatch 把 `AnalyzeService._upload_to_s3` 換成回傳 None 的替身（不上傳任何 S3），資料庫用帶 label 的臨時 Postgres 容器（複核佇列列寫進臨時庫，任務結束收掉）。本機 `.env` 不讀，所以不依賴它有沒有 S3 設定。

**C5 排除鍵（跑前凍結，來自 `analyze_service.py` 組回應處與 `analyze.py` `_apply_confidence_gating`）**：`file_url`（每次新上傳）、`stats.total_time_ms`、`review_item_id`（每次新佇列列）。其餘任何差異都算不符。

| ID | 規則 | 檢查 | 觀測點 | 證據 |
|---|---|---|---|---|
| C1 | R1 | 每份 G1～G4＋D-old，v2 回應六欄都是 `{value, position}`；`value` 等於同檔不帶參數回應的值 | 本機 API（TestClient 打 `/analyze`）全部；線上 5 份 | `E/runs/c1_c2_local.txt`、`E/runs/online_after.txt` |
| C2 | R2 | C2 判法：**錯框 0**；覆蓋率 **≥95%** | 本機判分腳本；線上回應同腳本 | `E/runs/c2_judge.txt` |
| C3 | R3 | 值為 null 的欄位 position 為 null；人為破壞幾何（頁面旋轉、文字層與原檔不符、重跑值與回應值不同）時 position 為 null | 單元測試 | pytest 輸出 |
| C4 | R4 | D-scan 只送一次（帶 v2）：六欄 position 全 null；六欄 value 等於**同一份回應** `pages[].structured_data.rental_terms` 依頁序取第一個非 null、非空字串的值（不比兩次模型呼叫） | 線上（直讀，1 份 1 頁） | `E/runs/online_scan.txt` |
| C5 | R5 | 部署前後，同一批 5 份（D-old、G1～G3 各第 1 份、G4 `gtb_contract_chinese.pdf`）不帶參數的回應，排除上列 3 個鍵後完全相同 | 線上，部署前後各一次 | `E/runs/c5_before.txt`、`c5_after.txt`、`c5_diff.txt` |
| C6 | R5 | 謄本 v2 不受影響：本線不改謄本分支；改後本機跑既有 `tests/unit/test_transcript_v2_spec.py` 全過，且 `git diff df41f2d -- backend/app/lib/multi_type_ocr/transcript_*.py` 為空。不對正式機送真實謄本 | 本機 | pytest 輸出、diff 輸出 |
| C7 | R1–R5、R8 | 單元測試：包裝形狀、第一個非空頁規則、多捕獲組日期起迄、跨行值（換行的民國日期）給 null、值不一致給 null、非文字層給 null、`contract_format=v3` 回 400、非合約忽略；`tests/unit` 全跑，起臨時 Postgres（帶 label）後 0 失敗。改前沒有測試資料庫時有 11 個失敗，全是 `password authentication failed`（`E/runs/c7_baseline_unit.txt`） | `pytest` | 輸出存檔 |
| C8 | R7、R8 | `INTEGRATION.md` 有 contract_format=v2 一節、直讀頁碼規則、400 錯誤碼；grep 舊說法殘留＋正對照 | 文件 | grep 輸出 |
| C9 | 全部 | fresh verifier 對照業主原話、`acceptance.md`、宣稱，另寫 ≥10 份沒出現過的電子合約輸入，用 C2 判法實跑；**只在本機**（TestClient），不對正式機送件 | verifier，本機 | `E/reviews/close-verify-*.md` |

### 廣度

| 項目 | 類型 | 資料組（用／可用） | 不同輸入數 | 重複次數 | 輸入撰寫者 | 改前對照 |
|---|---|---|---|---|---|---|
| C2 框到出處 | 使用者層 | 5／5（G1、G2、G3、G4、D-old） | 21 份（15＋5＋1）× 6 欄 | 1（決定性：同檔同程式結果相同） | G1～G3：不讀程式的代理；G4：jgb2 與既有合成檔；D-old：既有合成檔 | 改前沒有位置（`E/runs/current_e1e2.txt`），沒有可比的成效；宣稱只寫「機制做對＋錯框 0、覆蓋率 x%」 |
| C1、C3～C8 | 機制項 | — | — | — | — | — |

上位驗收方式：無。
可用但沒用在 C2 的：`data/contracts/` 11 份真實合約（全是掃描檔，NO-TEXT，C2 量不到；C4 也不用，改用合成掃描檔避免外送客戶合約）。

### 終點指標

目標文件＝本片 `acceptance.md`。

| 指標 | 現值（`df41f2d`） | 來源 | 本片預期 |
|---|---|---|---|
| E1 錯框數 | 0（沒有任何框） | `E/runs/current_e1e2.txt`（`contract_format` 0 處，正對照 `transcript_format` 11 處） | 維持 0（門檻 0）。理由：E1 是護欄不是進度——現值 0 只因為還沒有框；本片開始給框後要守住 0。本片的進度量在 E2。**這項預期變化為 0，需業主同意（§8，待確認）** |
| E2 覆蓋率 | 0%（0 個值有框） | 同上 | 0% → ≥95% |

佐證（不是現值，是可行性）：原型在 D-old 抽到 3 欄。以 `get_textbox` 取框內字時，`rental_address` 多一個開頭的冒號（`E/runs/proto_contract_pos.txt`）；改用 C2 判法（字元中心＋正規化）重跑後，3 欄都與值相同（`E/runs/proto_center.txt`）。所以冒號是 `get_textbox` 把框邊的鄰字算進來，不是框錯。
前兩片：無（新線）。

### 測試選擇與成本

| 執行 | 回答的決定 | 改變下一步的結果 | 規模理由 | 規模 × 時間（來源） | 呼叫／費用（來源） |
|---|---|---|---|---|---|
| C7 單元＋既有測試 | 能不能進驗收 | 任一失敗 ⇒ 修 | 便宜且決定性，每次改動全跑 | 1 次 × 約 30 秒（`E/runs/c7_baseline_unit.txt`：30.44s） | 0 |
| C1/C2 本機 | 能不能部署 | 錯框 ≥1 或覆蓋率 <95% ⇒ 停、查原因，修一輪不過交業主 | 全部 21 份：可用文字層檔全用，達廣度下限 | 21 × 不到 1 秒（線上同類檔 43 ms：`~/jgb-archive/qwen-direct-read-20261029/t2_textlayer/after1/contract/textlayer_lease.json` `stats.total_time_ms`） | 0（文字層不呼叫模型，差距 3） |
| C5 部署前 | 留改前基準 | —（基準） | 5 份合約：每個資料組 1 份，蓋到每種版型 | 5 × 不到 5 秒（同上 43 ms＋網路） | 0 |
| C1/C2/C5 部署後 | 留在線上或回滾 | 任一不符 ⇒ 回滾 | 與部署前同一批 5 份（C5 要同檔比對）；同檔帶 v2 再送 5 份，與本機結果比對，相同即證明線上與本機同一份程式 | 10 × 不到 5 秒 | 0 |
| C6 本機 | 謄本 v2 有沒有被改壞 | 失敗或 diff 不為空 ⇒ 修 | 既有謄本 v2 測試全跑：便宜且決定性 | 隨 C7 一起跑（約 30 秒，同 C7 來源） | 0 |
| C4 部署後 | R4 在線上成立 | 有 position 非 null，或 value 與同一份回應的逐頁合併值不同 ⇒ 回滾 | 1 份 1 頁：R4 是全有全無的分支，1 份即可 | 1 次 × 約 11 秒（直讀 2 頁合約 11,055 ms：`~/jgb-archive/qwen-direct-read-20261029/t2/after1/contract/70af4d5c….json`） | 1 次 Bedrock，每頁約 $0.0019（長邊 2000：`docs/testing/bedrock-vlm-eval-20261023.md:133`） |
| C9 verifier | 能不能收案 | REFUTED ⇒ 修或回滾 | 1 位；≥10 份新輸入，對到驗收廣度第 8 條下限 | ≥10 × 不到 1 秒（本機文字層，同 C1/C2 列來源） | 約 10 萬～16 萬 token（本線 plan-verifier 第 1 輪 94,791、第 2 輪 127,661，任務通知） |
| G1～G3 產生 | 驗收資料 | — | 1 位代理 | — | 約 10 萬 token（同上量級） |
| plan-verifier | 能不能交核可 | REVISE ⇒ 改 | 收斂審查 1 位 | — | 約 9.5 萬～13 萬 token（第 1 輪 94,791、第 2 輪 127,661） |

## 5. 部署、授權請求與回滾

**和 handover-photo-v2 的協調**（兩線共改 `analyze.py`、`INTEGRATION.md`，部署同一台機器）：
- 不同時部署：一線從 push 起到它的部署後檢查做完（或回滾完）為止，另一線不 push、不部署。
- 誰先核可、先做完驗收，誰先部署。後部署的一線先 rebase 到先部署那線的 commit，重跑 C7，C5 的部署前基準在先部署那線的部署後檢查完成**之後**重量，所以基準只涵蓋「先部署那線的 commit → 本線 commit」這一段。
- `INTEGRATION.md` 版本號在本線 commit 當下取 main 上最新版的下一個小版號（main 現在是 2.10.0；handover 若先進就是 2.12.0）。
- `analyze.py` 本線只動兩處：Form 參數宣告區加 `contract_format`、攔截之後的 v2 分支。rebase 衝突只可能在這兩處，手動合併後重跑 C7。
- 回滾用 `git revert <本線 commit>`，只撤本線的改動，不動另一線的 commit。

前置：謄本缺口線的 C9 06、07 先送完（等業主重啟容器），確保那條線量到的是 `df41f2d`。

順序：
1. 本機 C7、C1、C2 過 → commit（程式＋測試，不 push）。
2. **部署前檢查**（ssh 唯讀，存 `E/runs/deploy_pre.txt`）：線上 `git -C ~/DocuMind rev-parse HEAD`、`git -C ~/DocuMind status --porcelain`、`docker inspect -f '{{.State.OOMKilled}} {{.RestartCount}}' ai-doc-backend`、`docker stats --no-stream ai-doc-backend`；本機 `git fetch` 後的 `origin/main`。必須：線上 HEAD＝`origin/main`＝本線 commit 的父 commit、porcelain 空。不符（例：另一線已 push 或部署中）⇒ 停，照上面協調規則等待或 rebase，並報業主。
3. 部署前送 C5 基準。
4. push → ssh `git -C ~/DocuMind pull --ff-only`（`--reload` 生效）→ health 200、線上 HEAD＝本線 commit。
5. 部署後送 C1/C2（5 份）、C4、C5。
6. verifier（本機）→ 文件 commit → 再做一次第 2 步的檢查（父 commit＝線上 HEAD）→ push、server pull（只有文件）。

**請業主授權**：
1. 本線的 commit、push main。
2. ssh 只為本線部署與回滾：執行 `git pull --ff-only`，以及部署前、每次送件後的唯讀查詢（`git rev-parse HEAD`、`git status --porcelain`、`docker inspect` 的 OOMKilled／RestartCount、`docker stats --no-stream`）。
3. 線上送件最多 21 次：部署前 5 次（C5），部署後 11 次（C5 不帶參數 5、帶 v2 5、C4 1），回滾時再送 C5 5 次確認。verifier 只在本機跑，不送正式機。它們的副作用如下：
   - 每次都把送的檔案上傳 S3，`acl="public-read"`（`analyze_service.py` `_upload_to_s3`）。送的只有合成檔與 jgb2 自己的範本，沒有客戶文件、沒有真實謄本。
   - 每次都在正式資料庫寫一列用量紀錄 `api_usage_log`（`analyze_service.py` `_record_usage`）。
   - 判為低信心時會在正式資料庫的複核佇列加一列（`analyze.py` `_apply_confidence_gating`）。合成租約六欄只抽到 3 欄，很可能進佇列；這些列不刪，收案時列出 ID。
   - C4 會把 1 頁合成掃描檔送 Bedrock 直讀（1 次），內容是合成租約，不是客戶合約。
4. 給 AIChatbot 的訊息由業主送。

線上送件：一次一份；每次送完查 `OOMKilled`／`RestartCount`，有變動、或回 502、或 health 不是 200 ⇒ 停送、交業主（重啟是業主的動作）；記憶體照實記錄、不當停點。依據：前例 `.kiro/specs/transcript-records-converge/plan-deploy.md` §8.1 第 1 項（「> 1.8 GiB 就等回落」做不到，改看 OOMKilled／RestartCount；實測最高 1.872GiB 後持平）；容器閒置就約 1.79 GiB、跑過 OCR 約 1.84 GiB 持平（專案記憶 `production-host.md`），固定的記憶體門檻會被閒置用量觸發。本線送件都是文字層與 1 頁直讀，不跑本機 OCR。

回滾：部署後任一檢查不符 ⇒ `git revert` 本線 commit、push、server `git pull --ff-only`，再送 C5（5 次，已含在第 3 點的上限內）確認不帶參數回應與基準相同，報業主。

## 6. 停點

- C2 本機錯框 ≥1 或覆蓋率 <95%，修一輪後仍不過 ⇒ 交業主。
- OOMKilled／RestartCount 變動、502、health 非 200 ⇒ 停送、交業主。
- 部署前檢查不符（線上 HEAD、origin/main、porcelain）⇒ 停、報業主。
- handover-photo-v2 正在部署或部署後檢查中 ⇒ 等它結束，不搶。
- verifier 提出的解讀題 ⇒ 交業主，不自行裁定。

## 7. 用量報告

收案時報：各代理實際 token（任務通知加總）、Bedrock 呼叫次數與估價、S3 上傳次數、`api_usage_log` 新增列數、複核佇列新增的 ID。

## 8. 確認版（給業主，一頁）

**要做的**：AIChatbot 上傳合約時帶 `contract_format=v2`，回應裡租約的 6 個欄位（起訖日、月租、押金、地址、承租人）各附「這個值是從原檔哪一頁、哪個位置讀到的」。

**範圍**：只有電子 PDF（有文字層）給框；抽錯的值也框它讀到的地方（你 15:00 裁定）。照片和掃描檔線上走直讀，框一律給 null；對方說過這種就只標頁碼，頁碼的取法寫進對接文件。有值但對不到原文就給 null，不猜。不帶參數的回應不變。

**怎樣算做完**：
1. 另一個不看程式的代理寫 15 份電子租約（三種版型、各種寫法），加上 jgb2 範本與既有合成檔共 21 份。給出的框一個都不能框錯（框裡的字必須就是那個值），有值的欄位至少 95% 有框。
2. 合成的掃描合約帶參數，框全是 null。
3. 不帶參數的合約，上線前後回應相同；謄本 v2 在本機確認沒被改到（不對正式機送真實謄本）。
4. 上正式機後重驗 5 份，獨立驗證員另寫 10 份新合約再驗一次。
5. 上線後由你通知 AIChatbot。

**線上會留下的東西**：送 16 次，要回滾時再加 5 次，最多 21 次。每次都會把檔案以公開可讀上傳 S3，並在正式資料庫寫一列用量紀錄；低信心時正式複核佇列會多一列（不刪，收案時列出）；1 頁合成掃描檔會送 Bedrock 1 次。送的只有合成檔和 jgb2 自己的範本，沒有客戶文件、沒有真實謄本。獨立驗證員只在本機跑。

**要你同意的一項指標（待確認）**：「錯框數」這次預期變化是 0（現在 0、做完也要 0）。它是護欄：現在是 0 只因為還沒有框，做完開始給框後要守住 0。進度看另一項「有值的欄位多少有框」，從 0% 到至少 95%。

**和另一條線**：點交照片 v2（另一個 session）也改同一支 API、同一份對接文件。兩條線不同時部署，誰先驗收完誰先上。

**風險**：手上 11 份真實合約全是掃描檔，這次做的框用不上它們（你 14:50 已選原案）。電子合約的欄位抽取率本身不高（合成租約 6 欄抽到 3 欄），抽不到的欄位沒有值、也沒有框；抽錯的會框出錯值的位置。抽取率是另一件事，記在之後再做。

**要你核可的**：這份計畫，以及 §5 的 commit、push、ssh 部署與回滾、部署前後的唯讀查詢、最多 21 次線上送件的授權，以及「錯框數預期變化 0」。

### 我改動的地方

1. **加了 R7（直讀頁碼規則寫進 INTEGRATION.md）**：你沒說。出處是我 14:37 回覆 AIChatbot 的草稿「這條規則我們會寫進 INTEGRATION.md」，那份草稿你還沒核可。理由：AIChatbot 第 2 則訊息問頁碼放在哪裡，沒寫進文件的規則，對方不能依賴。
2. **收窄：照片不做「框到整行」**。AIChatbot 原話「電子檔框到值、照片框到整行，跟謄本一樣即可」，改成照片給 null。理由：你 14:50 選「照原案只做電子檔」。
3. **加了 R8（`contract_format` 不是 `v2` 回 400，其他文件類型忽略這個參數）**：你沒說，AIChatbot 也沒說。理由：比照現行 `transcript_format`（`analyze.py` 回 `INVALID_TRANSCRIPT_FORMAT`；帶給非謄本時不處理），同一個 API 的兩個格式參數行為一致。
4. **收窄：批次端點 `/analyze/batch` 不加**。AIChatbot 原話「建議用帶參數的方式開啟（例如 contract_format=v2）」，沒有指定端點。理由：`transcript_format` 也只在 `/analyze`。
5. **加了：有值但對不到原文時給 null**，原因包括頁面幾何檢查不過、文字層與原檔不符、重跑得到的值與回應不同、值的字跨到兩行以上（不給橫跨兩行的大框）。原案原話「在原文找不到的值，position 給 null」；我把「找不到」具體化成這幾種情況。理由：對不準就不給，這是「不要猜」的做法（AIChatbot 原話「找不到位置就給 null，不要猜」）。
6. **加了前置條件：謄本缺口線的 06、07 先送完再部署本線**。你沒說。理由：避免那條線量到的不是 `df41f2d`。
7. **加了：和點交照片 v2 線的部署協調規則**（§5）。你沒說。理由：兩線改同一支檔案、同一份文件，要部署同一台機器。
8. **選了：「上線」＝部署正式機**。原話「直接開發」沒提部署；原案寫「上線後帶參數就能測」，DocuMind 沒有測試機。部署要你在 §5 授權。
9. **選了：C4 改用合成掃描檔**。你的選項說明寫「要用合成租約和範本補驗收資料」。用真實客戶合約要把合約送 Bedrock，所以改成把合成租約轉成影像檔。
10. **範本已納入驗收資料（G4）**，照你的選項說明「和範本」；第 1 版漏了，這版補上。

## 9. 第 1 輪審查處置

審查紀錄：`E/reviews/plan-review-20261113.md`。

| # | 審查意見 | 處置 |
|---|---|---|
| 1 | 和 handover-photo-v2 共改檔案，沒有歸屬與部署順序 | FIX：§0 點名，§5 協調規則，§6 停點 |
| 2 | 線上送件會寫 S3 public-read、複核佇列，C4 外送真實合約，授權沒寫 | FIX：§5 第 3 點、§8 列出副作用；C4 改合成掃描檔 |
| 3 | 範本被排除，理由與 survey 不符 | FIX：加 G4（5 份），廣度表逐組列 |
| 4 | 「我改動的地方」缺 (a)～(d) | FIX：(a) 已問業主，15:00 裁定「有值就框出處」寫進 R2；(b)～(d) 列為第 3、4、5 條 |
| 5 | 業主確認出處對不上 | FIX：選項說明逐字歸檔；14:49 改寫成回覆 14:37 那則；12:47 那句寫明已由回覆稿處理 |
| 6 | 終點指標缺現值、預期，原型宣稱與來源不符 | FIX：E1／E2 現值與來源；原型重述，並以字元中心判法重跑查明原因 |
| 7 | C2 判法沒寫正規化 | FIX：C2 判法凍結（兩邊都套 `normalize_for_matching`） |
| 8 | C5／C6 排除鍵沒列 | FIX：列 3 個鍵，其餘差異都算不符 |
| 9 | 測試選擇缺規模理由與來源 | FIX：每列補規模理由、時間來源、費用來源 |
| 10 | 頁碼 1 起算的業界宣稱不成立 | FIX：§2 改寫成三家各自的起算方式 |

第 2 輪（REVISE，4 項，皆 P2 substantive）。兩輪自動 REVISE 後不再重送一般審查，由主會話逐項處置，送一次收斂審查：

| # | 審查意見 | 處置 |
|---|---|---|
| 1 | 記憶體查詢不在 ssh 授權內、沒有部署前檢查、1.7GiB 門檻無出處且低於閒置用量 | FIX：§5 授權列唯讀指令；順序第 2 步部署前檢查（不符即停）；停點改 OOMKilled／RestartCount 變動，附前例與記憶出處 |
| 2 | C9 在哪跑沒寫；本機 TestClient 會不會寫正式 S3 | FIX：C9 只在本機；本機執行 monkeypatch `_upload_to_s3`、用臨時 Postgres；C9 補規模與時間 |
| 3 | 跨行的值會得到大框 | FIX：路徑 2 跨行規則（給 null）、偏離段說明不給多區域、G 加「民國日期中間換行」、C7 加跨行測試 |
| 4 | C4 比兩次模型呼叫 | FIX：C4 只送一次，與同一份回應的逐頁合併值比；測試選擇的回滾條件同步 |

收斂審查（REVISE，3 項：2 項 P2 substantive、1 項 wording-only）。依規則收斂審查後不再送審，處置後交業主：

| # | 審查意見 | 處置 |
|---|---|---|
| 1 | 副作用漏列 `api_usage_log` 寫入；回滾重送 5 次不在授權次數內；C6 送業主提供的真實謄本 D1，§8 卻寫「都不是客戶文件」 | FIX：§5、§7、§8 列用量紀錄；授權上限改 21 次（含回滾 5 次）；C6 改在本機驗（既有謄本 v2 測試＋謄本模組 diff 為空），不再對正式機送真實謄本，§8 的說法因此成立 |
| 2 | `docker inspect` 樣板 `.State.RestartCount` 會出錯 | FIX：改 `{{.RestartCount}}`（同前例） |
| 3 | E1 錯框數預期變化 0，沒有理由與業主同意 | FIX：E1 列寫理由（護欄），§8 加「待確認」同意項 |
