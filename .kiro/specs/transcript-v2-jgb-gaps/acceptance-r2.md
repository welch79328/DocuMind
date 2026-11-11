# 謄本 v2 補 JGB 4 項缺口：規則與驗收清單修訂 r2（重新上線）

修的是本片（`transcript-v2-jgb-gaps`，計畫 `plan.md` 第 3 版、凍結清單 `acceptance.md`）。凍結檔不改；本檔只列改動處，未列的規則 R1、R3～R7 與清單 C1、C2、C4～C9、C11～C13 照 `acceptance.md`。E＝`~/jgb-archive/transcript-photo-fullparse-eval-20261109`。

第 3 版（第 1、2 版審查皆 REVISE，處置見 `E/reviews/plan-gaps-r2-20261111.md`）。

## 0. 目標正本定位

同 `plan.md`「目標正本定位」，本修訂不變：
- 上位文件 `docs/planning/transcript-status.md` §1 三條原則（「修法一律通用，不打特規」「凡是需人工或未解析的欄位，要說得出原因」「掃描／拍照件排到提升機器規格之後」）；§5 兩列（「25 欄 section／subsection 會切錯」「下游讀三種格式」）。
- 上位驗收方式 `docs/testing/transcript-online-acceptance.md`「兩條都要過」。
- 不碰新的已知偏離；不新增 AI 決定權（程式只補值，不改 LLM 呼叫）。
- 目標文件：本線 `acceptance.md`。
- 風險觸發：上線（正式機再部署）、跨元件驗收（JGB 讀帶參數格式）⇒ 送 fresh plan-verifier。審查紀錄：`E/reviews/plan-gaps-r2-20261111.md`。

## 1. 為什麼修訂

`0ce13c0` 部署後，C10（15 頁照片 `enable_llm=false`）R2 錯 1 格：D3p1 `所有權部[0].所有權人` 補成「态察律股股份有限公司」（答案 志嘉建設股份有限公司）。C3／C10 要求 R2 錯 0，不過，所以 15:34 依計畫 §6 回滾到 `328ea6c`，本機 revert 為 `63be362`（已 push）。

這格的值與 25 欄 `owner` 逐字相同。25 欄的取法照凍結的 C10：用線上回應的 `rule_postprocessed.text`，在本機以 `TranscriptFieldExtractor` 重抽。正對照 D3p3（補對）也與 25 欄逐字相同，見 `E/runs/gaps_r2_same.txt`（檔首有指令、時間、受測物），腳本 `E/check_r2_same.py`。量法與其餘結果見 `docs/testing/transcript-v2-jgb-gaps-20261111.md` §4。

## 2. 業主原話（逐字）

獨立來源：`E/reviews/owner-words-r2-20261111.md`（以程式從 session 紀錄擷取 AskUserQuestion 原文，含題目與選項描述）。

- 2026-11-11 15:38 AskUserQuestion，題目：「謄本 v2 補 4 項缺口已回滾：照片 D3p1 的所有權人補進了舊欄位本來就讀錯的字，違反凍結清單 C3「R2 補進的格錯 0」。下一步要怎麼做？」業主選「放寬 C3 後重新上線」。選項描述：「C3 改成「R2 新增的錯只能是舊欄位同字」（和段小段同一個標準），重新核可後再部署 0ce13c0。這個選項比你先前核可的「錯 0」寬。」
- 同一次：「本機的 revert commit 63be362 要不要 push 到 origin/main？」業主選「push (Recommended)」（已執行）。
- 先核可：2026-11-11 15:42 AskUserQuestion，業主選「先核可，READY 就做 (Recommended)」。選項描述：「審查 READY，或 REVISE 的每一項都被審查員標成純用字問題且我已改好，就直接重新上線；有實質問題就停下來問你。」第 1 版審查 REVISE 含實質問題，**這次先核可已失效**，第 2 版審完要業主重新核可。
- 核可：2026-11-11 16:36 AskUserQuestion，題目：「謄本 v2 重新上線的修訂版（acceptance-r2.md）收尾審查只卡一件事：補送 enable_llm=true 範本 04～07 時，正式機可能在中途 OOM。上午打掛過一次，停了 2.5 小時。要核可哪一種做法？選前三個都等於同意重新部署，也接受 04～07 的 true 值部署後才量。」業主選「核可，送；OOM 就停下交我裁定 (Recommended)」。選項描述：「一次送一張。中途 OOM：立刻停送、附重啟指令給你，沒送完的範本怎麼處理由你決定，我不自行收案。符合凍結的 C9「01～07」。」本規則與清單自此凍結。

## 3. 改動的規則與清單

| ID | 修訂後的可檢查條件 | 來源 | 業主確認於 |
|---|---|---|---|
| R2′（取代 R2「收案時以 C3「錯 0」把關」那一句） | R2 的條件 (a)(b) 不變；收案時以 C3′ 把關 | 「放寬 C3 後重新上線」 | 2026-11-11 16:36 AskUserQuestion「核可，送；OOM 就停下交我裁定」 |
| C3′（取代 C3 的「錯 0」那一句） | 15 頁照片：`標示部.層次[0]`、`所有權部[0]` 補進的格，新增的錯值只能是 25 欄同字：該格的值與同一頁 25 欄對應欄位（`owner`、`rights_scope`／`land_rights_scope`、`floor_level`、`floor_area`）逐字相等。C3 其餘（單元測試涵蓋）不變 | 「放寬 C3 後重新上線」；選項描述「R2 新增的錯只能是舊欄位同字（和段小段同一個標準）」 | 2026-11-11 16:36 AskUserQuestion「核可，送；OOM 就停下交我裁定」 |
| C10′（取代 C10 的「R2 補進的格錯 0」） | 正式機 15 頁照片 `enable_llm=false`：R2 新增的錯只能是 25 欄同字（判法同 C3′；25 欄取法同凍結的 C10：用回應各頁 `rule_postprocessed.text`，在本機以 `TranscriptFieldExtractor` 重抽）。C10 段小段那一句不變 | 同上 | 2026-11-11 16:36 AskUserQuestion「核可，送；OOM 就停下交我裁定」 |
| R8′（R8 的重新部署） | C3′、C10′ 核可後，分兩個 commit：**部署 commit**：`git checkout 0ce13c0 --` 下列 6 個檔，內容與 `0ce13c0` 逐位元組相同，commit、push，ssh `chatbot@54.248.201.66` 執行 `git pull --ff-only`。**文件 commit**：C9 補齊後，依 R7 照線上實測改寫文件（見下），只動 `docs/`、`.kiro/`，不動 `backend/`；verifier CONFIRMED 後 push、在正式機 `git pull --ff-only`。ssh 仍只限本次部署與回滾 | 「重新核可後再部署 0ce13c0」；先前「全部授權你做」 | 2026-11-11 16:36 AskUserQuestion「核可，送；OOM 就停下交我裁定」 |

部署 commit 的 6 個檔：
- 程式與測試：`backend/app/lib/multi_type_ocr/transcript_records.py`、`backend/tests/unit/test_transcript_v2_spec.py`。
- 文件：`docs/api/INTEGRATION.md`、`docs/planning/transcript-status.md`、`.kiro/specs/transcript-records-converge/followups.md`、`.kiro/specs/transcript-records-converge/jgb-note-draft.md`。

文件 commit 會改的地方：
- `docs/api/INTEGRATION.md` §3.1.4：「`enable_llm=true` 時 … 這部分沒有驗」那一句，改寫為 true 對 false 的實測結果。
- `.kiro/specs/transcript-records-converge/jgb-note-draft.md` 第 9 點：同上。
- `docs/testing/transcript-v2-jgb-gaps-20261111.md` §4：補重新部署與 C9 補齊的結果。
- 桌面 `~/Desktop/給JGB_謄本v2規格/` 重新產生。

| C9′（C9 的執行條件，判法不變） | 04～07 的 true 值在部署後才量（業主接受未量到部署後）。送件中 OOM 或 502、或送前記憶體 > 1.7GiB ⇒ 停送、交業主裁定沒送完的範本，裁定前不收案 | 「核可，送；OOM 就停下交我裁定」 | 2026-11-11 16:36 AskUserQuestion |

C9（`enable_llm=true`）的判法不變：錯比 false 多 ⇒ 給 JGB 的回覆照實寫、列進 followups（已列 G4），不是回滾條件。

## 4. 這次排定的執行（只跑回答決定所需）

| 執行 | 回答的決定／會改變下一步的結果 | 規模與理由 | 成本（跑前估計，附來源） |
|---|---|---|---|
| 本機：`git diff 0ce13c0 -- backend/` 為空、`git diff 0ce13c0 --` 其餘 4 個文件檔為空＋`tests/unit/test_transcript_v2_spec.py` | 整個 `backend/` 與 4 個文件檔都與 `0ce13c0` 逐位元組相同且 38 項通過 ⇒ 先前本機 C1～C7、C12 結果與驗證員 CONFIRMED（`E/reviews/close-verify-gaps-20261111.md`）適用於部署 commit；不同或失敗 ⇒ 停 | 便宜決定性檢查。全套 pytest 不重跑：整個 `backend/` 與已驗的 `0ce13c0` 逐位元組相同。現況：`git diff --stat 0ce13c0 63be362 -- backend/` 只有 R8′ 那 2 個檔，取回後預期為空 | 1 次 × 約 6 秒（本回合 15:3x 實跑 24 項 5.4 秒），模型 0 |
| 判 C10′：既有 `E/runs/gaps_c10_isolate.txt`＋`gaps_r2_same.txt` | R2 唯一的錯是否 25 欄同字 ⇒ 是則 C10′ 過；否則停 | 不重送：同一份程式，線上回應已存 | 0（已跑） |
| 部署後 C13 | HEAD 一致、health 200、`OOMKilled=false`、RestartCount 不變 ⇒ 繼續；否則回滾 | — | ssh 1 次＋curl，約 10 秒（`E/runs/gaps_deploy.txt` 上午部署實測），模型 0 |
| 部署後電子 D1～D5 兩種格式（C8） | 回應與 `0ce13c0` 上午線上那批（`E/runs/gaps_online/post_D*`、`post_nov2_D*`）相同（`file_url`、`stats`、`review_item_id` 除外）⇒ 上午的 C8、C10、C11 線上結果適用於這次部署；不同 ⇒ 回滾 | 屬「改動後重跑」的受影響範圍：電子每次都經過改動的函式。照片不重送：程式相同、結果已存，再送只增加 OOM 風險 | 10 次 × 約 0.5 秒（`E/runs/gaps_online/post_log.txt` D1～D5 為 0.4～0.6 秒），模型 0 |
| C9 剩下的 `enable_llm=true` 範本 04～07 | 補齊凍結清單 C9「01～07」；結果寫進給 JGB 的回覆 | 4 次，一次一張；每次送前先看容器記憶體，> 1.7GiB 就不送、停下交業主；每次送後照舊查 `OOMKilled`／RestartCount | 4 次 × 約 13～43 秒（`post_true_log.txt` 範本 01～03 為 41.5、42.6、13.0 秒）；模型 ≤ $0.16（每頁 ≤ $0.04，`plan.md` §6） |
| 文件 commit 後 C12 重 grep | 舊說法「所有實測都是 `enable_llm=false`」「這部分沒有驗」在現行文件 0 筆，且新句子（true 的對/錯/缺）命中 ⇒ 送 verifier；有殘留或正對照沒中 ⇒ 改完再 grep | 便宜決定性檢查 | 約 1 秒，模型 0 |
| fresh verifier：文件 commit 與線上狀態 | 驗：部署 commit 的 `backend/` 全部與 4 個文件檔都與 `0ce13c0` 相同（`git diff 0ce13c0 -- backend/` 為空）、C8 與 C13 的線上證據、C10′ 判法、C9 數字與文件的新句子一致、C12。CONFIRMED ⇒ push 文件 commit、正式機 pull、收案報告；不是 CONFIRMED ⇒ 依 Orchestration 處置，`plan.md` §8 停點適用 | 驗證員判過後文件又改了，與宣稱相關，所以要一次新驗證（Orchestration post-verdict change） | 1 次；約 16 萬 token（上一位驗證員 162,553，task notification） |

上位驗收方式與廣度表照 `acceptance.md`，本修訂不改。

## 5. 終點指標

目標文件＝`acceptance.md`；終點＝C1～C13 全過，C3、C10 依本檔改為 C3′、C10′。本片是本線第 1 片，沒有前兩片可比。

| 量法 | 現值 | 受測物 | 來源 | 本次預期 |
|---|---|---|---|---|
| C1 段小段補對 | 11 對、1 錯（25 欄同字） | 本機 `0ce13c0` | `E/runs/gaps_c1.txt` | 不變（程式相同） |
| C3′ R2 補進的錯 | 0 錯（6 對） | 本機 `0ce13c0` | `E/runs/gaps_c1.txt` | 不變 |
| C4 紀錄清空補對 | 145 對、8 錯 | 本機 `0ce13c0` | `E/runs/gaps_c1.txt` | 不變 |
| C2、C5、C6 單元測試 | 通過 | 本機 `0ce13c0` | `E/reviews/close-verify-gaps-20261111.md` | 部署 commit 重跑 38 項 |
| C7 電子 5 份 | 5/5 | 本機 `0ce13c0` | `E/runs/gaps_c1.txt` | 不變 |
| C8 線上電子 | FAIL 0 | 線上 `0ce13c0`（12:43～15:34） | `E/runs/gaps_online.txt` | 重新部署後重送，預期相同 |
| C9 true 對 false | 15 頁 162/28/626 對 147/19/650；範本 01～03 8/2/12 對 6/2/14；04～07 未量（業主接受部署後才量，C9′） | 線上 `0ce13c0` | `E/runs/gaps_llm.txt`、`gaps_llm_samples.txt` | 補齊 04～07 |
| C10′ 線上 15 頁 | 段小段錯 0；R2 錯 1，與 25 欄逐字相同 ⇒ 過 | 線上 `0ce13c0` | `E/runs/gaps_c10_isolate.txt`、`gaps_r2_same.txt` | 不變（不重送） |
| C11 線上範本 | 25/6/20（部署前 24/6/21）；02 有車位字串 | 線上 `0ce13c0` | `E/runs/gaps_samples_post.txt`、`gaps_samples_pre.txt` | 不變（不重送） |
| C12 文件 | 過（`0ce13c0` 的文字） | 本機 `0ce13c0` | `E/reviews/close-verify-gaps-20261111.md` | 文件 commit 後重 grep |
| C13 部署 | 過 | 線上 `0ce13c0` | `E/runs/gaps_deploy.txt` | 重新部署後重查 |

## 6. 回滾與停點（同 `plan.md` §8，另加一條）

- 回滾：正式機 `git reset --hard 328ea6c`，再確認 health；本機 revert 部署 commit。
- 停點：同 `plan.md` §8；另加：送 C9 前容器記憶體 > 1.7GiB。
- **C9 送件中正式機 OOM 或回 502**：
  - 立刻停送。下一則訊息就交業主，寫明服務中斷、影響（AIChatbot、jgb2 staging 送謄本會失敗），並附恢復指令 `! ssh chatbot@54.248.201.66 'docker restart ai-doc-backend'`。重啟正式服務不在我的授權內（ssh 只限部署與回滾），由業主執行；業主執行後，我查 health、記憶體、HEAD。
  - 不回滾：程式不是原因，C8、C10′、C11 已過；上午 OOM 時 `0ce13c0` 也已在線上。
  - 沒送完的範本怎麼處理，交業主裁定（C9′）；裁定前不做文件 commit、不收案。

## 7. 確認版（給業主，一頁）

**要做的事**：把 4 項補值（段小段、單值補層次與所有權人、空紀錄組 1 張、車位）重新上線。部署的是新 commit，但程式和上午部署的 `0ce13c0` 逐字相同。

**改的標準**：「單值補層次與所有權人」原本要求一格都不能錯，改成「錯的只能是舊欄位本來就讀錯的同一個字」，而且要和對應的那一欄**逐字相同**。這比段小段的判法嚴：段小段是只要出現在 25 欄任何一處就算同字。理由：唯一的錯是 OCR 把公司名讀錯，舊欄位 `owner` 也是同樣的錯字，補值只是照抄。

**完成標準**：
1. 本機程式與 `0ce13c0` 逐字相同，測試通過。
2. 部署後正式機版本一致、health 正常、沒有 OOM。
3. 電子 5 份兩種格式的回應，與上午部署時相同。
4. `enable_llm=true` 補送範本 04～07。每次送前看記憶體，太高就停。
5. 給 JGB 的說明照實寫：true 比 false 多錯 9 格；改完的文件由新的驗證員驗過才收案。

**風險**：上午就是送 true 範本 04 時把正式機打到 OOM，服務停了 2.5 小時。這次送前會先看記憶體，但仍可能再停。若停了，我會立刻告訴你並附重啟指令，要由你執行；沒送完的範本怎麼處理由你決定。

## 8. 我改動的地方

1. 你說「放寬 C3 後重新上線」，選項描述是「R2 新增的錯只能是舊欄位同字」。我把 C10 的 R2 那一句一併放寬，R2 規則裡「以 C3「錯 0」把關」也改指 C3′。理由：C10 是 C3 在線上的同一個判法；只改 C3，這次的錯仍然不過。
2. 你說「和段小段同一個標準」，我寫成「與同一頁 25 欄對應欄位逐字相等」。**這比你先前說的「和段小段同一個標準」窄**：段小段實際的判法是錯值出現在 25 欄某處就算。理由：取最嚴的讀法，避免剛好在別的欄位出現也算過。這次 D3p1 兩種判法都過，不影響這次的結果。
3. 你說「部署 0ce13c0」，我部署的是新 commit：6 個檔用 `git checkout 0ce13c0 --` 取回，內容逐字相同；之後另有一個只改文件的 commit。理由：`origin/main` 已有 revert `63be362`，無法直接部署舊 commit；文件要寫 true 的實測，得等 C9 補齊後才寫得出來。
4. 凍結的 R6／C9 寫「同一個 commit」。範本 04～07 的 true 會在新 commit 上跑，它們的 false 對照與 01～03 的 true 是在 `0ce13c0` 跑的。我讀成「程式逐字相同就算同一個 commit」。理由：部署 commit 前檢查 `git diff 0ce13c0 -- backend/` 為空（§4 第 1 列）；不為空就停，不部署。
5. 我沒重送 15 頁照片和範本 01～07 的 false：程式相同、結果已存，再送只增加 OOM 風險；改用電子 5 份確認部署後的行為與上午相同。
6. 我加了「送 C9 前記憶體 > 1.7GiB 就不送」：你沒說，是為了避免再打到 OOM。
