# AI Document Intelligence Demo - API 接口規格

## 1. API 總覽

### 1.1 Base URL

```
開發環境: http://localhost:8000/api/v1
生產環境: https://api.ai-doc-demo.com/api/v1
```

### 1.2 FastAPI 特性

本 API 使用 **FastAPI** 構建，具備以下特性：

- ✅ **自動生成文檔** - Swagger UI: `/api/docs`
- ✅ **自動數據驗證** - 使用 Pydantic 自動驗證請求
- ✅ **類型安全** - Python Type Hints 確保類型正確
- ✅ **異步支持** - 原生 async/await 支持
- ✅ **高效能** - 基於 Starlette + Uvicorn

### 1.3 認證方式

**MVP 階段：** 暫不實作認證（Demo 用途）

**未來版本：** Bearer Token / JWT

### 1.4 通用請求標頭

```http
Content-Type: application/json
Accept: application/json
```

### 1.5 通用回應格式

**FastAPI 直接返回數據（Pydantic Model）：**

成功回應示例：
```json
{
  "id": "uuid",
  "file_name": "document.pdf",
  "status": "completed",
  ...
}
```

**錯誤回應（FastAPI 標準格式）：**
```json
{
  "detail": "錯誤訊息"
}
```

或驗證錯誤：
```json
{
  "detail": [
    {
      "loc": ["body", "field_name"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### 1.5 HTTP 狀態碼

| 狀態碼 | 說明 |
|--------|------|
| 200 | 成功 |
| 201 | 建立成功 |
| 400 | 請求參數錯誤 |
| 404 | 資源不存在 |
| 413 | 檔案過大 |
| 425 | 資源尚未準備好 |
| 500 | 伺服器錯誤 |

---

## 2. API 端點列表

### 2.1 文件管理

| 端點 | 方法 | 功能 | 優先級 |
|------|------|------|--------|
| `/documents/upload` | POST | 上傳文件 | P0 |
| `/documents/:id/process` | POST | 處理文件 | P0 |
| `/documents/:id` | GET | 取得文件詳情 | P0 |
| `/documents` | GET | 列出所有文件 | P0 |
| `/documents/:id` | DELETE | 刪除文件 | P1 |

### 2.2 AI 功能

| 端點 | 方法 | 功能 | 優先級 |
|------|------|------|--------|
| `/documents/:id/chat` | POST | AI 問答 | P1 |
| `/documents/:id/create-record` | POST | 建立系統記錄 | P2 |

### 2.3 記錄管理

| 端點 | 方法 | 功能 | 優先級 |
|------|------|------|--------|
| `/records/:id` | GET | 取得記錄詳情 | P2 |
| `/records` | GET | 列出所有記錄 | P2 |

---

## 3. API 詳細規格

### 3.1 POST /api/documents/upload

**功能：** 上傳文件

**優先級：** P0

**請求格式：** `multipart/form-data`

**請求參數：**

| 參數名 | 類型 | 必填 | 說明 |
|--------|------|------|------|
| `file` | File | ✅ | 上傳的檔案 |

**支援格式：**
- `application/pdf`
- `image/jpeg`
- `image/png`

**檔案限制：**
- 最大 10MB

**請求範例（cURL）：**
```bash
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F "file=@/path/to/contract.pdf"
```

**Python 範例（使用 httpx）：**
```python
import httpx

with open("contract.pdf", "rb") as f:
    files = {"file": ("contract.pdf", f, "application/pdf")}
    response = httpx.post("http://localhost:8000/api/v1/documents/upload", files=files)
    document = response.json()
    print(document["id"])
```

**成功回應（201）：**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "file_name": "contract.pdf",
  "file_size": 1234567,
  "mime_type": "application/pdf",
  "status": "uploaded",
  "file_url": "https://s3.amazonaws.com/bucket/550e8400-e29b-41d4-a716-446655440000.pdf",
  "created_at": "2026-03-17T10:30:00Z",
  "updated_at": "2026-03-17T10:30:00Z"
}
```

**錯誤回應：**

**400 - 檔案格式不支援**
```json
{
  "detail": "不支援的檔案格式，請上傳 PDF、JPG 或 PNG 檔案"
}
```

**413 - 檔案過大**
```json
{
  "detail": "檔案大小超過 10MB 限制"
}
```

**500 - 上傳失敗**
```json
{
  "detail": "檔案上傳失敗：S3 upload error"
}
```

---

### 3.2 POST /api/documents/:id/process

**功能：** 觸發文件 AI 處理流程（OCR + 分類 + 抽取）

**優先級：** P0

**請求格式：** `application/json`

**路徑參數：**

| 參數名 | 類型 | 說明 |
|--------|------|------|
| `id` | UUID | 文件 ID |

**請求範例（cURL）：**
```bash
curl -X POST http://localhost:8000/api/v1/documents/550e8400-e29b-41d4-a716-446655440000/process
```

**Python 範例：**
```python
import httpx

document_id = "550e8400-e29b-41d4-a716-446655440000"
response = httpx.post(f"http://localhost:8000/api/v1/documents/{document_id}/process")
result = response.json()
print(result["status"])  # "processing"
```

**成功回應（200）：**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "message": "文件處理已開始，請稍後查詢結果"
}
```

**錯誤回應：**

**404 - 文件不存在**
```json
{
  "detail": "找不到指定的文件"
}
```

**400 - 文件已處理**
```json
{
  "detail": "此文件已處理完成"
}
```

---

### 3.3 GET /api/documents/:id

**功能：** 取得文件詳情及 AI 處理結果

**優先級：** P0

**路徑參數：**

| 參數名 | 類型 | 說明 |
|--------|------|------|
| `id` | UUID | 文件 ID |

**請求範例（cURL）：**
```bash
curl -X GET http://localhost:8000/api/v1/documents/550e8400-e29b-41d4-a716-446655440000
```

**Python 範例：**
```python
import httpx

document_id = "550e8400-e29b-41d4-a716-446655440000"
response = httpx.get(f"http://localhost:8000/api/v1/documents/{document_id}")
document = response.json()

# 檢查狀態
if document["status"] == "completed":
    print(f"文件類型: {document['ai_result']['doc_type']}")
    print(f"摘要: {document['ai_result']['summary']}")
```

**成功回應（200） - 處理完成：**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "file_name": "租約.pdf",
  "file_url": "https://s3.amazonaws.com/...",
  "mime_type": "application/pdf",
  "file_size": 1234567,
  "status": "completed",
  "created_at": "2026-03-17T10:30:00Z",
  "updated_at": "2026-03-17T10:31:00Z",
  "ocr_result": {
    "id": "ocr-result-uuid",
    "document_id": "550e8400-e29b-41d4-a716-446655440000",
    "raw_text": "租賃契約書...",
    "page_count": 2,
    "ocr_confidence": 95.5,
    "ocr_service": "textract",
    "created_at": "2026-03-17T10:30:15Z"
  },
  "ai_result": {
    "id": "ai-result-uuid",
    "document_id": "550e8400-e29b-41d4-a716-446655440000",
    "doc_type": "lease_contract",
    "confidence": 98.5,
    "summary": "承租人王小明承租台北市中山區XX路房屋，月租金25,000元，押金50,000元，租期自2026/01/01至2026/12/31。",
    "extracted_data": {
      "landlord_name": "張三",
      "tenant_name": "王小明",
      "address": "台北市中山區XX路XX號",
      "rent": 25000,
      "deposit": 50000,
      "lease_start": "2026-01-01",
      "lease_end": "2026-12-31",
      "contract_date": "2025-12-15"
    },
    "risks": [
      {
        "type": "missing_field",
        "field": "landlord_phone",
        "severity": "warning",
        "message": "缺少出租人聯絡電話"
      }
    ],
    "ai_model": "gpt-4o",
    "processing_time_ms": 8500,
    "created_at": "2026-03-17T10:30:45Z"
  }
}
```

**處理中狀態（200）：**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "file_name": "租約.pdf",
  "file_url": "https://s3.amazonaws.com/...",
  "mime_type": "application/pdf",
  "file_size": 1234567,
  "status": "processing",
  "created_at": "2026-03-17T10:30:00Z",
  "updated_at": "2026-03-17T10:30:30Z",
  "ocr_result": null,
  "ai_result": null
}
```

**處理失敗狀態（200）：**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "file_name": "租約.pdf",
  "file_url": "https://s3.amazonaws.com/...",
  "mime_type": "application/pdf",
  "file_size": 1234567,
  "status": "failed",
  "error_message": "OCR 處理失敗：檔案損毀",
  "created_at": "2026-03-17T10:30:00Z",
  "updated_at": "2026-03-17T10:30:15Z",
  "ocr_result": null,
  "ai_result": null
}
```

**錯誤回應：**

**404 - 文件不存在**
```json
{
  "detail": "找不到指定的文件"
}
```

---

### 3.4 GET /api/documents

**功能：** 列出所有文件（支援分頁）

**優先級：** P0

**查詢參數：**

| 參數名 | 類型 | 必填 | 預設值 | 說明 |
|--------|------|------|--------|------|
| `page` | Number | ❌ | 1 | 頁碼 |
| `limit` | Number | ❌ | 20 | 每頁筆數 |
| `status` | String | ❌ | - | 過濾狀態 |
| `docType` | String | ❌ | - | 過濾文件類型 |

**請求範例（cURL）：**
```bash
curl -X GET "http://localhost:8000/api/v1/documents?page=1&limit=10&status=completed"
```

**Python 範例：**
```python
import httpx

params = {"page": 1, "limit": 10, "status": "completed"}
response = httpx.get("http://localhost:8000/api/v1/documents", params=params)
data = response.json()

for doc in data["documents"]:
    print(f"{doc['file_name']}: {doc['status']}")
```

**成功回應（200）：**
```json
{
  "documents": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "file_name": "租約.pdf",
      "mime_type": "application/pdf",
      "status": "completed",
      "doc_type": "lease_contract",
      "created_at": "2026-03-17T10:30:00Z"
    },
    {
      "id": "660e8400-e29b-41d4-a716-446655440001",
      "file_name": "報價單.jpg",
      "mime_type": "image/jpeg",
      "status": "completed",
      "doc_type": "repair_quote",
      "created_at": "2026-03-17T09:15:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 10,
    "total": 25,
    "total_pages": 3
  }
}
```

---

### 3.5 POST /api/documents/:id/chat

**功能：** 針對特定文件進行 AI 問答

**優先級：** P1

**請求格式：** `application/json`

**路徑參數：**

| 參數名 | 類型 | 說明 |
|--------|------|------|
| `id` | UUID | 文件 ID |

**請求 Body：**

| 參數名 | 類型 | 必填 | 說明 |
|--------|------|------|------|
| `question` | String | ✅ | 使用者問題 |

**請求範例（cURL）：**
```bash
curl -X POST http://localhost:8000/api/v1/documents/550e8400-e29b-41d4-a716-446655440000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "這份租約的租金是多少？"
  }'
```

**Python 範例：**
```python
import httpx

document_id = "550e8400-e29b-41d4-a716-446655440000"
payload = {"question": "這份租約的租金是多少？"}
response = httpx.post(
    f"http://localhost:8000/api/v1/documents/{document_id}/chat",
    json=payload
)
result = response.json()
print(result["answer"])
```

**成功回應（200）：**
```json
{
  "id": "chat-log-uuid",
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "question": "這份租約的租金是多少？",
  "answer": "根據此租賃契約，月租金為 25,000 元。",
  "evidence": {
    "field": "rent",
    "value": 25000
  },
  "response_time_ms": 1200,
  "created_at": "2026-03-17T11:00:00Z"
}
```

**無法回答範例（200）：**
```json
{
  "id": "chat-log-uuid",
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "question": "出租人的手機號碼是多少？",
  "answer": "抱歉，此文件中未找到出租人的手機號碼資訊。",
  "evidence": null,
  "response_time_ms": 800,
  "created_at": "2026-03-17T11:00:00Z"
}
```

**錯誤回應：**

**404 - 文件不存在**
```json
{
  "detail": "找不到指定的文件"
}
```

**425 - 文件尚未處理完成**
```json
{
  "detail": "文件尚在處理中，請稍後再試"
}
```

**400 - 問題為空（Pydantic 驗證錯誤）**
```json
{
  "detail": [
    {
      "loc": ["body", "question"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

---

### 3.6 POST /api/documents/:id/create-record

**功能：** 從文件一鍵建立系統記錄

**優先級：** P2

**請求格式：** `application/json`

**路徑參數：**

| 參數名 | 類型 | 說明 |
|--------|------|------|
| `id` | UUID | 文件 ID |

**請求 Body（可選）：**

| 參數名 | 類型 | 必填 | 說明 |
|--------|------|------|------|
| `confirmedData` | Object | ❌ | 使用者確認/修正後的欄位 |

**請求範例（cURL）：**
```bash
curl -X POST http://localhost:8000/api/v1/documents/550e8400-e29b-41d4-a716-446655440000/create-record \
  -H "Content-Type: application/json" \
  -d '{
    "confirmed_data": {
      "rent": 26000
    }
  }'
```

**Python 範例：**
```python
import httpx

document_id = "550e8400-e29b-41d4-a716-446655440000"
payload = {
    "confirmed_data": {
        "rent": 26000
    }
}
response = httpx.post(
    f"http://localhost:8000/api/v1/documents/{document_id}/create-record",
    json=payload
)
record = response.json()
print(f"記錄 ID: {record['id']}")
```

**成功回應（201）：**
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440002",
  "record_type": "lease",
  "source_document_id": "550e8400-e29b-41d4-a716-446655440000",
  "payload": {
    "landlord_name": "張三",
    "tenant_name": "王小明",
    "address": "台北市中山區XX路XX號",
    "rent": 26000,
    "deposit": 50000,
    "lease_start": "2026-01-01",
    "lease_end": "2026-12-31",
    "status": "active"
  },
  "created_at": "2026-03-17T10:35:00Z"
}
```

**錯誤回應：**

**404 - 文件不存在**
```json
{
  "detail": "找不到指定的文件"
}
```

**425 - 文件尚未處理完成**
```json
{
  "detail": "文件尚未處理完成，無法建立記錄"
}
```

**400 - 文件類型不支援**
```json
{
  "detail": "此文件類型不支援建立記錄"
}
```

---

### 3.7 GET /api/records/:id

**功能：** 取得建立的記錄詳情

**優先級：** P2

**路徑參數：**

| 參數名 | 類型 | 說明 |
|--------|------|------|
| `id` | UUID | 記錄 ID |

**請求範例（cURL）：**
```bash
curl -X GET http://localhost:8000/api/v1/records/770e8400-e29b-41d4-a716-446655440002
```

**Python 範例：**
```python
import httpx

record_id = "770e8400-e29b-41d4-a716-446655440002"
response = httpx.get(f"http://localhost:8000/api/v1/records/{record_id}")
record = response.json()
print(f"記錄類型: {record['record_type']}")
```

**成功回應（200）：**
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440002",
  "record_type": "lease",
  "source_document": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "file_name": "租約.pdf"
  },
  "payload": {
    "landlord_name": "張三",
    "tenant_name": "王小明",
    "address": "台北市中山區XX路XX號",
    "rent": 26000,
    "deposit": 50000,
    "lease_start": "2026-01-01",
    "lease_end": "2026-12-31",
    "status": "active"
  },
  "created_at": "2026-03-17T10:35:00Z"
}
```

**錯誤回應：**

**404 - 記錄不存在**
```json
{
  "detail": "找不到指定的記錄"
}
```

---

### 3.8 DELETE /api/documents/:id

**功能：** 刪除文件（包含相關資料）

**優先級：** P1

**路徑參數：**

| 參數名 | 類型 | 說明 |
|--------|------|------|
| `id` | UUID | 文件 ID |

**請求範例（cURL）：**
```bash
curl -X DELETE http://localhost:8000/api/v1/documents/550e8400-e29b-41d4-a716-446655440000
```

**Python 範例：**
```python
import httpx

document_id = "550e8400-e29b-41d4-a716-446655440000"
response = httpx.delete(f"http://localhost:8000/api/v1/documents/{document_id}")
result = response.json()
print(result["message"])
```

**成功回應（200）：**
```json
{
  "message": "文件已成功刪除",
  "deleted_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**錯誤回應：**

**404 - 文件不存在**
```json
{
  "detail": "找不到指定的文件"
}
```

---

## 4. 錯誤代碼總覽

| 錯誤代碼 | HTTP 狀態碼 | 說明 |
|---------|------------|------|
| `UNSUPPORTED_FILE_TYPE` | 400 | 檔案格式不支援 |
| `FILE_TOO_LARGE` | 413 | 檔案過大 |
| `UPLOAD_FAILED` | 500 | 上傳失敗 |
| `DOCUMENT_NOT_FOUND` | 404 | 文件不存在 |
| `DOCUMENT_NOT_READY` | 425 | 文件尚未準備好 |
| `ALREADY_PROCESSED` | 400 | 文件已處理 |
| `INVALID_QUESTION` | 400 | 問題無效 |
| `UNSUPPORTED_RECORD_TYPE` | 400 | 記錄類型不支援 |
| `RECORD_NOT_FOUND` | 404 | 記錄不存在 |
| `OCR_FAILED` | 500 | OCR 處理失敗 |
| `AI_FAILED` | 500 | AI 處理失敗 |
| `INTERNAL_ERROR` | 500 | 內部錯誤 |

---

## 5. Rate Limiting

**MVP 階段：**
- 每個 IP 每分鐘最多 60 個請求
- 上傳端點每分鐘最多 10 個請求

**超過限制回應（429）：**
```json
{
  "detail": "請求過於頻繁，請稍後再試",
  "retry_after": 60
}
```

**FastAPI 實作方式：**
```python
from fastapi import FastAPI
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.post("/api/v1/documents/upload")
@limiter.limit("10/minute")
async def upload_document():
    pass
```

---

## 6. WebHook（未來擴展）

**功能：** 文件處理完成後主動通知前端

**端點：** 由前端提供

**事件類型：**
- `document.processing` - 處理開始
- `document.completed` - 處理完成
- `document.failed` - 處理失敗

**Payload 範例：**
```json
{
  "event": "document.completed",
  "data": {
    "documentId": "550e8400-e29b-41d4-a716-446655440000",
    "status": "completed",
    "timestamp": "2026-03-17T10:31:00Z"
  }
}
```

---

## 7. API 測試範例（Postman Collection）

```json
{
  "info": {
    "name": "AI Doc Demo API",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "item": [
    {
      "name": "Upload Document",
      "request": {
        "method": "POST",
        "url": "{{baseUrl}}/documents/upload",
        "body": {
          "mode": "formdata",
          "formdata": [
            {
              "key": "file",
              "type": "file",
              "src": "/path/to/file.pdf"
            }
          ]
        }
      }
    },
    {
      "name": "Process Document",
      "request": {
        "method": "POST",
        "url": "{{baseUrl}}/documents/{{documentId}}/process"
      }
    },
    {
      "name": "Get Document",
      "request": {
        "method": "GET",
        "url": "{{baseUrl}}/documents/{{documentId}}"
      }
    },
    {
      "name": "Chat with Document",
      "request": {
        "method": "POST",
        "url": "{{baseUrl}}/documents/{{documentId}}/chat",
        "header": [
          {
            "key": "Content-Type",
            "value": "application/json"
          }
        ],
        "body": {
          "mode": "raw",
          "raw": "{\n  \"question\": \"這份租約的租金是多少？\"\n}"
        }
      }
    }
  ],
  "variable": [
    {
      "key": "baseUrl",
      "value": "http://localhost:8000/api/v1"
    },
    {
      "key": "documentId",
      "value": ""
    }
  ]
}
```

---

## 8. API 實作檢查清單

### 8.1 基礎功能（P0）

- [ ] POST /documents/upload
- [ ] POST /documents/:id/process
- [ ] GET /documents/:id
- [ ] GET /documents
- [ ] 檔案格式驗證
- [ ] 檔案大小驗證
- [ ] 錯誤處理

### 8.2 AI 功能（P1）

- [ ] POST /documents/:id/chat
- [ ] AI 回應格式化
- [ ] 問答歷史記錄

### 8.3 進階功能（P2）

- [ ] POST /documents/:id/create-record
- [ ] GET /records/:id
- [ ] DELETE /documents/:id
- [ ] 風險檢測

---

**文檔版本**: v1.0
**最後更新**: 2026-03-17
**負責人**: API Team
