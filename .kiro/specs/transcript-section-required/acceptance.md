# 必填依「部」決定、空白標記回 null、抽列印時間——驗收清單（2026-10-14；已上線 `48dc2ab`）

切片 ID：**G4-section-blank-printdate**（單一切片；執行與整合皆由主 session 負責）

## 業主原話
- 「做完再跟我討論下一批：建物謄本不要求使用分區、抽申請謄本日期。」
- 「建議是? 這些是特規還是通用修法 ?」→ 回覆三個通用方向後：「照建議」
  （方向：①欄位屬於哪一部統一一處定義，有那一部才要求那一部的欄位；②空值標記依性質回 null，
  不比對字串；③新增列印時間欄位，格式同 `completion_date`，不含時分）
- 先前裁示仍適用：「禁止特規修改 需通用修改」（2026-10-13）

## 查核結果（2026-10-14，唯讀，決定方案的事實）
來源：線上複核項目 12 筆的 `original_result.pages[*]`（`GET /api/v1/review/{id}`）＋忠孝東路線上重送輸出。
1. **建物謄本一律被要求使用分區**：12 筆裡所有建物頁的 `needs_confirmation` 都含 `land_use_zone`；
   8 份基準中 02、03、04、06、07 的 `needs_confirmation` 都有它，**06 唯一的待確認欄位就是它**。
2. **同類未見案例已證實存在**：純土地謄本被要求建物欄位——基準 01 的待確認 7 欄
   （`building_address building_number floor_area floor_level main_material main_usage total_area`）全是建物欄位。
3. **列印時間**：有抬頭的文字全部印成 `列印時間:民國YYY年MM月DD日HH時MM分`——三份真實謄本、OCR 掃描件
   01（6df888ad）、02（37919363）、06（2eb94edb）、07（64f8a74d）的原文，以及 08 的 PDF 文字層（`pdftotext` 實看）；沒有的 3 份（03、04、05）是只拍到標示部或他項權利部的裁切圖，原文就沒有這行。
4. **空值標記的實際形式**（輸出裡全部的例子）：`(空白)`（`land_use_zone`、`land_use_type`、`main_usage`）、
   `民國---年--月--日`（`completion_date`）。只出現在頂層單值欄位，清單明細沒有。
5. **反例查找**：13 份原文中「冒號後是括號註記」：整個值就是括號註記 41 處，**全部是 `(空白)`**；
   找到的反例都是「括號註記後面還有內容」：`其他登記事項:(一般註記)登記原因:增建`、
   `證明書字號:(空白)字第號`——規則只認「整個值」就不會誤殺。
6. ⚠️ **必填欄位本身印空白**：長春路、懷寧街的 `main_usage` 原文是「主要用途:(空白)」（必填欄位）。
   若空白一律當「讀不到」，這兩份會新增進複核。方案：**空白標記＝讀到了「空」**（值 null、信心度 0.9、不進待確認）。
7. **沒有「部」標題的頁**：長春路、懷寧街第 2、4、6 頁沒有任何部的標題，但每頁都印抬頭「建物登記第二類謄本」；
   有抬頭的頁 100% 印「土地登記第X類謄本」或「建物登記第X類謄本」。完全認不出的只剩裁切圖（03、04 有標示部標題，05 什麼都沒有）。
8. **文件層聯集**（plan-verifier 指出）：文件層的評分欄位＝各頁待確認清單的聯集（`analyze_service._scored_fields_from_pages`）。
   各頁都認得出時，逐頁規則就足夠（每頁只要求自己那一部，聯集＝整份實際有的部）；有一頁認不出時，該頁照現行全部要求，
   整份仍會要求所有部的欄位——**刻意保留**：那一頁可能是讀壞的另一部。土地頁＋讀壞的建物頁正是 0658077 災情的情境
   （`_backfill_land_rights_scope` 會把土地持分以 0.9 補進 `rights_scope`，見其已知限制 1），目前唯一的攔截就是複核。

## 修法（三項皆通用規則，一處定義）
1. **必填依「部」決定**（`TranscriptFieldExtractor`）
   - **欄位所屬只宣告一次**（新增 `FIELD_SECTION`：欄位 → 土地／建物；未列＝兩種都有）：
     建物＝`building_number building_address main_usage main_material total_floors floor_level floor_area total_area completion_date
     sub_building_usage sub_building_area shared_build_number shared_area`（即現行 `_BUILDING_EVIDENCE_FIELDS` 的 13 欄）；
     土地＝`land_use_zone land_use_type land_rights_scope`；其餘（含 `land_number area rights_scope owner section print_date`）兩種都有。
   - 由這份宣告**推導**，不另列清單：(1) 各部專屬必填＝`REQUIRED_FIELDS` ∩ 該部（建物 7 欄、土地 `land_use_zone`）；
     (2) 判斷「有哪幾部」用的跡證欄位＝該部全部欄位（建物跡證因此與現行 13 欄相同，`_BUILDING_EVIDENCE_FIELDS` 改為由宣告產生）。
   - `_BUILDING_SECTION_FIELDS`、`_LAND_SECTION_FIELDS` 是另一個概念——**持分要在哪一段所有權部裡找**（`_scope_for` 的比對範圍），
     不是欄位所屬：`land_use_zone` 屬土地卻印在標示部，套那個範圍會讀不到。兩者保留，註解寫明差別。
   - 每頁判斷「有哪幾部」（抽成一個函式，`has_building_evidence` 也改由它產生；唯一變化是多認抬頭，見下方 ⚠️）：
     建物＝抬頭「建物登記…謄本」、建物所有權部或建物標示部標題，或任一建物欄位有讀到（信心度 > 0，含原文印空白）；
     土地＝抬頭「土地登記…謄本」、土地所有權部或土地標示部標題，或任一土地欄位有讀到。
     ⚠️ `has_building_evidence` 不加抬頭以外的新條件；加入抬頭只會讓它更容易成立（寧可多認，遞補只會更少發生）。
   - 必填＝兩種都有的必填 ∪ 該頁認出的那一部的專屬必填。**認不出任何一部 → 照現行全部要求。**
   - 基底 `RegexFieldExtractor._required_fields` 改成接受該頁文字與規則讀值（預設行為不變，帳單不受影響）。
   - **文件層不改**（`analyze_service` 不動）：理由見查核 8。
2. **空值標記 → null，算「讀到了」**（共用模組 `text_normalize`，新增 `is_blank_marker`；基底 `_extract_with_regex` 使用）
   - 依性質判斷，不列字串：(a) 整個值是一段括號註記；(b) 有日期結構（含「年」「月」）卻沒有任何數字；
     (c) 去掉空白、標點與符號（Unicode 類別 P、S）後什麼都不剩。
   - 實作細化（2026-10-14，未擴大範圍）：(b) 落實為「『年』前一個字是補位字元，且整個值沒有任何數字（Unicode 類別 N）」，
     國字日期「民國九十年五月三日」因此不會被誤判（單元測試鎖住）。
   - 值為 `null` 時 `document_fields` 不出現該鍵（既有合併行為：`_merge_fill_missing` 不寫入 null）。
   - 符合時值為 `null`、該欄信心度 0.9（原文明確印空白＝已讀到），不進 `needs_confirmation`、不觸發 LLM。
   - 謄本與帳單（經基底）共用。合約見非目標。
3. **新增 `print_date`（列印時間）**（`TranscriptFieldExtractor`）
   - 標籤式樣式，取 `列印時間:` 後的 `民國YYY年MM月DD日`，不含時分；格式同 `completion_date`。
   - 加入 `KEY_FIELDS`（排在最後）與 `FIELD_LABELS`（`列印時間`）；**不列必填**（裁切圖本來就沒有）。
4. **文件**：`docs/api/INTEGRATION.md` 升 2.2.0——§3.1 加 `print_date`、空白標記回 null 的語意（信心度 0.9 代表原文空白）、
   必填依部決定；連同尚未 commit 的 2.1.2（合約值半形）一起提交。

## 負責檔案（主 session 撰寫）
- 修改 `backend/app/lib/multi_type_ocr/text_normalize.py`（新增 `is_blank_marker`）
- 修改 `backend/app/lib/multi_type_ocr/field_extraction_base.py`（空白標記；`_required_fields` 可依頁面內容覆寫）
- 修改 `backend/app/lib/multi_type_ocr/transcript_field_extractor.py`（`FIELD_SECTION` 宣告與推導、部的判斷抽成一處、`print_date`）
- 新增 `backend/tests/unit/test_section_required.py`（C6 全部新測試）
- 更新 `backend/data/transcript_samples/expected/*.json`（僅「預期差異」表宣告的差異）
- 修改 `docs/api/INTEGRATION.md`、`docs/testing/transcript-online-acceptance.md`（若基準說明需同步）

## 預期差異（8 份基準，依查核結果推算，實作後以重放為準）
| 基準 | `needs_confirmation` 現況 → 預期 | 其他欄位 |
|---|---|---|
| 01 純土地 | 7 個建物欄位 → `[]` | `land_use_zone` `(空白)`→null；`print_date` 新增 |
| 02 | 去掉 `land_use_zone`，剩 4 欄 | `print_date` 新增 |
| 03、04 建物裁切 | 去掉 `land_use_zone` | 04 `completion_date` `民國---年--月--日`→null |
| 05 他項權利裁切 | **不變**（認不出任何一部，照現行全部要求） | 無 |
| 06 | `[land_use_zone]` → `[]` | `print_date` 新增 |
| 07 | 去掉 `land_use_zone` | `print_date` 新增 |
| 08 合併 | `[]` 不變 | `completion_date`、`land_use_zone`、`land_use_type` →null（信心度 0.9）；`print_date` 新增 |
`extraction_confidence` 隨評分欄位改變而變動（預期上升），逐份列出。
空白標記命中清單已用規則逐值掃過 8 份基準（2026-10-14）：只有 01 `land_use_zone`、04 `completion_date`、08 `completion_date land_use_type land_use_zone`，與上表一一對應。

## 驗收項
| # | 對應原話 | 觀察點 | 證據 | 通過條件 |
|---|---|---|---|---|
| C1 | 「建物謄本不要求使用分區」 | API `document_fields`（本機文字層重放；上線後線上實測） | 長春路、懷寧街＋基準 02、03、04、06、07 修正前後 diff | `needs_confirmation` 都不含 `land_use_zone`；06 變 `[]` |
| C2 | 「通用」同類未見案例 | 同上 | 基準 01 diff | 不再要求建物欄位（`needs_confirmation` 不含任何建物專屬欄位） |
| C3 | 「通用」不靜默放行 | 基準 05＋單元測試＋合併層測試（`_merge_page_structured_data` → `document_fields`、`_scored_fields_from_pages`） | diff＋pytest | 05 `needs_confirmation` 不變；測試：①只有抬頭「建物登記第二類謄本」、無部標題的頁認成建物（修正前失敗）；②標題讀壞但建物欄位有讀到仍認得；③單頁兩部皆認不出 → 全部要求；④**土地頁＋完全認不出的建物頁＋可遞補的土地持分 → 文件層 `needs_confirmation` 仍含建物專屬必填、閘控評分欄位含它們**（鎖住 0658077 的兜底，修正前後都通過）；⑤建物跡證欄位與建物專屬必填皆由 `FIELD_SECTION` 推導（改宣告兩者同步） |
| C4 | 「（空白）回 null」（照建議） | API `document_fields`＋`field_confidences` | 忠孝東路、長春路、懷寧街＋基準 01、04、08（含 08 `land_use_type`） | `(空白)`、`民國---年--月--日` 全為 null，該欄信心度 0.9、不在 `needs_confirmation`；長春路、懷寧街**不因 `main_usage` 新增待確認**；單元測試：`(一般註記)登記原因:增建`、`民國084年02月日`、遮罩姓名 `黃**`（08 的 owner）原值保留 |
| C5 | 「抽申請謄本日期」 | API `document_fields.print_date` | 三份真實謄本＋8 份基準 | 忠孝東路 `民國108年04月02日`、長春路 `民國101年07月11日`、懷寧街 `民國102年10月14日`；01、02、06、07、08 有值（對照原文）；03、04、05 為 null |
| C6 | 不退步 | backend/tests/unit 全套 | pytest | 全過；新測試分兩類並逐項標明——**修正前失敗、修正後通過**（新行為）：建物頁不要求使用分區（C1）、土地頁不要求建物欄位（C2）、C3① 抬頭認成建物、C3② 標題讀壞欄位有讀到仍認得、C3⑤ 由 `FIELD_SECTION` 推導、三種空白標記回 null 且信心度 0.9（C4）、列印時間（C5）；**修正前後都通過**（鎖住現行行為）：C3③ 兩部皆認不出照舊、C3④ 土地頁＋認不出的建物頁仍要求建物欄位、三個反例原值保留、帳單抽取器行為不變 |
| C7 | 不退步 | 8 份基準＋3 份真實謄本 | 與現況 diff | **只有**上表宣告的差異與 C1–C5 的變化；其他欄位 0 改變 |
| C8 | 處理速度 | 正式機 `stats.total_time_ms` | 三份真實謄本線上實測（一次一份，部署後先送一份暖機不計） | 與現行 38–70 ms 同量級（每份 < 0.5 秒） |
| C9 | 上線後成效 | 正式機 API | 三份真實謄本線上實測 | 線上輸出＝本機重放 |
| C10 | 下游看得到 | `docs/api/INTEGRATION.md` | 文件 diff | 寫明 `print_date`、空白回 null（信心度 0.9 的意義）、必填依部決定、版本 2.2.0 |

## 非目標
- **合約不套用空白標記**：合約信心度以「有沒有值」計算（`ContractFieldExtractor._calculate_confidence`），
  空白改 null 會被當成沒讀到而拉低信心度、可能多觸發 LLM；要做需另設計「讀到空白」的表示。
  目前也沒有真實合約原文出現整值括號註記的證據。
- 多棟謄本的頂層單值只放第一棟（既有行為）。附帶影響：某頁原本印「(空白)」擋住後頁值，改 null 後可能由後頁填入；
  這與「讀不到」的既有合併行為一致，清單欄位不受影響。
- `area` 的語意（建物謄本也會比到層次面積等）不在本批。
- **有一頁認不出是哪一部的多頁上傳**：整份照現行要求所有部的欄位（例：土地頁＋沒拍到抬頭的他項權利裁切頁仍會被要求建物欄位、進複核）。
  理由與殘餘影響見查核 8：放寬會拆掉 0658077 災情唯一的攔截；代價是這類上傳維持現狀（多一次複核），不會比現在差。
- 列印時間不轉西元、不含時分（業主照建議）。
- G2、公同共有、S3、外框 PDF 等其餘候選。

## 預算
- 修正／重驗：fresh verifier 最多 2 輪；第 2 輪仍 REFUTED 即暫停交業主。
- 線上實測：三份真實謄本 PDF 各 1 次（另加部署後暖機 1 次），一次一份，每份之間看 `docker stats`；不送任何多頁掃描件。

## 停止條件
| 條件 | 動作 |
|---|---|
| 部署前 C7 出現宣告以外的差異 | 暫停，不 commit，回報業主 |
| 單元測試有任何失敗 | 暫停修正（算入預算） |
| 上線後 C9 線上輸出與本機重放不同 | 回滾（`git reset --hard 3d07e2e`），回報 |
| 上線後 C8 暖機後任一份伺服器處理時間 > 0.5 秒 | 暫停後續實測，回報；是否回滾由業主決定 |
| 線上實測期間容器 OOM 或重啟 | 立刻停止實測，回滾，回報 |
| 健康檢查非 200 超過 2 分鐘 | 回滾，回報 |

## 回滾
伺服器 `cd /home/chatbot/DocuMind && git reset --hard 3d07e2e`（bind mount＋`--reload` 立即生效）；觸發條件見上表。

## 上線流程（核准本 Plan 即含以下動作）
本機實作 → C6、C7 → fresh verifier（C1–C7、C10）→ commit＋push main → 伺服器 `git pull` → health＋記憶體 →
C8、C9 → 回報。每次線上實測送出的謄本若進複核佇列，id 記入工作線快照（業主裁示先不刪）。

## 審查紀錄
| 輪 | 審查發現 | 處置 |
|---|---|---|
| 1 | 文件層聯集讓一頁認不出就帶回另一部欄位 | FIX→再收斂：先加文件層過濾（第 2 輪推翻），最後改為「不改文件層、認不出照現行」並列非目標（查核 8） |
| 1 | 08 `land_use_type` 漏宣告 | FIX：補上；規則逐值掃 8 份基準確認無其他遺漏 |
| 2 | 文件層過濾在「土地頁＋讀壞建物頁」靜默放行，拆掉 0658077 兜底 | FIX：移除文件層過濾（含 `section_scope`、前端與 `analyze_service` 改動）；C3④ 鎖住兜底 |
| 2 | 欄位所屬分散在多份清單 | FIX：`FIELD_SECTION` 單一宣告，必填專屬與跡證欄位皆由它推導；C3⑤ 鎖住 |
| 3（收尾） | C6 要求鎖現行行為的測試也「修正前失敗」，照字面無法達成（審查員標 wording-only，P2） | FIX：C6 分兩類逐項標明；**fixed, not re-reviewed** |
