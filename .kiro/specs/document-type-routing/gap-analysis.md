# document-type-routing - 實施差距分析

> 分析既有程式庫與本規格需求的落差,供設計階段參考。
> 分析日期:2026-07-04｜對象分支:main｜語言:zh-TW

## 1. 執行摘要

- **好消息:路由骨架已存在**。`ProcessorFactory` + `DocumentProcessor`(ABC 模板方法)已是「按類型路由 + 各自 pipeline」的雛形,只是僅註冊 `transcript` / `contract` 兩型。本規格大多是「擴充 + 補齊」,而非打掉重建。
- **壞消息:整個「回饋學習層」幾乎從零開始**。人工複核佇列、校正樣本儲存、few-shot 範例庫、CER/欄位級準確率的持久化評估——**現況全缺**。這是本規格最大、風險最高的新建工作。
- **既有品質評估是空殼**。`QualityAssessor` 全為 TODO 且未被任何 pipeline 呼叫;真正生效的信心度門檻(全文 LLM 0.85、欄位 LLM 0.7)是**散落各處的硬編碼常數**,且未從 `config.py` 讀取。需求 6(信心度門檻)需先把這件事收斂。
- **VLM 能力已具備但未用於照片**。`LLMService.call/structured_extraction` 已支援多模態影像輸入(OpenAI image_url / Anthropic image block),目前僅用於合約欄位抽取;修繕照片(需求 5)無專屬 pipeline,可複用此能力接新 processor。
- **型別體系三處不一致**,是設計階段必須先統一的技術債:工廠(`transcript`/`contract`)、`DocumentClassifier`(`transcript`/`lease`/`id_card`)、`ai_service`(`lease_contract`/`repair_quote`/`id_card`)。
- **建議策略:混合式(擴充既有 + 新建回饋層)**,分三階段落地,與需求的 Phase 1/2/3 對齊。

---

## 2. 現有能力分析

### 2.1 相關元件清單

| 元件 | 位置 | 角色 | 可重用度 |
|---|---|---|---|
| `AnalyzeService` | `services/analyze_service.py` | `/analyze` 編排:上傳→逐頁 OCR→(問答)→統計→記錄用量 | 高(擴充切入點) |
| `POST /api/v1/analyze` | `api/v1/analyze.py` | 已接受 `document_type` 指定,型別白名單寫死 | 高 |
| `ProcessorFactory` | `lib/multi_type_ocr/processor_factory.py` | 類型→processor 動態註冊表 | **極高(路由核心)** |
| `DocumentProcessor` (ABC) | `lib/multi_type_ocr/processor.py` | 模板方法:preprocess/extract_text/postprocess/extract_fields | **極高(pipeline 契約)** |
| `TranscriptProcessor` / `ContractProcessor` | `lib/multi_type_ocr/` | 兩型具體 pipeline(薄封裝 ocr_enhanced) | 高 |
| `EngineManager` | `lib/ocr_enhanced/engine_manager.py` | 多引擎(含 PaddleOCR 單例、tesseract)融合 | 中(Paddle 未啟用) |
| `TranscriptPreprocessor` | `lib/ocr_enhanced/preprocessor.py` | 浮水印移除/二值化/去噪 | 高 |
| `ContractFieldExtractor` | `lib/multi_type_ocr/contract_field_extractor.py` | 規則+LLM Vision 混合欄位抽取 | 高(帳單可仿此) |
| `LLMService` | `lib/llm_service/llm_service.py` | 統一 LLM 封裝,**支援多模態影像** | **極高(VLM 基礎)** |
| `ApiUsageLog` | `models/api_usage_log.py` | 用量/成本記錄 | 中(評估可仿此) |
| `ocr_test.py` | `api/v1/ocr_test.py` | debug 端點,已有 `ground_truth` 字元相似度比對 | 中(評估邏輯種子) |

### 2.2 功能對照表(需求 vs 現有)

| 需求 | 現有支援 | 狀態 |
|---|---|---|
| R1 文件類型路由 | 工廠 + API `document_type`,但僅 2 型、白名單寫死、分類器未串接 | 🟡 部分 |
| R2 謄本 pipeline | `TranscriptProcessor` 有前處理/OCR/後處理;**欄位抽取回 `{}` 未實作**;硬編碼只用 tesseract;**無 PP-Structure** | 🟡 部分 |
| R3 帳單 pipeline | **完全缺**(無 bill/invoice processor);可仿 `ContractFieldExtractor` | 🔴 缺 |
| R4 合約 PDF pipeline | `ContractProcessor` + 欄位抽取已可用;**但文字層偵測缺**(PDF 一律 300DPI 轉圖走 OCR,未用 pymupdf 文字層/分段) | 🟡 部分 |
| R5 修繕照片 pipeline | **無專屬 processor**;VLM 影像輸入能力已具備 | 🔴 缺(有基礎) |
| R6 信心度門檻 + 複核佇列 | 硬編碼門檻散落各處;`QualityAssessor` 空殼未接;**無佇列/認領/鎖定** | 🔴 缺 |
| R7 校正樣本 + few-shot 回灌 | **完全缺**;`LLMService` 無範例注入介面;唯一「範例」是 prompt 內硬編碼錯字表 | 🔴 缺 |
| R8 評估指標(CER/欄位準確率) | 僅 debug 端點有字元相似度;正式流程 `accuracy` 恆 `None`;**無持久化、無 CER、無欄位級** | 🔴 缺 |
| R9 fine-tune 決策點 | **完全缺** | 🔴 缺 |

### 2.3 可重用資產(關鍵)
- **模板方法契約**:任何新類型只要實作 `DocumentProcessor` 四方法 + `ProcessorFactory.register_processor` 即接入,R3/R5 走此路。
- **VLM 通道**:`LLMService.structured_extraction(text, image_data, schema)` 可直接支撐帳單掃描件與修繕照片。
- **前處理**:`TranscriptPreprocessor` 的浮水印移除可直接供 R2 使用。

---

## 3. 差距詳細分析

### 3.1 路由層(R1)
- **差距**:型別白名單寫死於 API(`SUPPORTED_DOCUMENT_TYPES = {"transcript","contract"}`);三處型別體系不一致;`DocumentClassifier`(規則)未接入主流程。
- **挑戰**:需先建立**單一權威型別列舉**(建議 `transcript`/`bill`/`contract`/`repair_photo`),API 白名單改由工廠 `supported_types()` 動態產生;分類器僅作「建議」回傳,不改變「使用者指定為準」的契約(符合 R1.3)。
- **風險**:低。多為收斂重構。

### 3.2 謄本 pipeline(R2)— 優先
- **差距**:①欄位抽取未實作(`extract_fields` 回 `{}`);②硬編碼只用 tesseract,PaddleOCR/PP-Structure 未啟用;③無版面/表格結構化輸出。
- **挑戰**:PP-Structure 為**新外部依賴**(需自架、模型下載、CPU/GPU 資源),須 PoC 驗證繁中謄本實效與成本(研究已標註「繁中謄本無現成 benchmark」)。欄位抽取可先仿 `ContractFieldExtractor` 的規則+LLM Vision 模式落地,PP-Structure 作為增強項而非阻塞項。
- **風險**:中(外部依賴 + 無 benchmark,須自有樣本實測)。

### 3.3 帳單 pipeline(R3)
- **差距**:完全無 processor。
- **挑戰**:新建 `BillProcessor` + 帳單 `patterns` + 欄位 schema(金額/日期/戶號);掃描劣化件走 VLM(研究:原生影像餵多模態明顯優於先轉文字)。工作量中等,可高度複用 `ContractFieldExtractor` 模式。
- **風險**:低-中。

### 3.4 合約 PDF pipeline(R4)
- **差距**:`ContractProcessor` 已可用,但**缺文字層偵測**——目前 `AnalyzeService._process_ocr` 對所有 PDF 一律 300DPI 轉圖走 OCR,浪費含文字層合約的成本。無分段 chunking。
- **挑戰**:在編排層(`_process_ocr`)前置「PDF 文字層偵測」分支(pymupdf/pymupdf4llm):有層→直接抽文字+分段;無層→維持現行 OCR。此為新依賴但風險低、成本效益高。
- **風險**:低。

### 3.5 修繕照片 pipeline(R5)
- **差距**:無 processor;`repair_quote` 型別只存在於 `ai_service` 純文字軌,未接工廠。
- **挑戰**:新建 `RepairPhotoProcessor`,走 VLM(先用既有 `LLMService` 的 OpenAI Vision 出 POC,地端 Qwen2-VL 作為後續自架選項)。輸出瑕疵分類+描述+信心度。注意 `DocumentProcessor` 契約以「文字/OCR」為中心,照片型可能需微調基類或以 `structured_data` 承載理解結果。
- **風險**:中(基類契約對「非 OCR 型」的適配 + 地端 VLM 資源)。

### 3.6 信心度門檻 + 人工複核佇列(R6)— 最高風險
- **差距**:①門檻硬編碼散落、不可配置、`QualityAssessor` 空殼;②**無任何佇列/認領/鎖定/狀態機資料模型與 API**;③前端無複核介面。
- **挑戰**:需新增資料表(review queue / review item / 狀態機:待複核→複核中(認領鎖定)→已完成)、後端 API(列表/認領/釋出/提交校正)、前端複核頁(原文對照 + 可編輯欄位)。認領鎖定的併發控制(R6.7)需 DB 層樂觀/悲觀鎖。
- **風險**:高(跨後端資料模型 + API + 前端,工作量最大)。

### 3.7 校正樣本 + few-shot 回灌(R7)
- **差距**:無校正樣本表;`LLMService` 無 few-shot 注入介面(prompt 為固定模板)。
- **挑戰**:①新增 correction sample 表(依類型分庫、含原始輸入/校正後值/是否黃金範例);②`LLMService` / 各 processor 的 extract 需新增「範例注入」參數;③範例選取策略(相似度/最近 N 筆)與去重(R7.5)。與 R6 強耦合(校正來源即複核提交)。
- **風險**:中-高。

### 3.8 評估指標(R8)
- **差距**:正式流程 `accuracy` 恆 `None`;僅 debug 端點有字元相似度;無 CER、無欄位級準確率、無持久化。
- **挑戰**:需標註樣本集管理 + CER/欄位準確率計算 + 依類型記錄基準線與前後對照。`ocr_test.py` 的相似度邏輯可作種子,但需正規化為 CER 並持久化。
- **風險**:中。此為 R2/R7 能否證明「越來越準」的前提,**建議與 R6 併於 Phase 1 早做**。

### 3.9 fine-tune 決策點(R9)
- **差距**:完全缺,但本規格只要求「決策準則 + 標示」,不含訓練實作。
- **風險**:低(以 R8 指標 + 樣本量門檻的判斷邏輯即可)。

---

## 4. 實施方案建議

### 方案 A:最大化擴充既有工廠(推薦)
- **描述**:沿用 `ProcessorFactory` / `DocumentProcessor`,新增 `BillProcessor` / `RepairPhotoProcessor`,補齊謄本欄位抽取;回饋層(佇列/樣本/評估)作為**新的獨立模組 + 資料表**,透過 `AnalyzeService` 編排串接;信心度收斂為可配置的統一評估點(復活 `QualityAssessor`)。
- **優點**:最大複用、與現有架構一致、增量交付、風險可控、符合分層規範。
- **缺點**:需先償還「型別體系不一致」「門檻硬編碼」技術債;基類對照片型的適配需設計。
- **工作量**:中-大(主要在 R6/R7/R8 新建)。
- **風險**:中。

### 方案 B:回饋層獨立為新服務層,pipeline 全部重寫對齊
- **描述**:重新設計統一的 processor 契約(含非 OCR 型),回饋層自成子系統。
- **優點**:架構最乾淨、對照片/多模態一等公民支援。
- **缺點**:重寫成本高、與 MVP 成本/時程相悖、丟棄可用的合約 pipeline。
- **工作量**:大。
- **風險**:高。

### 方案 C:僅接雲端 IDP(AWS BDA blueprint)
- **描述**:直接用雲端 per-type blueprint。
- **優點**:最省開發。
- **缺點**:**違反地端/隱私偏好與 <$15/月 成本限制**(research.md caveat 5),個資外送風險。
- **風險**:與需求不符,不建議。

**推薦:方案 A**。理由:既有工廠骨架正好是需求要的路由架構,複用度最高;回饋層本就是全新需求,獨立新建不影響既有;完全符合地端/成本/分層原則。

---

## 5. 技術研究需求(設計階段 / PoC)

1. **PP-StructureV3 地端 PoC**:以自有謄本樣本實測欄位級準確率、CPU/GPU 資源與冷啟動成本,決定是「主力」或「謄本增強選項」。(研究:繁中謄本無現成 benchmark)
2. **pymupdf4llm 文字層偵測**:驗證合約 PDF 文字層判定準則與分段輸出品質,量測省下的 OCR 成本。
3. **地端 VLM 選型**:Qwen2-VL 2B/7B(vs 先用 OpenAI Vision 出 POC)在修繕照片瑕疵辨識的繁中效果與最低硬體需求。
4. **few-shot 範例注入策略**:範例選取(相似度/最近 N)、注入 token 成本、對準確率的邊際效益。
5. **複核佇列併發模型**:認領鎖定用悲觀鎖 vs 樂觀鎖 + 版本欄的取捨。

---

## 6. 整合策略

### 6.1 API 設計考量
- `POST /api/v1/analyze`:`document_type` 白名單改由 `ProcessorFactory.supported_types()` 動態產生;新增 `bill` / `repair_photo`。
- 新增複核相關端點(列表/認領/釋出/提交校正)與評估端點(基準線/前後對照);沿用現行 `{"detail": ...}` 錯誤格式與繁中訊息。

### 6.2 資料模型變更(新增,不破壞既有)
- `review_queue_item`(文件、類型、整體信心度、狀態、認領者、鎖定時間)。
- `correction_sample`(類型、原始輸入參照、校正後欄位 JSONB、是否黃金範例、來源複核參照)。
- `evaluation_record`(類型、指標種類 CER/欄位準確率、數值、樣本集版本、時間)。
- 沿用 `JSONB`(現有 `DocumentAiResult.extracted_data` 已用 GIN 索引,慣例一致)。

### 6.3 向後相容策略
- 既有 `transcript`/`contract` 行為預設不變;新增型別與回饋層以**加法**方式導入。
- 信心度門檻統一收斂時,預設值對齊現行硬編碼(全文 0.85 / 欄位 0.7),再開放 `config.py` 調整(R6.6),避免行為突變。

### 6.4 配置與部署
- 新依賴(PP-Structure / pymupdf4llm / 地端 VLM)須評估 Docker 映像體積與資源;VLM 建議可選、預設關閉,契合 <$15/月 與地端偏好。
- 雲端 API 一律「組態明確開啟、預設關閉」(R 非功能:隱私)。

---

## 7. 對需求的回饋建議(供修訂參考)
- **建議先做的技術債收斂**應在設計中明列為前置任務:統一型別列舉、復活/取代 `QualityAssessor` 為統一信心度評估點。
- **R2 的 PP-Structure** 建議在需求/設計中定位為「增強項」而非硬性依賴,以免 PoC 不如預期時阻塞謄本主線(規則+LLM Vision 欄位抽取已足以先交付)。
- **R5 基類契約**:設計需決定是否擴充 `DocumentProcessor` 以一等公民支援「非 OCR 影像理解型」。

---

**文件版本**: 1.0
**最後更新**: 2026-07-04
**狀態**: gap-analysis-complete
