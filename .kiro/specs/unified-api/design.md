# unified-api - 技術設計文件

## 概述

### 設計目標
將現有的多步驟文件處理流程封裝為單一 `POST /api/v1/analyze` 端點，重用現有的 OCR 處理管線與 S3 儲存服務，對外提供簡潔的 API 介面。

### 設計原則
1. **重用優先**: 最大程度重用現有模組（ProcessorFactory、StorageService），不重寫邏輯
2. **向後相容**: 現有端點（`/ocr/test`、`/documents/*`、`/chat/*`）保持不變
3. **Facade 模式**: 新端點作為門面，封裝內部多步驟流程
4. **型別安全**: 所有介面使用 Pydantic model 定義，回應格式強型別
5. **最小 DB 依賴**: P0 階段不建立 Document 記錄，僅上傳 S3 + 即時回傳結果

### 架構決策摘要
1. **不建立 Document DB 記錄** — 即時處理模式，原始檔案存 S3 即可（詳見 research.md 決策 1）
2. **回應不含 original_image** — 節省頻寬，原始檔案透過 CDN URL 存取（詳見 research.md 決策 2）
3. **問答功能直接呼叫 ai_service** — 繞過 chat_service 避免不必要的 DB 依賴
4. **用量統計用獨立輕量表** — 與現有 Document 系統解耦

---

## 架構模式與邊界劃分

### 選定模式
**Facade + Pipeline 模式**: 新端點作為 Facade，內部按管道順序執行：驗證 → S3 上傳 → OCR 處理 → 問答（可選）→ 用量記錄 → 回傳結果

### 模組邊界圖

```
外部使用者
    │
    ▼
┌─────────────────────────────────────────┐
│  POST /api/v1/analyze                   │  ← API 層 (analyze.py)
│  ├─ 檔案驗證                            │
│  ├─ 參數解析                            │
│  └─ 回應組裝                            │
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│  AnalyzeService                         │  ← Service 層 (analyze_service.py)
│  ├─ upload_to_s3()                      │
│  ├─ process_ocr()                       │
│  ├─ answer_question() (可選)            │
│  └─ record_usage()                      │
└──┬──────┬──────────┬──────────┬─────────┘
   │      │          │          │
   ▼      ▼          ▼          ▼
┌──────┐┌──────────┐┌────────┐┌──────────┐
│S3    ││Processor ││AI      ││Usage     │
│Svc   ││Factory   ││Service ││Model     │
└──────┘└──────────┘└────────┘└──────────┘
 (既有)   (既有)      (既有)    (新增)
```

### 邊界劃分理由
- **API 層** (`analyze.py`): 參數驗證、檔案格式檢查、HTTP 錯誤處理、Swagger 文檔
- **Service 層** (`analyze_service.py`): 業務流程編排，協調各模組呼叫順序
- **Library 層**: 重用既有模組，不修改其介面

---

## 技術棧與對齊

### 核心技術選擇

| 技術領域 | 選擇 | 版本 | 理由 |
|---------|------|------|------|
| 語言 | Python | 3.11+ | 專案標準 |
| 框架 | FastAPI | 0.115+ | 專案標準 |
| 驗證 | Pydantic | 2.0+ | 專案標準 |
| 儲存 | boto3 (S3) | 既有 | 已整合完成 |
| OCR | Tesseract | 既有 | 透過 ProcessorFactory 呼叫 |
| LLM | OpenAI GPT-4o | 既有 | 透過 LLMService 呼叫 |

### 外部依賴

| 依賴 | 用途 | 風險評估 |
|------|------|---------|
| AWS S3 | 檔案持久化儲存 | 低 — 已在 .env 設定完成 |
| CloudFront CDN | 檔案公開存取 | 低 — 已設定 |
| OpenAI API | LLM 文字校正與問答 | 中 — 依賴外部服務 |

### 與現有系統對齊
- 遵循既有的 `api/v1/` 版本化路由結構
- 重用 `ProcessorFactory` 工廠模式
- 重用 `StorageService` 統一儲存介面
- 遵循既有的 Pydantic Schema 命名慣例（`*Response`）

---

## 元件與介面契約

### 元件 1: AnalyzeRouter (API 層)

**職責**: HTTP 請求處理、參數驗證、Swagger 文檔、錯誤回應

**公開介面**:
```python
@router.post("/analyze", response_model=AnalyzeResponse, status_code=200)
async def analyze_document(
    file: UploadFile = File(..., description="PDF 或圖片檔案"),
    document_type: Literal["transcript", "contract"] = Query(
        default="transcript",
        description="文件類型"
    ),
    enable_llm: bool = Query(
        default=True,
        description="是否啟用 LLM 文字校正"
    ),
    question: Optional[str] = Query(
        default=None,
        description="針對文件的問題（選填）"
    )
) -> AnalyzeResponse:
```

**對應需求**: 需求 1, 需求 4, 需求 5, 需求 8

---

### 元件 2: AnalyzeService (Service 層)

**職責**: 業務流程編排，協調 S3 上傳、OCR 處理、問答、用量記錄

**公開介面**:
```python
class AnalyzeService:
    async def analyze(
        self,
        file_contents: bytes,
        filename: str,
        document_type: str,
        enable_llm: bool,
        question: Optional[str] = None
    ) -> AnalyzeResult:
        """
        執行完整的文件分析流程

        Returns:
            AnalyzeResult 包含 file_url, pages, structured_data, answer, stats
        """
```

**依賴**:
- `StorageService` — S3 上傳
- `ProcessorFactory` — OCR 處理器
- `ai_service.answer_question()` — 問答（可選）

**對應需求**: 需求 1, 需求 2, 需求 3, 需求 6

---

### 元件 3: AnalyzeResponse (回應型別)

**職責**: 定義統一的 API 回應格式

**型別定義**:
```python
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class OcrPageResult(BaseModel):
    """單頁 OCR 結果"""
    page_number: int
    ocr_raw: OcrRawOutput
    rule_postprocessed: RulePostprocessedOutput
    llm_postprocessed: Optional[LlmPostprocessedOutput] = None
    structured_data: Optional[Dict[str, Any]] = None

class OcrRawOutput(BaseModel):
    text: str
    confidence: float

class RulePostprocessedOutput(BaseModel):
    text: str
    stats: Dict[str, Any]

class LlmPostprocessedOutput(BaseModel):
    text: str
    stats: Dict[str, Any]
    used: bool

class ProcessingStats(BaseModel):
    """處理統計"""
    total_time_ms: int
    total_pages: int
    llm_pages_used: int
    estimated_cost: float

class AnalyzeResponse(BaseModel):
    """統一分析回應"""
    file_name: str
    file_url: Optional[str] = None  # S3 CDN URL，上傳失敗時為 null
    document_type: str
    total_pages: int
    pages: List[OcrPageResult]
    answer: Optional[str] = None  # AI 問答結果
    stats: ProcessingStats
```

**對應需求**: 需求 2, 需求 3

---

### 元件 4: ApiUsageLog (用量追蹤模型)

**職責**: 記錄每次 API 呼叫的用量資訊

**型別定義**:
```python
class ApiUsageLog(Base):
    __tablename__ = "api_usage_logs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    endpoint: Mapped[str] = mapped_column(String(100))
    document_type: Mapped[str] = mapped_column(String(50))
    total_pages: Mapped[int] = mapped_column(Integer)
    llm_used: Mapped[bool] = mapped_column(Boolean)
    llm_cost: Mapped[float] = mapped_column(Float, default=0.0)
    processing_time_ms: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
```

**索引策略**:
- `idx_usage_created_at`: 按時間查詢用量

**對應需求**: 需求 7

---

## 資料模型與流程

### 資料流程

**流程: 文件分析 (POST /api/v1/analyze)**

```
[使用者上傳檔案]
  │
  ▼
[1. 檔案驗證]
  ├─ 格式檢查 (PDF/JPG/JPEG/PNG)
  ├─ 大小檢查 (≤ 20MB)
  └─ 文件類型檢查 (transcript/contract)
  │
  ▼
[2. S3 上傳]
  ├─ 路徑: uploads/ocr_{type}/{uuid}.{ext}
  ├─ ACL: public-read
  └─ 回傳: CDN URL
  │
  ▼
[3. PDF 拆頁] (PDF 才需要)
  ├─ fitz 開啟 PDF
  ├─ 逐頁轉 300 DPI PNG bytes
  └─ 回傳: List[page_bytes]
  │
  ▼
[4. OCR 處理] (每頁)
  ├─ ProcessorFactory.get_processor(type)
  ├─ processor.process(page_bytes, ...)
  └─ 回傳: PageResult (不含 original_image)
  │
  ▼
[5. AI 問答] (可選，有 question 時)
  ├─ 組合 OCR 文字為 context
  ├─ ai_service.answer_question(question, context)
  └─ 回傳: answer string
  │
  ▼
[6. 用量記錄]
  ├─ 寫入 api_usage_logs 表
  └─ 記錄: endpoint, type, pages, llm, cost, time
  │
  ▼
[7. 組裝回應]
  └─ AnalyzeResponse
```

**錯誤處理**:
- 步驟 1 失敗: 回傳 400/413 + 繁中錯誤訊息
- 步驟 2 失敗: 繼續處理 OCR，`file_url` 設為 null，附帶警告
- 步驟 4 單頁失敗: 標記該頁錯誤，繼續處理其餘頁面
- 步驟 5 失敗: `answer` 設為 null，附帶錯誤訊息
- 步驟 6 失敗: 靜默失敗（不影響回應）

---

## 整合點與 API 設計

### 內部整合點

#### 整合點 1: 與 ProcessorFactory 整合

**整合方式**: 直接呼叫 `ProcessorFactory.get_processor(document_type)`，取得處理器後呼叫 `process()` 方法

**介面定義**: 無需修改，完全重用現有介面

**相容性考量**: ProcessorFactory 回傳新實例，無狀態衝突

---

#### 整合點 2: 與 StorageService 整合

**整合方式**: 呼叫 `storage_service.upload_file(filename, content, path_prefix, acl)`

**路徑對應**:
```python
S3_PATH_MAP = {
    "transcript": "uploads/ocr_transcripts",
    "contract": "uploads/ocr_contracts",
}
```

**相容性考量**: 已支援 `path_prefix` 參數，無需修改

---

#### 整合點 3: 與 ai_service 整合

**整合方式**: 直接呼叫 `answer_question(question, context)`，繞過 `chat_service`

**介面定義**:
```python
async def answer_question(question: str, context: dict) -> str:
    # context = {"ocr_text": str, "doc_type": str, "extracted_data": dict}
```

**相容性考量**: `answer_question()` 為獨立函數，不依賴 DB

---

### 外部 API 設計

#### API 端點: POST /api/v1/analyze

**路徑**: `POST /api/v1/analyze`

**請求格式** (multipart/form-data):
```
file: (binary)          # 必填，PDF/JPG/JPEG/PNG
document_type: string   # 選填，預設 "transcript"
enable_llm: boolean     # 選填，預設 true
question: string        # 選填，AI 問答問題
```

**成功回應** (200):
```json
{
  "file_name": "謄本.pdf",
  "file_url": "https://d1h2hzes3rmzug.cloudfront.net/uploads/ocr_transcripts/uuid.pdf",
  "document_type": "transcript",
  "total_pages": 3,
  "pages": [
    {
      "page_number": 1,
      "ocr_raw": {
        "text": "土地登記第三類謄本...",
        "confidence": 0.82
      },
      "rule_postprocessed": {
        "text": "土地登記第三類謄本...",
        "stats": {"typo_fixes": 15, "format_corrections": 3}
      },
      "llm_postprocessed": {
        "text": "土地登記第三類謄本...",
        "stats": {"llm_used": true, "llm_cost": 0.02},
        "used": true
      },
      "structured_data": null
    }
  ],
  "answer": null,
  "stats": {
    "total_time_ms": 12500,
    "total_pages": 3,
    "llm_pages_used": 2,
    "estimated_cost": 0.04
  }
}
```

**錯誤碼**:

| 狀態碼 | error_code | 說明 |
|--------|-----------|------|
| 400 | `UNSUPPORTED_FILE_TYPE` | 不支援的檔案格式 |
| 400 | `UNSUPPORTED_DOCUMENT_TYPE` | 不支援的文件類型 |
| 413 | `FILE_TOO_LARGE` | 檔案超過 20MB |
| 500 | `PROCESSING_ERROR` | 處理過程發生錯誤 |
| 500 | `STORAGE_ERROR` | S3 儲存失敗 |

**錯誤回應格式**:
```json
{
  "detail": "不支援的檔案格式：.docx。支援的格式：PDF、JPG、JPEG、PNG",
  "error_code": "UNSUPPORTED_FILE_TYPE"
}
```

**對應需求**: 需求 1, 需求 2, 需求 3, 需求 4, 需求 5, 需求 6, 需求 8

---

#### API 端點: GET /api/v1/usage

**路徑**: `GET /api/v1/usage`

**回應格式** (200):
```json
{
  "total_calls": 156,
  "total_pages": 423,
  "total_llm_cost": 8.46,
  "period": "all_time"
}
```

**對應需求**: 需求 7

---

## 配置與部署

### 配置管理

**既有環境變數**（已設定完成）:
```bash
STORAGE_TYPE=s3
S3_BUCKET=jgb2-production-upload
S3_REGION=ap-northeast-1
S3_ACCESS_KEY=***
S3_SECRET_KEY=***
S3_CDN_URL=https://d1h2hzes3rmzug.cloudfront.net
OPENAI_API_KEY=***
```

**無需新增環境變數**

### 部署策略

**部署步驟**:
1. 執行資料庫遷移（新增 `api_usage_logs` 表）
2. 重新建構 Docker 映像
3. `docker compose up -d`
4. 驗證 `POST /api/v1/analyze` 可用

**Nginx 調整**:
```nginx
# 增加超時設定（大文件處理可能需要較長時間）
location /api/ {
    proxy_read_timeout 120s;
    proxy_send_timeout 120s;
}
```

**回滾計劃**: 新端點為純新增，不影響現有端點，移除 router 即可回滾

---

## 效能與可靠性

### 效能目標

| 指標 | 目標值 | 測量方式 |
|------|--------|---------|
| 單頁 JPG（不含 LLM）| < 30 秒 | API 回應 stats.total_time_ms |
| 單頁 JPG（含 LLM）| < 60 秒 | API 回應 stats.total_time_ms |
| 3 頁 PDF（不含 LLM）| < 90 秒 | API 回應 stats.total_time_ms |
| S3 上傳時間 | < 5 秒 | 內部日誌 |

### 可靠性設計

**錯誤處理策略**:
- S3 上傳失敗: 降級為不儲存，OCR 結果仍正常回傳
- 單頁 OCR 失敗: 跳過該頁，繼續處理其餘頁面
- LLM 呼叫失敗/拒絕: 回退使用規則修正結果
- 問答 LLM 失敗: `answer` 設為 null

**降級機制**:
- LLM 被拒絕 → 回退使用規則修正（已實作）
- S3 不可用 → `file_url` 為 null，不影響 OCR 結果

---

## 測試策略

### 單元測試

**測試範圍**:
- [ ] `analyze_document()` 端點參數驗證
- [ ] `AnalyzeService.analyze()` 流程編排
- [ ] `AnalyzeResponse` 型別正確性
- [ ] S3 路徑生成邏輯
- [ ] 用量記錄寫入正確性

**測試工具**: pytest, pytest-asyncio

---

### 整合測試

**測試場景**:
- [ ] 上傳 PDF 謄本 → OCR + 結構化欄位 + S3 CDN URL
- [ ] 上傳合約 + 問題 → OCR + 欄位 + AI 回答
- [ ] 上傳不支援格式 → 400 錯誤
- [ ] S3 上傳失敗降級 → OCR 結果正常、file_url 為 null

**測試資料**: 使用 `backend/data/` 目錄下的範例謄本

---

### 驗收測試

**成功標準**:
- [ ] 單次 API 呼叫取得完整 OCR + 結構化欄位結果
- [ ] 回應時間 < 30 秒（單頁，不含 LLM）
- [ ] Swagger 文件包含完整說明，第三方可自行串接

---

## 風險與緩解

### 技術風險

| 風險 | 嚴重程度 | 緩解措施 |
|------|---------|---------|
| 大文件處理超時 (>10 頁) | 中 | Nginx timeout 設 120s，文檔標明預期處理時間 |
| GPT-4o PII 過濾拒絕 | 低 | 已改為不傳圖片，純文字校正 + 拒絕偵測 fallback |
| S3 上傳失敗 | 低 | 降級處理，OCR 結果不受影響 |

### 營運風險

| 風險 | 嚴重程度 | 緩解措施 |
|------|---------|---------|
| LLM API 成本失控 | 中 | 用量統計追蹤，智能策略僅 < 85% 信心度時使用 LLM |
| 無認證被濫用 | 中 | MVP 階段暫不處理，未來加入 API Key 認證 |

---

## 實施里程碑

### Phase 1: 核心端點 (P0 需求)
- [ ] 新增 `analyze.py` 路由
- [ ] 新增 `analyze_service.py` 服務
- [ ] 新增 `AnalyzeResponse` Pydantic schema
- [ ] S3 上傳整合（按文件類型分路徑）
- [ ] 單元測試 + 整合測試

### Phase 2: 問答與文檔 (P1 需求)
- [ ] 整合 `answer_question()` 問答功能
- [ ] 統一錯誤格式與繁中訊息
- [ ] Swagger 文檔完善

### Phase 3: 用量統計 (P2 需求)
- [ ] 新增 `api_usage_logs` 資料表 + Alembic 遷移
- [ ] `GET /api/v1/usage` 端點
- [ ] 用量記錄寫入

---

**文件版本**: 1.0
**最後更新**: 2026-04-08
**設計狀態**: 待審核
**需求追溯**: 完整對應 requirements.md 中的需求 1-8
