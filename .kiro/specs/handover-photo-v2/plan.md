# 點交照片回傳格式 v2——計畫（F 片：格式＋上版；2026-11-13，第 3 版）

規則與凍結驗收清單：`.kiro/specs/handover-photo-v2/acceptance.md`（A0–A10）。業主原話逐字：`owner-words.md`。準確率（不在本片）：`accuracy-later.md`。證據目錄 `~/jgb-archive/handover-v2-20261113/`（簡寫 `E/`）。

## 0. 目標正本定位

無上層目標。查過：`docs/planning/`（只有謄本 `transcript-status.md`，不涵蓋點交照片）、`docs/api/INTEGRATION.md` §3.5（點交照片現行格式，是規格不是目標正本）、記憶快照 `snapshots/`（沒有點交照片的線）。終點的目標文件＝本片凍結驗收清單 `acceptance.md`。不碰任何已知偏離，不屬過渡修正。

風險觸發：資料／序列化（對外 API 回應新增 v2）＋上線（部署正式機）＋跨元件（jgb2 會改讀這個格式）→ 核可前派 plan-verifier，完成前派 verifier。
審查紀錄：第 1 輪 plan-verifier 2026-11-13 REVISE（10 項）；第 2 輪 REVISE（8 項）；處置見 §8。兩輪 REVISE 後不再自動送審；業主回答三題（R-src-5）後送收尾審查 1 次：2026-11-13 REVISE（5 項，1 項實質、4 項文字），處置見 §8 收尾審查；業主 2026-11-13 選「再審一次再交核可」，送第 4 次審查（業主指示）：2026-11-13 REVISE（1 項實質：`needs_confirmation`／`extraction_confidence` 歸屬未問業主），業主 R-src-6 裁定後新增 R19，處置見 §8 第 4 次審查；業主選再審，送第 5 次審查（業主指示）：2026-11-13 REVISE（1 項，審查員標 `Kind: wording-only`），已修、未再審，處置見 §8 第 5 次審查

**開工一句（做到什麼就收）**：v2 程式與單元測試進 `main` 並上正式機，A0–A10 成立、`INTEGRATION.md` 寫好 v2、給 JGB 的說明放業主桌面、verifier CONFIRMED，就收。準確率另開一片（`accuracy-later.md`）。

## 1. 終點指標

量法＝`acceptance.md` A0–A10 全部（目標文件裡沒有其他門檻；準確率不在目標文件內）。

| 項 | 現值 | 受測物 | 來源 | 本片預期 |
|---|---|---|---|---|
| A0 | 未成立（固定檔不存在） | `df41f2d` | `E/runs/current_a0.txt`（檔首有指令、時間、SHA；正對照同目錄測試檔存在） | 成立 |
| A1 | 部分：既有三個測試檔 66 passed；固定檔比對尚無 | `df41f2d`，backend 工作樹 0 改動 | `E/runs/current_a1.txt`（檔首有指令、時間、SHA） | 成立 |
| A2–A5、A7、A8 | 未成立（功能不存在：`handover_format` 0 處；正對照 `transcript_format` 65 處） | `df41f2d` | `E/runs/current_grep.txt`（檔首有指令、時間、SHA） | 成立 |
| A6 | **現值未量**（刻度未實測；要對 Bedrock 送照片，屬對外送出，核可前不做） | Bedrock `qwen.qwen3-vl-235b-a22b` | 量法＝第 1 步 | 成立 |
| A9 | **現值未量**（線上 HEAD、health、容器狀態；ssh 由代理執行，範圍依 R18） | 線上機 `54.248.201.66` | 量法＝第 6 步部署前唯讀查詢，存 `E/runs/deploy_pre.txt` | 成立 |
| A10 | **現值未量**（線上沒有 v2；部署前鍵形狀要對正式機送請求，核可前不做）。比對工具已驗證：`E/runs/keyshape_real_control.txt` | 線上機 | 量法＝第 6 步 | 成立 |

同一目標前兩片：無（第一片）。**A6、A9、A10 現值在核可前未量，業主已接受（R-src-5）**（A6 在第 1 步、A9 與 A10 在第 6 步部署前一定先量）。

## 2. 目標形態（設計方法第 1～4 步）

1. **目標**：jgb2「用AI自動帶入」能把每個品項裁成局部圖、預填情況簡述、每項有自己的信心值（需求文「背景」1～3）；現行 jgb2 不受影響（需求文一）。
2. **目標形態**：格式由需求方 JGB 指定（需求文二），本片不另找業界格式。第一原理推導、查無業界對應不另引用：(a) 框要對應使用者在 jgb2 看到的照片方向 → 送模型前依 EXIF 轉正（R9）；(b) 座標刻度依模型實際輸出決定（R11）；(c) 新格式不該改變誰要人工複核——複核是現行 jgb2 依賴的行為（`INTEGRATION.md` 要下游以 `needs_review` 判斷），v2 只是多給欄位（R13）。
3. **差距**：`handover_photo_processor.py` 只要品項名稱與整張信心值，品項信心值沒給時以整張補（`_to_vocabulary` `default=confidence`）；沒有框、損傷；影像理解路徑沒有 EXIF 轉正（`processor.py` `_cap_image_pixels` 後直接存 PNG；對照 `direct_read_processor.py` 有 `ImageOps.exif_transpose`）；端點沒有格式參數。
4. **路徑**（每項對到的規則）：
   - P-a 端點參數（R1）：`/analyze`、`/analyze/batch` 各加 Form 參數 `handover_format`，驗證比照 `transcript_format`；傳到 `AnalyzeService.analyze(..., handover_format=None, handover_v2_out=None)` → `_process_ocr`；點交且 v2 時改用 `HandoverPhotoProcessor(fmt="v2")`，其餘照舊 `ProcessorFactory`（點交不在直讀名單，`config.py` `DIRECT_READ_ELIGIBLE_DOCUMENT_TYPES`）。
   - P-b v2 提示詞（R3、R4、R6、R7、R10、R11）：新增 `_build_prompt_v2`，要求每項 `{name, confidence, box_2d, condition}` 與 `damages[{text, box_2d}]`；`condition`、`text` 用繁體中文；不列損傷範例詞；詞彙表同舊版。舊 `_build_prompt` 不動。
   - P-c 兩段輸出（R3–R8、R13）：v2 處理器對模型回覆**先跑舊的 `_to_vocabulary`**，得到舊形狀 `structured_data`（攔截、佇列、few-shot 都用它，行為同舊）；再跑新的 `_to_vocabulary_v2` 得到 v2 形狀，放在頁的私有鍵 `_handover_v2`。`AnalyzeService.analyze` 像 `_ocr_lines` 一樣把它 pop 出來交給呼叫端容器，頁結果與佇列都不留。端點在 `_apply_confidence_gating` **之後**才把 `structured_data` 換成 v2 形狀，`document_fields` 的 `furniture`、`appliance` 同樣換成 v2 品項並加 `damages`（R16），各處看得到的 `field_confidences` 依 R17（業主裁定 X：改用模型自評、沒給的品項省略），`document_fields.needs_confirmation`／`extraction_confidence` 依 R19 用 v2 品項重算（業主 R-src-6）（同謄本 v2 先例 `apply_transcript_format`）。新增 `_normalize_box`（換算 → 4 個有限數值 → 越界、x0≥x1、y0≥y1、面積 < 0.005 → `None`；4 位小數）、`_clip_text(30)`。
   - P-d EXIF 轉正（R9）：v2 處理器覆寫 `process`，在 `_cap_image_pixels` 與轉存 PNG 之前 `ImageOps.exif_transpose`。舊路徑不動。
   - P-e 座標刻度實測（R11）：第 1 步，結果決定 `_normalize_box` 的除數。
   - P-f `max_tokens`（R3、R7：輸出不能因長度被截斷）：第 1 步記錄輸出 token；接近 2048 就只把 v2 呼叫的上限調高，舊路徑的上限不動。
   - P-g 文件：`docs/api/INTEGRATION.md` §3.5 加 v2（含 R13：`needs_review` 與不帶參數相同；R19：`needs_confirmation` 含沒給自評的品項、`extraction_confidence` 只平均有自評的、全沒給就沒有這個鍵）、版本 2.11.0；桌面 `~/Desktop/給JGB_點交v2規格/`。
   - 相關但不在本次範圍（記進 `followups.md`）：舊路徑補 EXIF 轉正；修繕提示詞拿掉損傷範例；正式機有沒有點交 few-shot 校正樣本（§4）。

## 3. 不做（非目標）

- 準確率、框準度、損傷誤標，以及需求文三.3「用同一批照片比」（R-src-4「準確率之後再確認」；移到 `accuracy-later.md`）。本片**不宣稱** v2 辨識得比舊版好或一樣好。
- 不改舊格式路徑的任何行為（含不補 EXIF）。
- 不改 `.env`、不重建容器、不動 jgb2、不把說明送給 JGB。
- 不刪 A10 在正式機產生的 S3 檔、用量紀錄、複核佇列紀錄（刪除是正式機寫入；全部列進收案報告，由業主決定）。

## 4. 已知風險（待查，不擋本片）

- 正式機有沒有點交照片的 few-shot 校正樣本：未查（要讀正式資料庫 `correction_samples`，DocuMind 沒有唯讀 skill）。若有，會照舊注入 v2 提示詞，範例是舊形狀，可能讓模型少給框。A10 線上那次若框全 `null` ⇒ 停、交業主。

## 5. 步驟

1. **座標實測**（本機，真 Bedrock，金鑰經 `BEDROCK_KEY_FILE` 由腳本讀取、不印出）：桌面第 1、2 張＋archive `commons_brisbane_bedroom.jpg`，用 v2 提示詞草稿各送 1 次；`box_2d` 依 ÷1000 與不除兩種畫回原圖目視；記錄輸出 token。存 `E/probe/`。（不改 repo 程式）
2. **A0 固定檔**：在 `df41f2d`、程式未改前產生 `backend/tests/fixtures/handover_v1_baseline.json`（產生腳本放 `backend/tests/fixtures/make_handover_v1_baseline.py`，檔內寫入 SHA、時間、`git status --porcelain -- backend`）。
3. **實作 P-a～P-d、P-f**＋單元測試 `backend/tests/unit/test_handover_photo_v2.py`（A1–A5、A7、A8）。
4. **EXIF 實測**（A7 後半）：桌面第 2 張轉成像素轉 90 度、帶 Orientation=6 的 JPEG，本機 v2 處理器送 1 次，框畫在轉正後的圖上。
5. **全套單元測試**（`LOCAL_STORAGE_PATH`、`DATABASE_URL=...5433...`，`backend/venv`）；**文件** P-g、`followups.md`。
6. **線上部署前**（ssh 唯讀）：`git -C ~/DocuMind rev-parse HEAD`（預期 `df41f2d`）、`git -C ~/DocuMind status --porcelain`（有改動 ⇒ 停）、`docker inspect -f '{{.State.OOMKilled}} {{.RestartCount}}' ai-doc-backend`、`curl /api/health` → `E/runs/deploy_pre.txt`；`commons_brisbane_bedroom.jpg` 不帶參數送 `/api/v1/analyze/batch` 1 次 → `E/runs/online/pre.json`；`python3 -I E/keyshape.py selftest` 先過。
7. **commit、push**：分兩個 commit——C1＝程式＋測試＋固定檔＋`INTEGRATION.md`；C2＝`.kiro/specs/handover-photo-v2/`（計畫、規則、followups）。push `origin main`；線上 `git -C ~/DocuMind pull --ff-only`；等 `--reload` 重載（`docker logs --since 2m ai-doc-backend`）。
8. **A9、A10**：health、inspect → `E/runs/deploy_a9.txt`；同一張照片不帶參數、帶 v2 各 1 次 → `E/runs/online/post_v1.json`、`post_v2.json`；`keyshape.py same` 與 `keyshape.py v2 ... E/v2_expected.json` 判定 → `E/runs/online/keyshape.txt`。
9. **桌面給 JGB 的說明**；**verifier**：fresh verifier 對 `acceptance.md`、本計畫與證據驗證；CONFIRMED 才收案。

### 每次執行（測試選擇）

| 執行 | 回答的決定 | 會改變下一步的結果 | 規模理由 | 成本（跑前估，含出處） |
|---|---|---|---|---|
| 第 1 步座標實測 | `_normalize_box` 除以 1000 還是不除 | 兩種都不落在物件上 ⇒ 停、交業主 | 3 張：兩個資料來源都有、一張有損傷 | 3 次 × 約 4 秒＝約 12 秒（2026-10-28 線上點交 39 次 `elapsed` 中位數 4.11 秒、最大 7.21 秒，`~/jgb-archive/bedrock-qwen-switch-20261028/s2/after{1,2,3}/handover_photo/*.json`）；v2 輸出較長，可能多幾秒。費用約 $0.003（`INTEGRATION.md` §1「約 $0.001/頁」） |
| 第 3、5 步單元測試 | 程式對不對、有沒有弄壞其他類型（便宜、決定性，照跑全套） | 任一失敗 ⇒ 修，不部署 | 全套 | 三個點交相關檔 1.61 秒（`E/runs/current_a1.txt`）；全套約 1～2 分鐘（`~/jgb-archive/transcript-photo-fullparse-eval-20261109/runs/s4_full_unit.txt` 同套件）；0 模型呼叫 |
| 第 4 步 EXIF 實測 | 轉正有沒有生效 | 框落在未轉正位置 ⇒ 修 P-d | 1 張即可判方向 | 1 次 × 約 4 秒（同上出處）；約 $0.001 |
| 第 6、8 步線上 3 次 | A10：舊格式鍵形狀不變、v2 在正式機成立 | 部署後不帶參數鍵形狀不同 ⇒ 立即回滾；v2 缺鍵或框全 `null` ⇒ 不回滾、停、交業主 | 1 張 × 3 次足以判鍵形狀 | 3 次 × 約 4 秒（同上出處）；約 $0.003 |

## 6. 回滾與停點

- **回滾**：線上 `git -C ~/DocuMind checkout <第 6 步記下的 SHA>`（`--reload` 生效）→ health 200；本機 `git revert <C1>` 並 push（**只退 C1**：程式、測試、固定檔、`INTEGRATION.md` v2 段；**保留 C2**：計畫、規則、followups 與紀錄），線上 `git checkout main && git pull --ff-only`。
- **立即回滾**：部署後 2 分鐘 health 不是 200；`OOMKilled=true` 或 `RestartCount` 增加；`keyshape.py same <部署前> <部署後不帶>` 印「不同」（退出碼 1）。
- **停、交業主、不回滾**：v2 缺鍵、框全 `null`（目前沒有呼叫方用 v2）；第 6 步線上 HEAD 不是 `df41f2d` 或工作樹有改動。
- **對外寫入**：push `origin main`（C1、C2）；線上機程式版本；A10 的 3 次請求各可能產生：正式 S3 公開可讀上傳 1 份（`acl="public-read"`，`analyze_service.py` `_upload_to_s3`）、正式資料庫用量紀錄 1 筆（`_record_usage`）、複核佇列 1 筆——上限各 3。照片用 Wikimedia Commons 公開照，不用你桌面的照片。收案報告列出 `file_url`、`review_item_id`。

## 7. 用量回報

收案報告寫子代理 token 合計（plan-verifier 第 1 輪 98,330、第 2 輪 105,650、收尾 91,085、第 4 次 78,876、第 5 次 64,210，計畫階段合計 438,151；之後 verifier 照實加）與 Bedrock 呼叫次數（預估 7 次，約 $0.01）。

## 8. 第 1 輪審查意見處置

| # | 意見 | 處置 |
|---|---|---|
| 1 | 現值只寫總數、沒存檔，A1、A11 量法不符 | FIX：§1 逐項；`E/runs/current_a1.txt`、`current_grep.txt` 存檔；A9（原 A11）寫現值未量＋步驟，請業主核可時接受 |
| 2 | A8–A10 留在目標文件卻不量 | FIX：移出凍結清單到 `accuracy-later.md` |
| 3 | v2 的 `field_confidences` 會改變複核行為與佇列內容 | FIX：新增 R13（與不帶參數相同）、A8 單元測試、P-c 兩段輸出、P-g 文件；列入「我改動的地方」 |
| 4 | A1 的改前基準來源不明 | FIX：新增 A0，在 `df41f2d` 改程式前產生固定檔 |
| 5 | 鍵集合沒定義 | FIX：acceptance 寫明 `keyshape.py` 定義與兩個正對照 |
| 6 | 對外寫入漏 S3 公開上傳與用量紀錄 | FIX：§6、確認版補上；改用公開照片 |
| 7 | revert 範圍沒定義 | FIX：C1／C2 分開 commit，只退 C1 |
| 8 | 「我改動的地方」漏 6 條、需求文三.3 沒引用 | FIX：確認版補齊；三.3 引在 R14 與 §3 |
| 9 | R17 確認欄為「—」 | FIX：改為 R15「待確認」 |
| 10 | 測試選擇缺時間與出處 | FIX：§5 表補件數 × 時間與出處 |

### 第 2 輪（8 項）

| # | 意見 | 處置 |
|---|---|---|
| 1 | 鍵形狀定義會被模型輸出變動誤觸回滾；v2 沒有預期形狀 | FIX：`field_confidences` 當值不展開、空清單萬用；寫好 `E/keyshape.py`（4 個正對照）與 `E/v2_expected.json`；用 10/28 線上同張照片三次真實回應驗證判相同、反對照判不同（`E/runs/keyshape_real_control.txt`） |
| 2 | v2 的 `document_fields` 沒定義 | FIX：新增 R16（跟著換 v2 品項形狀並加 `damages`），A2、A10 檢查 |
| 3 | R13 把看得到的 `field_confidences` 也定成舊值，是沒問的讀窄；漏第三種做法 | FIX：R13 只留複核行為（我選的）；看得到的 `field_confidences` 拆成 R17，改成待確認第 3 題問業主，未答前不當規則 |
| 4 | 「繁體中文」沒被涵蓋 | FIX：R6、R7、P-b 加入；A5 檢查提示詞含「繁體中文」；不驗證模型輸出是否繁中，列「我改動的地方」 |
| 5 | A0 現值沒存檔 | FIX：`E/runs/current_a0.txt` |
| 6 | A6、A10 未量卻沒請業主接受 | FIX：待確認第 2 題擴大為 A6、A9、A10 |
| 7 | A0「早於程式改動」無法觀察 | FIX：固定檔寫入 `git status --porcelain -- backend`，通過條件改判它 |
| 8 | P-f 沒對到規則 | FIX：標 R3、R7，舊路徑上限不動 |

### 收尾審查（5 項；已修、未再審）

| # | 意見 | Kind | 處置 |
|---|---|---|---|
| 1 | A8 比頂層 `field_confidences` 相同，與 R17 衝突必紅；`needs_confirmation`／`extraction_confidence` 沒驗收項；`review_item_id` 每次新 UUID | substantive | FIX：A8 改比複核判定、`review_item_id` 是否為 null、佇列 pages 與 `field_confidences`、`needs_confirmation`／`extraction_confidence`；另加 (b) v2 四處不含沒給的品項；R13 同步 |
| 2 | R16「其他鍵不動」與 R17 衝突 | wording-only | FIX：R16 加「（`field_confidences` 依 R17）」 |
| 3 | §1 A9 殘留「ssh 由誰執行待你回覆」 | wording-only | FIX：改引用 R18 |
| 4 | 確認版第 0 點沒限定帶 v2 | wording-only | FIX：補「帶 `handover_format=v2` 時」 |
| 5 | R4 夾值讀法未列 | wording-only | FIX：R4 讀法欄與「我改動的地方」第 3 條補上 |

### 第 4 次審查（業主指示；1 項）

| # | 意見 | Kind | 處置 |
|---|---|---|---|
| 1 | v2 的 `needs_confirmation`／`extraction_confidence` 仍由整張補值算，和 R17 對不上；歸屬沒問業主 | substantive | FIX：問業主（R-src-6），新增 R19；R13、A8(a) 移除這兩鍵；A2 加 R19 三種輸入；P-c、P-g、確認版第 4 點、我改動的地方第 9 條、已回答同步 |

### 第 5 次審查（業主指示；1 項；已修、未再審）

| # | 意見 | Kind | 處置 |
|---|---|---|---|
| 1 | R16「其他鍵不動」沒排除 R19 改的兩鍵 | wording-only | FIX：R16 括號加「`needs_confirmation`、`extraction_confidence` 依 R19」；全文 grep「鍵不動」只剩此處與 §8 歷史紀錄 |

---

## 確認版（給業主，一頁）

**要做的事**
0. 帶 `handover_format=v2` 時，回應裡各處的品項信心值（含 `field_confidences`）都改用模型對該項的自評，沒給的不補（你選的 X）。
1. `/analyze`、`/analyze/batch` 新增 `handover_format=v2`。帶了才回新格式：每個品項多 `confidence`（模型對這一項的自評，沒給回 null）、`box`（0～1 的框，不合理回 null）、`condition`（損傷，30 字內）；另有 `damages[]`（牆、地板等）。不帶參數完全照舊。
2. 新格式提示詞不列損傷範例詞；手機照片先轉正再送模型。
3. 座標刻度先用 3 張照片實測再定。
4. 誰要人工複核（`needs_review`）新舊格式一樣，不因為新格式改變。帶 v2 時，`needs_confirmation` 列出自評低於 0.8 或沒給自評的品項，`extraction_confidence` 只平均有自評的品項、全都沒給就不放（你選的，R19）。回應裡的 `document_fields` 也跟著換成新的品項形狀並加 `damages`，下游讀哪一邊都一致。
5. 單元測試照 JGB 第四節寫，另先存一份「改前輸出」當基準；改好後上正式機，用 1 張公開照片在線上確認新舊格式。
6. 更新對接文件；給 JGB 的說明放你桌面（我不轉）。

**怎樣算完成**：A0–A10 全部成立（單元測試全綠、實測框落在物件上、正式機版本正確且服務正常、線上舊格式鍵形狀不變、新格式欄位齊全）、獨立驗證員確認。

**這次不做**：準確率（新舊比較、框準不準、損傷會不會亂標），照你說的之後再確認。上線時我不保證新格式辨識得和舊版一樣好。

**出問題怎麼辦**：服務不正常或舊格式變了 ⇒ 立刻退回再回報；只有新格式有問題 ⇒ 不退回（現在沒人用），停下來問你。

**會寫進正式環境的東西**：push 到 GitHub、線上程式版本；線上測 3 次，每次可能留下 1 份公開可讀的 S3 檔、1 筆用量紀錄、1 筆複核紀錄（都不刪，清單給你）。

### 我改動的地方

1. **R1 我加的**：`handover_format` 帶錯值回 400；非點交類型帶 v2 直接忽略（JGB 沒寫，比照謄本 `transcript_format`）。
2. **R2 讀法**：「回傳跟現在逐個欄位完全相同」讀成「同一個模型回覆，輸出逐鍵相同」——模型每次回覆本來就會變。
3. **R4 我選的**：品項信心值不是數字（例如「高」）時視同沒給，回 null；超出 0～1（例如 1.5、85）夾回 0～1，不回 null。你的原話只說「自評的 0～1」，沒說超界怎麼辦；box 越界你寫明回 null，信心值我選夾回，理由是超界多半是模型寫法差異，丟掉會失去資訊。
4. **R5 我加的**：框四捨五入到小數 4 位；不是 4 個數字也回 null。
5. **R6、R7 我選的**：「30 字」以字元數算；不是字串回 `""`。「繁體中文」只寫進提示詞，本片不驗證模型真的寫繁中（那是輸出品質，移到準確率片）——比你給的「繁體中文」窄。
6. **R7 我加的**：`damages` 裡 `text` 是空的整筆丟掉。
7. **R8 我加的**：v2 的 `structured_data` 也保留 `field_confidences`，只放有數值的品項。
8. **R9 我加的**：v2 先依 EXIF 轉正；舊格式不轉，以免改到現行 jgb2 拿到的結果。
9. **R13 我選的**：複核判斷新舊一樣。JGB 只說品項信心值沒給要回 null，沒說複核；若讓 null 影響複核，模糊照片會不再進複核、複核紀錄會變成新格式並被拿去當模型範例，所以我選不變。回應裡看得到的 `field_confidences` 由你裁定 X（R17）、`needs_confirmation`／`extraction_confidence` 由你裁定（R19），都不在本條。
9-1. **R16 我選的**：`document_fields` 跟著換成新品項形狀並加 `damages`（JGB 只寫 `structured_data`；對接文件說兩邊帶同樣的鍵）。
10. **R14 讀法與取代**：「上版」讀成 commit 進 main、push、線上 `git pull --ff-only`（本 repo 的部署做法）。你先前選的「先本機報告」由「先改格式 上版」取代；JGB 三.3「用同一批照片比」移到之後的準確率片。
11. **延後**：你先前選的正確率定義（兩個都看）、18 張照片、框準度檢查，依「準確率之後再確認」移到 `accuracy-later.md`。
12. **我加的交付物**：給 JGB 的說明放你桌面。
13. **A10 我加的**：上線前後在正式機送 1 張公開照片 3 次，會留下上面列的正式環境紀錄。

對照過的業主原話：`owner-words.md` R-src-1～R-src-6（皆 2026-11-13 本 session）。

### 已回答（R-src-5，2026-11-13 本 session）

1. 正式機指令：你授權我用 ssh 執行，只限第 6～8 步與 §6 回滾指令（R18）。
2. A6、A9、A10 現值核可前未量：你接受；核可後第 1 步、第 6 步一定先量，不符就停。
3. 看得到的 `field_confidences`：X，四處全部改用模型自評，沒給的品項省略（R17）。

### 已回答（R-src-6，2026-11-13 本 session，第 4 次審查後）

1. 帶 v2 時 `needs_confirmation`／`extraction_confidence`：依自評，沒給自評的品項列進待確認；平均只算有自評的，全都沒給就不放（R19）。
2. 改好後再審一次再交核可。

### 待確認

無（只剩核可本計畫）。

## 9. 核可後變更（2026-11-13）

- 第 6 步停點觸發：線上 HEAD＝`fd9f6d9`（合約 v2 線已部署），不是預期的 `df41f2d`。業主裁定 R-src-9「等合約線收完再部署」：等合約線部署後檢查與文件 commit 上 main 後，本線接到該 commit；第 6 步預期 SHA 改為該 commit；`INTEGRATION.md` 版號改 2.12.0；其餘照本計畫。本機已先把改動接到 `fd9f6d9`（`analyze.py` Form 參數、錯誤表、第 9 步分支與 `ADDED_REQUEST_PARAMS` 兩邊都保留），全套單元測試 2001 過、2 項只在 worktree 失敗（`test_annotation_storage_policy` 的 `.gitignore` 位置，改前 `df41f2d` 同樣失敗）。
