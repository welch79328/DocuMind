# 開發流程:本機與線上的分工

> 2026-08-24 定案。起因:PaddleOCR 在開發機(Apple Silicon Mac)上**完全跑不起來**,
> 但其餘所有開發與測試都正常。本文記錄分工方式與授權範圍,避免每次重新討論。

---

## 一句話

**本機只做編輯與快速回饋;任何驗證、驗收、判定,一律在線上。**

(2026-08-24 業主定案更正。本文件原寫「開發與測試在本機,只有真的要跑 PaddleOCR
才上線上」——那句話把本機測試結果當成了依據,實際上本機環境與 `requirements.txt`
不符,結果不可採信。**本機跑出來的綠燈不算數,紅燈也不必修。**)

---

## 為什麼:本機跑不了 PaddleOCR(2026-08-24 實測)

四條路徑全部實測失敗,不是推論:

| 環境 | 死在哪 | 症狀 |
|---|---|---|
| Docker `linux/arm64` | `import paddle` | `double free or corruption` |
| Docker `linux/amd64` + Rosetta | `import paddle` | `Illegal instruction` (SIGILL,Rosetta 不翻譯 AVX) |
| Docker `linux/amd64` + QEMU | `import paddle` | 卡死,10 秒 CPU 後永眠(多執行緒死結) |
| 原生 macOS venv | 推論 forward pass | 卡死 >2 分鐘(519×733 小圖) |

補充事實:

- `paddlepaddle 2.6.2` **有** macOS arm64 官方 wheel(`cp39-cp39-macosx_11_0_arm64`),裝得起來、`import` 也過,**死在推論**。
- Docker Desktop 在 macOS 上只能給 Linux 容器;能跑的 wheel 是 macOS 建置,格式不相容。Apple 的 `container` CLI 跑的也是 Linux 容器。
- macOS 原生 Rosetta 支援 AVX2,但 **Virtualization.framework 裡的 Linux Rosetta 不 expose AVX**,兩者不可混為一談。
- 本機 macOS 版本 14.2(Darwin 23C64)。

**不要再重試這四條路。** 要驗 PaddleOCR,上線上。

⚠️ **「照 `requirements.txt` 建一個釘版 venv」就是第四列,不是新方案。**
`backend/requirements.txt` 釘著 `paddlepaddle==3.3.1` / `paddleocr==3.7.0`(第 35–36 行),
在 Apple Silicon 上照它建 venv,等於重跑「原生 macOS venv」那一條。**不要建。**
需要釘版環境判定的事情,一律拿線上容器判定——那個容器就是 `requirements.txt` 的實體。

---

## 本機做什麼

**只做兩件事:編輯程式碼、拿本機測試當快速回饋訊號。**
本機測試**不是驗收依據**——環境與 `requirements.txt` 不符(詳見下表註記)。
要判定任何一條驗收標準,去線上跑。


實測(2026-08-24 重跑,取代本表先前「957 項全過」的記載——那筆與實況不符;
數字含當日新增的 6 項並行預設守衛與 3 項 OCR_SERVICE 預設守衛測試):

| 項目 | 狀態 |
|---|---|
| 後端單元測試 `tests/unit` | ⚠️ 收集 970 項:**933 passed / 1 failed / 36 errors** |
| 前端測試 36 項 | ✅ 全過(3 檔 36 項) |
| 後端整合測試 `tests/integration` | ❌ 3 個模組**收集期即失敗**,一項都沒跑到 |
| 寫程式、重構、跑測試迴圈 | ✅ 快,幾秒一輪 |

**那 37 項不是本規格造成的,也不是本機該修的:**

- 36 errors + 1 failed 全部集中在 5 個 `test_analyze_*` 模組。根因是本機實裝
  `fastapi 0.104.1` / `starlette 0.27.0` / `httpx 0.28.1`,與 `requirements.txt`
  釘的 `fastapi==0.115.0` / `httpx==0.27.2` 不符;httpx 0.28 移除了
  `Client(app=...)`,舊 starlette 的 `TestClient(app)` 因此全數 `TypeError`。
- `tests/integration` 三個模組(`test_contract_e2e`、`test_transcript_e2e`、
  `test_performance_report`)`import fitz` 失敗,本機未裝 PyMuPDF。

**兩者都不要在本機修**(修法只有建釘版 venv,見上方⚠️)。要判定「全數通過」,
在線上容器跑——`requirements.txt` 已釘 `pytest==8.3.3` 與 `PyMuPDF==1.24.13`,
容器裡這 37 項的成因都不存在:

```bash
docker compose exec -T backend python -m pytest tests/unit tests/integration -q
```

**日常開發九成在本機。** 本機是 2 vCPU EC2 的數倍快。

### 本機跑測試

```bash
cd backend && PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/unit -q
cd frontend && npx vitest run
```

⚠️ **`PYTHONDONTWRITEBYTECODE=1` 不是可選的。** macOS 系統 Python 的
`sys.pycache_prefix` 指向專案外的 `~/Library/Caches/com.apple.python`,
`find . -name __pycache__` 清不到。同長度的改動(如 `min`→`max`)在同一秒內
還原時會命中過期 bytecode,讓變異驗證給出假結果。已被坑過一次。

---

## 線上做什麼

**所有驗證與驗收。** 本節不是「本機做不到才來」的清單,而是判定的唯一場所。

- **跑測試套件做驗收判定**(任務 10.1、14.2)——容器已釘
  `fastapi==0.115.0` / `httpx==0.27.2` / `PyMuPDF==1.24.13` / `pytest==8.3.3`,
  本機那 37 項失敗的成因在容器內都不存在

  ```bash
  ssh -p 22 chatbot@54.248.201.66 \
    'cd ~/DocuMind && git pull && docker compose exec -T backend python -m pytest tests/unit tests/integration -q'
  ```

- 實際跑 PaddleOCR 辨識(本機裝不起來,**已實測驗證,見上方四條路**)
- 任務 3.3 首次正式基準
- 端到端整合測試
- 部署驗證

### 連線

```bash
ssh -p 22 chatbot@54.248.201.66
cd ~/DocuMind
```

### 那台機器的實況

| | |
|---|---|
| 規格 | 2 vCPU / 3.7GB RAM / 60GB 可用 |
| 架構 | x86_64,有 `avx avx2`(PaddleOCR 需要) |
| 系統 | Ubuntu 24.04 LTS,Docker 29.4.0 |
| 專案 | `~/DocuMind`(本專案)、`~/AIDemo`(另一個專案,勿動) |

**那台上同時跑兩個專案共 10 個容器。** 動 DocuMind 時只碰 `ai-doc-*` 四個,
`sales-*` 六個屬於 AIDemo,不要動。

### 熱重載已設定好

`docker-compose.yml` 有 `- ./backend:/app`,改 `backend/` 底下的檔案容器裡立刻生效,
**不需要重建 image**。

需要重建 image 的只有:改 `requirements.txt` 或 `Dockerfile`。

---

## git 流程(2026-08-24 起)

**業主已授權推送至 `origin`,不需每次詢問。**

```
本機:  改程式 → 跑測試 → commit → push
                                    ↓
                                 GitHub
                                    ↓
線上:  pull → 驗 OCR 相關 → (必要時 commit → push)
本機:  pull 同步回來
```

兩邊都透過 GitHub 同步,不要再用 rsync 搬檔案——那會讓遠端的 git 失真
(2026-08-24 發生過:142 個假的「未提交變更」)。

### 遠端有一處未提交的在地修改

`docker-compose.yml` 的 frontend healthcheck(6 行)。那是遠端環境需要的,
**pull 前先確認不會被蓋掉**,或把它正式提交進版控。

---

## 已知地雷

### 1. PaddleOCR 的匯入順序

```
先載 paddle,再載 pyclipper  →  SIGABRT
先載 pyclipper,再載 paddle  →  正常
```

`engine_manager.py` 載入 PaddleOCR 前必須先 `import pyclipper`。
那行看起來完全多餘(程式碼其他地方沒用到 pyclipper),**不要刪、不要移到後面**。

### 2. 未釘版的間接相依會讓建置變成抽獎

`requirements.txt` 只釘了 27 個直接相依,其餘 69 個間接相依浮動。
2026-08-24 發現 production 容器的 `import paddle` 直接記憶體毀損
(`free(): invalid pointer`),重建 image 後就正常——**差別只在相依版本**。

同一份 `requirements.txt`,不同時間建置,得到不同環境。
**建議產出 lockfile**(`pip freeze > requirements.lock.txt`),否則會再發生。

重建時務必 `--no-cache`,否則會重用舊的 pip 層,等於白做:

```bash
docker compose build --no-cache backend
```

### 3. 繁體中文模型停在 PP-OCRv3

`lang="chinese_cht"` 實際下載的是:

```
det: Multilingual_PP-OCRv3_det_infer
rec: chinese_cht_PP-OCRv3_rec_infer
```

而同套件的簡體中文拿到的是 **v4**。目前最新是 v6。
**主力語言用的是落後三代的模型。** 升級與否需先有基準數據支撐。

### 4. 資料庫與 redis 對外全開

那台上 `5433`(DocuMind pg)、`5434`(AIDemo pg)、`6379`(redis)都綁在 `0.0.0.0`。
若 security group 沒擋,從網際網路可直連。**redis 預設無密碼。**
與本專案無關,但該處理。

---

## 目前的阻擋(2026-08-24)

| 阻擋 | 卡在誰 |
|---|---|
| 任務 3.3 首次基準 | **謄本標註只有 2 筆,門檻 30 筆** — 人工作業 |
| 任務 3.2 合約標註 | **業主提供另外 19 份合約**(2026-08-24 定案:走「再找 19 份」);
現有 11 份 PDF 欄位全為 `null`,且 `BASELINE_MIN_SAMPLES=30` 在 `baseline_runner.py` 依 `doc_type` 分別計數,11 份填滿仍不足 |
| 任務 7 共識效度實證 | 依賴 3.3 |
| 任務 8.4「準確率未退步」 | 依賴 3.3 |
| Phase 2(11~14)執行與否 | 規格自訂閘門:須先看 Phase 1 基準 |

**樣本數守衛只擋「標記為正式基準」,不擋執行。** `is_baseline=False` 時
照跑照給數字,所以現在就能拿 2 筆跑出真實 CER,只是不能當正式基準線。
