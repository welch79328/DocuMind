# DocuMind OCR 對接規格（給外部系統開發者）

> 版本 2.0.0 ／ 2026-09-10
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

上傳 PDF 或圖片，一次完成 OCR → 文字校正 → 結構化欄位抽取（可選 AI 問答）。

### 2.1 請求（multipart/form-data）

| 欄位 | 型別 | 必填 | 預設 | 說明 |
|---|---|---|---|---|
| `file` | file | ✅ | — | `.pdf` / `.jpg` / `.jpeg` / `.png`，上限 **20 MB** |
| `document_type` | string | ✗ | `transcript` | 見 2.2 |
| `enable_llm` | bool | ✗ | `true` | 啟用 LLM 文字校正（OCR 信心度 < 85% 才實際觸發，約 $0.02/頁） |
| `question` | string | ✗ | `null` | 帶入時額外回傳 `answer`，基於本次 OCR 結果作答 |

### 2.2 `document_type` 可用值

| 值 | 文件 | 可接受格式 |
|---|---|---|
| `transcript` | 建物／土地謄本 | pdf, jpg, jpeg, png |
| `contract` | 合約（含租約） | pdf, jpg, jpeg, png |
| `bill` | 帳單（水電／管理費等） | pdf, jpg, jpeg, png |
| `repair_photo` | 修繕現場照片（VLM 影像理解，非 OCR） | **僅** jpg, jpeg, png |
| `handover_photo` | 點交現場照片（VLM 影像理解 + 詞彙白名單） | **僅** jpg, jpeg, png |

舊型別別名會自動轉換：`lease` / `lease_contract` → `contract`；`repair_quote` → `bill`。
傳入 `id_card`、`unknown` 等無對應型別 → `400 UNSUPPORTED_DOCUMENT_TYPE`。

### 2.3 呼叫範例

```bash
# 謄本，含 LLM 校正
curl -X POST "http://54.248.201.66:8085/api/v1/analyze" \
  -F "file=@謄本.jpg" \
  -F "document_type=transcript" \
  -F "enable_llm=true"

# 純 OCR，不花 LLM 成本
curl -X POST "http://54.248.201.66:8085/api/v1/analyze" \
  -F "file=@帳單.png" \
  -F "document_type=bill" \
  -F "enable_llm=false"

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
      "text_layer":         true   // 見下方說明;走 OCR 時此鍵不存在
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

**多頁文件務必讀 `document_fields`。** 謄本的地號在第 1 頁、建號在第 3 頁是常態，
單頁的 `structured_data` 必然殘缺；`document_fields` 是「只填補缺值」合併後的完整結果，
且 `needs_confirmation` 與 `extraction_confidence` 已依全文重算。

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

四種型別共通會附帶：
`field_confidences`（逐欄位 0.0–1.0）、`needs_confirmation`（信心不足、建議人工確認的欄位名陣列）、
`extraction_confidence`（必要欄位平均）、`llm_used_for_extraction`（bool）。

### 3.1 `transcript` — 扁平結構，23 欄

| key | 中文 | 必要欄位* |
|---|---|:--:|
| `land_number` | 地號 | ✅ |
| `building_number` | 建號 | ✅ |
| `area` | 面積 | ✅ |
| `rights_scope` | 權利範圍 | ✅ |
| `owner` | 所有權人 | ✅ |
| `section` | 段 | ✅ |
| `subsection` | 小段 | |
| `building_address` | 建物門牌 | ✅ |
| `main_usage` | 主要用途 | ✅ |
| `main_material` | 主要建材 | ✅ |
| `total_floors` | 層數 | |
| `floor_level` | 層次 | ✅ |
| `floor_area` | 層次面積 | ✅ |
| `total_area` | 總面積 | ✅ |
| `completion_date` | 建築完成日期 | |
| `sub_building_usage` | 附屬建物用途 | |
| `sub_building_area` | 附屬建物面積 | |
| `shared_build_number` | 共有部分建號 | |
| `shared_area` | 共有部分面積 | |
| `other_right_type` | 他項權利種類 | |
| `seizure_mark` | 查封或限制登記 | |
| `land_use_zone` | 使用分區 | ✅ |
| `land_use_type` | 使用地類別 | |

\* 只有「必要欄位」列入信心度計分。非必要欄位是**本來就可能不存在**
（透天沒有共有部分、無貸款沒有他項權利、`seizure_mark` 沒有才是好事），
抽不到不代表辨識失敗，下游不要當成錯誤。

### 3.2 `contract` — 巢狀結構

```jsonc
{
  "contract_metadata": { "contract_number": null, "signing_date": null, "effective_date": null },
  "parties":           { "party_a": null, "party_b": null, "party_a_address": null, "party_b_address": null },
  "financial_terms":   { "contract_amount": null, "currency": null,
                         "payment_method": null, "payment_deadline": null },
  "extraction_confidence": 0.0
}
```

租約另有：`date_start`、`date_end`、`monthly_rent`、`deposit`、`rental_address`、`tenant_name`
（關鍵欄位）與 `tenant_id_number`、`tenant_phone`、`landlord_name`、`landlord_id_number`、
`landlord_phone`、`management_fee`、`parking_fee`、`payment_day`（次要欄位）。
系統以原文關鍵詞（租賃／承租人／押金…）判定是否為租約，不是靠有沒有抽到租賃欄位。

### 3.3 `bill`

`amount`（金額）、`date`（日期）、`account_no`（戶號）。

### 3.4 `repair_photo` — 影像理解，非 OCR

```json
{ "defect_labels": ["漏水", "壁癌"], "description": "牆面出現大面積水漬與剝落…", "confidence": 0.82 }
```

VLM 不可用或影像無法辨識時降級為 `{"defect_labels": [], "description": "", "confidence": 0.0}`，
**不會回錯誤**，請以 `confidence` 判斷是否可用。

### 3.5 `handover_photo` — 影像理解 + 詞彙白名單

```json
{
  "space": "living_room",
  "space_label": "客廳",
  "furniture": ["sofa", "coffee_table"],
  "appliance": ["tv", "air_conditioner"],
  "description": "客廳配置三人座沙發與電視…",
  "confidence": 0.86,
  "dropped": ["裝飾畫"],
  "field_confidences": {}
}
```

**輸出經過白名單過濾：只回傳詞彙表裡的 7 個空間 key 與 94 個品項 key。**
模型講「電冰箱」「單人床架」這類自由文字，對不上就丟棄並記進 `dropped`。

設計取捨是 **寧可漏報，不可誤報** —— 憑空多出一個品項比少一個更難被發現，
而點交清單是有法律效力的文件。所以你拿到的品項一定對得上清單，
但**不保證涵蓋照片裡的所有東西**。

`dropped` 不是給終端使用者看的，是給維護者看的：同一個詞反覆出現代表詞彙表該補。
影像模糊或空房時四個欄位回空值（不是 `null`），`confidence` 為 `0.0`。

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

**4. `needs_review: true` 目前幾乎必然出現，而且原因不是辨識。**
2026-09-03 實測：文字層路徑給出 **99.85% 正確**的文字，
地號、建號、面積、權利範圍**仍然一個都沒抽到**，只抽到 owner。
**瓶頸在欄位抽取，不在文字辨識。**
請把結構化欄位當成「待人工確認的草稿」，不是可信輸出；
`ocr_raw.text` 的可信度則遠高於欄位。

**5. `enable_llm=true` 不等於每頁都花錢。** 只有 OCR 信心度 < 85% 的頁面才呼叫 LLM。
實際用量看 `stats.llm_pages_used` 與 `stats.estimated_cost`。
2026-09-09 實測全域平均約 **$0.0050/頁**（只有約 28% 的頁面真的觸發 LLM）。

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

---

## 9. 其他要知道的

- **回應不含原始圖檔。** `original_image` 已移除以縮小回應；需要原圖請用 `file_url`。
- **`bill`、`repair_photo`、`handover_photo` 尚無充足真實測資**，
  回傳結構未經端到端驗證，串接前請先實測。
- **另有一條舊上傳路徑** `POST /api/v1/documents/upload`（上限 10 MB，
  未列入 OpenAPI schema）。它走的是**另一條 OCR 路徑**（`pytesseract` 單引擎），
  行為與本文件描述的不同。**新系統請一律用 `/analyze`。**
