# document-type-routing - 技術設計文件

## 概述

### 設計目標
將現有以 `ProcessorFactory` / `DocumentProcessor` 為雛形的處理流程,擴充為完整的「文件類型路由 + 四類各自 pipeline + 共用回饋學習層」架構。以本地優先(PaddleOCR + 可插拔 LLM 層)達成隱私與成本目標,並以「零訓練」的 HITL + few-shot 迴路使系統隨使用累積校正而持續提升準確率。

### 設計原則
1. **本地優先、雲端可選**:OCR 一律本地;LLM/VLM 層抽象為可插拔 Provider,雲端預設關閉。
2. **最大化複用既有骨架**:沿用工廠 + 模板方法,以加法方式擴充,不破壞 `transcript`/`contract` 現行行為。
3. **零訓練學習迴路**:以校正樣本 + few-shot 注入達成「越用越準」,fine-tune 僅為 Phase 3 決策點。
4. **人只碰低信心**:信心度門檻攔截,高信心自動放行,人工量隨時間遞減。
5. **可量測**:每類文件建立 CER / 欄位級準確率基準線,證明準確率提升。

### 架構決策摘要
1. **統一文件類型列舉**(`transcript`/`bill`/`contract`/`repair_photo`),收斂現有三處不一致的型別體系(對應需求 1.1)。
2. **信心度評估收斂**:復活並實作 `QualityAssessor` 為單一評估點,取代散落硬編碼門檻,門檻可由 `config.py` 配置(對應需求 6.1、6.6)。
3. **LLM 層可插拔**:定義 `LLMProvider` 抽象(`OpenAIProvider` / `LocalQwenProvider`),`LLMService` 依組態注入,few-shot 範例注入介面納入契約(對應需求 7.3、非功能隱私)。
4. **回饋學習層為獨立新模組 + 新資料表**:複核佇列、校正樣本、few-shot 選取、評估,皆新建,透過 `AnalyzeService` 編排串接(對應需求 6、7、8)。
5. **PP-Structure 定位為謄本增強選項**:謄本欄位抽取先以「規則 + LLM Vision」落地(仿 `ContractFieldExtractor`),PP-Structure 作為可選增強,PoC 不如預期時不阻塞主線(對應需求 2.1、gap-analysis 建議)。

---

## 架構模式與邊界劃分

### 選定模式
- **策略 + 工廠模式**:文件類型 → Processor 的路由(既有 `ProcessorFactory`)。
- **模板方法模式**:`DocumentProcessor` 定義 pipeline 骨架(既有)。
- **管道 + 責任鏈**:各 Processor 內的 前處理 → OCR → 後處理 → 抽取。
- **策略模式(新)**:`LLMProvider` 可插拔(本地/雲端)。
- **狀態機(新)**:複核佇列的認領/鎖定生命週期。

### 模組邊界圖

```
                          POST /api/v1/analyze
                                   │
                                   ▼
                        ┌──────────────────────┐
                        │    AnalyzeService     │  (編排層)
                        │  + PDF 文字層偵測分支   │
                        └───────────┬──────────┘
                                    │ document_type
                          ┌─────────▼──────────┐
                          │  ProcessorFactory   │  (路由)
                          └─────────┬──────────┘
        ┌───────────────┬──────────┼───────────────┬───────────────┐
        ▼               ▼          ▼               ▼               
 TranscriptProcessor BillProcessor ContractProcessor RepairPhotoProcessor
   (謄本,增強PP-Struct) (帳單,新)   (合約,既有+文字層) (照片,新VLM)
        └───────────────┴──────────┼───────────────┴───────────────┘
                                    │ 每頁結果 + 欄位 + 信心度
                          ┌─────────▼──────────┐
                          │   QualityAssessor   │  (信心度評估,收斂)
                          └─────────┬──────────┘
                        低信心 │            │ 高信心
                              ▼            ▼
                     ┌──────────────┐   自動放行
                     │  回饋學習層    │
                     │ ┌──────────┐ │
                     │ │ReviewQueue│ │◀── 人工複核(認領鎖定→校正)
                     │ ├──────────┤ │
                     │ │Correction│ │──▶ 校正樣本入庫
                     │ │ Samples  │ │
                     │ ├──────────┤ │
                     │ │FewShotSel│ │──▶ 回灌範例到 LLMProvider
                     │ ├──────────┤ │
                     │ │Evaluator │ │──▶ CER/欄位準確率
                     │ └──────────┘ │
                     └──────────────┘
                                    │
                     ┌──────────────▼──────────────┐
                     │  LLMService (可插拔 Provider) │
                     │  OpenAIProvider│LocalQwenProv │
                     └─────────────────────────────┘
```

### 邊界劃分理由
- **編排層(AnalyzeService)** 只負責流程協調與跨頁彙整,不含類型邏輯,新增「PDF 文字層偵測」前置分支(需求 4.1)。
- **路由層(ProcessorFactory)** 為唯一型別分派點,新增型別在此註冊。
- **Processor 層** 各自封裝該類 pipeline,彼此獨立、可單獨演進(符合結構規範的可擴展設計)。
- **回饋學習層** 與 pipeline 解耦:pipeline 只「產生結果 + 信心度」,是否進佇列、如何學習由此層決定,確保任一類型都能共用同一套學習機制。
- **LLM 層** 以 Provider 抽象隔離本地/雲端差異,pipeline 與學習層不感知底層模型。

---

## 技術棧與對齊

### 核心技術選擇

| 技術領域 | 選擇 | 版本 | 理由 |
|---------|------|------|------|
| 語言 | Python | 3.11+ | 專案標準 |
| 框架 | FastAPI | 0.115+ | 專案標準 |
| ORM | SQLAlchemy | 2.0 | 專案標準 |
| 遷移 | Alembic | — | 專案標準 |
| OCR 引擎 | PaddleOCR (PP-OCRv5) | 3.x | 本地、中文最強、免費(research 佐證) |
| 版面解析(選) | PP-StructureV3 | 3.x | 謄本表格/印章結構化(增強項) |
| PDF 文字層 | PyMuPDF / pymupdf4llm | 最新 | 合約文字層偵測 + 分段 |
| 本地 LLM/VLM(選) | Qwen2-VL 2B/7B | — | Apache 2.0、可自架、支援中文 |
| 雲端 LLM(選) | OpenAI GPT-4o / mini | — | POC 起步、預設可關 |
| 前端 | Vue 3 + TS | 3.4+ | 複核介面 |

### 外部依賴

| 依賴 | 用途 | 風險評估 |
|------|------|---------|
| paddleocr / paddlepaddle | 本地 OCR 主力 | 低(既有 EngineManager 已含,需啟用) |
| paddleocr PP-Structure | 謄本版面解析 | 中(新依賴、映像體積、繁中謄本無 benchmark → 需 PoC) |
| pymupdf4llm | 合約文字層偵測/分段 | 低 |
| transformers + vLLM(本地 VLM) | 修繕照片理解 | 中(需 GPU;預設可關,先用雲端 POC) |
| openai / anthropic(既有) | 雲端 Provider | 低(既有,改為可插拔) |

### 與現有系統對齊
- 沿用 `app/lib/multi_type_ocr/` 的工廠與 Processor 契約,新增類別註冊即接入。
- 沿用 `JSONB` + GIN 索引慣例(既有 `DocumentAiResult.extracted_data`)。
- 沿用 `{"detail": ...}` 錯誤格式與繁中訊息;沿用 `pydantic-settings` 配置。
- `EngineManager` 內既有 PaddleOCR 單例,本設計將其在 `TranscriptProcessor`/`BillProcessor` 正式啟用(取代目前硬編碼 tesseract)。

---

## 元件與介面契約

### 元件 1: DocumentTypeRouter(擴充既有 ProcessorFactory)

**職責**: 依統一型別列舉將文件路由至對應 Processor;動態提供支援型別供 API 白名單使用;整合分類器建議。

**公開介面**:
```python
from enum import Enum
from typing import Optional
from PIL.Image import Image

class DocumentType(str, Enum):
    TRANSCRIPT = "transcript"      # 建物土地謄本
    BILL = "bill"                  # 帳單
    CONTRACT = "contract"          # 合約 PDF
    REPAIR_PHOTO = "repair_photo"  # 修繕照片

class ProcessorFactory:
    @classmethod
    def get_processor(cls, document_type: DocumentType) -> "DocumentProcessor": ...
    @classmethod
    def register_processor(cls, document_type: DocumentType, cls_: type) -> None: ...
    @classmethod
    def supported_types(cls) -> list[DocumentType]: ...

class DocumentClassifier:
    async def suggest(self, image: Image) -> tuple[DocumentType, float]:
        """回傳建議型別與信心度;僅為建議,不改變使用者指定為準的契約"""
```

**依賴**: `DocumentProcessor` 具體實作、`DocumentClassifier`(既有,型別體系收斂後接入)
**對應需求**: 1.1, 1.2, 1.3, 1.4

---

### 元件 2: DocumentProcessor 契約(重構:統一 analyze 模板,分離 OCR 型與影像理解型)

**職責**: 定義各類 pipeline 骨架。**審查修正(問題 1)**:原基類以 OCR 文字流為核心(`extract_text` 回 `(text, confidence)`),讓非 OCR 的修繕照片硬繞過(回 `("", 1.0)`)是契約氣味。改以更抽象的 `analyze(image) -> PageResult` 為模板核心,並分出兩個子契約——`OcrDocumentProcessor`(OCR 型:謄本/帳單/合約)與 `ImageUnderstandingProcessor`(影像理解型:修繕照片),兩者皆回傳統一 `PageResult`,使 `QualityAssessor` 能以同一套邏輯評估。

**公開介面**:
```python
from typing import Optional, TypedDict
from abc import ABC, abstractmethod

class FewShotExample(TypedDict):
    document_type: str
    layout_signature: str      # 版型指紋(見 FewShotSelector,供同版型選取)
    input_ref: str             # 原始輸入參照(影像路徑/文字摘要)
    corrected_fields: dict      # 校正後正確欄位值

class PageResult(TypedDict):
    page_number: int
    ocr_raw: Optional[dict]     # OCR 型:{text, confidence};影像理解型:None
    rule_postprocessed: Optional[dict]
    llm_postprocessed: Optional[dict]   # {text, stats, used}
    structured_data: dict        # 欄位抽取 / 影像理解結果
    field_confidences: dict      # {field_name: confidence}
    overall_confidence: float    # 統一信心度,供 QualityAssessor(語意:對結果整體的可信度)

class DocumentProcessor(ABC):
    """統一契約:analyze 為模板核心,回傳統一 PageResult"""
    @abstractmethod
    async def analyze(self, image: Image, image_data: Optional[str] = None,
                      enable_llm: bool = False,
                      few_shot: Optional[list[FewShotExample]] = None) -> PageResult: ...
    async def process(self, file_contents: bytes, filename: str, page_number: int,
                      total_pages: int, enable_llm: bool,
                      few_shot: Optional[list[FewShotExample]] = None) -> PageResult:
        """載入影像 → 呼叫 analyze → 補頁碼/base64 → 回傳(既有 process 職責保留)"""

class OcrDocumentProcessor(DocumentProcessor):
    """OCR 型預設實作:analyze = preprocess → extract_text → postprocess → extract_fields"""
    @abstractmethod
    async def preprocess(self, image: Image) -> Image: ...
    @abstractmethod
    async def extract_text(self, image: Image) -> tuple[str, float]: ...
    @abstractmethod
    async def postprocess(self, text: str, confidence: float,
                          image_data: Optional[str] = None) -> tuple[str, dict]: ...
    @abstractmethod
    async def extract_fields(self, text: str, image_data: Optional[str] = None,
                             enable_llm: bool = False,
                             few_shot: Optional[list[FewShotExample]] = None) -> dict: ...
    async def analyze(self, image, image_data=None, enable_llm=False, few_shot=None) -> PageResult:
        """預設編排四步並組出 PageResult;overall_confidence 由欄位信心度彙整"""

class ImageUnderstandingProcessor(DocumentProcessor):
    """影像理解型(修繕照片):不走 OCR,直接 VLM 理解"""
    @abstractmethod
    async def understand(self, image_data: str,
                         few_shot: Optional[list[FewShotExample]] = None) -> dict: ...
    async def analyze(self, image, image_data=None, enable_llm=True, few_shot=None) -> PageResult:
        """呼叫 understand → 以 {defect_labels, description, confidence} 填 structured_data,
        ocr_raw=None,overall_confidence=understand 回傳之 confidence"""
```

**相容性考量**: 既有 `TranscriptProcessor`/`ContractProcessor` 改繼承 `OcrDocumentProcessor`,原四方法簽名保留(僅上移一層),行為不變。
**對應需求**: 2.1, 2.3, 3.1, 5.1, 5.3, 7.3

---

### 元件 3: TranscriptProcessor(擴充)/ BillProcessor(新)/ RepairPhotoProcessor(新)

**職責**:
- `TranscriptProcessor`:啟用 PaddleOCR;實作謄本欄位抽取(地號/建號、面積、權利範圍、所有權人);浮水印移除(既有);PP-Structure 為可選增強。
- `BillProcessor`:PaddleOCR + 票證式 key-value 抽取(金額/日期/戶號);劣化件走 VLM。
- `RepairPhotoProcessor`:純 VLM,輸出瑕疵分類 + 描述 + 信心度(不走 OCR)。

**公開介面(以 BillProcessor / RepairPhotoProcessor 為例)**:
```python
class BillProcessor(OcrDocumentProcessor):          # OCR 型
    KEY_FIELDS = ("amount", "date", "account_no")
    async def extract_fields(self, text, image_data=None, enable_llm=False,
                             few_shot=None) -> dict:
        """規則抽取 → 信心度計算 → 低信心且允許時 VLM fallback(注入 few_shot)"""

class RepairPhotoProcessor(ImageUnderstandingProcessor):   # 影像理解型(非 OCR)
    async def understand(self, image_data, few_shot=None) -> dict:
        """VLM 影像理解:{defect_labels: [...], description: str, confidence: float}"""
```
**備註(問題 1)**:修繕照片改繼承 `ImageUnderstandingProcessor`,不再硬繞 `extract_text`;信心度語意統一由 `understand` 提供,交由 `QualityAssessor` 同一套門檻判定。

**對應需求**: 2.1, 2.2, 2.3, 3.1, 3.2, 3.4, 5.1, 5.2, 5.4

---

### 元件 4: QualityAssessor(復活實作,收斂信心度)

**職責**: 單一信心度評估點;計算整體信心度;依可配置門檻決定是否進入複核佇列;標記低信心欄位。

**公開介面**:
```python
class QualityDecision(TypedDict):
    overall_confidence: float
    needs_review: bool
    low_confidence_fields: list[str]

class QualityAssessor:
    def __init__(self, threshold: float = 0.8): ...   # 由 settings.OCR_QUALITY_THRESHOLD 注入
    def assess(self, page_result: PageResult,
               document_type: DocumentType) -> QualityDecision: ...
```

**依賴**: `config.settings`
**對應需求**: 6.1, 6.2, 6.6, 2.4, 3.3, 5.3
**備註**: 取代 `TranscriptPostprocessor` 0.85 與 `ContractFieldExtractor` 0.7 的硬編碼常數;預設值對齊現行行為避免突變(向後相容)。

---

### 元件 5: ReviewQueueService(新)

**職責**: 複核佇列狀態機;認領鎖定與併發控制;校正提交並記錄前後差異。

**公開介面**:
```python
from uuid import UUID

class ReviewStatus(str, Enum):
    PENDING = "pending"
    IN_REVIEW = "in_review"
    COMPLETED = "completed"

class ReviewQueueService:
    async def enqueue(self, document_id: UUID, document_type: DocumentType,
                      confidence: float, result: PageResult) -> UUID: ...
    async def claim(self, item_id: UUID, reviewer: str) -> bool:
        """認領鎖定;若已被認領回傳 False(需求 6.7)"""
    async def submit_correction(self, item_id: UUID, reviewer: str,
                                corrected_fields: dict) -> None:
        """記錄校正前後差異,狀態轉 COMPLETED,觸發校正樣本入庫"""
    async def release(self, item_id: UUID, reviewer: str) -> None: ...
    async def list_queue(self, status: Optional[ReviewStatus] = None) -> list[dict]: ...
```

**依賴**: `ReviewQueueItem` model、`CorrectionSampleService`
**對應需求**: 6.2, 6.3, 6.4, 6.5, 6.7
**併發控制**: 悲觀式—`claim` 以資料庫條件更新(`WHERE status='pending'`)保證單一認領者(見資料模型)。

---

### 元件 6: CorrectionSampleService + FewShotSelector(新)

**職責**: 校正樣本依類型入庫;黃金範例標記與去重;為新文件選取相關 few-shot 範例並回灌。

**公開介面**:
```python
class CorrectionSampleService:
    async def save(self, document_type: DocumentType, input_ref: str,
                   corrected_fields: dict, source_review_id: UUID) -> UUID: ...
    async def mark_golden(self, sample_id: UUID, is_golden: bool) -> None: ...
    async def dedupe(self, document_type: DocumentType) -> int:
        """偵測衝突/重複並提供覆寫(需求 7.5)"""

class FewShotSelector:
    def __init__(self, max_examples: int = 5): ...
    async def select(self, document_type: DocumentType,
                     layout_signature: Optional[str] = None) -> list[FewShotExample]:
        """依 v1 選取策略回傳範例(見下),上限 max_examples 控 token 成本"""
    async def seed(self, document_type: DocumentType,
                   examples: list[FewShotExample]) -> None:
        """種子範例冷啟動(上線前手動準備)"""

def compute_layout_signature(page_result: PageResult) -> str:
    """版型指紋 v1:以粗略版面特徵(頁面長寬比 + 文字區塊數量分桶 + 關鍵標題詞)
    產生穩定字串;僅需「足以區分不同版型」,非精確影像相似度"""
```

**選取策略(問題 2 — v1 明確定義,避免退化成純「最近 N」誤注入他版型範例)**:
1. **強制同 `document_type`**——絕不跨類型注入。
2. **同 `layout_signature` 優先**:先取相同版型指紋的範例(謄本/帳單「越來越準」的關鍵前提是注入同版型正確答案)。
3. **黃金範例優先**於一般校正樣本。
4. 同分再取 **最近 N**;整體上限 `max_examples`(預設 5)。
5. `layout_signature` 為 v1 粗略版型分桶(見 `compute_layout_signature`);**精確影像/版型相似度列為 Phase 2 PoC**(research openQuestion),v1 先以此基線確保「不注入不相關版型」。

**依賴**: `CorrectionSample` model(新增 `layout_signature` 欄位)
**對應需求**: 7.1, 7.2, 7.3, 7.4, 7.5

---

### 元件 7: EvaluationService(新)

**職責**: 以**獨立保留評估集(holdout)**計算 CER 與欄位級準確率;依類型記錄基準線與前後對照。

**審查修正(問題 3 — 防資料洩漏)**: 明確區分兩個互不重疊的資料集,避免「用來教模型的樣本又拿來考模型」導致準確率虛高:
- **校正樣本池(CorrectionSample, `purpose="train"`)**:可回灌 few-shot。
- **保留評估集(CorrectionSample, `purpose="holdout"`)**:獨立標註、版本化;**禁止被 `FewShotSelector` 取用**。
- `FewShotSelector.select` 一律過濾 `purpose != "holdout"`;`EvaluationService.evaluate` 一律只讀 `purpose == "holdout"`。兩者在資料層強制隔離。

**公開介面**:
```python
class EvalMetrics(TypedDict):
    cer: float
    field_accuracy: float
    sample_count: int

class EvaluationService:
    async def evaluate(self, document_type: DocumentType,
                       holdout_version: str) -> EvalMetrics:
        """僅讀 purpose='holdout' 的樣本;絕不觸及 few-shot 訓練池"""
    async def record_baseline(self, document_type: DocumentType,
                              metrics: EvalMetrics) -> None: ...
    async def compare(self, document_type: DocumentType,
                      before_version: str, after_version: str) -> dict: ...
    async def readiness_for_finetune(self, document_type: DocumentType) -> dict:
        """需求 9:訓練池樣本量達門檻 且 holdout 準確率停滯 → 標示可評估 fine-tune"""
```

**依賴**: `EvaluationRecord` model、`CorrectionSample`(`purpose` 欄位)
**對應需求**: 8.1, 8.2, 8.3, 8.4, 9.1, 9.2, 9.4

---

### 元件 8: LLMProvider 抽象(可插拔)

**職責**: 隔離本地/雲端模型差異;統一多模態影像輸入與 few-shot 注入。

**公開介面**:
```python
class LLMProvider(ABC):
    @abstractmethod
    async def call(self, prompt: str, image_data: Optional[str] = None,
                   few_shot: Optional[list[FewShotExample]] = None,
                   max_tokens: int = 2048, temperature: float = 0.0) -> str: ...

class OpenAIProvider(LLMProvider): ...     # 既有 LLMService 邏輯重構納入
class LocalQwenProvider(LLMProvider): ...   # 本地 Qwen2-VL,透過 vLLM/transformers

class LLMService:
    def __init__(self, provider: LLMProvider): ...   # 由 settings.LLM_PROVIDER 注入
```

**依賴**: `config.settings`
**對應需求**: 7.3, 非功能(隱私、成本)
**備註**: `few_shot` 注入為 prompt 組裝,不涉模型訓練(零訓練迴路核心)。

---

## 資料模型與流程

### 資料模型

#### Model 1: ReviewQueueItem

**用途**: 人工複核佇列項目與狀態機。

```python
class ReviewQueueItem(Base):
    __tablename__ = "review_queue_items"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    document_type: Mapped[str] = mapped_column(String(50))
    overall_confidence: Mapped[float] = mapped_column(Numeric(5, 4))
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/in_review/completed
    reviewer: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    claimed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    original_result: Mapped[dict] = mapped_column(JSONB)   # 校正前
    corrected_result: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # 校正後
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

**索引策略**: `idx_review_status`(status)、`idx_review_doc_type`(document_type)
**併發**: `claim` 以 `UPDATE ... WHERE id=? AND status='pending'` 之受影響列數判定成敗(需求 6.7)。

#### Model 2: CorrectionSample

**用途**: 校正樣本 / 黃金範例,依類型分庫,供 few-shot 回灌。

```python
class CorrectionSample(Base):
    __tablename__ = "correction_samples"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_type: Mapped[str] = mapped_column(String(50))
    layout_signature: Mapped[str] = mapped_column(String(120), default="")  # 版型指紋(問題 2,同版型選取)
    purpose: Mapped[str] = mapped_column(String(10), default="train")        # train | holdout(問題 3,防洩漏)
    input_ref: Mapped[str] = mapped_column(Text)          # 影像參照/文字摘要
    corrected_fields: Mapped[dict] = mapped_column(JSONB)
    is_golden: Mapped[bool] = mapped_column(Boolean, default=False)
    source_review_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("review_queue_items.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

**索引策略**: `idx_sample_select`(document_type, purpose, is_golden, layout_signature)、`corrected_fields` GIN。
**資料隔離**: `FewShotSelector` 僅取 `purpose='train'`;`EvaluationService` 僅取 `purpose='holdout'`——於服務層與查詢層雙重保證不重疊(問題 3)。

#### Model 3: EvaluationRecord

**用途**: 各類型準確率基準線與量測歷史。

```python
class EvaluationRecord(Base):
    __tablename__ = "evaluation_records"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_type: Mapped[str] = mapped_column(String(50))
    metric_type: Mapped[str] = mapped_column(String(30))   # cer / field_accuracy
    value: Mapped[float] = mapped_column(Numeric(6, 4))
    labeled_set_version: Mapped[str] = mapped_column(String(50))
    is_baseline: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

**索引策略**: `idx_eval_type_metric`(document_type, metric_type)。
**遷移考量**: 三表皆為新增,不影響既有 schema;以 Alembic 單一 migration 建立。

---

### 資料流程

**流程 1: 分析 + 信心度攔截 + 學習迴路**

```
[上傳文件 + document_type]
  → [AnalyzeService: PDF 文字層偵測]
        ├─ 合約且有文字層 → 直接抽文字 + 分段(略過 OCR)
        └─ 其餘 → 300DPI 轉圖
  → [ProcessorFactory.get_processor(type)]
  → [FewShotSelector.select(type) → 取得範例]
  → [Processor.process(..., few_shot)]  (本地 OCR + 抽取,必要時 LLM)
  → [QualityAssessor.assess() → overall_confidence]
        ├─ ≥ 門檻(0.8) → 自動放行 → 回傳結果
        └─ < 門檻 → [ReviewQueueService.enqueue()] → 待複核
  → [人工: claim → 校正 → submit_correction]
  → [CorrectionSampleService.save() → 校正樣本入庫]
  → [下次同類文件: FewShotSelector 自動納入此範例]
[結束]
```

**錯誤處理**:
- 單頁處理失敗 → 塞錯誤佔位結果,不中斷整份(沿用既有)。
- PP-Structure/VLM 失敗 → 降級為 PaddleOCR + 規則抽取。
- 本地 LLM Provider 不可用 → 依組態降級(跳過 LLM 或切雲端 fallback)。

**流程 2: fine-tune 決策(需求 9,不含訓練)**

```
[EvaluationService.readiness_for_finetune(type)]
  → 校正樣本量 ≥ 門檻 ? ── 否 → 維持 few-shot
        │ 是
  → few-shot 準確率停滯於目標下 ? ── 否 → 維持 few-shot
        │ 是
  → 標示「可評估 fine-tune」+ 附前後對照 → 人工核准
```

---

## 整合點與 API 設計

### 內部整合點

#### 整合點 1: 與 AnalyzeService 整合

**整合方式**: 於 `_process_ocr` 前置 PDF 文字層偵測;於逐頁處理後呼叫 `QualityAssessor` 與(低信心時)`ReviewQueueService`;處理前呼叫 `FewShotSelector`。

```python
async def analyze(self, file_contents: bytes, filename: str,
                  document_type: DocumentType, enable_llm: bool,
                  question: Optional[str] = None) -> dict:
    """新增:文字層偵測分支、few-shot 注入、信心度攔截、佇列入列"""
```

**相容性考量**: `transcript`/`contract` 預設行為不變;新流程以加法導入,`enable_llm` 語意保留。

### 外部 API 設計

#### API 端點 1: 分析(擴充既有)

**路徑**: `POST /api/v1/analyze`
**變更**: `document_type` 白名單改由 `ProcessorFactory.supported_types()` 動態產生,新增 `bill`、`repair_photo`;回應新增 `needs_review`、`review_item_id`、`field_confidences`。
**對應需求**: 1.1, 1.2, 4.1, 6.2

#### API 端點 2: 複核佇列

```
GET    /api/v1/review/queue?status=pending      # 列表
POST   /api/v1/review/{item_id}/claim           # 認領鎖定
POST   /api/v1/review/{item_id}/submit          # 提交校正
POST   /api/v1/review/{item_id}/release         # 釋出
```
**錯誤碼**: 409(已被他人認領,需求 6.7)、404、400。
**對應需求**: 6.2, 6.3, 6.4, 6.5, 6.7

#### API 端點 3: 評估與樣本

```
GET    /api/v1/evaluation/{document_type}       # 基準線與最新指標
POST   /api/v1/evaluation/{document_type}/run   # 以標註集重新評估
GET    /api/v1/samples/{document_type}          # 校正樣本/黃金範例
POST   /api/v1/samples/{document_type}/seed     # 種子範例冷啟動
```
**對應需求**: 7.4, 8.1, 8.3, 8.4, 9.2

---

## 配置與部署

### 配置管理

**新增/啟用環境變數**:
```bash
# 文件類型與門檻
OCR_QUALITY_THRESHOLD=0.8          # 復活生效,信心度攔截門檻(需求 6.6)
DOCUMENT_TYPES=transcript,bill,contract,repair_photo

# OCR 引擎(啟用既有 Paddle)
OCR_ENGINES=paddleocr,tesseract
OCR_PADDLEOCR_LANG=chinese_cht
OCR_ENABLE_PP_STRUCTURE=false       # 謄本增強,預設關(PoC 後開)

# LLM 層可插拔(本地優先)
LLM_PROVIDER=openai                 # openai | local_qwen
LLM_CLOUD_ENABLED=true              # 隱私硬需求時設 false
LOCAL_QWEN_ENDPOINT=                # 本地/EC2 vLLM 端點

# few-shot
FEWSHOT_MAX_EXAMPLES=5
```

**配置驗證**: `LLM_PROVIDER=local_qwen` 時 `LOCAL_QWEN_ENDPOINT` 必填;`LLM_CLOUD_ENABLED=false` 時禁止載入雲端 Provider(隱私保護)。

### 部署策略
**部署步驟**:
1. Alembic migration 建立三張新表。
2. (可選)部署本地 Qwen(vLLM)/PP-Structure;預設關閉,雲端 POC 可先不部署。
3. 部署後端與前端複核介面。
4. 種子範例匯入(`/samples/{type}/seed`)。

**回滾計劃**: 新表與新型別為加法,回滾僅需停用新端點與型別、還原 `document_type` 白名單;既有 `transcript`/`contract` 不受影響。

**監控指標**: 各類型 `needs_review` 比率(應隨時間下降)、LLM 呼叫次數/成本、單頁處理時間。

---

## 效能與可靠性

### 效能目標

| 指標 | 目標值 | 測量方式 |
|------|--------|---------|
| 單頁路由 + 本地 OCR(不含 LLM) | < 30 秒 | APM |
| 合約含文字層(略過 OCR) | 顯著低於全 OCR | 前後對比 |
| few-shot 注入額外 token | 受 `FEWSHOT_MAX_EXAMPLES` 上限控制 | 用量記錄 |

### 可靠性設計
**降級機制**:
- PP-Structure 失敗 → PaddleOCR + 規則抽取。
- 本地 VLM 不可用 → 依 `LLM_CLOUD_ENABLED` 決定切雲端或跳過。
- 認領衝突 → 回 409,前端提示重取佇列。

---

## 測試策略

### 單元測試
- [ ] `ProcessorFactory` 四型別路由與白名單動態產生
- [ ] `QualityAssessor.assess` 門檻分流(≥/< 0.8)
- [ ] `ReviewQueueService.claim` 併發:僅先認領者成功(需求 6.7)
- [ ] `FewShotSelector.select` 優先黃金範例、上限控制
- [ ] `EvaluationService` CER / 欄位準確率計算
- [ ] `LLMProvider` 可插拔:openai / local_qwen 注入

### 整合測試
- [ ] 端到端:上傳 → 低信心 → 進佇列 → 校正 → 樣本入庫 → 下次 few-shot 生效
- [ ] 合約含文字層 → 略過 OCR;純掃描 → 走 OCR(需求 4.1–4.3)
- [ ] `LLM_CLOUD_ENABLED=false` 時個資不外送(隱私驗證)
- [ ] 種子範例冷啟動後首份謄本準度基準

### 驗收測試
- [ ] 謄本經 few-shot 回灌後關鍵欄位準確率相對基準線提升(需求 8、成功標準 4)
- [ ] 四類文件路由正確率 > 95%
- [ ] 全流程地端運行、成本符合 < $15/月(信心度攔截式雲端呼叫)

---

## 風險與緩解

### 技術風險

| 風險 | 嚴重程度 | 緩解措施 |
|------|---------|---------|
| 繁中謄本無 benchmark,PP-Structure 實效未知 | 中 | 定位為增強項;規則+LLM Vision 先交付;PoC 驗證(research openQuestion 1) |
| 本地 Qwen 品質不足關鍵欄位 | 中 | few-shot 補足 + 低信心進複核;可切雲端 fallback |
| few-shot 範例膨脹致成本/延遲上升 | 中 | `FEWSHOT_MAX_EXAMPLES` 上限 + 相似度選取 + 去重 |
| 自我增強偏誤(錯誤範例回灌) | 高 | 僅「人工校正後」樣本可入庫;黃金範例人工標記;去重機制 |
| 評估資料洩漏(範例又當評估集) | 高 | 訓練池/holdout 以 `purpose` 欄位隔離,服務層+查詢層雙重保證(問題 3) |
| few-shot 注入他版型範例致變差 | 中 | 選取強制同 `layout_signature` 優先,精確相似度列 Phase 2 PoC(問題 2) |
| 複核佇列併發衝突 | 中 | 資料庫條件更新的悲觀鎖 |

### 營運風險

| 風險 | 嚴重程度 | 緩解措施 |
|------|---------|---------|
| 個資外送違反合規 | 高 | `LLM_CLOUD_ENABLED=false` 強制本地;預設 provider 可設 local |
| GPU 硬體/EC2 成本 | 中 | 本地 VLM 預設關;EC2 用完即關;量穩後轉地端機器 |
| 人工複核人力負荷 | 中 | 信心度攔截使人工量隨時間遞減;監控 needs_review 比率 |

---

## 實施里程碑(對齊需求分階段)

### Phase 1: 回饋迴路骨架(不需模型訓練)
- [ ] 統一 `DocumentType` 列舉,收斂型別體系(前置技術債)
- [ ] `QualityAssessor` 復活實作 + 門檻可配置(需求 6.1、6.6)
- [ ] 三張新表 migration + `ReviewQueueService`(需求 6)
- [ ] `CorrectionSampleService` + 前端複核介面(需求 7.1、7.2)
- [ ] `EvaluationService` 基準線(CER/欄位準確率)(需求 8)

### Phase 2: 文件類型路由 + few-shot(謄本先行)
- [ ] `LLMProvider` 可插拔重構(需求 7.3、隱私)
- [ ] 謄本啟用 PaddleOCR + 欄位抽取 + PP-Structure PoC(需求 2)
- [ ] `FewShotSelector` + 種子範例 + 回灌(需求 7.3–7.5)
- [ ] `BillProcessor`(需求 3)、合約文字層偵測(需求 4)
- [ ] `RepairPhotoProcessor` VLM POC(需求 5)

### Phase 3: fine-tune 決策(選配,不含訓練)
- [ ] `readiness_for_finetune` 判斷邏輯 + 標示(需求 9)

---

**文件版本**: 1.1(納入設計審查 3 項 Major 修正:①統一 analyze 契約分離 OCR/影像理解型 ②few-shot 同版型選取策略 ③評估集/訓練池防洩漏隔離)
**最後更新**: 2026-07-04
**設計狀態**: design-generated(待核准)
**需求追溯**: 完整對應 requirements.md 需求 1–9 與非功能需求
