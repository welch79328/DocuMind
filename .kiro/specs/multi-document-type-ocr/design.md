# multi-document-type-ocr - 技術設計文件

## 概述

### 設計目標

將現有的單一文件類型（謄本）OCR 系統擴展為通用的多文件類型 OCR 平台，透過策略模式實現文件類型的可插拔處理，支援謄本、合約等不同類型文件的專門化辨識與結構化資訊提取，同時保持 API 向後兼容性與系統可擴展性。

### 設計原則

1. **開放封閉原則（OCP）**: 對擴展開放，對修改封閉 - 新增文件類型無需修改核心代碼
2. **策略模式**：每種文件類型作為獨立處理策略，可互換且獨立演進
3. **型別安全**：使用 Python type hints 和 TypedDict 確保型別正確性
4. **向後兼容**：保持現有謄本 API 介面與回應格式完全不變
5. **可測試性**：所有元件提供清晰介面，支援單元測試與整合測試

### 架構決策摘要

1. **採用策略模式 + 抽象基類**：定義 `DocumentProcessor` 抽象基類，各文件類型實作獨立處理器
2. **工廠模式選擇處理器**：`ProcessorFactory` 根據 `document_type` 參數動態選擇對應處理器
3. **混合資訊提取方法**：合約關鍵欄位提取結合正則表達式（快速、低成本）與 LLM（高準確率、備選）
4. **統一基本回應 + 類型特定區塊**：所有類型返回基本結構，類型特定資訊放在 `structured_data` 區塊
5. **API 參數向後兼容**：新增可選參數 `document_type`，預設值為 `"transcript"` 保持現有行為

---

## 架構模式與邊界劃分

### 選定模式

**策略模式（Strategy Pattern）+ 工廠模式（Factory Pattern）**

策略模式定義一系列文件處理算法，將每個算法封裝起來並使它們可以互換。工廠模式負責根據文件類型參數選擇對應的處理策略。

### 模組邊界圖

```
┌─────────────────────────────────────────────────────────────────┐
│                     API Layer (FastAPI)                         │
│  /api/v1/ocr/test                                               │
│  ├─ document_type: Optional[str] = "transcript"                 │
│  └─ enable_llm: bool = True                                     │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                  ProcessorFactory (工廠)                        │
│  ┌──────────────────────────────────────────────────┐          │
│  │ get_processor(document_type: str)                │          │
│  │   → DocumentProcessor                             │          │
│  └──────────────────────────────────────────────────┘          │
└────────────┬────────────────────────┬───────────────────────────┘
             │                        │
    ┌────────▼──────────┐    ┌───────▼─────────┐
    │  TranscriptProcessor│    │ ContractProcessor│
    │  (謄本處理器)       │    │ (合約處理器)      │
    └────────┬──────────┘    └───────┬─────────┘
             │                        │
             │ implements             │ implements
             │                        │
    ┌────────▼────────────────────────▼─────────┐
    │      DocumentProcessor (抽象基類)         │
    │  ┌──────────────────────────────────┐    │
    │  │ + preprocess(image) → Image      │    │
    │  │ + extract_text(image) → str      │    │
    │  │ + postprocess(text) → str        │    │
    │  │ + extract_fields(text) → dict    │    │
    │  │ + format_response(...) → dict    │    │
    │  └──────────────────────────────────┘    │
    └───────────────┬──────────────────────────┘
                    │ 依賴
                    ▼
    ┌────────────────────────────────────────────┐
    │      ocr_enhanced/ (既有模組)              │
    │  ┌─────────────────────────────────────┐  │
    │  │  - TranscriptPreprocessor           │  │
    │  │  - EngineManager                    │  │
    │  │  - TranscriptPostprocessor          │  │
    │  │  - LLMPostprocessor                 │  │
    │  └─────────────────────────────────────┘  │
    └────────────────────────────────────────────┘
                    │ 使用
                    ▼
    ┌────────────────────────────────────────────┐
    │      ContractFieldExtractor (新模組)      │
    │  ┌─────────────────────────────────────┐  │
    │  │  - 正則表達式模式庫                  │  │
    │  │  - LLM 輔助提取                      │  │
    │  │  - 信心度評分                        │  │
    │  └─────────────────────────────────────┘  │
    └────────────────────────────────────────────┘
```

### 邊界劃分理由

**API 層 (ocr_test.py)**:
- 職責：HTTP 請求處理、參數驗證、回應格式化
- 邊界：不包含任何業務邏輯，僅委派給處理器

**ProcessorFactory 層**:
- 職責：根據 `document_type` 選擇對應的處理器
- 邊界：不執行處理邏輯，僅負責創建與選擇

**DocumentProcessor 抽象基類**:
- 職責：定義文件處理的標準流程（模板方法）
- 邊界：提供共用邏輯，具體實作由子類別完成

**TranscriptProcessor / ContractProcessor**:
- 職責：實作特定文件類型的處理邏輯
- 邊界：封裝該類型的所有特殊處理，不影響其他類型

**ocr_enhanced/ 套件**:
- 職責：提供 OCR 處理的基礎模組（預處理、引擎、後處理）
- 邊界：不感知文件類型，作為可重用的工具層

**ContractFieldExtractor**:
- 職責：從合約文字中提取結構化欄位
- 邊界：專注於合約資訊提取，不處理其他類型

---

## 技術棧與對齊

### 核心技術選擇

| 技術領域 | 選擇 | 版本 | 理由 |
|---------|------|------|------|
| 語言 | Python | 3.11+ | 專案標準，型別提示支援完善 |
| 框架 | FastAPI | 0.115+ | 專案標準，自動 API 文檔生成 |
| 型別檢查 | typing, TypedDict | Python 內建 | 確保型別安全，IDE 支援良好 |
| OCR 引擎 | Tesseract, PaddleOCR | 既有配置 | 已整合在 `ocr_enhanced/` 套件 |
| LLM 服務 | OpenAI GPT-4o | 1.54.5 | 支援視覺輸入，適合 OCR 修正 |
| 正則表達式 | re | Python 內建 | 合約欄位提取的基礎工具 |

### 外部依賴

| 依賴 | 版本 | 用途 | 風險評估 |
|------|------|------|---------|
| openai | 1.54.5 | LLM 輔助資訊提取與 OCR 修正 | 低風險（已在使用） |
| anthropic | 0.39.0 | 備選 LLM 服務 | 低風險（已配置） |
| PyMuPDF (fitz) | 1.24.13 | PDF 頁面提取與處理 | 低風險（已在使用） |

### 與現有系統對齊

**對齊策略**:
1. **重用既有模組**：`TranscriptPreprocessor`, `EngineManager`, `TranscriptPostprocessor` 等保持不變
2. **擴展而非修改**：新增 `DocumentProcessor` 抽象層，現有邏輯封裝為 `TranscriptProcessor`
3. **保持 API 契約**：`/api/v1/ocr/test` 端點介面向後兼容
4. **統一配置管理**：新增的配置項整合到現有 `config.py` 中

---

## 元件與介面契約

### 元件 1: DocumentProcessor (抽象基類)

**職責**: 定義文件處理的標準流程與介面契約

**公開介面**:
```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from PIL import Image

class DocumentProcessor(ABC):
    """
    文件處理器抽象基類

    定義所有文件類型處理器必須實作的介面
    """

    @abstractmethod
    async def preprocess(self, image: Image.Image) -> Image.Image:
        """
        預處理圖像

        Args:
            image: PIL Image 物件

        Returns:
            處理後的 Image 物件
        """
        pass

    @abstractmethod
    async def extract_text(self, image: Image.Image) -> tuple[str, float]:
        """
        提取文字

        Args:
            image: 預處理後的 Image 物件

        Returns:
            (文字內容, OCR 信心度)
        """
        pass

    @abstractmethod
    async def postprocess(
        self,
        text: str,
        confidence: float,
        image_data: Optional[str] = None
    ) -> tuple[str, Dict[str, Any]]:
        """
        後處理文字

        Args:
            text: 原始 OCR 文字
            confidence: OCR 信心度
            image_data: base64 編碼的圖像（可選，供 LLM 使用）

        Returns:
            (修正後文字, 處理統計)
        """
        pass

    @abstractmethod
    async def extract_fields(self, text: str) -> Dict[str, Any]:
        """
        提取結構化欄位

        Args:
            text: OCR 文字

        Returns:
            結構化欄位字典
        """
        pass

    async def process(
        self,
        file_contents: bytes,
        filename: str,
        page_number: int,
        total_pages: int,
        enable_llm: bool
    ) -> Dict[str, Any]:
        """
        處理單一頁面（模板方法）

        定義標準處理流程，子類別可覆寫特定步驟
        """
        # 實作標準流程...
        pass
```

**型別定義**:
```python
from typing import TypedDict, Literal, Optional

DocumentTypeEnum = Literal["transcript", "contract"]

class PageResult(TypedDict):
    page_number: int
    original_image: str
    ocr_raw: Dict[str, Any]
    rule_postprocessed: Dict[str, Any]
    llm_postprocessed: Optional[Dict[str, Any]]
    structured_data: Optional[Dict[str, Any]]  # 類型特定資訊
    accuracy: Optional[Dict[str, float]]
    processing_steps: Dict[str, str]
```

**依賴**:
- PIL.Image - 圖像處理
- typing - 型別定義

**對應需求**: [需求 1, 需求 2, 需求 5]

---

### 元件 2: TranscriptProcessor (謄本處理器)

**職責**: 封裝現有謄本處理邏輯，繼承 DocumentProcessor

**公開介面**:
```python
class TranscriptProcessor(DocumentProcessor):
    """謄本文件處理器"""

    def __init__(self):
        self.preprocessor = TranscriptPreprocessor(PreprocessConfig())
        self.engine_manager = EngineManager(engines=["tesseract"], parallel=False)
        self.postprocessor = TranscriptPostprocessor(
            enable_typo_fix=True,
            enable_format_correction=True,
            enable_llm=False  # 根據參數動態啟用
        )

    async def preprocess(self, image: Image.Image) -> Image.Image:
        """使用 TranscriptPreprocessor 進行預處理"""
        processed, _ = await self.preprocessor.preprocess(image)
        return processed

    async def extract_text(self, image: Image.Image) -> tuple[str, float]:
        """使用 EngineManager 提取文字"""
        text, confidence, _ = await self.engine_manager.extract_text_multi_engine(image)
        return text, confidence

    async def postprocess(
        self,
        text: str,
        confidence: float,
        image_data: Optional[str] = None
    ) -> tuple[str, Dict[str, Any]]:
        """使用 TranscriptPostprocessor 後處理"""
        result, stats = await self.postprocessor.postprocess(
            text,
            confidence,
            image_data
        )
        return result, stats

    async def extract_fields(self, text: str) -> Dict[str, Any]:
        """謄本欄位提取（未來實作）"""
        # TODO: 使用 TranscriptFieldExtractor 提取地號、面積等
        return {}
```

**型別定義**:
```python
class TranscriptStructuredData(TypedDict):
    # 未來可擴展謄本專屬欄位
    pass
```

**依賴**:
- DocumentProcessor - 抽象基類
- TranscriptPreprocessor - 謄本預處理
- EngineManager - OCR 引擎管理
- TranscriptPostprocessor - 謄本後處理

**對應需求**: [需求 1, 需求 3]

---

### 元件 3: ContractProcessor (合約處理器)

**職責**: 實作合約文件的專門化處理邏輯

**公開介面**:
```python
class ContractProcessor(DocumentProcessor):
    """合約文件處理器"""

    def __init__(self):
        # 合約可能需要不同的預處理策略
        self.preprocessor = TranscriptPreprocessor(
            PreprocessConfig(
                enable_watermark_removal=False,  # 合約通常無浮水印
                enable_binarization=False,
                enable_denoising=True  # 加強去噪
            )
        )
        self.engine_manager = EngineManager(engines=["tesseract"], parallel=False)
        self.postprocessor = TranscriptPostprocessor(
            enable_typo_fix=True,
            enable_format_correction=True,
            enable_llm=False
        )
        self.field_extractor = ContractFieldExtractor()

    async def preprocess(self, image: Image.Image) -> Image.Image:
        """合約專用預處理"""
        processed, _ = await self.preprocessor.preprocess(image)
        # 可添加合約特定的預處理步驟
        return processed

    async def extract_text(self, image: Image.Image) -> tuple[str, float]:
        """與謄本相同的 OCR 邏輯"""
        text, confidence, _ = await self.engine_manager.extract_text_multi_engine(image)
        return text, confidence

    async def postprocess(
        self,
        text: str,
        confidence: float,
        image_data: Optional[str] = None
    ) -> tuple[str, Dict[str, Any]]:
        """合約專用後處理（可能需要特殊法律用語處理）"""
        result, stats = await self.postprocessor.postprocess(
            text,
            confidence,
            image_data
        )
        return result, stats

    async def extract_fields(self, text: str, image_data: Optional[str] = None) -> Dict[str, Any]:
        """合約關鍵欄位提取"""
        fields = await self.field_extractor.extract(text, image_data)
        return fields
```

**型別定義**:
```python
class ContractMetadata(TypedDict):
    contract_number: Optional[str]
    signing_date: Optional[str]
    effective_date: Optional[str]

class PartyInfo(TypedDict):
    party_a: Optional[str]
    party_b: Optional[str]
    party_a_address: Optional[str]
    party_b_address: Optional[str]

class FinancialTerms(TypedDict):
    contract_amount: Optional[str]
    currency: Optional[str]
    payment_method: Optional[str]
    payment_deadline: Optional[str]

class ContractStructuredData(TypedDict):
    contract_metadata: ContractMetadata
    parties: PartyInfo
    financial_terms: FinancialTerms
    extraction_confidence: float
```

**依賴**:
- DocumentProcessor - 抽象基類
- TranscriptPreprocessor - 重用預處理邏輯
- EngineManager - OCR 引擎
- TranscriptPostprocessor - 重用後處理邏輯
- ContractFieldExtractor - 合約欄位提取

**對應需求**: [需求 2, 需求 3, 需求 4]

---

### 元件 4: ProcessorFactory (處理器工廠)

**職責**: 根據文件類型參數創建對應的處理器

**公開介面**:
```python
class ProcessorFactory:
    """文件處理器工廠"""

    _processors: Dict[str, type[DocumentProcessor]] = {
        "transcript": TranscriptProcessor,
        "contract": ContractProcessor,
    }

    @classmethod
    def get_processor(cls, document_type: str) -> DocumentProcessor:
        """
        取得文件處理器

        Args:
            document_type: 文件類型 ("transcript" 或 "contract")

        Returns:
            對應的處理器實例

        Raises:
            ValueError: 不支援的文件類型
        """
        processor_class = cls._processors.get(document_type)
        if processor_class is None:
            supported = ", ".join(cls._processors.keys())
            raise ValueError(
                f"不支援的文件類型: {document_type}。"
                f"支援的類型: {supported}"
            )
        return processor_class()

    @classmethod
    def register_processor(
        cls,
        document_type: str,
        processor_class: type[DocumentProcessor]
    ):
        """
        註冊新的處理器（用於擴展）

        Args:
            document_type: 文件類型名稱
            processor_class: 處理器類別
        """
        cls._processors[document_type] = processor_class

    @classmethod
    def supported_types(cls) -> list[str]:
        """返回支援的文件類型列表"""
        return list(cls._processors.keys())
```

**型別定義**:
```python
# 無額外型別定義，使用標準 Python 型別
```

**依賴**:
- DocumentProcessor - 抽象基類
- TranscriptProcessor - 謄本處理器
- ContractProcessor - 合約處理器

**對應需求**: [需求 1, 需求 5]

---

### 元件 5: ContractFieldExtractor (合約欄位提取器)

**職責**: 從合約文字中提取結構化欄位

**公開介面**:
```python
import re
from typing import Optional, Dict, Any

class ContractFieldExtractor:
    """合約關鍵欄位提取器"""

    # 正則表達式模式庫
    PATTERNS = {
        "contract_number": [
            r"合約(?:編號|字號|號碼)?[：:]\s*([A-Z0-9\-]+)",
            r"Contract\s+No[.:]?\s*([A-Z0-9\-]+)",
        ],
        "signing_date": [
            r"(?:簽訂日期|立約日期)[：:]\s*(\d+年\d+月\d+日)",
            r"中華民國\s*(\d+)\s*年\s*(\d+)\s*月\s*(\d+)\s*日",
        ],
        "party_a": [
            r"甲方[：:]\s*([^\n\r]+)",
            r"立合約書人[：:]?\s*([^\n（]+)",
        ],
        "party_b": [
            r"乙方[：:]\s*([^\n\r]+)",
        ],
        "amount": [
            r"(?:合約金額|總價|總金額)[：:]\s*(新台幣|新臺幣|NTD|TWD)?\s*([\d,]+)\s*元",
            r"([\d,]+)\s*元整",
        ],
    }

    def __init__(self):
        self.llm_client = None  # 延遲初始化

    async def extract(
        self,
        text: str,
        image_data: Optional[str] = None,
        use_llm_fallback: bool = True
    ) -> Dict[str, Any]:
        """
        提取合約欄位

        Args:
            text: OCR 文字
            image_data: base64 圖像（可選）
            use_llm_fallback: 是否在正則失敗時使用 LLM

        Returns:
            結構化欄位字典
        """
        # 1. 先用正則表達式提取
        fields = self._extract_with_regex(text)

        # 2. 計算信心度
        confidence = self._calculate_confidence(fields)

        # 3. 若信心度低且允許，使用 LLM 輔助
        if confidence < 0.7 and use_llm_fallback and image_data:
            llm_fields = await self._extract_with_llm(text, image_data)
            # 合併結果（LLM 優先）
            fields = self._merge_fields(fields, llm_fields)
            confidence = self._calculate_confidence(fields)

        return {
            "contract_metadata": {
                "contract_number": fields.get("contract_number"),
                "signing_date": fields.get("signing_date"),
                "effective_date": fields.get("effective_date"),
            },
            "parties": {
                "party_a": fields.get("party_a"),
                "party_b": fields.get("party_b"),
                "party_a_address": fields.get("party_a_address"),
                "party_b_address": fields.get("party_b_address"),
            },
            "financial_terms": {
                "contract_amount": fields.get("amount"),
                "currency": fields.get("currency", "TWD"),
                "payment_method": fields.get("payment_method"),
                "payment_deadline": fields.get("payment_deadline"),
            },
            "extraction_confidence": confidence
        }

    def _extract_with_regex(self, text: str) -> Dict[str, Optional[str]]:
        """使用正則表達式提取"""
        results = {}
        for field_name, patterns in self.PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    results[field_name] = match.group(1).strip()
                    break  # 找到即停止
        return results

    async def _extract_with_llm(
        self,
        text: str,
        image_data: str
    ) -> Dict[str, Optional[str]]:
        """使用 LLM 視覺提取（備選方案）"""
        # TODO: 實作 LLM 視覺提取邏輯
        return {}

    def _calculate_confidence(self, fields: Dict[str, Optional[str]]) -> float:
        """計算提取信心度"""
        total_fields = len(self.PATTERNS)
        extracted_fields = sum(1 for v in fields.values() if v is not None)
        return extracted_fields / total_fields if total_fields > 0 else 0.0

    def _merge_fields(
        self,
        regex_fields: Dict[str, Optional[str]],
        llm_fields: Dict[str, Optional[str]]
    ) -> Dict[str, Optional[str]]:
        """合併正則與 LLM 結果（LLM 優先）"""
        merged = regex_fields.copy()
        for key, value in llm_fields.items():
            if value is not None:
                merged[key] = value
        return merged
```

**型別定義**:
```python
# 使用 ContractStructuredData（已在 ContractProcessor 定義）
```

**依賴**:
- re - 正則表達式
- typing - 型別定義
- openai (可選) - LLM 輔助提取

**對應需求**: [需求 4]

---

## 資料模型與流程

### 資料模型

本功能主要處理 API 請求與回應，不涉及新的資料庫模型。

#### API 請求模型

```python
from pydantic import BaseModel, Field
from typing import Optional, Literal

class OcrTestRequest(BaseModel):
    """OCR 測試請求（透過 FastAPI 自動處理）"""
    file: UploadFile  # FastAPI File 參數
    document_type: Optional[Literal["transcript", "contract"]] = Field(
        default="transcript",
        description="文件類型：transcript（謄本）或 contract（合約）"
    )
    enable_llm: Optional[bool] = Field(
        default=True,
        description="是否啟用 LLM 智能修正"
    )
    ground_truth: Optional[str] = Field(
        default=None,
        description="標準答案（用於計算準確率）"
    )
    page_number: Optional[int] = Field(
        default=None,
        description="指定處理的頁碼（null 表示處理全部）"
    )
```

#### API 回應模型

```python
from typing import TypedDict, Optional, List, Dict, Any

class OcrRawResult(TypedDict):
    text: str
    confidence: float

class RulePostprocessedResult(TypedDict):
    text: str
    stats: Dict[str, Any]

class LlmPostprocessedResult(TypedDict):
    text: str
    stats: Dict[str, Any]
    used: bool

class PageResult(TypedDict):
    page_number: int
    original_image: str  # base64
    ocr_raw: OcrRawResult
    rule_postprocessed: RulePostprocessedResult
    llm_postprocessed: Optional[LlmPostprocessedResult]
    structured_data: Optional[Dict[str, Any]]  # 類型特定資訊
    accuracy: Optional[Dict[str, float]]
    processing_steps: Dict[str, str]

class OcrTestResponse(TypedDict):
    file_name: str
    total_pages: int
    document_type: str  # 新增：明確標示文件類型
    pages: List[PageResult]
```

---

### 資料流程

**流程 1: OCR 測試完整流程**

```
[使用者上傳文件]
         ↓
[API 接收請求] - 參數: file, document_type, enable_llm
         ↓
[參數驗證] - document_type 是否支援？
         ↓ (有效)
[ProcessorFactory.get_processor(document_type)]
         ↓
[選擇處理器] - TranscriptProcessor / ContractProcessor
         ↓
[PDF → 多頁圖像] - PyMuPDF 提取每一頁
         ↓
┌─────────────────────────────────────────┐
│  For each page:                         │
│  ┌─────────────────────────────────┐   │
│  │ 1. Preprocess (預處理)          │   │
│  │    - 去浮水印/去噪 (依類型而定)  │   │
│  │    - 解析度提升                  │   │
│  └─────────────────────────────────┘   │
│          ↓                              │
│  ┌─────────────────────────────────┐   │
│  │ 2. Extract Text (OCR 辨識)     │   │
│  │    - Tesseract / PaddleOCR     │   │
│  │    - 返回文字 + 信心度          │   │
│  └─────────────────────────────────┘   │
│          ↓                              │
│  ┌─────────────────────────────────┐   │
│  │ 3. Rule Postprocess (規則修正)  │   │
│  │    - 錯別字修正                  │   │
│  │    - 格式校正                    │   │
│  └─────────────────────────────────┘   │
│          ↓                              │
│  ┌─────────────────────────────────┐   │
│  │ 4. LLM Postprocess (視覺修正)   │   │
│  │    - 若 enable_llm=true         │   │
│  │    - 傳入圖像 + OCR 文字         │   │
│  │    - GPT-4o 視覺修正             │   │
│  └─────────────────────────────────┘   │
│          ↓                              │
│  ┌─────────────────────────────────┐   │
│  │ 5. Extract Fields (欄位提取)    │   │
│  │    - 謄本: (未來實作)            │   │
│  │    - 合約: 正則 + LLM 混合提取   │   │
│  └─────────────────────────────────┘   │
│          ↓                              │
│  [構建 PageResult]                     │
│          ↓                              │
│  [添加到結果列表]                       │
└─────────────────────────────────────────┘
         ↓
[構建完整回應] - OcrTestResponse
         ↓
[返回 JSON 給前端]
```

**步驟說明**:
1. **步驟 1 - Preprocess**: 處理器根據文件類型執行專門的預處理（謄本去浮水印，合約加強去噪）
2. **步驟 2 - Extract Text**: 使用 EngineManager 進行 OCR 辨識，返回文字與信心度
3. **步驟 3 - Rule Postprocess**: 應用規則修正（錯別字、格式），統計修正次數
4. **步驟 4 - LLM Postprocess**: 若啟用 LLM，傳入圖像與文字進行視覺修正
5. **步驟 5 - Extract Fields**: 謄本提取地號等，合約提取合約編號、雙方、金額等

**錯誤處理**:
- **文件類型不支援**: 返回 400 錯誤，列出支援的類型
- **PDF 解析失敗**: 返回 500 錯誤，詳細錯誤訊息
- **OCR 處理失敗**: 降級到原始圖像重試，仍失敗則返回空文字
- **LLM API 失敗**: 跳過 LLM 修正，僅使用規則後處理結果
- **欄位提取失敗**: 返回 null 欄位，標記低信心度

---

## 整合點與 API 設計

### 內部整合點

#### 整合點 1: 與 ocr_enhanced/ 套件整合

**整合方式**: 處理器重用現有模組，封裝為統一介面

**介面定義**:
```python
# TranscriptProcessor 使用範例
class TranscriptProcessor(DocumentProcessor):
    def __init__(self):
        # 整合既有模組
        self.preprocessor = TranscriptPreprocessor(PreprocessConfig())
        self.engine_manager = EngineManager(...)
        self.postprocessor = TranscriptPostprocessor(...)

    async def preprocess(self, image):
        # 委派給既有模組
        return await self.preprocessor.preprocess(image)
```

**相容性考量**:
- 保持 `ocr_enhanced/` 模組介面不變
- 僅通過組合方式使用，不修改內部實作
- 確保型別定義一致（使用 `ocr_enhanced/types.py`）

---

#### 整合點 2: 與前端界面整合

**整合方式**: 前端新增文件類型選擇元件

**介面定義**:
```typescript
// frontend/src/services/api.ts
export interface OcrTestParams {
  file: File
  documentType?: 'transcript' | 'contract'
  enableLlm?: boolean
  groundTruth?: string
  pageNumber?: number
}

export async function testOcr(params: OcrTestParams): Promise<OcrTestResponse> {
  const formData = new FormData()
  formData.append('file', params.file)
  if (params.documentType) {
    formData.append('document_type', params.documentType)
  }
  // ... 其他參數

  const response = await fetch('/api/v1/ocr/test', {
    method: 'POST',
    body: formData
  })
  return response.json()
}
```

**相容性考量**:
- 保持現有 API 調用方式可用（不提供 `document_type` 參數）
- 新增的 `document_type` 參數為可選
- 回應格式向後兼容（謄本格式不變）

---

### 外部 API 設計

#### API 端點 1: OCR 測試 (擴展)

**路徑**: `POST /api/v1/ocr/test`

**請求格式**:
```http
POST /api/v1/ocr/test HTTP/1.1
Content-Type: multipart/form-data

--boundary
Content-Disposition: form-data; name="file"; filename="contract.pdf"
Content-Type: application/pdf

<PDF 檔案內容>
--boundary
Content-Disposition: form-data; name="document_type"

contract
--boundary
Content-Disposition: form-data; name="enable_llm"

true
--boundary--
```

**參數說明**:
| 參數 | 類型 | 必填 | 預設值 | 說明 |
|------|------|------|--------|------|
| file | File | ✅ | - | PDF 或圖片檔案 |
| document_type | string | ❌ | "transcript" | 文件類型（transcript / contract） |
| enable_llm | boolean | ❌ | true | 是否啟用 LLM 修正 |
| ground_truth | string | ❌ | null | 標準答案文字 |
| page_number | integer | ❌ | null | 指定處理頁碼 |

**回應格式（謄本）**:
```json
{
  "file_name": "謄本.pdf",
  "total_pages": 1,
  "document_type": "transcript",
  "pages": [
    {
      "page_number": 1,
      "original_image": "data:image/png;base64,...",
      "ocr_raw": {
        "text": "原始 OCR 文字",
        "confidence": 0.8234
      },
      "rule_postprocessed": {
        "text": "規則修正後文字",
        "stats": {
          "typo_fixes": 15,
          "format_corrections": 3
        }
      },
      "llm_postprocessed": {
        "text": "LLM 修正後文字",
        "stats": {
          "llm_used": true,
          "llm_cost": 0.025
        },
        "used": true
      },
      "structured_data": null,
      "accuracy": null,
      "processing_steps": {
        "1_ocr_engine": "Tesseract",
        "2_rule_processing": "✓ 完成",
        "3_llm_processing": "✓ 完成"
      }
    }
  ]
}
```

**回應格式（合約）**:
```json
{
  "file_name": "contract.pdf",
  "total_pages": 3,
  "document_type": "contract",
  "pages": [
    {
      "page_number": 1,
      "original_image": "data:image/png;base64,...",
      "ocr_raw": { ... },
      "rule_postprocessed": { ... },
      "llm_postprocessed": { ... },
      "structured_data": {
        "contract_metadata": {
          "contract_number": "ABC-2026-001",
          "signing_date": "2026年3月26日",
          "effective_date": "2026年4月1日"
        },
        "parties": {
          "party_a": "甲公司股份有限公司",
          "party_b": "乙公司有限公司",
          "party_a_address": "台北市信義區...",
          "party_b_address": "新北市板橋區..."
        },
        "financial_terms": {
          "contract_amount": "1,000,000",
          "currency": "TWD",
          "payment_method": "電匯",
          "payment_deadline": "2026年5月31日"
        },
        "extraction_confidence": 0.85
      },
      "accuracy": null,
      "processing_steps": { ... }
    },
    ...
  ]
}
```

**錯誤碼**:
- **400 Bad Request**: 文件類型不支援、檔案格式錯誤、參數驗證失敗
  ```json
  {
    "detail": "不支援的文件類型: invoice。支援的類型: transcript, contract"
  }
  ```
- **413 Payload Too Large**: 檔案大小超過限制
- **500 Internal Server Error**: OCR 處理失敗、伺服器錯誤

**對應需求**: [需求 1, 需求 2, 需求 3, 需求 4]

---

## 配置與部署

### 配置管理

**新增環境變數** (backend/.env):
```bash
# 多文件類型 OCR 設定
OCR_SUPPORTED_TYPES=transcript,contract  # 支援的文件類型
OCR_DEFAULT_TYPE=transcript               # 預設類型

# 合約資訊提取設定
CONTRACT_EXTRACTION_CONFIDENCE_THRESHOLD=0.7  # 信心度閾值
CONTRACT_ENABLE_LLM_FALLBACK=true             # 允許 LLM 回退
```

**配置驗證**:
```python
# backend/app/config.py 新增欄位
class Settings(BaseSettings):
    # ... 既有配置 ...

    # Multi-document OCR Settings
    OCR_SUPPORTED_TYPES: List[str] = ["transcript", "contract"]
    OCR_DEFAULT_TYPE: str = "transcript"
    CONTRACT_EXTRACTION_CONFIDENCE_THRESHOLD: float = 0.7
    CONTRACT_ENABLE_LLM_FALLBACK: bool = True
```

---

### 部署策略

**部署步驟**:
1. **步驟 1**: 檢查環境變數配置
   ```bash
   # 確認必要的配置已設定
   docker-compose config
   ```

2. **步驟 2**: 重新建構後端映像檔
   ```bash
   docker-compose build backend
   ```

3. **步驟 3**: 重啟後端服務
   ```bash
   docker-compose up -d backend
   ```

4. **步驟 4**: 驗證服務健康狀態
   ```bash
   curl http://localhost:8003/api/health
   curl http://localhost:8003/api/docs  # 檢查 API 文檔
   ```

5. **步驟 5**: 執行迴歸測試
   ```bash
   pytest tests/test_ocr_multi_type.py
   ```

**回滾計劃**:
若新版本出現問題，執行以下步驟回滾：
```bash
# 1. 切換到舊版本代碼
git checkout <previous-commit>

# 2. 重新建構並啟動
docker-compose build backend
docker-compose up -d backend

# 3. 驗證服務恢復正常
curl http://localhost:8003/api/health
```

**監控指標**:
- **指標 1**: OCR 處理時間 (目標: 謄本 < 30秒, 合約 < 30秒)
- **指標 2**: 文件類型分布統計 (記錄 transcript vs contract 使用比例)
- **指標 3**: 合約欄位提取成功率 (目標: > 75%)
- **指標 4**: LLM API 成本追蹤 (每日/每月統計)

---

## 效能與可靠性

### 效能目標

| 指標 | 目標值 | 測量方式 |
|------|--------|---------|
| 單頁謄本處理時間 | < 30秒 | 後端日誌記錄 |
| 單頁合約處理時間 | < 30秒 | 後端日誌記錄 |
| 多頁合約處理時間 (10頁) | < 5分鐘 | 後端日誌記錄 |
| 合約欄位提取準確率 | > 75% | 人工標註測試集驗證 |
| API 回應時間 (不含 OCR) | < 100ms | APM 監控 |

### 可靠性設計

**錯誤處理策略**:
1. **文件類型驗證失敗**:
   - 返回 400 錯誤與明確訊息
   - 列出支援的文件類型清單

2. **OCR 處理失敗**:
   - 嘗試降級處理（跳過預處理）
   - 記錄錯誤日誌供除錯
   - 返回部分結果（已處理的頁面）

3. **合約欄位提取信心度低**:
   - 標記欄位為「需人工確認」
   - 返回原始文字供使用者參考
   - 記錄低信心度案例供改進

4. **LLM API 失敗**:
   - 自動回退到規則處理
   - 記錄 LLM 錯誤但不中斷流程
   - 在回應中標記 `llm_used: false`

**降級機制**:
- **Level 1**: LLM 修正失敗 → 降級到規則後處理
- **Level 2**: 規則後處理失敗 → 降級到原始 OCR 文字
- **Level 3**: OCR 失敗 → 返回錯誤訊息但保留已處理頁面

---

## 測試策略

### 單元測試

**測試範圍**:
- [ ] `DocumentProcessor` 抽象基類介面定義
- [ ] `TranscriptProcessor` 所有公開方法
- [ ] `ContractProcessor` 所有公開方法
- [ ] `ProcessorFactory` 處理器選擇邏輯
- [ ] `ContractFieldExtractor` 正則提取邏輯
- [ ] `ContractFieldExtractor` 信心度計算
- [ ] API 參數驗證邏輯

**測試工具**: pytest, pytest-asyncio, pytest-mock

**測試範例**:
```python
import pytest
from backend.app.lib.multi_type_ocr.processor_factory import ProcessorFactory

def test_factory_get_transcript_processor():
    """測試工廠返回謄本處理器"""
    processor = ProcessorFactory.get_processor("transcript")
    assert isinstance(processor, TranscriptProcessor)

def test_factory_unsupported_type():
    """測試不支援的文件類型拋出錯誤"""
    with pytest.raises(ValueError) as exc_info:
        ProcessorFactory.get_processor("invoice")
    assert "不支援的文件類型" in str(exc_info.value)
```

---

### 整合測試

**測試場景**:
- [ ] 場景 1: 端到端處理謄本 PDF (不提供 document_type)
- [ ] 場景 2: 端到端處理合約 PDF (明確指定 document_type=contract)
- [ ] 場景 3: 合約欄位提取準確性（使用 11 份範例合約）
- [ ] 場景 4: LLM 啟用與禁用的差異對比
- [ ] 場景 5: 錯誤處理（不支援的文件類型）
- [ ] 場景 6: 向後兼容性（現有前端調用不受影響）

**測試資料**:
- `backend/data/建物謄本.jpg` - 謄本測試資料
- `backend/data/建物土地謄本-杭州南路一段.pdf` - 多頁謄本
- `data/contracts/*.pdf` - 11 份真實合約樣本

**測試範例**:
```python
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_ocr_contract_end_to_end():
    """端到端測試合約 OCR"""
    with open("data/contracts/contract1.pdf", "rb") as f:
        response = client.post(
            "/api/v1/ocr/test",
            files={"file": ("contract1.pdf", f, "application/pdf")},
            data={"document_type": "contract", "enable_llm": "false"}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["document_type"] == "contract"
    assert data["total_pages"] > 0

    # 驗證結構化資訊
    page = data["pages"][0]
    assert "structured_data" in page
    assert "contract_metadata" in page["structured_data"]
    assert "parties" in page["structured_data"]
```

---

### 驗收測試

**成功標準**:
- [ ] API 能正確區分謄本與合約文件類型
- [ ] 合約 OCR 準確率達 85% 以上（基於 11 份範例）
- [ ] 合約關鍵欄位提取成功率達 75% 以上
- [ ] 謄本功能保持 100% 向後兼容（現有測試全數通過）
- [ ] 處理時間符合效能目標（單頁 < 30秒）
- [ ] 前端界面能成功調用新 API 並顯示合約結構化資訊
- [ ] API 文檔完整呈現新參數與回應格式（繁體中文）

---

## 風險與緩解

### 技術風險

| 風險 | 嚴重程度 | 緩解措施 |
|------|---------|---------|
| 合約格式多樣性導致提取失敗 | 高 | 使用 11 份真實合約訓練模式；實作信心度評分；提供 LLM 回退 |
| LLM API 成本超出預算 | 中 | 智能策略（僅在必要時用 LLM）；提供 enable_llm 參數；監控使用量 |
| 現有謄本功能受影響 | 低 | 完整迴歸測試；保持向後兼容；分階段部署 |
| 正則表達式維護成本高 | 中 | 建立模式庫檔案；提供單元測試；文檔化模式用途 |
| 處理器數量增加導致代碼複雜度上升 | 低 | 策略模式確保隔離；工廠模式集中管理；良好的文檔與測試 |

### 營運風險

| 風險 | 嚴重程度 | 緩解措施 |
|------|---------|---------|
| 使用者不知如何指定文件類型 | 中 | API 文檔清楚說明；前端提供下拉選單；預設值保持向後兼容 |
| 合約提取結果不符預期 | 中 | 提供完整原始文字；標記低信心度欄位；建立反饋機制 |
| 文檔不同步 | 低 | 使用 OpenAPI 自動生成文檔；在代碼中維護 docstring |

---

## 實施里程碑

### Phase 1: 核心架構建立 (Week 1)

**目標**: 建立處理器架構基礎

- [ ] 定義 `DocumentProcessor` 抽象基類與型別定義
- [ ] 實作 `ProcessorFactory` 工廠類
- [ ] 實作 `TranscriptProcessor`（封裝既有邏輯）
- [ ] 實作 `ContractProcessor`（基礎版，無欄位提取）
- [ ] 單元測試：處理器選擇邏輯
- [ ] 整合測試：端到端處理謄本（確保不破壞現有功能）

**驗收標準**: 謄本處理完全正常，合約能完成 OCR 但不提取欄位

---

### Phase 2: 合約欄位提取 (Week 2)

**目標**: 實作合約結構化資訊提取

- [ ] 實作 `ContractFieldExtractor` 正則提取邏輯
- [ ] 建立合約正則模式庫（基於 11 份範例）
- [ ] 實作信心度計算邏輯
- [ ] 整合 LLM 視覺提取作為備選方案
- [ ] 單元測試：正則提取準確性
- [ ] 整合測試：11 份範例合約端到端測試

**驗收標準**: 合約欄位提取成功率 > 75%，信心度計算準確

---

### Phase 3: API 整合與前端更新 (Week 3)

**目標**: 整合 API 與前端界面

- [ ] 修改 `/api/v1/ocr/test` 端點使用處理器架構
- [ ] 更新 API 文檔（繁體中文）
- [ ] 前端新增文件類型選擇下拉選單
- [ ] 前端顯示合約結構化資訊（UI 設計）
- [ ] 迴歸測試：確保現有前端功能不受影響
- [ ] E2E 測試：前端到後端完整流程

**驗收標準**: 前端能成功調用新 API，正確顯示合約資訊

---

### Phase 4: 優化與部署 (Week 4)

**目標**: 效能優化、文檔完善、生產部署

- [ ] 效能調優：OCR 處理時間優化
- [ ] 錯誤處理完善：所有異常場景覆蓋
- [ ] 監控指標實作：處理時間、成功率、成本追蹤
- [ ] 使用指南撰寫（markdown）
- [ ] 生產環境部署與驗證
- [ ] 使用者驗收測試（UAT）

**驗收標準**: 所有驗收測試通過，文檔完整，生產環境穩定運行

---

**文件版本**: v1.0
**最後更新**: 2026-03-26T23:45:54Z
**設計狀態**: 已生成，待審核批准
**需求追溯**: 完整對應 requirements.md 中的需求 1-6
