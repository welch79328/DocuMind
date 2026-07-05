# DocuMind 部署指南與建議規格

> 對象:DocuMind AI 文件智能處理系統(FastAPI + Vue3 + PostgreSQL + OCR/LLM)
> 最後更新:2026-07-05

---

## 0. TL;DR — 一分鐘結論

- **平台架構請用 x86_64**(Intel/AMD)。**勿用 ARM64/Apple Silicon 跑 PaddleOCR**——paddle 在 ARM64 有原生崩潰(見 §7)。
- **LLM 三選一**:雲端 OpenAI(最省事)/ 地端 Qwen(隱私+長期省)/ 混合。依隱私與量級選(見 §3)。
- **建議起步規格**:x86 2–4 vCPU / 8 GB RAM + PostgreSQL,LLM 走雲端 → 月成本 ~$10–15。
- **地端要 GPU**:7B 模型需 ~16 GB 顯存;2B 可 CPU(慢)。

---

## 1. 系統架構

```
使用者 → Nginx(前端 Vue3 靜態 + /api 反代)
             ↓
        FastAPI 後端  ── PostgreSQL(文件/OCR/AI/回饋層資料)
             ↓
   OCR 引擎(PaddleOCR / Tesseract)+ LLM Provider(OpenAI / 本地 Qwen vLLM)
```

**容器組成**(docker-compose):`frontend`(Nginx)、`backend`(FastAPI)、`postgres`。

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

> **選型建議**:demo/低量 → B;隱私硬需求 → C(或 D 用完即關);量穩定大 → C 地端 GPU 機。LLM 層可插拔,先 B 起步,硬體到位再無痛切 C。

---

## 4. OCR 引擎選擇

| 引擎 | 平台 | 繁中 | 備註 |
|---|---|---|---|
| **PaddleOCR**(預設主力) | **x86_64 only(可靠)** | chinese_cht | ARM64 崩潰(§7);中文辨識最強 |
| **Tesseract**(備援) | x86 + ARM64 皆可 | chi_tra | ARM 上唯一可用;已內建於映像 |

設定:`OCR_ENGINES`(如 `["paddleocr","tesseract"]` 融合,或 ARM 上設 `["tesseract"]`)。

---

## 5. 建議規格總表(依規模)

| 情境 | vCPU | RAM | GPU | LLM | 月成本(估) |
|---|---|---|---|---|---|
| **Demo / MVP** | 2–4 | 8 GB | — | 雲端 OpenAI | ~$10–15 |
| **地端小量(隱私)** | 4–8 | 16 GB | 2B 可 CPU | 本地 Qwen 2B | 電費 |
| **地端穩定量** | 8+ | 32 GB | **16–24 GB** | 本地 Qwen 7B | 硬體一次性 + 電費 |
| **EC2 用完即關** | g4dn/g5 | — | T4/A10G | 本地 Qwen(EC2) | 幾美元(批次) |

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
