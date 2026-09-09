# DocuMind OCR 對接規格（給外部系統開發者）

> 版本 1.0.0 ／ 對應程式碼 commit `f8c91b6`
> 唯一需要串的端點是 `POST /api/v1/analyze`；其餘為輔助。

---

## 1. 連線資訊

| 項目 | 值 |
|---|---|
| Base URL | `http://<host>:8000/api/v1` |
| 互動式文件 | `http://<host>:8000/api/docs` |
| OpenAPI JSON | `http://<host>:8000/api/openapi.json` |
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

舊型別別名會自動轉換：`lease` / `lease_contract` → `contract`；`repair_quote` → `bill`。
傳入 `id_card`、`unknown` 等無對應型別 → `400 UNSUPPORTED_DOCUMENT_TYPE`。

### 2.3 呼叫範例

```bash
# 謄本，含 LLM 校正
curl -X POST "http://<host>:8000/api/v1/analyze" \
  -F "file=@謄本.jpg" \
  -F "document_type=transcript" \
  -F "enable_llm=true"

# 純 OCR，不花 LLM 成本
curl -X POST "http://<host>:8000/api/v1/analyze" \
  -F "file=@帳單.png" \
  -F "document_type=bill" \
  -F "enable_llm=false"

# 合約 + 問答
curl -X POST "http://<host>:8000/api/v1/analyze" \
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
      "consensus":          null
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

**多頁文件務必讀 `document_fields`。** 謄本的地號在第 1 頁、建號在第 3 頁是常態，
單頁的 `structured_data` 必然殘缺；`document_fields` 是「只填補缺值」合併後的完整結果，
且 `needs_confirmation` 與 `extraction_confidence` 已依全文重算。

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

## 6. 對接時要知道的行為

1. **含文字層的 PDF 不走 OCR。** 網路申領的電子謄本直接抽文字層，實測 4 頁 <1 秒且逐字精確；
   走 OCR 則 85 秒、字元錯誤率 14.5%。判定門檻 20 字，掃描件會自動落回 OCR。
2. **回應不含原始圖檔。** `original_image` 已被移除以縮小回應；需要原圖請用 `file_url`。
3. **`enable_llm=true` 不等於每頁都花錢。** 只有 OCR 信心度 < 85% 的頁面才呼叫 LLM，
   實際用量看 `stats.llm_pages_used` 與 `stats.estimated_cost`。
4. **耗時。** 4 頁謄本走 OCR + LLM 實測約 151 秒（頁面併發後 LLM 段降至約 25 秒）。
   請把 client timeout 設在 **180 秒以上**，或改為非同步輪詢架構。
5. **另有一條舊上傳路徑** `POST /api/v1/documents/upload`（上限 10 MB，未列入 OpenAPI schema）。
   新系統請一律用 `/analyze`。
