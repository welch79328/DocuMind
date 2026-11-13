# 現行文件清理（2026-11-13）

業主原話（2026-11-13）：「舊線 清除 整理文件清掉過時資訊」。

## 目標正本定位

無上層目標。查過：`docs/README.md`、`docs/STRUCTURE.md`、`docs/planning/transcript-status.md`、DocuMind 記憶快照 `transcript-rights-scope`、`docs-alignment`、`bedrock-vlm-eval`。

風險觸發：無（理由：資安與信任——只改文件，不改認證、憑證、程式，不新增任何敏感資訊到公開 repo；破壞性／不可逆——刪的檔都在 git 追蹤內，可由 git 還原；資料／schema／序列化——不碰；上線——不部署、不 push（push 另問業主）；跨元件驗收——無；業主沒要求獨立審查）。

做到什麼就收：下列範圍的現行文件沒有與程式或最新紀錄相反的陳述、索引與引用同步、改動交業主看過；commit／push 另問。

## 範圍

- 根目錄與子專案說明：`README.md`、`OCR_VALIDATION_UI_GUIDE.md`、`backend/README.md`、`frontend/README.md`、`.kiro/steering/{product,tech,structure}.md`。
- `docs/`：`README.md`、`STRUCTURE.md`、`DEPLOYMENT.md`、`DEV_WORKFLOW.md`、`ANNOTATION_GUIDE.md`、`OCR_FLOW_FOR_MARKETING.md`、`tools/README.md`、`tools/build_marketing_pdf.py`（只改文字）、`planning/03-TECH-STACK.md`。
- 整檔刪除：`DOCKER_GUIDE.md`、`ENV_GUIDE.md`、`docs/frontend/01-FRONTEND-DESIGN.md`（2026-03 舊架構，盤查證據見兩份盤查報告）。

## 不在範圍

- 紀錄不改寫：`docs/testing/*`、`.kiro/specs/*`（本檔除外）、`docs/platform/*`、`docs/api/INTEGRATION.md`、`docs/planning/transcript-status.md`（後兩份 11 月仍在維護）。
- 程式不改（`Makefile`、OCR 測試頁標準答案傳不到後端、`frontend` `VITE_API_URL` 等程式問題記進 `docs/planning/followups.md`）。
- 行銷 PDF 不重產（要下載 mermaid、用瀏覽器列印），去留問業主。

## 改法規則（doc-hygiene）

- 錯了就改正文，不留附註、刪除線、「已更正／已失效」標記或過去式沿革句；量測數字保留日期與出處。
- 線上實況：OCR 單引擎 `["paddleocr"]`（DEPLOYMENT §0.5，2026-09-21 唯讀查證）；謄本補欄位 OpenAI，帳單／收據／合約／修繕／點交照片 Bedrock Qwen3 VL flex，收據／帳單／合約直讀（docs/testing 2026-10-28、10-29 報告）；compose 對外只開 nginx 8085、postgres 5433。
- repo 是公開的：不寫任何 `.env` 值、金鑰、主機帳號；不新增目前文件沒有的線上主機細節。
- 刪檔同一回合改所有引用處。
