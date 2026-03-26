# document-ocr-enhancement - 技術設計文件

## 概述

### 設計目標
建立模組化、可擴展的 OCR 增強系統,針對政府建物土地謄本文件提升辨識準確率 15% 以上,同時保持向後相容性並為未來擴展至其他文件類型奠定基礎。採用完全模組化架構(方案 B),確保程式碼品質、可測試性與長期可維護性。

### 設計原則
1. **模組化與解耦**: 七個獨立模組,職責單一,符合 SOLID 原則
2. **型別安全**: 所有公開介面使用 Python type hints 與 TypedDict,避免執行期型別錯誤
3. **可測試性**: 每個模組可獨立測試,依賴可注入,測試覆蓋率目標 80%+
4. **向後相容**: 保留現有 `extract_text_from_document()` 介面,新功能透過 `extract_text_enhanced()` 提供
5. **降級優雅**: 每個處理階段都有降級機制,確保系統可用性
6. **效能優先**: 關鍵路徑優化,目標單頁 JPG < 30秒,3頁 PDF < 90秒
7. **可觀測性**: 詳細日誌與監控指標,方便除錯與優化

### 架構決策摘要
1. **方案 B 完全模組化**: 建立 `backend/app/lib/ocr_enhanced/` 模組,包含 7 個子模組
2. **門面模式**: `EnhancedOCRPipeline` 作為統一入口,隱藏內部複雜性
3. **策略模式**: 預處理與引擎選擇使用策略模式,支援動態切換
4. **非同步並行**: 多引擎使用 `asyncio.gather()` 並行處理,降低總處理時間
5. **OpenCV 主導**: 圖像預處理主要使用 OpenCV,Pillow 輔助基本操作

---

## 架構模式與邊界劃分

### 選定模式
**主模式**: 門面模式(Facade Pattern) + 管道模式(Pipeline Pattern) + 策略模式(Strategy Pattern)

- **門面模式**: `EnhancedOCRPipeline` 提供統一的高層介面
- **管道模式**: 單引擎流程為線性管道(預處理 → OCR → 後處理)
- **策略模式**: 預處理策略、引擎選擇、後處理策略可動態替換

### 模組邊界圖

```
┌─────────────────────────────────────────────────────────────┐
│                    EnhancedOCRPipeline                      │
│                     (Facade / 入口)                          │
└────────────┬────────────────────────────────────────────────┘
             │
             │ 協調
             │
    ┌────────┴─────────┬──────────────┬──────────────┬──────────┐
    │                  │              │              │          │
    v                  v              v              v          v
┌─────────┐      ┌──────────┐   ┌─────────┐   ┌──────────┐ ┌────────┐
│Document │      │Preproc   │   │Engine   │   │Postproc  │ │Quality │
│Classifier│─────>│essor     │──>│Manager  │──>│essor     │─>│Assessor│
└─────────┘      └──────────┘   └─────────┘   └──────────┘ └────┬───┘
                                      │             │            │
                                      │             v            │
                                      │        ┌────────┐        │
                                      │        │Field   │        │
                                      │        │Extractor        │
                                      │        └────────┘        │
                                      v                          │
                                 ┌────────┐                      │
                                 │Config  │<─────────────────────┘
                                 └────────┘

[外部依賴]
OCR Engines: PaddleOCR, Tesseract, AWS Textract
Image Libs: OpenCV, Pillow
Storage: storage_service
Database: DocumentOcrResult model
```

### 邊界劃分理由

| 模組 | 職責 | 輸入 | 輸出 | 理由 |
|------|------|------|------|------|
| **DocumentClassifier** | 偵測文件類型 | 文件 URL | 文件類型(transcript/lease/id) | 不同文件類型需要不同預處理策略 |
| **Preprocessor** | 圖像預處理 | 原始圖像 | 增強後圖像 | 浮水印移除、二值化、去噪為獨立處理單元 |
| **EngineManager** | OCR 引擎管理 | 圖像 | OCR 文字 + 信心度 | 多引擎並行、融合邏輯複雜,需要專門管理 |
| **Postprocessor** | 文字後處理 | OCR 原始文字 | 校正後文字 | 錯別字修正、格式校正與 OCR 獨立 |
| **QualityAssessor** | 品質評估 | OCR 結果 | 品質分數 + 重試決策 | 品質判斷與重試邏輯為獨立關注點 |
| **FieldExtractor** | 欄位提取 | 文字 | 結構化欄位 | 正則提取與通用 OCR 流程解耦 |
| **Config** | 參數配置 | - | 配置參數 | 集中管理所有可調參數,方便調優 |

---

## 技術棧與對齊

### 核心技術選擇

| 技術領域 | 選擇 | 版本 | 理由 |
|---------|------|------|------|
| **語言** | Python | 3.11+ | 專案標準,豐富的圖像處理生態 |
| **框架** | FastAPI | 0.115+ | 專案標準,非同步支援完善 |
| **ORM** | SQLAlchemy | 2.0+ | 專案標準,型別安全 |
| **圖像處理** | OpenCV | 4.5.0+ | HSV 色彩空間、適應性二值化原生支援 |
| **圖像基礎** | Pillow | 11.0.0 | 專案已使用,輔助基本操作 |
| **OCR 引擎 1** | PaddleOCR | 2.8.1+ | 繁體中文效果最佳,免費 |
| **OCR 引擎 2** | Tesseract | 4.0+ | 開源標準,表格辨識佳 |
| **OCR 引擎 3** | AWS Textract | - | 品質最高,付費(可選) |
| **非同步** | asyncio | 內建 | 多引擎並行處理 |
| **型別檢查** | typing | 內建 | 靜態型別安全 |

### 外部依賴

| 依賴 | 版本 | 用途 | 風險評估 |
|------|------|------|---------|
| opencv-python-headless | ≥4.5.0 | 圖像預處理(HSV、二值化、去噪) | 低風險,成熟穩定 |
| paddleocr | ≥2.8.1 | 繁體中文 OCR | 低風險,百度維護 |
| pytesseract | 0.3.13 | 開源 OCR 引擎 | 低風險,Google 維護 |
| pdf2image | 1.17.0 | PDF 轉圖像 | 低風險,專案已使用 |
| numpy | <2.0.0 | 陣列操作 | 低風險,版本鎖定 |

### 與現有系統對齊

**對齊策略**:
1. **保留現有介面**: `extract_text_from_document()` 繼續使用,不影響現有功能
2. **新增增強入口**: `extract_text_enhanced()` 提供新功能,透過配置開關決定使用
3. **擴展資料模型**: `DocumentOcrResult` 增加欄位儲存新元數據(JSONB 避免 schema 大改)
4. **複用基礎設施**: storage_service、database、API 層完全複用
5. **統一錯誤處理**: 遵循現有 HTTPException 模式

---

## 元件與介面契約

### 元件 1: EnhancedOCRPipeline (門面類)

**職責**: 統一的 OCR 增強入口,協調所有子模組完成端到端處理

**公開介面**:
```python
from typing import TypedDict, Literal
from pathlib import Path

class OCRResult(TypedDict):
    text: str                      # OCR 辨識文字
    page_count: int                # 頁數
    quality_score: float           # 品質分數 (0-100)
    confidence: float              # 平均信心度 (0-1)
    metadata: dict                 # 處理元數據

class EnhancedOCRPipeline:
    """OCR 增強管道 - 門面類"""

    def __init__(
        self,
        enable_preprocessing: bool = True,
        enable_postprocessing: bool = True,
        enable_multi_engine: bool = False,
        enable_quality_check: bool = True
    ):
        """初始化管道

        Args:
            enable_preprocessing: 是否啟用預處理
            enable_postprocessing: 是否啟用後處理
            enable_multi_engine: 是否啟用多引擎融合
            enable_quality_check: 是否啟用品質檢查
        """
        pass

    async def process(
        self,
        file_url: str,
        doc_type: Literal["transcript", "lease", "id_card", "auto"] = "auto"
    ) -> OCRResult:
        """處理文件

        Args:
            file_url: 文件 URL (來自 storage_service)
            doc_type: 文件類型,auto 為自動偵測

        Returns:
            OCRResult 包含辨識結果與元數據

        Raises:
            ValueError: 檔案格式不支援
            OCRProcessingError: OCR 處理失敗
        """
        pass
```

**型別定義**:
```python
class ProcessingMetadata(TypedDict):
    """處理元數據"""
    doc_type: str                  # 文件類型
    preprocessing_applied: bool     # 是否套用預處理
    preprocessing_strategy: str     # 預處理策略名稱
    ocr_engines_used: list[str]    # 使用的 OCR 引擎
    processing_time_ms: int        # 總處理時間(毫秒)
    retry_count: int               # 重試次數
    watermark_removed: bool        # 是否移除浮水印
    confidence_scores: dict[str, float]  # 各引擎信心度
```

**依賴**:
- DocumentClassifier: 文件類型偵測
- Preprocessor: 圖像預處理
- EngineManager: OCR 引擎管理
- Postprocessor: 文字後處理
- QualityAssessor: 品質評估
- storage_service: 文件下載

**對應需求**: [需求 1, 2, 3, 4]

---

### 元件 2: DocumentClassifier

**職責**: 自動偵測文件類型,為不同類型文件選擇最佳處理策略

**公開介面**:
```python
from PIL import Image

class DocumentClassifier:
    """文件類型分類器"""

    async def classify(
        self,
        image: Image.Image
    ) -> Literal["transcript", "lease", "id_card", "unknown"]:
        """分類文件類型

        Args:
            image: PIL Image 物件

        Returns:
            文件類型字串

        Note:
            目前實作:基於關鍵字檢測(簡單快速)
            未來可升級:基於 ML 模型分類
        """
        pass

    def is_transcript(self, image: Image.Image) -> bool:
        """判斷是否為建物土地謄本"""
        pass
```

**實作策略**:
- **Phase 1**: 基於關鍵字檢測(搜尋「謄本」、「地政」、「建物標示部」等)
- **Phase 2**: 可升級為基於 ML 的圖像分類器

**依賴**: 無

**對應需求**: [需求 1.1]

---

### 元件 3: Preprocessor

**職責**: 針對謄本文件執行專用圖像預處理,移除干擾並增強文字

**公開介面**:
```python
import cv2
import numpy as np
from typing import Optional
from PIL import Image

class PreprocessingStrategy(Protocol):
    """預處理策略介面"""
    def apply(self, image: np.ndarray) -> np.ndarray:
        ...

class TranscriptPreprocessor:
    """謄本文件預處理器"""

    def __init__(self, config: 'PreprocessConfig'):
        self.config = config

    async def preprocess(
        self,
        image: Image.Image,
        strategy: Optional[PreprocessingStrategy] = None
    ) -> tuple[np.ndarray, dict]:
        """執行預處理

        Args:
            image: 原始 PIL Image
            strategy: 自訂策略,None 使用預設

        Returns:
            (處理後的 numpy 陣列, 處理元數據)

        Processing Pipeline:
            1. PIL → numpy array (RGB)
            2. Remove red watermark (HSV)
            3. Adaptive binarization
            4. Denoise (Gaussian blur)
            5. Resolution adjustment
        """
        pass

    def remove_red_watermark(
        self,
        image: np.ndarray,
        lower_hsv: tuple[int, int, int] = (0, 50, 50),
        upper_hsv1: tuple[int, int, int] = (10, 255, 255),
        upper_hsv2: tuple[int, int, int] = (160, 255, 255)
    ) -> np.ndarray:
        """移除紅色浮水印

        Args:
            image: BGR 格式 numpy 陣列
            lower_hsv: HSV 下界
            upper_hsv1: 紅色範圍 1 上界 [0, 10]
            upper_hsv2: 紅色範圍 2 上界 [160, 179]

        Returns:
            移除浮水印後的圖像

        Algorithm:
            1. Convert BGR → HSV
            2. Create mask for red range
            3. Morphological operations (remove noise)
            4. Fill masked area with white
        """
        pass

    def adaptive_binarize(
        self,
        image: np.ndarray,
        method: Literal["gaussian", "mean", "sauvola"] = "gaussian"
    ) -> np.ndarray:
        """適應性二值化

        Args:
            image: 灰階圖像
            method: 二值化方法

        Returns:
            二值化後圖像
        """
        pass

    def denoise(self, image: np.ndarray, kernel_size: int = 5) -> np.ndarray:
        """去噪處理"""
        pass

    def adjust_resolution(
        self,
        image: np.ndarray,
        target_dpi: int = 1500
    ) -> np.ndarray:
        """調整解析度"""
        pass

    async def compare_with_original(
        self,
        original: np.ndarray,
        processed: np.ndarray,
        ocr_engine
    ) -> tuple[bool, float]:
        """比較預處理前後的 OCR 效果

        Returns:
            (是否使用處理後圖像, 信心度差異)
        """
        pass
```

**型別定義**:
```python
from dataclasses import dataclass

@dataclass
class PreprocessConfig:
    """預處理配置"""
    enable_watermark_removal: bool = True
    enable_binarization: bool = True
    enable_denoising: bool = True
    binarization_method: str = "gaussian"
    target_dpi: int = 1500
    hsv_lower: tuple[int, int, int] = (0, 50, 50)
    hsv_upper1: tuple[int, int, int] = (10, 255, 255)
    hsv_upper2: tuple[int, int, int] = (160, 255, 255)
    gaussian_kernel_size: int = 5
```

**依賴**:
- OpenCV (cv2)
- NumPy
- Pillow
- Config 模組

**對應需求**: [需求 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7]

---

### 元件 4: EngineManager

**職責**: 管理多個 OCR 引擎,支援並行處理與結果融合

**公開介面**:
```python
from typing import Protocol

class OCREngine(Protocol):
    """OCR 引擎介面"""
    async def extract_text(self, image: np.ndarray) -> tuple[str, float]:
        """提取文字

        Returns:
            (文字, 信心度)
        """
        ...

class EngineResult(TypedDict):
    """單一引擎結果"""
    engine: str
    text: str
    confidence: float
    processing_time_ms: int

class EngineManager:
    """OCR 引擎管理器"""

    def __init__(
        self,
        engines: list[str] = ["paddleocr", "tesseract"],
        parallel: bool = False,
        fusion_method: Literal["best", "weighted", "vote"] = "best"
    ):
        """初始化引擎管理器

        Args:
            engines: 引擎列表
            parallel: 是否並行處理
            fusion_method: 融合方法
        """
        pass

    async def extract_text_multi_engine(
        self,
        image: np.ndarray,
        page_number: int = 1
    ) -> tuple[str, float, list[EngineResult]]:
        """使用多引擎提取文字

        Args:
            image: 圖像 numpy 陣列
            page_number: 頁碼(用於 PDF)

        Returns:
            (融合後文字, 融合後信心度, 各引擎結果)
        """
        pass

    async def _run_paddleocr(
        self,
        image: np.ndarray
    ) -> EngineResult:
        """執行 PaddleOCR"""
        pass

    async def _run_tesseract(
        self,
        image: np.ndarray
    ) -> EngineResult:
        """執行 Tesseract"""
        pass

    async def _run_textract(
        self,
        image: np.ndarray
    ) -> EngineResult:
        """執行 AWS Textract (可選)"""
        pass

    def _fuse_results(
        self,
        results: list[EngineResult]
    ) -> tuple[str, float]:
        """融合多個引擎結果

        Fusion Methods:
            - best: 選擇信心度最高的結果
            - weighted: 基於信心度的加權平均
            - vote: 字符級投票(複雜,Phase 2)
        """
        pass

    def _standardize_confidence(
        self,
        engine: str,
        raw_confidence: any
    ) -> float:
        """標準化信心度

        各引擎信心度格式不同,統一為 0-1 浮點數
        - PaddleOCR: 逐行信心度,取平均
        - Tesseract: 需額外配置才有
        - Textract: 原生支援
        """
        pass
```

**依賴**:
- PaddleOCR
- pytesseract
- boto3 (可選,用於 Textract)
- asyncio

**對應需求**: [需求 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7]

---

### 元件 5: Postprocessor

**職責**: OCR 結果後處理,包含錯別字修正、格式校正、結構還原

**公開介面**:
```python
import re

class TranscriptPostprocessor:
    """謄本文字後處理器"""

    def __init__(self):
        self.typo_dict = self._load_typo_dict()
        self.field_patterns = self._compile_field_patterns()

    def process(
        self,
        raw_text: str,
        doc_type: str = "transcript"
    ) -> tuple[str, dict]:
        """處理 OCR 原始文字

        Args:
            raw_text: OCR 原始文字
            doc_type: 文件類型

        Returns:
            (處理後文字, 處理統計)

        Processing Steps:
            1. Fix common Traditional Chinese typos
            2. Correct field formats (地號, 統一編號, etc.)
            3. Remove duplicate watermark text
            4. Restore logical structure
            5. Normalize numbers and amounts
        """
        pass

    def fix_traditional_chinese_typos(self, text: str) -> str:
        """修正繁體中文常見錯別字

        Examples:
            ㆞ → 地
            ㆗ → 中
            ㆟ → 人
            ０ → 0 (全形數字)
        """
        pass

    def correct_field_formats(self, text: str) -> str:
        """校正欄位格式

        Patterns:
            地號: XXXX-XXXX
            統一編號: A########
            日期: 民國XXX年XX月XX日
            面積: ##.## 平方公尺
        """
        pass

    def remove_duplicate_watermark_text(self, text: str) -> str:
        """移除重複的浮水印文字

        Detects:
            - 重複出現的「已列印」
            - 重複出現的「本謄本列印完畢」
        """
        pass

    def restore_logical_structure(self, text: str) -> str:
        """還原邏輯結構

        Identifies:
            - 土地標示部
            - 土地所有權部
            - 建物標示部
            - 建物所有權部
        """
        pass

    def _load_typo_dict(self) -> dict[str, str]:
        """載入錯別字字典"""
        return {
            "㆞": "地",
            "㆗": "中",
            "㆟": "人",
            "㈯": "土",
            "㊞": "印",
            "㆒": "一",
            "㆓": "二",
            "㆔": "三",
            "㆕": "四",
            "㈰": "日",
            "㈪": "月",
            "㈲": "有",
            "㊠": "項",
            # ... 更多錯別字對照
        }

    def _compile_field_patterns(self) -> dict[str, re.Pattern]:
        """編譯欄位正則表達式"""
        return {
            "land_number": re.compile(r"(?:㆞|地)號[：:]\s*(\d{4}-\d{4})"),
            "area": re.compile(r"面\s*積[：:]\s*([\d,]+\.?\d*)\s*平方公尺"),
            "unified_id": re.compile(r"統㆒編號[：:]\s*([A-Z]\d{2,3}\*+\d{1,2})"),
            # ... 更多模式
        }
```

**依賴**:
- 標準庫 re
- 自訂錯別字字典檔案

**對應需求**: [需求 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7]

---

### 元件 6: QualityAssessor

**職責**: 評估 OCR 結果品質,決策是否重試

**公開介面**:
```python
class QualityMetrics(TypedDict):
    """品質指標"""
    confidence_score: float        # 信心度分數
    character_density: float       # 字符密度
    field_match_rate: float        # 欄位匹配率
    anomaly_rate: float            # 異常字符比例
    overall_score: float           # 總體分數 (0-100)

class QualityAssessor:
    """品質評估器"""

    def __init__(
        self,
        quality_threshold: float = 60.0,
        max_retries: int = 3
    ):
        self.threshold = quality_threshold
        self.max_retries = max_retries

    def assess(
        self,
        ocr_result: str,
        confidence: float,
        doc_type: str = "transcript"
    ) -> QualityMetrics:
        """評估 OCR 結果品質

        Args:
            ocr_result: OCR 文字
            confidence: 平均信心度
            doc_type: 文件類型

        Returns:
            品質指標
        """
        pass

    def should_retry(
        self,
        metrics: QualityMetrics,
        retry_count: int
    ) -> tuple[bool, str]:
        """判斷是否需要重試

        Returns:
            (是否重試, 建議策略)
        """
        pass

    def generate_report(
        self,
        metrics: QualityMetrics,
        processing_history: list[dict]
    ) -> dict:
        """生成品質報告

        Returns:
            {
                'quality_score': float,
                'assessment': str,
                'recommendations': list[str],
                'processing_history': list[dict]
            }
        """
        pass

    def _calculate_confidence_score(self, confidence: float) -> float:
        """計算信心度分數 (0-100)"""
        return confidence * 100

    def _calculate_character_density(self, text: str) -> float:
        """計算字符密度"""
        # 字符數 / 預期字符數
        pass

    def _calculate_field_match_rate(
        self,
        text: str,
        doc_type: str
    ) -> float:
        """計算欄位匹配率

        檢查已知欄位(地號、面積等)是否正確格式
        """
        pass

    def _calculate_anomaly_rate(self, text: str) -> float:
        """計算異常字符比例

        異常字符:亂碼、過多特殊符號
        """
        pass
```

**依賴**:
- FieldExtractor (用於欄位驗證)
- Postprocessor (用於異常檢測)

**對應需求**: [需求 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7]

---

### 元件 7: FieldExtractor

**職責**: 使用正則表達式提取謄本專用欄位

**公開介面**:
```python
class ExtractedFields(TypedDict):
    """提取的欄位"""
    land_number: Optional[str]      # 地號
    area: Optional[float]           # 面積
    owner: Optional[str]            # 所有權人
    unified_id: Optional[str]       # 統一編號
    title_number: Optional[str]     # 權狀字號
    register_date: Optional[str]    # 登記日期
    validation_status: dict[str, bool]  # 欄位驗證狀態

class TranscriptFieldExtractor:
    """謄本欄位提取器"""

    def __init__(self):
        self.patterns = self._compile_patterns()

    def extract(
        self,
        text: str,
        fallback_to_ai: bool = True
    ) -> ExtractedFields:
        """提取欄位

        Args:
            text: OCR 文字
            fallback_to_ai: 正則失敗時是否回退到 AI

        Returns:
            提取的欄位資料

        Strategy:
            1. 優先使用正則表達式提取 (快速、準確、免費)
            2. 失敗時回退到 AI 提取 (靈活、成本高)
        """
        pass

    def extract_land_number(self, text: str) -> Optional[str]:
        """提取地號 (格式: XXXX-XXXX)"""
        pass

    def extract_area(self, text: str) -> Optional[float]:
        """提取面積 (單位: 平方公尺)"""
        pass

    def extract_owner(self, text: str) -> Optional[str]:
        """提取所有權人 (可能包含遮蔽符號 **)"""
        pass

    def extract_unified_id(self, text: str) -> Optional[str]:
        """提取統一編號"""
        pass

    def extract_title_number(self, text: str) -> Optional[str]:
        """提取權狀字號"""
        pass

    def extract_register_date(self, text: str) -> Optional[str]:
        """提取登記日期 (民國紀年)"""
        pass

    def validate_fields(
        self,
        fields: ExtractedFields
    ) -> dict[str, bool]:
        """驗證欄位格式正確性

        Returns:
            {field_name: is_valid}
        """
        pass

    def _compile_patterns(self) -> dict[str, re.Pattern]:
        """編譯所有正則表達式"""
        return {
            "land_number": re.compile(
                r"(?:㆞|地)號[：:]\s*(\d{4}-\d{4})"
            ),
            "area": re.compile(
                r"面\s*積[：:]\s*([\d,]+\.?\d*)\s*平方公尺"
            ),
            "unified_id": re.compile(
                r"統㆒編號[：:]\s*([A-Z]\d{2,3}\*+\d{1,2})"
            ),
            "title_number": re.compile(
                r"(\d{2,3})[北中南]建字第(\d+)號"
            ),
            "register_date": re.compile(
                r"民國(\d{2,3})年(\d{1,2})月(\d{1,2})日"
            ),
        }
```

**依賴**:
- ai_service (用於 AI 回退)

**對應需求**: [需求 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8]

---

## 資料模型與流程

### 資料模型

#### Model 1: DocumentOcrResult (擴展)

**用途**: 儲存 OCR 結果與增強處理元數據

**Schema 定義**:
```python
from sqlalchemy import Column, JSONB, Numeric, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB

class DocumentOcrResult(Base):
    __tablename__ = "document_ocr_results"

    # 現有欄位
    id = Column(UUID, primary_key=True)
    document_id = Column(UUID, ForeignKey("documents.id"))
    raw_text = Column(Text, nullable=False)
    page_count = Column(Integer, default=1)
    ocr_confidence = Column(Numeric(5, 2), nullable=True)
    ocr_service = Column(String(50), nullable=True)
    processing_time = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    # 新增欄位
    preprocessing_params = Column(JSONB, nullable=True)     # 預處理參數
    quality_score = Column(Numeric(5, 2), nullable=True)    # 品質分數(0-100)
    engines_used = Column(String(200), nullable=True)       # 使用的引擎
    retry_count = Column(Integer, default=0)                # 重試次數
    watermark_removed = Column(Boolean, default=False)      # 浮水印移除
    postprocessing_applied = Column(Boolean, default=False) # 後處理
    enhanced_mode = Column(Boolean, default=False)          # 增強模式
```

**索引策略**:
- 現有索引: `idx_ocr_document_id` (document_id)
- 新增索引: `idx_ocr_quality_score` (quality_score) - 用於品質分析查詢
- 新增索引: `idx_ocr_enhanced_mode` (enhanced_mode) - 用於區分增強/標準模式

**遷移考量**:
- 使用 Alembic 新增欄位,所有欄位 nullable=True 避免現有資料問題
- JSONB 欄位適合儲存動態元數據,無需頻繁修改 schema

---

### 資料流程

#### 流程 1: 增強 OCR 處理流程

```
[開始] file_url
  │
  ├─> [1. 下載文件] storage_service.download_file()
  │   └─> file_bytes
  │
  ├─> [2. 文件類型偵測] DocumentClassifier.classify()
  │   └─> doc_type: "transcript"
  │
  ├─> [3. 圖像預處理] Preprocessor.preprocess()
  │   ├─> 3.1 移除紅色浮水印 (HSV)
  │   ├─> 3.2 適應性二值化 (Gaussian)
  │   ├─> 3.3 去噪 (GaussianBlur)
  │   ├─> 3.4 調整解析度 (1500 DPI)
  │   └─> preprocessed_image
  │
  ├─> [4. OCR 引擎處理] EngineManager.extract_text_multi_engine()
  │   ├─> 4.1 並行運行 PaddleOCR + Tesseract
  │   ├─> 4.2 標準化信心度
  │   ├─> 4.3 融合結果 (選擇最佳)
  │   └─> (ocr_text, confidence, engine_results)
  │
  ├─> [5. 文字後處理] Postprocessor.process()
  │   ├─> 5.1 修正繁體中文錯別字
  │   ├─> 5.2 校正欄位格式
  │   ├─> 5.3 移除浮水印文字
  │   ├─> 5.4 還原邏輯結構
  │   └─> corrected_text
  │
  ├─> [6. 品質評估] QualityAssessor.assess()
  │   ├─> 6.1 計算品質分數
  │   ├─> 6.2 判斷是否重試
  │   └─> quality_metrics
  │
  ├─> [7. 重試決策]
  │   ├─> IF quality_score < threshold AND retry_count < max_retries
  │   │   └─> 回到步驟 3 (使用不同參數)
  │   └─> ELSE 繼續
  │
  ├─> [8. 專用欄位提取] FieldExtractor.extract()
  │   ├─> 8.1 正則表達式提取
  │   ├─> 8.2 格式驗證
  │   └─> extracted_fields
  │
  ├─> [9. 儲存結果]
  │   ├─> DocumentOcrResult (raw_text, quality_score, metadata)
  │   └─> database.commit()
  │
  └─> [結束] Return OCRResult
```

**錯誤處理**:

| 階段 | 錯誤類型 | 處理方式 |
|------|---------|---------|
| 1. 下載文件 | 網路錯誤 | 重試 3 次,失敗拋出異常 |
| 2. 類型偵測 | 無法判斷 | 降級為 "unknown",使用通用策略 |
| 3. 預處理 | 處理失敗 | 降級為原始圖像,記錄警告 |
| 4. OCR 引擎 | 單一引擎失敗 | 使用其他引擎結果,多引擎全失敗拋異常 |
| 5. 後處理 | 正則錯誤 | 跳過該欄位,不影響整體流程 |
| 6. 品質評估 | 評估失敗 | 使用預設分數 50,記錄警告 |
| 7. 重試 | 達到最大次數 | 回傳最佳結果,標記為低品質 |
| 8. 欄位提取 | 提取失敗 | 標記為 null,回退到 AI 提取 |

---

#### 流程 2: PDF 多頁處理流程

```
[開始] PDF file_url
  │
  ├─> [1. PDF 轉圖像] pdf2image.convert_from_bytes(dpi=300)
  │   └─> images: list[PIL.Image]
  │
  ├─> [2. 逐頁處理] for each image:
  │   ├─> [2.1 預處理] Preprocessor.preprocess()
  │   ├─> [2.2 OCR] EngineManager.extract_text()
  │   ├─> [2.3 後處理] Postprocessor.process()
  │   └─> page_results.append(text)
  │
  ├─> [3. 合併結果]
  │   └─> final_text = "\n\n--- Page X/Y ---\n\n".join(page_results)
  │
  ├─> [4. 整體品質評估] QualityAssessor.assess(final_text)
  │
  └─> [結束] Return OCRResult
```

---

## 整合點與 API 設計

### 內部整合點

#### 整合點 1: 與 ocr_service.py 整合

**整合方式**: 在現有 `ocr_service.py` 中新增入口函數

**介面定義**:
```python
# backend/app/lib/ocr_service.py

async def extract_text_enhanced(
    file_url: str,
    doc_type: str = "auto"
) -> dict:
    """增強 OCR 入口函數

    Returns:
        {
            'text': str,
            'page_count': int,
            'quality_score': float,
            'confidence': float,
            'metadata': dict
        }
    """
    from app.lib.ocr_enhanced import EnhancedOCRPipeline

    pipeline = EnhancedOCRPipeline(
        enable_preprocessing=settings.OCR_ENHANCED_MODE,
        enable_multi_engine=settings.OCR_MULTI_ENGINE,
        enable_quality_check=True
    )

    return await pipeline.process(file_url, doc_type)

# 保留現有函數
async def extract_text_from_document(file_url: str) -> tuple[str, int]:
    """標準 OCR 入口 (向後相容)"""
    # 現有實作不變
    pass
```

**相容性考量**:
- 現有 `extract_text_from_document()` 保持不變
- `document_service.py` 可透過配置選擇使用哪個函數
- 逐步遷移,降低風險

---

#### 整合點 2: 與 document_service.py 整合

**整合方式**: 修改 `process_document()` 函數,根據配置選擇 OCR 方法

**介面定義**:
```python
# backend/app/services/document_service.py

async def process_document(document_id: UUID, db: Session) -> Document:
    """處理文件"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    document.status = "processing"
    db.commit()

    try:
        start_time = time.time()

        # 選擇 OCR 方法
        if settings.OCR_ENHANCED_MODE:
            # 使用增強模式
            result = await extract_text_enhanced(document.file_url, doc_type="auto")
            ocr_text = result['text']
            page_count = result['page_count']
            quality_score = result.get('quality_score')
            metadata = result.get('metadata', {})
        else:
            # 使用標準模式
            ocr_text, page_count = await extract_text_from_document(document.file_url)
            quality_score = None
            metadata = {}

        ocr_time = int((time.time() - start_time) * 1000)

        # 儲存 OCR 結果
        ocr_result = DocumentOcrResult(
            document_id=document.id,
            raw_text=ocr_text,
            page_count=page_count,
            ocr_service=metadata.get('ocr_engines_used', settings.OCR_SERVICE),
            processing_time=ocr_time,
            quality_score=quality_score,
            enhanced_mode=settings.OCR_ENHANCED_MODE,
            preprocessing_params=metadata.get('preprocessing', {}),
            retry_count=metadata.get('retry_count', 0)
        )
        db.add(ocr_result)
        db.commit()

        # 繼續 AI 處理...
        # (現有邏輯不變)

    except Exception as e:
        document.status = "failed"
        document.error_message = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")
```

---

### 外部 API 設計

#### API 端點 1: 品質報告 API (新增)

**路徑**: `GET /api/v1/documents/{document_id}/ocr-quality-report`

**用途**: 獲取 OCR 品質評估報告

**請求參數**: 無

**回應格式**:
```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "quality_score": 85.5,
  "confidence": 0.92,
  "assessment": "良好",
  "metrics": {
    "confidence_score": 92.0,
    "character_density": 0.78,
    "field_match_rate": 0.95,
    "anomaly_rate": 0.02
  },
  "recommendations": [
    "OCR 品質良好,無需重新處理"
  ],
  "processing_details": {
    "engines_used": ["paddleocr", "tesseract"],
    "preprocessing_applied": true,
    "watermark_removed": true,
    "retry_count": 0,
    "processing_time_ms": 2500
  }
}
```

**錯誤碼**:
- 404: 文件不存在
- 404: OCR 結果不存在(文件尚未處理)
- 500: 伺服器錯誤

**實作**:
```python
# backend/app/api/v1/documents.py

@router.get("/{document_id}/ocr-quality-report")
async def get_ocr_quality_report(
    document_id: UUID,
    db: Session = Depends(get_db)
):
    """獲取 OCR 品質報告"""
    ocr_result = await document_service.get_ocr_result(document_id, db)
    if not ocr_result:
        raise HTTPException(404, "OCR result not found")

    if not ocr_result.enhanced_mode:
        raise HTTPException(400, "Quality report only available for enhanced mode")

    # 生成報告
    from app.lib.ocr_enhanced.quality_assessor import QualityAssessor

    assessor = QualityAssessor()
    metrics = assessor.assess(
        ocr_result.raw_text,
        float(ocr_result.ocr_confidence) if ocr_result.ocr_confidence else 0.0,
        doc_type="transcript"
    )

    report = assessor.generate_report(
        metrics,
        processing_history=[ocr_result.preprocessing_params or {}]
    )

    return {
        "document_id": str(document_id),
        "quality_score": float(ocr_result.quality_score) if ocr_result.quality_score else 0.0,
        "confidence": float(ocr_result.ocr_confidence) if ocr_result.ocr_confidence else 0.0,
        **report
    }
```

**對應需求**: [需求 4.7]

---

## 配置與部署

### 配置管理

**新增環境變數** (`backend/app/config.py`):
```python
class Settings(BaseSettings):
    # ... 現有設定 ...

    # OCR Enhancement Settings
    OCR_ENHANCED_MODE: bool = False                    # 是否啟用增強模式
    OCR_MULTI_ENGINE: bool = False                     # 是否啟用多引擎融合
    OCR_ENGINES: List[str] = ["paddleocr", "tesseract"] # 使用的引擎列表
    OCR_QUALITY_THRESHOLD: float = 60.0                # 品質閾值(0-100)
    OCR_MAX_RETRIES: int = 3                           # 最大重試次數

    # Preprocessing Settings
    OCR_WATERMARK_REMOVAL: bool = True                 # 是否移除浮水印
    OCR_POSTPROCESSING: bool = True                    # 是否啟用後處理
    OCR_PDF_DPI: int = 300                             # PDF 轉圖像 DPI
    OCR_BINARIZATION_METHOD: str = "gaussian"          # 二值化方法

    # Transcript-specific Settings
    TRANSCRIPT_FIELD_EXTRACTION: bool = True           # 是否啟用專用欄位提取

    # HSV Thresholds (可調參數)
    OCR_HSV_LOWER_H: int = 0
    OCR_HSV_LOWER_S: int = 50
    OCR_HSV_LOWER_V: int = 50
    OCR_HSV_UPPER1_H: int = 10
    OCR_HSV_UPPER2_H: int = 160
```

**配置驗證**:
```python
# backend/app/config.py

def validate_config(settings: Settings) -> None:
    """驗證配置正確性"""
    if settings.OCR_QUALITY_THRESHOLD < 0 or settings.OCR_QUALITY_THRESHOLD > 100:
        raise ValueError("OCR_QUALITY_THRESHOLD must be between 0 and 100")

    if settings.OCR_MAX_RETRIES < 0 or settings.OCR_MAX_RETRIES > 10:
        raise ValueError("OCR_MAX_RETRIES must be between 0 and 10")

    valid_engines = {"paddleocr", "tesseract", "textract"}
    for engine in settings.OCR_ENGINES:
        if engine not in valid_engines:
            raise ValueError(f"Invalid OCR engine: {engine}")

    print("✅ Configuration validated successfully")
```

---

### 部署策略

**部署步驟**:

1. **資料庫遷移**:
```bash
# 1.1 生成遷移腳本
alembic revision --autogenerate -m "Add OCR enhancement fields"

# 1.2 檢查遷移腳本
alembic history

# 1.3 執行遷移
alembic upgrade head

# 1.4 驗證遷移
alembic current
```

2. **Docker 映像建構**:
```dockerfile
# Dockerfile 更新

# 安裝 Tesseract 繁體中文語言包
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-chi-tra \
    && rm -rf /var/lib/apt/lists/*

# 確保 Python 依賴完整
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 預下載 PaddleOCR 繁體中文模型(避免首次啟動下載)
RUN python -c "from paddleocr import PaddleOCR; PaddleOCR(lang='chinese_cht')"
```

3. **環境變數設定**:
```bash
# .env 更新
OCR_ENHANCED_MODE=true
OCR_MULTI_ENGINE=false  # 先關閉多引擎,逐步啟用
OCR_QUALITY_THRESHOLD=60.0
OCR_MAX_RETRIES=3
OCR_WATERMARK_REMOVAL=true
OCR_POSTPROCESSING=true
OCR_PDF_DPI=300
```

4. **服務部署**:
```bash
# 使用 Docker Compose
docker-compose down
docker-compose build backend
docker-compose up -d

# 驗證服務健康狀態
curl http://localhost:8003/api/docs
```

5. **驗證部署**:
```bash
# 上傳測試文件
curl -X POST "http://localhost:8003/api/v1/documents/upload" \
  -F "file=@data/建物謄本.jpg"

# 觸發處理
curl -X POST "http://localhost:8003/api/v1/documents/{id}/process"

# 檢查品質報告
curl "http://localhost:8003/api/v1/documents/{id}/ocr-quality-report"
```

**回滾計劃**:
```bash
# 1. 關閉增強模式
# 編輯 .env: OCR_ENHANCED_MODE=false
docker-compose restart backend

# 2. 資料庫回滾(如果有問題)
alembic downgrade -1

# 3. 完全回滾到舊版本
git checkout <previous-commit>
docker-compose down
docker-compose build
docker-compose up -d
```

**監控指標**:

| 指標名稱 | 目標值 | 監控方式 | 警報閾值 |
|---------|--------|---------|---------|
| OCR 處理時間(JPG) | < 30秒 | APM / 日誌 | > 40秒 |
| OCR 處理時間(PDF) | < 90秒 | APM / 日誌 | > 120秒 |
| 品質分數平均值 | > 70 | 資料庫查詢 | < 60 |
| 重試率 | < 20% | 資料庫統計 | > 30% |
| 記憶體峰值 | < 1.5GB | Docker stats | > 2GB |
| API 錯誤率 | < 1% | APM | > 5% |

---

## 效能與可靠性

### 效能目標

| 指標 | 目標值 | 測量方式 | 優化策略 |
|------|--------|---------|---------|
| **單頁 JPG 處理時間** | < 30秒 | time.time() 計時 | 並行化預處理步驟 |
| **3頁 PDF 處理時間** | < 90秒 | time.time() 計時 | 多引擎並行,避免串行 |
| **多引擎融合時間** | < 60秒/頁 | asyncio.gather() 計時 | 使用免費引擎,避免 Textract |
| **記憶體用量** | < 1.5GB | Docker stats | 逐頁處理 PDF,及時釋放 |
| **並發處理能力** | 10 req/min | 壓力測試 | 限制並發數,避免 OOM |

**效能優化技巧**:
1. **圖像處理優化**: 使用 NumPy vectorized 操作,避免 Python 迴圈
2. **並行處理**: 多引擎使用 `asyncio.gather()`,預處理可使用 `ThreadPoolExecutor`
3. **快取機制**: 重複文件使用快取(可選,Phase 2)
4. **早期返回**: 品質分數達標時跳過重試

---

### 可靠性設計

**錯誤處理策略**:

| 階段 | 錯誤類型 | 處理策略 | 回退機制 |
|------|---------|---------|---------|
| **預處理失敗** | 圖像處理異常 | 記錄警告,使用原始圖像 | 100% 可用 |
| **OCR 單引擎失敗** | 引擎崩潰 | 使用其他引擎結果 | 多引擎保證可用性 |
| **OCR 全部失敗** | 所有引擎失敗 | 拋出異常,標記文件為失敗 | 人工介入 |
| **後處理失敗** | 正則表達式錯誤 | 使用原始 OCR 結果 | 100% 可用 |
| **品質評估失敗** | 評估邏輯錯誤 | 使用預設分數 50 | 功能降級 |
| **欄位提取失敗** | 正則匹配失敗 | 回退到 AI 提取 | 100% 可用 |

**降級機制**:

```python
# 降級層次
class DegradationLevel(Enum):
    FULL_ENHANCED = 1        # 完整增強模式
    NO_MULTI_ENGINE = 2      # 關閉多引擎融合
    NO_PREPROCESSING = 3     # 關閉預處理
    NO_POSTPROCESSING = 4    # 關閉後處理
    STANDARD_MODE = 5        # 完全降級為標準模式

# 自動降級邏輯
async def process_with_degradation(file_url: str):
    for level in DegradationLevel:
        try:
            return await _process_at_level(file_url, level)
        except Exception as e:
            logger.warning(f"Level {level} failed: {e}, degrading...")
            if level == DegradationLevel.STANDARD_MODE:
                raise  # 最後一級也失敗,拋出異常
```

**超時機制**:

```python
import asyncio

async def process_with_timeout(file_url: str, timeout: int = 120):
    """帶超時的處理函數"""
    try:
        return await asyncio.wait_for(
            _process_internal(file_url),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        logger.error(f"Processing timeout after {timeout}s")
        # 降級為單引擎模式重試
        return await _process_single_engine(file_url)
```

---

## 測試策略

### 單元測試

**測試範圍**:

| 模組 | 測試項目 | 工具 | 覆蓋率目標 |
|------|---------|------|-----------|
| **DocumentClassifier** | - classify()<br>- is_transcript() | pytest | 90%+ |
| **Preprocessor** | - remove_red_watermark()<br>- adaptive_binarize()<br>- denoise()<br>- adjust_resolution() | pytest<br>pytest-mock | 85%+ |
| **EngineManager** | - extract_text_multi_engine()<br>- _fuse_results()<br>- _standardize_confidence() | pytest-asyncio<br>pytest-mock | 85%+ |
| **Postprocessor** | - fix_traditional_chinese_typos()<br>- correct_field_formats()<br>- remove_duplicate_watermark_text() | pytest | 90%+ |
| **QualityAssessor** | - assess()<br>- should_retry()<br>- generate_report() | pytest | 90%+ |
| **FieldExtractor** | - extract_land_number()<br>- extract_area()<br>- validate_fields() | pytest | 95%+ |

**測試範例**:
```python
# tests/unit/test_preprocessor.py

import pytest
import numpy as np
from PIL import Image
from app.lib.ocr_enhanced.preprocessor import TranscriptPreprocessor

@pytest.fixture
def sample_image():
    """建立測試圖像"""
    return Image.new('RGB', (800, 600), color='white')

@pytest.fixture
def preprocessor():
    return TranscriptPreprocessor(config=PreprocessConfig())

def test_remove_red_watermark(preprocessor, sample_image):
    """測試紅色浮水印移除"""
    # 建立含紅色浮水印的圖像
    img_array = np.array(sample_image)
    img_array[100:200, 100:200] = [255, 0, 0]  # 紅色區塊

    # 執行移除
    result = preprocessor.remove_red_watermark(img_array)

    # 驗證紅色區塊被移除(變為白色)
    assert np.all(result[100:200, 100:200] >= [200, 200, 200])

def test_adaptive_binarize_gaussian(preprocessor):
    """測試 Gaussian 適應性二值化"""
    gray_image = np.random.randint(0, 256, (600, 800), dtype=np.uint8)

    result = preprocessor.adaptive_binarize(gray_image, method="gaussian")

    # 驗證輸出為二值化圖像(只有 0 或 255)
    assert np.all((result == 0) | (result == 255))
    assert result.shape == gray_image.shape
```

---

### 整合測試

**測試場景**:

```python
# tests/integration/test_ocr_pipeline.py

import pytest
from app.lib.ocr_enhanced import EnhancedOCRPipeline

@pytest.mark.asyncio
async def test_end_to_end_transcript_jpg():
    """端到端測試:建物謄本 JPG"""
    pipeline = EnhancedOCRPipeline(
        enable_preprocessing=True,
        enable_postprocessing=True,
        enable_multi_engine=False  # 單引擎加快測試
    )

    # 使用真實測試檔案
    file_url = "file:///app/data/建物謄本.jpg"

    result = await pipeline.process(file_url, doc_type="transcript")

    # 驗證結果
    assert result['text'] is not None
    assert result['page_count'] == 1
    assert result['quality_score'] > 60  # 品質分數應 > 閾值
    assert result['confidence'] > 0.7

    # 驗證關鍵欄位被正確識別
    assert "地號" in result['text'] or "㆞號" in result['text']
    assert "面積" in result['text']

@pytest.mark.asyncio
async def test_end_to_end_transcript_pdf():
    """端到端測試:建物土地謄本 PDF (3頁)"""
    pipeline = EnhancedOCRPipeline()

    file_url = "file:///app/data/建物土地謄本-杭州南路一段.pdf"

    result = await pipeline.process(file_url, doc_type="transcript")

    assert result['page_count'] == 3
    assert "--- Page 1/3 ---" in result['text']
    assert "--- Page 2/3 ---" in result['text']
    assert "--- Page 3/3 ---" in result['text']

    # 驗證處理時間 < 90秒
    assert result['metadata']['processing_time_ms'] < 90000

@pytest.mark.asyncio
async def test_multi_engine_fusion():
    """測試多引擎融合模式"""
    pipeline = EnhancedOCRPipeline(enable_multi_engine=True)

    file_url = "file:///app/data/建物謄本.jpg"
    result = await pipeline.process(file_url)

    # 驗證使用了多個引擎
    engines_used = result['metadata']['ocr_engines_used']
    assert len(engines_used) >= 2
    assert "paddleocr" in engines_used or "tesseract" in engines_used

    # 驗證融合後品質提升
    assert result['quality_score'] > 70
```

---

### 驗收測試 (UAT)

**成功標準**:

```python
# tests/acceptance/test_success_criteria.py

import pytest
from app.lib.ocr_enhanced import EnhancedOCRPipeline
from app.lib.ocr_service import extract_text_from_document

@pytest.mark.asyncio
async def test_accuracy_improvement_jpg():
    """驗收標準 1,2: JPG 準確率提升 >= 15%"""

    # Baseline: 標準 OCR
    baseline_text, _ = await extract_text_from_document(
        "file:///app/data/建物謄本.jpg"
    )
    baseline_accuracy = calculate_accuracy(baseline_text, ground_truth)

    # Enhanced: 增強 OCR
    pipeline = EnhancedOCRPipeline()
    result = await pipeline.process("file:///app/data/建物謄本.jpg")
    enhanced_accuracy = calculate_accuracy(result['text'], ground_truth)

    # 驗證提升 >= 15%
    improvement = enhanced_accuracy - baseline_accuracy
    assert improvement >= 0.15, f"Accuracy improvement: {improvement:.2%} < 15%"

@pytest.mark.asyncio
async def test_key_field_accuracy():
    """驗收標準 3: 關鍵欄位準確率 >= 95%"""
    pipeline = EnhancedOCRPipeline()
    result = await pipeline.process("file:///app/data/建物謄本.jpg")

    from app.lib.ocr_enhanced.field_extractor import TranscriptFieldExtractor
    extractor = TranscriptFieldExtractor()
    fields = extractor.extract(result['text'])

    # 驗證關鍵欄位
    expected = {
        'land_number': '0221-0000',
        'area': 153.00,
        'unified_id': 'A202*****6',
    }

    correct = 0
    total = len(expected)

    for key, value in expected.items():
        if fields.get(key) == value:
            correct += 1

    accuracy = correct / total
    assert accuracy >= 0.95, f"Field accuracy: {accuracy:.2%} < 95%"

@pytest.mark.asyncio
async def test_watermark_interference_reduction():
    """驗收標準 4: 浮水印干擾降低 >= 80%"""

    # 計算標準模式下浮水印文字出現次數
    baseline_text, _ = await extract_text_from_document(
        "file:///app/data/建物土地謄本-杭州南路一段.pdf"
    )
    baseline_watermark_count = baseline_text.count("已列印") + \
                               baseline_text.count("本謄本列印完畢")

    # 計算增強模式下浮水印文字出現次數
    pipeline = EnhancedOCRPipeline()
    result = await pipeline.process(
        "file:///app/data/建物土地謄本-杭州南路一段.pdf"
    )
    enhanced_watermark_count = result['text'].count("已列印") + \
                               result['text'].count("本謄本列印完畢")

    # 驗證降低 >= 80%
    if baseline_watermark_count > 0:
        reduction = 1 - (enhanced_watermark_count / baseline_watermark_count)
        assert reduction >= 0.80, f"Watermark reduction: {reduction:.2%} < 80%"

@pytest.mark.asyncio
async def test_processing_time_within_limit():
    """驗收標準 5: 處理時間不超過原有流程 2 倍"""

    import time

    # Baseline 處理時間
    start = time.time()
    await extract_text_from_document("file:///app/data/建物土地謄本-杭州南路一段.pdf")
    baseline_time = time.time() - start

    # Enhanced 處理時間
    pipeline = EnhancedOCRPipeline()
    start = time.time()
    await pipeline.process("file:///app/data/建物土地謄本-杭州南路一段.pdf")
    enhanced_time = time.time() - start

    # 驗證 <= 2 倍
    ratio = enhanced_time / baseline_time
    assert ratio <= 2.0, f"Processing time ratio: {ratio:.2f}x > 2.0x"

def calculate_accuracy(ocr_text: str, ground_truth: str) -> float:
    """計算準確率(字符級編輯距離)"""
    import difflib
    ratio = difflib.SequenceMatcher(None, ocr_text, ground_truth).ratio()
    return ratio
```

---

## 風險與緩解

### 技術風險

| 風險 ID | 風險描述 | 可能性 | 影響 | 嚴重程度 | 緩解措施 | 負責人 |
|---------|---------|--------|------|---------|---------|--------|
| **R1** | 浮水印移除過度,影響文字辨識 | 中 | 高 | **高** | 1. A/B 比較預處理前後信心度<br>2. 信心度下降 > 10% 時使用原始圖像<br>3. 可調 HSV 閾值參數 | 開發團隊 |
| **R2** | 多引擎並行處理時間超過 90 秒 | 中 | 中 | **中** | 1. 超時檢測(80秒警戒線)<br>2. 自動降級為單引擎<br>3. 配置僅使用免費引擎 | 開發團隊 |
| **R3** | PaddleOCR 繁體中文模型下載失敗 | 低 | 高 | **中** | 1. Docker 建構時預下載<br>2. 提供本地模型路徑配置<br>3. 降級為 Tesseract | DevOps |
| **R4** | 記憶體用量超過 1.5GB 限制 | 低 | 中 | **低** | 1. 逐頁處理 PDF<br>2. 及時釋放圖像記憶體<br>3. 監控記憶體峰值 | 開發團隊 |
| **R5** | 繁體中文錯別字字典不完整 | 中 | 低 | **低** | 1. Phase 1 使用基礎字典<br>2. Phase 2 持續擴充<br>3. 收集實際錯誤案例 | 開發團隊 |

---

### 營運風險

| 風險 ID | 風險描述 | 可能性 | 影響 | 嚴重程度 | 緩解措施 | 負責人 |
|---------|---------|--------|------|---------|---------|--------|
| **O1** | API 成本增加(Textract) | 低 | 低 | **低** | 1. 預設不使用 Textract<br>2. 透過配置開關控制<br>3. 優先使用免費引擎 | PM |
| **O2** | 處理時間過長影響用戶體驗 | 中 | 中 | **中** | 1. 顯示處理進度<br>2. 非同步處理,輪詢結果<br>3. 提供處理時間預估 | 產品團隊 |
| **O3** | Docker 映像大小增加 | 低 | 低 | **低** | 1. 使用 headless 版本 OpenCV<br>2. 多階段建構<br>3. 清理不必要檔案 | DevOps |
| **O4** | 部署回滾困難 | 低 | 中 | **低** | 1. 向後相容設計<br>2. 配置開關控制<br>3. 詳細回滾計劃 | DevOps |

---

## 實施里程碑

### Phase 1: 模組架構與核心模組 (Week 1-2, 10 天)

**目標**: 建立模組結構,實作預處理與引擎管理模組

**任務清單**:
- [ ] **Day 1**: 模組架構設計
  - 建立 `backend/app/lib/ocr_enhanced/` 目錄結構
  - 定義所有模組的 `__init__.py` 與介面
  - 建立 `EnhancedOCRPipeline` 框架
- [ ] **Day 2-4**: Preprocessor 模組實作
  - 實作 `remove_red_watermark()` (HSV 色彩空間)
  - 實作 `adaptive_binarize()` (Gaussian/Mean)
  - 實作 `denoise()` (GaussianBlur)
  - 實作 `adjust_resolution()`
  - 單元測試覆蓋率 > 85%
- [ ] **Day 5-7**: EngineManager 模組實作
  - 實作 `_run_paddleocr()` 並行處理
  - 實作 `_run_tesseract()` 並行處理
  - 實作 `_fuse_results()` (best 策略)
  - 實作 `_standardize_confidence()`
  - 單元測試覆蓋率 > 85%
- [ ] **Day 8**: DocumentClassifier 模組實作
  - 實作基於關鍵字的分類器
  - 單元測試覆蓋率 > 90%
- [ ] **Day 9**: Config 模組實作
  - 定義所有配置類別
  - 實作配置驗證
- [ ] **Day 10**: 整合測試
  - 端到端測試:預處理 → OCR
  - 效能測試:處理時間是否 < 30秒(JPG)

**交付物**:
- ✅ 預處理模組完整實作
- ✅ 引擎管理模組完整實作
- ✅ 單元測試通過,覆蓋率 > 85%
- ✅ 文件類型分類器實作

**里程碑驗證**:
```bash
pytest tests/unit/test_preprocessor.py -v --cov
pytest tests/unit/test_engine_manager.py -v --cov
pytest tests/integration/test_phase1.py -v
```

---

### Phase 2: 後處理與品質評估模組 (Week 2-3, 8 天)

**目標**: 實作後處理、品質評估與欄位提取模組

**任務清單**:
- [ ] **Day 11-13**: Postprocessor 模組實作
  - 建立繁體中文錯別字字典(50+ 項)
  - 實作 `fix_traditional_chinese_typos()`
  - 實作 `correct_field_formats()`
  - 實作 `remove_duplicate_watermark_text()`
  - 實作 `restore_logical_structure()`
  - 單元測試覆蓋率 > 90%
- [ ] **Day 14-15**: QualityAssessor 模組實作
  - 實作 `assess()` 品質評分算法
  - 實作 `should_retry()` 重試決策
  - 實作 `generate_report()` 品質報告
  - 單元測試覆蓋率 > 90%
- [ ] **Day 16-17**: FieldExtractor 模組實作
  - 編譯所有正則表達式模式
  - 實作各欄位提取函數
  - 實作 `validate_fields()` 驗證器
  - 整合 AI 回退機制
  - 單元測試覆蓋率 > 95%
- [ ] **Day 18**: 整合測試
  - 端到端測試:完整流程(預處理→OCR→後處理→評估)
  - 效能測試:3頁 PDF < 90秒
  - 品質測試:準確率提升 >= 15%

**交付物**:
- ✅ 後處理模組完整實作
- ✅ 品質評估模組完整實作
- ✅ 欄位提取模組完整實作
- ✅ 整合測試通過

**里程碑驗證**:
```bash
pytest tests/unit/test_postprocessor.py -v --cov
pytest tests/unit/test_quality_assessor.py -v --cov
pytest tests/unit/test_field_extractor.py -v --cov
pytest tests/integration/test_phase2.py -v
```

---

### Phase 3: 整合、API 與資料庫 (Week 3-4, 5 天)

**目標**: 整合所有模組,實作 API,更新資料庫

**任務清單**:
- [ ] **Day 19**: EnhancedOCRPipeline 整合
  - 整合所有模組到 Pipeline
  - 實作重試機制
  - 實作降級機制
  - 實作超時檢測
- [ ] **Day 20**: 資料庫遷移
  - Alembic 遷移腳本
  - 擴展 DocumentOcrResult 模型
  - 執行遷移與驗證
- [ ] **Day 21**: API 實作
  - 更新 `ocr_service.py` 新增 `extract_text_enhanced()`
  - 更新 `document_service.py` 整合增強模式
  - 新增品質報告 API
- [ ] **Day 22**: 配置與部署
  - 更新 `config.py` 新增環境變數
  - 更新 Dockerfile 安裝依賴
  - 更新 docker-compose.yml
  - 撰寫部署文件
- [ ] **Day 23**: 驗收測試
  - 執行所有驗收測試
  - 驗證 5 個成功標準
  - 效能測試與調優

**交付物**:
- ✅ 完整的 EnhancedOCRPipeline
- ✅ 資料庫遷移完成
- ✅ API 整合完成
- ✅ 部署文件完成
- ✅ 驗收測試通過

**里程碑驗證**:
```bash
pytest tests/acceptance/test_success_criteria.py -v
docker-compose up -d
curl http://localhost:8003/api/v1/documents/{id}/ocr-quality-report
```

---

### 總時程表

```
Week 1-2: Phase 1 - 模組架構與核心模組 (10天)
├─ Day 1:    模組架構設計
├─ Day 2-4:  Preprocessor 實作
├─ Day 5-7:  EngineManager 實作
├─ Day 8:    DocumentClassifier 實作
├─ Day 9:    Config 實作
└─ Day 10:   整合測試

Week 2-3: Phase 2 - 後處理與品質評估 (8天)
├─ Day 11-13: Postprocessor 實作
├─ Day 14-15: QualityAssessor 實作
├─ Day 16-17: FieldExtractor 實作
└─ Day 18:    整合測試

Week 3-4: Phase 3 - 整合、API 與資料庫 (5天)
├─ Day 19: Pipeline 整合
├─ Day 20: 資料庫遷移
├─ Day 21: API 實作
├─ Day 22: 配置與部署
└─ Day 23: 驗收測試

總工期: 23 天 (約 4.6 週)
```

---

## 附錄

### A. 參考資料

1. **OpenCV 官方文件**
   - [Color Space Conversions](https://docs.opencv.org/4.x/df/d9d/tutorial_py_colorspaces.html)
   - [Image Thresholding](https://docs.opencv.org/4.x/d7/d4d/tutorial_py_thresholding.html)

2. **PaddleOCR 文件**
   - [GitHub Repository](https://github.com/PaddlePaddle/PaddleOCR)
   - [PaddleOCR 3.0 Technical Report](https://arxiv.org/html/2507.05595v1)

3. **Tesseract OCR 文件**
   - [Improving Quality](https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html)

4. **研究論文**
   - "Sauvola Thresholding for Document Images" (2000)
   - "Ensemble Methods for OCR" (ACM)

### B. 術語表

| 術語 | 定義 |
|------|------|
| **HSV** | Hue, Saturation, Value - 色相、飽和度、明度色彩空間 |
| **適應性二值化** | 根據局部區域動態計算閾值的二值化方法 |
| **Otsu 方法** | 自動計算全域閾值的二值化方法 |
| **Sauvola 方法** | 基於局部均值與標準差的自適應二值化 |
| **形態學操作** | 開運算、閉運算等圖像處理操作 |
| **信心度融合** | 基於多個 OCR 引擎信心度合併結果 |
| **降級機制** | 功能失敗時自動回退到簡化版本 |

### C. 繁體中文錯別字字典 (精簡版)

```python
TRADITIONAL_CHINESE_TYPO_DICT = {
    # 注音符號替換
    "㆞": "地",
    "㆗": "中",
    "㆟": "人",
    "㈯": "土",
    "㊞": "印",
    "㆒": "一",
    "㆓": "二",
    "㆔": "三",
    "㆕": "四",
    "㈰": "日",
    "㈪": "月",
    "㈲": "有",
    "㊠": "項",

    # 全形數字替換
    "０": "0",
    "１": "1",
    "２": "2",
    "３": "3",
    "４": "4",
    "５": "5",
    "６": "6",
    "７": "7",
    "８": "8",
    "９": "9",

    # 常見 OCR 混淆字
    "苗": "苗",  # 避免混淆
    # ... (Phase 2 擴充)
}
```

---

**文件版本**: v1.0
**最後更新**: 2026-03-25
**設計狀態**: 已生成,待審核
**需求追溯**: 完整對應 requirements.md 中的需求 1-6
**對應研究**: research.md v1.0
**實施方案**: 方案 B (完全模組化)
