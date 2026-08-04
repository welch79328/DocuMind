# ocr-vlm-consensus - 實施差距分析

## 1. 執行摘要

### 分析範圍

針對 `requirements.md` 六項需求,盤查 `backend/app/lib/ocr_enhanced/`、`backend/app/lib/multi_type_ocr/`、`backend/app/lib/llm_service/`、`backend/app/services/evaluation_service.py`、既有標註資料與版控狀態。

### 主要發現

1. **需求 2(雙模態校正)不是「尚未實作」,而是「實作後被刻意停用」**
   `LLMPostprocessor.correct_full_text()` 的 `image_data` 參數早已存在,但呼叫 LLM 時硬編碼傳 `None`,原因寫在註解:「避免 PII 過濾拒絕處理」。同時 prompt 內文仍保留「請仔細查看上面提供的文件圖片」的指示——**目前是在要求模型查看一張不存在的圖片**,屬現存缺陷。此發現將需求 2 的性質從「新增功能」改為「解除既有封鎖 + 處理 PII 拒絕」。

2. **`image_data` 的管線佈線已完整貫穿,唯一斷點在最末端**
   `DocumentProcessor.process()` 已將原圖編碼為 base64 並逐層傳遞至 `analyze()` → `postprocess()` / `extract_fields()`。整條路徑都接受並傳遞 `image_data`,唯一中斷處是 `correct_full_text()` 內的一行 `image_data=None`。管線改造工作量趨近於零,真正的工作在 PII 與 Provider 選型。

3. **並存兩套 LLM 服務,且僅其中一套支援本地部署**
   `llm_postprocessor` 使用舊的 `LLMService`(僅 openai / anthropic,**無本地選項**);`repair_photo_processor` 使用新的 `providers.create_provider()`(支援 `local_qwen` 與 `LLM_CLOUD_ENABLED` 隱私守衛)。由於規避 PII 過濾的主要手段是改用本地模型,**需求 2 隱含一項前置工作:將 `llm_postprocessor` 遷移至新 Provider 抽象**。此項未寫入 requirements。

4. **並存兩套評估體系,彼此未接通**
   體系 A(檔案型):`ground_truth.json` + `run_baseline_benchmark.py`,以 `difflib.SequenceMatcher` 算相似度,不需資料庫。
   體系 B(資料庫型):`EvaluationService` 以 `CorrectionSample.purpose='holdout'` 為 ground truth,計算 CER 與欄位準確率。
   現有 JSON 標註**沒有匯入資料庫的路徑**。需求 1 要求輸出 CER 與欄位準確率(體系 B 的指標),但標註資料在體系 A。需補一座橋。

5. **標註成果有遺失風險(P0)**
   `.gitignore` 含 `/data/` 與 `/tests/`,因此標註對象(11 份合約 PDF)與標註成果(`tests/fixtures/ground_truth.json`、`data/contracts/ground_truth.json`)**皆不在版控內**。進版控的是 `backend/tests_all/` 下的副本。在決定存放位置前投入 1~2 人天標註,成果可能因換機或清理而消失。

### 建議策略

採**混合策略**:需求 1 新建匯入橋接與存放規範(P0,且須在標註動工前完成);需求 2 以「解除封鎖 + Provider 遷移」處理,不新建元件;需求 3、4 擴展既有 `EngineManager`,但需求 4 需擴展回傳型別以承載欄位級信心度。

---

## 2. 現有能力分析

### 相關元件清單

| 元件 | 路徑 | 與本規格的關係 |
|------|------|----------------|
| `LLMPostprocessor` | `lib/ocr_enhanced/llm_postprocessor.py` | 需求 2 主要改動點 |
| `LLMService`(舊) | `lib/llm_service/llm_service.py` | 僅雲端,需求 2 的遷移來源 |
| `create_provider`(新) | `lib/llm_service/providers.py` | 支援本地與隱私守衛,遷移目標 |
| `EngineManager` | `lib/ocr_enhanced/engine_manager.py` | 需求 3、4 主要改動點 |
| `QualityAssessor` | `lib/ocr_enhanced/quality_assessor.py` | 需求 4 下游,介面不得變更 |
| `DocumentProcessor` 階層 | `lib/multi_type_ocr/processor.py` | 需求 6 相容性保護對象 |
| `EvaluationService` | `services/evaluation_service.py` | 需求 1 指標計算 |
| `CorrectionSampleService` | `services/correction_sample_service.py` | 需求 1 holdout 資料來源 |
| `run_baseline_benchmark.py` | `tests/run_baseline_benchmark.py` | 需求 1 既有(未執行)基準腳本 |

### 功能對照表(需求 vs 現有)

| 需求 | 現有能力 | 狀態 |
|------|----------|------|
| 1. 標註資料集 | 謄本 2 份已標註;合約 11 份欄位全為 `null` | 🟡 部分 |
| 1. CER / 欄位準確率計算 | `EvaluationService.evaluate()` 已實作 | 🟢 可重用 |
| 1. 基準線持久化 | `record_baseline()`、`EvaluationRecord` 已實作 | 🟢 可重用 |
| 1. 標註 → holdout 匯入 | `POST /samples/{type}/seed` 支援指定 `purpose` | 🟡 缺 JSON 轉檔橋接 |
| 1. 訓練/評估隔離 | `list_for_fewshot()` 硬性僅回 `train` | 🟢 已滿足 |
| 1. 觸發率統計 | 無 | 🔴 缺 |
| 1. 樣本數不足時拒絕標記基準 | 無(`evaluate()` 樣本為空僅回 0) | 🔴 缺 |
| 2. `image_data` 管線傳遞 | 全鏈路已佈線 | 🟢 已滿足 |
| 2. 雙模態呼叫 | 參數存在但硬編碼 `None` | 🔴 遭封鎖 |
| 2. 影像失敗降級 | `_is_refusal()` 已處理 LLM 拒絕 | 🟡 部分 |
| 2. 欄位級信心度輸出 | 無 | 🔴 缺 |
| 3. 引擎註冊機制 | `EngineManager` 引擎為硬編碼分支,非註冊表 | 🟡 需擴展 |
| 3. 信心度標準化 | `_standardize_confidence()` 已實作 | 🟢 可重用 |
| 3. 引擎降級 | `extract_text_multi_engine()` 有 `valid_results` 過濾 | 🟡 部分 |
| 3. 停用雲端時僅載入本地 | `create_provider()` 有守衛,但 `EngineManager` 無 | 🟡 部分 |
| 4. 多引擎原始結果保留 | `extract_text_multi_engine()` 已回傳 `valid_results` | 🟢 已滿足 |
| 4. 逐欄位一致性比對 | 四種融合模式皆為「選單一贏家」 | 🔴 缺 |
| 4. 欄位級信心度承載 | `_fuse_results()` 回傳 `tuple[str, float]`,無欄位維度 | 🔴 型別限制 |
| 5. 分層觸發 | 無 | 🔴 缺 |
| 5. 成本記錄 | `ApiUsageLog` 已記錄 `llm_cost`、`processing_time_ms` | 🟢 可重用 |
| 6. 既有測試套件 | `backend/tests/unit/` 57 個測試檔 | 🟢 可作迴歸網 |

### 可重用資產

- **指標計算**:`character_error_rate()`、`field_accuracy()`、`EvaluationService.compare()` 皆已實作且有測試覆蓋
- **資料隔離**:防洩漏機制(`list_for_fewshot` 硬性僅回 train)已是既成設計,需求 1.7 無需新做
- **用量與成本**:`ApiUsageLog` 已有 `document_type` / `llm_cost` / `processing_time_ms` 欄位,需求 5 的成本歸因可直接擴充
- **多引擎結果透傳**:`extract_text_multi_engine()` 已回傳各引擎原始結果,需求 4.4 已滿足
- **迴歸安全網**:57 個既有單元測試 + 4 個整合測試,可直接作為需求 6 的驗收依據

---

## 3. 差距詳細分析

### 需求 1:可驗證準確率基準

**差距**

| 項目 | 說明 | 位置 |
|------|------|------|
| 標註量不足 | 謄本僅 2 份,需求要求 ≥30 份 | `tests/fixtures/ground_truth.json` |
| 合約標註未填 | 11 份全為 `null`,標記「需人工標註」 | `data/contracts/ground_truth.json` |
| 缺匯入橋接 | JSON 標註無路徑進入 `CorrectionSample(purpose='holdout')` | — |
| 缺樣本數守衛 | `evaluate()` 於 holdout 為空時回傳 0 值而非拒絕 | `evaluation_service.py:118-120` |
| 缺觸發率統計 | 無「低信心攔截觸發率」的計算與輸出 | — |
| 指標定義不一致 | 腳本用 `SequenceMatcher` 相似度,服務用 CER;兩者不可直接比較 | `run_baseline_benchmark.py:27` |

**技術挑戰**
- 兩套評估體系的指標語意不同,需決定以何者為正式基準(建議體系 B,因其為既有回饋學習層的一部分)
- 標註 30 份謄本需具備地政判讀能力的人力,屬專案外部相依

**風險評估**

| 風險 | 等級 | 說明 |
|------|------|------|
| 標註成果遺失 | 🔴 高 | `/data/`、`/tests/` 皆在 `.gitignore`,須先定案存放位置 |
| 標註品質不一 | 🟡 中 | 多人標註需有一致性規範,否則基準本身不可信 |
| 樣本數仍不足 | 🟡 中 | 30 份為估計值,若版型變異大則偵測力不足 |

---

### 需求 2:雙模態 LLM 校正

**差距**

| 項目 | 說明 | 位置 |
|------|------|------|
| 雙模態遭硬編碼封鎖 | `image_data=None` 且註解說明為規避 PII 過濾 | `llm_postprocessor.py:69-76` |
| prompt 與實作不一致 | prompt 要求「查看上面提供的文件圖片」,但未傳圖 | `llm_postprocessor.py:283` |
| 無本地 Provider 支援 | 舊 `LLMService` 僅 openai / anthropic | `llm_service.py:73-84` |
| 無欄位級信心度輸出 | `correct_full_text()` 僅回傳文字與統計 | `llm_postprocessor.py:49-83` |

**技術挑戰**
- **PII 過濾是需求 2 的核心障礙,非邊緣情況**。謄本含姓名、統一編號、地址,雲端模型的安全過濾可能拒絕處理影像。既有 `_is_refusal()` 的存在證明此問題曾實際發生
- 解除封鎖前需先確立 Provider 路線,否則會重現當初停用的原因

**風險評估**

| 風險 | 等級 | 說明 |
|------|------|------|
| PII 拒絕重現 | 🔴 高 | 若僅移除 `image_data=None` 而不換 Provider,將回到當初停用的狀態 |
| 個資外送 | 🔴 高 | 傳影像至雲端等同外送完整文件,與「地端優先」約束衝突 |
| 成本上升 | 🟡 中 | 影像 token 成本高於純文字,需納入 $15/月試算 |

---

### 需求 3:視覺語言 OCR 引擎整合

**差距**

| 項目 | 說明 | 位置 |
|------|------|------|
| 引擎為硬編碼分支 | `_run_paddleocr()` / `_run_tesseract()` 為具名方法,非註冊表 | `engine_manager.py:127,194` |
| 無雲端守衛 | `EngineManager` 未檢查 `LLM_CLOUD_ENABLED` | `engine_manager.py` |
| 引擎降級未明確 | 僅過濾失敗結果,無「次選引擎」概念 | `engine_manager.py:119` |

**技術挑戰**
- `ProcessorFactory` 已有成熟的註冊表模式(`register_processor`),`EngineManager` 可比照重構,但屬既有元件改造,需確保現有兩引擎行為不變
- 視覺語言引擎的推論速度與 GPU 需求,可能牴觸「30 秒/頁」的效能需求

**風險評估**

| 風險 | 等級 | 說明 |
|------|------|------|
| GPU 相依 | 🔴 高 | 現行部署為 Docker + CPU(`opencv-python-headless`),無 GPU 配置 |
| 效能不達標 | 🟡 中 | CPU 推論可能遠超 30 秒/頁 |
| 引擎重構影響既有行為 | 🟡 中 | 有 57 個既有測試可作安全網 |

---

### 需求 4:共識信心度融合

**差距**

| 項目 | 說明 | 位置 |
|------|------|------|
| 無逐欄位比對 | 四種融合模式皆回傳單一贏家結果 | `engine_manager.py:267-364` |
| 回傳型別無欄位維度 | `_fuse_results()` 回傳 `tuple[str, float]` | `engine_manager.py:267` |
| 無共識不可用標記 | 單引擎時無法區分「高信心」與「無共識訊號」 | — |

**技術挑戰**
- **這是本規格最大的型別相容性挑戰**。需求 4 要求欄位級信心度,但現有融合回傳僅有「文字 + 單一信心度」。擴展回傳型別會影響 `extract_text_multi_engine()` 的所有呼叫端
- 逐欄位比對需先有欄位,但融合發生在 OCR 階段(尚未抽欄位)。**架構上需決定共識比對發生在文字層或欄位層**——此為設計階段的核心待決事項
- 好消息:`extract_text_multi_engine()` 已回傳 `valid_results`,上層可取得各引擎原始結果,故共識比對可考慮下移至欄位抽取後執行,避免改動融合回傳型別

**風險評估**

| 風險 | 等級 | 說明 |
|------|------|------|
| 回傳型別破壞相容 | 🔴 高 | 直接擴展 `_fuse_results()` 回傳會影響既有呼叫端與測試 |
| 共識假設不成立 | 🟡 中 | 若兩引擎錯誤高度相關(同樣看錯),共識訊號將失效;需求 4.6 已要求實證 |
| 複核量暴增 | 🟡 中 | 過度敏感的不一致判定會使複核佇列塞爆,需門檻調校 |

---

### 需求 5:分層成本控制

**差距**:分層邏輯、觸發率統計、成本效益判斷提示皆為全新,現有僅 `ApiUsageLog` 可重用。

**技術挑戰**:啟用條件綁定需求 1 的實測觸發率,在基準產出前無法定案門檻值。

**風險評估**

| 風險 | 等級 | 說明 |
|------|------|------|
| 分層反而更貴 | 🟡 中 | 觸發率高時總成本 = 第一層 + 判斷 + 第二層;需求 5.4 已要求系統主動提示 |
| 過早實作 | 🟡 中 | 建議待需求 1 數據產出後再定案,故列 P2 |

---

### 需求 6:既有架構相容性保護

**差距**:無新增功能,但需明確定義「行為不變」的驗證方式。

**可重用資產**:`backend/tests/unit/` 57 個測試檔 + `backend/tests/integration/` 4 個整合測試,已涵蓋 `processor_factory`、`quality_assessor`、`review_api`、`few_shot_selector`、`analyze_*` 等本規格承諾不變動的介面,可直接作為迴歸網。

**風險評估**

| 風險 | 等級 | 說明 |
|------|------|------|
| 迴歸未被偵測 | 🟢 低 | 既有測試覆蓋度足以支撐需求 6 |

---

## 4. 實施方案建議

### 需求 2 的 Provider 路線(關鍵決策點)

#### 方案 A:遷移至本地 Provider

`llm_postprocessor` 改用 `create_provider()`,以 `local_qwen`(Qwen2-VL 類)執行雙模態校正。

- **優點**:無 PII 過濾問題;符合地端優先約束;邊際成本趨近零;可取得 logprobs 作為額外信心度來源
- **缺點**:需 GPU;需先統一兩套 LLM 服務;本地模型品質需實測驗證
- **工作量**:中(Provider 遷移 + 部署配置 + 驗證)
- **風險**:🟡 中(GPU 相依為主要變數)

#### 方案 B:維持雲端 + 影像脫敏

傳圖前遮蔽統一編號等敏感欄位。

- **優點**:無需 GPU;沿用現有部署
- **缺點**:**與目的衝突**——謄本的姓名、地號正是待辨識內容,脫敏後雙模態失去意義;且仍屬個資外送
- **工作量**:中
- **風險**:🔴 高(不建議)

#### 方案 C:維持雲端 + 依賴既有拒絕降級

直接解除 `image_data=None`,靠 `_is_refusal()` 接住拒絕。

- **優點**:改動最小(一行)
- **缺點**:回到當初停用的狀態;拒絕率不可控;個資仍外送
- **工作量**:極小
- **風險**:🔴 高

**推薦:方案 A**,理由是它同時滿足需求 2、需求 3(本地 VLM 引擎)與非功能性的隱私需求,且是唯一與「地端優先」約束相容的路線。方案 C 可作為**無 GPU 環境的過渡選項**,但須明確標示為暫時狀態並限制於非個資文件。

---

### 需求 4 的共識比對層級(關鍵決策點)

#### 方案 A:文字層共識(擴展 `_fuse_results`)

- **優點**:集中於 `EngineManager`,概念單純
- **缺點**:需擴展回傳型別,衝擊既有呼叫端;文字層難以定位「哪個欄位」不一致
- **工作量**:中
- **風險**:🔴 高(相容性)

#### 方案 B:欄位層共識(於欄位抽取後比對)

各引擎結果分別抽欄位,再比對同名欄位是否一致。

- **優點**:**不改動 `_fuse_results()` 回傳型別**,相容性風險大幅降低;直接產出欄位級信心度,天然吻合 `QualityAssessor` 的 `field_confidences` 介面;`extract_text_multi_engine()` 已回傳 `valid_results`,所需資料現成
- **缺點**:需對多份文字重複執行欄位抽取,成本上升(可用需求 5 分層緩解)
- **工作量**:中
- **風險**:🟡 中

**推薦:方案 B**。關鍵理由是它與既有 `QualityAssessor.assess(ocr_confidence, field_confidences)` 介面天然吻合——需求 6 承諾不變更該介面,方案 B 讓此承諾自然成立,方案 A 則需額外轉換層。

---

### 需求 1 的標註存放(須在標註動工前定案)

#### 方案 A:移至版控目錄

標註成果統一放 `backend/tests_all/fixtures/`(已在版控)。

- **優點**:立即解決遺失風險;與既有版控副本一致
- **缺點**:標註對象(合約 PDF)仍在 `/data/`,含真實個資,不宜進版控
- **工作量**:小

#### 方案 B:匯入資料庫作為單一真相

標註以 `POST /samples/{type}/seed`(`purpose='holdout'`)寫入資料庫,JSON 僅作匯入來源。

- **優點**:與體系 B 評估直接接通;與既有回饋學習層一致;避開個資進版控
- **缺點**:需備份策略;需寫匯入腳本
- **工作量**:小~中

**推薦:方案 B 為主 + 方案 A 為輔**——標註 JSON 放版控目錄作為可追溯來源,再匯入資料庫供評估使用;合約 PDF 本身維持不進版控。

---

## 5. 技術研究需求

| 研究項目 | 目的 | 建議形式 |
|----------|------|----------|
| 視覺語言 OCR 引擎於 CPU 的推論耗時 | 判定是否牴觸 30 秒/頁需求、是否必須配置 GPU | PoC:單頁謄本實測 |
| 本地 VLM 對繁中謄本的實際準確率 | 驗證外部 benchmark 是否適用於台灣地政文件版型 | PoC:以需求 1 標註集小樣本試跑 |
| 雲端模型對謄本影像的 PII 拒絕率 | 若無 GPU,判斷方案 C 過渡選項是否可行 | PoC:少量樣本實測拒絕率 |
| 兩引擎錯誤相關性 | 驗證需求 4.6 的共識假設是否成立 | 分析:基準測試後以標註集統計 |
| 影像 token 的實際成本 | 納入 $15/月試算 | 試算:以實測 token 量推估 |
| 部署環境 GPU 可用性 | 決定方案 A 是否可行 | 確認:現行部署環境規格 |

**最高優先**:GPU 可用性確認。此為需求 2 方案 A 與需求 3 的共同前提,結果為否將連動影響兩項需求的實施路線。

---

## 6. 整合策略

### API 設計考量
- 本規格不新增對外端點;`/api/v1/analyze` 回應結構須維持向後相容(需求 6.5)
- 若需暴露共識資訊,建議以**新增選填欄位**方式擴充 `AnalyzeResponse`,不修改既有欄位語意
- `/api/v1/evaluation/{type}` 與 `/api/v1/samples/{type}/seed` 為既有端點,需求 1 可直接沿用

### 資料模型變更
- `CorrectionSample`、`EvaluationRecord` 現有結構足以支撐需求 1,**預期無需 migration**
- 需求 5 的觸發率統計若需持久化,可擴充 `ApiUsageLog`(需新增 migration)
- 共識信心度屬執行期資料,建議隨回應輸出,不新增資料表

### 向後相容性策略
1. 新融合模式以**新增列舉值**方式加入,既有 `best`/`smart`/`vote`/`weighted` 行為完全不變
2. 新引擎以**新增註冊項**方式加入,`OCR_ENGINES` 預設值不變
3. 雙模態校正以**設定開關**控制,預設維持現行行為,確認有效後再切換預設
4. 每階段完成後執行既有 57 個單元測試 + 4 個整合測試作為迴歸門檻(需求 6.7)

### 部署與配置
- 新增設定項需在 `config.py` 提供**保守預設值**(預設關閉新行為)
- 若採方案 A,`docker-compose.yml` 需新增 GPU 配置與本地模型服務,屬部署層變更,需獨立驗證
- `LLM_CLOUD_ENABLED=false` 的完整本地路徑須納入整合測試(需求 3.4、非功能性隱私需求)

---

**文件版本**: 1.0.0
**最後更新**: 2026-08-04
**分析基準**: 分支 `feat/document-type-routing` @ b1c0d5a
