# 謄本帶參數格式 `transcript_format=v2`：正式機部署與線上確認（2026-11-11）

本紀錄補 `docs/testing/transcript-v2-20261109.md` §7 列為沒驗的「線上」一項（凍結清單 `acceptance.md` C14）。部署計畫：`.kiro/specs/transcript-records-converge/plan-deploy.md`。量測檔目錄 `~/jgb-archive/transcript-photo-fullparse-eval-20261109/`（下稱 `E/`）。所有請求 `enable_llm=false`。

## 部署

- 線上機 `54.248.201.66` 的 `~/DocuMind`：`dd4a42e` → `84b890e`（`git pull --ff-only`，快轉）。`dd4a42e` 與先前記為線上版本的 `ab38a55` 只差 2 個文件檔，程式相同。
- 部署前（2026-11-11 08:17）：health 200、`OOMKilled=false`、`RestartCount=0`、記憶體 1.921GiB／2GiB。輸出 `E/runs/deploy_pre.txt`。
- 部署後（08:23）：health 200、HEAD `84b890e`＝本機 `main`＝`origin/main`、`OOMKilled=false`、`RestartCount=0`、記憶體 665.7MiB（`--reload` 重載，PaddleOCR 預載 7.8 秒）。log 裡的 `SIGTERM` 是重載結束舊程序。輸出 `E/runs/deploy_post.txt`。

## 線上送件

| 批次 | 份數 | 每份耗時 | 記憶體（送完） | 輸出 |
|---|---|---|---|---|
| 部署前，不帶參數 | 電子 D1～D5 | 0.4～0.7 秒 | 1.92GiB（沒變） | `E/runs/c14_online_pre.txt` |
| 部署後，電子不帶／帶參數 | 5＋5 | 0.4～1.0 秒 | 686MiB | `E/runs/c14_online_post_pdf.txt` |
| 部署後，照片不帶／帶參數 | D5p1（劣化 1）、D3p3（劣化 2）、D4p1（劣化 3）各 2 次 | 17.8～25.4 秒 | 最高 1.872GiB，`OOMKilled=false` | `E/runs/c14_online_post_photo.txt` |
| 照片位置的電子對照框 | D5p1、D3p3、D4p1 單頁電子 PDF 帶參數 | 約 0.4 秒 | — | `E/runs/c14_online/ref_*_v2.json` |

照片的部署前對照沒有送：部署前容器閒置記憶體已是 1.92GiB（上限 2GiB），照片 OCR 有 OOM 風險。

複核佇列新增 2 筆（都是 D3p3，帶與不帶參數各 1 筆）：`d9fd8e30-3e21-41fd-b689-38b87f94f586`、`cb5bc14f-00e6-479c-b3ab-d49ba4633905`。本批共 24 次請求，其他 22 次都沒有新增複核項目。

## 判定

指令：`cd backend && LOCAL_STORAGE_PATH=<scratch> venv/bin/python E/check_c14_online.py`，2026-11-11 08:28 執行。輸出 `E/runs/c14_online.txt`，結果是 FAIL 0。

- **C6 不帶參數不變**：
  - 電子 5 份比部署前與部署後的線上回應，除 `file_url`、`stats`、`review_item_id` 以外整份相同。
  - 照片沒有線上部署前的對照；照片的「不帶參數不變」仍以本機量測為準（`docs/testing/transcript-v2-20261109.md`）。
- **C6 帶參數其餘不變**：電子 5 份與照片 3 張比帶參數與不帶參數，`document_fields` 其他鍵、每頁內容（`structured_data` 去 25 欄與 6 清單）、頂層其他鍵都相同；還原後通過帶參數 schema。
- **C5**：電子 5 份帶參數的 `transcript_records` 還原 `value` 後，與不帶參數的相同。
- **C10 電子位置**：
  - 框內文字相同 717/729＝98.4%，有位置 729/740＝98.5%，門檻都是 95%。
  - 兩個數字與本機收案時相同（`docs/testing/transcript-v2-20261109.md`）。
- **C11 照片位置**：
  - 行框包含電子同格值框中心的投影 44/46＝95.7%（門檻 90%），有位置 46/46。
  - 照片 3 張帶參數的 `transcript_records`，與本機同版本程式存的回應（`E/runs/s3_http/<頁>_v2.json`）逐位元相同。

## 收案驗證員的新輸入（2026-11-11）

業主裁定「送 10 張新照片」：驗證員對正式機另送 10 張 C14 沒用過的照片，分別是樣本外 6 張 `E/images/oos/`，以及劣化頁 D1p2、D2p1、D2p3、D5p2。這 10 張在 S3 本機量測都用過，不是從沒出現過的圖。

- 送法：每張帶參數、不帶參數各送一次，再加電子單頁對照框 6 次，一次一張。全程 `OOMKilled=false`、`RestartCount=0`，送前記憶體最高 1.901GiB。
- C11：行框含中心 92/97＝94.8%（門檻 90%），有位置 97/97。樣本外 6 張線上 30/32，與本機 `E/runs/s3_c11_oos.txt` 相同。
- C6 帶參數其餘不變：10/10。
- 複核佇列新增 22 筆，其中 2 筆來自電子單頁 D2p4、D4p2。這兩頁是續頁，主要欄位信心度 0，會進佇列。ID 全部列在 `E/reviews/close-verify-deploy-20261111.md`。

## 沒有驗的範圍

- 照片不帶參數的線上部署前對照（原因見上）。
- `enable_llm=true`，以及 5 份文件以外的版面：同 `docs/testing/transcript-v2-20261109.md` §7。
