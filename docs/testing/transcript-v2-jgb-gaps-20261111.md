# 謄本帶參數格式補 JGB 回報的 4 項缺口（2026-11-11）

紀錄。規則與凍結清單：`.kiro/specs/transcript-v2-jgb-gaps/acceptance.md`；計畫：同目錄 `plan.md`。對接規格：`docs/api/INTEGRATION.md` 2.10.0 §3.1.4（V2-07、V2-24～V2-26、V2-30～V2-32）。原始輸出在 `~/jgb-archive/transcript-photo-fullparse-eval-20261109/runs/`（下稱 `E/runs/`）。

## 1. 改了什麼
只改帶參數 `transcript_format=v2` 的補值（`backend/app/lib/multi_type_ocr/transcript_records.py::fill_from_rules`、`apply_transcript_format`），不帶參數的回應不變：
- R1 `謄本.段`、`謄本.小段`：整份 1 張時從全文切，鄉鎮市區以全國名稱表 `_TOWNS` 比對；不讀 25 欄 `section`／`subsection`。
- R2 清單補完後 `標示部.層次`、`所有權部` 仍空：用單值補第 1 筆。
- R3 `transcript_records` 是 `[]` 或不存在：依 `building_number`、`land_number` 組 1 張再補。
- R4 `共有部分` 由 `shared_parts` 補進時，車位寫進 `其他登記事項`，格式同電子謄本那一行。

## 2. 本機：照片補值
`E/runs/gaps_c1.txt`（指令 `E/measure_gaps.py`，受測物 `328ea6c`＋工作樹，2026-11-11 12:26）。15 頁模擬照片（D1～D5 各 3 種劣化，`enable_llm=false`），標準答案葉值 816 格。

| | 對 | 錯 | 缺 |
|---|---|---|---|
| `328ea6c`（改前） | 167 | 7 | 642 |
| 改後 | 184 | 8 | 624 |

- 改變的 18 格：R1 段小段對 11、錯 1；R2 層次與所有權人對 6、錯 0。
- 唯一新增的錯：D3p4 `謄本.段` 補「公国段」（答案「公園段」），OCR 本來就讀錯，25 欄 `section`＋`subsection` 是同一字。
- R3 模擬（15 頁 `transcript_records` 全清成 `[]`）：對 145、錯 8、缺 663；8 個錯值都等於不帶參數時舊欄位的同一個值（OCR 錯字 6、遮罩「黃**」讀成「黃」2）。
- R4：15 頁照片量不到——OCR 全文都沒有「停車位」，`shared_parts` 每頁 0 筆（本機用同一批 OCR 文字跑 `TranscriptProcessor`，2026-11-11）。格式由單元測試驗（含真實 `_PARKING_NUMBER` 取出的「2號」不會變「號號」）；含車位的 02 範本在線上量，見 §4。

## 3. 本機：電子 PDF 不受影響
同一檔：電子 5 份帶參數 `value` 還原後與 `transcript_records` 相同 5/5。單元測試 `backend/tests/unit/test_transcript_v2_spec.py` 38 項通過；全套 pytest 只有改前就失敗的 7 項（`test_contract_e2e` 3、`test_transcript_e2e` 3、`test_config_validation::test_valid_engine_names` 1）。

## 4. 線上：部署後 R2 錯 1 格，已回滾到 `328ea6c`
`0ce13c0` 於 12:43 部署（C13 通過），15:34:41 依計畫 §6「C1、C3 門檻不過 ⇒ 回滾」在正式機 `git reset --hard 328ea6c`。本片程式已在本機 revert；2.10.0 規格原文見 `git show 0ce13c0:docs/api/INTEGRATION.md`。

| 項 | 結果 | 證據 |
|---|---|---|
| C13 部署 | HEAD 一致、health 200、記憶體 673MiB | `E/runs/gaps_deploy.txt` |
| C8 電子 5 份 | 不帶參數與部署前相同 5/5；帶參數還原後＝`transcript_records` 5/5 | `E/runs/gaps_online.txt` |
| C11 範本 01～07（false） | 對/錯/缺 部署前 24/6/21 → 部署後 25/6/20；6 個錯都是遮罩姓名讀成單字（25 欄同字）；02 有「含停車位編號2號,權利範圍:1000分之55」 | `E/runs/gaps_samples_pre.txt`、`gaps_samples_post.txt` |
| C10 15 頁照片（false） | R1 段小段補對 13、錯 0；**R2 補對 6、錯 1**：D3p1 `所有權部[0].所有權人` 補成「态察律股股份有限公司」（答案 志嘉建設股份有限公司），與 25 欄 `owner` 同一個 OCR 錯字。C3 要求 R2 錯 0 ⇒ 不過 | `E/runs/gaps_c10_isolate.txt` |
| C9 enable_llm=true | 15 頁 true 162/28/626 對 false 147/19/650；範本只送到 01～03（true 8/2/12 對 false 6/2/14），04 遇 OOM，04～07 未送。LLM 實際執行：18 次全為 `extraction`（`gpt-5.6-terra`），每次都成功 | `E/runs/gaps_llm.txt`、`gaps_llm_samples.txt` |

C10 的量法：線上 OCR 與本機存的 OCR 不同，直接比本機 `328ea6c` 會混進 OCR 差異（`E/runs/gaps_llm.txt` 前段即是）。所以改用線上回應各頁 `ocr_raw`，在本機分別跑 `328ea6c` 與 `0ce13c0`，逐格比較。同一份線上 OCR 下：`328ea6c` 128/18/670 → `0ce13c0` 147/19/650。正對照：本機 `0ce13c0` 的結果與線上回應相同，15/15（`E/isolate_gaps_online.py`）。

true 比 false 多錯 9 格。多出的錯主要在 R2：LLM 抽的 25 欄單值被補進第 1 筆。例：D3p5 `層次` 補成一層～騎樓 5 筆，答案沒有；D5p3 所有權人補成「曾錫雄」、層次補成「九層」。R1 多錯 1 格：D3p1 段補成「中正段」，答案是公園段。

正式機 OOM：13:01 送 true 範本 04 時回 502，worker 被 OOM 殺掉（`OOMKilled=true`、重啟策略 `no`）。送之前記憶體已到 1.868GiB／2GiB。服務停到業主 15:31 手動 `docker restart` 才恢復。回滾後，電子 D4 兩種格式的回應都與部署前相同（`E/runs/gaps_online/rb_*`）。
