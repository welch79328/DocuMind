# DocuMind 帳單／照片／合約改走 Bedrock Qwen3 VL（flex）— 計畫

> 狀態：**已核可、凍結**（業主 2026-10-28「核可，開始 S1」，第 5 版；最後 1 項 wording-only 已修、未再審）。規則 R1–R7 與凍結驗收清單在同目錄 `acceptance.md`，判定以該檔為準。
> 安全審查：2026-10-28 security-reviewer（唯讀）完成，發現 F1–F11 與建議 SR-1～SR-11 已併入 §5；處置見 §10。

## 0. 業主原話與已告知的取捨

業主原話（2026-10-28）：
1. 「統一換成 Qwen3 VL 235B  flex」，附貼上的帳單、修繕照片、點交照片、合約四列。
2. 範圍：「不含謄本」。
3. 校正段：「一起換成 Qwen」。
4. 金鑰：「共用 AI 客服那把」。
5. 部署：「授權你來部署」。
6. 帳單（得知補欄位 prompt 的實測後）：「維持換，驗收照實報」。
7. flex 失敗：「改標準等級重送一次」。
8. `question` 問答：「不在這次範圍」。
9. 品質門檻：「只報不擋，差太多停下」。
10. R6 算法：「3 次平均」。
11. 合約觸發不足 5 份：「接受不足，照實報」。
12. 送 Bedrock 的圖要不要另外縮到長邊 2000：「先不做，沿用現在的圖」。

已當面告知業主、業主仍維持決定的取捨：
- 謄本沒有換 Qwen；AI 客服的定案（AIChatbot DSP-111）不涵蓋 DocuMind。
- 修繕照片實測 terra 10/10、Qwen 8/10（9 張非壁癌照片 Qwen 標 7 張壁癌、terra 4 張）（評估 §3.5）。
- 帳單用的是補欄位 prompt `_extract_with_llm`（與謄本補欄位同一支）。同一 prompt 讀謄本，terra 錯值 3、Qwen 9（評估 §3.2）；Qwen 的錯幾乎都是把別部的值填進來，帳單只有一部，不一定重現，但帳單本身沒測過。先前「帳單可以換」引用的 §3.4 92.6% 是評估自寫的 5 欄 prompt，不適用 DocuMind，已向業主更正。
- 業主沒有說明換的理由（成本或開源方向），本計畫不替業主補理由。

## 1. 目標、目標形態、差距、路徑

**目標**：DocuMind 的帳單、修繕照片、點交照片、合約，辨識流程中所有 LLM 呼叫改由 Bedrock 東京 Qwen3 VL 235B 以 flex 處理；謄本不動；品質照實報，任一類掉超過 20 個百分點就切回（R1–R7）。

**目標形態**（不看現況）：
- **依任務選模型**：每類文件明確指定供應商與模型，不靠一個全域開關。第一原理推導（同一服務內不同任務對準確度要求不同；評估也顯示同一模型在不同用法差很大），**查無業界對應**。
- **flex 的定位**，AWS 原文（`raw/aws-bedrock-service-tiers.txt`）：
  - 第 87 行：「For workloads that can handle longer processing times, the Flex tier offers cost-effective processing for a pricing discount.」
  - 第 83 行：「The Standard tier provides consistent performance for everyday AI tasks such as content generation, text analysis, and routine document processing. … You can also set the "service_tier" optional parameter to "default" for your inference request to be served with Standard tier.」
  - 第 95 行：「Your on-demand quota for a model is shared across the "priority", "default", and "flex" service tiers. … The service tier configuration for a served request is visible in API response」
- **重試**，AWS SDK 原文（`raw/aws-sdk-retry-behavior.txt`）：第 64 行「When a request to an AWS service fails due to a transient error or throttling, the SDK can automatically retry the request.」第 86 行「Standard mode retries failed requests using exponential backoff with jitter.」第 130 行 max attempts 預設 3。
- **失敗要看得見、不跨供應商偷偷改送**：第一原理（資料接收方要可預期、「沒用到」與「失敗」要分得出），**查無業界對應**；來源是安全審查 SR-3、SR-8。

**差距**（此時才看現況，依安全審查與主持人、審查員抽查）：
- 帳單抽取、修繕、點交都呼叫不帶名稱的 `create_provider()`，吃全域 `LLM_PROVIDER`；帳單和謄本共用 `field_extraction_base.py:_default_provider`（F1）。
- 帳單、合約的校正段寫死 `llm_provider = "openai"`（`bill_processor.py`、`contract_processor.py`）；合約抽取寫死 `LLMService(provider="openai", model="gpt-4o")`（`contract_field_extractor.py`）（F2）。
- 沒有 Bedrock 供應商；雲端守衛名單只有 openai、anthropic（F4）。
- 抽取失敗會靜默退回規則結果且仍標 `llm_used_for_extraction=True`（F6）。
- `AsyncOpenAI` 沒設 timeout、重試（F9）；成本表沒有 Qwen（F11）。
- 送進 LLM 的影像解析度，兩條路不同：
  - **上傳影像**：進 OCR 前縮到 `OCR_MAX_IMAGE_PIXELS=1_000_000`（`processor.py` 縮圖），LLM 收到的是這份縮圖。
  - **PDF**（合約、部分帳單）：fitz 依 `OCR_MAX_RENDER_PIXELS=1_000_000` 渲染（`analyze_service.py:_render_scale`），沒有點陣原檔。
  - 兩者都約 100 萬像素（A4 約 102 DPI、長邊約 1155）。評估顯示 Qwen 讀收據在長邊 1500 多錯 1 欄、1000 再多錯 3 欄，長邊 2000 與原圖相同（評估 §3.6）。
- 帳單和合約只在規則抽不到或信心度低時才呼叫 LLM（`field_extraction_base.py` 的 `if use_llm_fallback and needs and image_data`；`contract_field_extractor.py` 的信心門檻），校正也有條件才觸發。

**路徑**：§4 的兩片。偏離目標形態的取捨：
- 共用 AIChatbot 金鑰（業主裁定，R4），偏離「每系統專用最小權限身分」，代價見 D-4。
- flex 失敗只重送一次、而且改用 `default`，不是 SDK 式同請求三次指數退避：
  - 業主裁定（R2）。
  - 少重試：線上是單 worker、nginx 讀取逾時 600 秒，連續退避會把請求拖過上限。
  - 換等級：flex 的定位是「能接受較長處理時間」，被限流或逾時時同等級再送很可能再被拒；AWS 把標準等級定位為「consistent performance … routine document processing」。換等級是第一原理推導，**查無業界對應**。

## 2. 非目標（附理由）

- 謄本的抽取與校正（R3）。
- `/api/v1/analyze` 的 `question` 問答、`/chat`、`/documents`：業主裁定不在這次範圍。這三條直接用 OpenAI 且不看雲端開關（F3，既有問題），建議另開修補片。jgb2 staging 的兩個呼叫端都沒送 `question`（`HandoverPhotoAnalyzeService.php` 只送 `document_type`，同一查法命中該欄位當正對照）。
- 換 AIChatbot 本身的程式（DSP-111 由 AIChatbot 線處理）。
- 專用 IAM 身分（業主選共用）。
- 調整 OCR 本身的點陣上限（記憶體閘門，見 config 註解）。
- 另做長邊 2000 的影像送 Bedrock：業主裁定「先不做，沿用現在的圖」，要做另開一片（R7）。

## 3. 決策

| ID | 決策 | 理由 |
|---|---|---|
| D-1 | 送 Bedrock 的影像與現在送 OpenAI 的完全相同（上傳影像依 `OCR_MAX_IMAGE_PIXELS`、PDF 依 `OCR_MAX_RENDER_PIXELS`，約 100 萬像素），不另做高解析度複本；只有在該影像超過 Bedrock 單張 3.75MB 上限時，才為 Bedrock 請求另以同尺寸 JPEG 品質 92 重新編碼。OCR 輸入與記憶體行為不變 | 業主裁定「先不做，沿用現在的圖」。代價：評估顯示 Qwen 讀收據小字在長邊 1500 多錯 1 欄、1000 再多錯 3 欄（評估 §3.6），現行約長邊 1155，準確度可能低於評估值；由 A1–A4 改前改後實測呈現，掉太多由 R6 切回；要做長邊 2000 另開一片（需另外設計不影響 OCR 輸入與記憶體量測的做法，見 §10 第 4 版審查） |
| D-2 | 分流用一張「文件類型 → 供應商」表，預設全部 openai；線上 `.env` 設四類為 bedrock 才生效 | 程式先上線不改路由（SR-10）；回滾或 R6 切回單一類只改 `.env` 重建容器 |
| D-3 | 每次呼叫先送 `service_tier: "flex"`；遇 429、503、逾時，同模型同區改 `"default"` 重送一次；仍失敗走既有降級（規則結果或低信心進複核），不改送 OpenAI | R2 業主裁定；SR-3 |
| D-4 | 共用 AIChatbot 金鑰 | 業主裁定。代價：線上機外洩會連帶 AI 客服可用的 6 個模型；換金鑰兩邊一起斷；AWS 帳單與 CloudTrail 分不出系統；配額本來就共用（專用身分也解決不了） |
| D-5 | 品質只報不擋；任一類正確率比切換前低超過 20 個百分點，先把那一類切回 openai 並回報 | R6 業主裁定。修繕照片依評估預期約 −20 個百分點（10/10 → 8/10），落在門檻邊上，照實量 |
| D-6 | 回應每頁新增 `llm_calls`（階段、供應商、模型、實際 service_tier、成功或錯誤類別），錯誤只放類別、不放 AWS 原始訊息；抽取失敗時 `llm_used_for_extraction=False` | SR-8、F6、F7：讓「沒用到」與「失敗」分得出來，且不外露 IAM ARN |

## 4. 切片

### 程式封套
- 範圍：DocuMind `backend/app` 的 LLM 供應商層、四類處理器、設定、測試、文件；線上機部署。
- 擁有者：主 session 統籌；S1 由 `security-executor` 實作（涉及憑證載入與雲端守衛）；S2 部署與線上實測由主 session 執行（R5）；點交照片與帳單樣本由不看程式的代理挑選；A3、A4 由 `blind-judge` 判；結果由新開 `verifier` 驗。
- 停點：P0；線上實測打掛服務；業主喊停。

### S1｜本機實作（不碰線上）
- **成果**：Bedrock 供應商與分流完成。路由與模型預設不變（全部 openai）；回應的變動只有兩項：每頁多 `llm_calls`、抽取失敗時 `llm_used_for_extraction` 改為 `False`。A7、A9 全過。
- **範圍**：
  1. `providers.py` 新增 Bedrock 供應商：OpenAI 相容端點 `https://bedrock-runtime.ap-northeast-1.amazonaws.com/openai/v1`，bearer 金鑰只從 settings 讀；列入 `CLOUD_PROVIDERS`，建構子內也檢查 `LLM_CLOUD_ENABLED`；model ID 帶 `jp.`／`global.` 前綴即報錯（SR-2、SR-7）。→ A7 ③④
  2. D-3 的 flex 與單次 `default` 重送；明確 timeout（≤120 秒）與重試上限（SR-9）。→ A7 ⑤
  3. D-1：Bedrock 請求沿用現行影像，僅超過 3.75MB 時另以同尺寸 JPEG 重新編碼。→ A7 ⑥⑦
  4. D-2 分流表，未知名稱報錯；四類的抽取與校正依表取供應商；合約抽取改走 `create_provider`；謄本維持 openai（SR-1）。→ A7 ①②
  5. D-6 `llm_calls` 與 `llm_used_for_extraction` 修正（SR-8）。`llm_calls` 加進回應 schema `OcrPageResult`（`schemas/analyze.py`，該模型 `extra: "ignore"`，不加欄位會被丟掉）為選填欄位。→ A7 ⑧⑨
  6. `_PRICING` 補 Qwen flex／default 單價（F11）。→ A7 ⑩
  7. 文件：DEPLOYMENT、03-TECH-STACK 寫明「依文件類型分流表、預設 openai、由 `.env` 決定」（各類實際去向在 S2 依最終路由改）；INTEGRATION 補 `llm_calls`；`.env.example` 只放佔位鍵名（SR-11）。→ A9
- **非目標**：§2。
- **前置**：無。
- **驗收**：A7、A9；本機 `pytest` 全部（含既有）通過。
- **回滾**：不 commit 即可丟棄；commit 後 `git revert`。
- **用量報告**：子代理 token 合計＋API 費用（單元測試不打外部，預期 0）。
- **停點**：A7 或既有測試失敗、修復達 5 輪仍不過；verifier REFUTED 修復後再驗仍 REFUTED；verifier INCONCLUSIVE 補齊所缺證據重試一次仍 INCONCLUSIVE。任一發生即停下回報。

### S2｜線上切換與實測
- **成果**：線上四類走 Bedrock Qwen（flex，必要時 `default`），A1–A6、A8 有證據；觸發 R6 的類別已切回並回報。
- **前置**：S1 verifier CONFIRMED；A1、A3 樣本已由不看程式的代理挑選並凍結；業主看過 S2 的部署指令清單（R5 收窄）。
- **步驟**（SR-10、SR-6）：
  0. 送任何真實合約前，先送一張公開樣本確認回應的 `file_url` 是 `null`（線上上傳若被修好，程式會以 `public-read` 上傳原檔）；不是 `null` 就停下回報。
  1. 切換前基準：照 `acceptance.md` 廣度表，在現行線上（terra）跑 A1–A4 改前；謄本跑 A6(a) 基準。每輪線上實測會在複核佇列新增項目，跑完記下 ID。合約只送 3 頁以內、一次一份；每份送出前確認容器在跑且 `OOMKilled=false`（`docker inspect --format '{{.State.OOMKilled}}' ai-doc-backend`，只取這一欄，不印環境變數）。記憶體持平在約 1.8 GiB 是已知常態（工作線記憶 production-host），不等待回落。
  2. 主機 `git status`、記下目前 SHA。
  3. `git pull`（路由不變）。
  4. 金鑰：從本機授權路徑以 `scp` 傳到主機 repo 外的暫存檔（權限 600），在主機上寫進 `.env`，指令不帶金鑰值、不 `cat`，寫完刪暫存檔；同時寫入分流設定。只用鍵名確認有值，不跑 `docker compose config`／`docker inspect`。
  5. 用會重讀 `env_file` 的方式重建 backend 容器（`docker compose up -d --force-recreate backend`）。
  6. 改後實測：A1–A6、A8；verifier 另跑 10 個新輸入。
  7. 依最終路由（含 R6 切回的類別）改 DEPLOYMENT §0.5／§3、03-TECH-STACK §2 的各類去向（A10）。
- **執行估算**（只是估算，不是上限或停點）：

  | 執行 | 案例數 × 每案時間（出處） | 呼叫次數／費用（出處） |
  |---|---|---|
  | A1 帳單 改前 1＋改後 3 | ≥8 張 × 4 次 × 約 20 秒（OCR 每頁 15–24 秒，`docs/testing/transcript-online-acceptance.md` §3.2）≈ 11 分 | Bedrock ≤24 次，約 $0.001／張（評估 §3.8 單據每張費用）≈ $0.03；terra ≤8 次 ≈ $0.05（單價 $2／$12 每百萬 token，`docs/planning/03-TECH-STACK.md` §2） |
  | A2 修繕照片 改前 1＋改後 3 | ≥16 張 × 4 次 × 約 3–5 秒（評估 §3.7：中位數 2.5 秒、最慢 5.3 秒）≈ 5 分 | Bedrock 48 次 × 約 $0.00095（評估 §3.8 縮到 2000＋flex）≈ $0.05；terra 16 次 ≈ $0.16 |
  | A3 點交照片 改前 1＋改後 3 | ≥10 張 × 4 次 × 約 3–5 秒（同上）≈ 3 分 | Bedrock 30 次 ≈ $0.03；terra 10 次 ≈ $0.10 |
  | A4 合約 改前 1＋改後 1 | 5 份（2、2、3、3、3 頁）× 2 次 × 61–72 秒（2026-10-13 線上 2–5 頁合約實測，工作線記憶 production-host）≈ 12 分 | Bedrock ≤13 次（5 份共 13 頁，抽取另計 ≤5 次）≈ $0.03；terra 同量級 |
  | A6 謄本 (a) 改前＋改後 (b) 1 份 | 8 份 × 2 次，圖片頁約 15–24 秒、PDF 不到 1 秒 ≈ 6 分 | (a) `enable_llm=false` 無 LLM；(b) terra 1 次 ≈ $0.01 |
  | verifier 新輸入 | ≥10 個 × 約 1 分 ≈ 10 分 | < $0.10 |

  合計約 50 分鐘、不到 1 美元。每次執行會在線上複核佇列新增項目。
- **回滾**：`.env` 分流改回 openai（單一類或全部）後重建容器；程式回滾 `git checkout <記下的 SHA>`。
- **用量報告**：子代理 token＋Bedrock 費用＋改前基準的 OpenAI 費用，以實際用量回報。
- **停點**：
  - 線上任一請求連續 2 次回 5xx，或容器 OOM → 立即全部回滾並回報。
  - 任一類觸發 R6（掉超過 20 個百分點）→ 那一類切回 openai，其他類照常，回報業主。
  - 改後實測有一半以上的呼叫走 `default` → 停下回報業主（「flex 可接受」的前提可能不成立）。

## 5. 安全要求（來自安全審查）

SR-1 分流不改全域；SR-2 雲端守衛涵蓋 Bedrock（含建構子）；SR-3 不跨供應商備援；SR-4 範圍一致（校正段納入、`question` 等列非目標，皆業主裁定）；SR-5 憑證取捨寫明（D-4）；SR-6 金鑰存放與操作（S2 步驟 4）；SR-7 地區鎖定；SR-8 失敗可見、錯誤不帶 ARN（D-6）；SR-9 逾時與重試上限；SR-10 部署順序（S2）；SR-11 文件同回合改正。

## 6. 終點表

| 項目 | 角色 | 現值（版本、出處） | S1 預期變化 | S2 預期變化 | 前兩片 |
|---|---|---|---|---|---|
| 四類 LLM 呼叫符合 R1、R2 的比例 | **完成指標**（A1–A5 的通過條件） | 0%（DocuMind HEAD `ee72216`，程式路由：四類全走 OpenAI） | 0（S1 不改路由，是 S2 這一列的前置） | 0% → 100%（未被 R6 切回的類別） | 本目標無前片 |
| A1 帳單正確率 | 只報（R6），不作完成指標 | 現值未量：改用水電、管理費帳單樣本，S2 步驟 1 切換前量 | 0 | 未知；同一 prompt 讀謄本 Qwen 錯值較多（評估 §3.2） | 本目標無前片 |
| A2 修繕照片命中率 | 只報（R6），不作完成指標 | 參考：terra 10/10（評估 §3.5，線上 2026-10-20～23，SHA 未記）；正式現值於 S2 步驟 1 量 | 0 | 約 −20 個百分點（評估 Qwen 8/10）；業主已知並接受（§0） | 本目標無前片 |
| A3 點交照片正確率 | 只報（R6），不作完成指標 | 現值未量：沒有樣本，S2 步驟 1 量 | 0 | 未知（未測過） | 本目標無前片 |
| A4 合約正確率 | 只報（R6），不作完成指標 | 現值未量：沒有標準答案，S2 步驟 1 盲判 | 0 | 未知（未測過） | 本目標無前片 |

## 7. 驗證

S1 完成：新開 `verifier`，依 `acceptance.md` A7、A9 與 diff 驗。S2 完成：新開 `verifier`，依 A1–A6、A8、A10 驗，並另寫至少 10 個新輸入實跑。兩次都附業主原話、本檔與 `acceptance.md` 路徑。

## 8. 已查與待查

- 已查（2026-10-24 實測，AIChatbot DSP-111「呼叫須知」）：這把金鑰能打 OpenAI 相容端點；Qwen3 VL 收 `image_url` data URL；帶 `"service_tier": "flex"` 時回應標 `flex`；無效值回 400；輸入 token 與 Converse 相同。
- 待查（S2 執行時取證，不影響 S1）：AWS 拒絕存取的錯誤訊息是否帶 ARN（D-6 已改成只放類別）；8085 是否對外開放（影響 D-4 外洩面的大小；查主機 security group 需要 AWS Console，列給業主）。

## 9. 卡點

- 點交照片與帳單樣本：S2 前由不看程式的代理挑選並凍結（廣度表 A1、A3）。帳單若找不到 3 組公開樣張，照實報可用組數。

## 10. 處置紀錄

### 安全審查（2026-10-28）

| 發現 | 優先 | 處置 |
|---|---|---|
| F1 分流不能改全域 | P2 | FIX：S1 範圍 4、SR-1 |
| F2 校正段與合約抽取寫死 OpenAI | P2 | FIX：業主裁定校正一起換，S1 範圍 4 |
| F3 `question`／chat／documents 繞過守衛 | P2（既有） | DEFER：業主裁定不在範圍，建議另開修補片 |
| F4 新供應商須列雲端 | P2 | FIX：S1 範圍 1 |
| F5 共用金鑰 | P2 | 業主裁定共用，取捨寫入 D-4 |
| F6 失敗靜默降級 | P2 | FIX：D-6、S1 範圍 5 |
| F7 錯誤字串可能帶 ARN | P3 | FIX：D-6 只放類別 |
| F8 合約 LLM 輸出寫進 ERROR log | P3（既有） | DEFER：換模型不改機制；回報 |
| F9 逾時重試無上限 | P3 | FIX：S1 範圍 2 |
| F10 部署順序 | P2 | FIX：D-2、S2 步驟 |
| F11 成本低估 | P4 | FIX：S1 範圍 6 |
| 待查 1 flex 在相容端點是否生效 | — | 已查（§8） |

### 第一次 plan-verifier（2026-10-28，REVISE，12 項）

| 項目 | 處置 |
|---|---|
| R2 與 default 重送矛盾、讀法未裁 | 問業主 → 「改標準等級重送一次」；R2、D-3 改成同一套條件 |
| `question` 排除未裁 | 問業主 → 「不在這次範圍」；記入 R1 註記與 §2 |
| R5 收窄未標明 | R5 註記標「保守收窄」並附理由 |
| A1–A4「不比切換前差」無規則支持 | 問業主 → 「只報不擋，差太多停下」；新增 R6，A1–A4 通過條件改寫，判分寫明 |
| A1 欄位與資料組不符 | 判分改用 `amount`、`date`、`account_no`；收據不算帳單，改收水電、管理費樣本 |
| 未要求實際觸發 LLM | 清單與廣度表規定只計觸發 LLM 的輸入，A1、A4 下限 5 |
| PDF 路徑寫錯 | 差距分開影像與 PDF；D-1 補 PDF 重新渲染與記憶體依據 |
| S1 驗收證明不了成果 | A7 補 ①–⑪；S1 成果改寫成精確變動 |
| S1 無停點 | S1 補停點 |
| 終點表缺 | 新增 §6 |
| 帳單取捨未告知 | 已向業主更正並取得裁示（§0 第 6 點） |
| 第一原理標示與 D-3 理由 | §1 補「查無業界對應」與換等級理由 |

### 第二次 plan-verifier（2026-10-28，REVISE，7 項）— 停止自動重送，逐項處置

| 項目 | 優先 | 處置 |
|---|---|---|
| `llm_calls` 會被回應 schema 丟掉 | P2 | FIX：S1 範圍 5 加進 `OcrPageResult`；A7 ⑧ 改用 TestClient 讀序列化後的回應（主持人抽查 `schemas/analyze.py` 確認 `extra: "ignore"`） |
| S1 文件去向與程式預設相反 | P2 | FIX：A9 改為描述分流機制；各類去向移到 S2（A10，步驟 7） |
| D-1 記憶體依據不符程式 | P2 | FIX：影像改為同一次解碼取複本；PDF 重新渲染放進 `_get_ocr_gate()`；新增 A11 實測門檻 |
| R6 多次結果合成方式未定 | P2 | 問業主 →「3 次平均」，寫入 R6 與判分 |
| 終點表不完整 | P2 | FIX：新增完成指標列（呼叫符合比例、記憶體），品質列標「只報」 |
| 照片資料組只有 1 組、合約不足 5 份 | P2 | FIX：A2、A3 改 3 個公開授權來源；合約不足問業主 →「接受不足，照實報」 |
| R1 區域、R2 的 503 未標讀法 | P2（wording-only） | FIX：R1、R2 讀法註記補上 |
| （參考）線上 `STORAGE_TYPE` 若為 S3 會公開上傳真實合約 | — | FIX：S2 步驟 0 先確認 `file_url` 為 `null` |

### 收尾 plan-verifier（2026-10-28，REVISE，3 項：2 項 substantive、1 項 wording-only）— 依規則暫停交業主

| 項目 | 優先 | 處置（已改進本檔，未再審） |
|---|---|---|
| A11 現值未量沒有條件 | P2 substantive | 改寫 A11 列：量的是切換前後增量，S1 依定義為 0 |
| D-1 會讓 ≥16MP 照片失去 draft 縮小解碼 | P2 substantive | D-1 改為只在 bedrock 路由時取複本、以 draft 取 ≥2000 的縮小解碼；A11 與 A7 ⑦ 加 ≥24MP 輸入 |
| S2 缺執行估算 | P2 wording-only | S2 補執行估算表 |

### 第 4 版審查（業主指示再審，2026-10-28，REVISE，2 項 substantive）— 依業主指示停下詢問

| 項目 | 優先 | 處置 |
|---|---|---|
| D-1 的 draft 尺度規則前後矛盾，bedrock 路由下 OCR 輸入會變 | P2 | 問業主 →「先不做，沿用現在的圖」：D-1 改為沿用現行影像，OCR 輸入不變；長邊 2000 另開一片 |
| A11 起始狀態不同、貼近上限，量不出結果；步驟 1 等待回落做不到 | P2 | A11 隨 D-1 收窄刪除（影像與記憶體行為不變）；步驟 1 改為合約只送 3 頁以內、每份前確認 `OOMKilled=false`，不等待回落 |

### 第 5 版審查（2026-10-28，REVISE，1 項，審查員標 wording-only）

| 項目 | 優先 | 處置 |
|---|---|---|
| 業主第 13 句沒有對應規則或非目標；3.75MB 重新編碼是未標的放寬 | P2 wording-only | 已修，未再審：新增 R7（含放寬註記）、A7 掛 R7、§2 補非目標 |

