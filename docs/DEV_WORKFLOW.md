# 開發流程:本機與線上的分工

> 2026-08-24 定案。本機環境與線上容器(`backend/requirements.txt` 釘版、x86_64 Linux)不同,
> 本機結果不能當驗收依據。本文記錄分工方式,避免每次重新討論。

---

## 一句話

**本機只做編輯與快速回饋;任何驗證、驗收、判定,一律在線上。**

本機環境與 `requirements.txt` 不符,結果不可採信:**本機跑出來的綠燈不算數,紅燈也不必修。**

---

## PaddleOCR 在本機

**macOS 原生 venv 可以跑,只用於探查。** 2026-11-09 在 Mac 上另建 python3.11 venv
(裝 `paddlepaddle==3.3.1`、`paddleocr==3.7.0`、onnxruntime),照 `engine_manager.py` 的參數跑 OCR
(`docs/testing/transcript-photo-fullparse-eval-20261109.md`:本機 OCR 15 張、Mac 量測)。
它與線上 x86 容器的輸出是否逐字相同未驗,所以只拿來探查(例如取行框座標),
OCR 品質與速度的驗收一律送線上。

**Docker 在 Mac 上跑不起來**(2026-08-24 實測):

| 環境 | 死在哪 | 症狀 |
|---|---|---|
| Docker `linux/arm64` | `import paddle` | `double free or corruption` |
| Docker `linux/amd64` + Rosetta | `import paddle` | `Illegal instruction` (SIGILL,Rosetta 不翻譯 AVX) |
| Docker `linux/amd64` + QEMU | `import paddle` | 卡死,10 秒 CPU 後永眠(多執行緒死結) |

- Docker Desktop 在 macOS 上只能給 Linux 容器;macOS 建置的 wheel 格式不相容。Apple 的 `container` CLI 跑的也是 Linux 容器。
- macOS 原生 Rosetta 支援 AVX2,但 **Virtualization.framework 裡的 Linux Rosetta 不 expose AVX**,兩者不可混為一談。

需要釘版環境判定的事情,一律拿線上容器判定——那個容器就是 `requirements.txt` 的實體。

---

## 本機做什麼

**只做兩件事:編輯程式碼、拿本機測試當快速回饋訊號。**
本機測試**不是驗收依據**;要判定任何一條驗收標準,去線上跑。

要判定「全數通過」,在線上容器跑(容器已釘 `fastapi==0.115.0` / `httpx==0.27.2` /
`PyMuPDF==1.24.13` / `pytest==8.3.3`):

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
  `fastapi==0.115.0` / `httpx==0.27.2` / `PyMuPDF==1.24.13` / `pytest==8.3.3`

  ```bash
  ssh -p 22 chatbot@54.248.201.66 \
    'cd ~/DocuMind && git pull && docker compose exec -T backend python -m pytest tests/unit tests/integration -q'
  ```

- OCR 品質與速度的驗收(本機 OCR 只用於探查,見上方「PaddleOCR 在本機」)
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

## git 流程

**每次 commit、push 都要業主明確授權。**

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

---

## 已知地雷

### 1. 未釘版的間接相依會讓建置變成抽獎

`requirements.txt` 只列直接相依(28 個,其中 25 個以 `==` 釘版),間接相依不釘、浮動。
2026-08-24 發現 production 容器的 `import paddle` 直接記憶體毀損
(`free(): invalid pointer`),重建 image 後就正常——**差別只在相依版本**。

同一份 `requirements.txt`,不同時間建置,得到不同環境。
**建議產出 lockfile**(`pip freeze > requirements.lock.txt`),否則會再發生。

重建時務必 `--no-cache`,否則會重用舊的 pip 層,等於白做:

```bash
docker compose build --no-cache backend
```

### 2. 資料庫與 redis 對外全開

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
