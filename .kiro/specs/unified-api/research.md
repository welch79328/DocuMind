# unified-api - 技術研究日誌

## 研究摘要

### 研究範圍
分析 DocuMind 現有後端架構，評估如何將多步驟文件處理流程整合為單一 API 端點。重點研究現有 OCR 處理管線、儲存服務、問答服務的介面與整合方式。

### 關鍵發現
1. **現有 OCR 流程可直接重用**：`ocr_test.py` 的 `_process_single_page()` 已實作完整的 OCR 管線，可直接被新端點呼叫
2. **ProcessorFactory 模式完善**：工廠模式已支援 transcript/contract 兩種處理器，新端點只需呼叫 `get_processor()` 即可
3. **StorageService 已支援 S3 路徑前綴**：剛完成的 S3 改造已支援 `path_prefix` 參數，可直接按文件類型分路徑儲存
4. **問答功能需解耦**：現有 `chat_service` 強依賴 DB 中的 Document 記錄，統一端點需要支援無 DB 記錄的即時問答
5. **無需新增資料庫遷移（P0）**：P0 功能不需要持久化 Document 記錄，僅需即時處理並回傳結果

---

## 研究主題

### 主題 1: 現有 OCR 處理管線分析

**研究問題**: 現有 `ocr_test.py` 的處理流程能否直接被新端點重用？

**調查結果**:
- `_process_single_page()` 接受 `file_contents: bytes` 並回傳 `PageResult` dict，介面乾淨
- PDF 拆頁邏輯在 `test_ocr()` 中，需要提取為共用函數
- `ProcessorFactory.get_processor(document_type)` 回傳新實例，無狀態問題
- `PageResult` 包含 `original_image` (base64)，統一端點可能不需要回傳原始圖片（節省頻寬）

**設計影響**: 提取 `_process_single_page()` 為共用的 service 層函數，新舊端點共用

---

### 主題 2: S3 儲存整合

**研究問題**: 上傳的檔案如何按文件類型分路徑存放至 S3？

**調查結果**:
- `storage_service.upload_file()` 已支援 `path_prefix` 參數
- S3 路徑規則：`uploads/ocr_transcripts/{uuid}.{ext}` 和 `uploads/ocr_contracts/{uuid}.{ext}`
- CDN URL 格式：`https://d1h2hzes3rmzug.cloudfront.net/{path_prefix}/{uuid}.{ext}`
- 上傳設定 `public-read` ACL
- 設定已在 `.env` 和 `docker-compose.yml` 中完成

**設計影響**: 在 analyze 端點中先上傳至 S3 取得 CDN URL，再進行 OCR 處理

---

### 主題 3: 即時問答功能

**研究問題**: 如何在不建立 Document DB 記錄的情況下提供問答功能？

**調查結果**:
- 現有 `chat_service.chat_with_document()` 依賴 Document DB 記錄（需 document_id）
- 底層使用 `ai_service.answer_question(question, context)` 函數，接受 context dict
- `answer_question()` 可獨立使用，不依賴 DB
- context 結構：`{"ocr_text": str, "doc_type": str, "extracted_data": dict}`

**設計影響**: 統一端點直接呼叫 `answer_question()`，繞過 `chat_service`，避免不必要的 DB 操作

---

## 架構模式評估

### 模式 1: 管道模式 (Pipeline Pattern)

**描述**: 將處理流程組織為一系列順序執行的步驟

**優點**:
- 步驟間介面清晰
- 易於新增/移除處理步驟
- 與現有 ProcessorFactory 模式一致

**缺點**:
- 同步執行，無法並行處理獨立步驟

**評估結論**: ✅ 採用 — 與現有架構一致，MVP 階段足夠

---

### 模式 2: Facade 模式 (門面模式)

**描述**: 新端點作為 Facade，封裝多個子系統的呼叫

**優點**:
- 對外提供簡單介面
- 內部重用現有模組
- 不影響現有端點

**缺點**:
- Facade 本身可能變得臃腫

**評估結論**: ✅ 採用 — 統一端點本質上就是 Facade

---

## 技術決策

### 決策 1: 是否建立 Document DB 記錄

**選項**:
1. **建立 Document 記錄**: 完整持久化，可事後查詢
2. **不建立 Document 記錄**: 即時處理，僅上傳 S3 + 回傳結果

**最終決策**: 選擇選項 2（P0 階段不建立 DB 記錄）

**理由**: MVP 目標是提供即時 API 服務，使用者不需要事後查詢。S3 已保留原始檔案，未來需要時可補建 DB 記錄。用量統計用獨立的輕量表追蹤。

---

### 決策 2: 回應是否包含 original_image (base64)

**選項**:
1. **包含**: 與現有 OCR 測試端點一致
2. **不包含**: 節省回應大小（每頁約 1-3MB base64）

**最終決策**: 選擇選項 2（不包含 original_image）

**理由**: 統一 API 是給程式串接用的，不需要在回應中嵌入圖片。原始檔案已存在 S3，可透過 CDN URL 存取。

---

## 風險識別

### 風險 1: 大文件處理超時

**描述**: 多頁 PDF + LLM 校正可能超過 Nginx 預設 60 秒 timeout

**可能性**: 中

**影響**: 高（使用者收到 504 Gateway Timeout）

**緩解措施**: Nginx 設定 `proxy_read_timeout 120s`，文檔標明處理時間預期

---

### 風險 2: S3 上傳失敗不影響 OCR 結果

**描述**: S3 上傳失敗時，OCR 結果已處理完成但無法持久化原始檔案

**可能性**: 低

**影響**: 中

**緩解措施**: S3 上傳失敗時仍回傳 OCR 結果，但 `file_url` 為 null 並附帶警告

---

**研究日期**: 2026-04-08
**研究人員**: Claude AI
**文件版本**: v1.0
