# DocuMind OCR 對接規格（給外部系統開發者）

> 版本 2.10.0 ／ 2026-11-11（2.10.0：只影響帶參數 `transcript_format=v2`——照片讀不出結構時多補 `謄本.段`、`謄本.小段`（從全文以全國鄉鎮市區名稱切）、清單沒出來時用單值補第 1 筆 `標示部.層次` 與 `所有權部`、公設車位寫進 `共有部分[].其他登記事項`；`transcript_records` 是 `[]` 或不存在時依建號／地號組 1 張再補，不再回空；不帶參數的回應不變（§3.1.4）；2.9.0：`/analyze` 新增參數 `transcript_format=v2`（只對謄本）——`transcript_records` 每個值包成 `{value, position}`，附值在原檔的位置，照片的空格由 25 欄與清單補進，並拿掉 25 欄、6 種清單與 `transcripts`；不帶參數的回應不變；不帶參數的五種謄本舊格式公告棄用（§3.1.4、§3.1.5，新 schema `transcript_records_v2.schema.json`）；2.8.1：只改文件、回應不變——§3.1.3 的 jgb2 建物謄本表單對照表補「建議讀法」一欄：主建物層次 2–4、共有部分權利範圍與持分面積在清單 `floors`、`shared_parts` 就有，與 `transcript_records` 都有的值先讀清單；照片、掃描謄本的全文解析實測約 6%；§8 補 2026-11-09 另一批較難模擬照片的 25 欄本機實測 77%；2.8.0：欄位值一律是字串——模型補欄位時回的數字（如帳單 `amount` `714`、合約 `deposit` `50000`）改回字串 `"714"`、`"50000"`，見 §3；2.7.1：只改文件、回應不變——§3.5 點交照片範例改為實際格式（`furniture`、`appliance` 是物件陣列，8 個鍵與降級值寫明）；§3.2、§3.3 補金額欄位型別說明；2.7.0：`document_fields` 固定帶鍵——各頁 `structured_data` 有的鍵一律出現，各頁都是空值時回空值本身（`null`、`[]`、`""`），不再省略，見 §2；2.6.0：新增文件類型 `receipt`（收據、發票，回 `amount`、`date`），見 §3.3.1；修繕照片新增 `damaged_items`，見 §3.4；`/classify` 能回 `receipt`；帳單、合約的影像與掃描 PDF 可改由視覺模型直讀、不跑本機 OCR（伺服器設定 `DIRECT_READ_DOCUMENT_TYPES`，預設不列），直讀類與照片類一律呼叫模型、不看 `enable_llm`，見 §2.1、§6；2.5.0：每頁新增 `llm_calls`，列出這一頁每次 LLM 呼叫送到哪個供應商、模型、服務等級、成功或錯誤類別，見 §2.4；LLM 補欄位呼叫失敗時 `llm_used_for_extraction` 為 `false`；2.4.0：謄本新增固定輸出格式 `transcript_records`，每張謄本的鍵固定、沒印回 `null`／`[]`，附 JSON Schema，見 §3.1.3；2.3.0：謄本新增 `transcripts`，謄本上印的每一項都依原文標籤回傳，見 §3.1.2；2.2.0：謄本新增 `print_date`；原文印空白的欄位回 `null`；土地／建物專屬的必要欄位只在該部存在時要求，見 §3.1；2.1.2：合約欄位的值改為半形數字與標點、帶框字還原，見 §3.2；2.1.1：持分欄位的值統一為「分數」或「全部」，見 §3.1；2.1.0：謄本新增 6 個清單欄位與 `land_rights_scope`，並寫明各單值欄位的取值範圍）
> 本文件由 `docs/API_INTEGRATION.md` 與 `docs/api/02-INTEGRATION-API.md` 合併而成。
> 標示「實測」的數字皆取自線上環境(`54.248.201.66`),日期各自註明。
> 唯一需要串的端點是 `POST /api/v1/analyze`；其餘為輔助。

---

## 1. 連線資訊

| 項目 | 值 |
|---|---|
| Base URL | `http://54.248.201.66:8085/api/v1` |
| 互動式文件 | `http://54.248.201.66:8085/api/docs` |
| OpenAPI JSON | `http://54.248.201.66:8085/api/openapi.json` |
| 認證 | **目前無**（MVP 階段未實作 Token） |
| 編碼 | 請求 `multipart/form-data`；回應 `application/json`（UTF-8） |

**瀏覽器端呼叫需先加白名單。** CORS 預設只允許 `http://localhost:3000`、`http://localhost:3001`
（`backend/app/config.py` 的 `CORS_ORIGINS`）。伺服器對伺服器呼叫不受影響。

---

## 2. 主端點：`POST /api/v1/analyze`

上傳 PDF 或圖片，一次完成文字辨識 → 結構化欄位抽取（可選 AI 問答）。謄本與文字層 PDF 走 OCR／文字層加規則抽取；收據、帳單、合約的影像與掃描 PDF 在伺服器開啟「直讀」時，整頁交視覺模型讀，不跑本機 OCR（見 §6）。

### 2.1 請求（multipart/form-data）

| 欄位 | 型別 | 必填 | 預設 | 說明 |
|---|---|---|---|---|
| `file` | file | ✅ | — | `.pdf` / `.jpg` / `.jpeg` / `.png`，上限 **20 MB** |
| `document_type` | string | ✗ | `transcript` | 見 2.2 |
| `enable_llm` | bool | ✗ | `true` | 只影響**謄本**、**有文字層的 PDF**，以及**沒開直讀的帳單、合約**：啟用 LLM 文字校正與補欄位（OCR 信心度 < 85% 才實際觸發，約 $0.02/頁）。**直讀類**（收據、帳單、合約的影像與掃描 PDF，伺服器開啟直讀時）與**照片類**（`repair_photo`、`handover_photo`）一律呼叫視覺模型，不論 `enable_llm` 為何（約 $0.001/頁） |
| `question` | string | ✗ | `null` | 帶入時額外回傳 `answer`，基於本次 OCR 結果作答 |
| `transcript_format` | string | ✗ | 不帶 | 只接受 `v2`：謄本改用帶位置的新格式（§3.1.4），新串接請帶。其他值回 `400 INVALID_TRANSCRIPT_FORMAT`（`document_type` 不是謄本也一樣）；`document_type` 不是 `transcript` 時帶 `v2` 不起作用 |

### 2.2 `document_type` 可用值

| 值 | 文件 | 可接受格式 |
|---|---|---|
| `transcript` | 建物／土地謄本 | pdf, jpg, jpeg, png |
| `contract` | 合約（含租約） | pdf, jpg, jpeg, png |
| `bill` | 帳單（水電／管理費等） | pdf, jpg, jpeg, png |
| `receipt` | 收據、發票（統一發票、電子發票證明聯、手寫收據）。**只在伺服器設定 `DIRECT_READ_DOCUMENT_TYPES` 列入 `receipt` 時開放**，沒開放時回 `400 UNSUPPORTED_DOCUMENT_TYPE`；`400` 訊息裡的「支援的類型」清單可看目前開放哪些 | pdf, jpg, jpeg, png |
| `repair_photo` | 修繕現場照片（VLM 影像理解，非 OCR） | **僅** jpg, jpeg, png |
| `handover_photo` | 點交現場照片（VLM 影像理解 + 詞彙白名單） | **僅** jpg, jpeg, png |

收據的 PDF 不論有沒有文字層都整頁交視覺模型讀；帳單、合約的 PDF 有文字層時仍讀文字層。

舊型別別名會自動轉換：`lease` / `lease_contract` → `contract`；`repair_quote` → `bill`。
傳入 `id_card`、`unknown` 等無對應型別 → `400 UNSUPPORTED_DOCUMENT_TYPE`。

### 2.3 呼叫範例

```bash
# 謄本，含 LLM 校正
curl -X POST "http://54.248.201.66:8085/api/v1/analyze" \
  -F "file=@謄本.jpg" \
  -F "document_type=transcript" \
  -F "enable_llm=true"

# 謄本，新格式（帶位置；新串接請用這個，見 §3.1.4）
curl -X POST "http://54.248.201.66:8085/api/v1/analyze" \
  -F "file=@謄本.pdf" \
  -F "document_type=transcript" \
  -F "transcript_format=v2"

# 謄本，不用 LLM 校正（enable_llm 只影響謄本、文字層 PDF 與沒開直讀的帳單、合約）
curl -X POST "http://54.248.201.66:8085/api/v1/analyze" \
  -F "file=@謄本.jpg" \
  -F "document_type=transcript" \
  -F "enable_llm=false"

# 收據（需伺服器開放 receipt）；一律呼叫視覺模型，enable_llm 不影響
curl -X POST "http://54.248.201.66:8085/api/v1/analyze" \
  -F "file=@收據.jpg" \
  -F "document_type=receipt"

# 合約 + 問答
curl -X POST "http://54.248.201.66:8085/api/v1/analyze" \
  -F "file=@合約.pdf" \
  -F "document_type=contract" \
  -F "question=合約金額是多少？"
```

### 2.4 回應（200）

```jsonc
{
  "file_name": "謄本.jpg",
  "file_url": "https://cdn.example.com/uploads/ocr_transcripts/uuid.jpg",  // S3 上傳失敗時為 null
  "document_type": "transcript",
  "total_pages": 1,

  "pages": [
    {
      "page_number": 1,
      "ocr_raw":            { "text": "土地登記第三類謄本...", "confidence": 0.85 },
      "rule_postprocessed": { "text": "土地登記第三類謄本...", "stats": { "typo_fixes": 12 } },
      "llm_postprocessed":  { "text": "...", "stats": { "llm_cost": 0.02 }, "used": true },  // 未啟用時 null
      "structured_data":    { /* 依 document_type 而異，見 §3 */ },
      "field_confidences":  { "land_number": 0.9, "owner": 0.0 },
      "consensus":          null,
      "text_layer":         true,  // 見下方說明;走 OCR 時此鍵不存在
      "llm_calls": [               // 這一頁的每次 LLM 呼叫;沒有呼叫時是 []
        { "stage": "correction", "provider": "openai", "model": "gpt-5.6-luna",
          "requested_service_tier": null, "service_tier": "default", "ok": true, "error": null }
      ]
    }
  ],

  // ⚠️ 下游請優先讀這個，不要自己合併 pages[].structured_data
  "document_fields": { /* 跨頁彙整後的完整欄位，見 §3 */ },

  "answer": null,                      // 有帶 question 時才有值
  "stats": {
    "total_time_ms": 12500,
    "total_pages": 1,
    "llm_pages_used": 1,
    "estimated_cost": 0.02
  },

  "needs_review": false,               // true = 信心度不足，已自動入人工複核佇列
  "review_item_id": null,              // needs_review 為 true 時是佇列項目 id
  "field_confidences": { "land_number": 0.9 }   // 跨頁取各欄位最大值
}
```

> ⚠️ **影像理解型（`repair_photo`、`handover_photo`）的 `ocr_raw` 與
> `rule_postprocessed` 一律是 `null`** —— 它們走 VLM，不跑 OCR。
> 請勿假設這兩欄必有值（2026-09-09 前這兩欄宣告為必填，會讓那條路徑炸 500）。
> 直讀類（見 §6）的 `ocr_raw`、`rule_postprocessed` 同樣是 `null`。

**多頁文件務必讀 `document_fields`。** 謄本的地號在第 1 頁、建號在第 3 頁是常態，
單頁的 `structured_data` 必然殘缺；`document_fields` 是「只填補缺值」合併後的完整結果，
且 `needs_confirmation` 與 `extraction_confidence` 已依全文重算。
**`document_fields` 固定帶鍵**（2.7.0 起）：各頁 `structured_data` 有的鍵（含巢狀子鍵）在 `document_fields` 一律出現；
每一頁都是空值的欄位，值就是空值本身（`null`、`[]` 或 `""`），請用值判斷有沒有內容，不要用「鍵在不在」。所有文件類型都一樣。
例外：合約的 `rental_terms` 只在讀到租賃欄位時出現（§3.2）；謄本 `transcripts`／`transcript_records` 解析失敗時不出現（§3.1.2、§3.1.3），帶 `transcript_format=v2` 時 `transcripts` 與 25 欄、6 種清單一律不回（§3.1.4）；
`validation_warnings` 只在型別檢查不過時出現（§8）；所有頁都沒有 `structured_data` 時 `document_fields` 為 `null`。

#### `pages[].llm_calls` — 這一頁的 LLM 呼叫紀錄（2.5.0 起）

每次 LLM 呼叫記一筆，依發生順序排列。用來分辨「沒用到 LLM」（陣列為 `[]`）與「LLM 失敗了」（有 `ok: false` 的項目），
以及確認每次呼叫實際送到哪裡。批次端點的每一筆 `result.pages[]` 同樣有這個欄位。

| 欄位 | 說明 |
|---|---|
| `stage` | `correction`（OCR 文字校正）／`extraction`（欄位抽取）／`photo_understanding`（修繕、點交照片理解）／`direct_read`（收據、帳單、合約的整頁直讀，見 §6） |
| `provider` | `openai`／`bedrock`（另有 `anthropic`、`local_qwen`，目前未啟用）。收據、帳單、照片、合約依伺服器的分流設定，謄本一律 `openai` |
| `model` | 實際送出的模型 ID，例如 `gpt-5.6-terra`、`qwen.qwen3-vl-235b-a22b` |
| `requested_service_tier` | 送出時要求的服務等級；只有 `bedrock` 會帶（`flex` 或 `default`），其他為 `null` |
| `service_tier` | 供應商回應實際標示的服務等級；呼叫失敗時為 `null` |
| `ok` | 這次呼叫是否成功 |
| `error` | 失敗時的**錯誤類別**，不含供應商原始訊息：`timeout`、`rate_limited`（429）、`unavailable`（503）、`connection_error`、`invalid_response`、`missing_credentials`、`image_too_large`、`http_<狀態碼>`（如 `http_403`）、`error`（其他）；成功時為 `null` |

- 走 `bedrock` 時每次先送 `flex`；被限流（429）、暫時無法服務（503）或逾時，會以 `default` 重送一次，
  所以同一個階段可能出現兩筆：第一筆 `ok: false`，第二筆是重送的結果。重送仍失敗時，該階段退回規則結果（直讀類沒有規則結果：欄位全空、必要欄位全進 `needs_confirmation`），不會改送其他供應商。
- 欄位抽取失敗時，`structured_data.llm_used_for_extraction` 為 `false`：舊流程的欄位值是規則抽取的結果，直讀的帳單、合約欄位全空。
- 呼叫成功不代表內容讀對：成功的呼叫照樣可能讀錯，判斷欄位可信度仍看 `field_confidences`。

---

## 2.5 批次端點：`POST /api/v1/analyze/batch`

一次送多個檔案。為點交照片而設：現場一次拍十幾張，逐張呼叫要送十幾次請求，
中間斷一次就不知道要補哪幾張。

### 2.5.1 請求（multipart/form-data）

| 欄位 | 型別 | 必填 | 預設 | 說明 |
|---|---|---|---|---|
| `files` | file[] | ✅ | — | 重複帶同名欄位，**一次最多 20 個**，單檔上限 20MB |
| `document_type` | string | ✗ | `handover_photo` | **整批共用**，不能混送 |
| `enable_llm` | bool | ✗ | `true` | 同單張端點 |

批次端點沒有 `transcript_format`，帶了不起作用；謄本要新格式請逐份送單張端點（§3.1.4）。

```bash
curl -X POST "http://54.248.201.66:8085/api/v1/analyze/batch" \
  -F "files=@客廳.jpg" \
  -F "files=@廚房.jpg" \
  -F "files=@衛浴.jpg" \
  -F "document_type=handover_photo"
```

### 2.5.2 回應（200）

```jsonc
{
  "document_type": "handover_photo",
  "total": 3,
  "succeeded": 2,
  "failed": 1,
  "results": [
    { "index": 0, "file_name": "客廳.jpg", "status": "ok",
      "result": { /* 與單張端點的 AnalyzeResponse 完全相同 */ },
      "detail": null, "error_code": null },
    { "index": 1, "file_name": "廚房.pdf", "status": "error",
      "result": null,
      "detail": "檔案格式 .pdf 與文件類型「handover_photo」不相容。",
      "error_code": "INCOMPATIBLE_FILE_TYPE" }
  ]
}
```

### 2.5.3 對接三個重點

1. **單張失敗不會中斷整批。** 壞掉的那張 `status` 是 `"error"`、`result` 為 `null`，
   其餘照常回傳。**請逐筆檢查 `status`**，不要假設 `results` 每筆都有 `result`。
2. **`results` 與送出順序一致**，用 `index` 對回你自己的檔案即可。
3. **這是同步端點**，全部處理完才回應。併發度 4、上限 20 張，
   最壞情況約 5 輪 VLM 呼叫 —— **client timeout 請比照單張端點設 300 秒以上**。

整批共用的錯誤（沒帶檔案 `NO_FILES`、超過張數 `TOO_MANY_FILES`、
型別不支援 `UNSUPPORTED_DOCUMENT_TYPE`）直接回 400，不會進到 `results`。

---

## 3. `structured_data` / `document_fields` 欄位

`transcript`、`bill`、`contract` 與 `receipt` 共通會附帶：
`field_confidences`（逐欄位 0.0–1.0）、`needs_confirmation`（信心不足、建議人工確認的欄位名陣列）、
`extraction_confidence`（必要欄位平均）。`transcript`、`bill`、`contract` 另附 `llm_used_for_extraction`（bool；LLM 補欄位的呼叫成功才是 `true`，
沒有呼叫或呼叫失敗都是 `false`，失敗的細節見 `pages[].llm_calls`）；`receipt` 沒有這個鍵，每頁都由模型直讀。

**欄位值一律是字串**（2.8.0 起）：`transcript`、`bill`、`contract`、`receipt` 的單值欄位（含合約巢狀區塊裡的欄位）不是字串就是 `null`，不會是數字。
金額照讀到的樣子回字串（例：`"25,000"`、`"714"`），要計算請自行轉數字。模型回整數值時不帶小數點（`25000.0` 回 `"25000"`）。
`field_confidences`、`extraction_confidence` 這類信心度才是數字。

**信心度是「這欄怎麼讀到的」標籤，不是準確率，請勿顯示成百分比。**
`transcript`、`bill` 的 `field_confidences` 只會是下列幾個值，沒有中間值：

| 值 | 意思 |
|---|---|
| `0.9` | 規則比對到（含「原文印空白」，見 §3.1） |
| `0.8` | 規則沒比對到，由 LLM 補判（`enable_llm=true` 才會發生） |
| `0.3` | 型別檢查不過（見 §8），或多引擎讀出的值不一致 |
| `0.0` | 讀不到 |

- **直讀類**（收據、帳單、合約的影像與掃描 PDF，見 §6）的 `field_confidences` 值是 `0.9`（模型確定且格式驗證通過）、`0.5`（模型回「不確定」，或格式驗證不過：金額不是數字、日期解析不了）、`0.0`（讀不到）；低於 0.8 的必要欄位進 `needs_confirmation`。模型自評只用來「降」信心度，不會把格式不過的值抬高。
- 規則比對只有「中／沒中」，沒有機率；目前也沒有用人工核對過的標準答案逐欄校準過，所以沒有可給的準確率。
  不採用 LLM 自評的信心度：生成式模型讀錯時產出的是語法合法的錯值，自評分數跟著失準。
- `extraction_confidence` 是必要欄位上述值的平均，例如 4 欄讀到 3 欄得 0.675——意思是「3／4 欄有值」，不是 67.5% 正確。
- `ocr_raw.confidence`：電子檔（`text_layer: true`）固定 `1.0`；掃描件是 OCR 引擎對整頁各行的平均自評分數，未經校準，也不對應到單一欄位。
- ⚠️ LLM 補判的 `0.8` 恰等於複核門檻 0.8（低於門檻才列入），所以**補判的欄位不會進 `needs_confirmation`**。

**下游判斷要不要人工確認，請讀 `needs_review`（整份）與 `needs_confirmation`（哪幾欄），不要自己拿分數比門檻。**
畫面建議顯示狀態文字（已讀到／AI 判讀／需確認），不顯示數字。

### 3.1 `transcript` — 25 個單值欄位 + 6 個清單欄位（不帶參數）

單值欄位每個只有**一個值**；一份謄本有多筆（多位所有權人、多筆地號、多層、多筆公設）時，
單值欄位只放第一筆，**完整資料請讀 §3.1.1 的清單欄位**。

| key | 中文 | 必要欄位* |
|---|---|:--:|
| `land_number` | 地號 | ✅ |
| `building_number` | 建號 | ✅ 建物 |
| `area` | 面積 | ✅ |
| `rights_scope` | 權利範圍 | ✅ |
| `owner` | 所有權人 | ✅ |
| `section` | 段 | ✅ |
| `subsection` | 小段 | |
| `building_address` | 建物門牌 | ✅ 建物 |
| `main_usage` | 主要用途 | ✅ 建物 |
| `main_material` | 主要建材 | ✅ 建物 |
| `total_floors` | 層數 | |
| `floor_level` | 層次 | ✅ 建物 |
| `floor_area` | 層次面積 | ✅ 建物 |
| `total_area` | 總面積 | ✅ 建物 |
| `completion_date` | 建築完成日期 | |
| `sub_building_usage` | 附屬建物用途 | |
| `sub_building_area` | 附屬建物面積 | |
| `shared_build_number` | 共有部分建號 | |
| `shared_area` | 共有部分面積 | |
| `other_right_type` | 他項權利種類 | |
| `seizure_mark` | 查封或限制登記 | |
| `land_use_zone` | 使用分區 | ✅ 土地 |
| `land_use_type` | 使用地類別 | |
| `land_rights_scope` | 土地持分（土地所有權部的權利範圍） | |
| `print_date` | 列印時間（申請謄本日期），如 `民國108年04月02日`，不含時分；2.2.0 起 | |

\* 只有「必要欄位」列入信心度計分。非必要欄位是**本來就可能不存在**
（透天沒有共有部分、無貸款沒有他項權利、`seizure_mark` 沒有才是好事），
抽不到不代表辨識失敗，下游不要當成錯誤。

**「✅ 建物」「✅ 土地」只在該頁有那一部時才要求**（2.2.0 起）：建物謄本不要求使用分區，純土地謄本不要求建物欄位。
判斷依據是謄本抬頭（「建物登記第二類謄本」）、各部標題（建物標示部、土地所有權部…），或該部任一欄位有讀到。
**一頁完全認不出是哪一部時（例如只拍到他項權利部的裁切圖），照舊全部要求**——那一頁可能是讀壞的另一部，
所以多頁上傳中只要夾一張這樣的頁，整份仍會要求所有必要欄位、進複核。

**原文印空白的欄位回 `null`**（2.2.0 起）：謄本把沒有內容的欄位印成「使用分區:(空白)」「建築完成日期:民國---年--月--日」，
這類值不再原樣回傳。判斷規則：整個值是一段括號註記、日期的數字位置全是補位符號，或整個值只有符號。
「原文空白」與「讀不到」在值上都是 `null`，**用 `field_confidences` 分辨**：
原文空白是 0.9、不列入 `needs_confirmation`；讀不到是 0.0。2.2.0 以前這些欄位回的是字串 `"(空白)"`、`"民國---年--月--日"`。

**單值欄位的取值範圍**（同名標籤在謄本上會出現好幾次，以下是系統取的那一個）：

| key | 取的是 | 不會取到 |
|---|---|---|
| `rights_scope` | **建物**所有權部的權利範圍；純土地謄本（整份沒有任何建物跡證）改填土地持分 | 土地持分（合併謄本時）、他項權利部的「設定權利範圍」、公設的權利範圍、歷次取得權利範圍 |
| `land_rights_scope` | 土地所有權部的權利範圍 | 同上 |
| `building_number` | 本戶建號 | 公設（共有部分）建號、重測前舊建號、共同擔保建號 |
| `section` / `subsection` | 現行地段 | 重測前、重劃前的舊地段 |
| `land_number` | 第一個比對到的地號（通常是頁首抬頭） | 共同擔保地號、重測前地號（完整且排除沿革的清單請讀 `land_numbers`） |
| `floor_level` / `floor_area` | 第一個層次與其面積 | 公設的「建物層次:公共設施」 |
| `shared_area` | **整棟公設的面積**（照謄本印的） | ⚠️ 不是本戶分到的面積——那是 `shared_parts[].share_area` |
| `owner` | 第一位所有權人 | — |

**持分的值格式**（2.1.1 起）：`rights_scope`、`land_rights_scope`、`owners[].rights_scope`、`shared_parts[].rights_scope` 與車位持分一律只回 `a分之b` 或 `全部`（謄本印「全部 1分之1」回 `全部`）。標籤後面是說明文字、或值讀不出來時回 `null`，不猜；`rights_scope`／`land_rights_scope` 只取每張謄本第一筆所有權資料的持分：共有時第一位讀不到，不會改取第二位。一次上傳多張謄本（建號或地號抬頭不同）時，**每一張都讀得到且值相同**才回傳該值，否則回 `null` 並列入 `needs_confirmation`——各張的持分請讀 `owners`（每筆帶 `transcript_id`）。建號與地號分開判斷：一棟建物配多筆土地時，`rights_scope` 照常回傳。

`has_building_evidence`（bool）只出現在各頁的 `structured_data`，是合併時判斷「純土地謄本」用的旗標，不是欄位；
`document_fields` 不含它。

#### 3.1.1 清單欄位（2026-09-30 起；不帶參數）

每筆都是物件；讀不到的子欄位為 `null`，**寧可缺值，不給猜測值**。
清單是明細，不是單一欄位：**不出現在 `field_confidences`、`needs_confirmation`，也不計入信心度**。

| key | 每筆內容 | 規則 |
|---|---|---|
| `owners` | `part`（`"land"`／`"building"`／`null`）、`transcript_id`（該筆所屬謄本的地號或建號）、`order`（登記次序）、`name`、`rights_scope` | 每位所有權人一筆；`part` 依上方的所有權部標題決定，看不出就 `null`、不猜。第二類謄本姓名是遮蔽的 |
| `land_numbers` | `section`（段＋小段）、`number` | 只取頁首地號抬頭與建物坐落地號；同一筆地出現在土地抬頭與建物坐落時只算一次；沿革（分割、重測前）、共同擔保地號不算 |
| `floors` | `transcript_id`、`level`（如 `"二層"`、`"騎樓"`）、`area` | **只在各層面積加總等於總面積時才輸出**，否則為 `[]`（原因見 `floor_area_checks`）。名稱與面積數量對不上時不配對，`level` 為 `null` |
| `floor_area_checks` | `transcript_id`、`sum`、`total`、`matches`（`true`／`false`／`null`＝沒讀到總面積） | 每個有層次資料的建物頁一筆 |
| `sub_buildings` | `transcript_id`、`usage`（陽台、雨遮、平台、露台、花台…固定詞彙）、`area` | 用途與面積數量對不上時不配對 |
| `shared_parts` | `transcript_id`、`build_number`、`area`（整棟公設面積）、`rights_scope`（本戶持分）、`share_area`（＝`area`×持分，四捨五入兩位）、`parking`（`[{number, rights_scope, share_area}]`）、`parking_total`（如 `"5位"`） | 每筆共有部分一筆；`rights_scope` 只留分數或「全部」 |

```jsonc
// 範例（士林地政事務所公開範本，線上實測）
"shared_parts": [{
  "transcript_id": "19998-000", "build_number": "11994-000", "area": "509.05",
  "rights_scope": "1000分之193", "share_area": "98.25",
  "parking": [{ "number": "2號", "rights_scope": "1000分之55", "share_area": "28.00" }],
  "parking_total": "5位"
}]
```

多頁文件合併時，清單依頁序串接，只去掉**身分完全相同**的重複項（例如同一頁上傳兩次）；
身分不完整（例如沒有建號抬頭）的項目一律保留，不會被誤併。
各範本的實測結果與已知限制見 [`docs/testing/transcript-online-acceptance.md`](../testing/transcript-online-acceptance.md)。

#### 3.1.2 全文解析 `transcripts`（2.3.0 起；不帶參數）

`document_fields.transcripts` 是**謄本上印的每一項**，依謄本版面結構讀出，標籤用謄本原文（去空白），不另取英文鍵名。
上面 25 個單值欄位與 6 種清單照舊、取值不變；需要的值不在 25 個單值欄位、也不在 6 種清單時才讀這裡（例如所有權人住址、權狀字號、
抵押權人、擔保債權總金額、地目、公告土地現值、謄本檢查號）。

```jsonc
"transcripts": [                         // 一份 PDF 可含多張謄本（如土地 2 筆＋建物 1 筆、或 3 棟建物），每張一筆
  {
    "header": {                          // 頁首
      "謄本種類": "建物登記第二類謄本(建號全部)", "地段": "中山區中山段三小段", "編號": "02080-000", "編號類型": "建號",
      "列印時間": ["民國101年07月11日09時46分", "民國101年07月11日09時46分"], "頁次": ["1", "2"],   // 每頁一個
      "謄本檢查號": "101AC…8806,可至:http://land.hinet.net 查驗本謄本之正確性",
      "資料管轄機關": "臺北市中山地政事務所", "謄本核發機關": "臺北市中山地政事務所",
      "附註": ["本謄本係網路申領之電子謄本,由…自行列印", "中山地政事務所 主 任 施乃仁", "中山電謄字第312290號"]
    },
    "sections": [                        // 依原文的「部」
      { "部": "建物標示部", "entries": [ { "建物門牌": "長春路14之1號", "主要用途": "(空白)",
          "層次": ["一層", "二層", "三層", "四層", "騎樓"], "層次面積": ["96.51平方公尺", "…"], … } ] },
      { "部": "建物所有權部", "entries": [ { "次序": "0001", "登記次序": "0003", "登記原因": "買賣",
          "所有權人": { "_值": "新華開發股份有限公司", "住址": "台北市中山區中山北路二段27巷1號之2" },
          "權利範圍": "全部", "權狀字號": "098北中字第008757號", … } ] },
      { "部": "建物他項權利部", "entries": [ { "權利種類": "最高限額抵押權",
          "權利人": { "_值": "國泰世華商業銀行股份有限公司", "住址": "台北市松仁路7號1樓" },
          "擔保債權總金額": "新台幣 93,600,000元正", "設定義務人": "新華開發股份有限公司", … } ] }
    ],
    "注意事項": ["※注意:一、本電子謄本係依電子簽章法規定產製,…", "二、…"],
    "頁緣": ["88", "10"]                 // 頁面邊緣文字（地政事務所名、頁角碼），非謄本內容
  }
]
```

讀法：
- **`entries`**：所有權部、他項權利部依「(0001)登記次序」一筆一筆分；標示部通常一筆。`次序` 是行首括號內的流水號。
- **重複的標籤 → 清單**：同一筆裡同一個標籤出現多次（如層次表的「層次」「層次面積」）回傳陣列，順序同原文。
  續頁的頁首只略過與該張先前已收過的頁首行逐字相同的行；印有頁次的那一行每頁不同，所以 `header.列印時間`、`header.頁次` 通常是每頁一個的陣列。
- **`_值` 與子標籤**：原文縮排成一組的資料包成物件，`_值` 是組長那一行的值。例：`所有權人` 帶 `統一編號`、`住址`；
  `共有部分` 帶 `權利範圍`、`其他登記事項`；`其他登記事項` 另起一行的子項（如 `因分割增加地號`）。
- **`<標籤>_前文`**：同一行標籤前的文字，例：`公告土地現值_前文: "民國101年01月"`。
- **`注意事項`**：「本謄本列印完畢」之後的注意事項，依「一、二、…」分條，每條一個字串（跨行已接成一句）。
- **`附註`**：沒有標籤的說明句（如「本謄本僅係 所有權個人全部 節本…」），掛在所在的部或頁首。
- **值的形式**：比對用正規化後的文字（全形數字標點轉半形、帶框字 ㈲ 還原成「有」）；補位星號去掉，遮罩星號保留（`黃**`、`A202*****6`）；
  原文印的「(空白)」**原樣保留**（與上面 25 欄回 `null` 不同）。
- **限制**：
  - 只在 `document_type=transcript` 時出現；解析失敗時省略此鍵，其餘回應不受影響。
  - **掃描／拍照謄本**也會出現此鍵，但 OCR 文字沒有可靠的排版：模擬照片 15 頁實測讀對率 6.2%（`docs/testing/transcript-photo-fullparse-eval-20261109.md`）。不帶參數時照片、掃描謄本請讀 25 個單值欄位與 §3.1.1 清單；新串接請帶 `transcript_format=v2`（§3.1.4），照片的值會補進 `transcript_records`。
  - **車位**：公設車位那一行「含停車位○號,權利範圍:…」整行保留為文字、尚未拆成欄位；「停車位共計:○位」照常拆。
  - 只依「編號」分張：不同地段但編號相同的兩張相連會被併成一張（目前樣本無此情形）。

#### 3.1.3 固定輸出格式 `transcript_records`（2.4.0 起；舊形狀，已棄用，新串接請讀 §3.1.4）

`document_fields.transcript_records` 是把 §3.1.2 的 `transcripts` 放進**固定的鍵**：每張謄本一筆，鍵名依官方謄本格式定好、**一律存在**，
謄本上沒印的值回 `null`、沒有資料的清單回 `[]`。逐鍵定義（型別、單位、`null` 的意義）見
[`docs/api/transcript_records.schema.json`](transcript_records.schema.json)（JSON Schema 2020-12，`additionalProperties: false`、所有鍵 `required`）。

```jsonc
"transcript_records": [                  // 每張謄本一筆，順序同 transcripts
  {
    "謄本": { "謄本種類": "建物登記第二類謄本(建號全部)", "類別": "第二類", "申請範圍": "建號全部",
             "行政區": "中山區", "段": "中山段", "小段": "三小段", "編號": "02080-000", "編號類型": "建號",
             "列印時間": "民國101年07月11日09時46分", "頁數": 2,
             "查驗碼": "101AC…8806", "查驗碼標籤": "謄本檢查號", "查驗網址": "http://land.hinet.net",
             "資料管轄機關": "…", "謄本核發機關": "…", "頁首附註": ["本謄本係網路申領之電子謄本,由…自行列印", "…"] },
    "類型": "建物",                        // 土地 | 建物
    "標示部": { "建物門牌": "長春路14之1號", "主要用途": null, "總面積": 403.21,
              "建物坐落地號": [{ "段小段": "中山段三小段", "編號": "0660-0000" }],
              "層次": [{ "層次": "一層", "面積": 96.51 }, { "層次": "二層", "面積": 96.51 }, …],
              "附屬建物": [], "共有部分": [], "其他登記事項": [], … },          // 不帶參數時該部沒印 → null（帶參數見 §3.1.4）
    "所有權部": [{ "次序": "0001", "所有權人": "新華開發股份有限公司", "住址": "…", "權利範圍": "全部",
                 "權狀字號": "098北中字第008757號", "相關他項權利登記次序": ["0009-000"], … }],   // 沒印 → []
    "他項權利部": [{ "權利種類": "最高限額抵押權", "權利人": "國泰世華商業銀行股份有限公司",
                   "擔保債權總金額": 93600000, "設定權利範圍": "全部",
                   "共同擔保地號": [{ "段小段": "中山段三小段", "編號": "0660-0000" }], … }],
    "判定": { "他項權利": "有", "限制登記": "未見", "信託": "未見" },
    "部是否印出": { "標示部": true, "所有權部": true, "他項權利部": true },
    "部附註": { "標示部": [], "所有權部": [], "他項權利部": [] },   // 例:「本謄本僅係 所有權個人全部 節本,…」
    "注意事項": ["※注意:一、…"],
    "其他欄位": []                         // 固定鍵以外的項目，見下
  }
]
```

**各型別傳的欄位**（鍵一律存在；以 1 位所有權人、1 筆他項權利計，土地 86 鍵、建物 84 鍵，其中讀自謄本的資料欄位土地 74、建物 72；所有權部、他項權利部每多 1 筆就多一組）：

| 區塊 | 土地 | 建物 |
|---|---|---|
| `謄本`（頁首，16） | 謄本種類、類別、申請範圍、行政區、段、小段、編號、編號類型、列印時間、頁數、查驗碼、查驗碼標籤、查驗網址、資料管轄機關、謄本核發機關、頁首附註 | 同左 |
| `標示部` | 11：登記日期、登記原因、地目、等則、面積、使用分區、使用地類別、公告土地現值、公告土地現值年月、地上建物建號、其他登記事項 | 13：登記日期、登記原因、建物門牌、建物坐落地號、主要用途、主要建材、層數、總面積、層次、附屬建物、建築完成日期、共有部分、其他登記事項 |
| `所有權部[]`（每筆） | 18：次序、登記次序、登記日期、登記原因、原因發生日期、所有權人、統一編號、出生日期、住址、管理者、權利範圍、權狀字號、相關他項權利登記次序、其他登記事項，**另加地價 4 欄**：當期申報地價、當期申報地價年月、前次移轉現值、地價備註事項 | 14：左列前 14 欄（無地價欄） |
| `他項權利部[]`（每筆，29） | 次序、登記次序、權利種類、收件年期、字號、登記日期、登記原因、權利人、統一編號、住址、債權額比例、擔保債權總金額、擔保債權種類及範圍、擔保債權確定期日、存續期間、清償日期、利息(率)、遲延利息(率)、違約金、其他擔保範圍約定、債務人及債務額比例、權利標的、標的登記次序、設定權利範圍、證明書字號、設定義務人、共同擔保地號、共同擔保建號、其他登記事項 | 同左 |
| 輔助（12） | `類型`、`判定`（他項權利、限制登記、信託）、`部是否印出`（3 部）、`部附註`（3 部）、`注意事項`、`其他欄位` | 同左 |

清單欄位的子鍵：`建物坐落地號`／`共同擔保地號`／`共同擔保建號` `{段小段, 編號}`；`層次` `{層次, 面積}`；`附屬建物` `{用途, 面積}`；
`共有部分` `{坐落, 建號, 面積, 權利範圍, 其他登記事項}`；`管理者` `{姓名, 統一編號, 住址}`；`前次移轉現值` `{年月, 金額, 歷次取得權利範圍}`；
`其他登記事項` `{類別, 標籤, 內容}`；`其他欄位` `{部, 標籤, 值, 原因}`。

值的規則：
- **沒印 → `null`；原文「(空白)」「民國---年--月--日」「--」→ `null`**（與 25 欄一致）；清單沒有資料 → `[]`。原文仍在 `transcripts`。
  要分辨「沒印」與「印了空白」請看 `transcripts`；要分辨「這一部沒印」與「印了但沒有筆」請看 `部是否印出`。
- **數字**：`面積`、`總面積`、`層次[].面積`、`附屬建物[].面積`、`共有部分[].面積` 單位平方公尺；`公告土地現值`、`當期申報地價`、`前次移轉現值[].金額` 單位元／平方公尺；
  `擔保債權總金額` 單位元。值開頭的年月另存在對應的「…年月」鍵（`公告土地現值年月`、`當期申報地價年月`、`前次移轉現值[].年月`）。
- **權利範圍**（`權利範圍`、`設定權利範圍`、`共有部分[].權利範圍`、`前次移轉現值[].歷次取得權利範圍`）：「全部」或「a分之b」，同 §3.1 的 2.1.1 規則。
  `共有部分[].面積` 是共有部分建物的總面積，**不是持分面積**；持分面積＝`面積 × 權利範圍`。`債權額比例` 照原文。
- **日期**：民國原文字串（`民國050年03月14日`），不轉西元。**遮罩**照原文（`黃**`、`A202*****6`），第幾類謄本看 `謄本.類別`。
- **拆開的鍵**：`行政區` 取內政部全國鄉鎮市區名稱（國土測繪中心）中與頁首地段開頭最長相符者，沒有相符為 `null`；`段`、`小段` 由其餘部分切出。
  `建物坐落地號`、`共同擔保地號`、`共同擔保建號` 拆成 `{段小段, 編號}`。`層次` 與 `層次面積`、`附屬建物用途` 與 `面積` 依原文順序一對一配對。
  `其他登記事項` 每一項拆成 `{類別, 標籤, 內容}`：`類別` 是原文開頭括號內的分類（如「限制登記事項」，舊版沒有則 `null`），`標籤` 是冒號前的項目名（如「重測前」）。
- **`其他欄位`**：固定鍵以外的標籤（如尚未定鍵的地上權專屬欄位），或拆不開的原文（如層次與面積筆數對不上、讀不出數字），
  以 `{部, 標籤, 值, 原因}` 原樣附上，一個不丟；拆不開時對應的固定鍵為 `null` 或 `[]`。5 份實測電子謄本此欄皆為空。
- **`部附註`**：各部沒有標籤的說明句。所有權部、他項權利部是陣列，說明句屬於整個部，所以放在外層。

`判定`（**只輸出「有／未見／無法判定」，不輸出「無」**）：
| 鍵 | 有 | 未見 | 無法判定 |
|---|---|---|---|
| `他項權利` | 他項權利部有筆 | 申請範圍含他項權利部（全部、地號全部、建號全部、標示部及他項權利部、他項權利個人全部），讀到標示部而他項權利部沒有筆 | 其他申請範圍（如「所有權個人全部」不印他項權利部） |
| `限制登記` | 比對到內政部代碼表：其他登記事項類別「（限制登記事項）」、項目「預告登記請求權人」，或所有權部登記原因為查封、假扣押、假處分、破產登記、禁止處分、預告登記、未登記建物查封 | 沒比對到，申請範圍為全部／地號全部／建號全部，讀到標示部與所有權部，且標示部（含共有部分）與所有權部每一項其他登記事項都印有類別 | 其餘；特別是有任何一項其他登記事項沒有類別（舊版版面）時 |
| `信託` | 比對到：項目「委託人」、「信託財產，信託內容詳信託專簿」，或登記原因為信託、信託歸屬、信託取得 | 同上 | 同上 |

- 比對一律**整串相等**（代碼表見 `backend/app/lib/multi_type_ocr/transcript_records_codes.json`，記有資料集網址與版本）：
  「塗銷查封」，以及代碼表中含「預告登記」「信託」字樣的限制性註記句（如「…三年內不得辦理移轉或預告登記…」），都**不會**被判成有。
- 判定表各列要求的部沒讀到（例如掃描件 OCR 讀不出結構）時不給「未見」，回「無法判定」。
- **「未見」只表示這份謄本上沒印**，不等於法律上沒有；要確認請向地政事務所查證。舊版謄本以自由文字記載的查封不會被判成有，只會讓結果變成「無法判定」。

與其他欄位的關係：25 個單值欄位、6 種清單、`transcripts` 照舊、取值不變；`transcript_records` 由 `transcripts` 建構，只是換成固定的鍵。
限制：
- 只在 `document_type=transcript` 時出現；建構失敗時只省略此鍵，`transcripts` 與其餘回應不受影響。
- 多位所有權人、多筆抵押、附屬建物、管理者、限制登記、信託、第一類謄本：實測 5 份電子謄本皆無，只以合成樣本驗證。
- 地上權、農育權、不動產役權、典權的專屬欄位尚未定鍵（官方無樣本），出現時放進 `其他欄位`。車位不另拆（同 §3.1.2）。
- 掃描／拍照謄本也會出現此鍵，但 `transcripts` 靠行首縮排分層級，OCR 文字的縮排還原不穩：模擬照片 15 頁實測全文讀對率 6.2%（`docs/testing/transcript-photo-fullparse-eval-20261109.md`）。不帶參數時照片、掃描謄本請讀 25 個單值欄位與清單；新串接請帶 `transcript_format=v2`（§3.1.4）。

**jgb2 一般物件建物謄本表單（31 欄）對照**——只讀 25 個單值欄位時有 10 欄「需人工」；其中 8 欄在清單（§3.1.1）就有，另 2 欄謄本上沒有：
| jgb2 表單欄位 | 只讀 25 欄 | 建議讀法 | `transcript_records` 對應（清單沒有時） | 帶 v2 讀法（§3.1.4） |
|---|---|---|---|---|
| 段、小段、地號 | 自動 | 25 欄 | `謄本.段`、`謄本.小段`、`標示部.建物坐落地號[0].編號` | `謄本.段`、`謄本.小段`（照片不補）、`標示部.建物坐落地號[0].編號` |
| 稅籍編號 | 需人工 | 需人工（謄本上沒有） | — | — |
| 專有部分 建號、權利範圍、共計面積 | 自動 | 25 欄 | `謄本.編號`、`所有權部[].權利範圍`、`標示部.總面積` | 同左 |
| 主建物 層次1／面積1、用途、共計面積 | 自動 | 25 欄 | `標示部.層次[0]`、`標示部.主要用途`、`標示部.總面積` | 同左 |
| 主建物 層次2–4／面積（6 欄） | 需人工 | `floors` 中 `transcript_id`＝本戶建號的第 2～4 筆：`level`、`area` | `標示部.層次[1..3]` | 同左 |
| 附屬建物 用途／面積 | 自動（只一組） | `sub_buildings[]`：`usage`、`area` | `標示部.附屬建物[]` | 同左 |
| 共有部分 建號 | 自動 | 25 欄 `shared_build_number`；多筆讀 `shared_parts[].build_number` | `標示部.共有部分[].建號` | 同左 |
| 共有部分 權利範圍 | 需人工 | `shared_parts[].rights_scope` | `標示部.共有部分[].權利範圍` | 同左 |
| 共有部分 持分面積 | 需人工 | `shared_parts[].share_area`（DocuMind 已算好，＝`area`×持分，四捨五入兩位） | 自行推算 `共有部分[].面積 × 權利範圍` | 自行推算 `共有部分[].面積 × 權利範圍`（帶參數沒有 `share_area`） |
| 他項權利 有無／種類 | 偵測到才帶「有」 | `transcript_records`：`判定.他項權利`＋`他項權利部[].權利種類` | 同左 | 同左 |
| 查封 | 偵測到關鍵字才帶 | `transcript_records`：`判定.限制登記` | 同左 | 同左 |
| 土地標的清冊 段／小段／地號／使用分區 | 自動，只 1 筆 | `transcript_records` 每張 `類型=土地` 的謄本一筆：`謄本.段`、`謄本.小段`、`謄本.編號`、`標示部.使用分區` | 同左 | 同左 |
| 土地標的 租賃面積 | 需人工 | 需人工（謄本上沒有） | — | — |

讀法：
- **不帶參數時，清單與 `transcript_records` 都有的值，先讀清單；清單沒有該筆才讀 `transcript_records`。** 帶 `transcript_format=v2` 時不回清單，照表的「帶 v2 讀法」一欄讀 `transcript_records`（照片的值已由清單補進，§3.1.4）。 清單用逐欄規則抽，不靠版面；`transcript_records` 由全文解析建構，靠行首縮排分層級。實測 5 份電子謄本兩者的值相同；照片、掃描謄本上全文解析幾乎讀不出這些值（§3.1.2 限制）。
- `floors` 只在各層面積加總等於總面積時才輸出，否則為 `[]`（§3.1.1）；這時再讀 `標示部.層次`。名稱沒配上時 `level` 為 `null`、`area` 照給。
- 清單讀不到回 `null`／`[]`、不猜，也不列入 `needs_confirmation`：讀不到的格照「需人工」處理。
- 實測（2026-11-09，本機探查、非線上；`docs/testing/transcript-photo-fullparse-eval-20261109.md` §9）：5 份電子謄本的 7 個建物頁共 26 格，清單與全文都 26/26；同 7 頁的模擬照片（現行 OCR 文字），清單 9/26、全文 0/26，兩者錯值都是 0。照片上多數格仍要人工。

#### 3.1.4 帶參數格式 `transcript_format=v2`（2.9.0 起；**新串接用這個格式**）

本節與 §3.1.5 每句句末的方括號是依據：V2 編號是程式行為，各對應會實跑的單元測試（清單見 `.kiro/specs/transcript-records-converge/plan-s4.md` §2.5；V2-30～V2-32 與 2.10.0 改寫的 V2-07、V2-24～V2-26 見 `backend/tests/unit/test_transcript_v2_spec.py` 同名測試）；「實測」指向量測紀錄的章節；「政策」是規則編號（`.kiro/specs/transcript-records-converge/acceptance.md`）〔政策：R7〕。

##### 怎麼拿

- `POST /api/v1/analyze` 帶 `transcript_format=v2`、`document_type=transcript`（預設值）時，`document_fields` 的謄本部分改用本節格式〔V2-05〕〔V2-08〕
- 參數值只接受 `v2`；其他值（例：`v3`、空字串）回 400 `INVALID_TRANSCRIPT_FORMAT`；這個檢查在文件類型檢查之前，所以 `document_type=contract` 帶錯值也是 400〔V2-01〕
- `document_type` 不是 `transcript` 時帶 `v2` 不起作用，回應與不帶參數相同〔V2-02〕
- 批次端點 `/analyze/batch` 沒有這個參數，帶了不起作用〔V2-03〕
- 不帶參數時，回應與 2.8.1 相同（§3.1～§3.1.3）〔實測：docs/testing/transcript-v2-20261109.md#3. 電子 PDF 不受影響，不帶參數的回應不變（C5～C9）〕
- 新串接請帶這個參數；不帶參數的舊格式已公告棄用（§3.1.5）〔政策：R6〕

##### 形狀：每個值包成 `{value, position}`

- `document_fields.transcript_records` 每張謄本一筆，鍵與 §3.1.3 相同；每個不是 `null` 的值（字串、數字、布林，含空字串 `""`）換成 `{"value": 值, "position": 位置或 null}`，`null` 照舊是 `null`〔V2-08〕
- `判定`、`部是否印出` 兩個區塊不包，值照舊是字串與布林；`類型` 會包〔V2-08〕
- 包裝後的值只有 `value`、`position` 兩鍵，不附信心度或來源〔V2-27〕
- 逐鍵定義見 [`transcript_records_v2.schema.json`](transcript_records_v2.schema.json)，由 §3.1.3 的舊 schema 以固定規則衍生，單元測試鎖住兩檔同步；土地、建物、`類型` 為 `null` 三支互斥〔V2-23〕
- 與舊 schema 不同處：`標示部.層次[].層次`、`層次[].面積`、`附屬建物[].用途`、`附屬建物[].面積` 可為 `null`（補值時名稱沒配上，面積照補）〔政策：AM-1〕

```jsonc
"transcript_records": [                     // 數字為示意
  {
    "謄本": { "編號": { "value": "02080-000", "position": { "page": 1, "box": [0.62, 0.11, 0.71, 0.125], "unit": "ratio" } },
             "頁數": { "value": 2, "position": null }, … },
    "類型": { "value": "建物", "position": { "page": 1, "box": [0.3, 0.05, 0.6, 0.07], "unit": "ratio" } },
    "標示部": { "建物門牌": { "value": "長春路14之1號", "position": { … } }, "主要用途": null,
              "層次": [{ "層次": { "value": "一層", "position": { … } }, "面積": { "value": 96.51, "position": { … } } }], … },
    "所有權部": [{ "所有權人": { "value": "新華開發股份有限公司", "position": { … } }, … }],
    "判定": { "他項權利": "有", "限制登記": "未見", "信託": "未見" },        // 不包
    "部是否印出": { "標示部": true, "所有權部": true, "他項權利部": true }, // 不包
    …
  }
]
```

##### `position`：電子檔框到值，照片框到整行

- `page` 是第幾頁（從 1 起算）；`box` 是 `[x0, y0, x1, y1]`，以該頁寬、高的 0～1 比例表示，原點在左上；`unit` 固定是 `"ratio"`〔V2-17〕
- 畫框時乘上該頁圖片的寬、高即得像素座標（PDF 用該頁渲染後的寬高）〔V2-17〕
- **電子 PDF**（每一頁 `pages[].text_layer` 都是 `true`）：框到值本身的字〔V2-17〕；實測有位置的值 98.4% 框內文字與值相同〔實測：docs/testing/transcript-v2-20261109.md#4. 電子 PDF 位置框到值本身（C10）〕
- **照片與無文字層 PDF**：框到值所在的那一整行 OCR 文字，不是值本身；補進的值（見下方補值）也照樣找行；框超出頁面時夾在 0～1〔V2-19〕
- 同一個值的字出現在好幾行時挑一行給框，可能挑錯：先挑鍵名印在值前面、對上最多的行；清單裡第 k 次出現的同一個值取第 k 個符合的行；同一筆的其他欄位值也出現的行優先；只在該張謄本自己的頁裡找〔V2-20〕
- 照片的 `謄本.頁數` 也照樣找行，可能框到任一含那個數字的行，位置不代表頁數印在哪〔V2-28〕
- 只有部分頁有文字層的 PDF 不走電子定位；行框只從沒有文字層的頁找：值只印在有文字層的頁時 `position` 為 `null`，同樣的字也出現在無文字層頁時會框到那一行，不一定是值的出處〔V2-22〕
- 實測照片行框包含值中心 96.1%（15 頁）、樣本外 93.8%，多頁純影像 PDF 100% 與 97.4%，頁碼 0 錯；已知會框到別行的例子見該紀錄〔實測：docs/testing/transcript-v2-20261109.md#5. 照片位置框到值所在的那一行（C11）〕

##### `position` 為 `null` 的情形

- 電子 PDF：對不到值本身；`謄本.頁數`；某一頁對位不一致時該頁全部；重建的紀錄與回應不同或組裝失敗時整份全部〔V2-18〕
- 電子 PDF 補進的值（見下方補值）〔V2-16〕
- 照片與無文字層 PDF：找不到含該值的行；值是布林，或正規化後是空字串；圖片 EXIF 方向不是 1；頁文字與行框對不上；沒有行框（OCR 用到 Tesseract，或伺服器開了多引擎共識 `OCR_CONSENSUS_ENABLED`／`OCR_FUSION_METHOD=cross_check`）；組裝失敗〔V2-21〕
- `position` 為 `null` 只表示沒有框，不表示值錯〔V2-18〕〔V2-21〕

##### 補值：用同一份回應的規則欄位補空格

- 照片 OCR 讀不出結構時 `transcript_records` 大多是空的；帶參數時用同一份回應的 25 欄與清單（§3.1、§3.1.1）補進 `null` 格與空清單，不覆蓋已有的值〔V2-09〕
- 單值（建物的建物門牌、主要用途、主要建材、層數、總面積、建築完成日期；土地的面積、使用分區、使用地類別）、`謄本.編號`、`標示部.建物坐落地號` 與 `他項權利部`（只補一筆 `權利種類`）只在整份 `transcript_records` 只有 1 張時補〔V2-10〕
- `類型` 為 `null` 的張整張不補；整份 1 張時才由 `building_number`／`land_number` 推出 `類型`〔V2-11〕
- 清單（`層次`、`附屬建物`、`共有部分`、`所有權部`）只補屬於該張的筆：`transcript_id` 等於該張 `謄本.編號`，或沒有 `transcript_id` 且整份 1 張；`owners[].part` 要和類型相符（土地張只取 `land`、建物張只取 `building`）；目標陣列已有任何一筆就整組不補，不逐筆合併〔V2-12〕
- 鍵名以「日期」結尾的值要含年、月、日三段數字才補〔V2-13〕
- `類型` 已知而 `標示部` 為 `null`（謄本沒印標示部）時，回固定鍵的全空骨架（清單 `[]`、其餘 `null`），不限張數；有沒有印要看 `部是否印出.標示部`〔V2-14〕
- 補完後 `判定` 依補進的內容重算，可能和不帶參數不同；`部是否印出` 不隨補值改，所以補進 `所有權部`、`他項權利部` 的筆時它仍可能是 `false`〔V2-15〕
- 電子 PDF 也照同樣規則補〔V2-16〕
- `謄本.段`、`謄本.小段` 是 `null` 且整份 1 張時，從全文找第一行「鄉鎮市區名稱＋段（＋小段）＋地號或建號」切出來補；鄉鎮市區以全國名稱表比對（平鎮區、前鎮區、新市區也切得對；新竹市東區這類，段名不含區名），行首沒有鄉鎮市區名稱就不補；`謄本.段` 已有值時，`小段` 只取自同一段那一行。不讀 25 欄 `section`、`subsection`，兩者可能不同（25 欄遇到「鎮」「市」結尾的區名會切錯）〔V2-30〕
- 整份 1 張、清單補完後 `標示部.層次` 仍是 `[]` 時，用 `floor_level`、`floor_area` 補 1 筆；`所有權部` 仍是 `[]` 時，用 `owner` 與權利範圍補 1 筆（建物張取 `rights_scope`、土地張取 `land_rights_scope`），其餘鍵 `null`〔V2-31〕
- `共有部分` 由 `shared_parts` 補進時，每個車位（`parking[]`）在該筆 `其他登記事項` 加一項，`內容` 與電子謄本那行同格式：`含停車位編號2號,權利範圍:1000分之55`（`類別`、`標籤` 為 `null`）；編號或權利範圍沒有時省略該段，兩者都沒有就不加；電子 PDF 讀出的 `共有部分` 不動〔V2-32〕
- 照片補值：15 頁讀對從 73 格增加到 184 格，8 個錯值都與不帶參數時舊欄位的值相同；其中 2.10.0 新增 1 個（`謄本.段` 的 OCR 錯字，25 欄 `section` 是同一字）〔實測：docs/testing/transcript-v2-jgb-gaps-20261111.md#2. 本機：照片補值〕
- `enable_llm` 不帶時預設是 `true`〔V2-29〕
- `enable_llm=true` 時 25 欄可能含 LLM 補判的值，補進 `transcript_records` 的值也可能來自 LLM；這部分沒有驗〔實測：docs/testing/transcript-v2-20261109.md#7. 沒有驗的範圍〕

##### 帶參數時不回的舊格式

- `document_fields` 不含 25 個單值欄位、6 種清單（`owners`、`land_numbers`、`floors`、`sub_buildings`、`floor_area_checks`、`shared_parts`）與 `transcripts`〔V2-05〕
- 每頁 `pages[].structured_data` 只拿掉這 31 個鍵，其他鍵（例：`has_building_evidence`、`share_slots`、`validation_warnings`）照留〔V2-06〕
- `document_fields` 其他鍵（`field_confidences`、`needs_confirmation`、`extraction_confidence`、`llm_used_for_extraction`）與不帶參數相同〔V2-05〕
- 頂層 `needs_review` 與不帶參數相同，兩者都會建複核項目、回 `review_item_id`；複核佇列存的是未轉換的 `pages`（每頁仍有 25 欄與清單）與 `field_confidences`，與不帶參數相同〔V2-04〕
- `transcript_records` 是 `[]` 或不存在（全文一張謄本都沒解析出來，或建構失敗）時，有 `building_number` 就組 1 張建物張，沒有而有 `land_number` 就組 1 張土地張，再照「整份 1 張」的規則補；組出那張的 `部是否印出` 全為 `false`、`謄本.頁首附註` 為 `[]`。兩個號碼都沒有時 `transcript_records` 為 `[]`，回應沒有任何謄本值〔V2-07〕

##### 帶參數拿不到、不帶參數拿得到的值

| 不帶參數的值 | 帶參數為什麼拿不到 | 替代讀法 |
|---|---|---|
| `print_date`、`seizure_mark` | 補值不讀這 2 欄；照片讀不出結構時 `謄本.列印時間` 為 `null`，查封看 `判定.限制登記`（判法不同）〔V2-24〕 | 不帶參數讀 25 欄〔V2-24〕 |
| `section`、`subsection`（全文切不出段時） | 不讀這 2 欄，改從全文切；行首沒有鄉鎮市區名稱、或整份 2 張以上時 `謄本.段`、`謄本.小段` 仍是 `null`〔V2-30〕 | 不帶參數讀 25 欄（遇「鎮」「市」結尾的區名會切錯）〔V2-30〕 |
| `sub_building_usage`、`sub_building_area`、`shared_build_number`、`shared_area` | 不作補值來源，由 `sub_buildings`、`shared_parts` 清單補；清單沒輸出時拿不到〔V2-25〕 | 不帶參數讀 25 欄〔V2-25〕 |
| 第 2 筆以後的層次與所有權人（清單沒輸出時） | 單值只記第 1 筆，只補第 1 筆；整份 2 張以上時不補〔V2-31〕 | 不帶參數讀 25 欄（同樣只有第 1 筆）〔V2-31〕 |
| `shared_parts[].share_area`（持分面積、車位持分面積）、`parking_total`（車位總數）、`floor_area_checks` | DocuMind 算出的值，`transcript_records` 沒有對應鍵；車位編號與權利範圍寫進 `共有部分[].其他登記事項`（V2-32），鍵 `parking` 本身不回〔V2-26〕 | 持分面積自行以 `共有部分[].面積 × 權利範圍` 算；車位總數與面積核對要不帶參數〔V2-26〕 |
| 整份 2 張以上時的標示部單值、`謄本.編號`、`建物坐落地號`、`他項權利部` | 只在整份 1 張時補〔V2-10〕 | 不帶參數讀 25 欄（25 欄不分張）〔V2-10〕 |
| 清單裡對不到是哪一張的筆 | 不屬於該張就不補〔V2-12〕 | 不帶參數讀清單〔V2-12〕 |
| 全部謄本值（`transcript_records` 是 `[]` 或不存在，且 `building_number`、`land_number` 都沒有時） | 判不出建物或土地，不組〔V2-07〕 | 改用不帶參數〔V2-07〕 |

##### `needs_confirmation` 仍用 25 欄的英文鍵名

- 帶參數時 `field_confidences`、`needs_confirmation` 的鍵仍是 25 欄的英文鍵名；對應到 `transcript_records` 的位置與會不會補進如下表〔V2-05〕

| 25 欄鍵名 | `transcript_records` 位置 | 帶參數會不會補進 |
|---|---|---|
| `land_number` | 土地張 `謄本.編號`；建物張 `標示部.建物坐落地號[].編號` | 整份 1 張時補 `謄本.編號`，`建物坐落地號` 由 `land_numbers` 補〔V2-10〕 |
| `building_number` | 建物張 `謄本.編號` | 整份 1 張時補〔V2-10〕 |
| `area` | 土地張 `標示部.面積` | 整份 1 張時補〔V2-10〕 |
| `building_address`、`main_usage`、`main_material`、`total_floors`、`total_area`、`completion_date` | 建物張 `標示部.建物門牌`、`主要用途`、`主要建材`、`層數`、`總面積`、`建築完成日期` | 整份 1 張時補；日期要含年月日〔V2-10〕〔V2-13〕 |
| `land_use_zone`、`land_use_type` | 土地張 `標示部.使用分區`、`使用地類別` | 整份 1 張時補〔V2-10〕 |
| `other_right_type` | `他項權利部[0].權利種類` | 整份 1 張、他項權利部沒有筆時補一筆〔V2-10〕 |
| `owner`、`rights_scope`、`land_rights_scope` | `所有權部[0].所有權人`、建物張（純土地為土地張）`所有權部[].權利範圍`、土地張 `所有權部[].權利範圍` | 先由 `owners` 清單補；補完仍沒有筆、整份 1 張時，補 1 筆 `所有權人`＋權利範圍（建物張 `rights_scope`、土地張 `land_rights_scope`）〔V2-12〕〔V2-31〕 |
| `floor_level`、`floor_area` | `標示部.層次[0].層次`、`層次[0].面積` | 先由 `floors` 清單補；補完仍是 `[]`、整份 1 張時補 1 筆〔V2-12〕〔V2-31〕 |
| `sub_building_usage`、`sub_building_area` | `標示部.附屬建物[0].用途`、`附屬建物[0].面積` | 不由這 2 欄補，由 `sub_buildings` 清單補〔V2-25〕〔V2-12〕 |
| `shared_build_number`、`shared_area` | `標示部.共有部分[0].建號`、`共有部分[0].面積` | 不由這 2 欄補，由 `shared_parts` 清單補〔V2-25〕〔V2-12〕 |
| `section`、`subsection` | `謄本.段`、`謄本.小段` | 不讀這 2 欄；整份 1 張時改從全文切〔V2-24〕〔V2-30〕 |
| `print_date` | `謄本.列印時間`（到分；25 欄只到日） | 不補〔V2-24〕 |
| `seizure_mark` | 無對應鍵；查封看 `判定.限制登記` | 不補〔V2-24〕 |

##### 照片的值一律當待確認的草稿

- 照片的 `needs_confirmation` 抓不到 OCR 讀錯：實測照片補進的 7 個錯值，0 個列入 `needs_confirmation`，5 頁中 2 頁 `needs_review` 為 `false`〔實測：docs/testing/transcript-v2-20261109.md#6. 照片的 `needs_confirmation` 抓不到 OCR 讀錯；複核佇列不受參數影響〕
- 帶參數也不附信心度〔V2-27〕
- 照片、無文字層 PDF 的值一律當待確認的草稿；`position` 可用來在原圖上標出要人工確認的那一行〔實測：docs/testing/transcript-v2-20261109.md#6. 照片的 `needs_confirmation` 抓不到 OCR 讀錯；複核佇列不受參數影響〕
- 電子 PDF：實測 5 份帶參數的 `value` 還原後與不帶參數逐位元相同；這 5 份的標示部都有印，沒印時帶參數回全空骨架（見上方補值）〔實測：docs/testing/transcript-v2-20261109.md#3. 電子 PDF 不受影響，不帶參數的回應不變（C5～C9）〕

#### 3.1.5 舊格式棄用（只限 `document_type=transcript`）

- 下列五種舊格式自 2.9.0 起公告棄用〔政策：R6〕：
  1. 不帶參數時 `document_fields` 的 25 個單值欄位（§3.1）〔政策：R6〕
  2. 6 種清單（§3.1.1）〔政策：R6〕
  3. `transcripts`（§3.1.2）〔政策：R6〕
  4. 舊形狀的 `transcript_records`（§3.1.3）〔政策：R6〕
  5. `pages[].structured_data` 裡的 25 欄與清單〔政策：R6〕
- 下游請改帶 `transcript_format=v2`（§3.1.4）〔政策：R6〕
- 移除條件：AIChatbot 與 jgb2 都改帶參數、經 DocuMind 維護方確認後，另開一版把預設改成新格式並拿掉舊格式；目前沒有固定日期〔政策：R6〕
- 移除之前，不帶參數的回應維持不變〔政策：R6〕
- 其他文件類型不受影響〔V2-02〕

### 3.2 `contract` — 巢狀結構

```jsonc
{
  "contract_metadata": { "contract_number": null, "signing_date": null, "effective_date": null },
  "parties":           { "party_a": null, "party_b": null, "party_a_address": null, "party_b_address": null },
  "financial_terms":   { "contract_amount": null, "currency": null,
                         "payment_method": null, "payment_deadline": null },
  "extraction_confidence": 0.0,
  "llm_used_for_extraction": false
}
```

租約另有：`date_start`、`date_end`、`monthly_rent`、`deposit`、`rental_address`、`tenant_name`
（關鍵欄位）與 `tenant_id_number`、`tenant_phone`、`landlord_name`、`landlord_id_number`、
`landlord_phone`、`management_fee`、`parking_fee`、`payment_day`（次要欄位）。
系統以原文關鍵詞（租賃／承租人／押金…）判定是否為租約，不是靠有沒有抽到租賃欄位。

**值的形式（2026-10-14 起，commit `3d07e2e`）：** 合約欄位的值取自正規化後的文字，與謄本、帳單一致——
全形數字與標點變半形，帶框字（如 ㈲）還原成原字、不加括號。例如原文 `月租金：２５，０００元` 回 `25,000`，
`租期：２０２６年３月２７日至…` 的 `date_start` 回 `2026年3月27日`。下游若曾以全形比對合約值，請改為半形。
原本因全形逗號等讀不到的欄位現在讀得到，`extraction_confidence`、`needs_confirmation` 與是否進複核可能隨之改變。
`pages[].rule_postprocessed.text` 等原文欄位不受影響。

**直讀（影像與掃描 PDF，伺服器開啟 `contract` 直讀時）：** 回應鍵與上面相同（`contract_metadata`、`parties`、
`financial_terms`、有租賃欄位時的 `rental_terms`、`extraction_confidence`、`llm_used_for_extraction`），
另新增 `field_confidences`（鍵是上面的扁平欄位名，如 `party_a`、`monthly_rent`）與 `needs_confirmation`。
`llm_used_for_extraction` 在模型直讀成功時為 `true`、呼叫失敗時為 `false`（欄位全空、必要欄位全進 `needs_confirmation`）；`pages[].ocr_raw` 為 `null`。
是否為租約由模型判斷，通用合約不要求租賃欄位。多頁合約逐頁直讀、跨頁「只填補缺值」彙整，與 `document_fields` 一致。

### 3.3 `bill`

`amount`（金額）、`date`（日期）、`account_no`（戶號）。

**直讀（影像與掃描 PDF，伺服器開啟 `bill` 直讀時）：** 回應鍵與舊版完全相同
（`amount`、`date`、`account_no`、`field_confidences`、`needs_confirmation`、`extraction_confidence`、
`llm_used_for_extraction`：直讀成功 `true`、呼叫失敗 `false`），值是模型讀圖的結果；`pages[].ocr_raw` 為 `null`，
`pages[].llm_calls` 有 `stage: "direct_read"` 的紀錄。

### 3.3.1 `receipt` — 收據、發票（直讀）

```json
{
  "amount": "588",
  "date": "2026-10-12 14:35:20",
  "field_confidences": { "amount": 0.9, "date": 0.9 },
  "needs_confirmation": [],
  "extraction_confidence": 0.9
}
```

- 只回兩個欄位：`amount`（**整張單據的總計**，原始字串，不是單項明細金額）與 `date`（單據上印的日期，原樣回傳；
  沒有「日期」標籤的電子發票日期時間如 `2026-10-12 14:35:20`、民國年如 `115/10/12` 都讀得到）。不回商家、稅額、單號。
- **必要欄位是 `amount`、`date`，不含 `account_no`**（收據沒有戶號）。
- 模型分不出哪個數字是總計、或讀到的金額不是數字（`三千五`、夾帶文字）、日期解析不了時，該欄位信心度 `0.5`，
  並列入 `needs_confirmation`；`needs_review` 會是 `true`。讀不到的欄位值為 `null`、信心度 `0.0`。
- 模型呼叫失敗時不回錯誤，兩欄為 `null`、`needs_confirmation` 為 `["amount", "date"]`，失敗原因看 `pages[].llm_calls`。
- `pages[].ocr_raw` 為 `null`；多頁 PDF 逐頁讀、`document_fields` 跨頁補值。
- 讀不到的欄位在 `document_fields` 裡同樣是 `null`（鍵固定帶，見 §2）。

### 3.4 `repair_photo` — 影像理解，非 OCR

```json
{
  "defect_labels": ["漏水", "壁癌"],
  "damaged_items": ["水龍頭", "牆面"],
  "description": "牆面出現大面積水漬與剝落…",
  "confidence": 0.82
}
```

`damaged_items` 是照片裡**壞掉、損壞或有問題的物件**（字串陣列，照照片實際內容寫，不綁 JGB 的分類）；
`defect_labels` 是瑕疵標籤。兩者獨立，不保證一一對應。
四個鍵一律存在，`document_fields` 與 `pages[0].structured_data` 都一樣；看不出損壞時兩個陣列是 `[]`。

VLM 不可用或影像無法辨識時降級為 `{"defect_labels": [], "damaged_items": [], "description": "", "confidence": 0.0}`，
**不會回錯誤**，請以 `confidence` 判斷是否可用；失敗與否看 `pages[].llm_calls`。

### 3.5 `handover_photo` — 影像理解 + 詞彙白名單

```json
{
  "space": "living_room",
  "space_label": "客廳/餐廳",
  "furniture": [
    { "key": "sofa", "label": "沙發", "confidence": 0.9 },
    { "key": "table", "label": "桌子", "confidence": 0.9 }
  ],
  "appliance": [
    { "key": "TV", "label": "電視", "confidence": 0.86 }
  ],
  "description": "客廳配置三人座沙發與電視…",
  "confidence": 0.86,
  "dropped": ["裝飾畫"],
  "field_confidences": { "sofa": 0.9, "table": 0.9, "TV": 0.86 }
}
```

- `furniture`、`appliance` 是物件陣列：`key`（詞彙表的品項 key）、`label`（中文名）、`confidence`（該品項信心度）。
  分到哪一類以詞彙表為準，不看模型放在哪個陣列；同一品項只出現一次。
- `field_confidences` 的鍵是品項 key，值同該品項的 `confidence`；沒有品項時為 `{}`。
- `dropped` 是字串陣列（模型講了、但對不上詞彙表的原文）。

**輸出經過白名單過濾：只回傳詞彙表裡的 7 個空間 key 與 94 個品項 key。**
模型講「電冰箱」「單人床架」這類自由文字，對不上就丟棄並記進 `dropped`。

設計取捨是 **寧可漏報，不可誤報** —— 憑空多出一個品項比少一個更難被發現，
而點交清單是有法律效力的文件。所以你拿到的品項一定對得上清單，
但**不保證涵蓋照片裡的所有東西**。

`dropped` 不是給終端使用者看的，是給維護者看的：同一個詞反覆出現代表詞彙表該補。
8 個鍵一律存在，`document_fields` 同樣帶這些鍵（見 §2）。空房或影像模糊時 `furniture`、`appliance` 為 `[]`、`confidence` 偏低（`space` 可能仍有值）。
模型呼叫失敗或回應無法解析時降級為
`{"space": null, "space_label": "", "furniture": [], "appliance": [], "description": "", "confidence": 0.0, "dropped": [], "field_confidences": {}}`，
**不會回錯誤**，請以 `confidence` 判斷是否可用；失敗與否看 `pages[].llm_calls`。

---

## 4. 錯誤格式

所有錯誤統一為：

```json
{ "detail": "檔案大小超過限制：20MB", "error_code": "FILE_TOO_LARGE" }
```

| `error_code` | HTTP | 觸發條件 |
|---|---|---|
| `UNSUPPORTED_FILE_TYPE` | 400 | 副檔名不在 pdf/jpg/jpeg/png |
| `UNSUPPORTED_DOCUMENT_TYPE` | 400 | `document_type` 未指定或無對應處理器 |
| `INCOMPATIBLE_FILE_TYPE` | 400 | 格式與型別不相容（例：`repair_photo` 傳 PDF） |
| `FILE_TOO_LARGE` | 413 | 檔案 > 20 MB |
| `PROCESSING_ERROR` | 500 | 處理過程例外，訊息不外洩細節 |
| `INVALID_TRANSCRIPT_FORMAT` | 400 | `transcript_format` 帶了 `v2` 以外的值（含空字串）；`document_type` 不是謄本也一樣（§3.1.4） |
| `NO_FILES` | 400 | 批次端點沒帶任何檔案 |
| `TOO_MANY_FILES` | 400 | 批次端點超過 20 個檔案 |

單頁處理失敗不會讓整份請求失敗：該頁會回 `{"page_number": n, "error": "頁面處理失敗: ...", "ocr_raw": {"text": "", "confidence": 0.0}, ...}`，其餘頁面照常回傳。**請逐頁檢查 `error` 鍵。**

---

## 5. 輔助端點

### `POST /api/v1/classify` — 型別建議

上傳檔案（`file`），回傳建議型別供使用者確認。**永遠回 200**，判不出來時為 null：

```json
{ "suggested_document_type": "transcript", "confidence": 0.87 }
```

可能回 `transcript`、`contract`、`receipt` 或 `null`。`receipt` 依收據本身的字樣判斷（統一發票、電子發票、發票號碼、收據、證明聯）；
帳單目前不會被建議（回 `null`）。回 `receipt` 不代表伺服器已開放 `receipt` 類型，能不能送 `/analyze` 見 §2.2。

### `GET /api/v1/usage` — 累計用量

```json
{ "total_calls": 156, "total_pages": 423, "total_llm_cost": 8.46, "period": "all_time" }
```

### 人工複核佇列（`needs_review = true` 後的流程）

| 方法 | 路徑 | 說明 |
|---|---|---|
| GET | `/api/v1/review/queue?status=pending` | 列出佇列（`pending` / `in_review` / `completed`） |
| GET | `/api/v1/review/{item_id}` | 取單筆（含原文與欄位）；不存在 → 404 `NOT_FOUND` |
| POST | `/api/v1/review/{item_id}/claim` | body `{"reviewer": "..."}`；已被認領 → 409 `ALREADY_CLAIMED` |
| POST | `/api/v1/review/{item_id}/submit` | body `{"reviewer": "...", "corrected_fields": {...}}` → `{"status":"completed","diff":{...}}`；非認領者 → 403 `FORBIDDEN` |
| POST | `/api/v1/review/{item_id}/release` | body `{"reviewer": "..."}` → 回 `pending` |

校正提交會沉澱為 few-shot 樣本，後續同型別文件的抽取會越用越準。

---

## 6. 速度與準確率取決於「有沒有文字層」，不是文件類型

**直讀（Qwen 直接讀圖，不跑本機 OCR）。** 伺服器設定 `DIRECT_READ_DOCUMENT_TYPES`（JSON 陣列，可列
`receipt`、`bill`、`contract`；**預設是空**）列入的類型，影像與沒有文字層的 PDF 不再跑本機 OCR，
而是整頁（長邊 2000 像素、JPEG）交視覺模型讀欄位，供應商依伺服器的分流設定。
有文字層的帳單、合約 PDF 維持下面的文字層路徑；收據的 PDF（有或沒有文字層）一律直讀。
沒列入的帳單、合約照舊走本機 OCR 再補欄位。謄本不能直讀，維持本機 OCR。
直讀的回應 `pages[].ocr_raw` 為 `null`，`pages[].llm_calls` 的 `stage` 為 `direct_read`；
不論 `enable_llm` 為何都會呼叫模型。

| 來源 | 文字層 | 4 頁耗時 | 字元錯誤率 |
|---|---|---|---|
| 網路申領電子謄本、Word 轉出的 PDF | ✅ | **0.6 秒** | **0.15%** |
| 掃描件、手機拍照 | ❌ | 約 85 秒 | 14.5% |

**系統自動分流，呼叫端不需要指定。** 含文字層時直接讀取產生該 PDF 的原始字串
（不是辨識結果），略過 OCR；判定門檻 20 字，避免掃描件夾帶的少量浮水印文字造成誤判。
該頁回應會多一個 `text_layer: true`，且 `ocr_raw.confidence` 為 `1.0`；走 OCR 時此鍵不存在。

### 已量測的準確率（2026-09-03）

| 處理路徑 | 字元錯誤率 |
|---|---|
| PDF 文字層 | **0.15%** |
| PaddleOCR（強制走 OCR） | 14.5% |
| Tesseract（強制走 OCR） | 38.2% |

正確答案取自該 PDF 的內嵌文字層。⚠️ **樣本為 1 份 4 頁電子謄本，不是統計結果**；
掃描件上的成績未經量測，且大概率更差。

---

## 7. 串接前必須知道的五件事

**1. 沒有認證。** 端口對外開放，任何人都能呼叫。上線前要加。

**2. 掃描件很慢，而且是同步的。** 實測 4 頁掃描謄本約 **85 秒**（約 21 秒/頁）；
走 OCR + LLM 的完整路徑實測約 151 秒。**同步呼叫請把 timeout 設到 300 秒以上**，
或改為非同步流程。含文字層的 PDF 不受此限（0.6 秒）。

**3. 併發已有閘門，但仍是逐一處理。** OCR 由行程層級的 Semaphore 序列化
（`OCR_MAX_CONCURRENT=1`），第二個請求會**排隊**而不是把容器打掛
（單頁 OCR 峰值實測 1141–1778 MB，容器可用約 1695 MB）。
排隊期間呼叫端仍在等待，故高併發場景請自行控制送件節奏。

**4. 電子謄本的欄位可以直接採用；掃描／拍照件的欄位要當成待確認的草稿。**
2026-10-14～15 以 5 份真實電子謄本（共 11 張）線上實測：
25 個單值欄位逐欄對照原文的 3 份，值與欄位皆正確、皆不需人工；
`transcript_records` 11 張全部符合 Schema，640 個原文值 0 不符。
⚠️ 樣本為 5 份，不是統計結果；沒見過的版面仍可能讀錯，請保留人工抽查。
掃描件、手機拍照走 OCR，讀錯或缺的欄位大多來自 OCR 把字讀壞或讀漏
（例如遮罩星號被吃掉、日期少數字、「土」讀成「上」、「加強」讀成簡體「加强」、整行沒讀到）；
少數是 AI 補值（`enable_llm=true`）取到別處的值。
**OCR 讀錯的值會帶著高信心度送出、不一定觸發 `needs_review`**（見 §8）。
2026-10-20 曾把 5 份真實電子謄本（17 頁）轉成模擬掃描和模擬拍照的圖片送線上：25 欄正確率約 97%，
錯的 23 欄中有 16 欄沒進 `needs_confirmation`（[`docs/testing/bedrock-vlm-eval-20261023.md`](../testing/bedrock-vlm-eval-20261023.md) §3.3）。
2026-11-09 另一批較難的模擬照片（15 頁，含手機斜拍），本機 OCR、只用規則：25 欄 77%（掃描 98%、俯拍 83%、斜拍 58%），非線上（`docs/testing/transcript-photo-fullparse-eval-20261109.md` §9）。
掃描件的 `transcripts`／`transcript_records` 讀不出結構（同批實測 6.2%），不帶參數時請以 25 個單值欄位與 §3.1.1 清單為準；新串接請帶 `transcript_format=v2`（§3.1.4），照片的值會補進 `transcript_records`。
帶參數同樣適用本點：照片的值是待確認的草稿，`needs_confirmation` 抓不到 OCR 讀錯；帶參數另附 `position`，可在原圖上標出要人工確認的那一行（§3.1.4）。
實測明細見 [`docs/testing/transcript-online-acceptance.md`](../testing/transcript-online-acceptance.md) §3。

**5. `enable_llm=true` 不等於每頁都花錢。** 只有謄本、文字層 PDF 與沒開直讀的帳單、合約受 `enable_llm` 影響：OCR 信心度 < 85% 的頁面才呼叫 LLM。
直讀類（收據、帳單、合約的影像與掃描 PDF，伺服器開啟直讀時）與照片類（修繕、點交）每頁都呼叫視覺模型，不論 `enable_llm`。
謄本與文字層 PDF 的用量看 `stats.llm_pages_used` 與 `stats.estimated_cost`；直讀類與照片類不計入這兩欄，實際呼叫次數看每頁的 `llm_calls`。

---

## 8. 已知的辨識風險：錯值會帶著高信心度

2026-09-03 實測一份 4 頁謄本時觀察到：

```json
"building_number": "過溝段00004-000",
"area": "0555-0000",          ← 這是地號，被填進面積欄位
"field_confidences": { "area": 0.8 }
```

**錯值帶著 0.8 的高信心度。** 字串合法、型別正確，規則檢查與信心度都攔不住，
該頁只因整體信心度 0.320 才被拖進複核。這是生成式模型的典型失效模式
（語法合法但數值錯誤）。

**已於 2026-09-03 加上型別檢查**：數值欄位出現識別碼形狀（`\d+-\d+`）、
日期欄位無法解析、識別碼欄位不含數字時，信心度壓到 0.3（低於門檻）並列入
`needs_confirmation`，同時在 `structured_data.validation_warnings` 記錄原因。

但該檢查只涵蓋可規則化的型別錯誤，**擋不住所有幻覺**。
採用任何欄位前仍應自行做業務層驗證。

**謄本欄位的位置錯誤已於 2026-09-23～10-01 修正**：抵押權的設定權利範圍、公設的建號與權利範圍、
重測前的舊地段，以前會以 0.9 信心度被當成本戶的值，現在不再取到（見 §3.1 取值範圍表）。
目前已知仍會讀錯、但尚未修正的兩種版面列在
[`docs/testing/transcript-online-acceptance.md`](../testing/transcript-online-acceptance.md) §4。

---

## 9. 其他要知道的

- **回應不含原始圖檔。** `original_image` 已移除以縮小回應；需要原圖請用 `file_url`。
  ⚠️ 2026-10-01 實測線上的 `file_url` 一律為 `null`（線上 S3 設定問題，檔案沒有上傳成功），目前拿不到原圖。
- **`bill`、`receipt`、`repair_photo`、`handover_photo` 尚無充足真實測資**，
  回傳結構未經端到端驗證，串接前請先實測。
- **另有一條舊上傳路徑** `POST /api/v1/documents/upload`（上限 10 MB，
  未列入 OpenAPI schema）。它走的是**另一條 OCR 路徑**（`pytesseract` 單引擎），
  行為與本文件描述的不同。**新系統請一律用 `/analyze`。**
