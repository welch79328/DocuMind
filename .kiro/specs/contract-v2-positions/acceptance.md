# 合約 v2 位置：核可規則與凍結驗收清單

> 凍結於 2026-11-13 15:19（業主核可 `plan.md` 第 3 版，模式 ASK：本機開發與驗收照跑，push／ssh／線上送件前問業主一次）。
> 本檔是驗證、挑戰與解讀爭議的判定基準；之後收窄要重新核可。設計、部署順序與授權細節見 `plan.md` §2、§5。
> 證據目錄 E = `~/jgb-archive/contract-v2-positions-20261113/`

## 規則（業主確認版）

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
| R6 | 部署到正式機（沒有測試機），上線後由業主通知 AIChatbot；不承諾日期 | 原案「我們沒有另外的測試機，上線後帶參數就能測」；14:49「不用決定日期」 | 14:49、14:50；部署授權 15:19 核可計畫第 3 版（AskUserQuestion 回答「核可，照第 3 版做 (Recommended)」，session jsonl 2026-11-13T07:19:23Z） |
| R7 | `docs/api/INTEGRATION.md` 寫入 `contract_format=v2`，並寫明直讀的頁碼取法（依頁序第一個 `pages[].structured_data.rental_terms.<欄位>` 非 null、非空字串那頁的 `page_number`） | **我加的**（§8 第 1 條） | 15:19 核可計畫第 3 版（AskUserQuestion 回答「核可，照第 3 版做 (Recommended)」，session jsonl 2026-11-13T07:19:23Z） |
| R8 | `contract_format` 不是 `v2` 回 400 `INVALID_CONTRACT_FORMAT`；`document_type` 不是 `contract` 時忽略這個參數 | **我加的**（§8 第 3 條），比照 `transcript_format` | 15:19 核可計畫第 3 版（AskUserQuestion 回答「核可，照第 3 版做 (Recommended)」，session jsonl 2026-11-13T07:19:23Z） |

## 驗收清單（凍結）

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

## 廣度

| 項目 | 類型 | 資料組（用／可用） | 不同輸入數 | 重複次數 | 輸入撰寫者 | 改前對照 |
|---|---|---|---|---|---|---|
| C2 框到出處 | 使用者層 | 5／5（G1、G2、G3、G4、D-old） | 21 份（15＋5＋1）× 6 欄 | 1（決定性：同檔同程式結果相同） | G1～G3：不讀程式的代理；G4：jgb2 與既有合成檔；D-old：既有合成檔 | 改前沒有位置（`E/runs/current_e1e2.txt`），沒有可比的成效；宣稱只寫「機制做對＋錯框 0、覆蓋率 x%」 |
| C1、C3～C8 | 機制項 | — | — | — | — | — |

上位驗收方式：無。
可用但沒用在 C2 的：`data/contracts/` 11 份真實合約（全是掃描檔，NO-TEXT，C2 量不到；C4 也不用，改用合成掃描檔避免外送客戶合約）。

## 終點指標

目標文件＝本片 `acceptance.md`。

| 指標 | 現值（`df41f2d`） | 來源 | 本片預期 |
|---|---|---|---|
| E1 錯框數 | 0（沒有任何框） | `E/runs/current_e1e2.txt`（`contract_format` 0 處，正對照 `transcript_format` 11 處） | 維持 0（門檻 0）。理由：E1 是護欄不是進度——現值 0 只因為還沒有框；本片開始給框後要守住 0。本片的進度量在 E2。業主同意：15:19 核可計畫第 3 版（AskUserQuestion 回答「核可，照第 3 版做 (Recommended)」，session jsonl 2026-11-13T07:19:23Z） |
| E2 覆蓋率 | 0%（0 個值有框） | 同上 | 0% → ≥95% |

佐證（不是現值，是可行性）：原型在 D-old 抽到 3 欄。以 `get_textbox` 取框內字時，`rental_address` 多一個開頭的冒號（`E/runs/proto_contract_pos.txt`）；改用 C2 判法（字元中心＋正規化）重跑後，3 欄都與值相同（`E/runs/proto_center.txt`）。所以冒號是 `get_textbox` 把框邊的鄰字算進來，不是框錯。
前兩片：無（新線）。

## 測試選擇與成本

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
