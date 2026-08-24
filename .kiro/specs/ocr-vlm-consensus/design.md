# ocr-vlm-consensus - 技術設計文件

## 概述

### 設計目標

將既有「單一融合文字 → 純文字 LLM 校正」的辨識管線,升級為「多引擎候選 → 欄位層共識 → 雙模態校正」的混合架構,使系統在提升準確率的同時具備偵測隱形錯誤的能力。所有變更侷限於辨識管線內部,類型路由、信心度判定介面、人工複核佇列與 few-shot 回饋學習層維持不變。

### 設計原則

1. **共識優先於自評** — 信心度來源為多引擎結果的一致性,不依賴任何單一模型的自我評估
2. **保守預設** — 所有新行為以設定開關控制且預設關閉,既有路徑行為位元級不變
3. **介面向下相容** — 新增能力採「可選方法 + 預設實作」模式,既有子類別無需修改
4. **硬體無關的第一期** — 第一期核心價值不依賴 GPU;視覺語言引擎為可插拔的可選項
5. **降級不中斷** — 任一引擎、模型或影像編碼失敗皆降級處理並記錄事由,不使文件處理失敗

### 架構決策摘要

| # | 決策 | 選擇 | 理由 |
|---|---|---|---|
| 1 | 共識比對層級 | **欄位層**(非文字層) | 與既有 `QualityAssessor(ocr_confidence, field_confidences)` 介面天然吻合,免除變更 `_fuse_results()` 回傳型別的相容性風險 |
| 2 | 多引擎候選取得方式 | `OcrDocumentProcessor` 新增**可選**方法,預設實作包裝既有 `extract_text()` | 既有四個處理器無需修改即可運作(需求 6.6) |
| 3 | 雙模態校正的 Provider | 遷移至 `llm_service.providers.create_provider()` | 舊 `LLMService` 僅支援雲端;規避 PII 拒絕需本地選項(需求 2.6-2.7) |
| 4 | 視覺語言引擎定位 | 第一期為**離線評估工具**,非即時產品功能 | GPU 常駐成本無數據支撐 ⚠️ **原理由「評估可於開發機零成本完成」已於 2026-08-24 業主定案作廢**——開發機為 Apple Silicon,跑不了 `paddlepaddle`;執行環境改為待定,見 `tasks.md` 12.1 |
| 5 | 人機協作形態 | 即時回傳 + 欄位層標示 + 使用者當場確認 | 市面標準為欄位級分流;本專案使用者即最佳複核者 |
| 6 | 共識路徑的欄位抽取 | 各候選**僅規則式**抽取,LLM fallback **僅執行一次** | 避免 LLM 呼叫隨候選數倍增;使共識模式的 LLM 成本與現行相同 |
| 7 | 多引擎候選來源 | 複用 `extract_text_multi_engine()` 目前被丟棄的 `valid_results` | 引擎本已並行執行,停止丟棄即可,新增辨識成本為零 |

---

## 架構模式與邊界劃分

### 選定模式

**管道 + 策略 + 共識融合**(Pipeline + Strategy + Consensus Fusion)

沿用既有 `ocr_enhanced` 的管道模式與 `ProcessorFactory` 的策略註冊模式,在管道的「OCR」與「欄位提取」之間插入共識融合階段。

### 模組邊界圖

```
                    ┌─────────────────────────────────────────┐
                    │  即時路徑(面向使用者,秒級回應)          │
                    └─────────────────────────────────────────┘

  UploadView          analyze_service         OcrDocumentProcessor.analyze()
      │                     │                            │
      │  POST /analyze      │  ProcessorFactory          │
      ├────────────────────>├───────────────────────────>│
      │                     │                            │
      │                     │            ┌───────────────┴───────────────┐
      │                     │            │ 1. preprocess                 │
      │                     │            │ 2. extract_text_candidates()★ │
      │                     │            │      ├ PaddleOCR              │
      │                     │            │      └ Tesseract              │
      │                     │            │ 3. 各候選 → extract_fields()  │
      │                     │            │ 4. FieldConsensusResolver ★   │
      │                     │            │ 5. DualModalCorrector ★       │
      │                     │            └───────────────┬───────────────┘
      │                     │                            │
      │                     │         PageResult(field_confidences)
      │                     │<───────────────────────────┘
      │                     │
      │                     ├──> QualityAssessor ──> needs_review 判定
      │                     │         (介面不變)
      │<────────────────────┤
      │  結果 + 欄位信心度   │
      │                     │
  FieldConfirmPanel ★       │
      │ 使用者當場確認       │
      └────────────────────>├──> CorrectionSampleService ──> few-shot 回灌
                            │         (架構不變)
                            │
                    ┌───────┴─────────────────────────────────┐
                    │  離線路徑(不面向使用者)                  │
                    └─────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
  AnnotationImporter ★  BaselineRunner ★   VlmEngineAdapter ★
  (JSON → holdout)      (CER/準確率/觸發率)  (離線對照評估)
        │                   │                   │
        └──────────> EvaluationService <────────┘
                     (既有,介面不變)

  ★ = 本設計新增元件
```

### 邊界劃分理由

| 邊界 | 職責 | 不負責 |
|---|---|---|
| `extract_text_candidates()` | 產出多引擎候選文字 | 不決定哪個較好(交由共識層) |
| `FieldConsensusResolver` | 比對同名欄位、計算欄位信心度 | 不決定是否複核(交由 `QualityAssessor`) |
| `DualModalCorrector` | 以文字 + 影像校正 OCR 錯誤 | 不抽取欄位、不評估品質 |
| `QualityAssessor` | 依門檻判定是否需複核 | **介面完全不變**(需求 6.2) |
| `VlmEngineAdapter` | 將視覺語言模型包裝為引擎介面 | 第一期不進即時路徑 |
| `BaselineRunner` | 產出 CER、欄位準確率、觸發率 | 不修改辨識邏輯 |

關鍵邊界原則:**共識層只產生訊號,不做判定**。判定權完整保留在既有 `QualityAssessor`,確保需求 6.2 的介面不變承諾自然成立。

---

## 技術棧與對齊

### 核心技術選擇

| 技術領域 | 選擇 | 版本 | 理由 |
|---|---|---|---|
| 語言 | Python | 3.11+ | 專案標準 |
| 框架 | FastAPI | 0.115+ | 專案標準 |
| 型別 | TypedDict + Literal | stdlib | 對齊既有 `types.py` 慣例 |
| OCR 引擎(主) | PaddleOCR | 2.8.1 | 既有,繁中最強,x86 限定 |
| OCR 引擎(備) | Tesseract | 0.3.13 | 既有,ARM 可用,共識第二來源 |
| LLM 抽象 | `llm_service.providers` | 既有 | 支援本地與雲端可插拔 |
| 前端 | Vue 3 Composition API | 3.4+ | 專案標準 |

### 外部依賴

| 依賴 | 版本 | 用途 | 風險評估 |
|---|---|---|---|
| PaddleOCR-VL | 0.9B 系列 | 離線對照評估 | **中** — 須確認可否繞開 `paddlepaddle`(ARM64 上游缺陷) |
| Qwen2-VL | 2B / 7B | 本地雙模態校正、離線評估 | 低 — `LocalQwenProvider` **框架已實作但從未接線**:它只是對接 vLLM 端點的 HTTP client,自己不跑模型,且 `LOCAL_QWEN_ENDPOINT` 為空字串時建構子直接 raise |
| mlx-vlm | 最新 | ~~開發機離線評估~~ | **已排除**(2026-08-24):不在開發機建置,見 `tasks.md` 12.1 |

> ⚠️ **本表列的是候選與規劃,不是現況。** 截至 2026-08-24,生產路徑上**沒有任何 VLM 在運行**;
> 實際使用的 OCR 引擎只有 `OCR_ENGINES = ["paddleocr", "tesseract"]` 兩個
> (`backend/app/config.py`),LLM 走雲端 `openai` / `gpt-4o`。

### 與現有系統對齊

- **型別慣例**:新增型別一律以 `TypedDict` 定義並置於既有 `types.py`,與 `EngineResult`、`PageResult` 同層
- **列舉擴充**:`FusionMethod`、`OCREngineName` 為 `Literal` 別名,以**新增字面量**方式擴充,既有值不變
- **註冊模式**:引擎註冊比照 `ProcessorFactory.register_processor()` 的既有慣例
- **設定管理**:所有新設定項置於 `config.py` 的 `Settings`,採 `pydantic-settings`,預設值保守
- **降級慣例**:沿用既有 `logger.warning` + 回傳降級結果的模式(見 `analyze_service._upload_to_s3`)

---

## 元件與介面契約

### 元件 1: 多引擎候選提取(`OcrDocumentProcessor` 擴充)

**職責**: 於共識模式啟用時產出多個獨立引擎的辨識候選;未啟用時行為與既有完全一致。

**公開介面**:
```python
class OcrDocumentProcessor(DocumentProcessor):

    async def extract_text_candidates(
        self, image: Image.Image
    ) -> list[EngineResult]:
        """
        產出多引擎辨識候選。

        預設實作:包裝既有 extract_text(),回傳單一元素列表。
        此預設僅保證「既有子類別不會崩潰」,不足以啟動共識——
        因 extract_text() 回傳的是融合後的單一文字。
        真正的共識能力必須由子類別覆寫提供(見下方覆寫契約)。
        """
        text, confidence = await self.extract_text(image)
        return [{
            "engine": "default",
            "text": text,
            "confidence": confidence,
            "processing_time_ms": 0,
        }]
```

**⚠️ 覆寫契約(必要,否則共識機制不會運作)**

`EngineManager.extract_text_multi_engine()` **已經回傳各引擎原始結果**,但現行處理器將其丟棄:

```python
# transcript_processor.py 現況 — 第三個回傳值被丟棄
text, confidence, _engine_results = \
    await self.engine_manager.extract_text_multi_engine(image_array)
return text, confidence          # ← 多引擎候選在此消失
```

因此**每個 OCR 型處理器皆須覆寫** `extract_text_candidates()`,改為回傳該被丟棄的資料:

```python
class TranscriptProcessor(OcrDocumentProcessor):

    async def extract_text_candidates(
        self, image: Image.Image
    ) -> list[EngineResult]:
        """回傳各引擎原始候選(複用既有多引擎呼叫,不重跑引擎)"""
        image_array = self._to_bgr_array(image)   # 須先自 extract_text() 抽出此轉換
        _text, _conf, engine_results = \
            await self.engine_manager.extract_text_multi_engine(image_array)
        return engine_results
```

> 註:`_to_bgr_array()` 目前**不存在**——現行 `extract_text()` 內為內聯的 `np.array()` + BGR 通道交換。實作時須先將該段抽出為輔助方法,避免兩處重複。

**成本影響:零**。引擎本來就已並行執行,此覆寫僅停止丟棄既有結果,不新增任何辨識呼叫。

**適用範圍**: `TranscriptProcessor`、`ContractProcessor`、`BillProcessor`。`RepairPhotoProcessor` 繼承自 `ImageUnderstandingProcessor`,不走 OCR,不適用。

**型別定義**: 沿用既有 `EngineResult`(`ocr_enhanced/types.py`),不新增型別。

**依賴**: `EngineManager.extract_text_multi_engine()`(已回傳 `valid_results`)

**對應需求**: 4.1, 4.4, 6.6

---

### 元件 2: `FieldConsensusResolver`

**職責**: 接收多組欄位抽取結果,逐欄位比對一致性,產出合併欄位與欄位級信心度。不做複核判定。

**公開介面**:
```python
class FieldConsensusResolver:
    """欄位層共識解析器"""

    def __init__(self, normalizer: Optional["FieldNormalizer"] = None) -> None: ...

    def resolve(
        self,
        candidates: list["FieldCandidate"],
    ) -> "ConsensusResult":
        """
        逐欄位比對多個候選,產出共識結果。

        規則:
        - 全部一致 → 採該值,信心度取各引擎信心度之最小值(保守)
        - 不一致   → 採最高信心度候選之值,信心度壓低至不一致懲罰值
        - 僅單一候選 → 採該值,標記 consensus_available=False,不得回報高信心度
        """

    def normalize(self, field_name: str, value: Any) -> Any:
        """欄位值正規化後再比對(避免格式差異誤判為不一致)"""
```

**型別定義**:
```python
from typing import TypedDict, Optional, Any

class FieldCandidate(TypedDict):
    """
    單一引擎的欄位抽取結果。

    來源限定為「規則式(regex)抽取」——共識路徑不得對各候選觸發 LLM,
    否則 LLM 呼叫次數將隨候選數倍增(見流程 1 步驟 3/5 分工)。
    """
    engine: str
    fields: dict[str, Any]
    field_confidences: dict[str, float]
    extraction_method: Literal["regex"]   # 明示來源,防止誤用 LLM 路徑

class FieldAgreement(TypedDict):
    """單一欄位的共識狀態"""
    value: Any
    confidence: float
    agreed: bool                      # 各引擎是否一致
    engine_values: dict[str, Any]     # 保留各引擎原始值供複核對照(需求 4.4)

class ConsensusResult(TypedDict):
    """共識解析結果"""
    fields: dict[str, Any]
    field_confidences: dict[str, float]
    agreements: dict[str, FieldAgreement]
    consensus_available: bool         # 單引擎時為 False(需求 4.5)
```

**正規化規格表**(決定「一致」的判準)

「一致」定義為:**逐欄位正規化後字串相等**。各欄位型別的正規化規則如下,既有 `TranscriptPostprocessor` 已具備可重用實作:

| 欄位 | 型別 | 正規化規則 | 參考邏輯 |
|---|---|---|---|
| `land_number` 地號 | 識別碼 | 去空白;`O`/`o` → `0`;`l`/`I` → `1`;統一連字號 | `correct_field_formats()` 內地號 regex |
| `building_number` 建號 | 識別碼 | 同地號 | 同上 |
| `area` 面積 | 數值 | 去千分位逗號與單位後轉 `float` 比數值;容差 `0.01` | — |
| `rights_scope` 權利範圍 | 列舉字串 | 去空白;全形/半形統一 | `_clean_whitespace()` |
| `owner` 所有權人 | 人名 | 去空白;去除非中文標點 | `_clean_whitespace()` |
| `register_date` 登記日期 | 日期 | 民國紀年統一轉西元 `YYYY-MM-DD` 後比對 | `correct_field_formats()` 內民國日期 regex |
| `contract_amount` 合約金額 | 數值 | 去千分位與幣別符號;中文數字轉阿拉伯數字 | — |
| `signing_date` / `effective_date` | 日期 | 同登記日期 | 同登記日期 |
| 其他未列欄位 | 字串 | 去頭尾空白後字串相等 | — |

**⚠️ 「參考邏輯」不等於可直接重用**

`TranscriptPostprocessor.correct_field_formats()` 內的 `fix_land_number` 與 `fix_roc_date` 是**巢狀函式**,無法從外部呼叫,且簽章為 `(match)`(接收 regex match object)、語意為整段文字的 `re.sub` 格式統一——與「單一欄位值正規化」不同。

因此 `FieldNormalizer` 須**新建為獨立純函式模組**,僅**參考**上述既有實作的 regex 樣式與轉換規則,不可直接呼叫。`_clean_whitespace()` 為公開方法,可直接使用。

**設計理由**: 若不做正規化,`153.00` 與 `153`、`0221-0000` 與 `0221-0000␠` 會被誤判為不一致,使共識不一致率虛高、複核佇列塞爆。正規化為純函式且獨立於比對邏輯,便於單元測試(見測試策略)。

**依賴**: `TranscriptPostprocessor._clean_whitespace()`(可直接使用);其餘規則須新建。比對邏輯本身無外部依賴,為純函數

**對應需求**: 4.1, 4.2, 4.4, 4.5, 4.7

---

### 元件 3: `DualModalCorrector`

**職責**: 以「OCR 文字 + 頁面影像」雙模態校正 OCR 錯誤,取代既有 `LLMPostprocessor.correct_full_text()` 中被硬編碼停用的影像路徑。

**公開介面**:
```python
class DualModalCorrector:
    """雙模態 OCR 校正器"""

    def __init__(self, provider: Optional["LLMProvider"] = None) -> None:
        """provider 未提供時,由 create_provider() 依設定建立(支援本地)"""

    async def correct(
        self,
        ocr_text: str,
        doc_type: str,
        image_data: Optional[str] = None,
        few_shot: Optional[list[dict[str, Any]]] = None,
    ) -> "CorrectionResult":
        """
        校正 OCR 文字。

        image_data 為 None 或編碼失敗時降級為純文字校正並記錄事由(需求 2.3)。
        模型因內容政策拒絕時,回傳原始文字並記錄事由(需求 2.8)。
        """
```

**型別定義**:
```python
class CorrectionResult(TypedDict):
    text: str
    field_confidences: dict[str, float]   # 需求 2.2
    modality: Literal["dual", "text_only"] # 實際使用的模態
    degraded_reason: Optional[str]         # 降級事由(需求 2.3)
    refused: bool                          # 模型是否拒絕(需求 2.8)
    stats: dict[str, Any]
```

**依賴**: `llm_service.providers.create_provider()`(含 `LLM_CLOUD_ENABLED` 隱私守衛)

**對應需求**: 2.1, 2.2, 2.3, 2.6, 2.7, 2.8

**⚠️ 既有缺陷修正**: 現行 `_build_full_text_prompt()` 內含「請仔細查看上面提供的文件圖片」指示,但呼叫時傳 `image_data=None`。本元件須確保提示詞與實際傳入模態一致——純文字模態時不得保留查看圖片的指示。

---

### 元件 4: `VlmEngineAdapter`

**職責**: 將視覺語言模型包裝為符合既有引擎契約的介面,使其可作為共識來源之一。第一期僅用於離線評估。

**公開介面**:
```python
class VlmEngineAdapter:
    """視覺語言模型引擎轉接器"""

    def __init__(
        self,
        provider: Optional["LLMProvider"] = None,
        model_name: str = "",
    ) -> None: ...

    async def extract_text(self, image: np.ndarray) -> tuple[str, float]:
        """符合既有 OCREngine Protocol 契約"""

    async def run(self, image: np.ndarray) -> EngineResult:
        """回傳與 _run_paddleocr / _run_tesseract 一致的 EngineResult"""

    @property
    def is_available(self) -> bool:
        """引擎是否可用(非常駐部署時可能為 False,需求 3.8)"""
```

**型別定義**: 沿用既有 `EngineResult`;`OCREngineName` 擴充新字面量。

**依賴**: `llm_service.providers`;`EngineManager._standardize_confidence()`

**對應需求**: 3.1, 3.2, 3.4, 3.5, 3.8

---

### 元件 5: `AnnotationImporter`

**職責**: 將檔案型標註(`ground_truth.json`)轉換並匯入為 `CorrectionSample(purpose='holdout')`,銜接檔案型與資料庫型兩套評估體系。

**公開介面**:
```python
class AnnotationImporter:
    """標註資料匯入器"""

    def __init__(self, sample_service: "CorrectionSampleService") -> None: ...

    def import_from_file(
        self,
        file_path: str,
        document_type: "DocumentType",
        purpose: Literal["train", "holdout"] = "holdout",
    ) -> "ImportReport":
        """
        匯入標註檔為校正樣本。

        欄位值為 None 的項目視為未標註,計入 skipped 且不寫入。
        """
```

**型別定義**:
```python
class ImportReport(TypedDict):
    imported: int
    skipped: int
    skipped_refs: list[str]      # 未標註而略過的項目
    errors: list[str]
```

**依賴**: `CorrectionSampleService.save()`(已支援指定 `purpose`)

**對應需求**: 1.8, 1.9

---

### 元件 6: `BaselineRunner`

**職責**: 於指定引擎組態下對保留評估集執行辨識,產出 CER、欄位準確率與低信心攔截觸發率,並持久化為基準線。

**公開介面**:
```python
class BaselineRunner:
    """基準測試執行器"""

    def __init__(
        self,
        evaluation_service: "EvaluationService",
        min_samples: int = 30,
    ) -> None: ...

    async def run(
        self,
        document_type: "DocumentType",
        engine_profile: str,
        is_baseline: bool = False,
    ) -> "BaselineReport":
        """
        執行基準測試。

        Raises:
            InsufficientSamplesError: 樣本數低於門檻(需求 1.6)
            UnsupportedArchitectureError: 處理器架構不支援主力引擎(需求 1.10)
        """

    @staticmethod
    def check_environment() -> "EnvironmentCheck":
        """檢查執行環境是否可運行主力 OCR 引擎"""
```

**型別定義**:
```python
class EnvironmentCheck(TypedDict):
    architecture: str                 # 例: x86_64 / arm64
    primary_engine_available: bool
    reason: Optional[str]

class BaselineReport(TypedDict):
    document_type: str
    engine_profile: str
    cer: float
    field_accuracy: float
    sample_count: int
    review_trigger_rate: float        # 需求 1.5 / 5.4 的決策依據
    per_field_accuracy: dict[str, float]
    environment: EnvironmentCheck
```

**依賴**: `EvaluationService.evaluate()`、`record_baseline()`(既有)

**對應需求**: 1.3, 1.4, 1.5, 1.6, 1.10

---

### 元件 7: `CascadeCoordinator`

**職責**: 依信心度決定是否觸發第二引擎,並統計升級觸發率與成本效益。

**公開介面**:
```python
class CascadeCoordinator:
    """分層處理協調器"""

    def __init__(self, threshold: float, enabled: bool = False) -> None: ...

    def should_escalate(self, first_pass: "ConsensusResult") -> bool:
        """判斷是否需觸發第二引擎"""

    def record(self, escalated: bool, cost: float) -> None:
        """記錄觸發與成本"""

    def efficiency_report(self) -> "CascadeEfficiency":
        """產出成本效益報告;觸發率超標時標記不具效益(需求 5.4)"""
```

**型別定義**:
```python
class CascadeEfficiency(TypedDict):
    total_documents: int
    escalated_count: int
    escalation_rate: float
    is_cost_effective: bool
    recommendation: str
```

**依賴**: `ApiUsageLog`(成本記錄)

**對應需求**: 5.1, 5.2, 5.3, 5.4, 5.6

---

### 元件 8: `FieldConfirmPanel`(前端)

**職責**: 於結果頁標示低信心欄位,供使用者當場確認或修正;修正結果回寫為校正樣本。

**公開介面**:
```typescript
interface FieldConfirmProps {
  fields: Record<string, unknown>
  fieldConfidences: Record<string, number>
  agreements: Record<string, FieldAgreement>
  threshold: number
}

interface FieldAgreement {
  value: unknown
  confidence: number
  agreed: boolean
  engineValues: Record<string, unknown>
}

interface FieldConfirmEmits {
  (e: 'confirm', field: string, value: unknown): void
  (e: 'submitAll', corrections: Record<string, unknown>): void
}
```

**依賴**: `services/api.ts`;既有 `types/document.ts`

**對應需求**: 對應決策 5(人機協作形態);支援 4.3 的複核導入

---

## 資料模型與流程

### 資料模型

#### Model 1: `ApiUsageLog`(擴充既有)

**用途**: 記錄分層升級與成本歸因。

**Schema 變更**:
```python
class ApiUsageLog(Base):
    __tablename__ = "api_usage_logs"

    # --- 既有欄位不變 ---
    # endpoint, document_type, total_pages, llm_used,
    # llm_cost, processing_time_ms

    # --- 新增(皆為 nullable,向後相容) ---
    engine_profile: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    cascade_escalated: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    consensus_available: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
```

**索引策略**:
- `idx_usage_type_created` on `(document_type, created_at)` — 用於觸發率與成本彙總查詢

**遷移考量**:
- 新增三個 nullable 欄位,既有資料不需回填
- 需一份 Alembic migration;既有兩份遷移檔(`d18dbadf87e7`、`f1a2b3c4d5e6`)之後接續

> **其餘資料模型不變**。`CorrectionSample`、`EvaluationRecord`、`ReviewQueueItem` 現有結構已足以支撐需求 1 與需求 4,不需遷移。共識資訊屬執行期資料,隨回應輸出,不落庫。

---

### 資料流程

**流程 1: 即時共識辨識(需求 4 主流程)**

```
[上傳]
  → [1. preprocess: 去浮水印 / 二值化]
  → [2. extract_text_candidates: PaddleOCR ∥ Tesseract]
  → [3. 各候選「規則式」欄位抽取 ── 零 LLM 成本]
  → [4. FieldConsensusResolver.resolve: 正規化後逐欄位比對]
  → [5. LLM 欄位補全 fallback ── 僅對共識結果執行「一次」]
  → [6. DualModalCorrector: 文字 + 影像校正(可選)]
  → [7. 組裝 PageResult(field_confidences / overall_confidence)]
  → [8. QualityAssessor.assess: 介面不變]
  → [9. 立即回傳 + 低信心欄位標示]
  → [結束]
```

**步驟說明**:
1. **預處理** — 輸入原始頁面影像,輸出增強影像。既有邏輯不變
2. **多引擎辨識** — 輸入增強影像,輸出 `list[EngineResult]`。共識模式關閉時僅一個元素
3. **規則式欄位抽取** — 對每個候選文字**僅執行 regex 抽取**,輸出 `list[FieldCandidate]`。**此步驟不得觸發 LLM**
4. **共識比對** — 輸入候選列表,依正規化規格表比對,輸出 `ConsensusResult`。不一致欄位信心度被壓低
5. **LLM 欄位補全** — 僅在規則式抽取有欄位缺漏時,對**共識後的單一結果**執行一次 LLM fallback
6. **雙模態校正** — 輸入文字與影像,輸出校正文字與欄位信心度;失敗降級為純文字
7. **結果組裝** — 共識信心度寫入 `PageResult.field_confidences`
8. **品質判定** — **完全沿用既有 `QualityAssessor`,不傳入任何新參數**
9. **回傳** — 不等待任何人工介入(依決策 5)

**⚠️ 步驟 3 與 5 的分工(成本關鍵)**

既有 `RegexFieldExtractor.extract()` 內部依序執行 regex 抽取與 LLM fallback。若共識路徑對每個候選直接呼叫 `extract()`,**LLM 呼叫次數將隨候選數倍增**——依 `tech.md` 每頁 $0.02-0.03,雙候選即 $0.04-0.06/頁,直接衝擊 $15/月 約束。

因此共識路徑必須拆用兩個階段:

| 階段 | 使用 | 執行次數 | LLM 成本 |
|---|---|---|---|
| 步驟 3 各候選抽取 | `extract(text, use_llm_fallback=False)` | N 個候選 | **$0** |
| 步驟 5 缺漏補全 | `extract(text, image_data=..., use_llm_fallback=True)` | **僅 1 次** | 與現行相同 |

既有 `RegexFieldExtractor.extract()` 的 LLM 觸發條件為 `use_llm_fallback and needs and image_data` **三者皆成立**,因此步驟 3 只要不傳 `use_llm_fallback`(預設 `False`)即為純 regex 路徑。**無需變更任何既有方法的可見性**,僅調整呼叫參數。

**淨效果**: 共識模式的 LLM 成本與現行單引擎模式**相同**,增加的僅是 regex 比對的 CPU 時間。

**錯誤處理**:

| 錯誤情況 | 處理方式 | 需求 |
|---|---|---|
| 單一引擎失敗 | 排除該候選,以其餘引擎繼續;僅剩一個時標記 `consensus_available=False` | 3.5, 4.5 |
| 全部引擎失敗 | 回傳空文字與零信心度,標記需複核 | 3.5 |
| 影像編碼失敗 | 降級純文字校正,記錄 `degraded_reason` | 2.3 |
| 模型拒絕處理 | 保留原始辨識文字,標記 `refused=True` | 2.8 |
| 視覺語言引擎離線 | 以既有引擎完成,保留可重處理識別資訊 | 3.8, 3.9 |

---

**流程 2: 離線基準評估(需求 1 主流程)**

```
[標註 JSON]
  → [1. AnnotationImporter: 轉為 CorrectionSample(purpose=holdout)]
  → [2. BaselineRunner.check_environment: 架構檢查]
       ├─ 不支援 → [拒絕執行,提示所需環境] → [結束]
       └─ 支援 ↓
  → [3. 樣本數檢查]
       ├─ 不足 → [拒絕標記為正式基準線] → [結束]
       └─ 足夠 ↓
  → [4. 以指定引擎組態辨識 holdout 全集]
  → [5. EvaluationService.evaluate: CER + 欄位準確率]
  → [6. 計算低信心攔截觸發率]
  → [7. record_baseline 持久化]
  → [結束: BaselineReport]
```

**錯誤處理**:
- 架構不支援主力引擎 → 拋出 `UnsupportedArchitectureError`,**不得產出無效基準**(需求 1.10)
- 樣本數低於門檻 → 拋出 `InsufficientSamplesError`(需求 1.6)
- 標註欄位為 `None` → 計入 `skipped`,不納入評估

---

## 整合點與 API 設計

### 內部整合點

#### 整合點 1: 與 `QualityAssessor` 整合

**整合方式**: 共識結果寫入 `PageResult.field_confidences`,`QualityAssessor` 以既有簽章讀取,**不新增任何參數**。

**介面定義**:
```python
# 呼叫方式與現行完全一致
decision: QualityDecision = QualityAssessor().assess(
    ocr_confidence=page["overall_confidence"],
    field_confidences=page["field_confidences"],   # 共識信心度由此進入
)
```

**相容性考量**: `QualityAssessor.assess()` 採「取最差值」策略,共識壓低的欄位信心度會自然反映於 `overall_confidence` 與 `low_confidence_fields`。**零介面變更**(需求 6.2)。

---

#### 整合點 2: 與 `EngineManager` 整合

**整合方式**: 新增 `cross_check` 融合模式與視覺語言引擎註冊項,皆以新增字面量方式擴充。

**介面定義**:
```python
# ocr_enhanced/types.py — 擴充既有 Literal,既有值不變
FusionMethod = Literal["best", "weighted", "vote", "smart", "cross_check"]
OCREngineName = Literal["paddleocr", "tesseract", "textract", "paddleocr_vl", "qwen_vl"]
```

**相容性考量**: `_fuse_results()` 的回傳型別 `tuple[str, float]` **不變**;`cross_check` 於欄位層執行,不經過該方法。既有四種融合模式行為位元級不變(需求 4.7)。

---

#### 整合點 3: 與 `CorrectionSampleService` 整合

**整合方式**: 使用者當場確認的修正,經既有 `save(purpose='train')` 回灌 few-shot;`AnnotationImporter` 以 `purpose='holdout'` 匯入評估集。

**相容性考量**: `list_for_fewshot()` 硬性僅回 `train`,匯入的 holdout 樣本不會洩漏至 few-shot(需求 1.7,既有機制已保證)。

---

### 外部 API 設計

#### API 端點 1: 統一分析(擴充既有)

**路徑**: `POST /api/v1/analyze`

**請求格式**: **不變**(維持 `file`、`document_type`、`enable_llm`、`question` 等既有參數)

**回應格式**(新增欄位皆為選填,既有欄位語意不變):
```json
{
  "file_name": "謄本.pdf",
  "document_type": "transcript",
  "total_pages": 1,
  "pages": [{
    "page_number": 1,
    "field_confidences": { "地號": 0.42, "所有權人": 0.95 },
    "consensus": {
      "available": true,
      "agreements": {
        "地號": {
          "value": "0221-0000",
          "confidence": 0.42,
          "agreed": false,
          "engine_values": {
            "paddleocr": "0221-0000",
            "tesseract": "0221-OOOO"
          }
        }
      }
    }
  }],
  "needs_review": true,
  "review_item_id": null
}
```

**錯誤碼**: 沿用既有 `UNSUPPORTED_FILE_TYPE`、`UNSUPPORTED_DOCUMENT_TYPE`、`INCOMPATIBLE_FILE_TYPE`,不新增。

**對應需求**: 4.4, 6.5

---

#### API 端點 2: 標註匯入

**路徑**: `POST /api/v1/samples/{document_type}/import`

**請求格式**:
```json
{ "file_path": "backend/tests_all/fixtures/ground_truth.json", "purpose": "holdout" }
```

**回應格式**:
```json
{ "imported": 28, "skipped": 2, "skipped_refs": ["合約A.pdf"], "errors": [] }
```

**錯誤碼**: 400 文件類型不支援 / 404 檔案不存在 / 422 格式錯誤

**對應需求**: 1.8

---

#### API 端點 3: 基準測試執行

**路徑**: `POST /api/v1/evaluation/{document_type}/baseline`

**請求格式**:
```json
{ "engine_profile": "paddleocr+tesseract", "is_baseline": true }
```

**回應格式**:
```json
{
  "cer": 0.083, "field_accuracy": 0.91, "sample_count": 30,
  "review_trigger_rate": 0.23,
  "environment": { "architecture": "x86_64", "primary_engine_available": true }
}
```

**錯誤碼**:
- `409 INSUFFICIENT_SAMPLES` — 樣本數低於門檻(需求 1.6)
- `409 UNSUPPORTED_ARCHITECTURE` — 架構不支援主力引擎(需求 1.10)

**對應需求**: 1.3, 1.4, 1.5, 1.6, 1.10

---

## 配置與部署

### 配置管理

**新增環境變數**(全部預設保守,不改變既有行為):
```bash
# 共識信心度(需求 4)
OCR_CONSENSUS_ENABLED=false          # 預設關閉;啟用後才走多引擎候選
OCR_CONSENSUS_DISAGREE_PENALTY=0.3   # 不一致時的信心度懲罰值(0-1)

# 雙模態校正(需求 2)
LLM_DUAL_MODAL_ENABLED=false         # 預設關閉;啟用需確認 Provider 支援影像

# 分層成本控制(需求 5)
CASCADE_ENABLED=false                # 預設關閉
CASCADE_ESCALATE_THRESHOLD=0.8       # 低於此信心度才觸發第二引擎
CASCADE_MAX_ESCALATION_RATE=0.3      # 超過此觸發率則提示不具效益

# 基準測試(需求 1)
BASELINE_MIN_SAMPLES=30              # 低於此樣本數拒絕標記為正式基準線
```

**配置驗證**:
- `OCR_CONSENSUS_ENABLED=true` 但 `OCR_ENGINES` 僅一個引擎 → 啟動時警告,執行期標記 `consensus_available=False`
- `LLM_DUAL_MODAL_ENABLED=true` 且 `LLM_CLOUD_ENABLED=true` → 啟動時警告個資外送風險
- `CASCADE_ENABLED=true` 但無基準觸發率數據 → 啟動時警告尚未驗證成本效益

---

### 部署策略

**部署步驟**:
1. 執行 Alembic 遷移(新增 `ApiUsageLog` 三個 nullable 欄位)
2. 部署後端服務(所有新設定預設關閉,行為與現行一致)
3. 驗證健康狀態與既有測試套件全綠
4. 於 x86 環境匯入標註並執行基準測試,取得基準線
5. 逐項開啟新設定,每次開啟後重跑基準對照

**回滾計劃**:
- 設定層回滾:將新增設定改回 `false` 即恢復現行行為,無需重新部署
- 程式碼回滾:遷移僅新增 nullable 欄位,舊版程式碼可直接運行於新 schema

**監控指標**:
- 各文件類型 `needs_review` 比率(應隨校正累積下降)
- 共識不一致率(過高代表引擎品質差異大或門檻需調整)
- `consensus_available=False` 比率(過高代表引擎經常失敗)
- 分層升級觸發率(超過 `CASCADE_MAX_ESCALATION_RATE` 應檢討)

---

## 效能與可靠性

### 效能目標

| 指標 | 目標值 | 測量方式 |
|---|---|---|
| 單頁辨識(不含 LLM) | < 30 秒 | `ApiUsageLog.processing_time_ms` |
| 共識模式相對單引擎的耗時增幅 | < 1.5 倍 | 基準測試對照 |
| **共識模式相對單引擎的 LLM 成本增幅** | **0%(不得增加)** | `ApiUsageLog.llm_cost` 對照 |
| 未觸發升級的文件處理時間 | 不劣於現行基準 | 基準測試對照 |
| 記憶體用量 | < 1.5 GB | 容器監控 |

> 共識模式的額外開銷**僅為 regex 比對的 CPU 時間**(引擎本已並行執行,欄位抽取採零成本的規則式路徑)。
> LLM 成本增幅為 0% 是硬性約束——若實測顯示增加,代表步驟 3/5 的分工未正確實作。

### 可靠性設計

**錯誤處理策略**:
- 預處理失敗 → 降級為原始影像
- 單一引擎失敗 → 排除該候選,以其餘引擎繼續
- 全部引擎失敗 → 回傳零信心度並標記需複核
- 影像編碼失敗 → 降級純文字校正
- 模型拒絕 → 保留原始辨識文字

**降級機制**:
```
共識模式 ─失敗→ 單引擎模式 ─失敗→ 零信心度 + 強制複核
雙模態校正 ─失敗→ 純文字校正 ─失敗→ 原始 OCR 文字
視覺語言引擎 ─離線→ 既有 CPU 引擎(標記可重處理)
```

**核心不變量**: 信心度回報**不得高於**實際可信程度。單引擎時標記 `consensus_available=False` 而非回報高信心度(需求 4.5)。

---

## 測試策略

### 單元測試

**測試範圍**:
- [ ] `FieldConsensusResolver`:全一致 / 部分不一致 / 全不一致 / 單候選 四種情境
- [ ] `FieldConsensusResolver.normalize`:逐欄位型別驗證,格式差異不得誤判為不一致
      - 識別碼:`0221-0000` vs `0221-OOOO` vs `0221-0000␠` → 一致
      - 數值:`153.00` vs `153` vs `153.00平方公尺` → 一致
      - 日期:`民國075年05月27日` vs `075/05/27` → 一致
      - 真實差異:`0221-0000` vs `0221-0001` → **不一致**(不得因正規化而誤判為一致)
- [ ] **共識路徑不觸發 LLM**:各候選抽取階段的 LLM 呼叫次數為 0
- [ ] **處理器覆寫生效**:`extract_text_candidates()` 於多引擎組態下回傳 > 1 個候選
- [ ] `DualModalCorrector`:雙模態成功 / 影像失敗降級 / 模型拒絕 三路徑
- [ ] `VlmEngineAdapter`:結果符合 `EngineResult` 契約;不可用時 `is_available=False`
- [ ] `AnnotationImporter`:正常匯入 / `None` 欄位略過 / 格式錯誤
- [ ] `BaselineRunner`:樣本不足拒絕 / 架構不支援拒絕
- [ ] `CascadeCoordinator`:觸發判斷 / 觸發率統計 / 超標提示
- [ ] `extract_text_candidates` 預設實作:既有子類別無需修改即可運作

**測試工具**: pytest, pytest-asyncio

---

### 整合測試

**測試場景**:
- [ ] 端到端共識辨識(謄本 JPG / PDF)
- [ ] 共識模式關閉時,回應與現行版本一致(位元級對照)
- [ ] 停用雲端設定下的全本地路徑
- [ ] 單一引擎可用時的 `consensus_available=False` 標記
- [ ] 統一分析端點回應結構向後相容
- [ ] 複核佇列完整流程(入列→認領→提交→回灌)行為不變
- [ ] 修繕照片影像理解路徑未受影響

**測試資料**: `data/` 下真實謄本與 `data/contracts/` 11 份合約

**迴歸門檻**: 既有 `backend/tests/unit/` 57 個測試檔 + `integration/` 4 個整合測試須全數通過(需求 6.7)

---

### 驗收測試

**成功標準**:
- [ ] 關鍵欄位(地號、建號、面積、金額)準確率 ≥ 95%(需求 成功標準 1)
- [ ] 整體 OCR 辨識準確率 ≥ 85%(需求 成功標準 2)
- [ ] 低共識信心度樣本的實際錯誤率**顯著高於**高信心度樣本(需求 4.6)
- [ ] 未被攔截的錯誤欄位比率不高於現行基準(需求 成功標準 3)
- [ ] 月營運成本 < $15(需求 成功標準 4)
- [ ] `LLM_CLOUD_ENABLED=false` 下完整流程可全本地運行(需求 成功標準 5)

---

## 風險與緩解

### 技術風險

| 風險 | 嚴重程度 | 緩解措施 |
|---|---|---|
| 主力 OCR 引擎於 ARM64 崩潰 | **高** | 基準測試與生產一律 x86;`BaselineRunner.check_environment()` 主動拒絕(需求 1.10) |
| 雲端模型 PII 拒絕 | **高** | 雙模態走本地 Provider;拒絕時保留原始文字(需求 2.8) |
| 兩引擎錯誤高度相關,共識失效 | **高** | 需求 4.6 要求以標註集實證相關性;不成立則重新設計 |
| 共識過度敏感導致複核量暴增 | 中 | `OCR_CONSENSUS_DISAGREE_PENALTY` 可調;監控不一致率 |
| 共識模式耗時倍增 | 中 | 分層機制(需求 5);效能目標設 < 2 倍 |
| 欄位正規化不足導致誤判不一致 | 中 | `normalize()` 獨立可測;納入單元測試 |

### 營運風險

| 風險 | 嚴重程度 | 緩解措施 |
|---|---|---|
| 標註成果遺失 | **高** | 需求 1.9 要求版控存放;標註前先完成匯入機制 |
| 分層反而增加成本 | 中 | 需求 5.4 主動提示;綁定實測觸發率 |
| 第一期 VLM 對使用者無感 | 低 | 明確定位為評估工具;第一期價值來自共識與當場確認 |
| $15 成本基線本身可能已超出 | 中 | 需確認實際帳單;超出則重訂驗收數字 |

---

## 實施里程碑

### Phase 1: 基準與共識(不需 GPU,新增基礎設施支出 $0)

**1a. 標註基礎建設**(阻塞後續全部)
- [ ] `AnnotationImporter` 完成,標註存放位置定案(需求 1.8, 1.9)
- [ ] `BaselineRunner.check_environment()` 完成(需求 1.10)
- [ ] 於 x86 環境跑通現行引擎基準,取代 placeholder(需求 1.3, 1.4)
- [ ] 標註補齊至統計可用量(**人工前置作業**)

**1b. 欄位層共識**(不受硬體牽制)
- [ ] `extract_text_candidates()` 預設實作(需求 6.6)
- [ ] **各 OCR 型處理器覆寫 `extract_text_candidates()`,回傳現行被丟棄的 `valid_results`**
      ⚠️ 未完成此項則共識機制**不會啟動**,且所有單元測試仍會通過
- [ ] 自 `extract_text()` 抽出影像轉 BGR 陣列的輔助方法,供兩處共用
- [ ] 共識路徑改用 `extract(use_llm_fallback=False)`(防 LLM 成本倍增,無需變更既有方法可見性)
- [ ] **新建** `FieldNormalizer` 純函式模組(參考既有 regex 樣式;巢狀函式不可直接重用)
- [ ] `FieldConsensusResolver` 完成(需求 4.1-4.5, 4.7)
- [ ] 共識與實際錯誤率的相關性實證(需求 4.6)
- [ ] **端到端驗證共識確實啟動**:`consensus_available=True` 且不一致欄位信心度確被壓低
- [ ] **驗證 LLM 成本零增幅**:共識模式與單引擎模式的 `llm_cost` 相同
- [ ] 既有 57 個單元測試全數通過(需求 6.7)

**1c. 雙模態校正**
- [ ] `LLMPostprocessor` 遷移至 `create_provider()`(需求 2.6, 2.7)
- [ ] `DualModalCorrector` 完成,含降級與拒絕路徑(需求 2.1-2.3, 2.8)
- [ ] 提示詞與實際模態一致性修正(既有缺陷)

**1d. 使用者當場確認**
- [ ] `FieldConfirmPanel` 前端元件完成
- [ ] 修正回灌 few-shot 驗證(需求 6.4)

---

### Phase 2: 視覺語言引擎(依 Phase 1 數據決定是否執行)

**前置決策點**: Phase 1 基準顯示 CPU 雙引擎已達 95% 關鍵欄位準確率 → **本階段可不執行**

- [ ] `VlmEngineAdapter` 完成(需求 3.1-3.5)
- [ ] 於開發機以 MLX 完成離線對照評估(零成本)
- [ ] 非常駐部署的雙軌行為(需求 3.8, 3.9)
- [ ] `CascadeCoordinator` 完成,門檻依實測觸發率設定(需求 5)
- [ ] GPU 與成本上限決策(依 Phase 1 增益數據)

---

**文件版本**: 1.2.0
**最後更新**: 2026-08-04
**設計狀態**: design-generated(待審核)
**需求追溯**: 完整對應 requirements.md 需求 1-6 及非功能性需求

**v1.1.0 變更**(依 `/kiro:validate-design` NO-GO 審查意見修訂):
- **修正 Critical** — 元件 1 補上處理器覆寫契約。原設計的預設實作僅包裝 `extract_text()`(融合後單一文字),共識機制實際不會啟動;改為要求各 OCR 型處理器覆寫並回傳 `extract_text_multi_engine()` 目前被丟棄的 `valid_results`,新增辨識成本為零
- **修正 Major** — 流程 1 步驟 3/5 分離規則式抽取與 LLM fallback,避免 LLM 呼叫隨候選數倍增;新增「LLM 成本零增幅」為硬性效能約束
- **修正 Major** — 元件 2 補上逐欄位型別的正規化規格表,明訂「一致」判準,並標示可重用的既有 `TranscriptPostprocessor` 方法
- 架構決策摘要新增第 6、7 項;Phase 1b 新增四項任務;測試策略新增三類驗證
