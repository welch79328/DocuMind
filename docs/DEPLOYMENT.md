# DocuMind 部署指南與建議規格

> 對象:DocuMind AI 文件智能處理系統(FastAPI + Vue3 + PostgreSQL + OCR/LLM)
> 最後更新:2026-08-24(補入 §0.5 現行部署實況)

---

## 0. TL;DR — 一分鐘結論

- **平台架構請用 x86_64**(Intel/AMD)。**勿用 ARM64/Apple Silicon 跑 PaddleOCR**——paddle 在 ARM64 有原生崩潰(見 §7)。
- **LLM 三選一**:雲端 OpenAI(最省事)/ 地端 Qwen(隱私+長期省)/ 混合。依隱私與量級選(見 §3)。
- **建議起步規格**:x86 2–4 vCPU / 8 GB RAM + PostgreSQL,LLM 走雲端 → 月成本 ~$10–15。
- **地端要 GPU**:7B 模型需 ~16 GB 顯存;2B 可 CPU(慢)。

---

## 0.5 現行部署實況(2026-08-24 定案:暫定維持)

本節記錄**實際跑著什麼**,與 §3 的建議規格分開看。§3 是選型指南,本節是現況。

### 現行組態

| 項目 | 實際值 | 出處 |
|---|---|---|
| 部署位置 | AWS 東京區(`54.248.x.x`) | — |
| 機型 | **t3.medium 級:2 vCPU / 3.7 GB 可用** | 機上 `nproc` / `free`;**機型名為推定,未經 Console 確認** |
| 月費 | **約 $33–35**(推算) | §3.1 表 t3.medium `$30`(us-east-1)× 東京 +10–15% |
| 走哪個選項 | **選項 B — 雲端 OpenAI** | `backend/app/config.py:40` `LLM_PROVIDER="openai"`,`.env` 未覆寫 |
| LLM 模型 | **`gpt-5.6-terra`**(主)/ `gpt-5.6-luna`(分類、摘要、問答) | `.env`,2026-09-03 更新 |
| OCR 引擎(`ocr_enhanced` 路徑) | **`["paddleocr"]`** 單引擎 | `.env` 的 `OCR_ENGINES`,2026-09-03 定案 |
| OCR 引擎(`document_service` 路徑) | **`pytesseract` 單獨** | 兩台 `.env` 的 `OCR_SERVICE` |
| PaddleOCR 執行器 | **ONNX Runtime**(非 paddle 執行器) | `engine_manager.py` `engine="onnxruntime"` |
| GPU | **無,也不需要** | 選項 B 明訂「無需 GPU」 |
| 容器數 | **四個**:`frontend`、`backend`、`postgres`、`nginx` | `docker compose ps` 實測 |

### ⚠️ 系統有**兩條各自獨立**的 OCR 路徑,別搞混

| 路徑 | 入口 | 分派依據 | 目前實際跑什麼 |
|---|---|---|---|
| 舊 | `/api/v1/documents` → `services/document_service.py` → `lib/ocr_service.py` | `settings.OCR_SERVICE` | **`pytesseract` 單獨**(PaddleOCR 未參與) |
| 新 | `lib/multi_type_ocr/*` → `lib/ocr_enhanced/engine_manager.py` | `settings.OCR_ENGINES` | `paddleocr` + `tesseract` 雙引擎 |

本規格(`ocr-vlm-consensus`)的共識機制只作用在**新路徑**。
談「OCR 引擎是什麼」時務必先講清楚是哪一條。

**`OCR_SERVICE` 的預設值曾是安全破口。** 2026-08-24 由 `"textract"` 改為 `"pytesseract"`:
原預設會讓**任何沒設此鍵的部署一開機就呼叫 AWS Textract**——計費,且文件內容送出到 AWS。
boto3 client 是接好的、AWS 金鑰在 `.env`,而 `.env` 不進版控,等於把「不外送」擋在
一個換台機器就會消失的檔案上。兩台機器的 `.env` 本來就都設 `pytesseract`,故實際行為不變。

**ONNX 不是第三個引擎。** 它是 PaddleOCR 內部的推論執行器,跑的是同一組
PP-OCRv6_medium 權重,實測輸出與 paddle 執行器**逐項相同**(72 行、信心度 0.927),
只是快 2.75 倍。共識比對的兩個獨立來源仍然是 PaddleOCR 與 Tesseract。

### 與 §3 選項 B 建議規格的落差

| | 選項 B 建議 | 現況 | 判定 |
|---|---|---|---|
| CPU | 2–4 vCPU | 2 vCPU | 踩在下限 |
| **RAM** | **8 GB** | **3.7 GB** | **不足一半** |
| GPU | 無需 | 無 | ✅ |

目前跑得動,原因是 PaddleOCR 改用 ONNX Runtime 後記憶體足跡小於 paddle 執行器。
**RAM 不足是潛在風險,不是已發生的故障**——尚未觀察到 OOM。

### 已量到的痛點:2 vCPU 讓兩個引擎搶不過來

2026-08-24 同機實測:

| | 秒數 |
|---|---|
| paddleocr 單獨執行 | 19.6s |
| 雙引擎循序 | 36.7s |
| 雙引擎並行(`parallel=True`) | **31.7s(僅省 13.6%)** |

理論並行值應為 `max(19.6, 17.1) ≈ 19.6s`(省 47%)。實際只省 13.6%,
**核心爭搶吃掉三分之二的理論增益**——四核以上機器增益會明顯更大。

**2026-08-24 業主定案:`parallel` 改為預設開啟**(`settings.OCR_PARALLEL_ENGINES = True`)。
13.6% 雖不漂亮,但辨識結果不變、零品質代價,且機器規格既已定案不升級,
「等四核機器再開」不再是等待理由。

⚠️ **代價是峰值記憶體**:並行時兩引擎同時常駐,峰值為兩者之和而非最大值。
該機 RAM 僅 3.7 GB(建議值的一半),**若日後換更小機器或增加第三個引擎,須重新評估。**
上述 31.7s 即在該機實測取得,未觀察到 OOM,但僅為單份文件單次執行。

### 尚未量測的三項(換機型前必須先有)

1. **實際記憶體餘量與各容器佔用** — `free -h`、`docker stats --no-stream`
2. **CPUCreditBalance** — t 系列為 burstable,基準效能僅 2 vCPU 的 20%。
   持續跑 OCR 是典型的 credit 燃燒器;credit 耗盡後的表現與「核數不夠」難以分辨,
   但解法不同(換 c 系列 vs 加核)。**此項須在 AWS Console 看,ssh 進去看不到。**
3. **是否曾發生 OOM** — `dmesg | grep -i oom`

### ⚠️ 2026-08-24 OOM 事故與三道防線

在該機以 300 DPI 渲染合約頁 + 去噪 + 雙引擎並行跑 OCR:

```
docker inspect .State.OOMKilled  →  true
load average (2 vCPU)            →  51.35
產出                              →  無,一頁都沒完成
```

服務未中斷(四個容器沒重啟,nginx 仍回 200),被殺的是外掛行程。
但**核心的 OOM killer 挑記憶體佔用大的殺**,這次是運氣;若當時 postgres
正在膨脹,被殺的就是資料庫。

根因:`docker-compose.yml` **原本完全沒設 `mem_limit`**(cgroup `memory.max`
讀出來是 `max`),四個容器共用全部 3.7GB。

已補三道防線(`b7ba31a`):

| # | 防線 | 位置 |
|---|---|---|
| 1 | 容器記憶體上限 backend 2g / postgres 512m / frontend 256m / nginx 128m | `docker-compose.yml` |
| 2 | 可用記憶體低於 `OCR_PARALLEL_MIN_AVAILABLE_MB`(預設 1024)時,並行自動退回循序 | `lib/ocr_enhanced/memory_guard.py` |
| 3 | 單頁渲染像素上限 `OCR_MAX_RENDER_PIXELS`(預設 4M);A4 由 300 DPI/8.7M 降為 203 DPI/4.0M | `services/analyze_service.py` |

⚠️ **防線 1 需重啟容器才生效,尚未套用到線上。**

### 2026-09-03 的實測與變更

**一、含文字層的 PDF 一律略過 OCR。** 同一份 4 頁電子謄本:

| 路徑 | 耗時 | 字元錯誤率 |
|---|---|---|
| **文字層** | **0.6s** | **0.15%** |
| PaddleOCR | 85s | 14.5% |
| Tesseract | 78s | 38.2% |

快 140 倍、錯誤率降到近百分之一。台灣的網路申領電子謄本一律含文字層。
該分支原本只給 `contract`,查證 commit `5b62994` 後確認是遺漏而非決策
(該 commit 把文字層列為合約 pipeline 的特性,謄本那段完全沒提),
已開放給所有類型;純掃描件自動走 OCR。

**二、引擎選擇的依據換了。** 先前以「記憶體、速度、讀出字數」判斷而選 Tesseract。
有了文字層當真值後,準確率差距(38.2% vs 14.5%)大到讓其他考量變次要,
線上已切為 `["paddleocr"]`。

**三、OCR 併發閘門上線。** `OCR_MAX_CONCURRENT=1`(行程層級 Semaphore,
放在 `EngineManager` 而非 API 層,故同一文件的多頁併發與跨使用者併發受同一上限),
第二個請求排隊而不是把容器 OOM 掉。
頁面層另以 `OCR_MAX_CONCURRENT_PAGES=4` 併發讓 LLM 的網路等待重疊
——單頁 37.8s → 19.8s。

**四、速度優化在此硬體上已窮舉。** `det 限邊 640/960` 時間不變;
`rec batch 16/32` 反而更慢(2 vCPU 沒有平行度可餵)。
28 秒是這台機器上 PP-OCRv6 的實際成本。
`text_det_limit_side_len=960` 因零時間代價且降低 CER 而保留。

⚠️ **但瓶頸不在辨識。** 文字層路徑給出 99.85% 正確的文字之後,
地號、建號、面積仍然一個都沒抽到——**欄位抽取才是真瓶頸**。

### 決策(2026-08-24,業主定案)

**暫定維持現行規格,不升級。** 其他規格選項(t3.large 8 GB / 4 vCPU 級 /
c 系列非 burstable)等**系統穩定後**再討論。

理由:RAM 不足尚未造成故障;CPU 爭搶雖已量到,但成因未定(核數 vs credit),
在三項量測完成前任何升級都可能沒對症。

### 附帶事實:$15 月成本上限已與現況脫鉤

`docs/README.md:253` 的 `$10–15/月` 是照「Vercel、Railway、Cloudflare 免費額度」
估的,主機錢靠免費額度吃掉。自架 EC2 之後該前提失效——**光機器就約 $33–35,
已是上限的 2.2 倍,尚未計入 OpenAI API 費用。**

此事屬 `ocr-vlm-consensus` 規格的任務 14.3(成本驗收)範疇,該任務已預留處理方式:
「若現行成本基線本身已超出約定上限,須回報並提出上限重訂建議,而非強行宣告達標」。
**本節不重訂上限,只記錄事實。**

---

## 1. 系統架構

```
使用者 → Nginx(前端 Vue3 靜態 + /api 反代)
             ↓
        FastAPI 後端  ── PostgreSQL(文件/OCR/AI/回饋層資料)
             ↓
   OCR 引擎(PaddleOCR / Tesseract)+ LLM Provider(OpenAI / 本地 Qwen vLLM)
```

**容器組成**(docker-compose):`frontend`、`backend`(FastAPI)、`postgres`、`nginx`。
(2026-08-24 以 `docker compose ps` 實測更正:原記三個且把 nginx 誤寫成 frontend 的一部分;`redis` 不在本 compose 內。)

---

## 2. 平台與作業系統需求

| 項目 | 需求 | 備註 |
|---|---|---|
| **CPU 架構** | **x86_64(強烈建議)** | ARM64 會使 PaddleOCR 崩潰(§7);若堅持 ARM 需用 Tesseract 或 x86 模擬 |
| OS | Linux(容器化) | Debian/Ubuntu 基底 |
| Docker | 20+ / Compose 2+ | |
| PostgreSQL | 14+ | 遷移已於 PG 14 驗證 |
| 對外網路 | apt 走 HTTPS | 部分環境 http://deb.debian.org 受限,已於 Dockerfile 改 https(§7) |

---

## 3. LLM 部署選項與建議規格 ⭐

系統的 LLM 層**可插拔**(`LLM_PROVIDER`),依「隱私 × 成本 × 量級」三選一:

### 選項 B — 雲端 OpenAI(最省事,起步推薦)
- 設定:`LLM_PROVIDER=openai`、`OPENAI_API_KEY=...`
- 成本:MVP 量下僅需雲端 VM + API(智能策略:僅低信心才呼叫)→ **~$10–15/月**
- ⚠️ 個資會外送 OpenAI(美國)。**含身分證字號的謄本/身分文件請評估合規**
- 規格:x86 **2–4 vCPU / 8 GB RAM**,**無需 GPU**

### 選項 C — 地端 Qwen(隱私,個資不外送)
- 設定:`LLM_PROVIDER=local_qwen`、`LOCAL_QWEN_ENDPOINT=http://<vllm>:8000`、`LLM_CLOUD_ENABLED=false`(硬性禁雲端)
- 模型與硬體:

| 模型 | 顯存需求 | 硬體建議 | 品質 |
|---|---|---|---|
| Qwen2-VL **2B** | ~6 GB(或 CPU) | 入門 GPU / CPU(慢) | 堪用 |
| Qwen2-VL **7B** | **~16 GB** | RTX 4060 Ti 16G / A10G / 二手 3090 | 甜蜜點 |
| Qwen2-VL 72B | 大 GPU | 不建議自架 | 最佳但過重 |

- 成本:一次性 GPU 硬體,之後僅電費;個資不出機房
- 規格:**8+ vCPU / 32 GB RAM + GPU 16–24 GB**

### 選項 D — EC2 GPU「用完即關」(低量/驗證期)
- g4dn.xlarge(T4 16 GB)~$0.53/hr、g5.xlarge(A10G 24 GB)~$1.0/hr
- **批次處理、用完就關** → 月幾美元;常開會爆預算(24h ≈ $380+)
- 資料留你 VPC(≠ 交給 OpenAI 這種第三方 API)

### 選項 E — 本機 Apple Silicon(MLX,離線評估用)
- 工具:`mlx-vlm`(Apple Silicon 首選)或 llama.cpp(需 主模型 GGUF + mmproj 投影器 GGUF)
- 量化:有 MLX 版用 MLX 4-bit,否則 GGUF Q4_K_M
- 2B 級視覺模型可舒適運行於任何 Apple Silicon Mac;7B 需 16 GB 以上統一記憶體
- **成本 $0、個資不出機器**,但只能離線批次,不能當服務
- 用途:跑標註集對照評估、驗證 VLM 值不值得投資,**不進生產程式碼路徑**

> **選型建議**:demo/低量 → B;隱私硬需求 → C(或 D 用完即關);量穩定大 → C 地端 GPU 機;**只是要評估 VLM 效益 → E**。LLM 層可插拔,先 B 起步,硬體到位再無痛切 C。

---

## 3.1 GPU vs CPU 實際差異對照 ⭐

### 價格(us-east-1、on-demand、× 730hr;東京區約再貴 10-15%)

| 機型 | 規格 | 每小時 | 每月 |
|---|---|---|---|
| t3.medium | 2 vCPU / 4 GB | $0.042 | $30 |
| t3.large | 2 vCPU / 8 GB | $0.083 | $61 |
| t3.xlarge | 4 vCPU / 16 GB | $0.166 | $121 |
| **g4dn.xlarge** | 4 vCPU / 16 GB **+ T4 16 GB** | $0.526 | **$384** |
| g5.xlarge | 4 vCPU / 16 GB + A10G 24 GB | $1.006 | $734 |

同規格(4 vCPU / 16 GB)比較:**加一張 T4 的溢價 = $263/月**。

### 效能與每頁成本(量級估算,非實測)

| 項目 | CPU(t3.xlarge) | GPU(g4dn.xlarge + T4) |
|---|---|---|
| 每小時成本 | $0.166 | $0.526(貴 ~3 倍) |
| 可舒適運行的模型 | 2B(勉強) | 7B(甜蜜點) |
| 7B 處理單頁 | 10+ 分鐘(實務不可用) | 10-30 秒(快 ~20-60 倍) |
| 2B 處理單頁 | 1-3 分鐘 | 3-8 秒 |
| 7B 每頁換算成本 | ~$0.028 | ~$0.003(便宜 ~10 倍) |

> **核心結論:GPU 每小時貴 ~3 倍,但每頁便宜 ~10 倍。**
> 差異的本質不是「CPU 慢一點」,而是「**CPU 只能跑 2B(堪用),GPU 能跑 7B(良好)**」。
> 規模效應:500 頁批次於 CPU 跑 7B 約 3.5 天;於 T4 約 2 小時。

### 隱藏成本:關機也要付的儲存費

按需執行個體在**關機期間仍產生 EBS 費用**。Qwen2-VL 7B 約 15 GB + 執行環境,以 100 GB gp3 計約 **$8/月常態支出**。

- 壓低作法:模型放 S3(15 GB ≈ $0.35/月),開機時拉取
- 代價:每次啟動多幾分鐘下載時間(批次場景可接受)
- Spot 執行個體可再省 60-70%,適合可中斷的批次,**不適合即時服務**

### 判準:什麼時候才真的需要 GPU

| VLM 的用途 | 需要 GPU | 說明 |
|---|---|---|
| 離線評估、驗證效益 | ❌ | 選項 E(本機 MLX)即可,$0 |
| 批次重跑歷史文件 | ❌ | CPU 可行,僅較慢 |
| **進入即時路徑成為產品功能** | ✅ | 此時才需常駐運算資源 |

**關鍵:上 EC2 ≠ 需要 GPU。** 決定因素是「VLM 要做什麼」,不是「有沒有上生產環境」。
若即時路徑由 CPU OCR 引擎處理(PaddleOCR + Tesseract),生產環境維持一般 x86 機型即可。

---

## 4. OCR 引擎選擇

| 引擎 | 平台 | 繁中 | 備註 |
|---|---|---|---|
| **PaddleOCR**(預設主力) | **x86_64 only(可靠)** | chinese_cht | ARM64 崩潰(§7);中文辨識最強 |
| **Tesseract**(備援) | x86 + ARM64 皆可 | chi_tra | ARM 上唯一可用;已內建於映像 |

設定:`OCR_ENGINES`(如 `["paddleocr","tesseract"]` 融合,或 ARM 上設 `["tesseract"]`)。

---

## 5. 建議規格總表(依規模)

> ⚠️ **「月成本(估)」欄不含自架 VM 的機器費。**(2026-08-24 補註)
> 首列 Demo/MVP 的 `~$10–15` 沿用 `docs/README.md:253` 的前提——
> 「Vercel、Railway、Cloudflare 都有免費額度」,主機錢靠免費額度吃掉,該金額幾乎全是 API 費。
> **自架 EC2 之後這個前提不成立**:同樣 2 vCPU / 8 GB 在 §3.1 表上是 t3.large **$61/月**。
> 本表是選型指南;**實際跑著什麼、花多少,見 §0.5。**

| 情境 | vCPU | RAM | GPU | LLM | 月成本(估) |
|---|---|---|---|---|---|
| **Demo / MVP** | 2–4 | 8 GB | — | 雲端 OpenAI | ~$10–15 |
| **即時路徑純 CPU OCR** | 2–4 | 8 GB | — | 不用 / 雲端 | 同上(無增量) |
| **地端小量(隱私)** | 4–8 | 16 GB | 2B 可 CPU | 本地 Qwen 2B | 電費 |
| **地端穩定量** | 8+ | 32 GB | **16–24 GB** | 本地 Qwen 7B | 硬體一次性 + 電費 |
| **EC2 用完即關** | g4dn/g5 | — | T4/A10G | 本地 Qwen(EC2) | $1–13(視儲存策略,見 §3.1) |
| **本機評估(MLX)** | — | 16 GB+ 統一記憶體 | Apple Silicon | 本地 2B/7B | **$0**(離線評估專用) |

- **磁碟**:後端映像 ~1.9 GB(含 paddle/torch);資料庫依文件量;上傳暫存另計。
- **PostgreSQL**:小型 2 vCPU / 4 GB 即可起步。

---

## 6. 部署步驟

```bash
# 1. 取得程式
git clone <repo> && cd DocuMind

# 2. 設定環境變數(見 §8)
cp .env.example .env && nano .env

# 3. 建置 + 啟動(x86_64 主機)
make init            # 或 docker-compose up -d --build

# 4. 資料庫遷移
make migrate         # docker-compose exec backend alembic upgrade head

# 5. 驗證
#   前端 http://localhost:3000 ｜ API 文檔 http://localhost:8003/api/docs
```

### 在 Apple Silicon(ARM)本機開發
```bash
# paddle 會崩;二選一:
# (a) 用 Tesseract:.env 設 OCR_ENGINES=["tesseract"]
# (b) x86 模擬(較慢):docker build/run 加 --platform linux/amd64
```

---

## 7. 已知問題與必要注意 ⚠️

### 7.1 PaddleOCR 在 ARM64 崩潰
- 症狀:`import paddle` → `munmap_chunk()/free(): invalid pointer` → Aborted。
- 原因:**paddlepaddle 對 ARM64/aarch64 支援有原生 bug**(上游未修,見 PaddlePaddle/Paddle #76111)。Docker 容器**繼承主機 CPU 架構**,Apple Silicon 主機 → 容器即 aarch64 → 崩潰。
- 解法:**生產部署於 x86_64**(雲主機皆為 x86,不受影響);本機開發用 Tesseract 或 `--platform linux/amd64` 模擬。
- 影響面:僅 OCR 辨識;系統採惰性載入,paddle 崩潰不影響其他功能與測試。

### 7.2 Docker 建置 apt 走 HTTPS
- 部分網路環境 `http://deb.debian.org` 被 proxy 破壞/限速(404 / connection closed);**HTTPS 直通**。
- Dockerfile 已將 apt 來源改 https(`sed http→https`)。若在正常網路建置無此問題。

### 7.3 隱私
- 含個資文件(謄本/身分證)如需「不得外送」,設 `LLM_CLOUD_ENABLED=false` 強制地端;EC2 自架 ≠ 交第三方 API。

---

## 8. 關鍵環境變數

```bash
# 資料庫
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/documind

# 儲存
STORAGE_TYPE=local            # local / s3
LOCAL_STORAGE_PATH=/app/uploads

# OCR
OCR_ENGINES=["paddleocr","tesseract"]   # ARM 上改 ["tesseract"]
OCR_PADDLEOCR_LANG=chinese_cht
OCR_QUALITY_THRESHOLD=0.8     # 信心度攔截門檻(低於→人工複核)

# LLM(可插拔:本地優先 / 雲端可選)
LLM_PROVIDER=openai           # openai / local_qwen
LLM_CLOUD_ENABLED=true        # 隱私硬需求設 false(禁雲端)
LOCAL_QWEN_ENDPOINT=          # LLM_PROVIDER=local_qwen 時填 vLLM 端點
OPENAI_API_KEY=

# fine-tune 決策門檻(僅決策,不訓練)
FINETUNE_MIN_SAMPLES=200
FINETUNE_TARGET_ACCURACY=0.9
```

---

## 9. 上線後維運要點

- **監控**:各類型 `needs_review` 比率(應隨校正累積下降)、LLM 呼叫次數/成本、單頁處理時間。
- **回饋迴路**:定期由複核人員校正低信心文件 → 系統自動累積 few-shot 樣本 → 越用越準。
- **fine-tune 時機**:某類型訓練樣本達門檻且 holdout 準確率停滯時,系統標示「可評估 fine-tune」,由人工核准(不自動訓練)。
- **備份**:PostgreSQL(含 review_queue / correction_samples / evaluation_records 回饋資料)、上傳檔案。
- **回滾**:Alembic `downgrade`(遷移已驗證可回滾);容器版本回退。
```
