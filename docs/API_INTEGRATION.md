# DocuMind 文件辨識 API 串接文件

> 對象:要串接 DocuMind 辨識能力的外部系統
> 最後更新:2026-09-03(所有數字皆為當日於線上環境實測)
> 對應 commit:`51f630d`

---

## 基本資訊

```
Base URL    http://54.248.201.66:8085
認證        無(目前未啟用)
互動文件    http://54.248.201.66:8085/docs
```

---

## POST /api/v1/analyze

上傳文件,回傳 OCR 文字與結構化欄位。

### ⚡ 處理速度取決於 PDF 有沒有文字層,不是文件類型

| 來源 | 文字層 | 4 頁耗時 | 字元錯誤率 |
|---|---|---|---|
| **網路申領電子謄本、Word 轉出的 PDF** | ✅ | **0.6 秒** | **0.15%** |
| 掃描件、手機拍照 | ❌ | 約 85 秒 | 14.5% |

**系統自動分流,呼叫端不需要指定。** 含文字層時直接讀取原始字串(那就是產生
該 PDF 的文字,不是辨識結果),略過 OCR;純掃描件才走 OCR。

判定門檻為 20 字,避免掃描件夾帶的少量浮水印文字造成誤判。

### 請求

`multipart/form-data`

| 參數 | 型別 | 必填 | 預設 | 說明 |
|---|---|---|---|---|
| `file` | file | ✅ | — | PDF / JPG / JPEG / PNG,**上限 20 MB** |
| `document_type` | string | — | `transcript` | `transcript` 謄本 / `contract` 合約 / `bill` 帳單 / `repair_photo` 修繕圖 |
| `enable_llm` | boolean | — | `true` | 啟用 LLM 校正(OCR 信心度 < 0.85 時才實際觸發) |
| `question` | string | — | `null` | 針對文件提問,結果放在回應的 `answer` |

⚠️ **`document_type` 不填會當成謄本處理。** 上傳合約而忘了帶參數不會報錯,
只會抽不到欄位——`/api/v1/classify` 可先取得建議值。

### 範例

```bash
curl -X POST http://54.248.201.66:8085/api/v1/analyze \
  -F "file=@建物土地謄本.pdf" \
  -F "document_type=transcript" \
  -F "enable_llm=true"
```

### 回應 200

```json
{
  "file_name": "建物土地謄本.pdf",
  "file_url": null,
  "document_type": "transcript",
  "total_pages": 4,
  "pages": [
    {
      "page_number": 1,
      "ocr_raw":            { "text": "...", "confidence": 0.691 },
      "rule_postprocessed": { "text": "...", "stats": {} },
      "llm_postprocessed":  { "text": "...", "stats": {}, "used": true },
      "structured_data": {
        "land_number": "竹田鄉過溝段0555-0000地號",
        "building_number": null,
        "area": "3,406.98",
        "rights_scope": "全部",
        "owner": "林順員",
        "field_confidences": { "land_number": 0.8, "area": 0.9, "owner": 0.9 },
        "needs_confirmation": ["building_number"],
        "extraction_confidence": 0.700
      },
      "field_confidences": {},
      "consensus": null,
      "text_layer": true
    }
  ],
  "answer": null,
  "stats": {
    "total_time_ms": 150861,
    "total_pages": 4,
    "llm_pages_used": 4,
    "estimated_cost": 0.1112
  },
  "needs_review": true,
  "review_item_id": "98563520-43ad-43cb-a4ac-d04eb901f436",
  "field_confidences": {}
}
```

### 欄位說明

| 欄位 | 說明 |
|---|---|
| `pages[].ocr_raw.confidence` | OCR 引擎自評,0–1 |
| `pages[].llm_postprocessed` | **LLM 未觸發時為 `null`**,不是空物件 |
| `pages[].structured_data` | **依 `document_type` 而異**,謄本與合約的鍵不同 |
| `structured_data.extraction_confidence` | 該頁欄位抽取的整體信心度 |
| `structured_data.needs_confirmation` | 抽不到或不確定的欄位名清單 |
| **`needs_review`** | **`true` 代表該文件已進人工複核佇列,結果不應直接採用** |
| `review_item_id` | 複核項目 id,可用於後續查詢 |
| `stats.estimated_cost` | 該次請求的 LLM 費用(美元) |
| `pages[].text_layer` | **`true` 表示該頁直接讀自 PDF 文字層,未經 OCR**——文字為精確值(`ocr_raw.confidence` 為 1.0);走 OCR 時此欄不存在 |

### 各文件類型的 `structured_data`

**`transcript`(謄本)**

```
land_number · building_number · area · rights_scope · owner
```

**`contract`(合約)**

```
contract_metadata { contract_number, signing_date, effective_date }
parties           { party_a, party_b, party_a_address, party_b_address }
financial_terms   { contract_amount, currency, payment_method, payment_deadline }
```

`bill` 與 `repair_photo` 的處理器已註冊,但**尚無真實測資與端到端測試**,
回傳結構未經驗證,串接前請先實測。

### 錯誤

| HTTP | `error_code` | 觸發條件 |
|---|---|---|
| 400 | `UNSUPPORTED_FILE_TYPE` | 副檔名不是 pdf/jpg/jpeg/png |
| 400 | `UNSUPPORTED_DOCUMENT_TYPE` | `document_type` 不在四種之內 |
| 400 | `INCOMPATIBLE_FILE_TYPE` | 檔案格式與文件類型不相容 |
| 413 | `FILE_TOO_LARGE` | 超過 20 MB |
| 500 | `PROCESSING_ERROR` | 處理失敗 |

```json
{ "detail": "...", "error_code": "UNSUPPORTED_FILE_TYPE" }
```

---

## 其他端點

| 端點 | 用途 |
|---|---|
| `POST /api/v1/classify` | 上傳檔案,回傳建議的 `document_type` |
| `GET /api/v1/usage` | 用量與成本查詢 |
| `GET /api/v1/review` | 人工複核佇列 |
| `GET /api/v1/evaluation` | 準確率評估 |

`/api/v1/documents`、`/api/v1/chat`、`/api/v1/ocr` 標記為 `include_in_schema=False`,
不進 OpenAPI 文件,**不建議新系統串接**——`/documents` 走的是另一條 OCR 路徑
(`pytesseract` 單引擎),與本文件描述的行為不同。

---

## 串接前必須知道的四件事

**1. 沒有認證。** 端口對外開放,任何人都能呼叫。上線前要加。

**2. 掃描件很慢,而且是同步的。** 實測 4 頁掃描謄本約 **85 秒**(約 21 秒/頁)。
**同步 HTTP 呼叫請把 timeout 設到 300 秒以上**,或改為非同步流程。
含文字層的 PDF 不受此限(0.6 秒)。

**3. 併發已有閘門,但仍是逐一處理。** OCR 由行程層級的 Semaphore 序列化
(`OCR_MAX_CONCURRENT=1`),第二個請求會**排隊**而不是把容器打掛
(單頁 OCR 峰值實測 1141–1778 MB,容器可用約 1695 MB)。
排隊期間呼叫端仍在等待,故高併發場景請自行控制送件節奏。

**4. `needs_review: true` 目前幾乎必然出現,而且原因不是辨識。**
2026-09-03 實測:文字層路徑給出 **99.85% 正確**的文字,
地號、建號、面積、權利範圍**仍然一個都沒抽到**,只抽到 owner。
**瓶頸在欄位抽取,不在文字辨識。**
串接端應把結構化欄位當成「待人工確認的草稿」,不是可信輸出;
`ocr_raw.text` 的可信度則遠高於欄位。

---

## 已知的辨識風險

2026-09-03 實測一份 4 頁謄本時觀察到:

```json
"building_number": "過溝段00004-000",
"area": "0555-0000",          ← 這是地號,被填進面積欄位
"field_confidences": { "area": 0.8 }
```

**錯值帶著 0.8 的高信心度。** 字串合法、型別正確,規則檢查與信心度都攔不住,
該頁只因整體信心度 0.320 才被拖進複核。

這是生成式模型的典型失效模式(語法合法但數值錯誤)。

**已於 2026-09-03 加上型別檢查**:數值欄位出現識別碼形狀(`\d+-\d+`)、
日期欄位無法解析、識別碼欄位不含數字時,信心度壓到 0.3(低於門檻)並列入
`needs_confirmation`,同時在 `validation_warnings` 記錄原因。

但該檢查只涵蓋可規則化的型別錯誤,**擋不住所有幻覺**。
串接端在採用任何欄位前仍應自行做業務層驗證。

### 已量測的準確率(2026-09-03,單一份 4 頁電子謄本)

| 處理路徑 | 字元錯誤率 |
|---|---|
| PDF 文字層 | **0.15%** |
| PaddleOCR(強制走 OCR) | 14.5% |
| Tesseract(強制走 OCR) | 38.2% |

正確答案取自該 PDF 的內嵌文字層。⚠️ **樣本為 1 份文件,不是統計結果**;
掃描件上的成績未經量測,且大概率更差。
