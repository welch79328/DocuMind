# OCR 辨識測試頁使用指南

**功能**：上傳謄本或合約的 PDF／圖片，逐頁比對原始 OCR、規則後處理、LLM 文字校正的結果，並可當場確認欄位、回灌為校正樣本。

---

## ⚠️ 這頁只測 OCR 路徑

這頁（`/ocr-test`，後端 `POST /api/v1/ocr/test`）與正式串接的 `POST /api/v1/analyze` 走的路不同：

| | 本頁 | `/api/v1/analyze` |
|---|---|---|
| PDF | 每頁一律轉成 300 DPI 圖片再跑 OCR | 有文字層的 PDF 直接讀文字層、不經 OCR |
| 合約影像與掃描 PDF | 跑 OCR 流程（`ContractProcessor`） | 伺服器開啟直讀時整頁交視覺模型讀（線上已開啟） |
| 文件類型 | 只有 `transcript`、`contract` | 見 `docs/api/INTEGRATION.md` §2.2 |

所以拿電子謄本在這頁測出來的結果，不代表正式流程的結果。正式流程的速度與準確率見 `docs/api/INTEGRATION.md` §6。

---

## 🚀 開啟頁面

- Docker（`docker-compose up -d`）：`http://localhost:8085/ocr-test`
- 本機前端（`npm run dev`）：`http://localhost:3000/ocr-test`

或從頂部導航列點 **「🔬 OCR 測試」**。

---

## 📝 使用步驟

1. **選擇文件類型**：謄本或合約。
2. **選擇檔案**：`.pdf`、`.jpg`、`.jpeg`、`.png`。範例檔在 repo 的 `backend/data/`（`建物土地謄本-杭州南路一段.pdf`、`建物謄本.jpg`）。
3. **標準答案（Ground Truth）**：頁面上有這個欄位，但目前標準答案不會被後端使用——前端把它放在表單內容送出（`OcrTestView.vue` 的 `formData.append('ground_truth'`），後端只從網址參數讀（`ocr_test.py` 的 `ground_truth: Optional[str] = Query(`），頁面也不顯示準確率。
4. **啟用 LLM 智能修正**（預設勾選）：勾選時，OCR 信心度低於 85% 的頁面會再做 LLM 文字校正；不勾選只做規則後處理。
5. 點 **「開始測試」**，等待所有頁面處理完成。

---

## 📊 結果

- **欄位確認**：逐頁列出低信心或引擎不一致的欄位，可當場確認或修正，按「送出確認結果」寫回校正樣本（`POST /api/v1/samples/{document_type}/confirm`）。
- **合約欄位提取結果**（選合約時）：合約編號、日期、甲乙方、金額等，信心度低於 70% 會提示。
- **統計**：錯別字修正次數、格式校正次數、使用 LLM 的頁數、LLM 總成本（USD）。
- **最終辨識結果**：所有頁面合併在一個文字框，每頁用 `========== 第 X 頁 ==========` 分隔，優先顯示 LLM 校正結果，其次規則後處理、原始 OCR；可「📋 複製全文」。

---

## 🔧 技術細節

### 後端 API

`POST /api/v1/ocr/test`（不列在 API 文件中，`main.py` 以 `include_in_schema=False` 掛載）

- `file`（form）：PDF 或圖片
- 網址參數：
  - `document_type`：`transcript`（預設）或 `contract`
  - `enable_llm`：是否啟用 LLM 文字校正（預設 `true`）
  - `ground_truth`：標準答案文字，有帶時回傳 `accuracy`
  - `page_number`：只處理指定頁；不帶則處理所有頁

每頁回傳 `ocr_raw`、`rule_postprocessed`、`llm_postprocessed`；合約另有 `structured_data`。

### 處理流程

```
1. 上傳 PDF／圖片
2. PDF 每頁轉成 300 DPI 圖片
3. 每一頁交 ProcessorFactory 取得的處理器（TranscriptProcessor／ContractProcessor）：
   a. 預處理
   b. OCR：引擎清單取自 OCR_ENGINES（程式預設 ["paddleocr", "tesseract"]，線上 ["paddleocr"]）
   c. 規則後處理（錯別字、格式）
   d. LLM 文字校正（勾選且信心度 < 85% 時）：預設只送 OCR 文字；
      LLM_DUAL_MODAL_ENABLED=true 時才同時送出頁面影像
4. 合併所有頁面結果顯示
```

---

## 📂 相關檔案

- `backend/app/api/v1/ocr_test.py`：API 端點、逐頁處理、`ground_truth` 準確率計算
- `backend/app/lib/multi_type_ocr/processor_factory.py`：依文件類型取處理器
- `backend/app/lib/ocr_enhanced/postprocessor.py`：規則後處理、LLM 校正觸發門檻
- `backend/app/lib/ocr_enhanced/llm_postprocessor.py`：LLM 文字校正
- `frontend/src/views/OcrTestView.vue`：測試頁
- `frontend/src/components/FieldConfirmation.vue`、`frontend/src/composables/useFieldConfirmation.ts`：欄位確認
- `frontend/src/router/index.ts`：路由（`/ocr-test`）
- `frontend/src/App.vue`：導航列

---

## ❓ 常見問題

### 為什麼有些頁面沒使用 LLM？

只有 OCR 信心度低於 85% 的頁面才做 LLM 校正（`postprocessor.py` 的 `if confidence < 0.85:`），以節省成本。

### 出錯時看哪裡？

後端日誌（`docker-compose logs backend`）或瀏覽器 console。
