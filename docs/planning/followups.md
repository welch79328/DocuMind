# 之後再做（DocuMind 專案層清單）

工作線做到一半發現、不屬於該線範圍的事，登在這裡。謄本相關的待辦在 `transcript-status.md` §5，各規格線自己的清單在 `.kiro/specs/<線>/followups.md`；這裡放不屬於任何一條現行線的項目。

每項寫：發現的地方（可 grep 的符號）、影響、狀態（待查＝還沒重現；待決＝要業主決定；可做＝事實已清楚、等排入）。

## 程式

| ID | 問題 | 依據 | 影響 | 狀態 |
|---|---|---|---|---|
| P1 | `make init` 複製不存在的範本 | `Makefile` `init:` 下 `cp .env.docker.example .env`；repo 只有 `.env.example` | 新環境照 `make init` 會失敗；`make up` 印出的 8000／5432 也與 compose 對外的 8085／5433 不符 | 可做 |
| P2 | OCR 測試頁的標準答案傳不到後端 | 前端 `OcrTestView.vue` `formData.append('ground_truth', …)` 放在表單；後端 `ocr_test.py` `ground_truth: Optional[str] = Query(` 從網址參數讀 | 測試頁填了標準答案也不會算準確率 | 可做 |
| P3 | `VITE_API_URL` 同時當開發代理目標與 axios `baseURL` | `frontend/src/services/api.ts` `API_BASE_URL = import.meta.env.VITE_API_URL \|\| '/api'`；`vite.config.ts` proxy `target: process.env.VITE_API_URL`；`docker-compose.yml` `VITE_API_URL: ${VITE_API_URL:-http://backend:8000}` | 設成 `http://主機:8000` 時 `baseURL` 少了 `/api`，`/v1/review/queue` 會 404；不設時走 `/api` 正常 | 待查（未實際重現） |
| P4 | 前端 OCR 測試頁金額顯示 NaN | `OcrTestView.vue` `Number(page.structured_data.financial_terms.contract_amount)`；值是字串（規格 2.8.0），帶千分位時如 `Number("25,000")` 得 NaN | 帶逗號的金額顯示 NaN | 可做 |
| P5 | OpenAPI 版本號沒跟對接規格走 | `backend/app/main.py` `version="1.0.0"`；`docs/api/INTEGRATION.md` 已是 2.12.x | `/api/docs` 顯示的版本與規格不符 | 可做 |
| P6 | API 用量紀錄沒記到 Bedrock 費用 | `.kiro/specs/handover-v2-accuracy/followups.md` F5 | 無法從 `api_usage_logs.llm_cost` 算點交、帳單等走 Bedrock 的成本 | 待查 |

## 規格文字

| ID | 問題 | 依據 | 狀態 |
|---|---|---|---|
| S1 | `INTEGRATION.md` §3 總則寫欄位值「不是字串就是 null」，比實作絕對：模型回布林、物件、陣列時原樣保留 | 2026-10-29 Bedrock 讀圖模型線 verifier 延後 P4 | 可做 |

## 模型行為觀察（沒有量過，不是已確認的錯）

| ID | 觀察 | 出處 | 狀態 |
|---|---|---|---|
| M1 | 修繕照片 `damaged_items` 會漏牆面類損傷 | 2026-10-29 Bedrock 讀圖模型線實測 | 待查（要有牆面損傷照片的真值集） |
| M2 | `/classify` 把水費單判成收據 | 同上 | 待查 |
| M3 | 合約直讀時容器記憶體逐次上升 | 同上 | 待查（要在同一台機器連送多份量記憶體） |
| M4 | AIChatbot 合成收據 3 張（含提示詞注入）補測 | 同上；收據要由 AIChatbot 那邊提供 | 待決（等對方給樣本） |

## 其他

| ID | 事項 | 狀態 |
|---|---|---|
| D1 | 對外版串接文件（由 `INTEGRATION.md` 衍生、拿掉內部資訊）；2026-10-15 產過一版，產生腳本已不在 | 不處理（業主 2026-11-13 照建議：等 JGB 以外有對象要時再產） |
| D2 | 謄本工作線未登在 `transcript-status.md` 的三項：G2「值型別決定可否跨行」推廣到面積、日期、門牌；外框 PDF 跳過 OCR 只看字數（`pdf_text_layer` `_MIN_TEXT_CHARS = 20`）；`normalize_pattern` 遇「\（」或「[㎡]」這類樣式會變義（現行樣式沒有） | 可做（排入謄本線時一起看） |
