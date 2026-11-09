# S3 照片位置——片計畫（2026-11-09 業主核可）

本片是 `plan.md` program envelope 的 S3（envelope 與 S1 於 2026-11-09 業主核可；S1＝commit `76fa153`、S2＝commit `761fff3`，分支 transcript-converge，未 push）。規則與驗收清單照 `acceptance.md`（凍結＋檔尾「核可後更正」AM-1～AM-7；AM-6 為本片新增的 C11 判定細節、業主 2026-11-09 確認；AM-7 為本片 R5 的放寬、業主已選），本片不另改規則；本檔只寫做法、量法與本片才要定的細節。量測檔目錄 `~/jgb-archive/transcript-photo-fullparse-eval-20261109/`（簡寫 `E/`）。

## 0. 目標正本定位

目標正本：`docs/planning/transcript-status.md`。
- 碰到的原則（§1）：「電子謄本上印的每一項都要解析出來、而且讀對」——本片只在帶參數的 `transcript_records` 每個照片值旁附「那一行」的位置，不改值；「實際要處理的謄本是電子檔，掃描／拍照排到提升機器規格之後」——本片碰照片，依據是業主 2026-11-09 選「電子 PDF＋照片都做」（R5），只做位置，不含提升 OCR 讀對率；「修法一律通用，不打特規」——定位用值文字搜 OCR 行＋鍵名，不列欄位或字元清單（`memory/general-fix-not-local-patch.md`）。
- 碰到的待辦列（§5）：無新增；本片服務 envelope §3 S3 列「JGB 欄位位置需求」（照片）。
- 已知偏離：目標正本沒有編號的已知偏離；本片不屬過渡修正。
- 終點的目標文件：`acceptance.md`（envelope §5 已點名）。

風險觸發：資料／序列化格式（帶參數回應的照片 `position` 從一律 `null` 變成有值；OCR 引擎內部結果多帶行框）＋跨元件驗收（AIChatbot 正式機、jgb2 staging 讀不帶參數的回應，必須不變；改到 OCR 共用路徑 `engine_manager`，其他文件類型也走）→ 送審前派 plan-verifier、收案前 verifier（envelope 收案 verifier 在 S1～S3 後一次，見 §6）。
審查紀錄：/Users/chenqinghuang/jgb-archive/transcript-photo-fullparse-eval-20261109/reviews/plan-review-s3-round3-20261109.md（收尾審查第 3 輪 READY）
審查沿革：第 1 輪 REVISE，報告 /Users/chenqinghuang/jgb-archive/transcript-photo-fullparse-eval-20261109/reviews/plan-review-s3-round1-20261109.md（6 個 blocker 全 FIX，處置寫在報告檔尾）；第 2 輪 REVISE，報告 /Users/chenqinghuang/jgb-archive/transcript-photo-fullparse-eval-20261109/reviews/plan-review-s3-round2-20261109.md（2 個 blocker 全 FIX；兩次自動 REVISE 後的新 readiness epoch，第 3 版送一次收尾審查）。

## 1. 本片承接的規則與驗收項（不改，只引用）

| 規則／驗收 | 本片怎麼承接 |
|---|---|
| R4 | 照片（及無文字層 PDF）帶參數時，有值葉子的 `position`＝`{"page": 1 起算, "box": [x0,y0,x1,y1] 0～1 比例, "unit": "ratio"}`；找不到給 `null`；`判定`、`部是否印出` 不包 |
| R5 | 照片／掃描框到「值所在的那一行」（OCR 行框），不框到字 |
| R2 | 不帶參數，整份回應除易變鍵（`file_url`、`stats`、`review_item_id`，與 S2 `check_s2_http.py` 同）外逐位元不變，含 `pages[]` 全部內容（`ocr_raw.text`、`ocr_raw.confidence`、`overall_confidence`、`needs_review`）、其他文件類型、`/analyze/batch`、`/api/v1/ocr/test` |
| C11 | 照片：用 `E/images/degraded/*.json` 的 `page_corners`，把同一格在電子 PDF 上的值框（S2）中心投影到照片座標；照片回的行框包含投影中心的比例 ≥90%；有值路徑中有位置的比例照實報 |
| C12 | 展示項：照片原圖畫出回傳的 `position` 框，3 張（3 種劣化各 1、3 份不同文件），`shot-annotate` 截圖給業主看；不擋收案 |
| C10 | S2 已過；本片改 `transcript_records`（電子、照片共用），重跑 |
| C1～C9、C15 | 已驗；本片改 OCR 共用路徑與 API，重跑（§4） |

**C11 判定細節**（凍結清單沒寫的部分；寫成 `acceptance.md` AM-6（業主確認於 2026-11-09 AskUserQuestion「可以」；多行讀法 AM-7 已確認），連同確認頁 `confirm-s3.md` 交業主）：
- 「同一格」＝照片單頁回應的 `transcript_records` 與「電子原檔同一頁抽成單頁 PDF」帶參數回應的 `transcript_records`，以 `E/proto_fill.sheet_keys`（S1 評分用的同一個對齊）對齊張，再以葉子路徑對齊（與 C1 評分同口徑）。
- 投影＝`cv2.getPerspectiveTransform` 從電子頁四角 (0,0)(1,0)(1,1)(0,1) 到 `page_corners`（照片像素），再除以照片寬高。
- 「行框包含」＝投影中心點落在照片 `box` 內（含邊界）。
- 分母＝照片 `position` 非 null、且電子同格 `position` 非 null 的葉子；兩邊有一邊 null 的另計、照實報；分母為 0 ⇒ FAIL（非 0 退出）。

## 2. 目標 → 目標形態 → 差距 → 路徑

**目標**（`acceptance.md` R4、R5；JGB 原文「能不能在回傳的每一筆結果裡加上位置資訊？…找不到位置的欄位可以不給，或給 null」）：照片謄本帶參數時，下游拿到每個值在原圖上「那一行」的框，能在照片上標出來讓人核對。

**目標形態**：envelope §2 已查（`plan.md` §2：Azure Document Intelligence 回欄位 `boundingRegions`、Google Document AI 回 `pageAnchor`／`boundingPoly`、AWS Textract 回 `Geometry.BoundingBox` 比例座標；三家都把位置放在每個值旁，引文存 `E/sources/`，envelope 審查已逐句核對）。行框代值框：envelope §2 偏離 D3「查無業界對應，屬第一原理取捨」，本片照用。**以值文字反查 OCR 行**：業界對應未查完——上述三家的位置由抽取模型自己回、不是事後反查；LLM 抽取工具把抽出的字串對回原文位置（source grounding）可能是對應做法，本片沒有渲染取證，不引用。本片依第一原理——本系統照片值由規則與解析器從 OCR 全文抽出，抽取端沒有記來源行；反查是不改抽取器、對所有來源一致的做法。

**差距**（2026-11-09 盤查）：
1. 行框在 `app/lib/ocr_enhanced/engine_manager.py` `_run_paddleocr` 被丟掉：PaddleOCR 3.x `predict()` 回 `rec_texts`／`rec_scores`／`rec_polys`，只讀前兩個；`ocr_raw`＝`{text, confidence}`（`app/lib/multi_type_ocr/processor.py` `OcrDocumentProcessor.analyze`）；repo 內 `rec_polys` 0 處讀取（正對照：`rec_texts` 命中 `engine_manager.py`、`app/lib/ocr_service.py`）。
2. 影像轉換只有等比例縮放：`processor._cap_image_pixels`（超過 `OCR_MAX_IMAGE_PIXELS` 等比縮小）、`preprocessor.adjust_resolution`（等比放大）；無旋轉／去斜／裁切／透視（`app/` grep `rotate|deskew|warpAffine|warpPerspective|minAreaRect|copyMakeBorder|\.crop\(` 只命中 `direct_read_processor.py` 的 `exif_transpose`，非本路徑）。所以 `rec_polys ÷ 送進 predict() 的影像寬高`＝原圖比例座標。EXIF 方向沒有套用（OCR 路徑無 `exif_transpose`）。
3. 解析器吃的是 `rule_postprocessed.text`（`analyze_service._attach_full_transcripts`），`TranscriptPostprocessor.correct_field_formats` 的 `re.sub` 會跨換行合併（`地號[\s:：]*…` 等），行號不一定對得回 OCR 行；照片值大多由 S1 規則補值而來（S1 前 `transcript_records` 照片值 73 個讀對，補值後 167），補值來源（25 欄抽取器）沒有記來源行。
4. 共識與多引擎：`OCR_CONSENSUS_ENABLED` 預設 False；融合 `best`／`smart` 都是整段選一個引擎（`engine_manager._fuse_results`），不逐行混合；選到 Tesseract 時沒有 PaddleOCR 行框。

**路徑**：
1. `engine_manager._run_paddleocr`：多回 `lines: [{"text", "box": [x0,y0,x1,y1] 比例, 4 位小數}]`（`rec_polys` 每行外接矩形 ÷ 送進 `predict()` 的 `img_rgb` 寬高）；`rec_polys` 缺或與 `rec_texts` 數量不同 ⇒ `lines` 為 `None`。`text`、`confidence` 不變。
2. 傳到頁結果：`TranscriptProcessor.extract_text` 已拿到 `extract_text_multi_engine` 的各引擎結果；只有「融合後文字＝PaddleOCR 那份 `text`」時，把 `lines` 交到**該頁**結果的私有鍵 `_ocr_lines`（只在 transcript 處理器）。**行框必須隨該頁那一次呼叫的回傳值或區域變數交回該頁結果，禁止存在處理器、service 或模組層級的可變屬性上**：同一請求只建一個處理器（`analyze_service.py` 處理器建立處），各頁以 `asyncio.gather` 並發（上限 `OCR_MAX_CONCURRENT_PAGES`＝4，`config.py`），基底 `analyze` 在 `extract_text` 之後還要 await 後處理與欄位抽取才組頁結果（`processor.py` `OcrDocumentProcessor.analyze`），存在實例上會被下一頁蓋掉。另外三條限制（凍結的照片受測路徑 `acceptance.md`「照片受測路徑」與 `E/measure_s1_impl.py` 把 `proc.extract_text` 換成只回 `(text, conf)` 的函式、再呼叫 `proc.analyze`）：(i) `extract_text(image) -> (text, confidence)` 兩項介面不變；(ii) `analyze` 只呼叫一次 `self.extract_text`，不另跑 OCR；(iii) `extract_text` 被換掉、拿不到行框時，`analyze` 照常完成、該頁沒有 `_ocr_lines`。建議做法：`TranscriptProcessor.extract_text` 把行框放進 `contextvars.ContextVar`（`asyncio.gather` 每頁是獨立任務、各有自己的 context，不跨頁），基底 `analyze` 在同一任務內讀出後放進該頁結果並清掉；executor 可換做法，但須滿足以上全部限制。
3. 不外流：`AnalyzeService.analyze` 第 6 步組回應前，把每頁 `_ocr_lines` 取出，頁結果裡不留；取出的行框只在呼叫端傳入容器時交給呼叫端（例：`analyze(..., ocr_lines_out: dict | None = None)`，以頁碼為鍵；不傳就丟棄），不存 service 實例屬性（`/analyze/batch` 整批共用一個 service，`analyze.py` 批次段）；`app/api/v1/ocr_test.py` 直接呼叫 `processor.process` 的地方同樣先移除。結果：不帶參數的回應、複核佇列 `original_result`、`/analyze/batch`、其他文件類型都不出現此鍵。
4. API 單檔端點：呼叫 `service.analyze` 時傳入容器，第 8 步 `apply_transcript_format(result, contents, ocr_lines=<容器>)`；批次端點不傳。
5. 照片位置組裝（`transcript_positions.py` 加照片段，或新函式）：只對 `text_layer` 不是 true、有 `_ocr_lines`、且該頁 `ocr_raw.text`＝各行 `text` 以 `\n` 相接（一致性檢查，不一致 ⇒ 該頁全 null）的頁。影像檔 EXIF `Orientation` 標記存在且不是 1 ⇒ 該頁全 null（框座標系與下游看到的方向不同，不猜）；沒有標記視為 1。每個有值葉子：
   - 候選行＝正規化（`normalize_for_matching`＋去空白）後含正規化值字串的行；值是數字時，另含「行內任一數字記號 `to_number` 等於值」的行。
   - 0 行 ⇒ `null`；1 行 ⇒ 該行；多行 ⇒ 先留「葉鍵或上一層鍵名（去掉 `[i]`）出現在值之前」的行，有就取其中 OCR 順序第一行，沒有就取候選第一行（業主 2026-11-09 選「挑一行給框」，AskUserQuestion）。
   - `page`＝頁碼（影像＝1；無文字層 PDF＝該頁頁碼）；`box`＝該行框。
   - 多頁文件（無文字層 PDF）以「值所在的張」對到頁：每張 `transcript_records` 記在哪幾頁由解析器帳目（`parse_with_ledger(track=True)` 每個值的 spans 帶頁）可得；候選行限該張出現的頁，`page`＝命中行所在頁。帳目拿不到頁 ⇒ 候選行用全部頁、依頁序取第一。
6. 電子 PDF（S2）與不帶參數路徑不動。

**可行性探查**（`E/probe_s3.py`，輸出 `E/runs/probe_s3.txt`，2026-11-09 12:2x，受測物 `761fff3`；用 `E/runs/ocr_boxes/` 已存 OCR 行框，與 `run_ocr.py` 同參數但未經 `_cap_image_pixels` 縮小）：照片 15 頁 183 個有值葉子，每個都搜得到 ≥1 行；唯一行 110 個，行框含投影中心 109；多行 73 個，照上面規則含中心 61（取第一行不加鍵名 47）；合計 170/183＝92.9%。**這是在同一批 15 頁上調出來的規則（樣本內）**；正式量測走真實 OCR 路徑（影像會先縮到 1MP，OCR 結果與探查不同），樣本外輸入見 §6。探查中不含中心的 13 個：`謄本.編號類型` 6（值「建號／地號」先命中抬頭「（建號全部）」）、同值重複的清單項 4（`層次[i].面積` 同為 96.51，取到第一行）、`登記次序` 2、唯一行 1（`建物坐落地號[0].編號`）。

## 3. 範圍與擁有者

| 項目 | 檔 | 擁有者 |
|---|---|---|
| OCR 行框 | `app/lib/ocr_enhanced/engine_manager.py`（`_run_paddleocr` 回 `lines`） | executor |
| 行框交到頁結果、移除 | `app/lib/multi_type_ocr/transcript_processor.py`、`app/lib/multi_type_ocr/processor.py`（若需要）、`app/lib/ocr_enhanced/types.py`（`EngineResult` 若需補 `lines` 鍵）、`app/services/analyze_service.py`（第 6 步前取出）、`app/api/v1/ocr_test.py`（移除） | executor |
| 照片位置組裝 | `app/lib/multi_type_ocr/transcript_positions.py`、`app/lib/multi_type_ocr/transcript_records.py`（`apply_transcript_format` 多收 `ocr_lines`） | executor |
| API 單檔端點 | `app/api/v1/analyze.py`（只改單檔端點第 6 步的 `service.analyze(...)` 呼叫——傳容器——與第 8 步一行；批次端點不動） | executor |
| 單元測試 | 新 `tests/unit/test_transcript_positions_photo.py`（合成行框：唯一／多行鍵名／多行無鍵名／0 行／數字記號／一致性不符整頁 null／EXIF 旋轉 null／`_ocr_lines` 不出現在 `analyze` 回傳與 `pages`／**≥3 頁並發（假 OCR 各頁延遲不同），每頁行框對到自己頁碼**／不傳容器時行框丟棄／**`extract_text` 被換成只回兩項的函式時 `analyze` 正常完成、頁結果沒有 `_ocr_lines`**）；`tests/unit/test_transcript_positions.py`、`test_transcript_format_v2.py` 補參數；engine_manager 行框換算測試（假 `predict` 結果） | executor |
| 驗收腳本 | `E/check_s3_c11.py`（新，跑前凍結 sha1；照片與無文字層 PDF 兩種輸入）、`E/check_s3_http.py`（新：整份回應改前改後、`/analyze/batch`、`/api/v1/ocr/test`、其他文件類型、`position` 形狀）、`E/degrade_oos.py`（新：樣本外照片，見 §6）、`E/check_s3_c15.py`（由 `check_s1_c15.py` 複製，加斷言 `original_result` 與回應任何位置不含 `_ocr_lines`）、C12 截圖 | 主會話 |

非目標：提升 OCR 讀對率；框到字（R5 只要行）；EXIF 旋轉的照片給框（給 null）；Tesseract 結果、共識／`cross_check` 模式的行框（給 null）；直讀（Qwen）路徑；不帶參數回應的任何改動。

可碰的既有檔只有上表列的；executor 碰到清單外的既有檔須先停、回報主會話。

**回滾**：S2＝commit `761fff3`。開工前狀態（2026-11-09 實查 `git status --porcelain`）：` M .kiro/specs/transcript-records-converge/acceptance.md`、`?? .claude/`、`?? .kiro/specs/transcript-records-converge/confirm-s3.md`、`?? .kiro/specs/transcript-records-converge/plan-s3.md`；executor 開工前主會話重查一次、存 `E/runs/s3_git_before.txt`。還原：`git checkout 761fff3 -- <上表 backend/ 下的既有檔>`；刪除只限本片新增、列在上表的 `backend/` 檔（新測試檔），**不碰 `.kiro/specs/`、`.claude/` 與 `E/`**；再跑單元測試全套，失敗清單與 `E/baseline_s1/fail_s1.txt` 的 18 個逐項相同。

## 4. 每次執行（測試選擇）

| 執行 | 回答的決定 | 改變下一步的結果 | 規模與理由 | 成本（跑前估，附來源） |
|---|---|---|---|---|
| 單元測試全套 | 便宜決定性檢查 | 新增紅 ⇒ 不送驗收；既有 18 個（`E/baseline_s1/fail_s1.txt`）不算 | 全套 | 約 55 秒（2026-11-09 S2 收案實跑）；0 模型呼叫 |
| OCR 跨程序決定性（改前 :18088 同一張照片送 2 次、另起 :18088 重啟後再 1 次） | 下面「整份回應逐位元」比對能不能用 | 3 次整份回應（除易變鍵）不同 ⇒ 停，不放寬比對，回報主會話與業主 | 2 張（劣化類型不同的 D1p1、D4p1） | 6 次 × 2.4–9.5 秒（`E/runs/s1_c15.txt`，:18087 真 OCR）＋重啟約 60 秒，約 2 分鐘；0 模型呼叫 |
| C11 照片 15 頁（`check_s3_c11.py`，真 OCR，本機 :18087 改後）——**樣本內** | 照片行框對不對、有位置的有多少 | 含中心 <90% ⇒ 停，看逐格錯例決定修或交業主 | 15 頁全部（3 種劣化 × 5 份文件，C11 凍結的資料組；少一頁就少一種劣化或一份文件） | 15 × 2.4–9.5 秒（`E/runs/s1_c15.txt`）＋電子單頁 15 次約 0.1 秒（`E/runs/s2_http.txt` 電子 5 份約 2 秒）；約 2.5 分鐘；0 模型呼叫 |
| C11 樣本外：內容新 6 張（§6） | 選行規則在調參沒看過的版面上是否還 ≥90% | <90% ⇒ 停、交業主（附逐格錯例），不在本片內再調規則 | 6 張＝內容新的全部（D2p4、D4p2 × 3 種劣化）；少於 6 張就少一種劣化 | 6 × 2.4–9.5 秒（同上），約 1 分鐘；0 模型呼叫 |
| 多頁無文字層 PDF（D3 6 頁、D5 3 頁乾淨圖 `E/images/clean/` 組成純影像 PDF，`check_s3_c11.py` PDF 模式） | 多頁時 `page` 對不對、並發下行框有沒有掛錯頁 | 任一非 null `position` 的 `page` ≠ 電子同格 `page` ⇒ 停；含中心（電子框中心直接比，不投影）<90% ⇒ 停 | 2 份 9 頁（最多頁的 D3、次多且乾淨圖齊全的 D5；並發上限 4，6 頁與 3 頁分別跨批與不跨批）；機制項，內容在樣本內 | 9 × 2.4–9.5 秒，約 1.5 分鐘；0 模型呼叫 |
| 照片真 OCR 不帶參數改前改後（`check_s3_http.py`） | OCR 共用路徑改動有沒有改到不帶參數回應（R2） | 整份回應除 `file_url`、`stats`、`review_item_id` 外任何差異，或回應任何位置出現 `_ocr_lines` ⇒ 停 | 照片 15 頁全部（改的是每頁都走的 OCR 函式，判不出哪頁不受影響）；改前 :18088（`49faf53` worktree＋OCR，不帶參數輸出 S1、S2 未改）、改後 :18087；兩邊都用 `backend/venv` 同一個 Python 與 OCR 套件（:18086 現行啟動指令即用此 venv） | 30 × 2.4–9.5 秒（`E/runs/s1_c15.txt`），約 5 分鐘；0 模型呼叫 |
| `/analyze/batch`、`/api/v1/ocr/test`、其他文件類型，不帶參數（同上腳本，改前 :18088、改後 :18087） | 這三個出口回應不變、不含 `_ocr_lines`（R2） | 整份回應除易變鍵（batch 另排除每檔 `file_url`、`stats`）外任何差異，或出現 `_ocr_lines` ⇒ 停 | batch：`document_type=transcript`、`enable_llm=false`，照片 1 張＋電子 1 份；`/api/v1/ocr/test`：`document_type=transcript`、`enable_llm=false`，照片 1 張；其他類型：`data/transcript_samples/01_shilin_land.jpg` 以 `document_type=contract`、`enable_llm=false` 送 1 次（只驗 OCR 共用路徑與回應，不看內容；`enable_llm=false` 時合約後處理不帶影像、不呼叫模型，`processor.py` 步驟 4、`contract_processor.py` `postprocess`） | 改前改後各 3 次真 OCR＋2 次電子，6 × 2.4–9.5 秒＋約 1 秒，約 1 分鐘；0 模型呼叫 |
| 照片帶參數 `position` 形狀（同上腳本） | R4 形狀 | 非 null 者 `page` 非整數 ≥1、`box` 非 4 個 0～1 且 x0≤x1、y0≤y1、`unit`≠`"ratio"` ⇒ 停 | 15 頁，與 C11 同一次回應 | 0 額外 |
| C10 電子 5 份（`check_s2_c10.py`，sha1 `9a97c4c67195`）＋C5～C9（`check_s2_http.py`，sha1 `54e443b578f4`，不改：其照片段走已存 OCR 文字的組裝路徑、不經 OCR、沒有行框，position 仍應全為 null） | `transcript_records.py`／`transcript_positions.py` 改動有沒有改到電子 | C10 (a)(b) <95% 或任何 FAIL ⇒ 停 | 電子 5 份全部（同檔共用） | 約 2 秒（`E/runs/s2_http.txt` 執行 12:14:36、`s2_impl.txt` 12:14:38）＋C10 約 5 秒（S2 實跑）；0 模型呼叫 |
| C1～C4 收案重量（`measure_s1_impl.py`，不改） | 照片終點有沒有退、凍結的照片受測路徑在改後還能跑 | 跑不完、或輸出與 `E/runs/s2_impl.txt` 除檔首（指令、執行時間、受測物）外不逐行相同 ⇒ 停 | 15 頁＋5 份合併，同 S1 | 約 1 秒（S2 實跑，`s2_impl.txt` 與 `s2_http.txt` 執行時間差 2 秒內）；0 模型呼叫 |
| C15（`check_s3_c15.py`，3 張低信心照片，:18087） | 複核佇列不受影響、私有鍵沒進 DB | FAIL 或 0 頁產生複核項目 ⇒ 停 | 同 S1 的 3 頁（S1 實跑 2/3 產生複核項目） | 6 次 × 2.4–9.5 秒（`E/runs/s1_c15.txt` 實跑），約 1 分鐘；0 模型呼叫；寫本機 DB 5433 `review_queue_items` 約 4 筆（本機，收線時列出） |
| C12 截圖 3 張 | 給業主看框長怎樣（展示，不作宣稱） | 不改下一步；業主看了覺得框不對 ⇒ 業主決定 | 3 種劣化各 1、3 份不同文件 | 用 C11 同一批回應，不另送；`shot-annotate` 3 張約 1 分鐘（估計，無前次實測）；0 模型呼叫 |

不跑：直讀（Qwen）路徑、線上（C14，另問）。

## 5. 終點指標（目標文件＝`acceptance.md`）

受測物：DocuMind `761fff3`（S2 後）。同一目標前兩片：S1、S2。

| 指標 | 現值（`761fff3`） | S1 實際變化 | S2 實際變化 | S3 預期 | 現值來源 |
|---|---|---|---|---|---|
| E1 照片 15 頁葉值讀對（816）（C1） | 167 | 73→167 | 0 | 不變（≥167） | `E/runs/s2_impl.txt`（與 `baseline_s1/s1_impl.txt` 逐行同） |
| E1a 照片 15 頁錯值（C1） | 7，全與舊欄位同值 | 0→7 | 0 | 不變 | 同上 |
| E1b 照片 15 頁多出值（C1） | 0 | 0 | 0 | 0 | 同上 |
| E2 照片合併 5 份讀對（703）（C2） | 101 | 62→101 | 0 | 不變 | 同上 |
| E2a 照片合併錯值（C2） | 2，全同值 | 0→2 | 0 | 不變 | 同上 |
| E2b 照片合併多出值（C2） | 0 | 0 | 0 | 0 | 同上 |
| E3 jgb2 8 格（26）（C3） | 讀對 9、錯 0 | 0→9 | 0 | 不變 | 同上 |
| E4 判定讀對（45）（C4） | 40；0 | 35→40 | 0 | 不變 | 同上 |
| E5 電子帶參數與不帶參數不同份數（C5） | 0/5 | →0/5 | 0 | 0/5 | `E/runs/s2_http.txt` |
| E6 電子位置吻合率（C10 a，AM-3＋AM-4） | 717/729＝98.4% | 不適用 | 0→98.4% | 不變（≥95%） | `E/runs/s2_c10.txt` |
| E6a 電子有位置比例（C10 b） | 729/740＝98.5% | 不適用 | 0→98.5% | 不變 | 同上 |
| E7 照片行框包含率（C11） | 沒有位置（照片 `position` 一律 `null`） | 不適用 | 不適用 | ≥90%（樣本內探查 92.9%） | `E/runs/s2_http.txt` 照片「position 全為 null」列 |
| E7a 照片有值葉子有位置比例（C11 照實報） | 0% | 不適用 | 不適用 | 照實報（探查 183/183 搜得到行；真 OCR 未量） | 同上 |

斷路器不適用（S2 有變化）。

## 6. 收案與驗證

本片完成條件：§4 全部執行通過（C12 除外，展示項）、C11 樣本內 ≥90%、樣本外內容新 6 張 ≥90%、多頁 PDF `page` 全對且 ≥90%、單元測試無新增紅。

**樣本外輸入**（選行規則是在 15 頁樣本內調出的）：可用的電子謄本共 5 份 17 頁（下載、桌面、`data/` 的其他謄本 PDF 經 sha1 與全文比對都是這 5 份的副本，2026-11-09 實查），照片用掉 15 頁，有電子原檔可比、內容沒出現過的只有 2 頁（`backend/data/transcript_samples/` 6 張真實照片沒有電子原檔，無法照 C11 投影比對，不列入）：
- 內容新（本片停點）：`D2p4`（建物，32 個有值葉子）、`D4p2`（建物，29 個）× 3 種劣化（scan_mfp、phone_flat、phone_oblique）＝6 張；`E/degrade_oos.py` 沿用 `degrade.py` 的函式與凍結規格，種子＝sha256(頁ID|類型|2)；乾淨圖照 `prep_and_grade.py` 同法（300 dpi）。**核可後、executor 開工前**由主會話產生，sha1 寫入 `E/images/oos/SHA1SUMS`，executor 不讀這些檔。只有 2 頁、61 個葉子，結果照實報、附逐格錯例。
- 只換劣化（收案 verifier）：verifier 另寫 ≥10 張（15 頁換成沒用過的劣化類型或新種子），在本機真 OCR 路徑跑 C11 同口徑；這部分版面已在樣本內，只量劣化推廣，結果照實報。

之後接 S4；envelope 的收案 verifier 在 S1～S3 完成後一次跑（envelope §1、§4）。

## 7. 我改動的地方（相對 envelope 與凍結清單）

| 原文（出處） | 本片改成 | 理由 |
|---|---|---|
| envelope §3 S3「保留 OCR 行框 → 同一條鏈；補進的值以值文字搜 OCR 行定位」（`plan.md` §3） | 照片所有值（不只補進的）都以值文字搜 OCR 行定位 | 解析器吃後處理過的文字，`correct_field_formats` 會跨行合併，行號對不回 OCR 行（§2 差距 3）；一套做法對所有來源一致 |
| R5「照片／掃描框到值所在的那一行」（`acceptance.md` R5） | 值文字出現在多行時，依「鍵名在值之前」與 OCR 順序挑一行 | **放寬**，業主 2026-11-09 選「挑一行給框」（AskUserQuestion；選項已寫明比「框到那一行」寬、約 7% 框到別行）；另一讀法多行給 `null` 未採 |
| R4「找不到位置時 `position` 給 `null`」 | EXIF 方向非 1 的影像整頁 `null`；OCR 選到 Tesseract 時 `null`；共識模式（`OCR_CONSENSUS_ENABLED`）或 `OCR_FUSION_METHOD=cross_check` 時照片位置全 `null`（預設各為 False、`best`，`app/config.py`；線上值沒查，C14 部署時查）；頁文字與行框不一致整頁 `null` | 座標系或行框來源對不上時不猜；共識模式要另接 `extract_text_candidates`，不在本片 |
| C11（`acceptance.md`；沒寫怎樣算同一格、怎樣投影、分母） | AM-6：同一格＝電子同頁單頁 PDF 回應以 S1 評分同一對齊方式對齊；透視投影；分母＝兩邊都有位置的葉子 | 凍結清單沒寫細節，照 S1 評分口徑補 |
| C11 只寫照片 15 頁 | 加樣本外內容新 6 張與多頁無文字層 PDF 9 頁兩個停點 | **放寬**（多驗）：規則是樣本內調出的；R4 涵蓋無文字層 PDF |
| R2「其他文件類型與 `/analyze/batch` 不受影響」 | 其他文件類型只用 1 張影像以 `contract` 送驗 OCR 共用路徑與回應鍵 | `engine_manager` 共用；本機沒有合約影像樣本，以謄本影像驗共用路徑不驗內容 |

## 8. 用量回報

本片已用：盤查 scout 126,127 tokens；plan-verifier 第 1 輪 218,661 tokens、第 2 輪 176,474 tokens、第 3 輪（收尾）146,338 tokens（2026-11-09）；主會話探查。收尾審查後補；執行後補 executor token。模型費用 0（不呼叫模型）。
