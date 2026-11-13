# 點交照片回傳格式 v2——F 片（格式＋上版）核可規則與凍結驗收清單

狀態：**已核可、凍結**（業主 2026-11-13 本 session 回「核可」，對象為 plan.md 確認版；之後收窄要重新核可）。本片只驗格式、舊格式不變與上線健康，**不宣稱任何辨識品質**；準確率另見 `accuracy-later.md`（不屬本清單）。

## 1. 業主原話（來源）

逐字全文在 `owner-words.md`：R-src-1（業主貼上的 JGB 需求文，下稱「需求文」）、R-src-2「桌面/房間物件 照片」、R-src-3（四題選項回覆）、R-src-4「先改格式 上版 準確率之後再確認」、R-src-5（三題選項回覆）、R-src-6（兩題選項回覆）。R-src-4 取代 R-src-3 的「先本機報告」；R-src-3 其餘三項與 R-src-2 移到 `accuracy-later.md`。

## 2. 規則

| ID | 可檢查的條件 | 出處（逐字） | 讀法註記 | 業主確認於 |
|---|---|---|---|---|
| R1 | `/analyze` 與 `/analyze/batch` 收 `handover_format`；值為 `v2` 且 `document_type=handover_photo` 才回 v2；值不是 `v2`（也不是不帶）回 400 `INVALID_HANDOVER_FORMAT`；非點交類型帶 `v2` 忽略 | 「jgb2 呼叫時帶參數 handover_format=v2，才回新格式」；「批次端點…維持不變」 | 兩支端點都收。**我加的**：錯值 400、非點交類型忽略（比照 `transcript_format`） | 2026-11-13 業主「核可」（本 session，確認版） |
| R2 | 不帶 `handover_format` 時，同一個模型回覆產生的回應與 `df41f2d` 逐鍵逐值相同（`file_url`、`processing_time_ms` 等每次會變的值除外） | 「不帶這個參數時，回傳必須跟現在逐個欄位完全相同」 | 讀作「同一模型回覆下相同」：模型每次回覆本來就會變。舊路徑送圖方式也不動（不補 EXIF） | 2026-11-13 業主「核可」（本 session，確認版） |
| R3 | v2 的 `furniture[]`、`appliance[]` 每項恰為 `{key, label, confidence, box, condition}` | 「每一項改成：{key, label, confidence, box, condition}」 | — | 2026-11-13 業主「核可」（本 session，確認版） |
| R4 | 每項 `confidence` 是模型對該項自評，夾在 0～1；沒給或非數值回 `null`，不拿整張補 | 「模型對「這一項」自評的 0～1。不要再拿整張照片的信心值當預設；模型沒給就回 null」 | **我選的**：非數值（如 "高"）視同沒給；超出 0～1（如 1.5、85）夾回 0～1、不回 `null`（沿用現行 `_safe_float`；和 box 越界回 `null` 不同，理由：信心值超界多是模型寫法差異，丟掉會失去資訊，box 越界則無法安全裁圖） | 2026-11-13 業主「核可」（本 session，確認版） |
| R5 | `box` 為 `{"box":[x0,y0,x1,y1],"unit":"ratio"}`，0～1、原點左上、四捨五入到小數 4 位；抓不到、越界、x0≥x1 或 y0≥y1、面積 < 整張 0.5% → `null` | 「box：{"box":[x0,y0,x1,y1], "unit":"ratio"}，0～1 的比例…遇到以下情況回 null…」 | 越界不夾回、直接 `null`。**我加的**：4 位小數；非數值或不是 4 個數 → `null`；座標以 EXIF 轉正後為準（R9） | 2026-11-13 業主「核可」（本 session，確認版） |
| R6 | `condition` 為字串，> 30 字截成 30 字；沒看到損傷回 `""`；v2 提示詞要求用繁體中文寫 | 「看得到的損傷，繁體中文，30 字以內…沒看到損傷就回 ""」 | **我選的**：「字」以 Unicode 字元數計；非字串回 `""`。「繁體中文」只放進提示詞、本片不驗證模型真的寫繁中（屬輸出品質，移到準確率片） | 2026-11-13 業主「核可」（本 session，確認版） |
| R7 | v2 有 `damages[]`，每筆 `{text, box}`；`text` > 30 字截斷；`box` 規則同 R5；提示詞要求繁體中文 | 「新增 damages[]…每筆是 {text, box}，text 30 字以內，box 規則同上」 | **我加的**：`text` 去空白後是空字串的整筆丟掉 | 2026-11-13 業主「核可」（本 session，確認版） |
| R8 | v2 保留 `space`、`space_label`、`description`、整張 `confidence`、`dropped`、白名單過濾、詞彙表、批次端點、一次最多 20 張 | 「以下維持不變：…」 | **我加的**：v2 的 `structured_data` 也保留 `field_confidences` 這個鍵（舊格式本來就有），內容依 R17 | 2026-11-13 業主「核可」（本 session，確認版） |
| R9 | v2 送模型前依 EXIF 轉正，框對應轉正後的影像 | 無原話（第一原理：jgb2 瀏覽器顯示轉正後的照片，框要能直接裁） | **我加的**：點交路徑現在沒轉正（`processor.py` `_cap_image_pixels` 後直接存 PNG） | 2026-11-13 業主「核可」（本 session，確認版） |
| R10 | v2 提示詞不列任何損傷範例詞；看不到損傷就回空 | 「點交這邊的提示詞請不要列損傷範例清單，看不到就回空」 | — | 2026-11-13 業主「核可」（本 session，確認版） |
| R11 | 模型座標刻度以實測決定並換算成 0～1 | 「在 DocuMind 端統一換算成 0～1 再回傳」 | — | 2026-11-13 業主「核可」（本 session，確認版） |
| R12 | 單元測試涵蓋：不帶參數逐鍵相同；帶 v2 欄位齊全；不合理 box 回 `null`；`condition`、`text` 超過 30 字截斷 | 「單元測試：…」 | — | 2026-11-13 業主「核可」（本 session，確認版） |
| R13 | 帶 v2 時，`needs_review`、`review_item_id` 是否為 `null`，以及複核佇列存的 pages 與 `field_confidences`，都和同一個模型回覆不帶參數時相同（`document_fields.needs_confirmation`／`extraction_confidence` 不在本條，依 R19）（`review_item_id` 每次入列都是新 UUID，只比是否為 `null`）（攔截用舊算法：品項沒給信心值時以整張補；v2 轉換在攔截之後才做，佇列存舊形狀） | 無原話（需求文沒提複核） | **我選的**：複核行為不變（替代做法：讓 null 影響複核，模糊照片會不再進複核、佇列存 v2 形狀並變成 few-shot 範例）。比照謄本 v2 先例（佇列存未轉換 pages） | 2026-11-13 業主「核可」（本 session，確認版） |
| R16 | 帶 v2 時，`document_fields` 的 `furniture`、`appliance` 每項換成 R3 的 v2 品項形狀，並加上 `damages`（內容與 `structured_data` 相同）；其他鍵不動（`field_confidences` 依 R17；`needs_confirmation`、`extraction_confidence` 依 R19） | 無原話（`INTEGRATION.md` §3.5「`document_fields` 同樣帶這些鍵」） | **我選的**：`document_fields` 跟著 `structured_data` 換形狀，下游讀哪一邊都一致 | 2026-11-13 業主「核可」（本 session，確認版） |
| R17 | 帶 v2 時，回應中看得到的 `field_confidences`（頂層、頁層、`structured_data`、`document_fields`）全部改用模型對該項的自評；模型沒給的品項不放進 `field_confidences`；複核仍照 R13 | 「不要再拿整張照片的信心值當預設；模型沒給就回 null」；R-src-5「X：全部改用自評」 | 業主裁定 X（另一選項 Y 只改品項 `confidence`，比原話窄） | 2026-11-13 本 session 選項回覆（R-src-5） |
| R19 | 帶 v2 時，`document_fields.needs_confirmation` ＝ 所有頁 v2 品項（`furniture`、`appliance`）中 `confidence` 為 `null` 或低於 `OCR_QUALITY_THRESHOLD`（0.8）的 key，排序去重；`document_fields.extraction_confidence` ＝ 有數值 `confidence` 的 v2 品項平均（4 位小數），一個都沒有就不放這個鍵；`needs_review` 不受影響（R13） | R-src-6「依自評，沒給的列待確認」（選項說明見 `owner-words.md`）；需求文「不要再拿整張照片的信心值當預設」 | 業主裁定。「沒給的列待確認」是代理在選項裡加的，業主選了它 | 2026-11-13 本 session 選項回覆（R-src-6） |
| R18 | 正式機指令由代理以 `ssh -p 22 chatbot@54.248.201.66` 執行，只限 plan.md 第 6～8 步列出的指令與 §6 回滾指令；`.env` 不讀不改、不重建容器 | R-src-5「你用 ssh 執行」 | 授權只涵蓋本片 | 2026-11-13 本 session 選項回覆（R-src-5） |
| R14 | 本片改完格式後上正式機：程式 commit 進 `main`、push、線上機 `git pull --ff-only` | R-src-4「先改格式 上版 準確率之後再確認」；需求文一「這樣 DocuMind 可以先上線」 | 「上版」讀成本 repo 既有部署做法（`.kiro/specs/transcript-records-converge/plan-deploy.md` D1）。取代 R-src-3「先本機報告」；需求文三.3 的本機比較移到 `accuracy-later.md` Q4 | 2026-11-13 業主「核可」（本 session，確認版） |
| R15 | 交工時估計 | 需求文三.3「預估工時」 | 本 session 第一次回覆給 1～1.5 工作天（含準確率比較）；本片不含準確率，估約 1 工作天 | 2026-11-13 業主「核可」（本 session，確認版） |

## 3. 凍結驗收清單

| # | 服務規則 | 檢查與觀察點 | 證據 | 通過條件 |
|---|---|---|---|---|
| A0 | R2 | **改任何程式之前**，在 `df41f2d` 用固定的假模型回覆組（正常、缺信心值、非數值信心值、模型放錯陣列、不在詞彙表、空回覆、模型丟例外）跑處理器 `understand()` 與 `AnalyzeService.analyze`（S3、用量紀錄打樁），輸出存固定檔 `backend/tests/fixtures/handover_v1_baseline.json`；產生腳本在檔內寫入 SHA、產生時間、`git status --porcelain -- backend` 輸出 | 固定檔＋產生腳本 | 檔存在、SHA＝`df41f2d`、檔內 `git status` 輸出只有固定檔與產生腳本本身（＝產生時 backend 程式未改） |
| A1 | R2, R12 | 新程式不帶參數，同一組假回覆的輸出與 A0 固定檔逐鍵逐值相同；既有 `test_handover_photo.py`、`test_api_backward_compat.py`、`test_analyze_batch.py` 不改（唯一例外：`test_api_backward_compat.py` 的 `ADDED_REQUEST_PARAMS` 登記 `handover_format`，業主 R-src-8）且全綠 | pytest 輸出 | 全綠 |
| A2 | R1, R3, R4, R7, R8, R12, R16, R17, R19 | `/analyze`、`/analyze/batch`（TestClient）帶 v2，回應每個品項恰 5 鍵、有 `damages`、R8 各鍵在；`document_fields` 的品項與 `damages` 同 R16；各處 `field_confidences` 依 R17 業主答案；`document_fields.needs_confirmation`／`extraction_confidence` 依 R19（假回覆組含：自評 0.9 與 0.5 混合、部分沒給、全部沒給三種，各自核對兩個值與鍵是否存在）；`handover_format=v3` 回 400；`document_type=bill` 帶 v2 不影響回應 | pytest 輸出 | 全綠 |
| A3 | R5, R12 | 抓不到、越界、x0≥x1、y0≥y1、面積 < 0.5%、非數值、不是 4 個數 → `null`；面積恰 0.5% 不是 `null` | pytest 輸出 | 全綠 |
| A4 | R6, R7, R12 | 31 字截成 30；非字串 → `""`；空 `text` 整筆丟掉 | pytest 輸出 | 全綠 |
| A5 | R10, R6, R7 | v2 提示詞不含修繕提示詞的損傷詞（漏水、壁癌、龜裂、設備損壞）及剝落、水漬；含「繁體中文」；提示詞全文附收案報告 | pytest＋提示詞原文 | 全綠 |
| A6 | R11 | 本機實測：3 張照片要框，依兩種換算畫回原圖目視 | 疊框圖＋原始回覆（`~/jgb-archive/handover-v2-20261113/probe/`） | 選定的換算落在物件上 |
| A7 | R9, R5 | 單元測試：帶 EXIF Orientation=6 的 JPEG 在 v2 路徑送給模型的影像已轉正；本機實測一張轉向 JPEG 的框畫在轉正後的圖上 | pytest＋疊框圖 | 全綠；框落在物件上 |
| A8 | R13, R17 | 單元測試：同一組假回覆（含品項全沒給信心值、整張 confidence 0.3）分別不帶參數與帶 v2 跑 `/analyze`、`/analyze/batch`：(a) `needs_review`、`review_item_id` 是否為 `null`、寫進複核佇列的 pages 與 `field_confidences` 兩邊相同；(b) 帶 v2 時頂層、頁層、`structured_data`、`document_fields` 四處的 `field_confidences` 都不含沒給信心值的品項 | pytest 輸出 | 全綠 |
| A9 | R14 | 正式機：部署後 HEAD＝`origin/main`；`/api/health` 200；`OOMKilled=false`、`RestartCount` 與部署前相同 | ssh 唯讀指令＋curl，存 `runs/deploy_a9.txt` | 全部成立 |
| A10 | R1, R2, R3, R5, R16 | 正式機 `/api/v1/analyze/batch`，照片 `commons_brisbane_bedroom.jpg`（Wikimedia Commons 公開照）：部署前不帶參數 1 次、部署後不帶參數 1 次與帶 v2 1 次。`keyshape.py same <部署前> <部署後不帶>`；`keyshape.py v2 <部署前> <部署後 v2> v2_expected.json` | 回應 JSON＋`keyshape.py` 輸出，存 `runs/online/` | 兩個指令都印「相同」、退出碼 0 |

**鍵形狀比對（A10 與立即回滾條件共用）**：腳本 `~/jgb-archive/handover-v2-20261113/keyshape.py`（定義寫在檔首），v2 預期形狀 `~/jgb-archive/handover-v2-20261113/v2_expected.json`。規則：字典比鍵集合並遞迴；鍵名由資料決定的字典（`field_confidences`）當一個值、不展開；清單把所有元素形狀合併（鍵取聯集），**空清單是萬用**，與任何清單都算相同；`null` 是萬用；其他純值不比內容。`v2` 模式另判：`structured_data` 的鍵集合等於預期；`document_fields` 品項與 `damages` 元素形狀等於預期；框的數值都在 0～1。
已驗證（`~/jgb-archive/handover-v2-20261113/runs/keyshape_real_control.txt`）：自測 4 項通過（3 個正對照：品項數不同、品項 key 不同、一邊清單為空都判相同；1 個反對照：品項多出 `box` 判不同）；用 2026-10-28 線上同一版程式、同一張照片的三次真實回應比對，after1 對 after2、after3 都判相同，13 張照片 after1 對 after3 也全判相同；反對照（真實回應的品項加 `box`）判不同。

## 廣度

| 項目 | 類型 | 資料組（用／可用） | 不同輸入數 | 重複次數 | 輸入撰寫者 | 改前對照 |
|---|---|---|---|---|---|---|
| A0–A5、A7 單元測試、A8 | 機制項 | — | — | — | — | — |
| A6、A7 實測 | 機制項（換算與轉正對不對，不宣稱辨識品質） | — | — | — | — | — |
| A9、A10 | 機制項（上線健康、格式在線上成立） | — | — | — | — | — |

上位驗收方式：無（DocuMind 沒有點交照片的工作線目標正本）。需求文第四節的單元測試排入 A1–A4；同批照片新舊並列依 R-src-4 移到 `accuracy-later.md`。本片沒有使用者層項目。
