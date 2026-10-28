# DocuMind 技術棧現況

> 只寫現在實際用的東西。2026-03 的選型稿（Next.js、Railway、Cloudflare R2、AWS Textract、GPT-4o）已於 2026-10-15 刪除，要追溯請看 git 歷史。
> 線上機的組態、機型與月費見 [`docs/DEPLOYMENT.md`](../DEPLOYMENT.md) §0.5。

## 1. 總覽

| 層 | 用的是 |
|---|---|
| 前端 | Vue 3 + Vite、TypeScript、Tailwind CSS、Vue Router、Pinia（見 [`frontend/01-FRONTEND-DESIGN.md`](../frontend/01-FRONTEND-DESIGN.md)） |
| 後端 | Python + FastAPI、SQLAlchemy + Alembic、PostgreSQL |
| OCR | PaddleOCR（ONNX Runtime 執行器）+ Tesseract，本地執行；含文字層的 PDF 不經 OCR；收據、帳單、合約的影像與掃描 PDF 由視覺模型直讀、不經 OCR（線上已開啟；設定 `DIRECT_READ_DOCUMENT_TYPES`，程式預設不列，§3） |
| LLM | 謄本：OpenAI（§2）；帳單、修繕照片、點交照片、合約、收據：線上走 Bedrock 東京 Qwen3 VL 235B（flex），由分流表設定，程式預設 OpenAI |
| 檔案儲存 | 預設本機（`STORAGE_TYPE=local`）；S3 相容儲存已實作，線上設定有誤、上傳目前全數失敗（見 [`transcript-status.md`](./transcript-status.md) §5 `file_url`） |
| 部署 | AWS EC2 單機，Docker Compose 四個容器：`frontend`、`backend`、`postgres`、`nginx` |

## 2. LLM（2026-10-28 查證）

| 文件類型與用途 | 線上實際模型 | 定價 / 1M |
|---|---|---|
| 帳單、合約的欄位抽取與 OCR 校正；修繕、點交照片理解；直讀類（收據、帳單、合約的影像與掃描 PDF，設定列入時）的整頁讀圖 | Bedrock 東京 `qwen.qwen3-vl-235b-a22b`（flex；flex 遇 429、503 或逾時改標準等級重送一次） | flex $0.32 / $1.61、標準 $0.64 / $3.22 |
| 謄本欄位抽取（讀圖） | `gpt-5.6-terra` | $2.00 / $12.00 |
| 謄本全文校正 | `gpt-5.6-luna` | $0.20 / $1.20 |
| 分類、摘要、問答 | `gpt-5.6-luna` | $0.20 / $1.20 |

謄本的校正與抽取刻意分開：校正是純文字改錯字且輸出重，Terra 對 Luna 只贏 0.4 分；
抽取要讀圖並認出地號建號，Terra 領先 4 分。設定鍵為 `OPENAI_MODEL` 與 `OPENAI_MODEL_CORRECTION`（見 `app/config.py`）。

**依文件類型分流**：帳單、修繕照片、點交照片、合約的欄位抽取、照片理解與校正，
依分流表 `LLM_PROVIDER_BY_DOCUMENT_TYPE` 決定供應商，由 `.env` 設定；線上這四類與收據都設為 `bedrock`
（切換紀錄 [`docs/testing/bedrock-qwen-switch-20261028.md`](../testing/bedrock-qwen-switch-20261028.md)）。
程式預設空表 = 四類走 OpenAI（帳單抽取與照片照 `OPENAI_MODEL`，合約抽取固定 `gpt-4o`）。
謄本不在分流範圍。設定方式見 [`docs/DEPLOYMENT.md`](../DEPLOYMENT.md) §3「依文件類型分流」。

直讀類（見 §3）的呼叫也讀這張表；`receipt` 可寫進表（`{"receipt":"bedrock"}`），沒寫時走全域 `LLM_PROVIDER`。

Anthropic 與自架 `local_qwen` 兩個 Provider 已實作，線上未啟用。

## 3. OCR（2026-09-10 查證）

| 路徑 | 實際引擎 |
|---|---|
| `/api/v1/analyze`（現行） | **PaddleOCR 3.7.0**（ONNX Runtime 執行器）+ Tesseract |
| `/api/v1/documents`（已停用） | `pytesseract` 單獨 |
| AWS Textract | **未使用** |

**Textract 的預設值 2026-08-24 已被刻意改掉**：原預設會讓任何沒設
`OCR_SERVICE` 的部署一開機就呼叫 AWS Textract——計費，且文件內容送出到 AWS。
詳見 `app/config.py` 的 `OCR_SERVICE` 註解。

另有一條更關鍵的分流：**含文字層的 PDF 直接讀原始字串、完全略過 OCR**
（4 頁 0.6 秒、字元錯誤率 0.15%，對比走 OCR 的 85 秒 / 14.5%）。
台灣網路申領的電子謄本一律含文字層，所以多數請求根本不經過 OCR 引擎。

**Qwen 直讀（不跑本機 OCR）**：設定 `DIRECT_READ_DOCUMENT_TYPES`（`.env` 的 JSON 陣列，可列 `receipt`、`bill`、`contract`；**程式預設空**）
列入的類型，影像與沒有文字層的 PDF 不呼叫本機 OCR 引擎，而是整頁以長邊 2000 像素、JPEG 品質 92（單張 ≤ 3.75MB）
交視覺模型直接讀欄位，供應商依 §2 的分流表，每次呼叫記入回應的 `llm_calls`（`stage: "direct_read"`）。
動機：Qwen 本身就能讀字，不需要先跑本機 OCR；本機 OCR 每頁約 0.7 GiB、用完不還，是線上機 OOM 的來源。

- 有文字層的帳單、合約 PDF 維持文字層路徑；收據沒有舊流程，PDF 不論有沒有文字層都直讀，沒列入設定時 API 回「不支援的文件類型」。
- 直讀一律呼叫模型，不看 `enable_llm`。
- 欄位信心度由模型回「確定／不確定」加格式驗證決定（0.9／0.5／0.0），低於門檻進 `needs_confirmation` 與人工複核。
- 沒列入的帳單、合約照舊走本機 OCR 再補欄位；切回舊流程只改 `.env` 並重建容器。
- 謄本不在直讀範圍（模擬掃描評估：本機 OCR 加規則 97%，Qwen 只看圖 91%，[`docs/testing/bedrock-vlm-eval-20261023.md`](../testing/bedrock-vlm-eval-20261023.md) §3.3）。
- 欄位與回應鍵見 [`docs/api/INTEGRATION.md`](../api/INTEGRATION.md) §3.3、§3.3.1、§3.2。
