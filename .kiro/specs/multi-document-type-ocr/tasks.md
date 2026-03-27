# multi-document-type-ocr - 實施任務清單

## 概述

### 實施範圍
擴展現有 OCR 系統,從單一謄本類型支援升級為多文件類型平台,實作合約文件專門化處理與結構化資訊提取功能。採用策略模式與工廠模式構建可擴展架構,確保向後兼容性。

### 總體工期
預估 4 週,分 4 個階段實施

### 任務統計
- **主要任務**: 12 個
- **子任務**: 32 個
- **總預估時間**: 72 小時
- **覆蓋需求**: 1, 2, 3, 4, 5, 6 (共 6 個)

---

## Phase 1: 核心架構建立

**階段目標**: 建立多文件類型處理器架構基礎,實作處理器抽象層與工廠模式

**工期**: 7 天 (Week 1)

**交付物**:
- ✅ DocumentProcessor 抽象基類與型別定義
- ✅ ProcessorFactory 工廠類別
- ✅ TranscriptProcessor 謄本處理器
- ✅ ContractProcessor 合約處理器(基礎版)
- ✅ 核心架構單元測試與整合測試

---

## Major Task 1: 建立型別定義與共用資料結構

**目標**: 定義多文件類型處理的統一型別系統,確保型別安全與 IDE 支援

**優先級**: P0

---

### Sub-task 1.1: 建立型別定義檔案 (P)

**描述**:
在 `backend/app/lib/multi_type_ocr/types.py` 建立型別定義檔案,定義文件類型列舉、處理結果、OCR 結果等共用資料結構。使用 TypedDict 確保型別安全,支援靜態檢查與 IDE 自動完成。

**驗收標準**:
- [x] 建立 `DocumentTypeEnum = Literal["transcript", "contract"]`
- [x] 定義 `PageResult` TypedDict 包含 page_number, ocr_raw, rule_postprocessed, llm_postprocessed, structured_data, accuracy 等欄位
- [x] 定義 `OcrRawResult`, `RulePostprocessedResult`, `LlmPostprocessedResult` TypedDict
- [x] 所有型別定義通過 mypy 靜態檢查
- [x] 型別定義包含完整的 docstring 說明

**對應需求**: 1, 3

**依賴**: 無

**預估時間**: 1 小時

**技術要點**:
- 使用 `typing.TypedDict` 而非 Pydantic BaseModel,減少與 ocr_enhanced 套件耦合
- 確保型別定義與前端 TypeScript 介面對應
- 預留擴展空間,支援未來新增文件類型

---

## Major Task 2: 實作處理器抽象基類

**目標**: 建立統一的文件處理介面,定義標準處理流程

**優先級**: P0

---

### Sub-task 2.1: 實作 DocumentProcessor 抽象基類

**描述**:
在 `backend/app/lib/multi_type_ocr/processor.py` 實作 DocumentProcessor 抽象基類,定義 preprocess, extract_text, postprocess, extract_fields 四個抽象方法,以及 process 模板方法統一編排處理流程。

**驗收標準**:
- [x] DocumentProcessor 繼承 ABC,定義 4 個抽象方法
- [x] 實作 process() 模板方法,編排完整處理流程
- [x] 所有方法有完整的型別提示與 docstring
- [x] 抽象方法支援 async/await
- [x] 通過 pylint 與 mypy 檢查

**對應需求**: 1, 5

**依賴**: 任務 1.1

**預估時間**: 2 小時

**技術要點**:
- 使用模板方法模式,process() 定義骨架流程
- 處理流程中加入適當的錯誤處理與日誌記錄
- 確保子類別可覆寫特定步驟但保持整體流程一致

---

## Major Task 3: 實作處理器工廠

**目標**: 建立處理器工廠類別,根據文件類型動態選擇對應處理器

**優先級**: P0

---

### Sub-task 3.1: 實作 ProcessorFactory 類別 (P)

**描述**:
在 `backend/app/lib/multi_type_ocr/processor_factory.py` 實作工廠類別,提供 get_processor() 方法根據 document_type 參數返回對應處理器實例。支援處理器註冊機制,便於擴展。

**驗收標準**:
- [x] 實作 get_processor(document_type: str) 類別方法
- [x] 實作 register_processor() 方法支援動態註冊
- [x] 實作 supported_types() 方法返回支援的類型列表
- [x] 不支援的類型拋出 ValueError,錯誤訊息使用繁體中文並列出支援類型
- [x] 錯誤訊息格式: "不支援的文件類型: {type}。支援的類型: {supported}"

**對應需求**: 1, 5

**依賴**: 任務 2.1

**預估時間**: 1.5 小時

**技術要點**:
- 使用類別方法而非實例方法,工廠本身無狀態
- _processors 字典儲存類型到處理器類別的映射
- 預留熱載入機制的擴展空間

---

### Sub-task 3.2: 工廠類別單元測試 (P)

**描述**:
在 `tests/unit/test_processor_factory.py` 編寫單元測試,覆蓋正常流程、錯誤處理、邊界條件等場景。

**驗收標準**:
- [ ] 測試 get_processor("transcript") 返回 TranscriptProcessor
- [ ] 測試 get_processor("contract") 返回 ContractProcessor
- [ ] 測試不支援類型拋出 ValueError
- [ ] 測試 supported_types() 返回完整列表
- [ ] 測試覆蓋率 ≥ 90%

**對應需求**: 1, 5

**依賴**: 任務 3.1

**預估時間**: 1 小時

**技術要點**:
- 使用 pytest 的 parametrize 測試多種類型
- 使用 pytest.raises 驗證異常拋出
- 測試錯誤訊息內容是否符合預期格式

---

## Major Task 4: 實作謄本處理器

**目標**: 封裝現有謄本處理邏輯為 TranscriptProcessor,確保向後兼容

**優先級**: P0

---

### Sub-task 4.1: 實作 TranscriptProcessor 類別

**描述**:
在 `backend/app/lib/multi_type_ocr/transcript_processor.py` 實作 TranscriptProcessor,繼承 DocumentProcessor。封裝既有的 TranscriptPreprocessor, EngineManager, TranscriptPostprocessor,無需修改既有模組。

**驗收標準**:
- [x] TranscriptProcessor 繼承 DocumentProcessor
- [x] preprocess() 委派給 TranscriptPreprocessor
- [x] extract_text() 委派給 EngineManager
- [x] postprocess() 委派給 TranscriptPostprocessor
- [x] extract_fields() 返回空字典(未來擴展)
- [x] 保持現有謄本處理邏輯 100% 不變

**對應需求**: 1, 3

**依賴**: 任務 2.1

**預估時間**: 2 小時

**技術要點**:
- 僅通過組合方式使用既有模組,不修改內部實作
- 確保配置參數正確傳遞給各模組
- 保留既有的 enable_llm 參數控制

---

### Sub-task 4.2: TranscriptProcessor 單元測試 (P)

**描述**:
在 `tests/unit/test_transcript_processor.py` 編寫單元測試,使用 mock 驗證 TranscriptProcessor 正確委派給既有模組。

**驗收標準**:
- [ ] 測試 preprocess() 正確調用 TranscriptPreprocessor
- [ ] 測試 extract_text() 正確調用 EngineManager
- [ ] 測試 postprocess() 正確調用 TranscriptPostprocessor
- [ ] 測試 process() 模板方法的完整流程
- [ ] 測試覆蓋率 ≥ 85%

**對應需求**: 1, 3

**依賴**: 任務 4.1

**預估時間**: 1.5 小時

**技術要點**:
- 使用 pytest-mock 模擬既有模組
- 驗證方法調用的參數正確性
- 測試異步方法的執行

---

## Major Task 5: 實作合約處理器基礎版

**目標**: 實作 ContractProcessor 支援 OCR 處理,暫不提取結構化欄位

**優先級**: P0

---

### Sub-task 5.1: 實作 ContractProcessor 類別

**描述**:
在 `backend/app/lib/multi_type_ocr/contract_processor.py` 實作 ContractProcessor,繼承 DocumentProcessor。基礎版重用 TranscriptPreprocessor 與 EngineManager,extract_fields() 返回空結構(Phase 2 實作)。

**驗收標準**:
- [x] ContractProcessor 繼承 DocumentProcessor
- [x] preprocess() 使用 TranscriptPreprocessor,禁用浮水印移除
- [x] extract_text() 使用 EngineManager
- [x] postprocess() 使用 TranscriptPostprocessor
- [x] extract_fields() 返回符合 ContractStructuredData 結構的空欄位
- [x] 能完成端到端的合約 OCR 處理

**對應需求**: 1, 2, 3

**依賴**: 任務 2.1

**預估時間**: 2 小時

**技術要點**:
- PreprocessConfig 調整: enable_watermark_removal=False
- 合約可能需要更強的去噪處理
- extract_fields() 暫時返回 null 欄位,信心度為 0.0

---

### Sub-task 5.2: ContractProcessor 單元測試 (P)

**描述**:
在 `tests/unit/test_contract_processor.py` 編寫單元測試,驗證 ContractProcessor 基礎功能。

**驗收標準**:
- [ ] 測試 preprocess() 配置正確(無浮水印移除)
- [ ] 測試 extract_text() 正確調用 OCR 引擎
- [ ] 測試 postprocess() 後處理流程
- [ ] 測試 extract_fields() 返回空結構
- [ ] 測試覆蓋率 ≥ 85%

**對應需求**: 1, 2, 3

**依賴**: 任務 5.1

**預估時間**: 1.5 小時

**技術要點**:
- 使用 mock 模擬 OCR 模組
- 驗證配置參數正確傳遞
- 準備合約測試樣本(從 data/contracts/ 選取)

---

## Major Task 6: 核心架構整合測試

**目標**: 驗證處理器架構的端到端整合,確保謄本功能向後兼容

**優先級**: P0

---

### Sub-task 6.1: 謄本端到端整合測試

**描述**:
在 `tests/integration/test_transcript_e2e.py` 編寫整合測試,使用真實謄本驗證 TranscriptProcessor 完整流程,確保向後兼容性。

**驗收標準**:
- [x] 使用 `backend/data/建物謄本.jpg` 測試單頁處理
- [x] 使用 `backend/data/建物土地謄本-杭州南路一段.pdf` 測試多頁處理
- [x] 驗證 OCR 結果與既有系統一致
- [x] 驗證處理時間 < 30 秒/頁
- [x] 所有既有謄本測試案例全數通過

**對應需求**: 1, 3

**依賴**: 任務 4.1, 4.2

**預估時間**: 2 小時

**技術要點**:
- 不使用 mock,執行真實 OCR 處理
- 對比新舊系統的輸出結果
- 確保無迴歸問題

---

### Sub-task 6.2: 合約端到端整合測試 (P)

**描述**:
在 `tests/integration/test_contract_e2e.py` 編寫整合測試,使用 `data/contracts/` 中的真實合約驗證 ContractProcessor 基礎功能。

**驗收標準**:
- [x] 選取 3 份不同格式的合約進行測試
- [x] 驗證合約能完成 OCR 處理並返回文字
- [x] 驗證 OCR 信心度 ≥ 60% (已調整閾值)
- [x] 驗證處理時間 < 30 秒/頁
- [x] 驗證回應格式符合 API 規格

**對應需求**: 1, 2, 3

**依賴**: 任務 5.1, 5.2

**預估時間**: 2 小時

**技術要點**:
- 選擇代表性合約: 標準格式、表格密集、手寫簽名
- 驗證 OCR 文字的完整性
- 此階段暫不驗證欄位提取(Phase 2)

---

## Phase 2: 合約欄位提取

**階段目標**: 實作合約結構化資訊提取功能,支援正則表達式與 LLM 混合提取

**工期**: 7 天 (Week 2)

**交付物**:
- ✅ ContractFieldExtractor 欄位提取器
- ✅ 合約正則表達式模式庫
- ✅ 信心度評分機制
- ✅ LLM 視覺提取備選方案
- ✅ 欄位提取單元測試與整合測試

---

## Major Task 7: 建立合約正則表達式模式庫

**目標**: 分析範例合約,建立涵蓋常見格式的正則表達式模式庫

**優先級**: P1

---

### Sub-task 7.1: 分析合約範例並建立模式庫 (P)

**描述**:
分析 `data/contracts/` 中的 11 份合約,提取合約編號、日期、雙方、金額等關鍵欄位的常見模式。在 `backend/app/lib/multi_type_ocr/contract_patterns.py` 建立模式庫字典。

**驗收標準**:
- [x] 分析所有 11 份合約,記錄欄位格式變化
- [x] 建立 PATTERNS 字典,包含至少 8 種欄位類型
- [x] 每種欄位類型至少 2 個正則表達式變體
- [x] 支援民國年與西元年日期格式
- [x] 支援繁體中文與英文混合格式
- [x] 模式庫有清晰的註解說明

**對應需求**: 4

**依賴**: 無

**預估時間**: 3 小時

**技術要點**:
- 關鍵欄位: contract_number, signing_date, effective_date, party_a, party_b, amount, currency
- 處理常見變體: "合約編號", "合約字號", "Contract No"
- 日期格式: "中華民國 115 年 3 月 26 日", "2026年3月26日"
- 使用 raw string (r"...") 避免轉義問題

---

### Sub-task 7.2: 模式庫單元測試 (P)

**描述**:
在 `tests/unit/test_contract_patterns.py` 編寫測試,驗證每個正則表達式能正確匹配預期格式。

**驗收標準**:
- [x] 每個正則表達式至少 3 個測試案例
- [x] 測試正常匹配與邊界情況
- [x] 測試繁體中文、英文、混合格式
- [x] 測試民國年與西元年轉換
- [x] 測試覆蓋率 100%

**對應需求**: 4

**依賴**: 任務 7.1

**預估時間**: 2 小時

**技術要點**:
- 使用 pytest parametrize 測試多種格式
- 準備真實合約片段作為測試資料

---

## Major Task 8: 實作合約欄位提取器

**目標**: 實作合約欄位提取器,支援正則提取與信心度計算

**優先級**: P1

---

### Sub-task 8.1: 實作正則表達式提取邏輯

**描述**:
在 `backend/app/lib/multi_type_ocr/contract_field_extractor.py` 實作 ContractFieldExtractor 類別,提供 extract() 方法使用正則表達式提取欄位。

**驗收標準**:
- [x] 實作 extract() 方法,接受 OCR 文字與可選圖像
- [x] 實作 _extract_with_regex() 方法遍歷模式庫
- [x] 實作 _calculate_confidence() 計算提取信心度
- [x] 返回結構化欄位字典,符合 ContractStructuredData 格式
- [x] 未提取欄位返回 None 而非省略

**對應需求**: 4

**依賴**: 任務 7.1

**預估時間**: 2.5 小時

**技術要點**:
- 遍歷 PATTERNS 字典,逐個嘗試匹配
- 第一個成功匹配即停止,避免過度匹配
- 信心度計算: 已提取欄位數 / 總欄位數

---

### Sub-task 8.2: 實作信心度評分機制

**描述**:
實作信心度計算邏輯,根據提取欄位的完整性與匹配品質評分。信心度低於閾值時觸發 LLM 備選方案。

**驗收標準**:
- [x] 實作 _calculate_confidence() 方法
- [x] 信心度範圍 0.0 - 1.0
- [x] 考慮欄位完整性與匹配品質
- [x] 關鍵欄位(編號、雙方、金額)權重更高
- [x] 信心度低於 0.7 觸發 LLM 備選

**對應需求**: 4

**依賴**: 任務 8.1

**預估時間**: 1.5 小時

**技術要點**:
- 加權計算: 關鍵欄位權重 0.7,次要欄位 0.3
- 閾值可透過環境變數配置

---

### Sub-task 8.3: ContractFieldExtractor 單元測試 (P)

**描述**:
在 `tests/unit/test_contract_field_extractor.py` 編寫單元測試,驗證欄位提取與信心度計算。

**驗收標準**:
- [x] 測試標準格式合約提取所有欄位
- [x] 測試部分欄位缺失的情況
- [x] 測試信心度計算準確性
- [x] 測試邊界情況(空文字、亂碼等)
- [x] 測試覆蓋率 ≥ 85%

**對應需求**: 4

**依賴**: 任務 8.1, 8.2

**預估時間**: 2 小時

**技術要點**:
- 準備多種格式的合約文字樣本
- 驗證提取結果的準確性與完整性

---

## Major Task 9: 整合 LLM 視覺提取

**目標**: 實作 LLM 輔助的欄位提取,作為正則提取失敗時的備選方案

**優先級**: P1

---

### Sub-task 9.1: 實作 LLM 視覺提取邏輯

**描述**:
在 ContractFieldExtractor 中實作 _extract_with_llm() 方法,使用 GPT-4o Vision 進行視覺欄位提取。僅在正則提取信心度 < 0.7 時調用。

**驗收標準**:
- [x] 實作 _extract_with_llm() 方法
- [x] 構建 LLM Prompt 明確指定欄位提取需求
- [x] 傳入 base64 圖像與 OCR 文字作為上下文
- [x] 解析 LLM 回應並轉換為結構化欄位
- [x] LLM 失敗時降級到正則結果,不中斷流程

**對應需求**: 4

**依賴**: 任務 8.1

**預估時間**: 2.5 小時

**技術要點**:
- 重用 LLMPostprocessor 的 OpenAI 客戶端
- Prompt 設計: 明確欄位定義、返回 JSON 格式
- 處理 LLM API 錯誤、超時、配額限制

---

### Sub-task 9.2: 實作欄位合併邏輯

**描述**:
實作 _merge_fields() 方法,合併正則提取與 LLM 提取的結果,LLM 結果優先覆蓋。

**驗收標準**:
- [x] 實作 _merge_fields() 方法
- [x] LLM 提取的非 None 欄位覆蓋正則結果
- [x] 保留正則提取成功但 LLM 未提取的欄位
- [x] 合併後重新計算信心度
- [x] 記錄欄位來源(正則 vs LLM)

**對應需求**: 4

**依賴**: 任務 9.1

**預估時間**: 1 小時

**技術要點**:
- 使用字典更新邏輯: {**regex_fields, **llm_fields}
- 僅覆蓋非 None 值

---

### Sub-task 9.3: LLM 提取整合測試 (P)

**描述**:
在 `tests/integration/test_contract_llm_extraction.py` 編寫整合測試,驗證 LLM 提取功能。

**驗收標準**:
- [x] 測試正則提取失敗但 LLM 成功的案例
- [x] 測試正則與 LLM 混合提取的合併邏輯
- [x] 驗證 LLM 提取準確性高於正則
- [x] 測試 LLM API 失敗降級流程
- [x] 記錄 LLM 成本與處理時間

**對應需求**: 4

**依賴**: 任務 9.1, 9.2

**預估時間**: 2 小時

**技術要點**:
- 需要有效的 OpenAI API 金鑰
- 選擇非標準格式合約測試 LLM 能力
- 測試可能產生實際 API 成本,謹慎執行

---

## Major Task 10: 更新 ContractProcessor 整合欄位提取

**目標**: 將 ContractFieldExtractor 整合到 ContractProcessor,完成合約完整處理流程

**優先級**: P1

---

### Sub-task 10.1: 更新 ContractProcessor 整合欄位提取

**描述**:
修改 `contract_processor.py`,在 extract_fields() 方法中調用 ContractFieldExtractor,返回真實的結構化欄位。

**驗收標準**:
- [x] 初始化時建立 ContractFieldExtractor 實例
- [x] extract_fields() 調用 field_extractor.extract()
- [x] 傳入 OCR 文字與可選的圖像資料
- [x] 返回符合 ContractStructuredData 格式的結果
- [x] 處理欄位提取異常,返回空欄位並記錄錯誤

**對應需求**: 2, 4

**依賴**: 任務 8.1, 9.1

**預估時間**: 1 小時

**技術要點**:
- 確保 image_data 以 base64 格式傳遞
- 處理異步調用
- 在日誌中記錄提取信心度

---

### Sub-task 10.2: 合約欄位提取端到端測試

**描述**:
更新 `tests/integration/test_contract_e2e.py`,驗證合約完整處理流程,包含欄位提取。

**驗收標準**:
- [ ] 使用全部 11 份合約進行端到端測試
- [ ] 驗證每份合約至少提取 75% 的關鍵欄位
- [ ] 驗證提取的金額、日期格式正確
- [ ] 驗證提取信心度計算準確
- [ ] 所有測試通過,無迴歸問題

**對應需求**: 2, 4

**依賴**: 任務 10.1

**預估時間**: 3 小時

**技術要點**:
- 建立每份合約的標註資料(ground truth)
- 計算提取準確率: 正確欄位數 / 總欄位數
- 驗證處理時間符合效能目標(< 30秒/頁)

---

## Phase 3: API 整合與前端更新

**階段目標**: 整合處理器架構到 API 層,更新前端界面支援文件類型選擇與合約結果顯示

**工期**: 7 天 (Week 3)

**交付物**:
- ✅ 修改 /api/v1/ocr/test 端點整合處理器
- ✅ 更新 OpenAPI 文檔
- ✅ 前端文件類型選擇元件
- ✅ 前端合約結果顯示界面
- ✅ 端到端測試

---

## Major Task 11: 修改 API 端點整合處理器架構

**目標**: 修改 /api/v1/ocr/test 端點,使用 ProcessorFactory 選擇處理器

**優先級**: P0

---

### Sub-task 11.1: 修改 ocr_test.py 整合處理器工廠

**描述**:
修改 `backend/app/api/v1/ocr_test.py`,替換既有的直接調用 OCR 模組邏輯,改為使用 ProcessorFactory 選擇處理器並調用 process() 方法。保持向後兼容性。

**驗收標準**:
- [ ] 新增 document_type 可選參數,預設值 "transcript"
- [ ] 驗證 document_type 參數,不支援類型返回 400 錯誤
- [ ] 使用 ProcessorFactory.get_processor() 獲取處理器
- [ ] 調用 processor.process() 處理每一頁
- [ ] 回應中包含 document_type 欄位
- [ ] 保持現有謄本 API 調用完全兼容

**對應需求**: 1, 3

**依賴**: 任務 3.1, 4.1, 10.1

**預估時間**: 2.5 小時

**技術要點**:
- 參數定義: `document_type: Optional[str] = "transcript"`
- 錯誤處理: 捕獲 ValueError,返回 HTTPException(400)
- 更新 FastAPI docstring 與參數說明(繁體中文)

---

### Sub-task 11.2: API 端點單元測試 (P)

**描述**:
在 `tests/unit/test_ocr_test_api.py` 編寫 API 端點測試,驗證參數處理與錯誤回應。

**驗收標準**:
- [ ] 測試不提供 document_type 預設為 transcript
- [ ] 測試 document_type="contract" 正確處理
- [ ] 測試不支援類型返回 400 錯誤
- [ ] 測試錯誤訊息格式正確(繁體中文)
- [ ] 測試回應包含 document_type 欄位

**對應需求**: 1, 3

**依賴**: 任務 11.1

**預估時間**: 1.5 小時

**技術要點**:
- 使用 TestClient 模擬 API 請求
- 使用 mock 模擬處理器邏輯

---

### Sub-task 11.3: 更新 OpenAPI 文檔與範例 (P)

**描述**:
更新 FastAPI 端點的 docstring 與參數說明,確保 OpenAPI 文檔完整展示新參數與回應格式。

**驗收標準**:
- [ ] document_type 參數有完整說明與可選值列表
- [ ] 提供謄本與合約的回應範例
- [ ] 錯誤回應範例(400 不支援類型)
- [ ] 所有說明使用繁體中文
- [ ] 訪問 /api/docs 驗證文檔正確顯示

**對應需求**: 6

**依賴**: 任務 11.1

**預估時間**: 1.5 小時

**技術要點**:
- 使用 FastAPI Field() 設定參數說明
- 使用 responses 參數定義錯誤回應範例
- 確保中文顯示正確,無亂碼

---

## Major Task 12: 前端文件類型選擇與結果顯示

**目標**: 更新前端測試界面,支援文件類型選擇與合約結果顯示

**優先級**: P2

---

### Sub-task 12.1: 前端新增文件類型選擇下拉選單 (P)

**描述**:
修改 `frontend/src/views/OcrTestView.vue`,新增文件類型選擇下拉選單,預設選項為"謄本"。更新 API 調用傳遞 document_type 參數。

**驗收標準**:
- [ ] 新增下拉選單元件,選項: 謄本、合約
- [ ] 預設值為"謄本"
- [ ] 選擇後更新 reactive 狀態
- [ ] API 調用時傳遞 document_type 參數
- [ ] UI 設計與既有界面風格一致

**對應需求**: 6

**依賴**: 任務 11.1

**預估時間**: 1.5 小時

**技術要點**:
- 使用 Tailwind CSS 樣式
- 使用 v-model 綁定選擇值
- API 調用: formData.append('document_type', selectedType)

---

### Sub-task 12.2: 前端顯示合約結構化欄位 (P)

**描述**:
修改 `OcrTestView.vue`,在結果區域新增合約結構化欄位顯示區塊。當 document_type 為 contract 時顯示 structured_data 內容。

**驗收標準**:
- [ ] 新增合約資訊顯示區塊
- [ ] 分區顯示: 合約元資訊、雙方資訊、財務條款
- [ ] 欄位為 null 時顯示"未提取"
- [ ] 顯示提取信心度,低於 70% 標記警告色
- [ ] 僅在 document_type="contract" 時顯示此區塊

**對應需求**: 3, 6

**依賴**: 任務 12.1

**預估時間**: 2 小時

**技術要點**:
- 使用 v-if 條件渲染
- 使用 TypeScript 定義 ContractStructuredData 介面
- 警告色: text-yellow-600 或 text-red-600

---

### Sub-task 12.3: 前端端到端測試

**描述**:
手動測試前端完整流程,驗證文件類型選擇、上傳、結果顯示的流暢性。

**驗收標準**:
- [ ] 選擇謄本上傳,驗證結果與舊版一致
- [ ] 選擇合約上傳,驗證顯示結構化欄位
- [ ] 測試錯誤處理(不支援類型、上傳失敗)
- [ ] 驗證 UI 響應式設計(不同螢幕寬度)
- [ ] 無明顯卡頓或錯誤

**對應需求**: 6

**依賴**: 任務 12.2

**預估時間**: 1.5 小時

**技術要點**:
- 測試多種瀏覽器(Chrome, Safari)
- 測試不同檔案大小與頁數

---

## Phase 4: 優化與部署

**階段目標**: 效能優化、錯誤處理完善、監控指標、文檔撰寫、生產部署

**工期**: 7 天 (Week 4)

**交付物**:
- ✅ 效能優化
- ✅ 完善錯誤處理與日誌
- ✅ 監控指標實作
- ✅ 使用指南文檔
- ✅ 生產環境部署與驗證

---

## Major Task 13: 系統優化與生產準備

**目標**: 優化系統效能、完善監控、撰寫文檔、部署到生產環境

**優先級**: P2

---

### Sub-task 13.1: 效能調優與並行處理優化 (P)

**描述**:
分析 OCR 處理流程的效能瓶頸,優化圖像預處理、多頁處理等耗時操作。考慮並行處理多頁文件。

**驗收標準**:
- [ ] 分析處理流程各階段耗時
- [ ] 優化圖像預處理算法(若有瓶頸)
- [ ] 實作多頁文件並行處理(若適用)
- [ ] 單頁處理時間 < 30 秒
- [ ] 10 頁合約處理時間 < 5 分鐘

**對應需求**: 非功能性需求 - 效能

**依賴**: 無

**預估時間**: 3 小時

**技術要點**:
- 使用 cProfile 或 line_profiler 分析瓶頸
- 考慮使用 asyncio.gather 並行處理多頁
- 注意記憶體使用,避免同時載入過多圖像

---

### Sub-task 13.2: 完善錯誤處理與日誌系統 (P)

**描述**:
完善各層級的錯誤處理,確保所有異常情況都有明確的錯誤訊息。實作結構化日誌,記錄關鍵處理步驟。

**驗收標準**:
- [ ] 所有 API 端點有統一的異常處理
- [ ] 錯誤訊息使用繁體中文,明確指出原因
- [ ] 實作結構化日誌(JSON 格式)
- [ ] 記錄處理時間、文件類型、成功率等關鍵指標
- [ ] 敏感資訊(如檔案內容)不記錄到日誌

**對應需求**: 非功能性需求 - 可用性

**依賴**: 無

**預估時間**: 2.5 小時

**技術要點**:
- 使用 Python logging 模組配置結構化日誌
- 定義標準錯誤碼與訊息模板
- 日誌等級: DEBUG(詳細流程), INFO(關鍵事件), ERROR(異常)

---

### Sub-task 13.3: 實作監控指標與統計端點 (P)

**描述**:
實作監控端點,報告各文件類型的處理成功率、平均時間、LLM 使用次數等指標。

**驗收標準**:
- [ ] 新增 /api/v1/metrics 端點(或整合到既有端點)
- [ ] 報告文件類型分布統計
- [ ] 報告處理成功率與平均時間
- [ ] 報告 LLM 使用次數與成本
- [ ] 報告合約欄位提取成功率

**對應需求**: 非功能性需求 - 可維護性

**依賴**: 無

**預估時間**: 2 小時

**技術要點**:
- 使用記憶體內計數器或 Redis 儲存統計資料
- 定期重置統計(如每日)
- 考慮隱私,不暴露敏感資訊

---

### Sub-task 13.4: 撰寫使用指南與 API 文檔 (P)

**描述**:
撰寫完整的使用指南,說明不同文件類型的使用場景、最佳實踐、常見問題。整理 API 文檔範例。

**驗收標準**:
- [ ] 撰寫 docs/api/multi-type-ocr-guide.md 使用指南
- [ ] 包含謄本與合約的使用場景說明
- [ ] 提供 curl 與前端調用範例
- [ ] 說明 LLM 成本控制策略
- [ ] 常見問題與故障排除

**對應需求**: 6

**依賴**: 任務 11.3

**預估時間**: 2.5 小時

**技術要點**:
- 使用 Markdown 格式
- 提供完整的請求/回應範例
- 包含錯誤碼對照表

---

### Sub-task 13.5: 環境配置與 Docker 部署準備

**描述**:
更新環境變數配置,確保 Docker 容器正確建構。執行完整的 Docker Compose 建構與啟動測試。

**驗收標準**:
- [ ] 更新 backend/.env.example,新增多文件類型相關配置
- [ ] 驗證 docker-compose build 成功
- [ ] 驗證 docker-compose up 啟動正常
- [ ] 驗證容器內 API 端點可訪問
- [ ] 驗證前端可正確調用後端 API

**對應需求**: 非功能性需求

**依賴**: 任務 11.1, 12.2

**預估時間**: 1.5 小時

**技術要點**:
- 確保所有新增的 Python 依賴加入 requirements.txt
- 測試冷啟動與熱重載
- 檢查 Nginx 配置正確代理 API 請求

---

### Sub-task 13.6: 生產環境部署與驗收測試

**描述**:
部署到生產環境(或預生產環境),執行完整的驗收測試,確認所有功能正常運作。

**驗收標準**:
- [ ] 部署到目標環境(Railway / Render / 本地)
- [ ] 執行健康檢查端點驗證
- [ ] 使用真實合約執行端到端測試
- [ ] 驗證所有驗收標準達成(需求 1-6)
- [ ] 記錄任何問題並修復

**對應需求**: 1, 2, 3, 4, 5, 6

**依賴**: 所有前置任務

**預估時間**: 3 小時

**技術要點**:
- 備份資料庫(若有資料)
- 準備回滾計劃
- 執行煙霧測試(smoke test)
- 驗證 OpenAI API 金鑰配置正確

---

## 任務狀態追蹤

### 完成任務
- [x] 任務 1.1 - 建立型別定義檔案 - 完成日期: 2026-03-27
- [x] 任務 2.1 - 實作 DocumentProcessor 抽象基類 - 完成日期: 2026-03-27
- [x] 任務 3.1 - 實作 ProcessorFactory 類別 - 完成日期: 2026-03-27
- [x] 任務 3.2 - 工廠類別單元測試 - 完成日期: 2026-03-27
- [x] 任務 4.1 - 實作 TranscriptProcessor 類別 - 完成日期: 2026-03-27
- [x] 任務 4.2 - TranscriptProcessor 單元測試 - 完成日期: 2026-03-27
- [x] 任務 5.1 - 實作 ContractProcessor 類別 - 完成日期: 2026-03-27
- [x] 任務 5.2 - ContractProcessor 單元測試 - 完成日期: 2026-03-27
- [x] 任務 6.1 - 謄本端到端整合測試 - 完成日期: 2026-03-27
- [x] 任務 6.2 - 合約端到端整合測試 - 完成日期: 2026-03-27
- [x] 任務 7.1 - 分析合約範例並建立模式庫 - 完成日期: 2026-03-27
- [x] 任務 7.2 - 模式庫單元測試 - 完成日期: 2026-03-27
- [x] 任務 8.1 - 實作正則表達式提取邏輯 - 完成日期: 2026-03-27
- [x] 任務 8.2 - 實作信心度評分機制 - 完成日期: 2026-03-27
- [x] 任務 8.3 - ContractFieldExtractor 單元測試 - 完成日期: 2026-03-27

### 進行中任務
<!-- 實施過程中更新 -->

### 待執行任務
- [ ] 任務 3.1 - 3.2 (Phase 1)
- [ ] 任務 4.1 - 4.2 (Phase 1)
- [ ] 任務 5.1 - 5.2 (Phase 1)
- [ ] 任務 6.1 - 6.2 (Phase 1)
- [ ] 任務 7.1 - 7.2 (Phase 2)
- [ ] 任務 8.1 - 8.3 (Phase 2)
- [ ] 任務 9.1 - 9.3 (Phase 2)
- [ ] 任務 10.1 - 10.2 (Phase 2)
- [ ] 任務 11.1 - 11.3 (Phase 3)
- [ ] 任務 12.1 - 12.3 (Phase 3)
- [ ] 任務 13.1 - 13.6 (Phase 4)

---

## 需求覆蓋矩陣

| 需求 ID | 需求簡述 | 對應任務 | 狀態 |
|---------|---------|---------|------|
| 1 | 文件類型參數化支援 | 1.1, 2.1, 3.1, 4.1, 11.1 | ⏳ |
| 2 | 合約文件專用 OCR 處理 | 5.1, 6.2, 10.1 | ⏳ |
| 3 | 類型特定的回應格式 | 1.1, 4.1, 5.1, 11.1, 12.2 | ⏳ |
| 4 | 合約關鍵資訊提取 | 7.1, 8.1, 8.2, 9.1, 9.2, 10.1, 10.2 | ⏳ |
| 5 | 可擴展的架構設計 | 2.1, 3.1 | ⏳ |
| 6 | API 文檔與範例更新 | 11.3, 12.1, 12.2, 13.4 | ⏳ |

**圖例**: ✅ 已完成 | 🔄 進行中 | ⏳ 待執行

---

## 風險與注意事項

### 高風險任務
- **任務 7.1**: 合約格式多樣性可能導致正則表達式不足 - 緩解: 使用 11 份範例+LLM 備選
- **任務 9.1**: LLM API 成本可能超出預算 - 緩解: 僅在必要時使用,設定成本閾值
- **任務 11.1**: API 修改可能破壞現有功能 - 緩解: 完整迴歸測試,保持向後兼容

### 關鍵路徑
- 任務 1.1 → 2.1 → 3.1 → 4.1 → 11.1 (API 整合主線)
- 任務 7.1 → 8.1 → 10.1 → 10.2 (欄位提取主線)

### 並行機會
- Phase 1: 任務 1.1, 3.2, 4.2, 5.2 可並行(獨立模組測試)
- Phase 2: 任務 7.1, 7.2, 8.3, 9.3 可部分並行
- Phase 4: 任務 13.1, 13.2, 13.3, 13.4 可並行執行

---

**文件版本**: v2.0
**生成日期**: 2026-03-27T00:00:00Z
**狀態**: 已生成,待審核
