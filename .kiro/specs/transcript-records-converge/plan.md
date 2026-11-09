# 謄本輸出收斂＋欄位位置——計畫（2026-11-09 核可）

規則與驗收清單：同目錄 `acceptance.md`（2026-11-09 核可凍結）。量測檔在 `~/jgb-archive/transcript-photo-fullparse-eval-20261109/runs/`（簡寫 `runs/`）。

## 0. 目標正本定位

目標正本：`docs/planning/transcript-status.md`。
- 碰到的原則（§1）：「電子謄本上印的每一項都要解析出來、而且讀對」——S1 讓下游只讀一處就拿得到所有讀得到的值，S2 在電子檔附位置；「實際要處理的謄本是電子檔，掃描／拍照排到提升機器規格之後」——S1、S3 碰照片，依據是業主 2026-11-09 選「電子 PDF＋照片都做」，只限補值與位置，不含提升 OCR 讀對率（非目標）；「修法一律通用，不打特規」——S1 對應表依欄位意義、S1 日期檢查依鍵名性質、S2 字元位置對回原文不列字元清單。
- 碰到的待辦列（§5）：「下游讀三種格式」（本線直接處理：帶參數只回一種新格式＋舊格式公告棄用）；「TFS-2 jgb2 改讀 `transcript_records`」與「TFS-3 AIChatbot 改讀」（本線不改下游，交規格，下游改帶參數）；「照片／掃描謄本全文」（本線不提升讀對率）；「25 欄 `section`／`subsection` 會切錯」（S1 不從這兩欄補值）。
- 已知偏離：目標正本沒有編號的已知偏離；本片不屬過渡修正。
- 終點的目標文件：目標正本沒有寫本線「怎樣算完成」的量法，所以以本計畫的凍結驗收清單為目標文件。

審查紀錄：`~/jgb-archive/transcript-photo-fullparse-eval-20261109/reviews/plan-review-round6-20261109.md`（第 6 輪收尾審查 REVISE，1 項實質：R8 漏留 `validation_warnings`；已照最小修正改成「只拿掉舊欄位」）
省略審查：業主原話「改成只拿掉舊欄位」（2026-11-09 第 6 輪 REVISE 交回業主，業主選此項、未選「改完再審一輪」；收案 verifier 照舊）
風險觸發：資料／序列化格式（新增參數、帶參數時改變 `transcript_records` 形狀並不回舊格式）＋跨元件驗收（AIChatbot 正式機、jgb2 staging 讀這份回應）→ 送審前派 plan-verifier、收案前派 verifier。審查紀錄：第 1 輪 REVISE（子代理回報，未存檔）；第 2 輪 REVISE `~/jgb-archive/transcript-photo-fullparse-eval-20261109/reviews/plan-review-round2-20261109.md`；第 3 輪（收尾審查）REVISE `~/jgb-archive/transcript-photo-fullparse-eval-20261109/reviews/plan-review-round3-20261109.md`，修正後業主選「再審一輪」；其後業主改裁「照 JGB 放每個值旁邊」「帶參數換格式」，計畫已改，第 4 輪 REVISE `~/jgb-archive/transcript-photo-fullparse-eval-20261109/reviews/plan-review-round4-20261109.md`（R8 交業主裁定「都不回」；擁有者、受測路徑、攔截後才轉換已改）；第 5 輪 REVISE（同檔「第 5 輪」段：1 項實質照業主選項原文修正、4 項用字），修正後未再審，業主 2026-11-09 核可（工作模式 AUTO；C14 線上確認業主同意；R0 文件修正已 commit `49faf53`）。

## 1. 收案條件（開工一句）

S1～S4 的 C1～C11、C13、C15 全過（C12 是展示項，不擋收案）、收案 verifier CONFIRMED、`INTEGRATION.md` 2.9.0 與給 JGB 的說明草稿交到業主手上，就收；C14（線上確認）業主同意才做，不同意就在收案報告寫「線上未驗」。

## 2. 目標 → 目標形態 → 差距 → 路徑

**目標**（acceptance R0–R7）：下游只讀一處就拿得到所有讀得到的值；這一處的每個值旁邊附原檔位置；現有回應不變；舊格式公告棄用。

**目標形態**（業界原文存 `~/jgb-archive/documind-output-converge-20261109/sources/`，渲染後抽字；三家做法不同，不推成「業界都」）：
- 一個主要欄位結構＋另放全文。Azure：「Fields recognized are returned in the fields dictionary within the list of documents」（`azure-analyze-response.txt:113`），全文另放「The top-level content property contains a concatenation of all content elements in reading order」（`:97`）；明細是陣列欄位（`azure-rest-get-analyze-result.txt:6458-6464`）。Google：明細每列一個 entity，「line_item is a parent field that has two child fields」（`google-handle-response.txt:797`），全文另放 `text`（`google-rest-document.txt:221`）。AWS 不同：單值與明細分兩塊平行，「Each ExpenseDocument is further separated into LineItemGroups and SummaryFields」（`aws-expense-documents.txt:52`）。三家都沒有找到「同一個值在兩種欄位結構各放一次」的做法（未查完）。
- 每個值附位置：Azure「Each region specifies the page number (1-indexed) and bounding polygon」（`azure-analyze-response.txt:124`）；Google「pageAnchor … Represents the provenance of this entity wrt. the location on the page」（`google-rest-document.txt:1944`）；AWS「PageNumber: The page number the value was detected on」（`aws-api-expensefield.txt:112-114`）＋ Geometry（`aws-api-expensedetection.txt:98-100`）。三家位置都跟值放在同一個物件。
- 演進不破壞舊下游：Azure 以 api-version 鎖定、舊版公告停止支援日（`azure-migration.txt:71-73`），破壞性改動跟新版本出（`:185-186`）；Google 至少提前 6 個月通知（`google-processor-versions.txt:178`）。本線的對應：新格式要呼叫方帶參數才拿到、不帶參數的回應不動、舊格式公告棄用。
- 呼叫方以參數選擇回傳內容：Azure「An optional features query parameter to Analyze operations can optionally enable specific features」（`azure-migration.txt:155`）；AWS「You can choose which type of analysis to perform by specifying the FeatureTypes list」（`aws-api-analyzedocument.txt:79`）。兩家的參數是多回內容，不改既有欄位形狀（偏離 D5）。
- 讀不到：Azure 無法正規化時只給 content、省略 value（`azure-analyze-response.txt:275-279`）；Google `normalizedValue`「Absent if the extracted value could not be converted」（`google-rest-document.txt:1958`）。

**差距**（2026-11-09 查證）：
1. `transcript_records` 只由全文解析產生（`analyze_service._attach_transcript_records` → `build_transcript_records`）；照片 15 頁的 816 個葉值只讀對 73、錯 0、缺 743（`runs/s1_prodpath.txt` 改前欄，正式程式路徑）。規則抽到的值只在 25 欄與清單，下游要讀三處才拿得齊。15 張照片的 `transcript_records[0].標示部` 全是 `null`；AIChatbot 正式機以「`標示部` 是否為 dict」分電子／掃描路徑（AIChatbot `origin/main` `rag-orchestrator/services/documind_client.py` `extract_deed_fields`），所以補值不能寫進不帶參數的 `transcript_records`（業主 2026-11-09 裁：帶參數換格式）。
2. 位置完全沒有：電子 PDF 只取 `page.get_text()` 純文字（`app/lib/pdf_text_layer.py` `extract_text_layer_pages`）；OCR 的 `rec_polys` 行框在 `app/lib/ocr_enhanced/engine_manager.py` 被丟掉，只留整頁平均分數。
3. 可利用的既有機制：解析器帳目 `parse_with_ledger` 每行原文記 (頁, 行, 去處)；`build_with_trace` 記 transcripts 路徑 → records 路徑。電子 PDF `get_text()` 的行與 `get_text("dict")` 的行在 5 份 17 頁上一對一相同，且有逐字框（`rawdict` 共 25352 字；`probe_pdf_lines.py`）。OCR 沒開 `use_doc_unwarping`／`use_doc_orientation_classify`，前處理只有等比例縮放（`preprocessor.adjust_resolution`），OCR 框換成 0～1 比例後對得上原圖。
4. 規格沒有棄用機制：只有一個版本字串，沒有 api-version 參數。
5. 下游只讀指名的鍵：jgb2 `origin/staging`（`a2689ab6a8`）`app/Services/Transcript/TranscriptFieldMapper.php` 讀 `transcript_records`、`shared_parts` 等指名鍵（`$directMap` 迴圈、`allRecords`）；AIChatbot `extract_deed_fields` 同樣只讀指名鍵。不帶參數時回應不變，兩者不受影響（C7 驗 AIChatbot；jgb2 由 C6 舊鍵逐位元不變承接，未實跑 PHP）。

**偏離目標形態（每項附理由）**：
- （無 D1）位置與值放在同一個物件 `{"value", "position"}`，與三家做法及 JGB 提議一致（業主 2026-11-09 裁「照 JGB 放每個值旁邊」）。代價：帶參數的 `transcript_records` 值形狀與不帶參數不同，下游改帶參數時要改取 `value`。
- D2 不附信心度。理由：R3，與 2026-11-09 實驗（`runs/linescore_result.txt`：行層門檻 0.98 抓讀錯 115/136、誤標讀對 174/567；值層讀錯 6 個分數 0.93–0.998）。三家都有信心度，這是明確偏離。
- D3 照片框到行、不框到字。理由：PaddleOCR 只回行框（`rec_polys`）；以字數比例切字框是估計，不宣稱精確。查無業界對應的「行框代值框」做法，屬第一原理取捨。
- D4 棄用沒有固定停止支援日。理由：已知下游只有 AIChatbot 與 jgb2，移除條件寫成「兩者都改帶參數並經業主確認」，移除方式＝另開一片把預設改成新格式並拿掉舊格式；業主選「本線只公告棄用」。與 Azure／Google 的固定日期、6 個月通知不同。
- D5 帶參數會改變同一個鍵 `transcript_records` 的形狀。理由：業主 2026-11-09 選「帶參數換格式」，要同一份回應只有一種謄本結構；Azure `features`、AWS `FeatureTypes` 的參數只多回內容、不改既有欄位形狀（引文見上），本線比兩家多走一步。代價：同一個鍵依參數有兩種 schema，規格要分開寫清楚。

**路徑**：見 §3。每片對應的規則與目標寫在片內；相關但不在本次範圍：信心度（D2）、提升照片 OCR 讀對率、實際移除舊格式、AIChatbot 與 jgb2 改讀（業主選「只改 DocuMind」）、真實掃描件驗證。

## 3. 切片（program envelope；本次送審＝envelope＋S1）

| 片 | 規則 | 服務的目標／待辦列 | 內容 | 依賴 |
|---|---|---|---|---|
| S1 參數＋補值 | R1 R2 R3 R8 | §1 每一項讀得到就給；§5「下游讀三種格式」 | `/analyze` 新增 `transcript_format`；帶參數時 `transcript_records`＝補值＋每值包 `{value, position}`、不回五種舊格式 | R0 不擋 S1（S1 不碰文件） |
| S2 電子 PDF 位置 | R4 R5 R2 | JGB 欄位位置需求（業主「併進來一起做」） | 文字層逐字框 → 帳目 → trace → 帶參數 `transcript_records` 各值的 `position` | S1 |
| S3 照片位置 | R4 R5 R2 | 同上 | 保留 OCR 行框 → 同一條鏈；補進的值以值文字搜 OCR 行定位 | S1、S2（共用位置組裝） |
| S4 規格與交付 | R0 R6 R7 | §5「下游讀三種格式」、TFS-2、TFS-3 | `INTEGRATION.md` 2.9.0、帶參數格式 schema、給 JGB 說明草稿 | S1–S3 驗收過；R0 文件修正已 commit 或併入 |

### S1 參數＋補值（本次送審的可執行片）

- **做什麼**：`app/api/v1/analyze.py` 的 `analyze_document` 新增表單參數 `transcript_format: Optional[str] = Form(default=None)`；值不是 `None`／`"v2"` ⇒ 400（`error_code` `INVALID_TRANSCRIPT_FORMAT`）；`document_type` 不是 `transcript` 時忽略。`app/lib/multi_type_ocr/transcript_records.py` 新增 `fill_from_rules(records, fields)`（深拷貝 `transcript_records`，依下表補值，再把每個有值的葉子包成 `{"value": 原值, "position": null}`；S1 一律 `null`，S2、S3 才填；`判定`、`部是否印出` 不包、`null` 葉子不包）與 `apply_transcript_format(result)`（對整份 result 深拷貝：`document_fields.transcript_records` 換成 `fill_from_rules` 的結果、拿掉 25 欄／6 種清單／`transcripts`、每頁 `structured_data` 只拿掉舊欄位（`TranscriptFieldExtractor.KEY_FIELDS` 的 25 欄＋`analyze_service._LIST_DETAIL_KEYS` 的 6 種清單）、其餘鍵全留，回傳新 dict）。`analyze_document` 在 `_apply_confidence_gating(result, db)` **之後**、帶參數時回傳 `apply_transcript_format(result)`；不帶參數時完全不走這段。放在信心度攔截之後，是因為 `_apply_confidence_gating` 讀 `pages[].structured_data`、複核佇列存 `{"pages": pages, ...}`（`analyze.py:162`、`:190-195`），前端複核畫面只讀各頁 `structured_data`（`analyze_service.py:357`）；深拷貝讓佇列內容與不帶參數相同（C15）。`AnalyzeService`、`_attach_full_transcripts` 不改；`/analyze/batch` 不加參數。
- **對應表**（原型 `~/jgb-archive/transcript-photo-fullparse-eval-20261109/proto_fill.py` `fill` 已在正式程式路徑上實測，正式實作照此）。「1 張」＝整份回應的 `transcript_records` 只有 1 張；「屬於該張」＝項目 `transcript_id` 等於該張 `謄本.編號`，或項目沒有 `transcript_id` 且只有 1 張。

  | 目標格 | 來源（規則鍵） | 條件 | 轉換 |
  |---|---|---|---|
  | `類型` | `building_number` 有值→建物，否則 `land_number` 有值→土地 | 1 張且 `類型` 為 null | — |
  | `謄本.編號` | 建物 `building_number`／土地 `land_number` | 1 張且為 null | — |
  | `標示部`（整個為 null 時） | 依類型建立固定鍵骨架（`BUILDING_MARK_KEYS`／`LAND_MARK_KEYS`，清單鍵為 `[]`、其餘 null） | `類型` 已知 | — |
  | 建物 `建物門牌` `主要用途` `主要建材` `層數` `建築完成日期` | `building_address` `main_usage` `main_material` `total_floors` `completion_date` | 1 張、格為 null | 原樣；`建築完成日期` 須含年、月、日三段數字（鍵名以「日期」結尾的通則） |
  | 建物 `總面積` | `total_area` | 同上 | `to_number` |
  | 土地 `面積` `使用分區` `使用地類別` | `area` `land_use_zone` `land_use_type` | 同上 | `面積` 用 `to_number` |
  | 建物 `層次[]` | `floors[]` {level, area} → {層次, 面積} | 陣列為空、項目屬於該張 | 面積 `to_number` |
  | 建物 `附屬建物[]` | `sub_buildings[]` {usage, area} → {用途, 面積} | 同上 | 同上 |
  | 建物 `共有部分[]` | `shared_parts[]` {build_number, area, rights_scope} → {建號, 面積, 權利範圍} | 同上 | 同上 |
  | 建物 `建物坐落地號[]` | `land_numbers[]` {section, number} → {段小段, 編號} | 陣列為空、1 張（清單沒有 `transcript_id`） | — |
  | `所有權部[]` | `owners[]`（`part` 與類型相符）{order, name, rights_scope} → {登記次序, 所有權人, 權利範圍}，其餘固定鍵 null | 陣列為空、項目屬於該張 | — |
  | `他項權利部[]` | `other_right_type` → [{權利種類}]，其餘固定鍵 null | 陣列為空、1 張 | — |
  | `判定` | 補值後以既有 `_verdicts` 重算 | 每張 | — |

  不補（附理由）：`謄本.段`／`小段`（`section`／`subsection` 已知切錯，`transcript-status.md` §5）；`謄本.列印時間`（`print_date` 只到日，records 到分，格式不同）；`floor_level`、`floor_area`、`sub_building_*`、`shared_build_number`、`shared_area`、`owner`、`rights_scope`、`land_rights_scope`（由清單涵蓋，單值是清單第一筆）；`seizure_mark`（限制登記判定只依 `所有權部`／`他項權利部` 原文，不憑規則標記改判定）；`has_building_evidence`、`share_slots`、`floor_area_checks`（程式判斷結果，不是謄本上印的值）。
- **受測路徑**：acceptance §2「照片受測路徑」（`measure_s1.py`，函式順序寫在該節）；實作後腳本在組好的 result 上呼叫 `apply_transcript_format`（與 `analyze_document` 帶參數時同一個函式）、讀 `transcript_records`，先把 `{"value","position"}` 還原成 `value` 再評分，不再呼叫原型。
- **原型實測**（`runs/s1_prodpath.txt`，正式程式路徑，檔首有指令、時間、受測物；各單位 `document_fields` 存 `runs/s1_prodpath/`）：照片 15 頁讀對 73→167/816，錯 0→7（7 格全部與舊欄位同值：商業、土造、過满段、最高限额抵押權、加强磚造、黃 ×2），多出 0→0（「民國」由日期通則擋掉）；合併 5 份 62→101/703，錯 0→2（同樣與舊欄位同值）；jgb2 8 格只讀帶參數 `transcript_records` 0→9/26、錯 0；判定 35→40/45，與答案不同的 5 格帶參數全是「無法判定」（判定不同且非無法判定 0）；電子 5 份補值後與 `transcript_records` 不同 0/5。先前原型路徑（未後處理、多頁接起來抽一次）的數字 169／97 不再使用。原型「屬於該張」條件已照 R1(b) 改寫後重量，數字不變（`proto_fill.py` sha1 `0625ac32f1c4`）。
- **不做**：不帶參數的回應不改任何值；不新增鍵；不改 OCR；不改 `/analyze/batch`；不改 `transcript_records.schema.json`（帶參數的 `transcript_records` 還原 `value` 後形狀與它相同，C8 驗證；帶參數格式自己的 schema 檔在 S4）。
- **擁有者**：executor（獨佔 `app/api/v1/analyze.py` 的 `analyze_document`（參數、400、呼叫 `apply_transcript_format`、docstring 錯誤代碼表）；`app/lib/multi_type_ocr/transcript_records.py`（`fill_from_rules`、`apply_transcript_format`）；新測試檔）；主會話整合、跑驗收；收案 verifier。
- **完成標準**：acceptance C1–C9、C15（C8 含包裝形狀檢查，S1 所有 `position` 為 `null`）；單元測試全綠（`backend/venv` 全套）。
- **回滾**：單一 commit，`git revert` 即回；未部署前對線上零影響；部署是另外的業主決定。
- **停點**：C5 或 C6 有任何 diff ⇒ 停、回報；C1–C4 任一讀對數低於門檻、錯值或多出超過門檻 ⇒ 停、回報；C1／C2 出現與舊欄位不同值的錯值 ⇒ 停、回報；C4「判定不同且非無法判定」≥1 ⇒ 停、回報；需要改 schema 檔或既有鍵才做得到 ⇒ 停、回報。

### S2、S3、S4（之後各自送審，這裡只列範圍）
- S2：`extract_text_layer_pages` 另存每行逐字框（內部，不出現在回應）；正規化前後字元位置要對回原文，處理長度會變的字元時依 Unicode 正規化的實際長度對位，不列字元清單（`memory/general-fix-not-local-patch.md`）。
- S3：`engine_manager` 保留每行 `rec_polys` 與文字（內部）；照片補進的值以文字搜尋 OCR 行定位，搜不到給 `null`（11-09 探查：122 個值中 15 個搜不到所在行）。
- S4：版本 2.9.0（新增參數；不帶參數不變、不移除）；帶參數時的形狀、`position` 格式與不回的舊格式（含每頁 `structured_data` 的 25 欄與清單）；五種舊格式（只限謄本）棄用段落與移除條件；照片 `needs_confirmation` 抓不到 OCR 讀錯的說明；帶參數格式 schema 檔。

## 4. 每次執行（測試選擇，S1）

| 執行 | 回答的決定 | 改變下一步的結果 | 規模與理由 | 成本（跑前估，附來源） |
|---|---|---|---|---|
| 單元測試全套 | 便宜決定性檢查，每次改動照跑 | 任一紅 ⇒ 不送驗收 | 全套 | 時間未實測（第一次跑時記下）；0 模型呼叫 |
| C5、C6、C7 電子 | 參數有沒有碰到不帶參數的回應與電子檔 | 任何 diff ⇒ 停 | 5 份 17 頁全部（電子檔是主要用途） | 5 份 × 40–72 ms（伺服器端，`transcript-status.md` §2 速度列）＋HTTP 往返；0 模型呼叫（`enable_llm=false`） |
| C1–C4、C6、C7 照片 | 補值讀對多少、錯值是否都與舊欄位同值、既有鍵是否不變 | 不同值的錯值 ⇒ 停；終點沒動 ⇒ 計入斷路器 | 15 頁＋5 份合併，用已存 OCR 文字（`runs/A/`），不重跑 OCR | 15 頁＋5 份合併＋電子 5 份共 1 次執行約 1 秒（2026-11-09 本機實跑 `measure_s1.py`，不含 OCR），即每單位不到 0.05 秒；0 模型呼叫 |
| C15 複核佇列 | 帶參數會不會改到複核佇列存的內容 | 任何 diff ⇒ 停 | 3 頁（D3、D4、D5 各 1 張低信心照片）× 帶／不帶各 1 次：只需證明轉換在攔截之後、深拷貝不回寫，1 頁即可證，取 3 份不同文件防單一文件剛好沒觸發複核 | 6 次 × 本機 OCR 每頁中位 10.8 秒、最長 24.2 秒（評估報告 `docs/testing/transcript-photo-fullparse-eval-20261109.md`）；0 模型呼叫（`enable_llm=false`） |
| 收案 verifier | 獨立推翻 | REFUTED ⇒ 照 Orchestration 處置 | ≥10 張新劣化照 | 本機 OCR 每頁中位 10.8 秒、最長 24.2 秒（評估報告 `docs/testing/transcript-photo-fullparse-eval-20261109.md` §3.5 A 列）→ 10 張 × 10.8–24.2 秒 ≈ 2–4 分鐘 OCR；verifier 用量未估（上一位 plan-verifier 110,350 token） |

不跑：讀圖模型（Qwen）路徑——不在正式流程；線上（C14）——需業主同意，且 S1 不改 OCR。

## 5. 終點指標（目標文件＝本計畫凍結驗收清單）

受測物：DocuMind `ab38a55`（`app/` 無未提交變動）；改前值取自 `runs/s1_prodpath.txt` 的改前欄（正式程式路徑，檔首有指令、時間、受測物版本），S1 預期取同檔原型改後欄。同一目標文件的前兩片：無（新目標文件，不足兩片）。

| 指標 | 現值（`ab38a55`） | S1 預期 | 來源 |
|---|---|---|---|
| E1 照片 15 頁葉值讀對（816）（C1） | 73 | ≥167 | `runs/s1_prodpath.txt` |
| E1a 照片 15 頁錯值（C1） | 0 | ≤7，且全部與舊欄位同值 | 同上 |
| E1b 照片 15 頁多出值（C1） | 0 | 0 | 同上 |
| E2 照片合併 5 份葉值讀對（703）（C2） | 62 | ≥101 | 同上 |
| E2a 照片合併錯值（C2） | 0 | ≤2，且全部與舊欄位同值 | 同上 |
| E2b 照片合併多出值（C2） | 0 | 0 | 同上 |
| E3 只讀單一結構取 jgb2 8 格（26）（C3） | 0 讀對、0 錯（`transcript_records`） | ≥9、錯 0 | 同上 |
| E4 照片判定讀對（45）（C4） | 35 | ≥40；判定不同且非無法判定＝0（現值 0） | 同上 |
| E5 電子 5 份帶參數（還原 `value`）與不帶參數 `transcript_records` 不同份數（C5） | 參數不存在 | 0/5 | 同上末行（原型 0/5） |
| E6 電子位置吻合率（C10 第一道） | 沒有位置 | S1 不變（前提片）；S2 ≥95% | — |
| E6a 電子有值路徑中有位置的比例（C10 第二道） | 沒有位置 | S1 不變（前提片）；S2 ≥95% | — |
| E7 照片行框包含率（C11） | 沒有位置 | S1 不變（前提片）；S3 ≥90% | — |

C6–C9、C13、C15 是機制項，不列終點。

## 6. 非目標
信心度、提升 OCR 讀對率、移除舊格式、改 AIChatbot 或 jgb2、部署上線（另由業主決定）、真實掃描件驗證。

## 7. 用量回報
已用：業界調查代理約 22 萬 token；plan-verifier 第 1 輪 110,350 token；Bedrock 0。每片收案時回報子代理 token 合計與模型費用。
