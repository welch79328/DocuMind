# S4 規格與交付——片計畫（2026-11-09 業主核可：「核可 S4」）

本片是 `plan.md` program envelope 的 S4（envelope 與 S1 於 2026-11-09 業主核可；S1＝commit `76fa153`、S2＝commit `761fff3`，S3＝commit `bf0c465`（業主 2026-11-09 選「先 commit」，本機、未 push）；分支 transcript-converge，未 push）。規則與驗收清單照 `acceptance.md`（凍結＋檔尾「核可後更正」AM-1～AM-9），本片不改規則；本檔只寫做法、量法與本片才要定的細節。量測檔目錄 `~/jgb-archive/transcript-photo-fullparse-eval-20261109/`（簡寫 `E/`）。

## 0. 目標正本定位

目標正本：`docs/planning/transcript-status.md`。
- 碰到的原則（§1）：「電子謄本上印的每一項都要解析出來、而且讀對」——本片只把 S1～S3 做出來的樣子寫進規格，不改程式行為；「實際要處理的謄本是電子檔，掃描／拍照排到提升機器規格之後」——本片在規格寫明照片值的限制（補值來源、行框不是值框、`needs_confirmation` 抓不到 OCR 讀錯）；「修法一律通用，不打特規」——不適用（只改文件與 schema）。
- 碰到的待辦列（§5）：「下游讀三種格式」（本片寫棄用公告與移除條件，並把該列狀態改成現況）；「TFS-2 jgb2 改讀」「TFS-3 AIChatbot 改讀」（本片只交規格與 JGB 說明草稿，不改下游；兩列補「可改帶 `transcript_format=v2`」）。
- 已知偏離：目標正本沒有編號的已知偏離；本片不屬過渡修正。
- 終點的目標文件：`acceptance.md`（envelope §5 已點名）。

風險觸發：資料／序列化格式（新增帶參數格式的 JSON Schema 檔，是對外的序列化契約；規格描述的回應形狀若與實作不符，下游照規格寫會壞）＋跨元件驗收（jgb2、AIChatbot 依此規格改帶參數）→ 送審前派 plan-verifier；收案 verifier 在 S1～S4 完成後一次（envelope §1、§4）。
審查紀錄：`E/reviews/plan-review-s4-round1-20261109.md`（第 1 輪 REVISE，6 條全 FIX）；`E/reviews/plan-review-s4-round2-20261109.md`（第 2 輪 REVISE，4 條全 FIX）；`E/reviews/plan-review-s4-closing-20261109.md`（收尾 REVISE，4 條全 FIX；依規定暫停交業主，業主 2026-11-09 選「改完再審一次」（AskUserQuestion）——業主指示的續審，非預設）；`E/reviews/plan-review-s4-round4-20261109.md`（業主指示續審 REVISE，4 條全 FIX；業主 2026-11-09 選「改法：每句都配測試再審」（AskUserQuestion），新增 §2.5 行為清單與 §4 行為清單檢查、C13 逐行盤點）；`E/reviews/plan-review-s4-round5-20261109.md`（業主指示續審 REVISE，5 條全 FIX；依規定暫停交業主，業主 2026-11-09 選「改完再審第 6 輪」（AskUserQuestion）——業主指示的續審，非預設）；`E/reviews/plan-review-s4-round6-20261109.md`（第 6 輪 READY）

## 1. 本片承接的規則與驗收項（照抄 `acceptance.md`，不改）

| 規則 | 可檢查條件（`acceptance.md` §1 原文摘要） | 業主原話（出處同 `acceptance.md`） | 業主確認於 |
|---|---|---|---|
| R6 | 規格公告五種舊格式棄用：不帶參數時回的 25 欄、6 種清單、`transcripts`、`transcript_records`（舊形狀）、`pages[].structured_data` 的 25 欄與清單（只限謄本）；寫明下游改帶參數、移除條件（下游都改帶參數並經業主確認後，另開一片把預設改成新格式並拿掉舊格式）；本線不移除、不改預設 | 「下游改完後棄用移除」＋「本線只公告棄用」；第五題題目對舊格式的定義 | 2026-11-09 業主核可確認版（AskUserQuestion「核可」） |
| R7 | 更新對接規格，並擬一段給 JGB 的說明；轉不轉、何時轉由業主決定（「驗證完」＝本線收案 verifier 通過後才交） | 「等等驗證完回提供給 JGB 規格再讓他們調整」；「只改 DocuMind＋交規格」 | 2026-11-09 業主核可確認版（AskUserQuestion「核可」） |
| R8 | 帶參數時回應不含舊格式（`document_fields` 不含 25 欄、6 種清單、`transcripts`；每頁 `structured_data` 只拿掉舊欄位，其餘鍵全留）；`field_confidences`、`needs_confirmation`、`needs_review` 與不帶參數相同；複核佇列存的內容與不帶參數相同 | 第四題「同一份回應只有一種謄本結構」；第五題選「都不回」、後改「只拿掉舊欄位」 | 2026-11-09 第 6 輪收尾審查後業主重新核可（AskUserQuestion「改成只拿掉舊欄位」） |
| R4、R5、R1、R2、R3 | 規格要描述的行為（位置格式、電子框到值、照片框到行、補值條件、不帶參數不變、不附信心度）；本片不改，只照實寫 | 同 `acceptance.md` | 同 `acceptance.md`；AM-1～AM-9 各列已記業主確認 |

| 驗收 | 條件（`acceptance.md` §2 原文） |
|---|---|
| C13 | `INTEGRATION.md` 升 2.9.0：寫明參數 `transcript_format`、帶參數時 `transcript_records` 的形狀與 `position` 格式、帶參數時不回的舊格式（含每頁 `structured_data` 的 25 欄與清單）、五種舊格式棄用（只限謄本）與移除條件、照片 `needs_confirmation` 抓不到 OCR 讀錯；新增帶參數格式的 schema；附給 JGB 的說明草稿。觀察點：文件 diff＋grep（與新規格相反的舊陳述 0 命中，含同義改寫；正對照命中） |

C13 是機制項（文件），不適用「驗收廣度」下限；本片沒有使用者層項目。

## 2. 目標 → 目標形態 → 差距 → 路徑

**目標**（R6、R7、R8）：下游開發者只看 `INTEGRATION.md` 與 schema 檔，就能正確改成帶 `transcript_format=v2`、知道拿得到什麼、拿不到什麼、位置怎麼用、哪些值要人工確認；舊格式的棄用與移除條件寫清楚；JGB 拿到一段照著改就好的說明。

**目標形態**（envelope §2 已查並經審查逐句核對；本片用到的三點，原文存 `~/jgb-archive/documind-output-converge-20261109/sources/`，渲染後抽字）：
- 棄用要公告停止支援的時間並給遷移指引。Azure：「Document Intelligence REST API v2.1 reaches end of support on September 15, 2027.」「To avoid production disruption, use this migration guide to move to Azure Document Intelligence 2024-11-30 v4.0 before these dates.」（`azure-migration.txt:72-74`）。Google：「Stable versions are discontinued after a new one is released. Google gives you at least six months' notice when this occurs.」（`google-processor-versions.txt:178`）。本線偏離：沒有固定日期，移除條件寫成事件（envelope 偏離 D4，業主選「本線只公告棄用」）。
- 破壞性改動在規格中逐項寫出改了什麼。Azure：「REST API 2023-07-31 release includes a breaking change in the REST API analyze response JSON. The boundingBox property is renamed to polygon in each instance.」（`azure-migration.txt:185-186`）。本片對應：帶參數時不回的鍵、值形狀從「值」變成 `{value, position}`，逐項列出。
- 回應格式附機器可讀的定義：本 repo 2.4.0 起已用 JSON Schema（`docs/api/transcript_records.schema.json`）；業界做法本片未另查（不宣稱業界），沿用 repo 既有做法。

**差距**（2026-11-09 查證）：
1. `INTEGRATION.md` 2.8.1 沒有 `transcript_format`（§2.1 請求表、§2.3 範例、§4 錯誤表都沒有；`grep -c transcript_format docs/api/INTEGRATION.md`＝0，正對照 `grep -c transcript_records`＞0）。實作已有：`backend/app/api/v1/analyze.py` `analyze_document` 的 `transcript_format` 參數，非 `None`／`"v2"` 一律 400 `INVALID_TRANSCRIPT_FORMAT`（在文件類型檢查之前，所以非謄本類型帶錯值也 400）；`document_type` 不是 `transcript` 時帶 `v2` 被忽略；`/analyze/batch` 沒有此參數。
2. 現行文件與新規格相反或會誤導的陳述（`grep -n` 實查；下面先列 `INTEGRATION.md` 5 處，其餘 6 處在本點末段，合計 11 處）：
   - `INTEGRATION.md:386` §3.1.3 標題「**新串接請讀這裡**」（舊形狀 `transcript_records` 要公告棄用）；
   - `:382`、`:465`「照片、掃描謄本請讀 25 個單值欄位與（§3.1.1）清單」；`:720` §7 第 4 點「請以 25 個單值欄位與 §3.1.1 清單為準」（這些都是舊格式；帶參數後照片值已補進 `transcript_records`）；
   - `:485` jgb2 對照表讀法「清單與 `transcript_records` 都有的值，先讀清單」（帶參數時不回清單）；
   - `:3` 版本列 2.8.1 的同一句（版本列是沿革，保留，新增 2.9.0 條目於最前）。
   另 `docs/planning/transcript-status.md` §5「下游讀三種格式」狀態寫「未規劃」（實際本線已做帶參數格式），`:62` TFS-2 列「照片上 `transcript_records` 幾乎讀不到，建議讀法見 INTEGRATION 2.8.1 §3.1.3」（帶參數後照片值已補進 `transcript_records`）；`INTEGRATION.md:404`「該部沒印 → null」只對不帶參數成立（差距 7），改寫為標明不帶參數；`INTEGRATION.md:134` 通則段「謄本 `transcripts`／`transcript_records` 解析失敗時不出現」（帶參數時 `transcripts` 一律不回）；`transcript-status.md:23`「沒印回 `null`／`[]`」（帶參數時標示部沒印回骨架，差距 7）、`:65`「下游讀三種格式」列「未規劃」。合計要改 11 處：`INTEGRATION.md` 7 處（`:134`、`:382`、`:386`、`:404`、`:465`、`:485`、`:720`）、`transcript-status.md` 3 處（`:23`、`:62`、`:65`）、`transcript-online-acceptance.md` 1 處（`:82`）；版本沿革列（`INTEGRATION.md:3`）不改。這份清單由 §4 C13 逐行盤點覆核，不只靠反向詞列舉；`docs/testing/transcript-online-acceptance.md:82`（現行文件，檔首「最後更新」）「掃描件請以 25 個單值欄位與清單為準」與 `INTEGRATION.md:720` 同一句意思。全 `docs/` 與 `README.md` 以 §4 C13 反向詞實查（2026-11-09），另只命中紀錄檔 `docs/testing/transcript-photo-fullparse-eval-20261109.md:152`（有日期的報告，不改）。
3. 帶參數時拿不到、不帶參數拿得到的值＝帶參數移除的鍵（`apply_transcript_format` 的 `KEY_FIELDS` 25 欄＋`_LIST_DETAIL_KEYS` 6 種清單＋`transcripts`，`transcript_records.py` `apply_transcript_format`）減去 `fill_from_rules` 的補值來源（`plan.md` §3 S1 對應表），以鍵來算三類；另有依條件拿不到的第四類。現行文件都沒寫：
   - (a) S1 不補的 4 個單值欄位：`section`／`subsection`（→`謄本.段`／`小段`；已知會切錯，`transcript-status.md` §5）、`print_date`（→`謄本.列印時間`；只到日、records 到分，格式不同）、`seizure_mark`（限制登記判定只依原文，不憑規則標記）。照片全文沒讀到這幾格時，不帶參數 25 欄有值、帶參數 `transcript_records` 為 `null`。
   - (b) 由清單涵蓋、本身不作補值來源的 9 個單值欄位：`floor_level`、`floor_area`、`sub_building_usage`、`sub_building_area`、`shared_build_number`、`shared_area`、`owner`、`rights_scope`、`land_rights_scope`。對應清單有輸出時已經由清單補進；清單沒輸出時（例：`floors` 只在各層面積加總等於總面積時輸出，INTEGRATION §3.1.1）這幾格帶參數同樣拿不到。
   - (c) DocuMind 算出、`transcript_records` 沒有對應鍵的 3 項：`shared_parts[].share_area`（持分面積，可自行以 `共有部分[].面積 × 權利範圍` 推算）、`shared_parts[].parking`／`parking_total`（車位，`transcript_records` 不另拆，INTEGRATION §3.1.3）、`floor_area_checks`。
   - (d) 依條件拿不到（鍵是補值來源，但條件不成立就不補；`transcript_records.py` `fill_from_rules`、`apply_transcript_format`）：
     - 整份 `transcript_records` 超過 1 張時（`one = len(out) == 1` 為假）：9 個標示部單值（`_FILL_B_SINGLE` 6 個：建物門牌、主要用途、主要建材、層數、總面積、建築完成日期；`_FILL_L_SINGLE` 3 個：面積、使用分區、使用地類別）、`謄本.編號`（由 `building_number`／`land_number`，`if one and no is None`）、`建物坐落地號`（由 `land_numbers`）、`他項權利部`（由 `other_right_type`）都不補——單值補值來源共 12 個＝9＋`building_number`／`land_number`＋`other_right_type`；`類型` 為 `null` 的那張整張不補（`類型` 只在整份 1 張時由 `building_number`／`land_number` 推得）。電子 5 份中 4 份是多張（`E/runs/s4_pre_impl.txt` 第 29～33 行），所以多張的照片是常見情形。替代：改用不帶參數讀 25 欄（25 欄不分張）。
     - 清單項目的 `transcript_id` 對不到該張 `謄本.編號`（或沒有 `transcript_id` 且整份多張）就不補；`owners[].part` 與該張類型不符（土地張只取 `land`、建物張只取 `building`）不補；目標陣列（`層次`、`附屬建物`、`共有部分`、`所有權部`）已有任何一筆，整組不補（只補空清單，不逐筆合併）。替代：不帶參數讀清單。
     - 全文解析 0 張（`transcript_records`＝`[]`），或建構失敗、`transcript_records` 鍵不存在（`analyze_service.py` `_attach_transcript_records` 只記 log、省略此鍵）：帶參數照樣拿掉 25 欄、6 種清單與 `transcripts`，回應沒有任何謄本值；不帶參數仍有 25 欄。替代：改用不帶參數。這是實作現況，本片只照實寫進規格；要不要改實作（例：此時保留舊欄位）登記 followups，收線時業主裁（R8 已裁「只拿掉舊欄位」，改它要另開一片並重新核可）。
   不算拿不到：`has_building_evidence`、`share_slots` 不在移除集合，帶參數時仍在每頁 `structured_data`（`analyze_service.py` 合併處註解「各頁 structured_data 仍保留它」）；清單項目的 `transcript_id`、`owners[].part` 由 `transcript_records` 每張謄本本身與所在部表示。
4. 帶參數時 `field_confidences`、`needs_confirmation` 的鍵仍是 25 欄的英文鍵名（R8 要求與不帶參數相同），但 25 欄本身不回；文件要給「25 欄鍵名 → `transcript_records` 路徑」對照，下游才知道 `needs_confirmation: ["owner"]` 指哪一格。
5. `enable_llm=true` 時 25 欄可能含 LLM 補判值（信心度 0.8，§3），S1 補值照用 25 欄（`transcript_records.fill_from_rules`），所以帶參數的照片值可能來自 LLM；本線 S1～S3 驗收都在 `enable_llm=false`（`E/check_s*_*.py` 皆送 `enable_llm=false`），這部分未驗。
8. 帶參數的 `判定` 與 `部是否印出`：補值後以 `_verdicts` 重算 `判定`（`fill_from_rules` 末段 `r["判定"] = _verdicts(r)`），可能和不帶參數不同（照片 15 頁 35→40/45，`acceptance.md` C4 與「我加的」列），依據可能是規則補進的筆（例：只有 1 張時由 `other_right_type` 補進 `他項權利部[0]`，`判定.他項權利` 變「有」）；`部是否印出` 不隨補值改（補進 `所有權部`／`他項權利部` 筆時仍可能是 `false`），所以「`部是否印出` 為 false ⇒ 該部陣列為空」帶參數時不成立。補值對電子 PDF 也照做（`apply_transcript_format` 不分來源呼叫 `fill_from_rules`），電子補進值的 `position` 為 `null`（S2 AM-3 (4)）。
6. 帶參數格式沒有 schema 檔：`docs/api/` 只有舊形狀 `transcript_records.schema.json`；驗收用的帶參數規則在測試碼裡（`backend/tests/unit/test_transcript_format_v2.py` `v2_schema`：只放寬 AM-1 四個鍵為可 `null`，驗的是還原 `value` 後的形狀，不含 `{value, position}` 包裝）。
7. 帶參數時「`標示部` 沒印 → `null`」不成立：不帶參數時 `標示部` 初值 `null`、只有 `部是否印出.標示部` 為真才建（`transcript_records.py` `_build_sheet`）；帶參數時 `fill_from_rules` 遇 `標示部 is None` 一律建固定鍵骨架（清單鍵 `[]`、其餘 `null`，不限張數），只有 `類型` 為 `null` 的張維持 `null`。所以謄本沒印標示部時（例：所有權個人全部節本）帶參數回全空物件；現行 `INTEGRATION.md:404`「該部沒印 → null」與舊 schema 描述「謄本沒印 → null 或 []」只對不帶參數成立。下游判斷有沒有印要看 `部是否印出.標示部`。C5「電子帶參數還原 value 後＝不帶參數」只在本線 5 份（標示部都有印）成立，不是通則。

**路徑**（每項對應的規則寫在 §3 表）：
1. 新 schema 檔 `docs/api/transcript_records_v2.schema.json`：由舊 schema 以固定規則衍生，不手寫——(a) 先套 AM-1（`v2_schema` 同一放寬）；(b) 每個葉子型別 T 換成「`null`，或 `{value: T 去掉 null, position: Position 或 null}`（`additionalProperties: false`、兩鍵 `required`）」；`判定`、`部是否印出` 不換（`transcript_records._UNWRAPPED_KEYS`）；`類型` 例外處理以保持 `items.oneOf` 三支互斥（舊 schema 以 `類型` 的 `const "土地"`／`const "建物"`／`type null` 分支）：土地、建物兩支的 `類型` 必須是包裝後物件、`value` 為該 const、不可為 `null`，null 支的 `類型` 維持只能是 `null`（`_wrap` 不包 `None`）；`標示部` 的 description 不照抄舊的「沒印 → null」，改寫成「`類型` 已知時一律是物件（沒印時是全空骨架），`類型` 為 `null` 時為 `null`；有沒有印看 `部是否印出.標示部`」（差距 7）；(c) `Position`＝`{page: 整數 ≥1, box: 4 個 0～1 數字, unit: const "ratio"}`。空字串 `""` 也會被包（`_wrap` 只略過 `None`），schema 照實作。衍生函式放在新單元測試檔，測試斷言「repo 內 schema 檔＝衍生結果」（舊 schema 改了沒同步就紅）。
2. `INTEGRATION.md` 2.9.0（只改文件、回應不變；新增參數是相容改動，所以升次版號）：
   - 版本列最前加 2.9.0 條目。
   - §2.1 請求表加 `transcript_format` 列；§2.3 加帶參數範例；§2.5 寫批次端點沒有此參數（帶了會被忽略，§4 執行驗）；§4 錯誤表加 `INVALID_TRANSCRIPT_FORMAT`（含「非謄本類型帶錯值也 400」）。
   - 新 §3.1.4「帶參數格式 `transcript_format=v2`」：形狀（`{value, position}`、`null` 葉子照舊、`判定`／`部是否印出` 不包）；`position` 格式與座標系（0～1 比例、左上原點、`page` 1 起算）；電子 PDF 框到值本身、照片／無文字層 PDF 框到值所在那一行（不是值框）；同一個值的字出現在好幾行時挑一行（AM-7～AM-9 的規則用白話寫），可能框到別行；`position` 為 `null` 的情形（電子：對不到值本身、`謄本.頁數`、補進的值、單頁對位不一致；照片：搜不到行、EXIF 方向不是 1、OCR 用到 Tesseract、共識或 `cross_check` 模式、頁文字與行框不一致）；照片值的補值來源與條件（R1 (a)～(d) 白話）；補值不新增錯、只把舊欄位已有的錯帶進來（C1 量法）；`enable_llm=true` 時可能含 LLM 補判值、未驗（差距 5）；不回的舊格式（R8，逐鍵列）；`標示部` 沒印時也回全空骨架、有沒有印看 `部是否印出.標示部`（差距 7）；帶參數拿不到的值（差距 3 的 (a)～(c) 三類與 (d) 依條件拿不到，逐項列並寫原因、程式條件與替代讀法或「改用不帶參數」）；`判定` 依補值後重算、可能與不帶參數不同，`部是否印出` 不隨補值改，補值對電子 PDF 也做（差距 8）；**§3.1.4、§3.1.5 每一句都帶標記（規則見 §2.5「標記規則」）：程式行為句標〔V2-xx〕、量測結論與驗收範圍句標〔實測：…〕、業主裁定的政策與讀法建議句標〔政策：…〕**；`enable_llm` 未帶時預設 `true`，所以「照片補值可能含 LLM 補判、未驗」適用於預設（V2-29）；`field_confidences`／`needs_confirmation`／`needs_review`／`review_item_id` 與不帶參數相同、鍵名仍是 25 欄英文名＋對照表（差距 4）；**照片的 `needs_confirmation` 抓不到 OCR 讀錯**，帶參數也不附信心度（R3），照片值一律當待確認草稿；複核佇列存的是未轉換的 `pages` 與 `field_confidences`（與不帶參數相同）；實測數字只寫結論與報告路徑。
   - 新 §3.1.5「舊格式棄用（只限 `document_type=transcript`）」：五種舊格式逐項列；下游改帶參數；移除條件（AIChatbot 與 jgb2 都改帶參數並經業主確認後，另開一片把預設改成新格式並拿掉舊格式）；沒有固定日期。
   - 改寫差距 2 列的 `INTEGRATION.md` 7 處（`:134` 例外句補「帶 `transcript_format=v2` 時 `transcripts` 一律不回（§3.1.4）」；其餘 `:382`、`:386`、`:404`、`:465`、`:485`、`:720` 如下）：§3.1.3 標題改成「舊形狀，已棄用，新串接請讀 §3.1.4」；§3.1、§3.1.1、§3.1.2 三個標題末尾加「（不帶參數）」——這三節的鍵帶參數時都不回，`:299`「請讀 `land_numbers`」、`:304`「請讀 `owners`」等引導句由標題限定（第 5 輪審查第 4 條）；`:382`、`:465`、`:720` 改成「不帶參數時照片請讀 25 欄與清單；新串接請帶 `transcript_format=v2`（§3.1.4）」；`:404` 註解改成「不帶參數時該部沒印 → null（帶參數見 §3.1.4）」；jgb2 對照表加一欄「帶 v2 讀法」（`transcript_records` 路徑；持分面積改為自行以 `共有部分[].面積 × 權利範圍` 推算），讀法第一點改成只對不帶參數適用。
   - §7 第 4 點補一句帶參數時同樣適用（照片值是草稿）。
   - `docs/testing/transcript-online-acceptance.md:82` 改寫同 `:720`（不帶參數時以 25 欄與清單為準；新串接帶 `transcript_format=v2`，見 `INTEGRATION.md` §3.1.4），檔首「最後更新」改日期。
3. 實測報告 `docs/testing/transcript-v2-20261109.md`（紀錄，有日期）：S1～S3 驗收結果摘要（C1～C11、C15 的數字、受測物版本、指令與輸出檔路徑；C5 寫明樣本範圍「5 份電子謄本、標示部都有印」，不寫成通則），`INTEGRATION.md` 只引用它；收案 verifier 的樣本外結果收案時另加一節（AM-9）。
4. 給 JGB 的說明草稿 `.kiro/specs/transcript-records-converge/jgb-note-draft.md`：一頁白話——怎麼帶參數、拿到什麼、`position` 怎麼畫框、照片框是整行、哪些值拿不到要自算、哪些要人工確認、`標示部` 有沒有印要看 `部是否印出`（差距 7）、`判定` 可能與舊格式不同且 `部是否印出` 不隨補值改（差距 8）、舊格式棄用與時程（無固定日）；附 `INTEGRATION.md` 章節號。**不送出**，收案 verifier 通過後交業主，轉不轉、何時轉由業主決定（R7）。
5. 索引與目標正本：`docs/README.md` 加 schema 與報告兩列；`docs/STRUCTURE.md` 目錄樹 `api/` 加 `transcript_records_v2.schema.json` 一行、`testing/` 有列檔時加報告一行（完成後 grep `transcript_records_v2.schema.json` 在兩檔都命中）；`docs/planning/transcript-status.md` `:23`（標明不帶參數；帶參數見 INTEGRATION §3.1.4）與 §5「下游讀三種格式」、TFS-2、TFS-3 三列改成現況（帶參數格式已做、舊格式已公告棄用、下游可改帶 `v2`；本線不改下游）。
6. 「之後再做」：新建 `.kiro/specs/transcript-records-converge/followups.md`，登記差距 5（`enable_llm=true` 下帶參數補值未驗）、差距 3 (d) 的「`transcript_records` 空或不存在時帶參數沒有任何謄本值」，與 S3 已知未解（登記次序「0001」框到別部、`謄本.編號類型`「建號」框到抬頭），各寫去處待業主收線時裁。

### 2.5 規格行為清單（每句配測試；業主 2026-11-09 選「改法：每句都配測試再審」，AskUserQuestion）

方法：逐一走過帶參數路徑上的程式分支——`analyze.py` `analyze_document` 的 400 檢查與第 8 步、`analyze_batch`、`transcript_records.py` `apply_transcript_format`／`fill_from_rules`／`_wrap`／`_wrap_record`／`_electronic_positions`／`_photo_positions`、`transcript_positions.py` `compute_positions`／`compute_photo_positions`——每個會改變回應的分支對到一列行為；`INTEGRATION.md` §3.1.4、§3.1.5 的每句行為描述標該列 ID。只在內部、不改回應的分支（例：例外記 log）併入對應列，寫成「降級為 null」。「測試」欄：既有測試寫 `檔名::測試名`（本 session 已逐一讀過斷言）；「新增」的放 `backend/tests/unit/test_transcript_v2_spec.py`，測試名以 `test_v2_xx_` 開頭，只測現有行為、不改程式。

| ID | 規格要寫的行為 | 程式依據（符號） | 測試 |
|---|---|---|---|
| V2-01 | `transcript_format` 不是 `v2` 就回 400 `INVALID_TRANSCRIPT_FORMAT`，檢查在文件類型之前，所以非謄本類型帶錯值也是 400 | `analyze_document` `transcript_format not in (None, "v2")` | 既有 `test_transcript_format_v2.py::TestApi::test_invalid_value_400`（謄本）；新增 `test_v2_01_invalid_value_400_for_contract`、`test_v2_01_empty_value_400`（空字串也算錯值；`E/runs/s4_pre_check_s2_http.txt` HTTP 實測 400） |
| V2-02 | `document_type` 不是 `transcript` 時帶 `v2` 被忽略，回應與不帶參數相同 | `transcript_format == "v2" and resolved_document_type == "transcript"` | 新增 `test_v2_02_non_transcript_whole_response_equal`：同一份假 service 結果，`contract` 帶與不帶 `v2` 各送一次，整份回應相等（易變鍵在測試內明列並逐一說明；既有 `test_ignored_for_non_transcript` 只斷言 `building_number`，不足以支持本列） |
| V2-03 | `/analyze/batch` 沒有此參數，帶了被忽略 | `analyze_batch` 簽名沒有 `transcript_format` | 新增 `test_v2_03_batch_ignores_param` |
| V2-04 | 複核佇列存的是未轉換的 `pages`（每頁 `structured_data` 仍有 25 欄與清單）與 `field_confidences`，與不帶參數相同（佇列只存這兩鍵，不存整份回應；執行時查明，2026-11-09）；`needs_review`、`review_item_id` 與不帶參數相同 | 第 7 步 `_apply_confidence_gating` 在第 8 步轉換之前 | 既有 `test_transcript_format_v2.py::TestReviewQueueUntransformed::test_queue_keeps_old_structured_data`（只證佇列含舊鍵）；新增 `test_v2_04_review_queue_same_as_without_param`：同一份結果帶與不帶各送一次，斷言 `needs_review` 相等、兩次 `review_item_id` 都非 `null`、兩筆佇列 `original_result` 去掉測試內明列的易變鍵後相等 |
| V2-05 | `document_fields` 拿掉 25 欄、6 種清單與 `transcripts`；`field_confidences`、`needs_confirmation` 等其他鍵不變（鍵名仍是 25 欄英文名，附對照表） | `apply_transcript_format` 對 `old_keys \| {"transcripts"}` pop | 既有 `test_transcript_format_v2.py::TestApply::test_document_fields_keys`、`test_transcript_format_v2.py::TestApply::test_removed_key_sets` |
| V2-06 | 每頁 `structured_data` 只拿掉這 31 個舊鍵，其他鍵（含 `has_building_evidence`、`share_slots`）保留 | 同上，`pages` 迴圈 | 既有 `test_transcript_format_v2.py::TestApply::test_structured_data_remove_list_only`；新增 `test_v2_06_building_evidence_and_share_slots_kept` |
| V2-07 | `transcript_records` 為 `[]` 或不存在時，帶參數回應沒有任何謄本值，舊欄位照樣拿掉 | `isinstance(records, list)` 不成立仍 pop；`_attach_transcript_records` 失敗時省略鍵 | 新增 `test_v2_07_absent_or_empty_records_still_drop_old_keys` |
| V2-08 | 每個非 `null` 葉子（含 `""`、數字、布林）包成 `{value, position}`；`null` 葉子照舊；`判定`、`部是否印出` 不包；`類型` 會包 | `_wrap`、`_wrap_record`、`_UNWRAPPED_KEYS` | 既有 `test_transcript_format_v2.py::TestApply::test_wrap_shape`；新增 `test_v2_08_empty_string_wrapped` |
| V2-09 | 補值只補 `null` 與空清單，不覆蓋既有值 | `fill_from_rules` `m.get(k) is None`、`if not m[...]` | 既有 `test_transcript_format_v2.py::TestFill::test_no_overwrite` |
| V2-10 | 整份只有 1 張時，才補 9 個標示部單值、`謄本.編號`、`建物坐落地號`、`他項權利部` | `one = len(out) == 1` | 既有 `test_transcript_format_v2.py::TestFill::test_single_sheet_fills_building_values`、`test_transcript_format_v2.py::TestFill::test_multi_sheet_no_single_value_fill`、`test_transcript_format_v2.py::TestFill::test_other_right_filled_only_when_one_sheet`；新增 `test_v2_10_multi_sheet_no_number_or_land_numbers` |
| V2-11 | `類型` 為 `null` 的張整張不補；只有整份 1 張時，才由 `building_number`／`land_number` 推出 `類型` | `if kind is None: continue` | 新增 `test_v2_11_null_type_sheet_untouched` |
| V2-12 | 清單項目要屬於該張：`transcript_id` 等於該張 `謄本.編號`，或沒有 `transcript_id` 且整份 1 張；`owners[].part` 要與類型相符；目標陣列已有任何一筆，整組不補 | `mine`、`x.get("part") == ...`、`if not m["層次"]` 等 | 既有 `test_transcript_format_v2.py::TestFill::test_list_ownership_by_transcript_id`、`test_transcript_format_v2.py::TestFill::test_list_item_without_tid_belongs_when_one_sheet`、`test_transcript_format_v2.py::TestFill::test_owner_part_must_match_type`；新增 `test_v2_12_nonempty_list_not_merged` |
| V2-13 | 日期鍵要含年、月、日三段數字才補 | `_DATE_OK` | 既有 `test_transcript_format_v2.py::TestFill::test_date_check` |
| V2-14 | `標示部` 為 `null` 且 `類型` 已知時，建全空骨架（不限張數）；有沒有印要看 `部是否印出.標示部` | `if r.get("標示部") is None: r["標示部"] = _skel(...)` | 新增 `test_v2_14_unprinted_mark_part_becomes_skeleton_multi_sheet` |
| V2-15 | `判定` 依補值後的內容重算，可能和不帶參數不同；`部是否印出` 不隨補值改 | `r["判定"] = _verdicts(r)`；`部是否印出` 沒有寫入 | 既有 `test_transcript_format_v2.py::TestFill::test_land_values_and_verdict_recomputed`；新增 `test_v2_15_filled_other_right_sets_verdict_but_not_printed_flag` |
| V2-16 | 補值對電子 PDF 也做；補進值的 `position` 為 `null` | `apply_transcript_format` 不分來源；`_wrap` 值對不上 → `None` | 既有 `test_transcript_positions.py::TestRules::test_filled_value_has_null_position` |
| V2-17 | 電子 PDF（每頁都有文字層）的 `position` 框到值本身；`page` 從 1 起算，`box` 是 0～1 比例、原點在左上，`unit` 恆為 `"ratio"` | `_electronic_positions`、`compute_positions` | 既有 `test_transcript_positions.py::TestRules::test_substring_value_is_framed_exactly`、`test_transcript_positions.py::TestRules::test_number_frames_the_number_token_only`、`test_transcript_positions.py::TestRules::test_every_non_null_position_has_the_r4_shape` |
| V2-18 | 電子 `position` 為 `null` 的情形：對不到值本身、`謄本.頁數`、補進值、單頁對位不一致（該頁全為 null）、重建紀錄與回應不同或組裝失敗（整份為 null） | `compute_positions` `rebuilt != records`、`_frame`、`except` | 既有 `test_transcript_positions.py::TestRules::test_page_count_is_null`、`test_transcript_positions.py::TestNull::test_page_that_does_not_align_is_all_null`、`test_transcript_positions.py::TestNull::test_rebuilt_records_differ_means_all_null`、`test_transcript_positions.py::TestNull::test_failure_inside_assembly_degrades_to_null` |
| V2-19 | 照片和無文字層 PDF 的 `position` 框到值所在的那一行（不是值本身的框），補進的值也照樣找行；`box` 夾在 0～1 | `compute_photo_positions`、`_clamp_box` | 既有 `test_transcript_positions_photo.py::test_unique_line`、`test_transcript_positions_photo.py::test_number_matches_by_number_token`；新增 `test_v2_19_box_clamped`；執行中補 `test_v2_19_filled_value_framed_on_photo`（寫規格時發現「照片補進的值也有框」沒有經 `apply_transcript_format` 的測試，2026-11-09） |
| V2-20 | 同一個值出現在多行時挑一行，可能挑錯。挑法：取鍵名在值之前、對上最多的行；清單裡第 k 次出現的同一個值，取第 k 個符合的行；同一項的其他欄位值也出現的行優先；只在該張謄本的頁裡找 | `_pick_line`、`_sheet_page_sets`、`_head_pages` | 既有 `test_transcript_positions_photo.py` 的 `test_multi_line_*`（3 個）、`test_same_value_*`（2 個）、`test_transcript_positions_photo.py::test_list_item_prefers_line_with_its_other_field_values`、`test_other_field_values_*`（2 個）、`test_multi_page_*`（2 個）、`test_transcript_positions_photo.py::test_empty_sheet_page_set_falls_back_to_all_pages`、`test_transcript_positions_photo.py::test_position_page_is_hit_page_for_multi_page_pdf` |
| V2-21 | 照片 `position` 為 `null` 的情形：搜不到行、值是布林或正規化後為空、EXIF 方向不是 1、該頁有文字層、頁文字與行框不一致、沒有行框（OCR 用到 Tesseract、共識或 `cross_check` 模式）、組裝失敗 | `compute_photo_positions` 各個 `continue`／`return None`；`engine_manager` 的行框來源 | 既有 `test_transcript_positions_photo.py::test_zero_lines_gives_no_entry`、`test_transcript_positions_photo.py::test_exif_rotation_gives_none_but_orientation_1_and_missing_ok`、`test_transcript_positions_photo.py::test_text_layer_page_not_used`、`test_transcript_positions_photo.py::test_inconsistent_page_text_gives_none`、`test_transcript_positions_photo.py::test_no_lines_when_engine_gives_none`、`test_transcript_positions_photo.py::test_no_lines_when_fused_text_is_not_paddle_text`、`test_transcript_positions_photo.py::test_apply_format_wraps_photo_position_and_keeps_none_without_lines`；新增 `test_v2_21_bool_value_has_null_position`；新增 `test_v2_21_consensus_mode_has_no_lines`：`_consensus_enabled` 為 True（`OCR_CONSENSUS_ENABLED` 或 `OCR_FUSION_METHOD=cross_check`，`processor._consensus_enabled` 兩者走同一條）時頁結果沒有 `_ocr_lines`，經 `apply_transcript_format` 後所有 `position` 為 `null`（既有兩個行框測試都把共識關掉，不足以支持本子句） |
| V2-22 | 只有部分頁有文字層的 PDF：不走電子定位；照片行框只從無文字層的頁找，有文字層的頁不當候選——值只印在有文字層頁時 `position` 為 `null`；同樣文字也出現在無文字層頁時，會框到無文字層頁那一行（不一定是值的出處，第 5 輪審查待查 1，`compute_photo_positions` 候選 `pool` 對所有張的值都只取 `usable` 頁） | `_electronic_positions` 要求每頁 `text_layer is True`；`compute_photo_positions` 略過有文字層的頁 | 新增 `test_v2_22_mixed_text_layer_pdf`（兩種情形各一個斷言） |
| V2-23 | 帶參數格式 schema 三支互斥，`類型` 為 `null` 的張只符合 null 支 | 路徑 1 衍生規則 | 新增 `test_transcript_v2_schema.py::test_null_type_sheet_validates_once`，另加 §4 的實際回應檢查 |
| V2-24 | S1 沒補的 4 欄（`section`、`subsection`、`print_date`、`seizure_mark`）帶參數拿不到：`fill_from_rules` 不讀這 4 鍵 | `_FILL_B_SINGLE`、`_FILL_L_SINGLE` 與 `fill_from_rules` 本文都沒有這 4 鍵 | 新增 `test_v2_24_s1_unfilled_keys_change_nothing`：`fill_from_rules(records, 只含這 4 鍵)` 等於 `fill_from_rules(records, {})` |
| V2-25 | 由清單涵蓋的 9 個單值（差距 3 (b)）不作補值來源；清單沒輸出時帶參數同樣拿不到 | 同上，9 鍵不在補值表 | 新增 `test_v2_25_list_covered_singles_change_nothing`：只給 9 個單值、清單皆空，結果等於 `fill_from_rules(records, {})` |
| V2-26 | DocuMind 算出的 `shared_parts[].share_area`、車位 `parking`／`parking_total`、`floor_area_checks` 在帶參數回應裡沒有任何對應鍵 | `apply_transcript_format` pop `_LIST_DETAIL_KEYS`；`transcript_records` 無對應鍵 | 新增 `test_v2_26_computed_items_absent`：輸入含這幾項，走遍帶參數回應所有鍵，這些鍵名 0 次 |
| V2-27 | 帶參數也不附信心度（R3）：每個包裝葉子只有 `value`、`position` 兩鍵，`transcript_records` 內沒有信心度或來源類鍵 | `_wrap` 只產兩鍵 | 新增 `test_v2_27_wrapped_leaf_has_only_value_and_position`（另有 `E/runs/s4_pre_check_s2_http.txt` C9 HTTP 實測） |
| V2-28 | 照片的 `謄本.頁數` 和其他值一樣找行，可能框到任一含該數字的行，位置不代表頁數印在哪（電子為 `null`，見 V2-18） | `_SKIP_KEYS` 只排除 `判定`、`部是否印出` | 新增 `test_v2_28_photo_page_count_framed_to_any_line`（第 5 輪審查待查 2） |
| V2-29 | `enable_llm` 未帶時預設 `true` | `analyze_document` 的 `enable_llm` Form 預設值 | 新增 `test_v2_29_enable_llm_defaults_true`（第 5 輪審查待查 3） |

標記規則（§4「行為清單檢查」以腳本執行）：
- 「句」的定義：§3.1.4、§3.1.5 內，標題行、程式碼區塊、表頭與分隔列以外的每一行；表格資料列與清單項目整行算一句，段落行以「。」切開後每段（去空白後非空）算一句。
- 每一句至少帶一個標記：〔V2-xx〕＝程式行為，對到本表；〔實測：<repo 內報告路徑>#<節標題>〕＝量測結論與驗收範圍（例：補值不新增錯（C1）、`enable_llm=true` 未驗、照片 `needs_confirmation` 抓不到 OCR 讀錯），報告與節標題要存在；〔政策：<`acceptance.md` 規則或 AM ID>〕＝業主裁定的棄用、移除條件、讀法建議（例：§3.1.5 棄用與移除條件引 R8），ID 要在 `acceptance.md` 找得到。
- 程式行為句不得只標〔實測〕或〔政策〕：判定由主會話寫標記時做，收案 verifier 逐句覆核（腳本判不了句子性質）。

清單完整性檢查（§4「行為清單檢查」）：
- 從 `INTEGRATION.md` §3.1.4、§3.1.5 抽出的 ID 集合，要等於本表的 ID 集合。
- 每一句都有標記，〔實測〕〔政策〕的出處都存在。
- 每列的測試節點都存在，而且通過。
- 收案 verifier 逐列核對：測試的斷言是否逐項支持該列文字（腳本只能證明節點存在且通過，證明不了斷言對題；第 5 輪審查第 2 條就是這種落差）。
- 收案 verifier 另外對上列函式逐一覆核分支：每個會改變回應的分支都要有一列，找到沒有列的分支就是發現。

## 3. 範圍與擁有者

| 項目 | 檔 | 服務的規則 | 擁有者 |
|---|---|---|---|
| 帶參數格式 schema | 新 `docs/api/transcript_records_v2.schema.json` | C13「新增帶參數格式的 schema」；R4、AM-1 | 主會話（衍生腳本產生） |
| schema 同步測試 | 新 `backend/tests/unit/test_transcript_v2_schema.py`（衍生函式＋「檔案＝衍生結果」＋以既有合成紀錄 `_wrap_record` 後通過新 schema＋3 個反例必須不過：`unit` 為 `"px"`、少 `position` 鍵、未包裝的舊形狀） | C13 schema；防止 schema 與實作漂移 | 主會話 |
| 對接規格 | `docs/api/INTEGRATION.md`（§2 路徑 2 列的各處） | R6、R7、R8、C13 | 主會話 |
| 規格行為測試 | 新 `backend/tests/unit/test_transcript_v2_spec.py`（§2.5「新增」各列；只測既有行為，不改 `backend/app/`） | R6（下游只看規格能正確改）；業主 2026-11-09 選「改法：每句都配測試再審」 | 主會話 |
| 線上驗收文件一句 | `docs/testing/transcript-online-acceptance.md:82` | C13「與新規格相反的舊陳述 0 命中」 | 主會話 |
| 實測報告 | 新 `docs/testing/transcript-v2-20261109.md` | R7（規格引用的數字要有出處） | 主會話 |
| JGB 說明草稿 | 新 `.kiro/specs/transcript-records-converge/jgb-note-draft.md` | R7 | 主會話 |
| 索引、目標正本 | `docs/README.md`、`docs/STRUCTURE.md`、`docs/planning/transcript-status.md` §5 三列 | 文件衛生 6；R6 | 主會話 |
| 之後再做 | 新 `.kiro/specs/transcript-records-converge/followups.md` | 工作線收束 2 | 主會話 |

**由主會話直接寫、不派 executor**：內容全是本 session 已查證的實作細節與量測結果（S1～S3 驗收在本 session 進行），交給新代理要重建同樣脈絡，重建成本高於直接寫；寫完由收案 verifier 獨立比對文件與實作（§6）。

非目標：改任何程式行為（`backend/app/` 0 行變動）；改舊 schema `transcript_records.schema.json`；移除舊格式或改預設；送出 JGB 說明；改 AIChatbot、jgb2；英文版規格。

**回滾**：本片只改 5 個既有文件、新增 6 個檔。還原既有文件＝`git checkout 761fff3 -- docs/api/INTEGRATION.md docs/README.md docs/STRUCTURE.md docs/planning/transcript-status.md docs/testing/transcript-online-acceptance.md`（這 5 個檔在 `761fff3` 之後沒有變動，2026-11-09 `git status` 實查；S3 commit `bf0c465` 沒有碰這些檔）；刪除本片新增的 6 個檔：`docs/api/transcript_records_v2.schema.json`、`docs/testing/transcript-v2-20261109.md`、`backend/tests/unit/test_transcript_v2_schema.py`、`backend/tests/unit/test_transcript_v2_spec.py`、`.kiro/specs/transcript-records-converge/jgb-note-draft.md`、`.kiro/specs/transcript-records-converge/followups.md`（刪前列給業主）。開工前主會話再查一次 `git status --porcelain` 存 `E/runs/s4_git_before.txt`。

**開工前提**：S3 §4 驗收全過（envelope §3 S4 依賴「S1–S3 驗收過」），已 commit `bf0c465`；文件寫的是 S3 最終版本的行為。S3 已定版在 AM-9 第四版（四種 C11 全過，見 §5）。

## 4. 每次執行（測試選擇）

| 執行 | 回答的決定 | 改變下一步的結果 | 規模與理由 | 成本（跑前估，附來源） |
|---|---|---|---|---|
| 單元測試全套 | 便宜決定性檢查（本片新增 2 個測試檔：`test_transcript_v2_schema.py`、`test_transcript_v2_spec.py`（23 個測試）） | 新增紅 ⇒ 不送收案；既有 18 個（`E/baseline_s1/fail_s1.txt`）不算 | 全套 | 約 55 秒（S2 收案實跑）；0 模型呼叫 |
| 新 schema 驗實際回應（`E/check_s4_schema.py`，新） | schema 是否接受實作真的回的東西（下游照 schema 驗不會誤擋） | 任一份不過 ⇒ 改 schema 衍生規則或回報實作與規格不符，停 | 電子 5 份（17 頁，帶參數重送 :18085，含多頁、`page`＞1）＋照片 15 頁（`E/runs/s3_http/<頁>_v2.json` 已存的 S3 最終版回應，不重跑 OCR）＋D3 純影像 PDF 6 頁 1 份（`check_s3_c11.py` pdf 模式同一做法組 PDF，帶 `v2` 送 :18087 真 OCR，回應存 `E/runs/s4_schema_d3pdf_v2.json`）：照片單頁回應裡 `類型`＝`null` 0 筆（2026-11-09 主會話實查 15 份、15 張、0 筆），多張合併才會出現，這份照實報 `類型`＝`null` 筆數；`類型`＝`null` 必過的正例另由單元測試 `test_null_type_sheet_validates_once`（合成多張紀錄）保證，不依賴這份剛好有 | 電子約 2 秒（`E/runs/s2_http.txt` 電子 5 份）＋讀檔約 1 秒＋D3 6 頁 × 每頁 2.4–9.5 秒（`E/runs/s1_c15.txt`）約 15～60 秒；0 模型呼叫 |
| 規格範例實跑（同腳本） | 文件寫的請求與錯誤是否與實作一致 | 任一不符 ⇒ 改文件 | 5 個請求：帶 `v2` 謄本 1 次（200、`document_fields` 無 25 欄）；`transcript_format=v3` 謄本 1 次、`contract` 1 次（都 400 `INVALID_TRANSCRIPT_FORMAT`）；`/analyze/batch` 帶 `v2` 與不帶各 1 次（電子 1 份，除易變鍵外相同） | 約 2 秒（電子檔，`s2_http.txt`）；0 模型呼叫 |
| 行為清單檢查（`E/check_s4_claims.py`，新，跑前凍結 sha1） | 規格每一句是否都帶標記，行為句是否都有對應測試且通過（業主選「每句都配測試」） | 任一句沒標記、規格 ID 集合≠§2.5 ID 集合、〔實測〕〔政策〕出處不存在、任一列測試節點不存在或不過 ⇒ 改規格或補測試，停 | 依 §2.5「標記規則」切句檢查；抽 `〔V2-xx〕` 與本檔 §2.5 表比對集合；逐列跑表內 pytest 節點（完整節點 `檔::類別::名`，先 `pytest --collect-only` 印出實際收集到的節點；`test_multi_line_*` 等萬用字元以 `-k` 展開並印節點數，需與表內括號相同）；正對照三份副本都須判不過：少 1 個 ID、留 1 句沒標記、〔政策：R99〕（不存在的 ID）；正式規格須判過 | 約 25 秒（表內約 60 個節點，全套 55 秒的子集）；0 模型呼叫 |
| C13 grep（`E/check_s4_c13.sh`，新，跑前凍結 sha1） | 現行文件還有沒有與新規格相反的陳述 | 反向詞命中 ≥1（排除版本沿革列與紀錄檔）或正對照沒中 ⇒ 改文件 | 反向詞：「新串接請讀這裡」、「請讀 25 個單值欄位」、「請以 25 個單值欄位」、「先讀清單」、「下游讀三種格式」列的「未規劃」；同義改寫另列「照片.*請讀.*清單」「掃描.*25 個單值」「新串接.*transcript_records」「`transcript_records` 幾乎讀不」「幾乎讀不到」「建議讀法見 INTEGRATION 2\.8\.1」「該部沒印 → null」；**排除規則（所有反向詞與同義改寫一體適用，腳本判定）**：同一行含「不帶參數」就略過；範圍：`docs/` 下全部 `.md` 與根目錄 `README.md`，只排除有日期的紀錄檔（檔名含 `-2026MMDD`：`docs/testing/` 的 `amount-string-type-20261029.md`、`bedrock-qwen-switch-20261028.md`、`bedrock-vlm-eval-20261023.md`、`document-fields-fixed-keys-20261029.md`、`qwen-direct-read-20261029.md`、`transcript-photo-fullparse-eval-20261109.md`，與本片新增的 `transcript-v2-20261109.md`）及 `INTEGRATION.md` 版本沿革列（檔首 `> 版本` 開頭的行）；改寫前先跑一次存 `E/runs/s4_c13_before.txt`，須命中 `INTEGRATION.md:382`、`:386`、`:404`、`:465`、`:485`、`:720`、`transcript-online-acceptance.md:82` 與 `transcript-status.md:62`（正對照：證明反向詞抓得到）；另把 §2 路徑 2 寫的改寫句（「不帶參數時照片請讀 25 欄與清單；新串接請帶 `transcript_format=v2`（§3.1.4）」等）存成 `E/runs/s4_c13_rewrite_probe.md` 試跑，須 0 命中（證明改寫句不會被誤抓）；正對照：`transcript_format=v2`、`INVALID_TRANSCRIPT_FORMAT`、`transcript_records_v2.schema.json`、「棄用」各須命中 ≥1 | <1 秒；0 模型呼叫 |
| C13 逐行盤點（`E/check_s4_census.py`，新，跑前凍結 sha1） | 現行文件每一句描述謄本回應形狀的話，對兩種格式是否都正確（範圍不只靠關鍵字） | 有範圍內的行沒有判定，或判「只對不帶參數」的行內沒有「不帶參數」、也不在標題含「不帶參數」或「舊形狀」的小節 ⇒ 改文件，停 | 範圍＝(1) `INTEGRATION.md` §3.1～§3.1.3 與 §7 全部非空、非程式碼圍欄行（以標題定界，不以行號）；(2) 19 個現行文件（排除清單同 C13 grep）中命中樣式的行；樣式＝`transcripts\|transcript_records\|25 個單值\|沒印\|§3\.1\.[123]\|has_building_evidence\|share_slots` 加 31 個舊鍵名（腳本以 `ast` 讀 `TranscriptFieldExtractor.KEY_FIELDS` 與 `analyze_service._LIST_DETAIL_KEYS`，不手抄）；改寫前跑一次存 `E/runs/s4_census_before.tsv`（主會話 2026-11-09 以近似樣式試算約 286 行：INTEGRATION 245、transcript-status 12、online-acceptance 14、`docs/platform/` 兩檔 9、其他 5 檔各 1～2；以腳本實數為準），差距 2 的 11 處與 `INTEGRATION.md:299`、`:304` 必須都在其中（正對照）；改寫後重跑，主會話逐行寫判定（兩種格式都成立／只對不帶參數／帶參數專述／沿革）存 `E/s4_census_after.tsv`，腳本檢查每行都有判定且合判定規則；收案 verifier 全查判「兩種格式都成立」與「帶參數專述」的行（另兩種由腳本規則把關） | <1 秒；人工判定約 290 行；0 模型呼叫 |
| 收案 verifier（S1～S4 一次） | 獨立推翻實作與規格 | REFUTED ⇒ 照 Orchestration 處置 | envelope §4 與 AM-9（≥10 張新照片，劣化類型或種子沒用過）；另比對規格每項宣稱與實作（自己送請求） | 跑前估：≥10 張照片 × 每張 2.4–9.5 秒真 OCR（`E/runs/s1_c15.txt`，:18087）約 1.5 分鐘＋電子對照與規格比對約 20 次請求 × 約 0.4 秒（`E/runs/s2_http.txt` 電子 5 份約 2 秒）；DocuMind 模型呼叫 0（`enable_llm=false`）；verifier token 約 20 萬（本線同類子代理 171,156～218,661，`plan-s3.md` §8 與 S4 審查第 1 輪）；估計，不是上限 |

不跑：照片真 OCR 的位置量測（本片不改程式，S3 已量；上面 D3 PDF 只為 schema 正例）；線上（C14，另問）。

## 5. 終點指標（目標文件＝`acceptance.md`）

受測物：DocuMind `bf0c465`（S3 定版 commit，內容＝量測時的 `761fff3`＋未提交 S3 定版，`git diff` 對量測時檔案 sha1 相同；AM-9 第四版；`transcript_positions.py` sha1 `1c1dc0da71b6`，2026-11-09 14:42 定版；重跑 14:5x～15:1x）。同一目標前兩片：S2、S3。

| 指標 | 現值（S3 最終版） | S2 實際變化 | S3 實際變化 | S4 預期 | 現值來源 | 前兩片變化來源 |
|---|---|---|---|---|---|---|
| E1／E1a／E1b 照片 15 頁讀對／錯／多出（C1） | 167／7（7/7 與舊欄位同值）／0 | 0 | 0 | 不變（不改程式） | `E/runs/s4_pre_impl.txt`（S3 定版上重跑 `measure_s1_impl.py`，檔首寫 commit 與未提交檔 sha1；第 3～34 行與 `E/runs/s2_impl.txt` 逐行相同） | S2：`plan-s3.md` §5 E1～E2b 列（`runs/s2_impl.txt` 第 3～34 行與 `runs/s1_impl.txt` 相同）；S3：`runs/s4_pre_impl.txt` 對 `runs/s2_impl.txt` 第 3～34 行逐行相同 |
| E2／E2a／E2b 照片合併（C2） | 101／2（2/2 同值）／0 | 0 | 0 | 不變 | 同上 | 同 E1 列 |
| E3 jgb2 8 格（C3） | 9 對、0 錯 | 0 | 0 | 不變 | 同上 | 同 E1 列（`plan-s3.md` §5 E3） |
| E4 判定（C4） | 40；0 | 0 | 0 | 不變 | 同上 | 同 E1 列（`plan-s3.md` §5 E4） |
| E5 電子帶參數還原後不同份數（C5） | 0/5 | 0 | 0 | 不變 | `E/runs/s4_pre_check_s2_http.txt`（S3 定版上重跑 `check_s2_http.py`，檔首寫版本：FAIL 0、EXIT 0） | S2：`plan-s3.md` §5 E5（`runs/s2_http.txt`）；S3：`runs/s4_pre_check_s2_http.txt` 與 `runs/s2_http.txt` 皆 FAIL 0 |
| E6／E6a 電子位置（C10） | 98.4%／98.5% | 0→98.4%／98.5% | 0 | 不變 | `E/runs/s3_final_c10.txt`（S3 定版後重跑 `check_s2_c10.py`：717/729、729/740） | S2：`runs/s2_c10.txt` 717/729、729/740（S2 前沒有位置，`plan-s3.md` §5 E6）；S3：`runs/s3_final_c10.txt` 第 30～31 行同數 |
| E7 照片行框包含率（C11，樣本內） | 147/153＝96.1%（樣本內）；樣本外 6 張 30/32＝93.8%；多頁 D3＋D5 26/26、D2＋D4 37/38，頁碼 0 錯 | 不適用 | 0→96.1% | 不變 | `E/runs/s3_c11_photo.txt`、`s3_c11_oos.txt`、`s3_c11_pdf.txt`、`s3_c11_pdf_oos.txt`（執行 14:5x，`transcript_positions.py` `1c1dc0da71b6`） | S2：`runs/s2_http.txt` 照片「position 全為 null」列（`plan-s3.md` §5 E7）；S3：`runs/s3_c11_*.txt` 對照 S2 的 0 |
| E7a 照片有位置比例 | 153/153＝100%（多頁 D3＋D5 33/36） | 不適用 | 0→100% | 不變 | 同上 | 同 E7 列 |
| E7-OOS 收尾樣本外 ≥10 張新照片：含中心率、頁碼錯（AM-9，門檻 ≥90%、頁碼 0 錯） | 現值未量 | 不適用 | 不適用 | 不變（本片不改程式）；由收案 verifier 量 | 業主已接受由收案 verifier 量（`acceptance.md` AM-9「樣本外證據改由收尾驗證員自己做的 ≥10 張新照片提供」）；沒過停下問業主 | 不適用（新指標） |

S4 預期全部不變（只改文件與新增測試，不改程式行為）。斷路器：S3 有變化（E7 0→≥90%），S4 為 0，連續 0 只有 1 片，不觸發；S4 之後沒有下一片（收案）。

## 6. 收案與驗證

本片完成條件：§4 單元測試、schema 驗實際回應、範例實跑、行為清單檢查、C13 逐行盤點與 C13 grep 全過。之後跑 envelope 收案 verifier（S1～S4 一次）：brief 給業主原話（`acceptance.md` §1 原話欄）、`acceptance.md` 路徑、本檔與 `plan.md`、`plan-s2.md`、`plan-s3.md` 路徑、diff；verifier 另比對 `INTEGRATION.md` §3.1.4、§3.1.5 每項宣稱與實作（可自己送請求驗）；對 §2.5 方法段列的函式逐一覆核分支，找沒有列進行為清單、會改變回應的分支；全查 `E/s4_census_after.tsv` 中判「兩種格式都成立」「帶參數專述」的行；逐句覆核 §3.1.4、§3.1.5 標記性質（行為句不得只標〔實測〕〔政策〕），逐列核對 §2.5 測試斷言是否支持該列文字；並做 AM-9 的 ≥10 張新照片。CONFIRMED 後才把 `INTEGRATION.md` 2.9.0 與 JGB 說明草稿交業主（R7）；commit 另問。

## 7. 我改動的地方（相對業主原話、凍結規則與清單）

| 原文（出處） | 本片改成 | 理由 |
|---|---|---|
| C13「新增帶參數格式的 schema」（`acceptance.md`） | schema 由舊 schema 以固定規則衍生，另加一個單元測試鎖住兩檔同步 | **我加的**（測試）：防止日後改舊 schema 忘了改新 schema；不改回應 |
| C13 只列 `INTEGRATION.md`、schema、JGB 草稿 | 另寫實測報告 `docs/testing/transcript-v2-20261109.md`，並改 `docs/README.md`、`docs/STRUCTURE.md`、`transcript-status.md`（`:23` 與 §5 三列）、`transcript-online-acceptance.md:82` | **放寬**：規格引用的數字要有 repo 內出處（`E/` 在 repo 外，下游看不到）；索引與目標正本照文件衛生第 5、6 條同步 |
| C13「與新規格相反的舊陳述 0 命中」 | 改寫差距 2 的 11 處（`INTEGRATION.md` 7、`transcript-status.md` 3、`transcript-online-acceptance.md` 1） | 照文件衛生第 2 條改正文 |
| C13「與新規格相反的舊陳述 0 命中」 | **收窄**：grep 排除 `INTEGRATION.md` 版本沿革列與有日期的紀錄檔（§4 列出 7 個檔名）；範圍限 `docs/` 全部 `.md` 與根 `README.md`（不含程式碼註解、`.kiro/`） | 版本列與紀錄是沿革，文件衛生第 3 條不改寫；程式碼註解與 `.kiro/` 計畫檔不是對下游的規格 |
| C13（只要求 schema 存在、舊陳述 0 命中） | **我加的**驗證：新 schema 驗實際回應（電子 5 份＋照片 15 頁＋D3 影像 PDF 1 份）＋`類型` null 合成正例＋3 個反例必須不過；規格範例實跑 5 個請求；C13 逐行盤點 | schema 和範例若與實作不符，下游照規格寫會壞；只看檔案存在證明不了 |
| 業主選「改法：每句都配測試再審」（2026-11-09 AskUserQuestion） | §2.5 行為清單 29 列；新增 `test_transcript_v2_spec.py`（23 個，執行中補 1 個成 24 個）與 schema 測試 1 個，只測現有行為 | 照業主選項；測試留在 repo，日後行為改動會紅 |
| 業主選「改法：每句都配測試再審」 | **收窄**：只有 §3.1.4、§3.1.5 的程式行為句配測試；量測結論句改標〔實測：報告〕、業主裁定的政策與讀法建議句改標〔政策：規則 ID〕，不配單元測試；既有 §3.1～§3.1.3、§7 與改寫的 11 處不配測試，改由 C13 逐行盤點判定 | 量測結論（例：補值不新增錯）與政策（棄用條件）不是程式分支，單元測試證明不了；既有小節描述不帶參數格式，不在本片新規格範圍 |
| R8「只拿掉舊欄位」（業主已裁定） | 規格照實寫 V2-07（`transcript_records` 空或不存在時帶參數無謄本值），改不改程式登記 followups | **我加的**：只揭露、不改裁定 |
| R8「`needs_confirmation` 與不帶參數相同」 | 規格加「25 欄鍵名 → `transcript_records` 路徑」對照表 | **我加的**：帶參數時 25 欄不回，鍵名沒對照下游看不懂；不改回應 |
| R6「寫明下游改帶參數」 | 另寫帶參數拿不到的值（差距 3 四類：S1 不補的 4 欄、清單沒輸出時的 9 欄、DocuMind 算出的 3 項、依條件拿不到的 3 種情形）與替代讀法 | **我加的**：照實寫換格式會掉的東西，避免下游改了才發現 |
| R7「擬一段給 JGB 的說明」 | 草稿存 `.kiro/specs/`，不送出；收案 verifier 通過後交業主 | 照 R7 的讀法（業主已確認）；送出是對外動作，業主決定 |
| （業主沒說） | 規格寫明 `enable_llm=true` 時照片補值可能含 LLM 補判值、未驗，並登記 followups | **我加的**：照實揭露驗收範圍；要不要驗留給收線時業主裁 |

## 8. 用量回報

本片已用：主會話讀文件與實作；plan-verifier 第 1 輪 171,156、第 2 輪 177,569、收尾 207,579、業主指示續審 193,604、第 5 輪 216,307、第 6 輪 136,247 tokens；收案 verifier 用量收案時補。DocuMind 模型費用 0。
