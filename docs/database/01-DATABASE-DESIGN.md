# AI Document Intelligence Demo - 資料庫設計

## 1. 資料庫選型

### 1.1 選擇 PostgreSQL

**理由：**
- ✅ 支援 JSONB 類型（適合儲存 AI 抽取的動態欄位）
- ✅ 支援 GIN 索引（加速 JSONB 查詢）
- ✅ 成熟穩定，社群支援好
- ✅ SQLAlchemy ORM 支援完善
- ✅ Railway/Render 免費提供
- ✅ Alembic 自動生成 migrations

## 2. 資料表設計

### 2.1 documents（文件表）

**用途：** 儲存上傳的文件基本資訊

| 欄位名稱 | 資料型別 | 約束 | 說明 |
|---------|---------|------|------|
| `id` | UUID | PK, NOT NULL | 文件唯一識別碼 |
| `file_name` | VARCHAR(255) | NOT NULL | 原始檔案名稱 |
| `file_url` | TEXT | NOT NULL | S3/R2 儲存位置 URL |
| `mime_type` | VARCHAR(100) | NOT NULL | 檔案 MIME 類型 |
| `file_size` | INTEGER | NOT NULL | 檔案大小（bytes） |
| `status` | VARCHAR(50) | NOT NULL, DEFAULT 'uploaded' | 處理狀態 |
| `error_message` | TEXT | NULL | 錯誤訊息（如果處理失敗） |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | 建立時間 |
| `updated_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | 更新時間 |

**索引：**
```sql
CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_created_at ON documents(created_at DESC);
```

**狀態值說明：**
- `uploaded` - 檔案已上傳，待處理
- `processing` - 正在處理中
- `completed` - 處理完成
- `failed` - 處理失敗

**SQLAlchemy Model:**
```python
from sqlalchemy import Column, String, Integer, Text, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base
import uuid

class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_name = Column(String(255), nullable=False)
    file_url = Column(Text, nullable=False)
    mime_type = Column(String(100), nullable=False)
    file_size = Column(Integer, nullable=False)
    status = Column(String(50), nullable=False, default="uploaded")
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    ocr_results = relationship("DocumentOcrResult", back_populates="document", cascade="all, delete-orphan")
    ai_results = relationship("DocumentAiResult", back_populates="document", cascade="all, delete-orphan")
    chat_logs = relationship("DocumentChatLog", back_populates="document", cascade="all, delete-orphan")
    created_records = relationship("CreatedRecord", back_populates="source_document", cascade="all, delete-orphan")
```

---

### 2.2 document_ocr_results（OCR 結果表）

**用途：** 儲存 OCR 文字辨識結果

| 欄位名稱 | 資料型別 | 約束 | 說明 |
|---------|---------|------|------|
| `id` | UUID | PK, NOT NULL | OCR 結果唯一識別碼 |
| `document_id` | UUID | FK, NOT NULL | 關聯的文件 ID |
| `raw_text` | TEXT | NOT NULL | OCR 完整文字內容 |
| `page_count` | INTEGER | NOT NULL, DEFAULT 1 | 頁數 |
| `ocr_confidence` | DECIMAL(5,2) | NULL | OCR 信心度 (0-100) |
| `ocr_service` | VARCHAR(50) | NULL | 使用的 OCR 服務 |
| `processing_time` | INTEGER | NULL | 處理時間（毫秒） |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | 建立時間 |

**索引：**
```sql
CREATE INDEX idx_ocr_document_id ON document_ocr_results(document_id);
```

**外鍵：**
```sql
ALTER TABLE document_ocr_results
  ADD CONSTRAINT fk_ocr_document
  FOREIGN KEY (document_id) REFERENCES documents(id)
  ON DELETE CASCADE;
```

**SQLAlchemy Model:**
```python
from sqlalchemy import Column, String, Integer, Text, DateTime, Numeric, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base
import uuid

class DocumentOcrResult(Base):
    __tablename__ = "document_ocr_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    raw_text = Column(Text, nullable=False)
    page_count = Column(Integer, default=1, nullable=False)
    ocr_confidence = Column(Numeric(5, 2), nullable=True)
    ocr_service = Column(String(50), nullable=True)
    processing_time = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    document = relationship("Document", back_populates="ocr_results")
```

---

### 2.3 document_ai_results（AI 處理結果表）

**用途：** 儲存 AI 分類、抽取、摘要等結果

| 欄位名稱 | 資料型別 | 約束 | 說明 |
|---------|---------|------|------|
| `id` | UUID | PK, NOT NULL | AI 結果唯一識別碼 |
| `document_id` | UUID | FK, NOT NULL | 關聯的文件 ID |
| `doc_type` | VARCHAR(50) | NOT NULL | 文件類型 |
| `confidence` | DECIMAL(5,2) | NOT NULL | 分類信心度 (0-100) |
| `summary` | TEXT | NULL | AI 生成的摘要 |
| `risks` | JSONB | NULL | 風險檢測結果 |
| `extracted_data` | JSONB | NOT NULL | 抽取的欄位資料 |
| `ai_model` | VARCHAR(50) | NULL | 使用的 AI 模型 |
| `processing_time` | INTEGER | NULL | 處理時間（毫秒） |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | 建立時間 |

**索引：**
```sql
CREATE INDEX idx_ai_document_id ON document_ai_results(document_id);
CREATE INDEX idx_ai_doc_type ON document_ai_results(doc_type);
CREATE INDEX idx_ai_extracted_data ON document_ai_results USING GIN (extracted_data);
```

**外鍵：**
```sql
ALTER TABLE document_ai_results
  ADD CONSTRAINT fk_ai_document
  FOREIGN KEY (document_id) REFERENCES documents(id)
  ON DELETE CASCADE;
```

**doc_type 值：**
- `lease_contract` - 租賃合約
- `repair_quote` - 修繕報價單
- `id_card` - 身分證
- `unknown` - 無法識別

**extracted_data JSON 結構範例：**

**租賃合約：**
```json
{
  "landlord_name": "張三",
  "tenant_name": "王小明",
  "address": "台北市中山區XX路XX號",
  "rent": 25000,
  "deposit": 50000,
  "lease_start": "2026-01-01",
  "lease_end": "2026-12-31",
  "contract_date": "2025-12-15"
}
```

**修繕報價單：**
```json
{
  "vendor_name": "大安水電行",
  "quote_date": "2026-03-10",
  "amount": 5000,
  "item_summary": "冷氣機維修更換壓縮機"
}
```

**身分證：**
```json
{
  "name": "王小明",
  "national_id": "A123456789",
  "birth_date": "1990-05-15"
}
```

**risks JSON 結構範例：**
```json
[
  {
    "type": "missing_field",
    "field": "contract_date",
    "severity": "warning",
    "message": "缺少合約簽訂日期"
  },
  {
    "type": "low_confidence",
    "field": "rent",
    "severity": "info",
    "message": "租金欄位辨識信心度較低"
  }
]
```

**SQLAlchemy Model:**
```python
from sqlalchemy import Column, String, Integer, Text, DateTime, Numeric, ForeignKey, func, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base
import uuid

class DocumentAiResult(Base):
    __tablename__ = "document_ai_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    doc_type = Column(String(50), nullable=False)
    confidence = Column(Numeric(5, 2), nullable=False)
    summary = Column(Text, nullable=True)
    risks = Column(JSONB, nullable=True)
    extracted_data = Column(JSONB, nullable=False)
    ai_model = Column(String(50), nullable=True)
    processing_time = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    document = relationship("Document", back_populates="ai_results")

    # Indexes
    __table_args__ = (
        Index('idx_ai_document_id', 'document_id'),
        Index('idx_ai_doc_type', 'doc_type'),
        Index('idx_ai_extracted_data', 'extracted_data', postgresql_using='gin'),
    )
```

---

### 2.4 created_records（建立的記錄表 - P2）

**用途：** 儲存從文件一鍵建立的系統記錄

| 欄位名稱 | 資料型別 | 約束 | 說明 |
|---------|---------|------|------|
| `id` | UUID | PK, NOT NULL | 記錄唯一識別碼 |
| `source_document_id` | UUID | FK, NOT NULL | 來源文件 ID |
| `record_type` | VARCHAR(50) | NOT NULL | 記錄類型 |
| `payload` | JSONB | NOT NULL | 記錄資料 |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | 建立時間 |

**索引：**
```sql
CREATE INDEX idx_records_document_id ON created_records(source_document_id);
CREATE INDEX idx_records_type ON created_records(record_type);
```

**外鍵：**
```sql
ALTER TABLE created_records
  ADD CONSTRAINT fk_records_document
  FOREIGN KEY (source_document_id) REFERENCES documents(id)
  ON DELETE CASCADE;
```

**record_type 值：**
- `lease` - 租約記錄
- `repair_quote` - 報價單記錄
- `tenant` - 租客記錄

**payload JSON 結構範例：**

**租約記錄：**
```json
{
  "landlord_name": "張三",
  "tenant_name": "王小明",
  "address": "台北市中山區XX路XX號",
  "rent": 25000,
  "deposit": 50000,
  "lease_start": "2026-01-01",
  "lease_end": "2026-12-31",
  "status": "active"
}
```

**SQLAlchemy Model:**
```python
from sqlalchemy import Column, String, DateTime, ForeignKey, func, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base
import uuid

class CreatedRecord(Base):
    __tablename__ = "created_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    record_type = Column(String(50), nullable=False)
    payload = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    source_document = relationship("Document", back_populates="created_records")

    # Indexes
    __table_args__ = (
        Index('idx_records_document_id', 'source_document_id'),
        Index('idx_records_type', 'record_type'),
    )
```

---

### 2.5 document_chat_logs（問答記錄表 - 可選）

**用途：** 儲存 AI 問答歷史記錄

| 欄位名稱 | 資料型別 | 約束 | 說明 |
|---------|---------|------|------|
| `id` | UUID | PK, NOT NULL | 問答記錄唯一識別碼 |
| `document_id` | UUID | FK, NOT NULL | 關聯的文件 ID |
| `question` | TEXT | NOT NULL | 使用者問題 |
| `answer` | TEXT | NOT NULL | AI 回答 |
| `ai_model` | VARCHAR(50) | NULL | 使用的 AI 模型 |
| `response_time` | INTEGER | NULL | 回應時間（毫秒） |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | 建立時間 |

**索引：**
```sql
CREATE INDEX idx_chat_document_id ON document_chat_logs(document_id);
CREATE INDEX idx_chat_created_at ON document_chat_logs(created_at DESC);
```

**外鍵：**
```sql
ALTER TABLE document_chat_logs
  ADD CONSTRAINT fk_chat_document
  FOREIGN KEY (document_id) REFERENCES documents(id)
  ON DELETE CASCADE;
```

**SQLAlchemy Model:**
```python
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, func, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base
import uuid

class DocumentChatLog(Base):
    __tablename__ = "document_chat_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    ai_model = Column(String(50), nullable=True)
    response_time = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    document = relationship("Document", back_populates="chat_logs")

    # Indexes
    __table_args__ = (
        Index('idx_chat_document_id', 'document_id'),
        Index('idx_chat_created_at', 'created_at'),
    )
```

---

## 3. 資料庫設置與遷移

```prisma
// This is your Prisma schema file,
// learn more about it in the docs: https://pris.ly/d/prisma-schema

generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

model Document {
  id            String   @id @default(uuid())
  fileName      String   @map("file_name")
  fileUrl       String   @map("file_url")
  mimeType      String   @map("mime_type")
  fileSize      Int      @map("file_size")
  status        String   @default("uploaded")
  errorMessage  String?  @map("error_message")
  createdAt     DateTime @default(now()) @map("created_at")
  updatedAt     DateTime @updatedAt @map("updated_at")

  ocrResults     DocumentOcrResult[]
  aiResults      DocumentAiResult[]
  chatLogs       DocumentChatLog[]
  createdRecords CreatedRecord[]

  @@index([status])
  @@index([createdAt(sort: Desc)])
  @@map("documents")
}

model DocumentOcrResult {
  id             String   @id @default(uuid())
  documentId     String   @map("document_id")
  rawText        String   @map("raw_text")
  pageCount      Int      @default(1) @map("page_count")
  ocrConfidence  Decimal? @map("ocr_confidence") @db.Decimal(5, 2)
  ocrService     String?  @map("ocr_service")
  processingTime Int?     @map("processing_time")
  createdAt      DateTime @default(now()) @map("created_at")

  document Document @relation(fields: [documentId], references: [id], onDelete: Cascade)

  @@index([documentId])
  @@map("document_ocr_results")
}

model DocumentAiResult {
  id             String   @id @default(uuid())
  documentId     String   @map("document_id")
  docType        String   @map("doc_type")
  confidence     Decimal  @map("confidence") @db.Decimal(5, 2)
  summary        String?
  risks          Json?
  extractedData  Json     @map("extracted_data")
  aiModel        String?  @map("ai_model")
  processingTime Int?     @map("processing_time")
  createdAt      DateTime @default(now()) @map("created_at")

  document Document @relation(fields: [documentId], references: [id], onDelete: Cascade)

  @@index([documentId])
  @@index([docType])
  @@map("document_ai_results")
}

model CreatedRecord {
  id               String   @id @default(uuid())
  sourceDocumentId String   @map("source_document_id")
  recordType       String   @map("record_type")
  payload          Json
  createdAt        DateTime @default(now()) @map("created_at")

  document Document @relation(fields: [sourceDocumentId], references: [id], onDelete: Cascade)

  @@index([sourceDocumentId])
  @@index([recordType])
  @@map("created_records")
}

model DocumentChatLog {
  id           String   @id @default(uuid())
  documentId   String   @map("document_id")
  question     String
  answer       String
  aiModel      String?  @map("ai_model")
  responseTime Int?     @map("response_time")
  createdAt    DateTime @default(now()) @map("created_at")

  document Document @relation(fields: [documentId], references: [id], onDelete: Cascade)

  @@index([documentId])
  @@index([createdAt(sort: Desc)])
  @@map("document_chat_logs")
}
```

---

## 4. 資料庫初始化腳本

### 4.1 建立資料庫

```bash
# 使用 Docker 快速啟動 PostgreSQL
docker run --name ai-doc-demo-db \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=ai_doc_demo \
  -p 5432:5432 \
  -d postgres:14-alpine
```

### 4.2 Prisma 指令

```bash
# 安裝 Prisma
npm install @prisma/client
npm install -D prisma

# 初始化 Prisma
npx prisma init

# 執行 migration
npx prisma migrate dev --name init

# 生成 Prisma Client
npx prisma generate

# 開啟 Prisma Studio（資料庫視覺化工具）
npx prisma studio
```

---

## 5. 查詢範例

### 5.1 取得文件及其 AI 結果

```typescript
const document = await prisma.document.findUnique({
  where: { id: documentId },
  include: {
    ocrResults: true,
    aiResults: true,
    chatLogs: {
      orderBy: { createdAt: 'desc' },
      take: 10
    },
    createdRecords: true
  }
});
```

### 5.2 查詢特定類型的文件

```typescript
const leaseContracts = await prisma.document.findMany({
  where: {
    aiResults: {
      some: {
        docType: 'lease_contract'
      }
    }
  },
  include: {
    aiResults: true
  }
});
```

### 5.3 搜尋抽取欄位（JSONB 查詢）

```typescript
// 查詢租金大於 20000 的租約
const documents = await prisma.$queryRaw`
  SELECT d.*, ai.*
  FROM documents d
  JOIN document_ai_results ai ON d.id = ai.document_id
  WHERE ai.doc_type = 'lease_contract'
    AND (ai.extracted_data->>'rent')::int > 20000
`;
```

### 5.4 取得處理失敗的文件

```typescript
const failedDocuments = await prisma.document.findMany({
  where: {
    status: 'failed'
  },
  select: {
    id: true,
    fileName: true,
    errorMessage: true,
    createdAt: true
  }
});
```

---

## 6. 資料遷移策略

### 6.1 版本控制

- ✅ 所有 schema 變更透過 Prisma migration
- ✅ Migration 檔案納入 Git 版本控制
- ✅ 生產環境部署前先在 staging 測試

### 6.2 向下相容

- ⚠️ 新增欄位使用 NULL 或 DEFAULT
- ⚠️ 避免直接刪除欄位（先標記為 deprecated）
- ⚠️ JSONB 欄位變更需考慮舊資料相容性

---

## 7. 備份策略（正式環境）

### 7.1 自動備份

```bash
# 每日自動備份（使用 pg_dump）
0 2 * * * pg_dump -U postgres ai_doc_demo > /backup/ai_doc_demo_$(date +\%Y\%m\%d).sql
```

### 7.2 備份保留政策

- 每日備份保留 7 天
- 每週備份保留 4 週
- 每月備份保留 12 個月

**注意：** MVP 階段可使用 Railway/Render 的自動備份功能。

---

## 8. 效能優化建議

### 8.1 索引優化

- ✅ 在常用查詢欄位建立索引
- ✅ 使用 GIN 索引加速 JSONB 查詢
- ✅ 定期執行 `ANALYZE` 更新統計資訊

### 8.2 查詢優化

- ✅ 使用 `select` 只查詢需要的欄位
- ✅ 分頁查詢使用 `take` 和 `skip`
- ✅ 避免 N+1 查詢（使用 `include` 或 `select`）

### 8.3 連線池設定

```typescript
const prisma = new PrismaClient({
  datasources: {
    db: {
      url: process.env.DATABASE_URL,
    },
  },
  // 連線池設定
  log: ['query', 'error', 'warn'],
});
```

---

## 9. 資料清理策略

### 9.1 清理舊資料（未來）

```sql
-- 刪除 90 天前處理失敗的文件
DELETE FROM documents
WHERE status = 'failed'
  AND created_at < NOW() - INTERVAL '90 days';

-- 清理孤立的 OCR 結果（理論上不應該發生，因為有 CASCADE）
DELETE FROM document_ocr_results
WHERE document_id NOT IN (SELECT id FROM documents);
```

### 9.2 資料歸檔

- 文件超過 1 年可移至歸檔表
- S3 檔案可移至 Glacier（降低成本）

---

**文檔版本**: v1.0
**最後更新**: 2026-03-17
**負責人**: Database Team
