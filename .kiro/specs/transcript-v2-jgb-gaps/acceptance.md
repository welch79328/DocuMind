# 謄本 v2 補 JGB 4 項缺口：規則與凍結驗收清單

計畫：`.kiro/specs/transcript-v2-jgb-gaps/plan.md`。本檔先列規則、再列清單，核可後兩者一起凍結。E＝`~/jgb-archive/transcript-photo-fullparse-eval-20261109`。

## 業主原話（逐字）

- 2026-11-11 業主貼上 JGB 需求，整則訊息只有貼文，原文見 `plan.md` §0，下稱「JGB 文」。
- 2026-11-11 AskUserQuestion 答覆（第 1 輪）：
  - 第 1 項段、小段：業主選「先通用修切法再補 (Recommended)」。選項描述：「改用全國鄉鎮市區名稱表切（transcript_records 已經這樣做），修好後才補進 謄本.段、小段」。
  - 第 3 項：業主選「改，組 1 張 (Recommended)」。選項描述：「改掉 11/9 的 R8 裁定；JGB 就能完全不讀舊格式。組出來的那張是讀錯風險最高的情況，會量錯幾格」。
  - enable_llm：業主選「一併量 true (Recommended)」。選項描述：「把 F1 併進這條線；JGB 實際用的就是 true，不量等於沒驗 JGB 會拿到的值」。
  - 第 2、4 項：業主選「可以，寫計畫 (Recommended)」。題目：「照 JGB 的說法做，第 2 項計畫裡先量補了會錯幾格再決定」。
- 2026-11-11 業主：「快速修改部署」。
- 2026-11-11 AskUserQuestion 答覆（部署）：業主選「全部授權你做 (Recommended)」。
  - 選項描述：「驗證員 CONFIRMED 後，我 commit、push，再 ssh 進 chatbot@54.248.201.66 git pull，最後做線上確認」。
  - 題目：「ssh 範圍同上次，只限這次部署與回滾」。
- 2026-11-11 第 1 次先核可：業主選「先核可，READY 就做 (Recommended)」。第 1 輪審查回 REVISE，有實質阻擋，這次先核可已失效（`E/reviews/plan-gaps-20261111.md`）。
- 2026-11-11 AskUserQuestion 答覆（第 2 輪）：
  - 段小段修法：業主選「乙：只在 v2 另外切」。
    - 題目：「段、小段：舊格式 25 欄的 section 遇到平鎮區、前鎮區、新市區會切錯（AIChatbot 正式機讀這份）。要連舊欄位一起修，還是只在 v2 另外切？」
    - 選項描述：「舊欄位不動、繼續切錯，AIChatbot 收到的完全不變。這個選項比你先前說的「先通用修切法再補」窄」。
  - 第 2 次先核可：業主選「再給先核可 (Recommended)」。
    - 題目：「修完後我會再送一次審查（最後一次）。要不要再給一次先核可：這次回 READY，或只剩措辭問題且我已修好，就直接開工、做完直接部署？」
    - 選項描述：「條件和上次相同。又出現實質修改或要你判斷的讀法，我就停下來問你」。
    - 適用的計畫：本線 `plan.md`，以第 2 輪審查的版本為準。

- 2026-11-11 AskUserQuestion 答覆（第 3 輪，收尾審查後）：
  - C11 現值：業主選「接受未量，部署前才量」。題目：「C11 的現值（01～07 範本在正式機現行版能補對幾格）還沒量。要不要現在就送 7 張到正式機量（enable_llm=false，約 3 分鐘，不花模型費；會新增複核項目，ID 全記下來、不刪）？」選項描述：「先開工，部署前再送這 7 張。現值要到那時才知道」。
  - 核可：業主選「核可，開工 (Recommended)」。題目：「計畫第 3 版（`.kiro/specs/transcript-v2-jgb-gaps/plan.md`）收尾審查的 6 項都已改好；依規定不再送審，要你核可才能開工。核可後照之前的授權做到部署，再做線上確認。」選項描述：「改程式、本機驗收、驗證員 CONFIRMED 後 commit、push、部署，再做線上確認（含 enable_llm=true 的 22 次，模型費 ≤ $0.9）」。本規則與清單自此凍結。

## 規則

| ID | 可檢查的條件 | 出處 | 收窄／放寬／擇一 | 業主確認於 |
|---|---|---|---|---|
| R1 | 帶參數、整份只有 1 張、且 `謄本.段`（或 `小段`）為 `null` 時，從該份全文找出「全國鄉鎮市區名稱＋段名（＋小段）＋地號／建號」那一行，用名稱表切出段、小段補進去。找不到行政區名稱就不補，保持 `null`。行政區名稱以「鎮」或「市」結尾的（平鎮區、前鎮區、新市區等）要切對；縣轄市或省轄市後面又接區名的（例：新竹市東區），段名不得含區名。不帶參數的 25 欄 `section`／`subsection` 不改 | JGB 文第 1 項；「先通用修切法再補」；「乙：只在 v2 另外切」 | **收窄**：業主裁定 25 欄不動。**收窄**：JGB 文寫「讀 section、subsection」，改成從全文切，因為 25 欄的值正是會切錯的那份；行首沒有鄉鎮市區名稱時，原本 25 欄有值，現在不補 | 2026-11-11 AskUserQuestion「乙：只在 v2 另外切」 |
| R2 | 帶參數、整份只有 1 張時：(a) 建物張 `標示部.層次` 補完清單後仍是 `[]`，且 `floor_level` 或 `floor_area` 有值 → 補 1 筆 `{層次: floor_level, 面積: floor_area 轉成數字}`。(b) `所有權部` 補完清單後仍是 `[]`，且所有權人或權利範圍有值 → 補 1 筆：`所有權人` 取 `owner`；`權利範圍` 建物張取 `rights_scope`、土地張取 `land_rights_scope`；其餘固定鍵留空 | JGB 文第 2 項；「可以，寫計畫」 | **放寬**：多補 `所有權人`（`owner`）。**收窄**：只補第 1 筆。**代理決定**：業主說「先量補了會錯幾格再決定」，原型量到 6 格對、0 格錯（`E/runs/proto_gaps.txt`），所以照做；收案時以 C3「錯 0」把關 | 2026-11-11 AskUserQuestion「可以，寫計畫」 |
| R3 | 帶參數時 `document_fields.transcript_records` 是 `[]` 或不存在：`building_number` 有值 → 組 1 張建物張；否則 `land_number` 有值 → 組 1 張土地張。組好後照「整份 1 張」的補值規則補（含 R1、R2、R4）。兩個都沒有 → 回 `[]`。組出的那張：`部是否印出` 全為 `false`，`部附註` 各為 `[]`，`注意事項`、`其他欄位` 為 `[]`；`謄本` 與 `_header` 的空白形狀相同（`頁首附註` 為 `[]`，其餘固定鍵除了補進的以外都是 `null`） | JGB 文第 3 項；「改，組 1 張」 | **收窄**：`building_number`、`land_number` 都沒有時不組。取代 11/9 R8 對空紀錄的處理與 F2 | 2026-11-11 AskUserQuestion「改，組 1 張」 |
| R4 | 帶參數、`共有部分` 由 `shared_parts` 補進（全文沒有共有部分）時，每一筆 `shared_parts[].parking` 在補進那筆的 `其他登記事項` 加一個字串 `含停車位編號{number},權利範圍:{rights_scope}`。`number` 照原值放，它本身已經以「號」結尾（例 `2號`，`transcript_field_extractor.py` `_PARKING_NUMBER`）。`number` 是 `null` 就省略「編號{number}」，`rights_scope` 是 `null` 就省略「,權利範圍:…」，兩者都是 `null` 就不加 | JGB 文第 4 項；「可以，寫計畫」 | **擇一**：JGB 舉例寫「含停車位○號」，實作多加「編號」兩字，因為 jgb2 staging 拆車位的正規式要先看到「編號」（`TranscriptOcrV2Mapper.php` `preg_match_all('/編號\s*…`） | 2026-11-11 AskUserQuestion「可以，寫計畫」 |
| R5 | 不帶參數的回應不變；電子 PDF 帶參數的 `value` 還原後仍等於不帶參數的 `transcript_records` | 11/9 R2（沿用）；JGB 文「電子謄本照目前規格應該不缺」；「乙」 | — | 沿用 2026-11-09 核可 R2；2026-11-11「乙」 |
| R6 | 量 `enable_llm=true`：正式機以同一個 commit、同 15 頁照片與 01～07 範本（7 張，含唯一有車位的 02），帶參數分別送 `enable_llm=true` 和 `false` 各一次，報每頁 LLM 有沒有實際執行、補值的對/錯/缺，兩者並列；結果寫進給 JGB 的回覆 | JGB 文「請確認 true 時上面這幾項也成立」；「一併量 true」 | — | 2026-11-11 AskUserQuestion「一併量 true」 |
| R7 | 規格 `docs/api/INTEGRATION.md` 改成實作後的樣子，並備好給 JGB 的回覆（逐項寫做到什麼、怎麼做）；要不要轉給 JGB 由業主決定 | JGB 文「哪一項做不到也請直接說」；11/9 R7 沿用 | — | 沿用 2026-11-09 核可 R7 |
| R8 | 部署正式機：驗證員 CONFIRMED 後 commit、push，ssh 到 `chatbot@54.248.201.66` 執行 `git pull --ff-only`，再做線上確認 | 「快速修改部署」；「全部授權你做」 | ssh 只限本次部署與回滾 | 2026-11-11 AskUserQuestion「全部授權你做」 |

## 驗收清單

| # | 規則 | 觀察點（業主用的那一層） | 證據 |
|---|---|---|---|
| C1 | R1 | 本機正式程式路徑（新腳本 `E/measure_gaps.py`：跑改後正式實作，逐格列出與 `328ea6c` 相比新增或改變的格，另有紀錄清空模式）15 頁照片帶參數：`謄本.段`、`小段` 補對 ≥11 格；新增的錯值只能是 25 欄裡同一個 OCR 錯字（例：D3p4「公国段」） | `E/runs/gaps_c1.txt` |
| C2 | R1 | 單元測試涵蓋：平鎮區平鎮段、前鎮區前鎮段、新市區新市段、有縣市前綴、新竹市東區（段名不含「東區」）、帶小段、沒有行政區名稱（不補）、多張（不補）。不帶參數的 `section`／`subsection` 改前改後相同 | pytest 輸出 |
| C3 | R2 | 15 頁照片：`標示部.層次[0]`、`所有權部[0]` 補進的格錯 0（原型 6 對 0 錯）。單元測試涵蓋：建物張與土地張各取哪個權利範圍、清單有值時不補、多張時不補 | `E/runs/gaps_c1.txt`、pytest |
| C4 | R3 | 單元測試：`[]` 和不存在兩種都組成 1 張，鍵通過帶參數 schema（`docs/api/transcript_records_v2.schema.json`）；兩個編號都沒有時回 `[]`；`謄本.頁首附註` 包裝後為 `{value: [], …}` 形狀、還原後是 `[]`。15 頁照片把 `transcript_records` 清空模擬：補對 ≥145 格，錯的格都等於舊欄位的同一個值（原型 145 對 8 錯） | pytest、`E/runs/gaps_c1.txt` |
| C5 | R3 | 照片帶參數、紀錄為空時，位置組裝不出錯：組出那張的 `position` 形狀符合 11/9 R4，或是 `null` | pytest（輸入用 S3 照片 OCR 行框） |
| C6 | R4 | 單元測試，輸入用 share reader 實際產出的形狀（`number` 例 `"2號"`）：有編號＋持分、只有編號、只有持分、兩者都沒有、全文已有共有部分（不加）五種；輸出不得出現「號號」 | pytest |
| C7 | R5 | 本機：電子 5 份帶參數的 value 還原後，與 `transcript_records` 相同 5/5；被改的函式只在 `analyze.py` 帶參數分支被呼叫；全套 pytest 通過 | `E/runs/gaps_c1.txt`、grep、pytest |
| C8 | R5、R8 | 正式機部署後，電子 D1～D5：不帶參數的回應與 `E/runs/c14_online/post_*.json`（部署前現行版）相同（`file_url`、`stats`、`review_item_id` 除外）；帶參數的 value 還原後，與不帶參數的 `transcript_records` 相同 | `E/runs/gaps_online.txt` |
| C9 | R6 | 正式機同一個 commit、15 頁照片與 01～07 範本，帶參數 `enable_llm=true` 對 `false`：每頁 `llm_used`、補值的對/錯/缺並列 | `E/runs/gaps_llm.txt` |
| C10 | R1～R4 | 正式機部署後 15 頁照片（`enable_llm=false`，即 C9 的 false 那一組）：段小段新增的錯只能是 25 欄同字（25 欄的值：用回應各頁 `rule_postprocessed.text`，在本機以 `TranscriptFieldExtractor` 重抽 `section`／`subsection`）；R2 補進的格錯 0 | `E/runs/gaps_llm.txt` |
| C11 | R1、R2、R4 | 正式機 01～07 範本（7 張圖：01～06 是 `backend/data/transcript_samples/*.jpg`，07 是 `backend/data/建物謄本.jpg`，對應寫在 `backend/scripts/transcript_online_acceptance.py`）帶參數 `enable_llm=false`，部署前、部署後各送一次，對照 `backend/data/transcript_samples/truth.json` 的 段、小段、層次、所有權人、權利範圍、共有部分（建號、面積、權利範圍、車位）：部署後補對的格 ≥ 部署前，新增的錯只能是 25 欄同字（取法同 C10）；02_shilin_build 部署後 `共有部分[0].其他登記事項` 含「含停車位編號2號,權利範圍:1000分之55」 | `E/runs/gaps_samples_pre.txt`、`E/runs/gaps_samples_post.txt` |
| C12 | R7 | INTEGRATION 的版本列與 §3.1.4 改寫（V2-07、V2-24、V2-25、V2-26 與補值表）；grep 舊說法 0 筆，並附正對照；桌面給 JGB 的檔案重新產生 | grep 輸出 |
| C13 | R8 | 線上 HEAD＝本機 `main`＝`origin/main`；health 200；`OOMKilled=false`；`RestartCount` 不變 | `E/runs/gaps_deploy.txt` |

## 廣度

| 項目 | 類型 | 資料組（用／可用） | 不同輸入數 | 重複次數 | 輸入撰寫者 | 改前對照 |
|---|---|---|---|---|---|---|
| C1、C3、C4 本機補對／補錯 | 使用者層 | 5／12：D1～D5 用；01～07 本機沒有全文 OCR 文字，改到 C11 線上量 | 15 頁照片（3 種劣化） | 1 | 照片劣化由 S1 腳本產生，標準答案取文字層，都不是本線實作者撰寫 | 同 15 頁，`328ea6c` 帶參數（`E/runs/gaps_pre.txt`） |
| C10 線上補對／補錯 | 使用者層 | 5／12（同上） | 15 頁 | 1 | 同上 | 本機改前（`gaps_pre.txt`）；這 15 頁沒有線上改前（理由見 plan §6） |
| C11 線上 01～07 | 使用者層 | 7／12：01～07 全用（08＝D5 同檔，已在 C8） | 7 張 | 1 | 公開導讀圖與 repo 素材；正確答案 `truth.json` 人工判讀，非本線撰寫 | 同 7 張，線上部署前 |
| C9 enable_llm=true | 使用者層 | 12／12：D1～D5 與 01～07 全用 | 15 頁＋7 張 | 1 | 同 C1、C11 | 同一批，線上 `enable_llm=false`，同一個 commit |
| C2、C5、C6、C7、C8 | 機制項 | — | — | — | — | — |

上位驗收方式：`docs/testing/transcript-online-acceptance.md`「謄本功能的驗收分兩條線，**兩條都要過**」「本機 unit 綠燈只證明前者。圖片、掃描件的結果一定要送線上看。」本線照做：抽取邏輯由 C2～C7 驗，照片線上由 C9～C11 驗。
