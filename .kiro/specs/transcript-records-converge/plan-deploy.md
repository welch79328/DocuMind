# 謄本輸出收斂＋欄位位置——部署計畫（D 片，2026-11-11；已執行，執行紀錄見 §8）

本片把已收案的 S1～S4（分支 `transcript-converge`，commit `76fa153`、`761fff3`、`bf0c465`、`a1a73b6`，前面另有文件 commit `49faf53`）部署到 DocuMind 線上機，並做凍結清單裡的 C14 線上確認。規則與驗收清單：本檔 §2、§4（核可後一併凍結在本檔）；S1～S4 的規則與清單照 `acceptance.md`，本片不改。量測檔目錄 `~/jgb-archive/transcript-photo-fullparse-eval-20261109/`（簡寫 `E/`）。

## 0. 目標正本定位

目標正本：`docs/planning/transcript-status.md`。本片只部署已收案的程式與文件，碰到的原則、待辦列與 `plan.md` §0 相同（電子謄本每一項解析且讀對、通用修法、下游讀三種格式）；不碰任何已知偏離（目標正本沒有編號的已知偏離），不屬過渡修正。終點的目標文件：`acceptance.md`（凍結驗收清單，`plan.md` §0 已點名）。

風險觸發：上線（部署到正式機）＋對外寫入（C14 會在正式機複核佇列新增紀錄）→ 送審前派 plan-verifier、完成後派 verifier。
審查紀錄：plan-verifier 2026-11-11 REVISE（7 項，處置見 §8.1）；業主在審查結果回來前要部署指令、親自執行第 2～3 步（§8.2）。

## 1. 終點指標與收案條件

終點量法＝`acceptance.md` C1～C15 的門檻。現值：2026-11-09 收案驗證 CONFIRMED（`E/reviews/close-verify-s1-s4-20261109.md`），C1～C11、C13、C15 全過，受測物 `a1a73b6`（本機）；C14 未做（業主 2026-11-09 選「先不做」）。本片預期變化：本機各列不變；新增 C14 線上判定。前兩片實際變化：S3 新增 C11 照片位置（四種樣本皆過門檻，`docs/testing/transcript-v2-20261109.md` §5）；S4 新增 C13 規格（`E/runs/s4_claims_final.txt` FAIL 0）。不是連續 0，不觸發斷路器。

**收案條件（開工一句）**：線上機 HEAD 等於 push 後的 `origin/main`、服務健康、C14 判定成立（或照 §6 停點回滾並回報）、受影響的現行文件改正、給 JGB 的規格（更新後）放在業主桌面、verifier CONFIRMED，就收。

## 2. 規則（業主原話 → 可檢查條件）

| ID | 可檢查條件 | 業主原話（出處） | 讀法註記 | 業主確認於 |
|---|---|---|---|---|
| D1 | `transcript-converge` 快轉合併進 `main`（不產生合併 commit）並 push `origin main`；線上機 `54.248.201.66` 的 `~/DocuMind` 執行 `git pull --ff-only`，HEAD 等於 push 後的 `origin/main` | 「部署」（2026-11-11 對話） | 「部署」讀成「合併、push、線上機 pull」：這是本 repo 先前每一片的部署做法（`document-fields-fixed-keys/plan.md` 部署列、`amount-string-type/plan.md` 第 4 步）；線上機只有這一台 | 待確認 |
| D2 | 線上機指令由代理用 `ssh -p 22 chatbot@54.248.201.66` 執行，只限 §5 列出的指令（本次部署、C14 所需的狀態查詢、§6 回滾） | AskUserQuestion「授權你用 ssh 執行」（2026-11-11） | 授權只涵蓋本片；`.env` 不讀、不改 | 待確認 |
| D3 | 部署後做 `acceptance.md` C14：電子 PDF 3 份（D1、D2、D3）＋照片 3 張（D5p1 劣化 1、D3p3 劣化 2、D4p1 劣化 3），C5、C6、C10、C11 的判定在線上回應成立 | AskUserQuestion「做 C14」（2026-11-11） | C14 原文的改前對照是「線上改前版本」（`acceptance.md` 廣度表），所以部署前要先對線上送同 6 份不帶參數，比原題目說的多送一輪（見「我改動的地方」1） | 待確認 |
| D4 | `followups.md` 加 F10（D1p2 `標示部.共有部分[0].權利範圍` 回 `1000分之72`，標準答案 `10000分之672`，未列在 C1 的 7 個錯值中），與 11/9 的裁定一起 commit，隨本次 push | AskUserQuestion「加 F10 後一起 commit」（2026-11-11） | 只改 `followups.md`；不改已 commit 的規格與紀錄數字 | 待確認 |
| D5 | 給 JGB 的規格放在業主桌面 `~/Desktop/給JGB_謄本v2規格/`；代理不轉給 JGB | 「給我 給 JGB 的規格」（2026-11-11）；`acceptance.md` R7「轉不轉、何時轉由業主決定」 | C14 後第 9 點會變，桌面版在第 7 步重新產生 | 待確認 |

## 3. 不做（非目標）

- 不刪 C14 在正式機複核佇列新增的紀錄（刪除是正式機寫入，不在 D2 授權內）；ID 列進收案報告，由業主決定。
- 不改 `.env`、不重建容器、不動 AIChatbot 與 jgb2。
- 不查 F10 的成因、不改 C1 的數字（F10 待查，`followups.md`）。
- 不把給 JGB 的說明送出（R7）。

## 4. 驗收清單

| ID | 規則 | 檢查 | 觀察點 | 證據 |
|---|---|---|---|---|
| P1 | D1 | 本機 `main`＝`origin/main`＝線上機 HEAD＝同一個 SHA | `git rev-parse`；ssh `git -C ~/DocuMind rev-parse HEAD` | 指令輸出（`E/runs/deploy_p1.txt`） |
| P2 | D1 | 部署後 `GET http://54.248.201.66:8085/api/health`（`backend/app/main.py` `@app.get("/api/health")`）200；`docker inspect ai-doc-backend` 的 `OOMKilled=false`、`RestartCount` 與部署前相同；`docker stats` 記憶體 < 1.9 GiB | ssh＋curl | 指令輸出（`E/runs/deploy_p2.txt`） |
| P3 | D3（C6） | 6 份不帶參數的線上回應，部署前後相同（`file_url`、`stats`、`review_item_id` 除外，同 `docs/testing/transcript-v2-20261109.md` §3 C6 判法） | 線上 `/api/v1/analyze` | `E/runs/c14_online.txt`＋回應 JSON（`E/runs/c14_online/`） |
| P4 | D3（C5） | 電子 3 份帶參數的 `transcript_records`，`value` 還原後與部署後不帶參數的 `transcript_records` 相同；標示部沒印的份照 §3.1.4 例外報 | 同上 | 同上 |
| P5 | D3（C10） | 電子 3 份帶參數：有位置的值中框內文字與值相同 ≥95%；有值葉子中有位置 ≥95%（判法同 `check_s2_c10.py`，框內文字取本機原 PDF） | 同上＋本機原 PDF | 同上 |
| P6 | D3（C11） | 照片 3 張帶參數：行框包含投影值中心 ≥90%（判法同 `check_s3_c11.py` photo 模式，參考框取本機電子原檔該頁），有位置比例照實報 | 同上 | 同上 |
| P7 | D4 | `followups.md` 有 F10 列，隨本次 push 進 `origin/main` | `git show origin/main:.kiro/specs/transcript-records-converge/followups.md` | 指令輸出 |
| P8 | D5 | 桌面資料夾的 4 個檔與 push 後 repo 內對應文件一致（說明檔只少草稿標頭那一行） | `diff` | 指令輸出 |

**C14 結果寫在哪**：新增紀錄 `docs/testing/transcript-v2-online-20261111.md`（有日期的紀錄）。現行文件中寫「正式機尚未部署」的地方改正文：`jgb-note-draft.md` 第 9 點；`docs/testing/transcript-v2-20261109.md` §7 是紀錄、不改寫，新紀錄在開頭寫明補了 §7 的線上項。2026-11-11 `git grep -E "尚未部署|未部署|線上未驗|正式機尚未|C14" -- docs .kiro/specs/transcript-records-converge/jgb-note-draft.md` 只中這兩處（正對照：同指令中到 `transcript-v2-20261109.md:94` 的 C14 字樣）。

### 廣度

| 項目 | 類型 | 資料組（用／可用） | 不同輸入數 | 重複次數 | 輸入撰寫者 | 改前對照 |
|---|---|---|---|---|---|---|
| P3～P6（C14） | 使用者層 | 5／5（D1～D5） | 6 | 1 | 照片劣化規格由看不到實作的代理寫成、2026-11-09 凍結；電子檔是業主提供的真實謄本 | 線上部署前版本（`ab38a55`，預期；第 2 步實查），同 6 份不帶參數 |

上位驗收方式：`acceptance.md` 廣度表 C14 列（「5／5 份、輸入 6、重複 1、改前對照＝線上改前版本」），本片照做。

## 5. 步驟與指令

1. **本機**：`followups.md` 加 F10；跑全套單元測試（`backend`，`LOCAL_STORAGE_PATH`、`DATABASE_URL` 照 S4）確認仍綠；commit `followups.md`。
2. **線上部署前**（ssh，唯讀）：`git -C ~/DocuMind rev-parse HEAD`、`git -C ~/DocuMind status --porcelain`（有未提交改動 ⇒ 停、交業主）、`docker inspect -f '{{.State.OOMKilled}} {{.RestartCount}}' ai-doc-backend`、`docker stats --no-stream ai-doc-backend`。存 `E/runs/deploy_pre.txt`。
3. **線上改前對照**：對 `http://54.248.201.66:8085/api/v1/analyze` 依序送 6 份、不帶參數、`enable_llm=false`，一次一份；照片每份送完看 `docker stats`，> 1.8 GiB 就等回落再送。回應存 `E/runs/c14_online/pre_<份>.json`。
4. **合併與 push**：`git checkout main && git merge --ff-only transcript-converge && git push origin main`。
5. **線上 pull**（ssh）：`git -C ~/DocuMind pull --ff-only`；等 `--reload` 重載（看 `docker logs --since 2m ai-doc-backend` 出現啟動完成與 PaddleOCR 預載完成）；P1、P2。
6. **C14**：同 6 份各送不帶參數、帶 `transcript_format=v2` 一次（共 12 次，一次一份，同第 3 步看記憶體）；新腳本 `E/check_c14_online.py` 判 P3～P6，輸出 `E/runs/c14_online.txt`（檔首寫指令、時間、線上 SHA）。
7. **文件**：寫 `docs/testing/transcript-v2-online-20261111.md`、改 `jgb-note-draft.md` 第 9 點；commit、push；線上 `git pull --ff-only`（只動文件，不碰 `backend/`，不觸發重載）；重新產生桌面資料夾；P7、P8。
8. **verifier**：fresh verifier 對本檔 §2 規則、§4 清單、上述證據檔驗證；CONFIRMED 才收案。

**每次執行**（測試選擇）：

| 執行 | 回答的決定 | 會改變下一步的結果 | 規模理由 | 成本（跑前估） |
|---|---|---|---|---|
| 第 1 步單元測試 | followups commit 前程式仍綠（便宜、決定性，照跑全套） | 任一失敗 ⇒ 停、不部署 | 全套 | 約 1～2 分鐘（S4 `E/runs/s4_full_unit.txt` 實測）；0 模型呼叫 |
| 第 3 步線上改前 6 份 | P3 的改前基準 | 送不進或 5xx ⇒ 停、不部署 | C14 凍結的 6 份 | 電子 3 份各數秒（無 OCR）＋照片 3 張各 15～24 秒（`production-host` 實測每頁 15–24 秒）≈ 1.5 分鐘；0 模型呼叫（`enable_llm=false`） |
| 第 6 步線上改後 12 次 | P3～P6（C5、C6、C10、C11 在線上成立） | P3 不同 ⇒ 回滾（§6）；P4～P6 低於門檻 ⇒ 不回滾、停、交業主 | 同 6 份 × 帶／不帶 | 約 3 分鐘；0 模型呼叫 |

## 6. 回滾與停點

- **回滾**：線上機 `git -C ~/DocuMind checkout <第 2 步記下的 SHA>`（`--reload` 自動生效），確認 health 200；之後本機 `git revert` 本次合併的 commit 範圍並 push，線上 `git checkout main && git pull --ff-only` 回到分支上。授權範圍含在 D2。
- **立即回滾**：部署後 2 分鐘內 health 不是 200；`OOMKilled=true` 或 `RestartCount` 增加；P3 不帶參數的回應與部署前不同（影響 AIChatbot 正式機）。
- **停、交業主、不回滾**：P4～P6 低於門檻（帶參數是新功能，目前沒有呼叫方，留在線上不影響現有下游）；第 2 步線上工作樹有未提交改動或 HEAD 不是 `ab38a55`。
- **對外寫入**：第 3、6 步每份照片可能在正式機複核佇列新增 1 筆（電子檔與照片都可能；最多 18 筆，`review_item_id` 全部記入收案報告）。

## 7. 用量回報

收案時回報子代理 token 合計（plan-verifier、verifier）與模型 API 花費（預期 0：`enable_llm=false`）。

---

## 確認版（給業主，一頁）

**要做的事**
1. 把 11/9 收案的謄本新格式（S1～S4）合併進 main、push，線上機拉新版（我用 ssh 執行，只跑本計畫列的指令）。
2. 部署前先對線上送 6 份（電子 3、照片 3，不帶參數）留底；部署後同 6 份帶與不帶參數各送一次，確認：不帶參數的回應和部署前一樣、電子檔新格式的值和舊格式一樣、框對得上。
3. `followups.md` 加 F10（D1p2 共有部分權利範圍讀錯但沒算進錯誤數），一起 commit。
4. 把線上結果寫成新紀錄、改掉「正式機尚未部署」的說法，更新桌面上給 JGB 的規格。

**怎樣算完成**：線上機版本＝ main、服務正常、記憶體沒爆、上面第 2 點全部成立、文件改好、獨立驗證員確認。

**出問題怎麼辦**：服務不正常或不帶參數的回應變了 ⇒ 立刻退回部署前版本再回報；只有新格式不合格 ⇒ 不退回（目前沒人用新格式），停下來問你。

**會寫進正式機的東西**：程式版本；複核佇列最多 18 筆測試紀錄（不刪，ID 給你）。

### 我改動的地方

1. **多送一輪部署前對照**：我問你時說「新增約 6 筆」，但凍結清單 C14 的改前對照是「線上改前版本」，要在部署前先送同 6 份，所以總共送 18 次、複核佇列最多 18 筆（電子檔多半不進佇列，實際預估較少）。這比我問題裡說的寬。
2. **「部署」讀成合併＋push＋線上 pull**：你只說「部署」，這是本 repo 每次部署的做法，線上機只有一台。
3. **我加的**：寫線上紀錄、改正「正式機尚未部署」兩處文件、更新桌面規格（文件衛生規定，部署後那兩句會變成錯的）。
4. **不刪複核佇列測試紀錄**：刪除是正式機寫入，不在你這次的授權內。
5. **給 JGB 的規格**：桌面資料夾是 repo 文件的複本，說明檔拿掉了內部草稿標頭那一行；對接規格 §3.1.4 內有 74 個內部追溯標記（〔V2-xx〕等）照原樣保留。

對照過的業主原話：「部署 並給我 給 JGB 的規格」（2026-11-11）；AskUserQuestion 三題答案（2026-11-11）。

## 8. 執行紀錄（2026-11-11）

### 8.1 plan-verifier 意見處置

| # | 意見 | 處置 |
|---|---|---|
| 1 | 照片間記憶體等待條件「> 1.8 GiB 就等回落」做不到 | FIX（實際做法）：每份送完查 `OOMKilled`／`RestartCount`，變動即停（`send.py`）；記憶體照實記錄。實測最高 1.872GiB 後持平，未觸發停點 |
| 2 | C14 廣度不到下限、電子未用 D4、D5 | FIX：電子改用 D1～D5 全部 5 份；照片 3 張不足 5 種輸入，由業主裁定的收案驗證員另送 10 張新照片補（§8.2 第 2 題） |
| 3 | verifier 對線上的範圍沒寫、與寫入授權衝突 | 業主裁定（§8.2 第 2 題）：驗證員對正式機送 10 張新照片，一次一張、看記憶體，佇列新增 ID 全部列出、不刪 |
| 4 | 終點指標沒逐項列、現值版本不符來源 | FIX：見 §8.4 |
| 5 | 漏改目標正本 `transcript-status.md` | FIX：§3 加 `84b890e` 列、檔首日期改 2026-11-11 |
| 6 | P8 沒列 4 個檔 | FIX：見 §8.3 P8 |
| 7 | 回滾 revert 範圍沒定 | FIX：revert 只限 `76fa153`、`761fff3`、`bf0c465`、`a1a73b6`（程式與規格）；`49faf53`、`84b890e`（文件、F10）保留。未觸發回滾 |

### 8.2 業主裁定與實際執行

- 業主 2026-11-11「給我 ! 部署指令」後親自執行第 1 步 commit（`84b890e`，含本檔與 F10）、第 2 步合併 push、第 3 步線上 `git pull --ff-only`。第 1 步的單元測試沒有跑：`84b890e` 只改 `followups.md` 與本檔，程式與 S4 收案時相同（S4 全套 `E/runs/s4_full_unit.txt`）。
- AskUserQuestion（2026-11-11）第 1 題「先留底再部署」：部署前對線上送電子 5 份不帶參數。照片 3 張沒有送，比裁定窄：部署前容器閒置已用 1.921GiB／2GiB（`E/runs/deploy_pre.txt`），照片 OCR 有 OOM 風險；已在對話中當下告知業主。
- 第 2 題「送 10 張新照片」：收案驗證員對正式機送 10 張沒用過的照片。
- 線上部署前版本實為 `dd4a42e`（不是 `ab38a55`；兩者只差 2 個文件檔，程式相同），回滾點改為 `dd4a42e`。
- 照片位置的電子對照框改為把電子原檔該頁單頁 PDF 送線上取得（本機沒有服務在跑；電子不跑 OCR），共 3 次，都沒有新增複核項目（電子續頁主要欄位信心度 0 時會進佇列，見收案驗證）。

### 8.3 驗收結果

| ID | 結果 | 證據 |
|---|---|---|
| P1 | 本機 `main`＝`origin/main`＝線上 HEAD＝`84b890e` | `E/runs/deploy_post.txt` |
| P2 | health 200、`OOMKilled=false`、`RestartCount=0`、部署後 665.7MiB；C14 送件後最高 1.872GiB | `E/runs/deploy_post.txt`、`E/runs/c14_online_post_photo.txt` |
| P3 | 電子 5 份部署前＝部署後（除 `file_url`、`stats`、`review_item_id`）；8 份帶參數其餘不變 | `E/runs/c14_online.txt` |
| P4 | 電子 5 份 C5 PASS | 同上 |
| P5 | 717/729＝98.4%、729/740＝98.5% | 同上 |
| P6 | 44/46＝95.7%、有位置 46/46 | 同上 |
| P7 | `git show origin/main:.kiro/specs/transcript-records-converge/followups.md` 有 F10 | 指令輸出 |
| P8 | 桌面 `1_給JGB的說明.md` ↔ `.kiro/specs/transcript-records-converge/jgb-note-draft.md`（少第 3 行、標題去「草稿」）；`2_對接規格_3.1.4-3.1.5.md` ↔ `docs/api/INTEGRATION.md` 的 `#### 3.1.4 ` 起到 `### 3.2 ` 前；`3_transcript_records_v2.schema.json` ↔ `docs/api/transcript_records_v2.schema.json`；`4_INTEGRATION_完整對接規格_2.9.0.md` ↔ `docs/api/INTEGRATION.md` | `diff` |

廣度（實際）：

| 項目 | 類型 | 資料組（用／可用） | 不同輸入數 | 重複次數 | 輸入撰寫者 | 改前對照 |
|---|---|---|---|---|---|---|
| P3（電子） | 使用者層 | 5／5 | 5 | 1 | 業主提供的真實謄本 | 線上部署前 `dd4a42e`，同 5 份 |
| P4、P5 | 使用者層 | 5／5 | 5 | 1 | 同上 | 本機收案量測（同數字） |
| P6（照片） | 使用者層 | 3／5（D3、D4、D5） | 3＋收案驗證員 10 | 1 | 劣化規格由看不到實作的代理寫成，2026-11-09 凍結；新照片由驗證員產生 | 線上部署前沒有（OOM 風險）；對照本機同版本回應逐位元相同 |

複核佇列新增：`d9fd8e30-3e21-41fd-b689-38b87f94f586`、`cb5bc14f-00e6-479c-b3ab-d49ba4633905`（D3p3 不帶／帶參數），不刪，由業主決定。

### 8.4 終點指標

| 門檻（`acceptance.md`） | 現值與來源 | 受測物 | 本片預期／實際變化 | S3、S4 實際變化 |
|---|---|---|---|---|
| C1～C4 補值 | 167/7/0、101/2/0（`E/reviews/close-verify-s1-s4-20261109.md`） | `bf0c465`＋S4 未提交（來源檔首雜湊；S4 只改文件與測試） | 不變（本片不改程式） | S3、S4 不變（只動位置與文件） |
| C10 電子位置 | 線上 98.4%／98.5%（`E/runs/c14_online.txt`） | 線上 `84b890e` | 新增線上值，與本機相同 | S3 不變、S4 不變 |
| C11 照片位置 | 線上 95.7%（3 張）；本機 93.8%／100%／97.4%（收案驗證） | 線上 `84b890e` | 新增線上值 | S3 新增；S4 不變 |
| C14 線上 | 本次 FAIL 0（`E/runs/c14_online.txt`） | 線上 `84b890e` | 未量 → 已量 | — |

### 8.5 業主裁定（收案驗證後，AskUserQuestion 2026-11-11）

- 照片線上部署前對照：「接受不補，記成不做」。P3 照片部分改為非目標；照片不帶參數不變以本機量測為準。
- 「送 10 張新照片」的「新」：「C14 沒用過就算」。
- 給 JGB 的對接規格：「另出乾淨版」。桌面另存 `2_對接規格_3.1.4-3.1.5_乾淨版.md`，拿掉 88 個追溯標記（先前說 74 個是錯的，實數 88）和說明標記的那一段；repo 原檔與桌面原 `2_` 檔不動。`4_` 整份規格的 §3.1.4 仍帶同樣標記。
