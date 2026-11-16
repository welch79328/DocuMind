# 謄本影像改由 Qwen3 VL 讀字、正式機不載入 PaddleOCR — 計畫（2026-11-16，業主核可）

要什麼：謄本的照片、掃描件、沒有文字層的 PDF 頁，讀字改由 Bedrock `qwen.qwen3-vl-235b-a22b` 來做。正式機不再載入、也不呼叫 PaddleOCR，程式先留著（Q1 甲）。有文字層的 PDF 不改（Q2 維持）。
怎樣算做到：`acceptance.md` 的 A1–A9 每項都有判定；正式機容器在改後量測期間不載入 PaddleOCR，記憶體照實報出。
做到什麼就收：同一批 24 頁在正式機改前跑 1 次、改後跑 3 次，結果交給業主；`acceptance.md` A1–A9 每項都有判定；`followups.md` 每項都有去處。

**未經審查。本計畫沒有另查業界做法**：§3 的目標形態用第一原理推，量測數字引用 2026-10-23 與 2026-11-09 兩份既有評估。

## 0. 先答三題（廣度）

- **資料**：3 組共 24 頁。G1 是 repo 的遮罩樣本 6 張；G2 是 11/09 那 15 張模擬照片，有掃描、俯拍、斜拍 3 種劣化，各 5 張；G3 是杭州南路電子謄本轉成的掃描圖 3 頁。改前每頁跑 1 次，改後跑 3 次。
- **輸入誰寫**：G1 原本就在 repo。G2 的劣化規格由看不到實作的代理寫好並凍結（`~/jgb-archive/transcript-photo-fullparse-eval-20261109/spec/`）。G3 由我轉圖，只算中間證據。標準答案：G1 用 `expected/`，G2、G3 用同一頁文字層經解析器的輸出。
- **改前改後**：要比。改前是正式機現行版本（OCR）跑同一批 24 頁，見 §6 S2 與待答 Q-C。

## 1. 目標正本定位

無上層目標。查過：`docs/DEPLOYMENT.md` §0.5、§3「Qwen 直讀」；`docs/api/INTEGRATION.md` §3.1、§3.1.4；`docs/testing/bedrock-vlm-eval-20261023.md` §3.1–§3.3；`docs/testing/transcript-photo-fullparse-eval-20261109.md` §1–§4、§9；`.kiro/specs/ocr-vlm-consensus/requirements.md`（舊的共識管線構想，與本計畫不衝突，本計畫不做共識）。

## 2. 規則（業主原話 → 可檢查條件）

| ID | 條件 | 出處 | 讀法、收窄或放寬 | 業主確認於 |
|---|---|---|---|---|
| R1 | 謄本的影像頁（照片、掃描、沒有文字層的 PDF 頁）由 `qwen.qwen3-vl-235b-a22b` 讀字；該頁 `llm_calls` 有一筆 bedrock 讀字呼叫，沒有 PaddleOCR | 「Qwen3 VL 235B 都用」 | 「都用」還包不包含謄本 AI 補欄位、`/classify`，見 Q-A、Q-B | 2026-11-16「核可，全照建議」 |
| R2 | 正式機設定改成不載入、不呼叫 PaddleOCR；程式與套件保留，改回設定就能退回 | 「本地 oCR 拿掉」＋回 Q1「甲：」 | — | 2026-11-16「核可，全照建議」 |
| R3 | 有文字層的 PDF 讀法不變：同一批電子 PDF 改前改後的輸出逐字相同 | 回 Q2「Q2（維持」 | — | 2026-11-16「核可，全照建議」 |
| R4 | 正確率可以比現行低。改後 25 欄 3 次平均低於 91.3% 就停下交業主，先不留在正式機 | 業主看過 97.1–97.4% 對 91.3–91.8% 後仍說「Qwen3 VL 235B 都用」 | 91.3% 這條線是我加的：取業主看過的 Qwen 數字裡最低的一個，比它更低就不在業主看過的範圍內 | 2026-11-16「核可，全照建議」 |
| R5 | 回應格式不變。`transcript_format=v2` 照片的 `position` 改用 Qwen 回的每段座標，不變成全部 `null` | 主持人加 | jgb2 有在讀照片位置（`TranscriptOcrV2Mapper.php` `mapRecords` 的 `$positions`） | 2026-11-16「核可，全照建議」 |
| R6 | Qwen 呼叫失敗時，該頁回空結果並 `needs_review: true`，不退回本機 OCR | 主持人加 | 跟帳單、合約直讀失敗時一樣（`direct_read_processor.py`「直讀失敗,降級為空結果」）；退回 OCR 就又要載入 PaddleOCR | 2026-11-16「核可，全照建議」 |
| R7 | 一份 12 頁的謄本，整份要在 480 秒內回應 | 主持人加 | JGB 等 DocuMind 最多 480 秒（jgb2 `config/transcript.php` `timeout`）；Qwen 帶座標每頁中位 39.2 秒、最長 61.7 秒（11/09 §3 C2），逐頁做會超過，所以同一份的各頁要同時送 | 2026-11-16「核可，全照建議」 |
| R8 | `INTEGRATION.md`、`DEPLOYMENT.md` 照實改寫 | 主持人加 | JGB、AIChatbot 照文件串接 | 2026-11-16「核可，全照建議」 |

## 3. 目標形態（第一原理，未查業界做法）

1. **讀字的地方只換一處，下游不動**：Qwen 回「每段文字＋0–1000 座標」，交出來的格式跟 PaddleOCR 一樣（`{"text","box"}` 的行，加上全文）。這樣 25 欄、清單、全文解析、`transcript_records` 和 v2 位置都沿用現有程式，電子 PDF 和影像也還是同一套解析規則。
2. **為什麼不讓 Qwen 直接回 25 欄**：10/23 §3.3 量過 Qwen 直接回 25 欄是 91.3–91.8%。它的錯多是語意錯，例如把債務人當所有權人、地號和建號對調，這類正好是規則解析器擋得住的。OCR 的錯是字形錯，這類 Qwen 三次都讀對。讓 Qwen 讀字、規則抽欄位，兩邊的長處都留得住。這個組合的 25 欄正確率**還沒量過**，S1 會量。
3. **既有量測（11/09，同一批 G2 的 15 張，本機）**：「全文每一項」Qwen 抄錄＋座標（C2）是 58.2%，現行 OCR 逐行接起（A）是 6.2%；字元正確率 C2 80.9%、A 75.9%；jgb2 表單 8 格的清單路徑 C2 8/26、A 9/26。斜拍那組 C2 的字元正確率只有 59.4%，是最弱的一類。
4. **記憶體**：11/11 正式機實測，容器送謄本照片前 686.3 MiB，送 3 張後 1.826 GiB（`~/jgb-archive/transcript-photo-fullparse-eval-20261109/runs/c14_online_post_photo.txt`），差的就是 PaddleOCR。改成 Qwen 以後，影像讀字不吃容器記憶體。

## 4. 差距（現況）

- 謄本不能直讀：`config.py` `DIRECT_READ_ELIGIBLE_DOCUMENT_TYPES` 只有 receipt、bill、contract。謄本讀字走 `transcript_processor.py` `TranscriptProcessor.extract_text` → `engine_manager.py` `EngineManager.extract_text_multi_engine`，引擎由 `settings.OCR_ENGINES` 決定；正式機設的是 `["paddleocr"]`。
- 照片位置靠 OCR 行框：`transcript_positions.py` `compute_photo_positions` 讀 `ocr_lines`，而且 `transcript_processor.py` 只收 `engine == "paddleocr"` 的 `lines`。
- 啟動預載：`main.py` 在 `OCR_ENGINES` 含 paddleocr 時呼叫 `preload_paddleocr`。
- 「依座標還原縮排」的程式只在評估資料夾裡（`rebuild_only.py`），沒有進 repo。
- 謄本的 AI 補欄位、校正走 OpenAI，`config.py` `LLM_ROUTABLE_DOCUMENT_TYPES` 刻意排除謄本（業主先前裁定「不含謄本」，bedrock-qwen-documind R3）。
- `/classify`（`document_classifier.py` `_extract_text`）和隱藏的 `/api/v1/documents`、`/api/v1/ocr` 用的是 pytesseract。tesseract 每次呼叫才起子程序，不常駐記憶體。

## 5. 我會改的程式（核可後）

- `lib/ocr_enhanced/engine_manager.py`：新增引擎 `qwen`。每頁送一次 Bedrock，prompt 沿用 11/09 C2 那一版；解析成 `{"text","box"}` 行，全文的接法由 S1 決定（J 逐行接起，或 R 依座標還原縮排），信心度固定 0.9。0.9 是 OCR 現在通常回的值，這樣 `needs_review` 的判定方式不變；OCR 行分數本來就不能當信心度（專案記憶 `ocr-line-score-not-confidence`）。
- `config.py`、`config_conflicts.py`：`OCR_ENGINES` 接受 `qwen`。
- `transcript_processor.py`：`qwen` 回的 `lines` 跟 paddleocr 一樣收下，照片位置照舊計算。
- 同一份文件的各頁同時送，上限 4 頁一起（R7）。一頁失敗只影響那一頁（R6）。
- `llm_calls` 記下讀字呼叫，stage 值見 S1：先 grep jgb2、AIChatbot 有沒有列舉 stage，再決定用新值還是沿用既有值。
- 測試：新引擎的解析、失敗降級、位置換算，以及 `transcript_processor` 收 qwen 行。
- 文件：`INTEGRATION.md`（謄本影像讀法、耗時、`llm_calls`）、`DEPLOYMENT.md`（正式機設定、退回方式）。
- 正式機 `.env`：`OCR_ENGINES=["qwen"]`、`OCR_PRELOAD_MODEL=false`，改完重建容器。這一步由業主做，我只寫指令。

## 6. 片與順序

| 片 | 做什麼 | 在哪 | 誰做 |
|---|---|---|---|
| S1 | 寫程式＋局部測試；本機用 Bedrock 跑 24 頁 × 3 次，同一份輸出各用 J、R 兩種接法跑解析器，取 25 欄較高的一種，平手取全文較高的 | 本機 | 我（本機打 Bedrock 要用之前評估用過的 `BEDROCK_KEY_FILE`，路徑由業主提供，我不讀內容） |
| S2 | 改前：正式機現行版本 24 頁 × 1 次，`enable_llm=false`，一次一頁，送前看容器記憶體，超過 1.9 GiB 就停 | 正式機 | 我（要業主授權，見 Q-C） |
| S3 | 上線前跑全套單元測試，失敗 id 跟基線比 → 業主 commit、部署、改 `.env`、重建容器 | 本機／正式機 | 我跑測試；業主部署 |
| S4 | 改後：同 24 頁 × 3 次；記錄記憶體、每頁與每份的耗時、費用；另送 1 份 12 頁的組合件量 R7 | 正式機 | 我（要業主授權） |
| S5 | 改文件、寫收案報告 | 本機 | 我 |

**退回**：正式機 `.env` 改回 `OCR_ENGINES=["paddleocr"]`、`OCR_PRELOAD_MODEL=true`，重建容器。程式不必 revert。

**停點（只看結果）**：S1 的 25 欄低於 91.3% ⇒ 不部署，交業主（R4）。S4 的 25 欄低於 91.3%，或 12 頁超過 480 秒 ⇒ 交業主決定要不要退回。S2、S4 途中容器 OOMKilled，或連續 2 次 5xx ⇒ 停送。

## 7. 終點指標

目標文件＝本線 `acceptance.md`，前面沒有同一目標的片。

| 指標 | 現值 | 本線預期 |
|---|---|---|
| 25 欄正確率（24 頁） | 現值未量，S2 量（10/23 另一批 34 張是 97.1–97.4%，版本不同，不能直接比） | 比現行低，不低於 91.3% |
| 全文每一項讀對率（G2） | 現值未量，S2 量（11/09 本機 A 6.2%，不是線上） | 上升（11/09 本機 C2 58.2%） |
| 讀錯又沒進 `needs_confirmation` 的欄數 | 現值未量 | 只報 |
| 容器記憶體 | 1.923 GiB／2 GiB（2026-11-16，`~/jgb-archive/bill-electric-fields-20261116/runs/before/send-log.txt`） | 送完 24 頁後不超過 0.9 GiB（11/11 實測沒載入 PaddleOCR 時 686.3 MiB） |
| 每頁耗時 | 線上 OCR 18.2–25.4 秒（11/11，3 張） | 變慢；12 頁 ≤ 480 秒 |

## 8. 每次執行回答什麼、要多少成本

| 執行 | 回答的決定 | 哪種結果改變下一步 | 規模與成本（來源：11/09 §3 C2 每頁 $0.0052、39.2 秒） |
|---|---|---|---|
| S1 本機 24 頁 × 3 | 用 J 還是 R；要不要部署 | 25 欄 < 91.3% ⇒ 停 | 72 次呼叫，約 $0.37；4 頁同時送約 12 分鐘 |
| S2 正式機 24 × 1 | 改前現值 | 沒有它就不能說「下降多少」 | 24 次 OCR，不呼叫模型；約 10 分鐘 |
| S4 正式機 24 × 3＋12 頁 1 份 | R1、R4、R5、R7 與記憶體 | 見 §6 停點 | 84 次呼叫，約 $0.44；約 15 分鐘 |
| 單元測試 | 開發時只跑改到的檔＋`test_transcript*`、`test_engine_manager*`；上線前跑一次全套 | 新失敗 ⇒ 修 | 全套約 4 分鐘（今天本機實測） |

## 9. 業主回答（2026-11-16「核可，全照建議」）

裁定：Q-A 維持 OpenAI；Q-B 不動，記 `followups.md` F1；Q-C 選 (a)，業主先重啟容器；S2、S4 送正式機已授權。

**修訂 2（2026-11-16 業主「本地 OCR 不啟用 接收目前品質」）**：S1 第 1 輪 25 欄 J 81.1%、R 79.1%，低於 91.3%。業主接受目前品質：R4 的 91.3% 停點與 §6「S1 的 25 欄低於 91.3% ⇒ 不部署」「S4 的 25 欄低於 91.3% ⇒ 交業主」兩條取消，A4 改為只報；謄本影像不退回 PaddleOCR。以 `acceptance.md`「修訂 2」為準。

**修訂 1（2026-11-16 業主「不用量測前」）**：S2 改前量測取消。業主重啟容器後送 4 頁，容器從 563.3 MiB 升到 1.915 GiB，碰到 1.9 GiB 停送線（`~/jgb-archive/qwen-all-no-local-ocr-20261116/runs/before/send-log.txt`）；業主先選分批重啟，隨後改為「不用量測前」。影響：A4、A5 改後只跟標準答案比，不寫「比改前下降／上升多少」；A6、A8 沒有改前對照；已送的 4 頁（G1 01–04）只當參考。規則 R1–R8 與停點（25 欄 < 91.3%）不變。以下是當時的題目原文。

- **Q-A**：「都用」包不包含謄本的 AI 補欄位？現在 `enable_llm=true` 時補欄位走 OpenAI。10/23 §3.2 量過：terra 錯 3 欄，Qwen 錯 9 欄。你先前也裁定過「不含謄本」。我推薦不改；**這個選項比你說的「都用」窄**。
- **Q-B**：`/classify` 和隱藏舊端點用的 tesseract 要不要也換成 Qwen？tesseract 不常駐記憶體；換了以後每次判類型都要多打一次 Bedrock。我推薦這次不動、記進 followups；**這個選項比「都用」窄**。
- **Q-C**：改前量測要在正式機跑現行版本，會用到 PaddleOCR。容器現在已經 1.923/2 GiB，直接送有 OOM 的風險。(a) 你先重啟容器（`ssh chatbot@54.248.201.66 'docker restart ai-doc-backend'`，11/11 實測重啟後約 0.7 GiB），我再一頁一頁送，超過 1.9 GiB 就停；(b) 不量改前，改後只跟標準答案比，不說「下降多少」。我推薦 (a)。
- **授權**：S2、S4 要送 24 頁到正式機。G2 的 15 張出自 5 份真實謄本、含個資，10/23、11/11 已經送過正式機和 Bedrock。每頁會在正式機複核佇列留一筆；清掉算刪正式資料，我不清。

## 我改動的地方

- 「Qwen3 VL 235B 都用」：只改謄本影像讀字，不改謄本 AI 補欄位和 `/classify`。這兩項沒有自己決定，列成 Q-A、Q-B 問你。
- 「本地 oCR 拿掉」：照 Q1 甲，只在正式機設定關掉，程式和套件保留。
- 我加的規則：R4 的 91.3% 停點、R5 位置保留、R6 失敗不退回 OCR、R7 480 秒、R8 文件。理由都寫在 §2。
- 收窄：位置準不準只在 G3 的 3 頁比框（只有 G3 有原始 PDF 可以算真值框），G2 只畫框給我自己目視；G3 是我轉的圖，只算中間證據。

## 出處

業主原話逐字：`~/jgb-archive/qwen-all-no-local-ocr-20261116/reviews/owner-words-20261116.md`。
